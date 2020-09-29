# -*- coding: utf-8 -*-
"""
策略基类，包含了事件驱动的运行框架
"""
from tqdm import tqdm
from abc import abstractmethod
from copy import copy
from pymongo import MongoClient
from collections import OrderedDict

from core.utility import datetime_to_timestamp, date_str_to_int, timestamp_to_datetime
from core.const import RunMode, Interval, MongoDbName, Exchange, EventType
from core.object import AccountData, BarData
from core.context import Context
from engine.event_engine_base import EventEngineBase


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
        self.timestamp = 0
        self.bar_index = 0
        self.bar_len = 0

        self.data_dict = OrderedDict()
        self.trade_dict = OrderedDict()

        # 事件驱动引擎的实例化
        self.strat_event_engine = EventEngineBase(timer_interval=0.2)

        # 市场事件的监听/回调函数注册
        self.strat_event_engine.register(EventType.EVENT_MARKET, self.handle_bar)
        self.strat_event_engine.register(EventType.EVENT_MARKET, self.handle_bar)
        self.strat_event_engine.register(EventType.EVENT_MARKET, self.handle_bar)
        self.strat_event_engine.register(EventType.EVENT_MARKET, self.handle_bar)



    def load_data_from_mongo(self):
        """加载策略运行所用数据"""
        mc = MongoClient()
        db = mc[MongoDbName.DAILY_DB_NAME.value]

        for symbol in self.universe:
            flt = {'timetag': {'$gte': self.start, '$lte': self.end}}
            cursor = db[symbol].find(flt).sort('datetime')

            for d in cursor:
                bar = BarData()

                bar.gateway_name = 'mongodb'
                bar.symbol = symbol
                bar.datetime = d['timetag']
                bar.open = d['open']
                bar.high = d['high']
                bar.low = d['low']
                bar.close = d['close']
                bar.volume = d['volume']

                if 'open_interst' in d.keys():
                    bar.open_interest = d['open_interest']
                if 'amount' in d.keys():
                    bar.amount = d['amount']
                if symbol[-2:] == 'SH':
                    bar.exchange = Exchange.SSE.value
                else:
                    bar.exchange = Exchange.SZSE.value

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
        if self.run_mode == RunMode.TRADE.value:
            self.end = self.get_data.get_end_timetag(benchmark=self.benchmark, interval=Interval.DAILY.value)

        # 缓存数据，和bar_index的计算
        stock_list = copy(self.universe)
        stock_list.append(self.benchmark)
        stock_list = list(set(stock_list))
        if self.interval == Interval.DAILY.value:
            Context.daily_data = self.get_data.get_all_market_data(stock_code=stock_list,
                                                                   field=["open", "close"],
                                                                   start=self.start,
                                                                   end=self.end,
                                                                   interval=Interval.DAILY.value)
            Context.benchmark_index = [datetime_to_timestamp(str(int(i)), '%Y%m%d')
                                       for i in Context.daily_data["close"].loc[self.benchmark].index
                                       if i >= self.start]
            self.bar_len = len(Context.benchmark_index)

        # print(self.benchmark, self.start, self.end, self.interval, self.rights_adjustment, self.run_mode)

        self.bar_index = 0
        # while True:
        while:
            try:
                self.timestamp = Context.benchmark_index[self.bar_index]
                cur_event = self.strat_event_engine.get()
            except IndexError:
                # 回测完成
                print('策略运行完成')
                break
            else:
                # 在历史数据上跑，以实时的形式回测。之所以用时间戳为索引，是统一时间轴格式
                date = int(timestamp_to_datetime(timestamp=self.timestamp, format="%Y%m%d"))
                print(date)
                # run_bar_engine(self)        # 启动 bar_engine 进行事件驱动的回测

    def strategy_analysis(self):
        pass

    def show_results(self):
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
