# -*- coding: utf-8 -*-
"""
策略模板基类
"""
from copy import deepcopy
from abc import abstractmethod
from queue import Empty

from core.const import *
from core.event import Event
from core.utility import (
    datetime_to_timestamp,
    timestamp_to_datetime,
    date_str_to_int,
    get_exchange,
    generate_random_id,
    round_to,
    get_contract_params
)
from core.object import OrderData, StopOrder, TradeData
from core.context import Context
from engine.event_manager import EventManager
from data_center.get_data import GetData


class StrategyBaseBacktest(object):
    def __init__(self):
        self.gateway = None
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
        self.pos = {}  # 某些合约每个bar的动态持仓总值，用于下单时判断持仓
        self.context = Context()  # 记录、计算交易过程中各类信息
        # self.fields = ['open', 'high', 'low', 'close', 'order_volume', 'open_interest']
        self.fields = ['open', 'high', 'low', 'close', 'volume']

        # 事件驱动引擎实例化
        self.event_engine = EventManager()

        # 各类事件的监听/回调函数注册
        self.event_engine.register(EVENT_MARKET, self.update_bar)
        self.event_engine.register(EVENT_ORDER, self.handle_order_)
        self.event_engine.register(EVENT_ORDER, self.handle_risk)
        self.event_engine.register(EVENT_TRADE, self.handle_trade)
        # self.event_engine.register_general(self.update_bar_info)

    # 回测滑点设置
    def set_slippage(self,
                     stock_type=Product_STOCK,
                     slippage_type=SLIPPAGE_FIX,
                     value=0):
        self.context.slippage_dict[stock_type] = {"slippage_type": slippage_type,
                                                  "value": value}

    # 回测手续费和印花税
    def set_commission(self,
                       stock_type=Product_STOCK,
                       tax=0,
                       open_commission=0,
                       close_commission=0,
                       close_today_commission=0,
                       min_commission=0):
        self.context.commission_dict[stock_type] = {"tax": tax,
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
                    event_market = Event(EVENT_MARKET, self.datetime, self.gateway)
                    self.event_engine.put(event_market)
                except StopIteration:
                    print('策略运行完成')
                    self.strategy_analysis()
                    self.show_results()
                    break
            else:
                # 监听/回调函数根据事件类型处理事件
                self.event_engine.event_process(cur_event)

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
            long_cross = (order.direction == Direction_LONG
                          and order.price >= long_cross_price > 0
                          )

            short_cross = (order.direction == Direction_SHORT
                           and order.price <= short_cross_price
                           and short_cross_price > 0
                           )

            # 如果委托单仍然不能被成交，则其所有状态都不改变，继续等待被成交
            if not long_cross and not short_cross:
                continue

            # 委托单被成交了，相应的属性变更
            order.filled_volume = order.order_volume
            order.status = Status_ALL_TRADED
            self.context.limit_orders[order.order_id].status = Status_ALL_TRADED
            event_order = Event(EVENT_ORDER, event_market.dt, order)
            # self.event_engine.put(event_order)
            self.handle_order_(event_order)

            # 将当前委托单从未成交委托单清单中去掉
            self.context.active_limit_orders.pop(order.order_id)

            # 交易数量 + 1
            self.context.trade_count += 1

            if long_cross:
                trade_price = min(order.price, long_best_price)
                # pos_change = order.order_volume
            else:
                trade_price = max(order.price, short_best_price)
                # pos_change = -order.order_volume

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
                              account=order.account
                              )
            # self.pos[trade.symbol] += pos_change

            # 及时更新 context 中的成交信息
            # self.context.current_trade_data = trade.__dict__

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
                              order_datetime=event_market.dt
                              )

            self.context.limit_orders[order.order_id] = order

            # 更新stop_order对象的属性
            # stop_order.order_ids.append(order.order_id)
            stop_order.filled_datetime = event_market.dt
            stop_order.status = StopOrderStatus_TRIGGERED

            # 未成交止损单清单中将本止损单去掉
            if stop_order.order_id in self.context.active_stop_orders:
                self.context.active_stop_orders.pop(stop_order.order_id)

            # 止损单被触发，本地止损单转成限价单成交，新增order_event并送入队列中
            # event_order = Event(EVENT_ORDER, event_market.dt, order)
            # self.event_engine.put(event_order)

            # 止损单被触发，新建一个成交对象
            if long_cross:
                trade_price = max(stop_order.price, long_best_price)
                pos_change = order.order_volume
            else:
                trade_price = min(stop_order.price, short_best_price)
                pos_change = -order.order_volume

            self.context.trade_count += 1

            trade = TradeData(symbol=order.symbol,
                              exchange=order.exchange,
                              order_id=order.order_id,
                              trade_id=generate_random_id('filled'),
                              direction=order.direction,
                              offset=order.offset,
                              price=trade_price,
                              volume=order.order_volume,
                              datetime=self.datetime,
                              gateway=self.gateway,
                              account=order.account
                              )
            # self.pos[trade.symbol] += pos_change

            # 及时更新 context 中的交易信息
            self.context.current_trade_data.trade_id = trade.trade_id
            self.context.current_trade_data.order_id = trade.order_id
            self.context.current_trade_data.symbol = trade.symbol
            self.context.current_trade_data.exchange = trade.exchange
            self.context.current_trade_data.account_id = trade.account
            self.context.current_trade_data.price = trade.price
            self.context.current_trade_data.direction = trade.direction
            self.context.current_trade_data.offset = trade.offset
            self.context.current_trade_data.volume = trade.volume
            self.context.current_trade_data.datetime = trade.datetime
            self.context.current_trade_data.frozen += trade.volume

            # 新建成交事件，并推送到事件队列中
            event_trade = Event(EVENT_TRADE, event_market.dt, trade)
            # self.event_engine.put(event_trade)
            self.handle_trade_(event_trade)

    def update_bar(self, event_market):
        """新出现市场事件 event_market 时的监听/回调函数，在回测模式下，模拟委托单的撮合动作"""
        print("this is update_bar() @ {0}".format(event_market.dt))

        self.bar_index += 1

        # 处理股票今日持仓的冻结数量（股票当日买入不能卖出）
        self.update_position_frozen(event_market.dt)

        # 所持头寸要除权除息？
        self.position_rights(event_market.dt)

        # 所持头寸要换月？
        self.position_move_warehouse(event_market.dt)

        # 未成交订单要除权除息？
        self.order_rights(event_market.dt)

        # 未成交订单要换月？
        self.order_move_warehouse(event_market.dt)

        # 取最新的市场数据，看未成交订单在当前bar是否能成交
        cur_mkt_data = {'low': {}, 'high': {}, 'open': {}}
        cur_date = date_str_to_int(event_market.dt)
        for uii in self.universe:
            cur_mkt_data['low'][uii] = self.context.daily_data['low'].loc[uii][cur_date]
            cur_mkt_data['high'][uii] = self.context.daily_data['high'].loc[uii][cur_date]
            cur_mkt_data['open'][uii] = self.context.daily_data['open'].loc[uii][cur_date]
        self.cross_limit_order(event_market, cur_mkt_data)  # 处理委托时间早于当前bar的未成交限价单
        self.cross_stop_order(event_market, cur_mkt_data)  # 处理委托时间早于当前bar的未成交止损单

        # 更新黑名单
        self.context.black_name_list = self.update_black_list(event_market.dt)

        # 更新合约池
        self.update_contracts_pool(event_market.dt)

        # 是否有新委托信号
        self.handle_bar(event_market)

        # 当前bar的持仓、账户信息更新
        self.update_bar_info(event_market)

    def handle_order_(self, event_order):
        """
        从队列中获取到 event_order 事件，后续处理内容是：
        订单量是否规范，开仓的话现金是否足够，平仓的话头寸是否足够;
        订单通过规范性处理，才推送入事件驱动队列中，此时订单状态是'待发出'
        """
        print('handle_order_() method @ {0}'.format(event_order.data.order_datetime))

        # 订单发出之前进行前置风控检查，并且此时是新订单
        if event_order.data.status == Status_SUBMITTING:
            # 持仓信息保存到 context 对应变量中
            self.context.current_order_data = event_order.data.__dict__
            order_accnt = event_order.data.account

            # 股票开仓数量要整百，期货持仓要整数
            if event_order.data.exchange in ['SSE', 'SZSE'] and event_order.data.offset == 'open':
                cur_order_volume = 100 * int(event_order.data.order_volume / 100)
            elif event_order.data.exchange in ['SHFE', 'DCE', 'CZCE', 'CFFEX', 'INE', 'SGE']:
                cur_order_volume = int(event_order.data.order_volume)
            else:
                cur_order_volume = abs(event_order.data.order_volume)
            self.context.current_order_data.total_volume = cur_order_volume

            # 开仓时账户现金要够付持仓保证金，否则撤单
            # 股票视为100%保证金
            # 考虑到手续费、滑点等情况，现金应该多于开仓资金量的 110%
            if event_order.data.offset == 'open':
                contract_params = get_contract_params(event_order.data.symbol)
                trade_balance = self.context.current_order_data.total_volume * self.context.current_order_data.price * \
                                contract_params['multiplier'] * contract_params['margin']

                # todo: 原本对账户现金是否足够的判断，需要更细化，现在先笼统处理，下一步在逐个股票的判别时，要有冻结资金的概念
                #       即组合中每个标的物的订单都会冻结一部分资金，后边的股票判断可用现金时要将总现金减去冻结的现金后再判断
                #       类似真实交易终端下单时一样
                if trade_balance / 0.90 > self.context.current_account_data[order_accnt].available:
                    self.context.current_order_data.status = Status_WITHDRAW
                    print("Insufficient Available cash")

            # 平仓时账户中应该有足够头寸，否则撤单
            if event_order.data.offset == 'close':
                position_hold = False
                if self.context.bar_position_data_dict:
                    for cur_pos in self.context.bar_position_data_dict:
                        # 根据资金账号限制卖出数量
                        if cur_pos[event_order.data.symbol]:
                            position_hold = True
                            if self.context.current_order_data.order_volume > (
                                    cur_pos[event_order.data.symbol].volume - cur_pos[event_order.data.symbol].frozen):
                                print("Insufficient Available Position")
                                self.context.current_order_data.status = Status_WITHDRAW

                                break
                    # 如果遍历完持仓，没有此次平仓的持仓，Status改为WITHDRAW
                    if position_hold is False:
                        print("No Available Position")
                        self.context.current_order_data.status = Status_WITHDRAW

                # 如果持仓为空，Status改为WITHDRAW
                else:
                    print("Insufficient Available Position")
                    self.context.current_order_data.status = Status_WITHDRAW

    def handle_risk(self, event_order):
        """从队列中获取到订单事件，进行前置风控的审核，根据注册时的顺序，一定发生在 handle_order_() 之后：
        要交易的合约是否在黑名单上
        todo: 单一合约的开仓市值是否超过总账户的1/3
        通过风控审核才推送入事件驱动队列中（真正发出），将订单状态更改为'未成交'"""
        print('handle_risk() method @ {0}'.format(event_order.data.order_datetime))

        if self.context.current_order_data.status == Status_SUBMITTING:
            cur_symbol = self.context.current_order_data.symbol
            if cur_symbol in self.context.black_name_list:
                self.context.is_pass_risk = False
                self.context.current_order_data.status = Status_WITHDRAW
                print("Order Stock_code in Black_name_list")
            else:
                self.context.current_order_data.status = Status_NOT_TRADED
                if event_order.data.order_type == OrderType_LIMIT:
                    self.context.active_limit_orders[event_order.data.order_id].status = Status_NOT_TRADED
                self.context.is_send_order = True

    def handle_trade_(self, event_trade):
        """订单成交后，在 context 中更新相关持仓数据"""
        print('handle_trade() method @ {0}'.format(event_trade.data.datetime))

        cur_symbol = event_trade.data.symbol

        # 更新 context 中的当前成交信息
        self.context.current_trade_data = event_trade.data.__dict__

        # 计算滑点成交价位
        if self.context.current_trade_data.exchange == "SH" or self.context.current_trade_data.exchange == "SZ":
            if self.context.slippage_dict[Product_STOCK]["slippage_type"] == SLIPPAGE_FIX:
                if self.context.current_trade_data.offset == Offset_OPEN:
                    self.context.current_trade_data.price += \
                        self.context.slippage_dict[Product_STOCK]["value"]

                elif self.context.current_trade_data.offset == Offset_CLOSE:
                    self.context.current_trade_data.trade_price -= \
                        self.context.slippage_dict[Product_STOCK]["value"]

            elif self.context.slippage_dict[Product_STOCK]["slippage_type"] == SLIPPAGE_PERCENT:
                if self.context.current_trade_data.offset == Offset_OPEN:
                    self.context.current_trade_data.price *= (
                            1 + self.context.slippage_dict[Product_STOCK]["value"])

                elif self.context.current_trade_data.offset == Offset_CLOSE:
                    self.context.current_trade_data.trade_price *= (
                            1 - self.context.slippage_dict[Product_STOCK]["value"])

        # 计算手续费
        commission = {}
        trade_balance = self.context.current_trade_data.price * self.context.current_trade_data.volume
        # 分市场标的计算手续费率
        if self.context.current_trade_data.exchange == Exchange_SSE:
            commission = self.context.commission_dict[Product_STOCK_SH]
        elif self.context.current_trade_data.exchange == Exchange_SZSE:
            commission = self.context.commission_dict[Product_STOCK_SZ]

        # 根据经过交易手续费后的成交额，更新成交价格
        if self.context.current_trade_data.offset == Offset_OPEN:
            total_commission = commission['open_commission']
            trade_balance *= 1 + total_commission
            self.context.current_trade_data.price = trade_balance / self.context.current_trade_data.volume

        elif self.context.current_trade_data.offset == Offset_CLOSE:
            total_commission = commission['close_commission'] + commission['tax']
            trade_balance *= 1 + total_commission
            self.context.current_trade_data.price = trade_balance / self.context.current_trade_data.volume

        # 更新 context 中的持仓信息
        self.context.current_position_data.symbol = self.context.current_trade_data.symbol
        self.context.current_position_data.exchange = self.context.current_trade_data.exchange
        self.context.current_position_data.account = self.context.current_order_data.account
        self.context.current_position_data.trade_id = self.context.current_trade_data.trade_id
        self.context.current_position_data.order_id = self.context.current_trade_data.order_id

        self.context.current_position_data.price = self.context.current_trade_data.price
        self.context.current_position_data.direction = self.context.current_trade_data.direction
        self.context.current_position_data.offset = self.context.current_trade_data.offset
        self.context.current_position_data.volume = self.context.current_trade_data.volume
        self.context.current_position_data.datetime = self.context.current_trade_data.datetime
        self.context.current_position_data.frozen += self.context.current_trade_data.volume

        # 根据symbol，将当前持仓情况按当前交易情况更新
        if self.context.bar_position_data_dict:
            if cur_symbol in self.context.current_position_data.keys():
                # 当前 bar 已有持仓数据，并且当前 symbol 已有持仓
                position_cost_balance = self.context.current_position_data[cur_symbol].volume * \
                                        self.context.current_position_data[cur_symbol].price
                trade_balance = self.context.current_trade_data.volume * self.context.current_trade_data.price

                if event_trade.data.offset == Offset_OPEN:
                    total_position = self.context.current_position_data[cur_symbol].volume + event_trade.data.volume

                    # 更新持仓成本
                    self.context.current_position_data[cur_symbol].price = \
                        (position_cost_balance + trade_balance) / total_position

                    # 更新持仓数量
                    self.context.current_position_data[cur_symbol].volume = total_position

                    # 更新冻结数量
                    self.context.current_position_data[cur_symbol].frozen += event_trade.data.volume

                elif event_trade.data.offset == Offset_CLOSE:
                    total_position = self.context.current_position_data[cur_symbol].volume - event_trade.data.volume

                    if total_position > 0:
                        self.context.current_position_data[cur_symbol].price = \
                            (position_cost_balance - trade_balance) / total_position
                    else:
                        self.context.current_position_data[cur_symbol].price = 0
                    self.context.current_position_data[cur_symbol].volume = total_position

            else:
                # 当前 bar 有持仓数据，但是当前 symbol 尚无持仓
                if self.context.current_trade_data[cur_symbol].volume > 0:
                    self.context.bar_position_data_dict[cur_symbol] = self.context.current_position_data
        else:
            # 当前 bar 没有持仓数据
            self.context.bar_position_data_dict[cur_symbol] = self.context.current_position_data

        # 更新委托的状态和成交数量
        # self.context.current_order_data.status = Status_ALL_TRADED
        # self.context.current_order_data.trade_volume = self.context.current_trade_data.trade_volume
        # self.context.bar_order_data_dict[cur_symbol] = self.context.current_order_data

        # 把此次成交添加到 self.context.bar_trade_data_dict
        self.context.bar_trade_data_dict[cur_symbol] = self.context.current_trade_data

        # 更新现金
        if self.context.bar_account_data_dict:
            if self.context.current_trade_data.offset == Offset_OPEN:
                # 更新可用资金
                self.context.bar_account_data_dict[event_trade.data.account].available -= \
                    self.context.current_trade_data.price * self.context.current_trade_data.trade_volume
            elif self.context.current_trade_data.offset == Offset_CLOSE:
                self.context.bar_account_data_dict[event_trade.data.account].available += \
                    self.context.current_trade_data.price * self.context.current_trade_data.trade_volume

        # 交易事件更新
        self.context.trade_data_dict[event_trade.data.trade_id] = event_trade.data
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
        self.update_position_and_account_close(event_market.dt)
        self.save_current_bar_data(event_market.dt)
        self.context.refresh_bar_dict()

    def buy(self, dt, accnt, stock: str, price: float, volume: int, is_stop: bool, comments:str =''):
        self.send_order(dt, accnt, stock, Direction_LONG, Offset_OPEN, price, volume, is_stop, comments)

    def sell(self, dt, accnt, stock: str, price: float, volume: int, is_stop: bool, comments=''):
        self.send_order(dt, accnt, stock, Direction_SHORT, Offset_CLOSE, price, volume, is_stop, comments)

    def sell_short(self, dt, accnt, stock: str, price: float, volume: int, is_stop: bool, comments=''):
        self.send_order(dt, accnt, stock, Direction_SHORT, Offset_OPEN, price, volume, is_stop, comments)

    def buy_to_cover(self, dt, accnt, stock: str, price: float, volume: int, is_stop: bool, comments=''):
        self.send_order(dt, accnt, stock, Direction_LONG, Offset_CLOSE, price, volume, is_stop, comments)

    def send_order(self, dt, accnt, stock, diretion, offset, price, volume, is_stop, comments):
        stock_paras = get_contract_params(stock)
        price = round_to(price, stock_paras['price_tick'])

        if is_stop:
            self.send_stop_order(dt, accnt, stock, diretion, offset, price, volume, comments)
        else:
            self.send_limit_order(dt, accnt, stock, diretion, offset, price, volume, comments)

    def send_stop_order(self, dt, accnt, stock, direction, offset, price, volume, comments):
        self.context.stop_order_count += 1

        stop_order = StopOrder(symbol=stock,
                               exchange=get_exchange(stock),
                               order_id=generate_random_id('stoporder'),
                               direction=direction,
                               offset=offset,
                               price=price,
                               order_volume=volume,
                               account=accnt,
                               gateway=self.gateway,
                               order_datetime=dt,
                               comments=comments
                               )

        self.context.active_stop_orders[stop_order.order_id] = stop_order
        self.context.stop_orders[stop_order.order_id] = stop_order

        event_order = Event(EVENT_ORDER, dt, stop_order)
        self.event_engine.put(event_order)

    def send_limit_order(self, dt, accnt, stock, direction, offset, price, volume, comments):
        self.context.limit_order_count += 1

        order = OrderData(symbol=stock,
                          exchange=get_exchange(stock),
                          order_id=generate_random_id('order'),
                          direction=direction,
                          offset=offset,
                          price=price,
                          order_volume=volume,
                          status=Status_SUBMITTING,
                          account=accnt,
                          gateway=self.gateway,
                          order_datetime=dt,
                          comments=comments
                          )

        self.context.active_limit_orders[order.order_id] = order
        self.context.limit_orders[order.order_id] = order

        event_order = Event(EVENT_ORDER, dt, order)
        self.event_engine.put(event_order)

    def strategy_analysis(self):
        """策略的绩效分析"""
        pass

    def show_results(self):
        """展示策略绩效分析结果"""
        pass

    def update_position_frozen(self, dt):
        """处理当日情况前，先更新当日股票的持仓冻结数量"""
        if self.bar_index > 0 and self.context.bar_position_data_list:
            last_timestamp = self.context.benchmark_index[self.bar_index - 1]
            last_day = timestamp_to_datetime(last_timestamp, '%Y%M%d')
            for position_data in self.context.bar_position_data_list:
                if last_day != dt:
                    position_data.frozen = 0
                    print('—— * 更新今仓冻结数量 *')
        pass

    def delete_position_zero(self):
        """将数量为0的持仓，从持仓字典中删掉"""
        self.context.bar_position_data_list = [position_data for position_data in self.context.bar_position_data_list
                                               if position_data.position != 0]
        pass

    def update_position_and_account_close(self, dt: str):
        """基于close，更新每个持仓的持仓盈亏，更新账户总资产"""
        if self.context.bar_position_data_list:
            dt = dt[:4] + '-' + dt[4:6] + '-' + dt[6:]
            for account in self.context.bar_account_data_list:
                hold_balance = 0
                for position_data in self.context.bar_position_data_list:
                    if account.account_id == position_data.account_id:
                        cur_close = self.get_data.get_market_data(self.context.daily_data,
                                                                  stock_code=[position_data.symbol],
                                                                  field=["close"],
                                                                  start=dt,
                                                                  end=dt)
                        hold_balance += position_data.position * cur_close
                        position_data.position_pnl = position_data.position * (
                                cur_close - position_data.average_price
                        )
                    account.total_balance = account.available + hold_balance
        print("-- * 以当前bar的close更新持仓盈亏和账户总值 {0} , 总资产：{1}".format(
            self.context.bar_account_data_list[0].account_id,
            self.context.bar_account_data_list[0].total_balance))

    def save_current_bar_data(self, dt: str):
        """记录每根bar的信息，包括资金、持仓、委托、成交等"""
        print('-- save_current_bar_data() @ {0} 记录每根bar的信息，包括资金、持仓、委托、成交'.format(dt))
        cur_timestamp = datetime_to_timestamp(dt)
        self.context.order_data_dict[cur_timestamp] = self.context.bar_order_data_list
        self.context.trade_data_dict[cur_timestamp] = self.context.bar_trade_data_list
        self.context.position_data_dict[cur_timestamp] = deepcopy(self.context.bar_position_data_list)
        self.context.account_data_dict[cur_timestamp] = deepcopy(self.context.bar_account_data_list)

    def position_rights(self, dt: str):
        """将持仓头寸除权除息"""
        if self.context.bar_position_data_list:
            print('-- * 将持仓头寸除权除息 *')
        pass

    def position_move_warehouse(self, dt: str):
        """期货持仓头寸移仓"""
        if self.context.bar_position_data_list:
            print('-- * 将持仓头寸换月移仓 *')
        pass

    def order_rights(self, dt: str):
        """未成交订单头寸与价格按除权除息折算，买入的话要取整"""
        if self.context.bar_order_data_list:
            print('-- * 将未成交订单除权除息 *')

    def order_move_warehouse(self, dt: str):
        """期货订单移仓"""
        if self.context.bar_order_data_list:
            print('-- * 将订单中的合约换月移仓 *')
        pass

    def update_contracts_pool(self, dt: str):
        print('-- * 合约池更新 *')

    def update_black_list(self, dt: str):
        print('-- * 黑名单更新 *')
        bl = []
        return bl

    @abstractmethod
    def init_strategy(self):
        pass

    @abstractmethod
    def handle_bar(self, event):
        pass

    @abstractmethod
    def handle_trade(self):
        pass

