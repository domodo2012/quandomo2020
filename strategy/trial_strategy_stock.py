# -*- coding: utf-8 -*-

import talib
from numpy import array
from pandas import Timedelta, to_datetime, isnull
from time import strftime

from core.const import RunMode, RightsAdjustment, Product, Slippage, Direction
from core.utility import date_str_to_int, Timer, Logger, ColorLogger
from strategy.strategy_base_backtest import StrategyBaseBacktestStock


# 继承strategy基类
class TrialStrategyStock(StrategyBaseBacktestStock):
    def __init__(self):
        super(TrialStrategyStock, self).__init__()

    def init_strategy(self, log_full_path: list, color_log=True, start_str='20180101', end_str='20200222'):  # 确定参数值
        self.gateway = 'ctp'
        self.run_mode = RunMode.BACKTESTING
        self.start = date_str_to_int(start_str)
        self.end = date_str_to_int(end_str)
        self.account = [{'name': 'acc0', 'equity': 200000}]
        self.benchmark = "000300.SH"
        self.rights_adjustment = RightsAdjustment.NONE  # 设置复权方式，决定画 K 线时的价格，对策略运行无影响

        # 设置股票池
        # self.universe = ['000001.SZ', '000002.SZ', '600000.SH', '600001.SH']
        self.universe = ['000001.SZ']

        # 设置回测滑点
        self.set_slippage(symbol_type=Product.STOCK.value, slippage_type=Slippage.FIX, value=0.01)

        # 设置回测股票手续费和印花税，卖出印花税，千分之一；开仓手续费，万分之三；平仓手续费，万分之三，最低手续费，５元
        # 沪市，卖出有万分之二的过户费，加入到卖出手续费中
        self.set_commission(symbol_type=Product.STOCK_SH, tax=0.001, open_commission=0.0003,
                            close_commission=0.0005,
                            close_today_commission=0, min_commission=5)
        # 深市不加过户费
        self.set_commission(symbol_type=Product.STOCK_SZ, tax=0.001, open_commission=0.0003,
                            close_commission=0.0003,
                            close_today_commission=0, min_commission=5)

        if not color_log:
            self.context.logger = Logger(log_full_path[0])
        else:
            self.context.logger = ColorLogger(log_full_path[0] + log_full_path[1])      # color log

    def calc_position_size(self, account_available, symbol_price):
        psize = account_available / len(self.universe) * 0.9 / symbol_price
        psize = int(psize / 100) * 100
        return psize

    def handle_bar(self, event_bar):
        self.context.logger.info("handle_bar() @ {0}".format(event_bar.dt))
        self.activate_trade_signal = False

        # 取当前bar的持仓情况
        available_position_dict = self.context.bar_position_data_dict

        account_data = self.context.current_account_data

        # 获取并计算出技术指标的起止时间，并转成正确格式待用
        current_date_int = date_str_to_int(event_bar.dt)
        cur_start_date = to_datetime(event_bar.dt) - Timedelta(days=60)
        cur_start_date_int = date_str_to_int(str(cur_start_date)[:10])

        # 循环遍历股票池
        for stock in self.universe:
            # 取当前股票的数据
            close_price = self.get_data.get_market_data(self.context.daily_data,
                                                        all_symbol_code=[stock],
                                                        field=["close"],
                                                        start=cur_start_date_int,
                                                        end=current_date_int)
            # close_array = array(close_price)
            if len(close_price) > 0:
                # 指标计算
                ma5 = talib.MA(array(close_price), timeperiod=5)
                ma20 = talib.MA(array(close_price), timeperiod=20)

                # 数据有效时才判断
                if current_date_int in close_price.keys() and (not isnull(ma5[-1])) and (not isnull(ma20[-1])):
                    # 如果5日均线突破20日均线，并且没有持仓，则买入这只股票100股，委托价为当前bar的收盘价
                    if ma5[-1] > ma20[-1]:
                        # live模式下，此处需要更新一次持仓状态，这样判别持仓才准确
                        if stock not in available_position_dict.keys():
                            self.activate_trade_signal = True
                            comments = "限价买入"
                            psize = self.calc_position_size(account_data.available, close_price.iloc[-1])
                            self.buy(event_bar.dt, self.account[0]['name'], stock, close_price.iloc[-1],
                                     psize, False, comments)

                            self.context.logger.info(
                                "-- 资金账号 {3} 发出委托买入 {0} {1} 股，委托价为 {2}".format(stock, psize, close_price.iloc[-1],
                                                                               self.account[0]['name']))

                    # 如果20日均线突破5日均线，并且有持仓，则卖出这只股票100股，委托价为当前bar的收盘价
                    elif ma5[-1] < ma20[-1]:
                        # live模式下，此处需要更新一次持仓状态，这样判别持仓才准确
                        if stock in available_position_dict.keys() and available_position_dict[stock].volume > 0 \
                                and available_position_dict[stock].direction == Direction.LONG:
                            self.activate_trade_signal = True
                            pos_abs = abs(available_position_dict[stock].volume)
                            comments = "限价卖出"
                            self.sell(event_bar.dt, self.account[0]['name'], stock,
                                      close_price.iloc[-1], pos_abs, False, comments)

                            self.context.logger.info(
                                "-- 资金账号 {3} 发出委托卖出 {0} {1} 股，委托价为 {2}".format(stock, pos_abs, close_price.iloc[-1],
                                                                               self.account[0]['name']))

    def handle_order(self, event_order):
        """针对委托单状态变动的响应"""
        self.context.logger.info('-- {0} 的委托单 {1} 当前状态是 {2}'.format(event_order.data.symbol,
                                                                    event_order.data.order_id,
                                                                    event_order.data.status))

    def handle_trade(self, event_trade):
        """成交后立即添加止损止盈"""
        self.context.logger.info('-- {0} 的委托单 {1} 已成交，如有必要请立即添加止损止盈'.format(event_trade.data.symbol,
                                                                            event_trade.data.order_id))


if __name__ == "__main__":
    output_path = 'D:/python projects/quandomo/doc/'
    log_name = '{0}.log'.format(strftime('%Y-%m-%d_%H%M%S'))
    is_color_log = True
    start_date = '20050104'
    end_date = '20190922'

    # 测试运行完整个策略所需时间
    time_test = Timer(True)
    with time_test:
        trial_strategy = TrialStrategyStock()
        trial_strategy.init_strategy([output_path, log_name], is_color_log, start_date, end_date)
        trial_strategy.run_strategy()
        trial_strategy.strategy_analysis(output_path)  # 绩效分析
        trial_strategy.show_results(output_path)  # 运行结果展示
