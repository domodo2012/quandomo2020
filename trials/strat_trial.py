# -*- coding: utf-8 -*-

import talib
from numpy import array
from pandas import Timedelta, to_datetime, isnull

from core.const import *
from core.utility import (
    date_str_to_int,
    Timer,
)
from trials.event_drive_trial import StrategyBase


# 继承strategy基类
class TrialStrategy(StrategyBase):
    def __init__(self):
        super(TrialStrategy, self).__init__()

    def init_strategy(self):  # 父类中有定义，但是没有实现，此处实现
        # 设置运行模式，回测或者交易
        self.gateway = 'ctp'
        self.run_mode = RunMode_BACKTESTING
        self.start = date_str_to_int("20050104")  # 设置回测起止时间
        self.end = date_str_to_int("20060222")
        # self.interval = "d"  # 设置运行周期
        self.account = [{'name': 'acc0', 'equity': 1000000},
                        {'name': 'acc1', 'equity': 1000}]  # 设置资金账号及初始资金量
        self.benchmark = "000300.SH"  # 设置回测基准
        # self.rights_adjustment = RightsAdjustment_NONE  # 设置复权方式

        # 设置股票池
        # self.universe = ['000001.SZ', '000002.SZ', '600000.SH', '600001.SH']
        self.universe = ['000001.SZ', '600000.SH']

        # 组合中所有合约的持仓量初始化
        # for ss in self.universe:
        #     self.context.pos[ss] = 0

        # 回测滑点设置
        # self.set_slippage_type = 'FIX'
        self.set_slippage(stock_type=Product_STOCK, slippage_type=SLIPPAGE_FIX, value=0.01)

        # 回测股票手续费和印花税，卖出印花税，千分之一；开仓手续费，万分之三；平仓手续费，万分之三，最低手续费，５元
        # 沪市，卖出有万分之二的过户费，加入到卖出手续费
        self.set_commission(stock_type=Product_STOCK_SH, tax=0.001, open_commission=0.0003,
                            close_commission=0.0003,
                            close_today_commission=0, min_commission=5)
        # 深市不加过户费
        self.set_commission(stock_type=Product_STOCK_SZ, tax=0.001, open_commission=0.0003,
                            close_commission=0.0005,
                            close_today_commission=0, min_commission=5)

    def handle_bar(self, event_market):
        print("-- this is handle_bar() method @ {0}".format(event_market.dt))

        # 取当前bar的持仓情况
        available_position_dict = {}
        for position in self.context.bar_position_data_list:
            available_position_dict[position.instrument + "." + position.exchange] = position.position

        # 当前bar的具体时间，时间str转换成int，方便后面取数据时过滤
        current_date_int = date_str_to_int(event_market.dt)
        cur_start_date = to_datetime(event_market.dt) - Timedelta(days=40)
        cur_start_date_int = date_str_to_int(str(cur_start_date)[:10])

        # 循环遍历股票池
        for stock in self.universe:
            # 取当前股票的数据
            close_price = self.get_data.get_market_data(self.context.daily_data,
                                                        stock_code=[stock],
                                                        field=["close"],
                                                        start=cur_start_date_int,
                                                        end=current_date_int)
            close_array = array(close_price)
            if len(close_array) > 0:
                # 利用talib计算MA
                ma5 = talib.MA(array(close_price), timeperiod=5)
                ma20 = talib.MA(array(close_price), timeperiod=20)

                # 过滤因为停牌没有数据
                if current_date_int in close_price.keys() and (not isnull(ma5[-1])) and (not isnull(ma20[-1])):
                    # 如果5日均线突破20日均线，并且没有持仓，则买入这只股票100股，委托价为当前bar的收盘价
                    if ma5[-1] > ma20[-1] and stock not in available_position_dict.keys():
                        comments = "限价买入"
                        self.buy(event_market.dt, self.account[0]['name'], stock, close_array[-1], 100, False, comments)

                        print("发出委托买入股票 {0} {1} 股，委托价为 {2}，资金账号为 {3} ...".
                              format(stock, 100, close_array[-1], self.account[0]['name']))

                    # 如果20日均线突破5日均线，并且有持仓，则卖出这只股票100股，委托价为当前bar的收盘价
                    elif ma5[-1] < ma20[-1] and stock in available_position_dict.keys():
                        pos_abs = abs(available_position_dict[stock])
                        comments = "限价卖出"
                        self.sell(event_market.dt, self.account[0]['name'], stock,
                                  close_array[-1], pos_abs, False, comments)

                        print("发出委托卖出股票 {0} {1} 股，委托价为 {2}，资金账号为 {3} ...".
                              format(stock, pos_abs, close_array[-1], self.account[0]['name']))


if __name__ == "__main__":
    # 测试运行完整个策略所需时间
    time_test = Timer(True)
    with time_test:
        trial_strategy = TrialStrategy()
        trial_strategy.init_strategy()
        trial_strategy.run_strategy()
        trial_strategy.strategy_analysis()  # 绩效分析
        trial_strategy.show_results()  # 运行结果展示
