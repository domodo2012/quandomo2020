# -*- coding: utf-8 -*-
"""
策略模板基类
"""
from copy import deepcopy
from abc import abstractmethod
from queue import Empty
from time import sleep, time
from pandas import DataFrame, to_datetime, Series
from numpy import cov, var, std
from math import sqrt
from pyecharts import Line, Page

from core.const import *
from core.event import Event
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
from data_center.get_data import GetData


class EmptyClass(object):
    pass


class StrategyBaseBacktestStock(object):
    def __init__(self):
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

        self.get_data = GetData()  # 从 mongodb 取数据
        self.timestamp = None
        self.datetime = None
        self.bar_index = None
        self.bar_len = None
        self.activate_trade_signal = False

        self.pos = {}  # 某些合约每个bar的动态持仓总值，用于下单时判断持仓
        self.context = Context(self.gateway)  # 记录、计算交易过程中各类信息
        # self.fields = ['open', 'high', 'low', 'close', 'order_volume', 'open_interest']
        self.fields = ['open', 'high', 'low', 'close', 'volume']

        # 事件驱动引擎实例化
        self.event_engine = EventManager()

        # 各类事件的监听/回调函数注册
        self.event_engine.register(EVENT_BAR, self.update_bar)
        self.event_engine.register(EVENT_ORDER, self.handle_order)
        self.event_engine.register(EVENT_PORTFOLIO, self.handle_portfolio_risk)
        self.event_engine.register(EVENT_TRADE, self.handle_trade)
        # self.event_engine.register_general(self.update_bar_info)

        # 绩效指标
        self.performance_indicator = {}

    # 回测滑点设置
    def set_slippage(self,
                     symbol_type=Product_STOCK,
                     slippage_type=SLIPPAGE_FIX,
                     value=0):
        self.context.slippage_dict[symbol_type] = {"slippage_type": slippage_type,
                                                  "value": value}

    # 回测手续费和印花税
    def set_commission(self,
                       symbol_type=Product_STOCK,
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
        stk_all_list = self.universe + [self.benchmark]
        self.context.daily_data = self.get_data.get_all_market_data(stock_code=stk_all_list,
                                                                    field=self.fields,
                                                                    start=self.start,
                                                                    end=self.end,
                                                                    interval=Interval_DAILY)
        # 生成 benchmark 的 bar_index 数据
        self.context.benchmark_index = [datetime_to_timestamp(str(int(i)), '%Y%m%d')
                                        for i in self.context.daily_data["close"].loc[self.benchmark].index]
        # 将benchmark的时间戳做成迭代器
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
                    event_market = Event(EVENT_BAR, self.datetime, self.gateway)
                    self.event_engine.put(event_market)
                except StopIteration:
                    print('策略运行完成')
                    # self.strategy_analysis()
                    # self.show_results()
                    break
            else:
                # 监听/回调函数根据事件类型处理事件
                self.event_engine.event_process(cur_event)
                # sleep(0.1)      # 模拟实时行情中每个行情之间的时间间隔

    def cross_limit_order(self, event_market, cur_mkt_data):
        """处理未成交限价单，如有成交即新建成交事件"""
        print("-- this is cross_limit_order() @ {0}".format(event_market.dt))

        # 逐个未成交委托进行判断
        for order in list(self.context.active_limit_orders.values()):
            # 只处理已发出的（状态为“未成交”）未成交委托
            if order.status == Status_SUBMITTING:
                continue

            long_cross_price = cur_mkt_data['low'][order.symbol]
            short_cross_price = cur_mkt_data['high'][order.symbol]
            long_best_price = cur_mkt_data['open'][order.symbol]
            short_best_price = cur_mkt_data['open'][order.symbol]

            # 检查限价单是否能被成交
            long_cross = ((order.direction == Direction_LONG and order.offset == Offset_OPEN)
                          or (order.direction == Direction_SHORT and order.offset == Offset_CLOSE)
                          and order.price >= long_cross_price > 0
                          )

            short_cross = ((order.direction == Direction_SHORT and order.offset == Offset_OPEN)
                           or (order.direction == Direction_LONG and order.offset == Offset_CLOSE)
                           and order.price <= short_cross_price
                           and short_cross_price > 0
                           )

            # 如果委托单仍然不能被成交，则其所有状态都不改变，继续等待被成交
            if not long_cross and not short_cross:
                continue

            if long_cross:
                trade_price = min(order.price, long_best_price)
                # pos_change = order.order_volume
            else:
                trade_price = max(order.price, short_best_price)
                # pos_change = -order.order_volume

            # 委托单被成交了，相应的属性变更
            order.filled_volume = order.order_volume
            order.filled_datetime = event_market.dt
            order.filled_price = trade_price
            order.status = Status_ALL_TRADED
            self.context.limit_orders[order.order_id].status = Status_ALL_TRADED
            event_order = Event(EVENT_ORDER, event_market.dt, order)

            self.context.bar_order_data_dict[order.symbol] = deepcopy(order)

            # live状态下的运行逻辑是将 event_order 事件送到队列中，
            # 但是在回测中暂无法并行处理，直接调用 handle_order 更好一些
            # self.event_engine.put(event_order)
            self.handle_order(event_order)

            # 将当前委托单从未成交委托单清单中去掉
            self.context.active_limit_orders.pop(order.order_id)

            # 交易数量 + 1
            self.context.trade_count += 1

            # 新建交易事件并送入事件驱动队列中
            trade = TradeData(symbol=order.symbol,
                              exchange=order.exchange,
                              order_id=order.order_id,
                              trade_id=generate_random_id('filled'),
                              direction=order.direction,
                              offset=order.offset,
                              price=trade_price,
                              volume=order.order_volume,
                              datetime=event_market.dt,
                              gateway=self.gateway,
                              account=order.account,
                              frozen=order.order_volume,
                              symbol_type=order.symbol_type,
                              comments=order.comments
                              )
            # self.pos[trade.symbol] += pos_change

            # 及时更新 context 中的成交信息
            # self.context.current_trade_data = trade

            event_trade = Event(EVENT_TRADE, event_market.dt, trade)

            # 更新 context 中的成交、持仓信息
            # self.event_engine.put(event_trade)
            self.handle_trade_(event_trade)

    def cross_stop_order(self, event_market, cur_mkt_data):
        """处理未成交止损单"""
        print("-- this is cross_stop_order() @ {0}.".format(event_market.dt))

        # 逐个未成交委托进行判断
        for stop_order in list(self.context.active_stop_orders.values()):
            long_cross_price = cur_mkt_data['high'][stop_order.symbol]
            short_cross_price = cur_mkt_data['low'][stop_order.symbol]
            long_best_price = cur_mkt_data['open'][stop_order.symbol]
            short_best_price = cur_mkt_data['open'][stop_order.symbol]

            # 检查止损单是否能被触发
            long_cross = (
                    stop_order.direction == Direction_LONG
                    and stop_order.price <= long_cross_price
            )

            short_cross = (
                    stop_order.direction == Direction_SHORT
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
                              status=Status_ALL_TRADED,
                              account=stop_order.accnt,
                              order_datetime=event_market.dt,
                              symbol_type=stop_order.symbol_sype,
                              comments=stop_order.comments
                              )

            if long_cross:
                trade_price = max(order.price, long_best_price)
            else:
                trade_price = min(order.price, short_best_price)

            # 委托单被成交了，相应的属性变更
            order.filled_price = trade_price
            order.filled_datetime = event_market.dt,

            self.context.limit_orders[order.order_id] = order

            # 更新止损单总清单中当前止损单的属性
            self.context.stop_orders[stop_order.order_id].fill_datetime = event_market.dt
            self.context.stop_orders[stop_order.order_id].status = StopOrderStatus_TRIGGERED

            # 将止损单及其转化成的limit单都加进来，保证信息不丢失
            self.context.bar_order_data_dict[order.symbol] = [deepcopy(order),
                                                              deepcopy(self.context.stop_orders[stop_order.order_id])]

            # 未成交止损单清单中将本止损单去掉
            if stop_order.order_id in self.context.active_stop_orders:
                self.context.active_stop_orders.pop(stop_order.order_id)

            # 止损单被触发，本地止损单转成限价单成交，新增order_event并送入队列中
            # event_order = Event(EVENT_ORDER, event_bar.dt, order)
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
            # self.pos[trade.symbol] += pos_change

            # 及时更新 context 中的交易信息
            # self.context.current_trade_data = deepcopy(trade)

            # 新建成交事件，并推送到事件队列中
            event_trade = Event(EVENT_TRADE, event_market.dt, trade)
            # self.event_engine.put(event_trade)
            self.handle_trade_(event_trade)

    def update_bar(self, event_bar):
        """新出现市场事件 event_bar 时的监听/回调函数，在回测模式下，模拟委托单的撮合动作"""
        print("this is update_bar() @ {0}".format(event_bar.dt))

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
        for uii in self.universe:
            cur_mkt_data['low'][uii] = self.context.daily_data['low'].loc[uii, cur_date]
            cur_mkt_data['high'][uii] = self.context.daily_data['high'].loc[uii, cur_date]
            cur_mkt_data['open'][uii] = self.context.daily_data['open'].loc[uii, cur_date]
        self.cross_limit_order(event_bar, cur_mkt_data)  # 处理委托时间早于当前bar的未成交限价单
        self.cross_stop_order(event_bar, cur_mkt_data)  # 处理委托时间早于当前bar的未成交止损单

        # 更新黑名单
        self.update_black_list(event_bar.dt)

        # 更新合约池
        self.update_symbol_pool(event_bar.dt)

        # 是否有新委托信号
        self.handle_bar(event_bar)

        # 如果当前 bar 没有触发新的交易信号，则看是否会触发投资组合的调整信号
        if not self.activate_trade_signal:
            self.handle_portfolio_risk(event_bar)
            # self.activate_trade_signal = False

        # 当前bar的持仓、账户信息更新
        self.update_bar_info(event_bar)

    def handle_portfolio_risk(self, event_bar):
        """投资组合的调整"""
        # todo: 单一合约的开仓市值是否超过总账户的1 / 3，或者其他限制
        print('handle_portfolio_risk method @ {0}'.format(event_bar.dt))

        pass

    def handle_trade_(self, event_trade):
        """
        订单成交后，在 context 中更新相关数据:
        1）更新当前交易信息
        2）计算受滑点、手续费因素影响的该笔交易数据变动
        3）在当日交易 dict 中新增该笔交易
        4）当日标的物持仓更新        
        """
        print('handle_trade() method @ {0}'.format(event_trade.data.datetime))

        cur_symbol = event_trade.data.symbol
        cur_symbol_type = event_trade.data.symbol_type
        symbol_type_short = cur_symbol_type.split('_')[0]

        # 更新 context 中的当前成交信息
        self.context.current_trade_data = deepcopy(event_trade.data)

        # 计算滑点成交价位
        if self.context.slippage_dict[symbol_type_short]["slippage_type"] == SLIPPAGE_FIX:
            if self.context.current_trade_data.offset == Offset_OPEN:
                if self.context.current_trade_data.direction == Direction_LONG:
                    self.context.current_trade_data.price += \
                        self.context.slippage_dict[symbol_type_short]["value"]
                elif self.context.current_trade_data.direction == Direction_SHORT:
                    self.context.current_trade_data.price -= \
                        self.context.slippage_dict[symbol_type_short]["value"]

            elif self.context.current_trade_data.offset == Offset_CLOSE:
                if self.context.current_trade_data.direction == Direction_LONG:
                    self.context.current_trade_data.price -= \
                        self.context.slippage_dict[symbol_type_short]["value"]
                elif self.context.current_trade_data.direction == Direction_SHORT:
                    self.context.current_trade_data.price += \
                        self.context.slippage_dict[symbol_type_short]["value"]

        elif self.context.slippage_dict[symbol_type_short]["slippage_type"] == SLIPPAGE_PERCENT:
            if self.context.current_trade_data.offset == Offset_OPEN:
                self.context.current_trade_data.price *= (
                        1 + self.context.slippage_dict[symbol_type_short]["value"])

            elif self.context.current_trade_data.offset == Offset_CLOSE:
                self.context.current_trade_data.price *= (
                        1 - self.context.slippage_dict[symbol_type_short]["value"])

        # 分市场标的计算手续费率
        commission = self.context.commission_dict[cur_symbol_type]
        trade_balance = self.context.current_trade_data.price * self.context.current_trade_data.volume

        # 更新考虑了交易手续费后的成交价格
        total_commission = commission['open_commission']
        cur_commission = 0
        if self.context.current_trade_data.offset == Offset_OPEN:
            cur_commission = max(commission['min_commission'], trade_balance * total_commission)
            if self.context.current_trade_data.direction == Direction_LONG:
                trade_balance += cur_commission
            elif self.context.current_trade_data.direction == Direction_SHORT:
                trade_balance -= cur_commission

        elif self.context.current_trade_data.offset == Offset_CLOSE:
            total_commission = commission['close_commission'] + commission['tax']
            cur_commission = max(commission['min_commission'], trade_balance * total_commission)
            if self.context.current_trade_data.direction == Direction_LONG:
                trade_balance -= cur_commission
            elif self.context.current_trade_data.direction == Direction_SHORT:
                trade_balance += cur_commission

        self.context.current_trade_data.price = trade_balance / self.context.current_trade_data.volume

        self.context.current_commission_data = cur_commission
        self.context.bar_commission_data_dict[cur_symbol] = self.context.current_commission_data

        # 把此次成交添加到对应字典中
        self.context.bar_trade_data_dict[cur_symbol] = self.context.current_trade_data

        # 根据 event_trade 数据，新建 current_position_data 用于新持仓，如果持仓已有，则这部分就不用了
        contract_params = get_symbol_params(cur_symbol)
        self.context.current_position_data.symbol = event_trade.data.symbol
        self.context.current_position_data.exchange = event_trade.data.exchange
        self.context.current_position_data.account = event_trade.data.account
        self.context.current_position_data.trade_id = event_trade.data.trade_id
        self.context.current_position_data.order_id = event_trade.data.order_id
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

        # 根据symbol，将 context 中当前持仓情况按当前交易情况更新
        if self.context.bar_position_data_dict:
            if cur_symbol in self.context.bar_position_data_dict.keys():
                # 当前 bar 已有持仓数据，并且当前 symbol 已有持仓，则仓位根据本次成交的情况调整
                cur_pos = self.context.bar_position_data_dict[cur_symbol]
                position_cost_balance = cur_pos.init_volume * cur_pos.init_price
                trade_balance = self.context.current_trade_data.volume * self.context.current_trade_data.price

                if event_trade.data.offset == Offset_OPEN:
                    total_position = cur_pos.volume + self.context.current_trade_data.volume

                    # 更新持仓成本
                    cur_pos.price = (position_cost_balance + trade_balance) / total_position

                    # 更新持仓数量
                    cur_pos.volume = total_position

                    # 更新冻结数量
                    cur_pos.frozen += self.context.current_trade_data.volume

                elif event_trade.data.offset == Offset_CLOSE:
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

        # 更新现金与冻结资金
        if self.context.bar_account_data_dict:
            if self.context.current_trade_data.offset == Offset_OPEN:
                # 更新可用资金(减少)
                self.context.bar_account_data_dict[event_trade.data.account].available -= \
                    self.context.current_trade_data.price * self.context.current_trade_data.volume

                # 更新冻结的资产（增加）
                self.context.bar_account_data_dict[event_trade.data.account].frozen += \
                    self.context.current_trade_data.price * self.context.current_trade_data.volume
            elif self.context.current_trade_data.offset == Offset_CLOSE:
                self.context.bar_account_data_dict[event_trade.data.account].available += \
                    self.context.current_trade_data.price * self.context.current_trade_data.volume

        # 交易完成，相应的委托清除
        self.context.refresh_current_data()

        self.handle_trade()

        # 订单状态及时更新
        print('--- * update trade info *')

    def handle_timer(self, event_timer):
        """每隔固定时间，就获取一次账户状态数据，只在 live 模式中有效"""
        print('... di da di, {0} goes, updates account status'.format(event_timer.type_))
        pass

    def update_bar_info(self, event_market: object):
        """每个bar所有事件都处理完成后，更新该bar下总体情况，内容包括：
        1、持仓数量为0的仓位，清掉；
        2、以当日收盘价计算所持合约的当日pnl，并汇总得到当日账户总pnl,计算当日账户总值；
        3、将每根bar上的资金、持仓、委托、成交存入以时间戳为键索引的字典变量中；
        4、更新当前bar的委托、交易情况
        """
        print('this is update_bar_info() @ {0}'.format(event_market.dt))

        self.delete_position_zero()
        self.update_position_and_account_bar_data(event_market.dt)
        self.save_current_bar_data(event_market.dt)
        self.context.refresh_bar_dict()

    def buy(self, dt, account, stock: str, price: float, volume: int, is_stop: bool, comments: str = ''):
        self.send_order(dt, account, stock, Direction_LONG, Offset_OPEN, price, volume, is_stop, comments)

    def sell(self, dt, account, stock: str, price: float, volume: int, is_stop: bool, comments: str = ''):
        self.send_order(dt, account, stock, Direction_LONG, Offset_CLOSE, price, volume, is_stop, comments)

    def sell_short(self, dt, account, stock: str, price: float, volume: int, is_stop: bool, comments: str = ''):
        self.send_order(dt, account, stock, Direction_SHORT, Offset_OPEN, price, volume, is_stop, comments)

    def buy_to_cover(self, dt, account, stock: str, price: float, volume: int, is_stop: bool, comments: str = ''):
        self.send_order(dt, account, stock, Direction_SHORT, Offset_CLOSE, price, volume, is_stop, comments)

    def send_order(self, dt, account, symbol, diretion, offset, price, volume, is_stop, comments):
        symbol_paras = get_symbol_params(symbol)
        price = round_to(price, symbol_paras['price_tick'])
        prior_risk_result = self.prior_risk_control(dt, account, symbol, diretion, offset, price, volume)

        # 委托数量取整
        if prior_risk_result:
            cur_exchange = get_exchange(symbol)
            if cur_exchange in ['SSE', 'SZSE'] and offset == Offset_OPEN:
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
            print('*** 事前风控未通过，委托单不发送出去 ***')

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

        event_order = Event(EVENT_ORDER, dt, stop_order)
        self.event_engine.put(event_order)

    def send_limit_order(self, dt, account, symbol, direction, offset, price, volume, comments):
        self.context.limit_order_count += 1
        cur_exchange = get_exchange(symbol)
        if symbol.split('.')[1] == 'SH':
            cur_symbol_type = Product_STOCK_SH
        elif symbol.split('.')[1] == 'SZ':
            cur_symbol_type = Product_STOCK_SZ
        else:
            cur_symbol_type = Product_FUTURES

        order = OrderData(symbol=symbol,
                          exchange=cur_exchange,
                          order_id=generate_random_id('order'),
                          direction=direction,
                          offset=offset,
                          price=price,
                          order_volume=volume,
                          status=Status_NOT_TRADED,
                          account=account,
                          gateway=self.gateway,
                          order_datetime=dt,
                          comments=comments,
                          symbol_type=cur_symbol_type
                          )

        self.context.active_limit_orders[order.order_id] = order
        self.context.limit_orders[order.order_id] = order
        self.context.bar_order_data_dict[order.symbol] = deepcopy(order)

        event_order = Event(EVENT_ORDER, dt, order)
        self.event_engine.put(event_order)

    def data_to_dataframe(self, data_obj, data_dict, fpath):
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
        all_data.to_pickle(fpath)
        return all_data

    def strategy_analysis(self, fpath):
        """策略的绩效分析"""
        # 1、将 order、trade、position、account 数据转成 dataframe，并以 pkl 格式保存到指定目录
        self.context.backtesting_record_order = self.data_to_dataframe(self.context.current_order_data,
                                                                       self.context.order_data_dict,
                                                                       fpath + 'order_data.pkl')
        self.context.backtesting_record_trade = self.data_to_dataframe(self.context.current_trade_data,
                                                                       self.context.trade_data_dict,
                                                                       fpath + 'trade_data.pkl')
        self.context.backtesting_record_position = self.data_to_dataframe(self.context.current_position_data,
                                                                          self.context.position_data_dict,
                                                                          fpath + 'position_data.pkl')
        self.context.backtesting_record_account = self.data_to_dataframe(self.context.current_account_data,
                                                                         self.context.account_data_dict,
                                                                         fpath + 'account_data.pkl')

        # 2、计算绩效指标
        # 计算 benckmark 的净值
        bm_close = self.get_data.get_market_data(market_data=self.context.daily_data,
                                                 stock_code=[self.benchmark],
                                                 field=['close'],
                                                 start=self.start,
                                                 end=self.end
                                                 )
        bm_nv = bm_close / bm_close.iloc[0]

        # 计算策略的净值
        strat_value = self.context.backtesting_record_account[['datetime', 'total_balance']]
        strat_value = strat_value.set_index('datetime')
        strat_nv = strat_value['total_balance'] / strat_value['total_balance'].iloc[0]

        # 计算收益率、年化收益率
        bt_period = (to_datetime(str(self.end)) - to_datetime(str(self.start))).days / 365
        bm_ret = bm_nv.iloc[0] / bm_nv.iloc[-1] - 1
        strat_ret = strat_nv.iloc[0] / strat_nv.iloc[-1] - 1
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

        risk_free_ret = 0.03
        strat_alpha = strat_nv.iloc[-1] / strat_nv.iloc[0] - 1 - risk_free_ret - \
                      strat_beta * (bm_nv.iloc[-1] / bm_nv.iloc[0] - 1 - risk_free_ret)

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
        strat_downside_chge = strat_chge[strat_chge > risk_free_ret]
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

        # 计算最大回撤
        drawdown = Series(0., index=bm_nv.index)
        if len(strat_nv) > 0:
            for ii in strat_nv.index:
                dd = 1 - strat_nv[ii] / max(strat_nv.loc[:ii].values)
                drawdown.iloc[ii] = dd

        self.performance_indicator['bm_nv_series'] = bm_nv
        self.performance_indicator['strat_nv_series'] = strat_nv
        self.performance_indicator['strat_drawdown_series'] = drawdown

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

    def show_results(self, fpath):
        """将策略绩效分析结果保存到 html 文件中"""
        # 结果打印
        last_timestamp = list(self.context.account_data_dict)[-1]
        results = {'开始时间': self.start,
                   '结束时间': self.end,
                   '期初资金': self.account[0]['equity'],
                   '期末资金': round_to(self.context.account_data_dict[last_timestamp][self.account[0]['name']].total_balance, 4),
                   '基准年化算术回报率': round_to(self.performance_indicator['bm_annnual_ret_arith'], 4),
                   '策略年化算术回报率': round_to(self.performance_indicator['strat_annual_ret_arith'], 4),
                   '策略波动率': round_to(self.performance_indicator['strat_vol'], 4),
                   '策略最大回测率': round_to(self.performance_indicator['strat_drawdown_series'].iloc[-1], 4),
                   '策略 sharp ratio': round_to(self.performance_indicator['sharp_ratio'], 4),
                   '策略 downside risk': round_to(self.performance_indicator['downside_risk'], 4),
                   '策略 sortino ratio': round_to(self.performance_indicator['sortino_ratio'], 4),
                   '策略 tracking error': round_to(self.performance_indicator['tracking_error'], 4),
                   '策略 information ratio': round_to(self.performance_indicator['information_ratio'], 4)
                   }

        print(dict_to_output_table(results))

        # 展示曲线保存到html
        datetime_index = self.performance_indicator['bm_nv_series'].index.values

        # page = Page("strategy backtesting indicator")
        page = Page()
        line_net_value = Line("net_asset_value", width=1300, height=400, title_pos="8%")
        line_net_value.add("benchmark_net_asset_value", datetime_index,
                           [round(i, 4) for i in self.performance_indicator['bm_nv_series'].values],
                           tooltip_tragger="axis", legend_top="3%", is_datazoom_show=True)
        line_net_value.add("strategy_net_asset_value", datetime_index,
                           [round(i, 4) for i in self.performance_indicator['strat_nv_series'].values],
                           tooltip_tragger="axis", legend_top="3%", is_datazoom_show=True)
        page.add(line_net_value)

        for indicator_name, indicator in self.performance_indicator.items():
            self.add_to_page(page, indicator, indicator_name, datetime_index)

        # 生成本地 HTML 文件
        cur_datetime = timestamp_to_datetime(int(time()), '%Y%m%d_%H%M%S')
        page.render(path=fpath + "strategy_backtest_" + cur_datetime + ".html")

    def add_to_page(self, page, indicator, indicator_name, datetime_index):
        line = Line(indicator_name, width=1300, height=400, title_pos="8%")
        try:
            line.add(indicator_name, datetime_index, indicator,
                     tooltip_tragger="axis", legend_top="3%", is_datazoom_show=True)
            page.add(line)
        except:
            pass

    def update_position_frozen(self, dt):
        """处理当日情况前，先更新当日股票的持仓冻结数量"""
        if self.bar_index > 0 and self.context.bar_position_data_dict:
            last_timestamp = self.context.benchmark_index[self.bar_index - 1]
            last_day = timestamp_to_datetime(last_timestamp, '%Y%m%d')
            for position_data in self.context.bar_position_data_dict.values():
                if last_day != dt:
                    position_data.frozen = 0

                    # 前日所有冻结的资产都释放出来
                    if self.context.bar_account_data_dict[position_data.account].frozen != 0:
                        self.context.bar_account_data_dict[position_data.account].frozen = 0
                    print('—— * 更新今仓冻结数量 *')

        pass

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
                                                                  stock_code=[position_data.symbol],
                                                                  field=["close"],
                                                                  start=dt,
                                                                  end=dt)
                        hold_balance += position_data.volume * cur_close
                        position_data.datetime = dt
                        position_data.position_pnl = \
                            position_data.volume * cur_close - position_data.init_volume * position_data.init_price
                    account.total_balance = account.available + hold_balance
        else:
            for account in self.context.bar_account_data_dict.values():
                account.datetime = dt
                account.pre_balance = account.total_balance

        print("-- * 以当前bar的close更新账户总体情况")

    def save_current_bar_data(self, dt: str):
        """记录每根bar的信息，包括资金、持仓、委托、成交等"""
        print('-- save_current_bar_data() @ {0} 记录每根bar的信息，包括资金、持仓、委托、成交'.format(dt))
        cur_timestamp = datetime_to_timestamp(dt)
        self.context.order_data_dict[cur_timestamp] = self.context.bar_order_data_dict
        self.context.trade_data_dict[cur_timestamp] = self.context.bar_trade_data_dict
        self.context.position_data_dict[cur_timestamp] = deepcopy(self.context.bar_position_data_dict)
        self.context.commission_data_dict[cur_timestamp] = deepcopy(self.context.bar_commission_data_dict)
        self.context.account_data_dict[cur_timestamp] = deepcopy(self.context.bar_account_data_dict)

    def position_rights(self, dt: str):
        """将持仓头寸除权除息"""
        if self.context.bar_order_data_dict:
            print('-- * 将持仓头寸除权除息 *')
        pass

    def position_move_warehouse(self, dt: str):
        """期货持仓头寸移仓"""
        if self.context.bar_order_data_dict:
            print('-- * 将持仓头寸换月移仓 *')
        pass

    def order_rights(self, dt: str):
        """未成交订单头寸与价格按除权除息折算，买入的话要取整"""
        if self.context.bar_order_data_dict:
            print('-- * 将未成交订单除权除息 *')

    def order_move_warehouse(self, dt: str):
        """期货订单移仓"""
        if self.context.bar_order_data_dict:
            print('-- * 将订单中的合约换月移仓 *')
        pass

    def update_symbol_pool(self, dt: str):
        print('-- * 合约池更新 *')

    def update_black_list(self, dt: str):
        print('-- * 黑名单更新 *')
        self.context.black_name_list = []

    def prior_risk_control(self, dt, account, symbol, diretion, offset, price, volume):
        """市场数据触发的交易信号，需要事前风控审核"""
        print('prior_risk_control @ {0}'.format(dt))

        # 黑名单审核
        if symbol in self.context.black_name_list:
            self.context.is_pass_risk = False
            print("Order Stock_code in Black_name_list")
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
            if trade_balance / 0.90 > self.context.current_account_data.available:
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

    @abstractmethod
    def init_strategy(self):
        pass

    @abstractmethod
    def handle_bar(self, event):
        pass

    @abstractmethod
    def handle_order(self, event_order):
        pass

    @abstractmethod
    def handle_trade(self):
        pass
