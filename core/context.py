# -*- coding: utf-8 -*-
"""
保存交易运行中的各类信息
"""

import pandas as pd

from .object import OrderData, TradeData, PositionData, AccountData


class Context(object):
    def __init__(self, gateway):
        self.gateway = gateway

        # 三层嵌套dict变量，每一根 bar 的时间戳是 dict 的 key
        self.account_data_dict = {}    # {timestamp : [account_data]}, 基于close，update_bar_info 后append
        self.order_data_dict = {}      # {timestamp : [order_data,order_data]}, handle_order 后append, handle_risk后update
        self.trade_data_dict = {}         # {timestamp : [deal_data,deal_data]}, handle_trade_ 后append
        self.position_data_dict = {}     # timestamp : [position_data,position_data]  handle_trade_ 后append
        self.commission_data_dict = {}

        self.bar_order_data_dict = {}   # 每个bar上有可能不止一个order
        self.bar_trade_data_dict = {}
        self.bar_position_data_dict = {}
        self.bar_account_data_dict = {}
        self.bar_commission_data_dict = {}

        self.current_order_data = OrderData()
        self.current_trade_data = TradeData()
        self.current_commission_data = 0
        self.current_position_data = PositionData()
        self.current_account_data = AccountData()

        self.active_stop_orders = {}            # 动态未成交止损单
        self.stop_orders = {}                   # 已成交止损单合集
        self.active_limit_orders = {}           # 动态未成交限价单
        self.limit_orders = {}                  # 已成交限价单合集

        # 各类交易的总数
        self.stop_order_count = 0
        self.limit_order_count = 0
        self.trade_count = 0

        # 市场数据
        self.daily_data = pd.DataFrame()
        self.index_daily_data = pd.DataFrame()
        self.benchmark_index = []
        self.ex_rights_dict = None

        # 风控
        self.black_name_list = None
        self.is_pass_risk = True
        self.is_send_order = False

        # 滑点值参数，key 键是合约代码
        self.slippage_dict = {}

        # 手续费参数，key 键是合约代码
        self.commission_dict = {}

        # 回测的交易记录
        self.backtesting_record_order = pd.DataFrame()
        self.backtesting_record_trade = pd.DataFrame()
        self.backtesting_record_position = pd.DataFrame()
        self.backtesting_record_account = pd.DataFrame()

        self.logger = None

    def init_account(self, accounts):
        for ai, acc in enumerate(accounts):
            self.current_account_data = AccountData()       # 这里必须新建一个AccountData对象，不然下边添加的是同一个
            self.current_account_data.account_id = acc['name']
            self.current_account_data.gateway = self.gateway
            self.current_account_data.total_balance = acc['equity']
            self.current_account_data.available = acc['equity']
            self.bar_account_data_dict[acc['name']] = self.current_account_data

    # 每根bar结束，清空当前 bar 的 order 和　trade 的list
    def refresh_bar_dict(self):
        self.bar_order_data_dict = {}
        self.bar_trade_data_dict = {}
        self.bar_commission_data_dict = {}
        # self.context.logger.info('-- this is Context.refresh_bar_dict 清空当前bar的 order_dict 和 trade_dict')

    # 每次委托成交后，清空 order 和 trade 的数据，重置是否通过风控
    def refresh_current_data(self):
        self.current_order_data = OrderData()
        self.current_trade_data = TradeData()
        self.current_position_data = PositionData()
        self.is_pass_risk = True
        self.is_send_order = False
