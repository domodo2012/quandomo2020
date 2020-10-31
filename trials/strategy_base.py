# -*- coding: utf-8 -*-
"""
策略基类，包含了事件驱动的运行框架
"""

from abc import abstractmethod
from copy import copy
from pymongo import MongoClient
from collections import OrderedDict

from core.const import *
from core.utility import datetime_to_timestamp, timestamp_to_datetime
from core.object import AccountData, BarData
from core.context import Context
from core.event import Event
from trials.event_engine_base import EventEngineBase


class StrategyBase(object):
    def __init__(self):
        self.run_mode = None
        self.start = None
        self.end = None
        self.interval = None
        self.account = None
        self.benchmark = None
        self.rights_adjustment = None
        self.universe = None
        self.set_slippage_type = None

        self.get_data = None            # 从 mongodb 取数据
        self.timestamp = None
        self.datetime = None
        self.bar_index = None
        self.bar_len = None

        self.data_dict = OrderedDict()
        self.trade_dict = OrderedDict()

        # 事件驱动引擎的实例化
        self.strat_event_engine = EventEngineBase(timer_interval=0.2)

        # 市场事件的监听/回调函数注册
        self.strat_event_engine.register(EVENT_BAR, self.new_bar)
        # self.event_engine.register(EVENT_BAR, self.handle_bar)

        # 订单委托事件的监听/回调函数注册
        self.strat_event_engine.register(EVENT_ORDER, self.handle_order)

        # 事前风控事件的监听/回调函数注册
        self.strat_event_engine.register(EVENT_RISK_MANAGEMENT, self.handle_risk)

        # 成交事件的监听/回调函数注册
        self.strat_event_engine.register(EVENT_TRADE, self.handle_trade)

        # 通用事件的监听/回调函数注册（数据记录）
        self.strat_event_engine.register_general_handler(self.event_record)

    def load_data_from_mongo(self):
        """加载策略运行所用数据"""
        mc = MongoClient()
        db = mc[MongoDbName_DAILY_DB_NAME]

        for symbol in self.universe:
            flt = {'timetag': {'$gte': self.start, '$lte': self.end}}
            cursor = db[symbol].find(flt).sort('datetime')

            for d in cursor:
                bar = BarData()

                bar.gateway_name = 'mongodb'
                bar.symbol = d['code']
                bar.datetime = d['timetag']
                bar.open = d['open']
                bar.high = d['high']
                bar.low = d['low']
                bar.close = d['close']
                bar.volume = d['order_volume']

                if 'open_interst' in d.keys():
                    bar.open_interest = d['open_interest']
                if 'amount' in d.keys():
                    bar.amount = d['amount']
                if symbol[-2:] == 'SH':
                    bar.exchange = Exchange_SSE
                else:
                    bar.exchange = Exchange_SZSE

                # todo: 因为从mongodb中取出来的数据exchange、open_interest、amount字段不齐全，因此bar的相应字段值没法直接赋值，必须
                # todo: 判断后再赋值，因此BarData的结构没有得到充分应用，以后再看是要改进数据还是改进BarData结构

                # self.data_dict 新增一个item，其key键为当前品种bardata的时间，value值为当前品种bardata的值
                bar_dict = self.data_dict.setdefault(bar.datetime, OrderedDict())
                bar_dict[bar.symbol] = bar

            # print(u'%s数据加载完成，总数据量：%s' % (symbol, cursor.count()))

        print(u'全部数据加载完成')

    def run_backtesting(self):
        # 初始化　account_data
        if self.account:
            for account in self.account:
                Context.current_account_data = AccountData()
                Context.current_account_data.account_id = account
                Context.current_account_data.total_balance = self.account[account]
                Context.current_account_data.available = self.account[account]
                Context.bar_account_data_list.append(Context.current_account_data)

        # 实时交易模式下，最后时间为数据库中基准标的物的最后时间戳（日）
        if self.run_mode == RunMode_LIVE:
            self.end = self.get_data.get_end_timetag(benchmark=self.benchmark, interval=Interval_DAILY)

        # 缓存数据，和bar_index的计算
        stock_list = copy(self.universe)
        stock_list.append(self.benchmark)
        stock_list = list(set(stock_list))
        if self.interval == Interval_DAILY:
            Context.daily_data = self.get_data.get_all_market_data(stock_code=stock_list,
                                                                   field=["open", "close"],
                                                                   start=self.start,
                                                                   end=self.end,
                                                                   interval=Interval_DAILY)
            Context.benchmark_index = [datetime_to_timestamp(str(int(i)), '%Y%m%d')
                                       for i in Context.daily_data["close"].loc[self.benchmark].index
                                       if i >= self.start]
            self.bar_len = len(Context.benchmark_index)

        # print(self.benchmark, self.start, self.end, self.interval, self.rights_adjustment, self.run_mode)

        bmi_iter = iter(Context.benchmark_index)
        self.bar_index = 0

        self.strat_event_engine.start()
        while True:
            try:
                self.timestamp = next(bmi_iter)
            except Exception:
                # 回测完成
                print('策略运行完成')
                break
            else:
                # 在历史数据上跑，以实时的形式回测。之所以用时间戳为索引，是统一时间轴格式
                self.datetime = timestamp_to_datetime(self.timestamp, format="%Y%m%d")
                self.bar_index += 1
                cur_event = Event(EVENT_BAR, self.datetime)
                self.strat_event_engine.put(cur_event)
                # print("{0} {1}".format(self.datetime, cur_event.event_type))
                # run_bar_engine(self)        # 启动 bar_engine 进行事件驱动的回测

    def strategy_analysis(self):
        pass

    def show_results(self):
        pass

    def cross_limit_order(self):
        print("run deal_limit_order() method")

    def cross_stop_order(self):
        print("run deal_stop_order() method")

    def new_bar(self, bar: BarData):
        """"""
        self.cross_limit_order()
        self.cross_stop_order()
        self.handle_bar(bar)

    def handle_order(self):
        print("run handle_order_() method")
        pass

    def handle_risk(self):
        print("run handle_risk() method")
        pass

    def handle_trade(self):
        print("run handle_trade() method")
        pass

    def event_record(self):
        print("run update_bar_info() method")
        pass

    @abstractmethod
    def init_strategy(self):
        pass

    @abstractmethod
    def handle_bar(self, event):
        pass


class Trade(object):
    @classmethod
    def order_shares(cls, stock_code, shares, order_type, order_price, account):
        pass
