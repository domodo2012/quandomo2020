# -*- coding: utf-8 -*-
"""
策略模板基类
"""
from copy import deepcopy
from time import sleep
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
    get_symbol_params
)
from core.object import OrderData, StopOrder, TradeData
from core.context import Context
from engine.event_manager import EventManager
from data_center.get_data import GetData


class StrategyBase(object):
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
        self.pos = {}  # 某些合约每个的动态持仓总值，用于下单时判断持仓
        self.context = Context()  # 记录、计算交易过程中各类信息
        # self.fields = ['open', 'high', 'low', 'close', 'order_volume', 'open_interest']
        self.fields = ['open', 'high', 'low', 'close', 'volume']

        # 事件驱动引擎实例化
        self.event_engine = EventManager()

        # 各类事件的监听/回调函数注册
        self.event_engine.register(EVENT_BAR, self.update_bar)
        self.event_engine.register(EVENT_ORDER, self.handle_order)
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

        # todo: 如果是实时模式，则从数据库中取数据的结束时间为其中数据的最后时间，
        # 该时间与实时时间之间的数据再从数据api上取，补足到策略启动时
        if self.run_mode == RunMode_LIVE:
            # self.end =
            pass

        # 从数据库读取数据
        # todo: 现在先将所有数据都取到内存，以后为了减少内存占用，考虑以下方案：
        # 只将close读到内存，其他数据用到时才从数据库中取，以减少内存占用，交易次数不多的话，对速度的影响不大
        # 而每个bar上都要用close计算账户净值，必须读入内存中
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
                    if self.run_mode == RunMode_BACKTESTING:
                        # 回测模式下，市场数据通过生成器推送过来，并生成市场事件
                        self.timestamp = next(bmi_iter)
                        self.datetime = timestamp_to_datetime(self.timestamp, format="%Y%m%d")
                        event_market = Event(EVENT_BAR, self.datetime, self.gateway)
                        self.event_engine.put(event_market)
                    else:
                        # todo: live模式下，市场数据通过api订阅后推送过来
                        pass
                except BacktestFinished:
                    print('策略运行完成')
                    self.strategy_analysis()
                    self.show_results()
                    break
            else:
                # 监听/回调函数根据事件类型处理事件
                self.event_engine.event_process(cur_event)

    def cross_limit_order(self, event_market, cur_mkt_data):
        """处理未成交限价单"""
        print("-- this is cross_limit_order() @ {0}".format(event_market.dt))

        # 逐个未成交委托进行判断
        for order in list(self.context.active_limit_orders.values()):
            long_cross_price = cur_mkt_data['low'][order.symbol]
            short_cross_price = cur_mkt_data['high'][order.symbol]
            long_best_price = cur_mkt_data['open'][order.symbol]
            short_best_price = cur_mkt_data['open'][order.symbol]

            # 委托状态从“待提交”转成“未成交“
            if order.status == Status_SUBMITTING:
                order.status = Status_NOT_TRADED
                event_order = Event(EVENT_ORDER, event_market.dt, order)
                self.event_engine.put(event_order)

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

            # 委托单被成交了，状态改变成 filled
            order.filled_volume = order.order_volume
            order.status = Status_ALL_TRADED
            event_order = Event(EVENT_ORDER, event_market.dt, order)
            self.event_engine.put(event_order)

            self.context.active_limit_orders.pop(order.order_id)

            # 交易数量 + 1
            self.context.trade_count += 1

            if long_cross:
                trade_price = min(order.price, long_best_price)
                pos_change = order.order_volume
            else:
                trade_price = max(order.price, short_best_price)
                pos_change = -order.order_volume

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
                              gateway=self.gateway
                              )
            self.pos[trade.symbol] += pos_change

            event_trade = Event(EVENT_TRADE, event_market.dt, trade)
            self.event_engine.put(event_trade)
            self.handle_trade(event_trade)

            # 交易事件更新
            self.context.trade_data_dict[trade.trade_id] = trade

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
            event_order = Event(EVENT_ORDER, event_market.dt, order)
            self.event_engine.put(event_order)

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
                              gateway=self.gateway
                              )
            self.pos[trade.symbol] += pos_change

            # 新建成交事件，并推送到事件队列中
            event_trade = Event(EVENT_TRADE, event_market.dt, trade)
            self.event_engine.put(event_trade)
            self.handle_trade(event_trade)

            self.context.trade_data_dict[trade.trade_id] = trade

    def update_bar(self, event_market):
        """新出现市场事件 event_bar 时的监听/回调函数，在回测模式下，模拟委托单的撮合动作"""
        print("this is update_bar() @ {0}".format(event_market.dt))

        self.bar_index += 1
        if self.run_mode == RunMode_BACKTESTING:  # 回测模式下的报单反馈
            # 处理股票今日持仓的冻结数量（股票当日买入不能卖出）
            self.update_position_frozen(event_market.dt)

            # 取最新的市场数据
            cur_mkt_data = {'low': {}, 'high': {}, 'open': {}}
            for uii in self.universe:
                cur_date = date_str_to_int(event_market.dt)
                cur_mkt_data['low'][uii] = self.context.daily_data['low'].loc[uii][cur_date]
                cur_mkt_data['high'][uii] = self.context.daily_data['high'].loc[uii][cur_date]
                cur_mkt_data['open'][uii] = self.context.daily_data['open'].loc[uii][cur_date]
            self.cross_limit_order(event_market, cur_mkt_data)  # 处理委托时间早于当前bar的未成交限价单
            self.cross_stop_order(event_market, cur_mkt_data)  # 处理委托时间早于当前bar的未成交止损单
        else:  # live模式下的报单反馈（未完成）
            pass

        self.handle_bar(event_market)
        self.update_bar_info(event_market)

    def handle_order(self, event_order):
        """从队列中获取到 event_order 事件，后续处理内容是：
        订单量是否规范，开仓的话现金是否足够，平仓的话头寸是否足够;
        订单通过规范性处理，才推送入事件驱动队列中，此时订单状态是'待发出'"""
        print('handle_order_() method @ {0}'.format(event_order.data.order_datetime))

        # 持仓信息保存到 context 对应变量中
        # 订单代码
        self.context.current_order_data.order_id = event_order.data.order_id
        self.context.current_order_data.symbol = event_order.data.symbol
        self.context.current_order_data.exchange = event_order.data.exchange

        # 订单内容
        self.context.current_order_data.order_type = event_order.data.order_type
        self.context.current_order_data.price = event_order.data.price
        self.context.current_order_data.offset = event_order.data.offset
        self.context.current_order_data.order_volume = abs(event_order.data.order_volume)
        self.context.current_order_data.filled_volume = 0
        self.context.current_order_data.status = event_order.data.status
        self.context.current_order_data.order_datetime = event_order.data.order_datetime

        # 股票开仓数量要整百，期货持仓要整数
        if event_order.data.exchange in ['SSE', 'SZSE'] and event_order.data.offset == 'open':
            event_order.data.order_volume = 100 * int(event_order.data.order_volume / 100)
        elif event_order.data.exchange in ['SHFE', 'DCE', 'CZCE', 'CFFEX', 'INE', 'SGE']:
            event_order.data.order_volume = int(event_order.data.order_volume)
        self.context.current_order_data.total_volume = event_order.data.order_volume

        # 开仓时账户现金要够付持仓保证金，否则撤单
        # 股票视为100%保证金
        # 考虑到手续费、滑点等情况，现金应该多于开仓资金量的 110%
        if event_order.data.offset == 'open':
            contract_params = get_symbol_params(event_order.data.symbol)
            trade_balance = self.context.current_order_data.order_volume * self.context.current_order_data.price * \
                            contract_params['multiplier'] * contract_params['margin']

            cur_accnt = None
            for aii in self.context.bar_account_data_list:
                if aii.account_id == 'acc0':
                    cur_accnt = aii
            if trade_balance / 0.90 > cur_accnt.available:
                event_order.data.order_type = Status_WITHDRAW
                self.context.current_order_data.status = event_order.data.order_type

        # 平仓时账户中应该有足够头寸，否则撤单
        if event_order.data.offset == 'close':
            if self.context.current_order_data.offset == 'close':
                position_hold = False
                if self.context.bar_position_data_list:
                    for position_data in self.context.bar_position_data_list:
                        # 根据资金账号限制卖出数量
                        for account_data in self.context.bar_account_data_list:
                            if account_data.account_id == self.context.current_order_data.account_id:

                                if self.context.current_order_data.symbol == position_data.symbol:
                                    position_hold = True
                                    if self.context.current_order_data.total_volume > (
                                            position_data.position - position_data.frozen):
                                        print("Insufficient Available Position")
                                        self.context.current_order_data.status = Status_WITHDRAW
                                        break
                    # 如果遍历完持仓，没有此次平仓的持仓，Status改为WITHDRAW
                    if position_hold is False:
                        print("Insufficient Available Position")
                        self.context.current_order_data.status = Status_WITHDRAW

                # 如果持仓为空，Status改为WITHDRAW
                else:
                    print("Insufficient Available Position")
                    self.context.current_order_data.status = Status_WITHDRAW

        # 订单状态及时更新
        print('--- * update order info *')

    def handle_risk(self, event_order):
        """从队列中获取到订单事件，进行前置风控的审核，根据注册时的顺序，一定发生在 handle_order_() 之后：
        要交易的合约是否在黑名单上
        todo: 单一合约的开仓市值是否超过总账户的1/3
        通过风控审核才推送入事件驱动队列中，此时订单状态是'未成交'"""
        print('handle_risk() method @ {0}'.format(event_order.data.order_datetime))

        cur_symbol = self.context.current_order_data.symbol
        if self.context.current_order_data.status == Status_SUBMITTING:
            if cur_symbol in self.context.black_name_list:
                self.context.is_pass_risk = False
                self.context.current_order_data.status = Status_WITHDRAW
                print("Order Stock_code in Black_name_list")
            else:
                self.context.current_order_data.status = Status_NOT_TRADED
                self.context.is_send_order = True

        # 订单状态及时更新
        print('--- * update order info *')

    def handle_trade(self, event_trade):
        """订单成交后，在 context 中更新相关持仓数据"""
        print('handle_trade() method @ {0}'.format(event_trade.data.order_datetime))

        # 更新 context 中的交易信息
        self.context.current_trade_data.trade_id = generate_random_id('traded')
        self.context.current_trade_data.order_id = self.context.current_order_data.order_id
        self.context.current_trade_data.symbol = self.context.current_order_data.symbol
        self.context.current_trade_data.exchange = self.context.current_order_data.exchange
        self.context.current_trade_data.account_id = self.context.current_order_data.account_id
        self.context.current_trade_data.price = self.context.current_order_data.price
        self.context.current_trade_data.direction = self.context.current_order_data.direction
        self.context.current_trade_data.offset = self.context.current_order_data.offset
        self.context.current_trade_data.volume = self.context.current_order_data.total_volume
        self.context.current_trade_data.datetime = self.context.current_order_data.order_time
        self.context.current_trade_data.frozen += self.context.current_order_data.filled_volume

        # 计算滑点
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
        trade_balance = self.context.current_trade_data.price * self.context.current_trade_data.trade_volume
        # 分市场标的计算手续费率
        if self.context.current_trade_data.exchange == "SH":
            commission = self.context.commission_dict[Product_STOCK_SH]
        elif self.context.current_trade_data.exchange == "SZ":
            commission = self.context.commission_dict[Product_STOCK_SZ]

        # 根据经过交易手续费后的成交额，更新成交价格
        if self.context.current_trade_data.offset == Offset_OPEN:
            total_commission = commission['open_commission']
            trade_balance *= 1 + total_commission
            self.context.current_trade_data.price = trade_balance / self.context.current_trade_data.trade_volume

        elif self.context.current_trade_data.offset == Offset_CLOSE:
            total_commission = commission['close_commission'] + commission['tax']
            trade_balance *= 1 - total_commission
            self.context.current_trade_data.price = trade_balance / self.context.current_trade_data.trade_volume

        # 更新 context 中的持仓信息
        self.context.current_position_data.trade_id = self.context.current_trade_data.trade_id
        self.context.current_position_data.order_id = self.context.current_trade_data.order_id
        self.context.current_position_data.symbol = self.context.current_trade_data.symbol
        self.context.current_position_data.exchange = self.context.current_trade_data.exchange
        self.context.current_position_data.account_id = self.context.current_order_data.account_id
        self.context.current_position_data.price = self.context.current_trade_data.price
        self.context.current_position_data.direction = self.context.current_trade_data.direction
        self.context.current_position_data.offset = self.context.current_trade_data.offset
        self.context.current_position_data.volume = self.context.current_trade_data.total_volume
        self.context.current_position_data.datetime = self.context.current_trade_data.order_time
        self.context.current_position_data.frozen += self.context.current_trade_data.filled_volume

        if self.context.bar_position_data_list:
            position_num = 0
            position_hold = False
            for position_data in self.context.bar_position_data_list:
                position_num += 1
                if self.context.current_position_data.symbol == position_data.symbol:
                    position_hold = True
                    # print(self.context.current_trade_data.offset, "方向"*10)
                    if self.context.current_trade_data.offset == Offset_OPEN:
                        total_position = position_data.position + self.context.current_trade_data.trade_volume
                        position_cost_balance = position_data.position * position_data.init_price
                        trade_balance = \
                            self.context.current_trade_data.trade_volume * self.context.current_trade_data.price
                        # 更新持仓成本
                        position_data.init_price = \
                            (position_cost_balance + trade_balance) / total_position
                        # 更新持仓数量
                        position_data.position = total_position
                        # 更新冻结数量
                        position_data.frozen += self.context.current_trade_data.trade_volume
                        # print("update_position_list")

                    elif self.context.current_trade_data.offset == Offset_CLOSE:
                        total_position = \
                            position_data.position - self.context.current_trade_data.trade_volume
                        position_cost_balance = position_data.position * position_data.init_price
                        trade_balance = \
                            self.context.current_trade_data.trade_volume * self.context.current_trade_data.price
                        if total_position > 0:
                            position_data.init_price = \
                                (position_cost_balance - trade_balance) / total_position
                        else:
                            position_data.init_price = 0
                        position_data.position = total_position
                        # print("sell position"*5, position_data.position)

            # 持仓不为空，且不在持仓里面的，append到self.context.bar_position_data_list
            if position_num == len(self.context.bar_position_data_list) and position_hold is False:
                self.context.current_position_data.init_price = self.context.current_trade_data.trade_price
                self.context.current_position_data.position = self.context.current_trade_data.trade_volume
                self.context.bar_position_data_list.append(self.context.current_position_data)

        else:
            self.context.current_position_data.init_price = self.context.current_trade_data.trade_price
            self.context.current_position_data.position = self.context.current_trade_data.trade_volume
            # 持仓为空，append到self.context.bar_position_data_list
            self.context.bar_position_data_list.append(self.context.current_position_data)

        # 更新委托的状态和成交数量，并把此次委托append到self.context.bar_order_data_list
        self.context.current_order_data.status = Status_ALL_TRADED
        self.context.current_order_data.trade_volume = self.context.current_trade_data.trade_volume
        self.context.bar_order_data_list.append(self.context.current_order_data)
        # 把此次成交append到self.context.bar_trade_data_list
        self.context.bar_trade_data_list.append(self.context.current_trade_data)

        # 更新现金
        if self.context.bar_account_data_list:
            for account in self.context.bar_account_data_list:
                if account.account_id == self.context.current_order_data.account_id:
                    if self.context.current_trade_data.offset == Offset_OPEN:
                        # 更新可用资金
                        account.available -= \
                            self.context.current_trade_data.price * self.context.current_trade_data.trade_volume
                    elif self.context.current_trade_data.offset == Offset_CLOSE:

                        account.available += \
                            self.context.current_trade_data.price * self.context.current_trade_data.trade_volume

        self.context.refresh_current_data()

        # 订单状态及时更新
        print('--- * update trade info *')

    def handle_timer(self, event_timer):
        """每隔固定时间，就获取一次账户状态数据，只在 live 模式中有效"""
        print('... di da di, {0} goes, updates account status'.format(event_timer.type_))
        pass

    def update_bar_info(self, event_market: object):
        """每个bar所有事件都处理完成后，更新该bar下总体情况，内容包括：
        1、持仓数量为0的仓位，清掉；
        2、检查现有持仓的股票是否有除权除息，有则处理其现金与持仓市值相应变动；
        3、检查现有持仓的期货是否换月，有则发出换月委托对应计算总体持仓的市值pnl；
        4、以当日收盘价计算所持合约的当日pnl，并汇总得到当日账户总pnl；
        5、计算当日账户总值
        6、将每根bar上的资金、持仓、委托、成交存入以时间戳为键索引的字典变量中
        """
        print('this is update_bar_info() @ {0}'.format(event_market.dt))

        self.delete_position_zero()
        self.position_rights(event_market.dt)
        self.position_move_warehouse(event_market.dt)
        self.update_position_close(event_market.dt)
        self.update_account_close(event_market.dt)
        self.save_current_bar_data(event_market.dt)
        self.context.refresh_bar_dict()

    def buy(self, dt, accnt, stock: str, price: float, volume: int, is_stop: bool, comments=''):
        self.send_order(dt, accnt, stock, Direction_LONG, Offset_OPEN, price, volume, is_stop, comments)

    def sell(self, dt, accnt, stock: str, price: float, volume: int, is_stop: bool, comments=''):
        self.send_order(dt, accnt, stock, Direction_SHORT, Offset_CLOSE, price, volume, is_stop, comments)

    def sell_short(self, dt, accnt, stock: str, price: float, volume: int, is_stop: bool, comments=''):
        self.send_order(dt, accnt, stock, Direction_SHORT, Offset_OPEN, price, volume, is_stop, comments)

    def buy_to_cover(self, dt, accnt, stock: str, price: float, volume: int, is_stop: bool, comments=''):
        self.send_order(dt, accnt, stock, Direction_LONG, Offset_CLOSE, price, volume, is_stop, comments)

    def send_order(self, dt, accnt, stock, diretion, offset, price, volume, is_stop, comments):
        if self.run_mode == RunMode_LIVE:
            order_id = None
        else:
            stock_paras = get_symbol_params(stock)
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

    @abstractmethod
    def init_strategy(self):
        pass

    @abstractmethod
    def handle_bar(self, event):
        pass

    def update_position_frozen(self, dt):
        """处理当日情况前，先更新当日股票的持仓冻结数量"""
        if self.bar_index > 0 and self.context.bar_position_data_list:
            last_timestamp = self.context.benchmark_index[self.bar_index - 1]
            last_day = timestamp_to_datetime(last_timestamp, '%Y%m%d')
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

    def update_position_close(self, dt: str):
        """基于close，更新每个持仓的持仓盈亏"""
        if self.context.bar_position_data_list:
            dt = dt[:4] + '-' + dt[4:6] + '-' + dt[6:]
            for position_data in self.context.bar_position_data_list:
                cur_close = self.get_data.get_market_data(self.context.daily_data,
                                                          stock_code=[position_data.symbol],
                                                          field=["close"],
                                                          start=dt,
                                                          end=dt)
                position_data.position_pnl = position_data.position * (
                        cur_close - position_data.init_price
                )
        print("—— * 以当前bar的close更新持仓盈亏 *")

    def update_account_close(self, dt):
        """基于close，更新账户总资产"""
        dt = dt[:4] + '-' + dt[4:6] + '-' + dt[6:]
        if self.context.bar_position_data_list:
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
                    account.total_balance = account.available + hold_balance
        print("-- * 以当前bar的close更新账户 {0} , 总资产：{1}".format(
            self.context.bar_account_data_list[0].account_id,
            self.context.bar_account_data_list[0].total_balance))

    def save_current_bar_data(self, dt: str):
        """记录每根bar的信息，包括资金、持仓、委托、成交等"""
        print('-- this is save_current_bar_data() @ {0} 记录每根bar的信息，包括资金、持仓、委托、成交'.format(dt))
        cur_timestamp = datetime_to_timestamp(dt)
        self.context.order_data_dict[cur_timestamp] = self.context.bar_order_data_list
        self.context.trade_data_dict[cur_timestamp] = self.context.bar_trade_data_list
        self.context.position_data_dict[cur_timestamp] = deepcopy(self.context.bar_position_data_list)
        self.context.account_data_dict[cur_timestamp] = deepcopy(self.context.bar_account_data_list)

        pass

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


if __name__ == '__main__':
    StrategyBase().run_strategy()
