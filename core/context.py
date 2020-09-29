# -*- coding: utf-8 -*-
"""
保存交易运行中的各类信息
"""

import pandas as pd

from .object import OrderData, TradeData, PositionData, AccountData


class Context(object):
    # key键 就是每一根 bar 的时间戳
    order_data_dict = {}        # timestamp : [order_data,order_data]　　mission_engine risk 之后append
    trade_data_dict = {}         # timestamp : [deal_data,deal_data]    broker_engine  deal 之后append
    position_data_dict = {}     # timestamp : [position_data,position_data]  broker_engine deal 之后append

    # timestamp : [account_data] ,account_data 只有一个，是当前bar最后一天的,main_engine market_close 之后append
    account_data_dict = {}

    current_order_data = OrderData()
    current_deal_data = TradeData()
    current_position_data = PositionData()
    current_account_data = AccountData()

    bar_order_data_list = []
    bar_deal_data_list = []
    bar_position_data_list = []
    bar_account_data_list = []

    daily_data = pd.DataFrame()
    index_daily_data = pd.DataFrame()

    benchmark_index = []

    # 风控部分
    black_name_list = []
    is_pass_risk = True
    is_send_order = False

    # 滑点值，key键是合约代码
    slippage_dict = {}

    # 手续费值，key键是合约代码
    commission_dict = {}

    # 每根bar结束，清空当前 bar 的 order 和　trade 的list
    @classmethod
    def refresh_list(cls, event):
        cls.bar_order_data_list = []
        cls.bar_deal_data_list = []
        print('清空当前bar的 order_list 和 deal_list')

    # 回测的交易记录
    backtesting_record_order = pd.DataFrame()
    backtesting_record_trade = pd.DataFrame()
    backtesting_record_position = pd.DataFrame()
    backtesting_record_account = pd.DataFrame()

    # 每次下单交易完成，经过回测 broker 之后清空 order 和 trade 的数据，重置是否通过风控
    @classmethod
    def refresh_current_data(cls, event):
        cls.current_order_data = OrderData()
        cls.current_deal_data = TradeData()
        cls.current_position_data = PositionData()
        cls.is_pass_risk = True
        cls.is_send_order = False
