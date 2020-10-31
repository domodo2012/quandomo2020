# -*- coding: utf-8 -*-
"""
策略模板基类
"""

from copy import deepcopy
from abc import abstractmethod
from time import sleep, time
from pandas import DataFrame, to_datetime, isna, merge, read_pickle, isnull
from numpy import cov, var, std, nan, hstack
from math import sqrt
from pyecharts import Line, Page
from queue import Empty
# from collections import OrderedDict

from core.const import (
    Product,
    Event,
    Slippage,
    Interval,
    Status,
    Direction,
    Offset,
    StopOrderStatus
)
from core.event import MakeEvent
from core.utility import (
    datetime_to_timestamp,
    timestamp_to_datetime,
    date_str_to_int,
    get_exchange,
    generate_random_id,
    round_to,
    get_symbol_params,
    dict_to_output_table
)
from core.object import OrderData, StopOrder, TradeData
from core.context import Context
from engine.event_manager import EventManager
from data_center.get_data import GetMongoData, GetSqliteData


class EmptyClass(object):
    pass


class StrategyBaseBacktestStock(object):
    def __init__(self, universe_limit):
        self.gateway = 'ctp'
        self.run_mode = None
        self.start = None
        self.end = None
        self.interval = None
        self.account = None
        self.benchmark = None
        self.rights_adjustment = None
        self.universe = None
        self.set_slippage_type = None

        # self.get_data = GetMongoData()  # 从 mongodb 取数据
        self.get_data = GetSqliteData()  # 从 sqlite 取数据
        self.timestamp = None
        self.datetime = None
        self.bar_index = None
        self.bar_len = None
        self.activate_trade_signal = False
        self.is_universe_dynamic = False
        self.universe = None
        self.index_members = DataFrame()
        self.universe_limit = universe_limit

        self.context = Context(self.gateway)  # 记录、计算交易过程中各类信息
        self.fields = ['open', 'high', 'low', 'close', 'volume']

        # 事件驱动引擎实例化
        self.event_engine = EventManager()

        # 各类事件的监听/回调函数注册
        self.event_engine.register(Event.BAR, self.update_bar)
        self.event_engine.register(Event.ORDER, self.handle_order)
        self.event_engine.register(Event.PORTFOLIO, self.handle_portfolio_risk)
        self.event_engine.register(Event.TRADE, self.handle_trade_)
        # self.event_engine.register_general(self.update_bar_info)

        # 绩效指标
        self.performance_indicator = {}

    # 回测滑点设置
    def set_slippage(self,
                     symbol_type=Product.STOCK,
                     slippage_type=Slippage.FIX,
                     value=0):
        self.context.slippage_dict[symbol_type] = {"slippage_type": slippage_type,
                                                   "value": value}

    # 回测手续费和印花税
    def set_commission(self,
                       symbol_type=Product.STOCK,
                       tax=0,
                       open_commission=0,
                       close_commission=0,
                       close_today_commission=0,
                       min_commission=0):
        self.context.commission_dict[symbol_type] = {"tax": tax,
                                                     "open_commission": open_commission,
                                                     "close_commission": close_commission,
                                                     "close_today_commission": close_today_commission,
                                                     "min_commission": min_commission
                                                     }

    def set_black_list(self):
        """设置黑名单"""
        pass

    def run_strategy(self):
        """初始化　account_data"""
        if self.account:
            self.context.init_account(self.account)

        # 从数据库读取数据
        # todo: 现在先将所有数据都取到内存，以后为了减少内存占用，考虑只读入close（每个bar上都要用来计算账户净值，必须读入内存中），
        #  其他数据用到时才从数据库中取，交易次数不多的话，对速度的影响不大。
        if not self.universe:
            self.update_universe(self.start)

        symbol_all_list = self.universe + [self.benchmark]
        daily_data = self.get_data.get_all_market_data(all_symbol_code=symbol_all_list,
                                                       field=self.fields,
                                                       start=self.start,
                                                       end=self.end,
                                                       interval=Interval.DAILY)
        self.context.daily_data = daily_data[daily_data['volume'] > 0]
        # 将 benchmark 的时间轴转成时间戳 list，最后转成迭代器，供推送时间事件用
        self.context.benchmark_index = [datetime_to_timestamp(str(int(i)), '%Y%m%d')
                                        for i in self.context.daily_data["close"].loc[self.benchmark].index]
        bmi_iter = iter(self.context.benchmark_index)

        self.bar_index = 0
        # self.event_engine.start()
        while True:
            # todo：以后外围包裹一个父函数，用来进行时间控制，只在交易时间内启动
            try:
                cur_event = self.event_engine.get()
            except Empty:
                try:
                    self.timestamp = next(bmi_iter)
                    self.datetime = timestamp_to_datetime(self.timestamp, format="%Y%m%d")
                    event_bar = MakeEvent(Event.BAR, self.datetime, self.gateway)
                    self.event_engine.put(event_bar)
                except StopIteration:
                    self.context.logger.info('策略运行完成，开始计算绩效。')
                    break
            else:
                # 监听/回调函数根据事件类型处理事件
                self.event_engine.event_process(cur_event)
                # sleep(0.8)      # 模拟实时行情中每个行情之间的时间间隔

    def deal_limit_order(self, event_bar, cur_mkt_data):
        """处理未成交限价单，如有成交即新建成交事件"""
        # self.context.logger.info("-- this is deal_limit_order() @ {0}".format(event_market.dt))

        # 逐个未成交委托进行判断
        for order in list(self.context.active_limit_orders.values()):
            # 只处理已发出的（状态为“未成交”）未成交委托
            if order.status == Status.SUBMITTING:
                continue

            # 只处理有市场数据的(停牌则当日数据为 -1)
            cur_open = self.get_data.get_market_data(self.context.daily_data,
                                                     all_symbol_code=[order.symbol],
                                                     field=["close"],
                                                     start=event_bar.dt,
                                                     end=event_bar.dt)
            if isna(cur_mkt_data['open'][order.symbol]) or cur_open < 0:
                continue

            long_cross_price = cur_mkt_data['low'][order.symbol]
            short_cross_price = cur_mkt_data['high'][order.symbol]
            long_best_price = cur_mkt_data['open'][order.symbol]
            short_best_price = cur_mkt_data['open'][order.symbol]

            # 检查限价单是否能被成交
            long_cross = ((order.direction == Direction.LONG and order.offset == Offset.OPEN)
                          or (order.direction == Direction.SHORT and order.offset == Offset.CLOSE)
                          and order.price >= long_cross_price > 0
                          )

            short_cross = ((order.direction == Direction.SHORT and order.offset == Offset.OPEN)
                           or (order.direction == Direction.LONG and order.offset == Offset.CLOSE)
                           and order.price <= short_cross_price
                           and short_cross_price > 0
                           )

            if long_cross or short_cross:
                if long_cross:
                    trade_price = min(order.price, long_best_price)
                else:
                    trade_price = max(order.price, short_best_price)

                # 委托单被成交了，相应的属性变更
                order.filled_volume = order.order_volume
                order.filled_datetime = event_bar.dt
                order.filled_price = trade_price
                order.status = Status.ALL_TRADED
                self.context.limit_orders[order.order_id].status = Status.ALL_TRADED

                event_order = MakeEvent(Event.ORDER, event_bar.dt, order)
                self.context.bar_order_data_dict[order.symbol] = deepcopy(order)

                # live状态下的运行逻辑是将 event_order 事件送到队列中，
                # 但是在回测中暂无法并行处理，直接调用 handle_order 更好一些
                # self.event_engine.put(event_order)
                self.handle_order(event_order)

                # 将当前委托单从未成交委托单清单中去掉
                self.context.active_limit_orders.pop(order.order_id)

                # 新建交易事件并送入事件驱动队列中
                trade = TradeData(symbol=order.symbol,
                                  exchange=order.exchange,
                                  order_id=order.order_id,
                                  trade_id=generate_random_id('filled'),
                                  direction=order.direction,
                                  offset=order.offset,
                                  price=trade_price,
                                  volume=order.order_volume,
                                  datetime=event_bar.dt,
                                  gateway=self.gateway,
                                  account=order.account,
                                  frozen=order.order_volume,
                                  symbol_type=order.symbol_type,
                                  comments=order.comments
                                  )

            # 如果委托单本次不能被成交（即挂出买入委托单时价格跳空高开，或者卖出委托单时价格跳空低开）
            # 就将原委托单撤回，按当前 bar 的 open 重新下单
            # elif not long_cross and not short_cross:
            else:
                # 不能正常触发时的处理方式：撤单后追单
                order_new = deepcopy(order)

                # 原委托单撤销
                order.cancel_datetime = event_bar.dt
                self.context.limit_orders[order.order_id].status = Status.WITHDRAW
                self.context.active_limit_orders.pop(order.order_id)

                self.context.logger.info('-- {0} 的委托单 {1} 无法成交，撤回重发'.format(order.symbol, order.order_id))
                event_order = MakeEvent(Event.ORDER, event_bar.dt, order)
                self.handle_order(event_order)

                # 重新下单
                order_new.order_datetime = event_bar.dt
                order_new.order_id = generate_random_id('order')
                order_new.order_price = cur_mkt_data['open'][order_new.symbol]

                self.context.limit_orders[order_new.order_id] = order_new
                self.context.limit_order_count += 1

                event_order = MakeEvent(Event.ORDER, event_bar.dt, order_new)
                if order_new.offset == Offset.OPEN:
                    cur_str = '买入'
                else:
                    cur_str = '卖出'
                self.context.logger.info(
                    "-- 资金账号 {0} 发出委托{1} {2} {3} 股，委托价为 {4}".format(order_new.account,
                                                                    cur_str,
                                                                    order_new.symbol,
                                                                    order_new.order_volume,
                                                                    order_new.order_price))
                self.handle_order(event_order)

                # 新建交易事件并送入事件驱动队列中
                trade = TradeData(symbol=order_new.symbol,
                                  exchange=order_new.exchange,
                                  order_id=order_new.order_id,
                                  trade_id=generate_random_id('filled'),
                                  direction=order_new.direction,
                                  offset=order_new.offset,
                                  price=cur_mkt_data['open'][order.symbol],
                                  volume=order_new.order_volume,
                                  datetime=event_bar.dt,
                                  gateway=self.gateway,
                                  account=order_new.account,
                                  frozen=order_new.order_volume,
                                  symbol_type=order_new.symbol_type,
                                  comments=order_new.comments
                                  )

            # 交易数量 + 1
            self.context.trade_count += 1

            # 及时更新 context 中的成交信息
            # self.context.current_trade_data = trade

            event_trade = MakeEvent(Event.TRADE, event_bar.dt, trade)

            # 更新 context 中的成交、持仓信息
            # self.event_engine.put(event_trade)
            self.handle_trade_(event_trade)

    def deal_stop_order(self, event_bar, cur_mkt_data):
        """处理未成交止损单"""
        # self.context.logger.info("-- this is deal_stop_order() @ {0}.".format(event_market.dt))

        # 逐个未成交委托进行判断
        for stop_order in list(self.context.active_stop_orders.values()):
            long_cross_price = cur_mkt_data['high'][stop_order.symbol]
            short_cross_price = cur_mkt_data['low'][stop_order.symbol]
            long_best_price = cur_mkt_data['open'][stop_order.symbol]
            short_best_price = cur_mkt_data['open'][stop_order.symbol]

            # 检查止损单是否能被触发
            long_cross = (
                    stop_order.direction == Direction.LONG
                    and stop_order.price <= long_cross_price
            )

            short_cross = (
                    stop_order.direction == Direction.SHORT
                    and stop_order.price >= short_cross_price
            )

            # 如果委托单仍然不能被触发，则其所有状态都不改变，继续等待被触发
            if not long_cross and not short_cross:
                continue

            # 否则新增一笔限价单（止损单在本地被触发后，最终以限价单形式发送到交易所）
            self.context.limit_order_count += 1

            order = OrderData(symbol=stop_order.symbol,
                              exchange=get_exchange(stop_order.symbol),
                              order_id=generate_random_id('order'),
                              direction=stop_order.direction,
                              offset=stop_order.offset,
                              price=stop_order.price,
                              order_volume=stop_order.order_volume,
                              filled_volume=stop_order.order_volume,
                              status=Status.ALL_TRADED,
                              account=stop_order.accnt,
                              order_datetime=event_bar.dt,
                              symbol_type=stop_order.symbol_sype,
                              comments=stop_order.comments
                              )

            if long_cross:
                trade_price = max(order.price, long_best_price)
            else:
                trade_price = min(order.price, short_best_price)

            # 委托单被成交了，相应的属性变更
            order.filled_price = trade_price
            order.filled_datetime = event_bar.dt,

            self.context.limit_orders[order.order_id] = order

            # 更新止损单总清单中当前止损单的属性
            self.context.stop_orders[stop_order.order_id].fill_datetime = event_bar.dt
            self.context.stop_orders[stop_order.order_id].status = StopOrderStatus.TRIGGERED

            # 将止损单及其转化成的limit单都加进来，保证信息不丢失
            self.context.bar_order_data_dict[order.symbol] = [deepcopy(order),
                                                              deepcopy(self.context.stop_orders[stop_order.order_id])]

            # 未成交止损单清单中将本止损单去掉
            if stop_order.order_id in self.context.active_stop_orders:
                self.context.active_stop_orders.pop(stop_order.order_id)

            # 止损单被触发，本地止损单转成限价单成交，新增order_event并送入队列中
            # event_order = Event(Event.ORDER, Event.BAR.dt, order)
            # self.event_engine.put(event_order)

            # 止损单被触发，新建一个成交对象
            if long_cross:
                trade_price = max(stop_order.price, long_best_price)
                # pos_change = order.order_volume
            else:
                trade_price = min(stop_order.price, short_best_price)
                # pos_change = -order.order_volume

            self.context.trade_count += 1

            trade = TradeData(symbol=order.symbol,
                              exchange=order.exchange,
                              order_id=order.order_id,
                              trade_id=generate_random_id('filled'),
                              direction=order.direction,
                              offset=order.offset,
                              price=trade_price,
                              volume=order.order_volume,
                              frozen=order.order_volume,
                              datetime=self.datetime,
                              gateway=self.gateway,
                              account=order.account,
                              comments=order.comments
                              )

            # 及时更新 context 中的交易信息
            # self.context.current_trade_data = deepcopy(trade)

            # 新建成交事件，并推送到事件队列中
            event_trade = MakeEvent(Event.TRADE, event_bar.dt, trade)
            # self.event_engine.put(event_trade)
            self.handle_trade_(event_trade)

    def update_bar(self, event_bar):
        """新出现市场事件 Event.BAR 时的监听/回调函数，在回测模式下，模拟委托单的撮合动作"""
        # self.context.logger.info("this is update_bar() @ {0}".format(Event.BAR.dt))

        # 处理股票今日持仓的冻结数量（股票当日买入不能卖出）
        self.update_position_frozen(event_bar.dt)

        self.bar_index += 1

        # 所持头寸要除权除息？
        self.position_rights(event_bar.dt)

        # 所持头寸要换月？
        self.position_move_warehouse(event_bar.dt)

        # 未成交订单中的交易标的物要除权除息？
        self.order_rights(event_bar.dt)

        # 未成交订单中的交易标的物要换月？
        self.order_move_warehouse(event_bar.dt)

        # 取最新的市场数据，看未成交订单在当前 bar 是否能成交
        cur_mkt_data = {'low': {}, 'high': {}, 'open': {}}
        cur_date = date_str_to_int(event_bar.dt)
        position_symbol = [pos.symbol for pos in self.context.active_limit_orders.values()]
        cur_all_symbol = self.universe + position_symbol
        for uii in cur_all_symbol:
            try:
                cur_mkt_data['low'][uii] = self.context.daily_data['low'].loc[uii, cur_date]
                cur_mkt_data['high'][uii] = self.context.daily_data['high'].loc[uii, cur_date]
                cur_mkt_data['open'][uii] = self.context.daily_data['open'].loc[uii, cur_date]
            except KeyError:
                cur_mkt_data['low'][uii] = nan
                cur_mkt_data['high'][uii] = nan
                cur_mkt_data['open'][uii] = nan
        self.deal_limit_order(event_bar, cur_mkt_data)  # 处理委托时间早于当前bar的未成交限价单
        self.deal_stop_order(event_bar, cur_mkt_data)  # 处理委托时间早于当前bar的未成交止损单

        # 更新黑名单
        self.update_black_list(event_bar.dt)

        # 更新合约池
        self.update_universe(event_bar.dt)
        if len(self.universe) > self.universe_limit:
            self.universe = self.universe[:10]

        # 是否有新委托信号
        self.handle_bar(event_bar)

        # 如果当前 bar 没有触发新的交易信号，则看是否会触发投资组合的调整信号
        if not self.activate_trade_signal:
            self.handle_portfolio_risk(event_bar)

        # 当前bar的持仓、账户信息更新
        self.update_bar_info(event_bar)

    def handle_portfolio_risk(self, event_bar):
        """投资组合的调整"""
        # todo: 单一合约的开仓市值是否超过总账户的1 / 3，或者其他限制
        # self.context.logger.info('handle_portfolio_risk method @ {0}'.format(Event.BAR.dt))

        pass

    def handle_trade_(self, event_trade):
        """
        订单成交后，在 context 中更新相关数据:
        1）更新当前交易信息
        2）计算受滑点、手续费因素影响的该笔交易数据变动
        3）在当日交易 dict 中新增该笔交易
        4）当日标的物持仓更新        
        """
        # self.context.logger.info('handle_trade() method @ {0}'.format(event_trade.data.datetime))
        self.context.logger.info('-- {0} 的委托单 {1} 于 {2} 成交，成交价为 {3}'.format(event_trade.data.symbol,
                                                                            event_trade.data.order_id,
                                                                            event_trade.data.datetime,
                                                                            event_trade.data.price))

        cur_symbol = event_trade.data.symbol
        cur_symbol_type = event_trade.data.symbol_type
        symbol_type_short = cur_symbol_type.value.split('_')[0]

        # 更新 context 中的头寸冻结信息
        self.context.current_trade_data = deepcopy(event_trade.data)
        if event_trade.data.offset == Offset.CLOSE:
            self.context.current_trade_data.frozen = 0

        # 计算滑点成交价位
        order_price = self.context.current_trade_data.price
        if self.context.slippage_dict[symbol_type_short]["slippage_type"] == Slippage.FIX:
            if self.context.current_trade_data.offset == Offset.OPEN:
                if self.context.current_trade_data.direction == Direction.LONG:
                    self.context.current_trade_data.price += \
                        self.context.slippage_dict[symbol_type_short]["value"]
                elif self.context.current_trade_data.direction == Direction.SHORT:
                    self.context.current_trade_data.price -= \
                        self.context.slippage_dict[symbol_type_short]["value"]

            elif self.context.current_trade_data.offset == Offset.CLOSE:
                if self.context.current_trade_data.direction == Direction.LONG:
                    self.context.current_trade_data.price -= \
                        self.context.slippage_dict[symbol_type_short]["value"]
                elif self.context.current_trade_data.direction == Direction.SHORT:
                    self.context.current_trade_data.price += \
                        self.context.slippage_dict[symbol_type_short]["value"]

        elif self.context.slippage_dict[symbol_type_short]["slippage_type"] == Slippage.PERCENT:
            if self.context.current_trade_data.offset == Offset.OPEN:
                self.context.current_trade_data.price *= (
                        1 + self.context.slippage_dict[symbol_type_short]["value"])

            elif self.context.current_trade_data.offset == Offset.CLOSE:
                self.context.current_trade_data.price *= (
                        1 - self.context.slippage_dict[symbol_type_short]["value"])
        cur_slippage = self.context.current_trade_data.price - order_price

        # 分市场标的计算手续费率
        commission = self.context.commission_dict[cur_symbol_type]
        trade_balance = self.context.current_trade_data.price * self.context.current_trade_data.volume

        # 计算手续费，并更新考虑了交易手续费后的成交价格（现在暂不考虑）
        total_commission = commission['open_commission']
        cur_commission = 0
        if self.context.current_trade_data.offset == Offset.OPEN:
            cur_commission = max(commission['min_commission'], trade_balance * total_commission)
            # if self.context.current_trade_data.direction == Direction.LONG:
            #     trade_balance += cur_commission
            # elif self.context.current_trade_data.direction == Direction.SHORT:
            #     trade_balance -= cur_commission

        elif self.context.current_trade_data.offset == Offset.CLOSE:
            total_commission = commission['close_commission'] + commission['tax']
            cur_commission = max(commission['min_commission'], trade_balance * total_commission)
            # if self.context.current_trade_data.direction == Direction.LONG:
            #     trade_balance -= cur_commission
            # elif self.context.current_trade_data.direction == Direction.SHORT:
            #     trade_balance += cur_commission

        # 成交对象的信息更新
        symbol_params = get_symbol_params(cur_symbol)
        self.context.current_trade_data.price = trade_balance / self.context.current_trade_data.volume
        self.context.current_trade_data.commission = cur_commission
        self.context.current_trade_data.slippage = cur_slippage
        self.context.current_trade_data.margin = symbol_params['margin']
        self.context.current_trade_data.multiplier = symbol_params['multiplier']
        self.context.current_trade_data.price_tick = symbol_params['price_tick']

        # 把此次成交添加到对应字典中
        self.context.bar_trade_data_dict[cur_symbol] = self.context.current_trade_data

        self.context.current_commission_data = cur_commission
        self.context.bar_commission_data_dict[cur_symbol] = self.context.current_commission_data

        # 根据 event_trade 数据，新建 current_position_data 用于新持仓，如果持仓已有，则这部分就不用了
        contract_params = get_symbol_params(cur_symbol)
        self.context.current_position_data.symbol = event_trade.data.symbol
        self.context.current_position_data.exchange = event_trade.data.exchange
        self.context.current_position_data.account = event_trade.data.account
        self.context.current_position_data.trade_id = event_trade.data.trade_id
        self.context.current_position_data.order_id = event_trade.data.order_id
        self.context.current_position_data.init_datetime = event_trade.data.datetime
        self.context.current_position_data.datetime = event_trade.data.datetime
        self.context.current_position_data.direction = event_trade.data.direction
        self.context.current_position_data.offset = event_trade.data.offset
        self.context.current_position_data.init_volume = event_trade.data.volume
        self.context.current_position_data.volume = event_trade.data.volume
        self.context.current_position_data.frozen = event_trade.data.frozen
        self.context.current_position_data.init_price = event_trade.data.price
        self.context.current_position_data.price = event_trade.data.price
        self.context.current_position_data.symbol_type = event_trade.data.symbol_type
        self.context.current_position_data.gateway = event_trade.data.gateway
        self.context.current_position_data.multiplier = contract_params['multiplier']
        self.context.current_position_data.price_tick = contract_params['price_tick']
        self.context.current_position_data.margin = contract_params['margin']
        self.context.current_position_data.position_value = \
            self.context.current_trade_data.price * event_trade.data.volume
        self.context.current_position_data.position_value_pre = \
            self.context.current_trade_data.price * event_trade.data.volume

        # 根据symbol，将 context 中当前持仓情况按当前交易情况更新
        if self.context.bar_position_data_dict:
            if cur_symbol in self.context.bar_position_data_dict.keys():
                # 当前 bar 已有持仓数据，并且当前 symbol 已有持仓，则仓位根据本次成交的情况调整
                cur_pos = self.context.bar_position_data_dict[cur_symbol]
                position_cost_balance = cur_pos.init_volume * cur_pos.init_price
                trade_balance = self.context.current_trade_data.volume * self.context.current_trade_data.price

                if event_trade.data.offset == Offset.OPEN:
                    total_position = cur_pos.volume + self.context.current_trade_data.volume

                    # 更新持仓成本
                    cur_pos.price = (position_cost_balance + trade_balance) / total_position

                    # 更新持仓数量
                    cur_pos.volume = total_position

                    # 更新冻结数量
                    cur_pos.frozen += self.context.current_trade_data.volume

                elif event_trade.data.offset == Offset.CLOSE:
                    total_position = cur_pos.volume - self.context.current_trade_data.volume

                    # 更新持仓成本
                    if total_position > 0:
                        cur_pos.price = (position_cost_balance - trade_balance) / total_position
                    else:
                        cur_pos.price = 0

                    # 更新持仓数量
                    cur_pos.volume = total_position
            else:
                # 当前 bar 有持仓数据，但是当前 symbol 尚无持仓
                if self.context.current_trade_data.volume > 0:
                    self.context.bar_position_data_dict[cur_symbol] = self.context.current_position_data
        else:
            # 当前 bar 没有持仓数据
            self.context.bar_position_data_dict[cur_symbol] = self.context.current_position_data

        # 更新现金与冻结资金(记得减去手续费)
        if self.context.bar_account_data_dict:
            if self.context.current_trade_data.offset == Offset.OPEN:
                # 更新可用资金(减少)
                self.context.bar_account_data_dict[event_trade.data.account].available -= \
                    self.context.current_trade_data.price * self.context.current_trade_data.volume + \
                    self.context.current_trade_data.commission

                # 更新冻结的资产（增加）
                self.context.bar_account_data_dict[event_trade.data.account].frozen += \
                    self.context.current_trade_data.price * self.context.current_trade_data.volume

                # 更新账户总权益
                self.context.bar_account_data_dict[event_trade.data.account].total_balance = \
                    self.context.bar_account_data_dict[event_trade.data.account].available + \
                    self.context.bar_account_data_dict[event_trade.data.account].frozen
            elif self.context.current_trade_data.offset == Offset.CLOSE:
                # 更新可用资金（增加）
                self.context.bar_account_data_dict[event_trade.data.account].available += \
                    self.context.current_trade_data.price * self.context.current_trade_data.volume - \
                    self.context.current_trade_data.commission

                # 更新冻结的资产（减少）
                self.context.bar_account_data_dict[event_trade.data.account].frozen = 0

                # 更新账户总权益
                self.context.bar_account_data_dict[event_trade.data.account].total_balance = \
                    self.context.bar_account_data_dict[event_trade.data.account].available + \
                    self.context.bar_account_data_dict[event_trade.data.account].frozen

        # 交易完成，相应的委托清除
        self.context.refresh_current_data()

        self.handle_trade(event_trade)

        # 订单状态及时更新
        # self.context.logger.info('--- * update trade info *')

    def handle_timer(self, event_timer):
        """每隔固定时间，就获取一次账户状态数据，只在 live 模式中有效"""
        self.context.logger.info('... di da di, {0} goes, updates account status'.format(event_timer.type_))
        pass

    def update_bar_info(self, event_bar: object):
        """每个bar所有事件都处理完成后，更新该bar下相关数据"""
        # self.context.logger.info('this is update_bar_info() @ {0}'.format(event_market.dt))

        # 清除持仓数量为0的仓位
        self.delete_position_zero()

        # 以当日收盘价计算所持合约的当日pnl，并汇总计算当日账户总pnl、当日账户总值
        self.update_position_and_account_bar_data(event_bar.dt)

        # 将每根bar上的资金、持仓、委托、成交存入以时间戳为键索引的字典变量中
        self.save_current_bar_data(event_bar.dt)

        # 更新当前bar的委托、交易情况
        self.context.refresh_bar_dict()

    def buy(self, dt, account, stock: str, price: float, volume: int, is_stop: bool, comments: str = ''):
        self.send_order(dt, account, stock, Direction.LONG, Offset.OPEN, price, volume, is_stop, comments)

    def sell(self, dt, account, stock: str, price: float, volume: int, is_stop: bool, comments: str = ''):
        self.send_order(dt, account, stock, Direction.LONG, Offset.CLOSE, price, volume, is_stop, comments)

    def sell_short(self, dt, account, stock: str, price: float, volume: int, is_stop: bool, comments: str = ''):
        self.send_order(dt, account, stock, Direction.SHORT, Offset.OPEN, price, volume, is_stop, comments)

    def buy_to_cover(self, dt, account, stock: str, price: float, volume: int, is_stop: bool, comments: str = ''):
        self.send_order(dt, account, stock, Direction.SHORT, Offset.CLOSE, price, volume, is_stop, comments)

    def send_order(self, dt, account, symbol, diretion, offset, price, volume, is_stop, comments):
        symbol_paras = get_symbol_params(symbol)
        price = round_to(price, symbol_paras['price_tick'])
        prior_risk_result = self.prior_risk_control(dt, account, symbol, diretion, offset, price, volume)

        # 委托数量取整
        if prior_risk_result:
            cur_exchange = get_exchange(symbol)
            if cur_exchange in ['SSE', 'SZSE'] and offset == Offset.OPEN:
                cur_order_volume = 100 * int(volume / 100)
            elif cur_exchange in ['SHFE', 'DCE', 'CZCE', 'CFFEX', 'INE', 'SGE']:
                cur_order_volume = int(volume)
            else:
                cur_order_volume = abs(volume)

            if is_stop:
                self.send_stop_order(dt, account, symbol, diretion, offset, price, cur_order_volume, comments)
            else:
                self.send_limit_order(dt, account, symbol, diretion, offset, price, cur_order_volume, comments)
        else:
            self.context.logger.info('*** 事前风控未通过，委托单不发送出去 ***')

    def send_order_portfolio(self, dt, account, stock, diretion, offset, price, volume, comments):
        stock_paras = get_symbol_params(stock)
        price = round_to(price, stock_paras['price_tick'])

        self.send_limit_order(dt, account, stock, diretion, offset, price, volume, comments)

    def send_stop_order(self, dt, account, stock, direction, offset, price, volume, comments):
        self.context.stop_order_count += 1

        stop_order = StopOrder(symbol=stock,
                               exchange=get_exchange(stock),
                               order_id=generate_random_id('stoporder'),
                               direction=direction,
                               offset=offset,
                               price=price,
                               order_volume=volume,
                               account=account,
                               gateway=self.gateway,
                               order_datetime=dt,
                               comments=comments
                               )

        self.context.active_stop_orders[stop_order.order_id] = stop_order
        self.context.stop_orders[stop_order.order_id] = stop_order
        self.context.bar_order_data_dict[stop_order.symbol] = deepcopy(stop_order)

        event_order = MakeEvent(Event.ORDER, dt, stop_order)
        self.event_engine.put(event_order)

    def send_limit_order(self, dt, account, symbol, direction, offset, price, volume, comments):
        self.context.limit_order_count += 1
        cur_exchange = get_exchange(symbol)
        if symbol.split('.')[1] == 'SH':
            cur_symbol_type = Product.STOCK_SH
        elif symbol.split('.')[1] == 'SZ':
            cur_symbol_type = Product.STOCK_SZ
        else:
            cur_symbol_type = Product.FUTURES

        order = OrderData(symbol=symbol,
                          exchange=cur_exchange,
                          order_id=generate_random_id('order'),
                          direction=direction,
                          offset=offset,
                          price=price,
                          order_volume=volume,
                          status=Status.NOT_TRADED,
                          account=account,
                          gateway=self.gateway,
                          order_datetime=dt,
                          comments=comments,
                          symbol_type=cur_symbol_type
                          )

        self.context.active_limit_orders[order.order_id] = order
        self.context.limit_orders[order.order_id] = order
        self.context.bar_order_data_dict[order.symbol] = deepcopy(order)

        event_order = MakeEvent(Event.ORDER, dt, order)
        self.event_engine.put(event_order)

    def data_to_dataframe(self, data_obj, data_dict, output_path):
        data_property = [i for i in dir(data_obj) if i not in dir(deepcopy(EmptyClass()))]
        data_property = [i for i in data_property if i[0] != '_']
        if 'is_active' in data_property:
            data_property.remove('is_active')

        values = []
        for timestamp in self.context.benchmark_index:
            timestamp_data_list = []
            dict_data = dict(data_dict[timestamp])
            if len(dict_data) > 0:
                for k, v in dict_data.items():
                    timestamp_data_list.append([v.__dict__[property_data] for property_data in data_property])
                values.extend(timestamp_data_list)

        all_data = DataFrame(values, columns=data_property)
        all_data.to_pickle(output_path)
        return all_data

    def strategy_analysis(self, output_path):
        """策略的绩效分析"""
        # 1、将 order、trade、position、account 数据转成 dataframe，并以 pkl 格式保存到指定目录
        self.context.backtesting_record_order = self.data_to_dataframe(self.context.current_order_data,
                                                                       self.context.order_data_dict,
                                                                       output_path + 'order_data.pkl')
        self.context.backtesting_record_trade = self.data_to_dataframe(self.context.current_trade_data,
                                                                       self.context.trade_data_dict,
                                                                       output_path + 'trade_data.pkl')
        self.context.backtesting_record_position = self.data_to_dataframe(self.context.current_position_data,
                                                                          self.context.position_data_dict,
                                                                          output_path + 'position_data.pkl')
        self.context.backtesting_record_account = self.data_to_dataframe(self.context.current_account_data,
                                                                         self.context.account_data_dict,
                                                                         output_path + 'account_data.pkl')

        # 2、计算绩效指标
        # 计算 benckmark 的净值
        bm_close = self.get_data.get_market_data(market_data=self.context.daily_data,
                                                 all_symbol_code=[self.benchmark],
                                                 field=['close'],
                                                 start=self.start,
                                                 end=self.end
                                                 )
        bm_nv = bm_close / bm_close.iloc[0]

        # 计算策略的净值，为消除 warning，用中间变量 x 处理一下
        strat_value = self.context.backtesting_record_account[['datetime', 'total_balance']]
        x = strat_value.copy()
        x.loc[:, 'datetime'] = x.loc[:, 'datetime'].apply(date_str_to_int)
        strat_value = x.set_index('datetime')

        strat_nv = strat_value['total_balance'] / strat_value['total_balance'].iloc[0]

        # 计算收益率、年化收益率
        bt_period = (to_datetime(str(self.end)) - to_datetime(str(self.start))).days / 365
        bm_ret = bm_nv.iloc[-1] / bm_nv.iloc[0] - 1
        strat_ret = strat_nv.iloc[-1] / strat_nv.iloc[0] - 1
        bm_annnual_ret_arith = bm_ret / bt_period
        strat_annual_ret_arith = strat_ret / bt_period

        # 计算策略相对基准的 alpha、beta
        bm_chge = bm_close.pct_change()
        bm_chge.iloc[0] = 0
        strat_chge = strat_nv.pct_change()
        strat_chge.iloc[0] = 0
        if len(bm_chge) > 1:
            strat_beta = cov(strat_chge, bm_chge)[0, 1] / var(bm_chge)
        else:
            strat_beta = 0

        risk_free_ret = 0.00
        strat_alpha = strat_ret - risk_free_ret - strat_beta * (bm_ret - risk_free_ret)

        if len(bm_chge) > 0:
            # 计算波动率
            bm_vol = sqrt(252) * std(bm_chge)
            strat_vol = sqrt(252) * std(strat_chge)
        else:
            bm_vol = 0
            strat_vol = 0

        # 计算 sharp 率
        if strat_vol > 0:
            sharp_ratio = (strat_ret - risk_free_ret) / strat_vol
        else:
            sharp_ratio = 0

        # 计算 downside risk 和 sortino ratio
        strat_downside_chge = strat_chge[strat_chge < risk_free_ret]
        if len(strat_downside_chge) > 0:
            downside_risk = std(strat_downside_chge)
            sortino_ratio = (strat_ret - risk_free_ret) / downside_risk
        else:
            downside_risk = 0
            sortino_ratio = 0

        # 计算 tracking error 和 information ratio
        bm_strat_dif = bm_chge - strat_chge
        if len(bm_strat_dif) > 0:
            tracking_error = sqrt(252) * std(bm_strat_dif)
            information_ratio = (strat_annual_ret_arith - bm_annnual_ret_arith) / tracking_error
        else:
            tracking_error = 0
            information_ratio = 0

        # 计算最大回撤（两种方法）
        strat_nv_df = strat_nv.to_frame()
        strat_nv_df['highlevel'] = strat_nv_df['total_balance'].rolling(min_periods=1,
                                                                        window=len(strat_nv_df),
                                                                        center=False).max()
        strat_nv_df['drawdown'] = strat_nv_df['total_balance'] / strat_nv_df['highlevel'] - 1
        drawdown = strat_nv_df['drawdown']

        # drawdown = Series(0., index=bm_nv.index)
        # if len(strat_nv) > 0:
        #     for ii, datei in enumerate(strat_nv.index):
        #         if ii > 0:
        #             dd = 1 - strat_nv[datei] / max(strat_nv.iloc[:ii].values)
        #         else:
        #             dd = 0
        #         drawdown.iloc[ii] = dd

        total_commssion = 0
        for ii in self.context.commission_data_dict.keys():
            cur_dict = self.context.commission_data_dict[ii]
            if cur_dict:
                for jj in cur_dict.keys():
                    total_commssion += cur_dict[jj]

        # 计算每天的持仓数量
        pos_cnt = self.context.backtesting_record_position.groupby(['datetime']).count()['symbol']
        pos_cnt2_index = []
        for ii in pos_cnt.index.values:
            pos_cnt2_index.append(int(''.join(ii.split('-'))))
        pos_cnt.index = pos_cnt2_index
        pos_cnt2 = merge(pos_cnt, drawdown, left_index=True, right_index=True, how='right')['symbol'].fillna(0)

        self.performance_indicator['bm_nv_series'] = bm_nv
        self.performance_indicator['strat_nv_series'] = strat_nv
        self.performance_indicator['strat_drawdown_series'] = drawdown
        self.performance_indicator['pos_cnt_series'] = pos_cnt2

        self.performance_indicator['total commission'] = total_commssion
        self.performance_indicator['bm_ret'] = bm_ret
        self.performance_indicator['strat_ret'] = strat_ret
        self.performance_indicator['bm_annnual_ret_arith'] = bm_annnual_ret_arith
        self.performance_indicator['strat_annual_ret_arith'] = strat_annual_ret_arith
        self.performance_indicator['strat_beta'] = strat_beta
        self.performance_indicator['strat_alpha'] = strat_alpha
        self.performance_indicator['strat_vol'] = strat_vol
        self.performance_indicator['sharp_ratio'] = sharp_ratio
        self.performance_indicator['downside_risk'] = downside_risk
        self.performance_indicator['sortino_ratio'] = sortino_ratio
        self.performance_indicator['tracking_error'] = tracking_error
        self.performance_indicator['information_ratio'] = information_ratio

    def show_results(self, output_path):
        """将策略绩效分析结果保存到 html 文件中"""
        # 结果打印，必须用英文，否则排版有问题
        last_timestamp = list(self.context.account_data_dict)[-1]
        results = {'Start Date': self.start,
                   'End Date': self.end,
                   'Initial Equity': round(self.account[0]['equity'], 2),
                   'Final Equity': round(
                       self.context.account_data_dict[last_timestamp][self.account[0]['name']].total_balance, 2),
                   'total commission': round(self.performance_indicator['total commission'], 4),
                   'Benchmark Annual Return % (arith)': round(self.performance_indicator['bm_annnual_ret_arith'] * 100,
                                                              4),
                   'Strategy Annual Return % (arith)': round(self.performance_indicator['strat_annual_ret_arith'] * 100,
                                                             4),
                   'Strategy Volatility': round(self.performance_indicator['strat_vol'], 4),
                   'Strategy Max Drawdown %': round(min(self.performance_indicator['strat_drawdown_series']), 2) * 100,
                   'Sharp Ratio': round(self.performance_indicator['sharp_ratio'], 4),
                   'Downside Risk': round(self.performance_indicator['downside_risk'], 4),
                   'Sortino Ratio': round(self.performance_indicator['sortino_ratio'], 4),
                   'Tracking Error': round(self.performance_indicator['tracking_error'], 4),
                   'Information Ratio': round(self.performance_indicator['information_ratio'], 4)
                   }

        print(dict_to_output_table(results))

        # 净值、回撤曲线保存到html
        datetime_index = self.performance_indicator['bm_nv_series'].index.values

        page = Page()
        line_net_value = Line("净值曲线", width=1300, height=400, title_pos="8%")
        line_net_value.add("基准的净值曲线", datetime_index,
                           [round(i, 4) for i in self.performance_indicator['bm_nv_series'].values],
                           tooltip_tragger="axis", legend_top="3%", is_datazoom_show=True, yaxis_min='dataMin')
        line_net_value.add("策略的净值曲线", datetime_index,
                           [round(i, 4) for i in self.performance_indicator['strat_nv_series'].values],
                           tooltip_tragger="axis", legend_top="3%", is_datazoom_show=True, yaxis_min='dataMin')
        page.add(line_net_value)

        # for indicator_name, indicator in self.performance_indicator.items():
        self.add_to_page(page, self.performance_indicator['strat_drawdown_series'], '策略的回撤曲线', datetime_index)
        self.add_to_page(page, self.performance_indicator['pos_cnt_series'], '策略的持仓数量曲线', datetime_index)

        cur_datetime = timestamp_to_datetime(int(time()), '%Y%m%d_%H%M%S')
        page.render(path=output_path + "strategy_backtest_" + cur_datetime + ".html")

    def add_to_page(self, page, indicator, indicator_name, datetime_index):
        line = Line(indicator_name, width=1300, height=400, title_pos="8%")
        line.add(indicator_name, datetime_index, indicator,
                 tooltip_tragger="axis", legend_top="3%", is_datazoom_show=True,
                 yaxis_min='dataMin', yaxis_max='dataMax')
        page.add(line)

    def update_position_frozen(self, dt):
        """处理当日情况前，先更新当日股票的持仓冻结数量"""
        if self.bar_index > 0 and self.context.bar_position_data_dict:
            last_timestamp = self.context.benchmark_index[self.bar_index - 1]
            last_day = timestamp_to_datetime(last_timestamp, '%Y%m%d')
            for position_data in self.context.bar_position_data_dict.values():
                cur_close = self.get_data.get_market_data(self.context.daily_data,
                                                          all_symbol_code=[position_data.symbol],
                                                          field=["close"],
                                                          start=dt,
                                                          end=dt)

                if last_day != dt:
                    if cur_close > 0:
                        position_data.frozen = 0

                        # 前日冻结的仓位可以交易了
                        self.context.bar_account_data_dict[position_data.account].frozen = 0
                    else:   # 停牌（价格为 -1），持仓被冻结，不能交易，持仓占用的资金也被冻结
                        position_data.frozen = position_data.volume

                        self.context.bar_account_data_dict[position_data.account].frozen = position_data.position_value


        # print('—— * 更新今仓冻结数量 *')

    def delete_position_zero(self):
        """将数量为0的持仓，从持仓字典中删掉"""
        for symbol in list(self.context.bar_position_data_dict.keys()):
            if self.context.bar_position_data_dict[symbol].volume == 0:
                del self.context.bar_position_data_dict[symbol]

    def update_position_and_account_bar_data(self, dt: str):
        """基于close，更新每个持仓的持仓盈亏，更新账户总资产"""
        dt = dt[:4] + '-' + dt[4:6] + '-' + dt[6:]
        if self.context.bar_position_data_dict:
            for account in self.context.bar_account_data_dict.values():
                hold_balance = 0
                account.datetime = dt
                account.pre_balance = account.total_balance
                for position_data in self.context.bar_position_data_dict.values():
                    if account.account_id == position_data.account:
                        cur_close = self.get_data.get_market_data(self.context.daily_data,
                                                                  all_symbol_code=[position_data.symbol],
                                                                  field=["close"],
                                                                  start=dt,
                                                                  end=dt)

                        position_data.datetime = dt
                        position_data.position_value_pre = position_data.position_value
                        if cur_close > 0:
                            position_data.position_value = position_data.volume * cur_close
                        else:
                            self.context.logger.info('price = -1 {0}'.format(position_data.symbol))
                        hold_balance += position_data.position_value_pre

                        position_data.position_pnl = position_data.position_value - \
                                                     position_data.init_volume * position_data.init_price
                    account.total_balance = account.available + hold_balance
                    account.frozen = hold_balance
        else:
            for account in self.context.bar_account_data_dict.values():
                account.datetime = dt
                account.pre_balance = account.total_balance
                account.total_balance = account.available
                account.frozen = 0

        # print("-- * 以当前bar的close更新账户总体情况")

    def save_current_bar_data(self, dt: str):
        """记录每根bar的信息，包括资金、持仓、委托、成交等"""
        # print('-- save_current_bar_data() @ {0} 记录每根bar的信息，包括资金、持仓、委托、成交'.format(dt))
        cur_timestamp = datetime_to_timestamp(dt)
        self.context.order_data_dict[cur_timestamp] = self.context.bar_order_data_dict
        self.context.trade_data_dict[cur_timestamp] = self.context.bar_trade_data_dict
        self.context.position_data_dict[cur_timestamp] = deepcopy(self.context.bar_position_data_dict)
        self.context.commission_data_dict[cur_timestamp] = deepcopy(self.context.bar_commission_data_dict)
        self.context.account_data_dict[cur_timestamp] = deepcopy(self.context.bar_account_data_dict)

    def prior_risk_control(self, dt, account, symbol, diretion, offset, price, volume):
        """市场数据触发的交易信号，需要事前风控审核"""
        # print('prior_risk_control @ {0}'.format(dt))

        # 黑名单审核。如果 context 中的黑名单能动态更新，这里就不用更新，直接取值判断就可
        if symbol in self.context.black_name_list:
            self.context.is_pass_risk = False
            # print("Order Stock_code in Black_name_list")
            return False

        # 开仓时账户现金要够付持仓保证金，否则撤单
        # 股票视为100%保证金
        # 考虑到手续费、滑点等情况，现金应该多于开仓资金量的 110%
        if offset == 'open':
            contract_params = get_symbol_params(symbol)
            trade_balance = volume * price * contract_params['multiplier'] * contract_params['margin']

            # todo: 原本对账户现金是否足够的判断，需要更细化，现在先笼统处理，下一步在逐个股票的判别时，要有冻结资金的概念
            #       即组合中每个标的物的订单都会冻结一部分资金，后边的股票判断可用现金时要将总现金减去冻结的现金后再判断
            #       类似真实交易终端下单时一样
            if trade_balance / 0.90 > self.context.current_account_data.available / len(self.universe):
                print("Insufficient Available cash")
                return False

        # 平仓时账户中应该有足够头寸，否则撤单
        if offset == 'close':
            # 是否有持仓
            if self.context.bar_position_data_dict:
                # 指定资金账号中是否有指定合约的持仓
                if self.context.bar_position_data_dict[symbol] and \
                        self.context.bar_position_data_dict[symbol].account == account:
                    if volume > (self.context.bar_position_data_dict[symbol].volume -
                                 self.context.bar_position_data_dict[symbol].frozen):
                        print("Insufficient Available Position")
                        return False
                else:
                    print("No Available {0} Position in account {1}".format(symbol, account))
                    return False
            else:
                print("No Position")
                return False

        return True

    def position_rights(self, dt: str):
        """将持仓头寸除权除息"""
        # print('-- * 将持仓头寸除权除息 *')
        if self.context.bar_position_data_dict:
            dt_int = int(dt)
            # 逐个持仓检查，今天是否需要除权除息
            for cur_pos in self.context.bar_position_data_dict.values():
                # 当前持仓今日除权除息
                try:
                    res = cur_pos.symbol in self.context.ex_rights_dict.keys()
                except KeyError:
                    res = False

                if res and dt_int in self.context.ex_rights_dict[cur_pos.symbol].keys():
                    self.context.logger.info('-- {0} 今日 {1} 除权除息，所持仓位量价相应变动'.format(cur_pos.symbol, dt))

                    # 换算当前持仓除权除息之后的量
                    cur_rights_price = cur_pos.position_value / cur_pos.volume
                    cur_dividend = self.context.ex_rights_dict[cur_pos.symbol][dt_int]['CASH_DIVIDEND_RATIO']
                    cur_issue_price = self.context.ex_rights_dict[cur_pos.symbol][dt_int]['RIGHTSISSUE_PRICE']
                    cur_issue_ratio = self.context.ex_rights_dict[cur_pos.symbol][dt_int]['RIGHTSISSUE_RATIO']
                    cur_bonus_ratio = self.context.ex_rights_dict[cur_pos.symbol][dt_int]['BONUS_SHARE_RATIO']
                    cur_conversed_ratio = self.context.ex_rights_dict[cur_pos.symbol][dt_int]['CONVERSED_RATIO']
                    try:
                        price_new = ((cur_rights_price - cur_dividend) + cur_issue_price * cur_issue_ratio) / \
                                    (1 + cur_bonus_ratio + cur_conversed_ratio)
                    except:
                        pass
                    volume_new = (cur_rights_price - cur_dividend) * cur_pos.volume / price_new

                    # 更新持仓与账户信息
                    self.context.bar_account_data_dict[self.account[0]['name']].available += \
                        cur_dividend * cur_pos.volume
                    cur_pos.price = price_new
                    cur_pos.volume = volume_new

    def position_move_warehouse(self, dt: str):
        """期货持仓头寸移仓"""
        # print('-- * 将持仓头寸换月移仓 *')
        if self.context.bar_order_data_dict:
            pass

    def order_rights(self, dt: str):
        """股票订单发出之前，头寸与价格按除权除息折算，买入的话要取整"""
        # print('-- * 将未成交订单除权除息 *')
        if not self.context.ex_rights_dict:
            fields = ['S_INFO_WINDCODE',
                      'EX_DATE',
                      'CASH_DIVIDEND_RATIO',
                      'BONUS_SHARE_RATIO',
                      'RIGHTSISSUE_RATIO',
                      'RIGHTSISSUE_PRICE',
                      'CONVERSED_RATIO']
            self.context.ex_rights_dict = self.get_data.get_ex_rights_data('AShareEXRightDividendRecord',
                                                                           fields,
                                                                           'EX_DATE',
                                                                           self.start)
        if self.context.active_limit_orders:
            dt_int = int(dt)
            for cur_order in list(self.context.active_limit_orders.values()):
                # 逐个未成交委托检查是否需要将委托价格和数量调整
                try:
                    res = cur_order.symbol in self.context.ex_rights_dict
                except KeyError:
                    res = False

                if res and dt_int in self.context.ex_rights_dict[cur_order.symbol].keys():
                    self.context.logger.info('-- {0} 今日 {1} 除权除息，委托单量价相应变动'.format(cur_order.symbol, dt))

                    # 除权除息价 = [(股权登记日收盘价 - 股息）+配股价 * 配股比例 * 配股发行结果] / （1+送股转增导致股份变动比例）
                    cur_price = cur_order.price
                    cur_order_id = cur_order.order_id
                    cur_dividend = self.context.ex_rights_dict[cur_order.symbol][dt_int]['CASH_DIVIDEND_RATIO']
                    cur_issue_price = self.context.ex_rights_dict[cur_order.symbol][dt_int]['RIGHTSISSUE_PRICE']
                    cur_issue_ratio = self.context.ex_rights_dict[cur_order.symbol][dt_int]['RIGHTSISSUE_RATIO']
                    cur_bonus_ratio = self.context.ex_rights_dict[cur_order.symbol][dt_int]['BONUS_SHARE_RATIO']
                    cur_conversed_ratio = self.context.ex_rights_dict[cur_order.symbol][dt_int]['CONVERSED_RATIO']
                    price_new = ((cur_price - cur_dividend) + cur_issue_price * cur_issue_ratio) / \
                                (1 + cur_bonus_ratio + cur_conversed_ratio)
                    volume_new = (cur_price - cur_dividend) * cur_order.order_volume / price_new

                    # 更新持仓信息：原委托单撤除，按新参数发出新委托单
                    order_new = deepcopy(cur_order)
                    order_new.order_id = generate_random_id('order')
                    order_new.order_datetime = dt
                    order_new.price = price_new
                    order_new.order_volume = volume_new

                    self.context.active_limit_orders[order_new.order_id] = order_new
                    self.context.active_limit_orders.pop(cur_order.order_id)

                    self.context.limit_orders[cur_order.order_id].status = Status.WITHDRAW
                    self.context.limit_orders[cur_order.order_id].cancel_datetime = dt
                    order_event = MakeEvent(Event.ORDER, dt, cur_order)
                    self.handle_order(order_event)
                    # self.context.logger.info(
                    #     "-- {0} 的委托单 {1} 当前状态是 {2}".format(cur_order.symbol, cur_order.order_id, cur_order.status))

                    self.context.limit_orders[order_new.order_id] = order_new
                    if order_new.offset == Offset.OPEN:
                        offset_str = '买入'
                    else:
                        offset_str = '卖出'
                    self.context.logger.info(
                        "-- 资金账号 {0} 发出委托{0} {1} {2} 股，委托价为 {3}".format(order_new.account, offset_str,
                                                                        order_new.symbol, order_new.price))
                    order_event = MakeEvent(Event.ORDER, dt, order_new)
                    self.handle_order(order_event)

    def order_move_warehouse(self, dt: str):
        """期货订单发出之前，如果主力合约换月，需要将持仓移仓"""
        # print('-- * 将订单中的合约换月移仓 *')
        if self.context.bar_order_data_dict:
            pass

    def update_universe(self, dt: str):
        # print('-- * 合约池更新 *')
        update_universe = False
        if isinstance(self.is_universe_dynamic, str):
            update_universe = True

            if len(self.index_members.index) == 0:
                self.index_members = \
                    read_pickle(r'D:/python projects/quandomo/data_center/data/xctushare/hs300_members.pkl')

        # 动态股票池，每天更新一次股票池
        if update_universe:
            dt_int = int(dt)
            try:
                cur_universe1 = self.index_members[(self.index_members['in_date'] <= dt_int) & (self.index_members['out_date'] > dt_int)]['stock_code'].values
                cur_universe2 = self.index_members[(self.index_members['in_date'] <= dt_int) & (self.index_members['out_date'] == 0)]['stock_code'].values
                cur_universe = set(hstack((cur_universe1, cur_universe2)))
            except BaseException:
                pass
            else:
                self.universe = list(cur_universe)

    def update_black_list(self, dt: str):
        # print('-- * 黑名单更新 *')
        self.context.black_name_list = []

    @abstractmethod
    def init_strategy(self, log_name):
        pass

    @abstractmethod
    def handle_bar(self, event):
        pass

    @abstractmethod
    def handle_order(self, event_order):
        pass

    @abstractmethod
    def handle_trade(self, event_trade):
        pass
