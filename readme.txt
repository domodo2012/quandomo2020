quandomo 框架概述
一、数据存贮与使用
1、数据存贮
从最基础的远程数据库中取数据，以相同的结构保存到本地（sqlite）数据库中。

2、数据使用
回测时，将数据从本地数据库中读取后，逐个时间戳形成市场事件推送入队列。
然后从队列中取数据，针对不同的事件类型，已注册的不同监控函数对应响应。

二、整体框架
1、后台事务在策略的父类中进行，具体的策略本身继承之后，重写 handle_bar、handle_order、handle_trade 等方法，实现具体的策略。
2、回测时，将数据从本地数据库中读出，逐个时间戳新建市场事件并推送入队列，之后从队列中取事件，不同的事件类型有已注册的不同监控函数响应，从而驱动策略运行。

三、例程
# ExampleStrategy.py
# -*- coding: utf-8 -*-
Import …
from … import ...

class TrialStrategyStock(StrategyBaseBacktestStock):
    def __init__(self, universe_limit):
        super(TrialStrategyStock, self).__init__(universe_limit)

    def init_strategy(self, log_full_path: list, color_log=True, start_str='20180101', end_str='20200222'):  # 确定参数值
        self.gateway = 'ctp'
        self.run_mode = RunMode.BACKTESTING
        self.start = date_str_to_int(start_str)
        self.end = date_str_to_int(end_str)
        self.account = [{'name': 'acc0', 'equity': 200000}]
        self.benchmark = "000300.SH"
        # self.rights_adjustment = RightsAdjustment.NONE  # 只在画 K 线时有效，对策略运行无影响

        # 动态股票池（沪深300指数成分股）
        self.is_universe_dynamic = '000300.SH'

        # 固定股票池
        # self.is_universe_dynamic = False
        # self.universe = ['000562.SZ', '600710.SH', '600757.SH', '600761.SH']

        # 设置回测滑点
        self.set_slippage(symbol_type=Product.STOCK.value, slippage_type=Slippage.FIX, value=0.01)

        # 设置沪市交易成本
        self.set_commission(symbol_type=Product.STOCK_SH, tax=0.001, open_commission=0.0003,
                            close_commission=0.0005,
                            close_today_commission=0, min_commission=5)
        # 设置深市交易成本
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

        available_position_dict = self.context.bar_position_data_dict
        account_data = self.context.current_account_data

        current_date_int = date_str_to_int(event_bar.dt)
        cur_start_date = to_datetime(event_bar.dt) - Timedelta(days=60)
        cur_start_date_int = date_str_to_int(str(cur_start_date)[:10])

        # 循环处理旧持仓
        for pos_symbol in available_position_dict.keys():
            close_price = self.get_data.get_market_data(self.context.daily_data,
                                                        all_symbol_code=[pos_symbol],
                                                        field=["close"],
                                                        start=cur_start_date_int,
                                                        end=current_date_int)
            if len(close_price) > 0:
                # 指标计算
                ma5 = talib.MA(array(close_price), timeperiod=5)
                ma20 = talib.MA(array(close_price), timeperiod=20)

                if current_date_int in close_price.keys() and (not isnull(ma5[-1])) and (not isnull(ma20[-1])):
                    if ma5[-1] < ma20[-1]:
                        if available_position_dict[pos_symbol].volume > 0 and available_position_dict[pos_symbol].direction == Direction.LONG:
                            self.activate_trade_signal = True
                            pos_abs = abs(available_position_dict[pos_symbol].volume)
                            comments = "限价卖出"
                            self.sell(event_bar.dt, self.account[0]['name'], pos_symbol,
                                      close_price.iloc[-1], pos_abs, False, comments)

                            self.context.logger.info(
                                "-- 资金账号 {3} 发出委托卖出 {0} {1} 股，委托价为 {2}".format(pos_symbol, pos_abs,
                                                                               close_price.iloc[-1],
                                                                               self.account[0]['name']))

        # 循环遍历股票池，看是否有新信号
        for symbol in self.universe:
            # 取当前股票的数据
            close_price = self.get_data.get_market_data(self.context.daily_data,
                                                        all_symbol_code=[symbol],
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
                        if symbol not in available_position_dict.keys():
                            self.activate_trade_signal = True
                            comments = "限价买入"
                            # psize = self.calc_position_size(account_data.available, close_price.iloc[-1])
                            psize = 300
                            if psize > 0:
                                self.buy(event_bar.dt, self.account[0]['name'], symbol, close_price.iloc[-1],
                                         psize, False, comments)

                                self.context.logger.info(
                                    "-- 资金账号 {0} 发出委托买入 {1} {2} 股，委托价为 {3}".format(self.account[0]['name'],
                                                                                   symbol, psize, close_price.iloc[-1]))

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
    start_date = '20160104'     # hs300 成分股数据开始于 20050408
    end_date = '20190902'
    universe_limit = 5

    # 测试运行完整个策略所需时间
    time_test = Timer(True)
    with time_test:
        trial_strategy = TrialStrategyStock(universe_limit)
        trial_strategy.init_strategy([output_path, log_name], is_color_log, start_date, end_date)
        trial_strategy.run_strategy()
        trial_strategy.strategy_analysis(output_path)  # 绩效分析
        trial_strategy.show_results(output_path)  # 运行结果展示


四、结果展示
1、log 文件（节选）
[32m[2020-11-02 12:33:17,289] [INFO]- handle_bar() @ 20170519[0m
[32m[2020-11-02 12:33:17,301] [INFO]- handle_bar() @ 20170522[0m
[32m[2020-11-02 12:33:17,312] [INFO]- handle_bar() @ 20170523[0m
[32m[2020-11-02 12:33:17,325] [INFO]- handle_bar() @ 20170524[0m
[32m[2020-11-02 12:33:17,338] [INFO]- -- 600000.SH 今日 20170525 除权除息，所持仓位量价相应变动[0m
[32m[2020-11-02 12:33:17,339] [INFO]- handle_bar() @ 20170525[0m
[32m[2020-11-02 12:33:17,343] [INFO]- -- 资金账号 acc0 发出委托卖出 600000.SH 389.99999999999994 股，委托价为 12.93[0m
[32m[2020-11-02 12:33:17,348] [INFO]- -- 资金账号 acc0 发出委托买入 000001.SZ 300 股，委托价为 9.1[0m
[32m[2020-11-02 12:33:17,352] [INFO]- -- 资金账号 acc0 发出委托买入 000002.SZ 300 股，委托价为 20.5[0m
[32m[2020-11-02 12:33:17,356] [INFO]- -- 600000.SH 的委托单 order_45210397 当前状态是 Status.NOT_TRADED[0m
[32m[2020-11-02 12:33:17,356] [INFO]- -- 000001.SZ 的委托单 order_23461750 当前状态是 Status.NOT_TRADED[0m
[32m[2020-11-02 12:33:17,357] [INFO]- -- 000002.SZ 的委托单 order_07982456 当前状态是 Status.NOT_TRADED[0m
[32m[2020-11-02 12:33:17,359] [INFO]- -- 600000.SH 的委托单 order_45210397 无法成交，撤回重发[0m
[32m[2020-11-02 12:33:17,360] [INFO]- -- 600000.SH 的委托单 order_45210397 当前状态是 Status.WITHDRAW[0m
[32m[2020-11-02 12:33:17,360] [INFO]- -- 资金账号 acc0 发出委托卖出 600000.SH 389.99999999999994 股，委托价为 12.81[0m
[32m[2020-11-02 12:33:17,361] [INFO]- -- 600000.SH 的委托单 order_78069125 当前状态是 Status.NOT_TRADED[0m
[32m[2020-11-02 12:33:17,361] [INFO]- -- 600000.SH 的委托单 order_78069125 当前状态是 Status.ALL_TRADED[0m
[32m[2020-11-02 12:33:17,362] [INFO]- -- 600000.SH 的委托单 order_78069125 于 20170526 成交，成交价为 12.92[0m
[32m[2020-11-02 12:33:17,363] [INFO]- -- 600000.SH 的委托单 order_78069125 已成交，如有必要请立即添加止损止盈[0m
[32m[2020-11-02 12:33:17,364] [INFO]- -- 000001.SZ 的委托单 order_23461750 当前状态是 Status.ALL_TRADED[0m
[32m[2020-11-02 12:33:17,366] [INFO]- -- 000001.SZ 的委托单 order_23461750 于 20170526 成交，成交价为 9.09[0m
[32m[2020-11-02 12:33:17,366] [INFO]- -- 000001.SZ 的委托单 order_23461750 已成交，如有必要请立即添加止损止盈[0m
[32m[2020-11-02 12:33:17,367] [INFO]- -- 000002.SZ 的委托单 order_07982456 当前状态是 Status.ALL_TRADED[0m
[32m[2020-11-02 12:33:17,368] [INFO]- -- 000002.SZ 的委托单 order_07982456 于 20170526 成交，成交价为 20.31[0m
[32m[2020-11-02 12:33:17,369] [INFO]- -- 000002.SZ 的委托单 order_07982456 已成交，如有必要请立即添加止损止盈[0m
[32m[2020-11-02 12:33:17,370] [INFO]- handle_bar() @ 20170526[0m
[32m[2020-11-02 12:33:17,388] [INFO]- handle_bar() @ 20170531[0m
[32m[2020-11-02 12:33:17,405] [INFO]- handle_bar() @ 20170601[0m
....

2、策略简要绩效指标
+-----------------------------------------------+
| Start Date                        |  20160104 |
| End Date                          |  20170902 |
| Initial Equity                    |    200000 |
| Final Equity                      | 210881.55 |
| total commission                  | 1400.5727 |
| Benchmark Annual Return % (arith) |    6.2657 |
| Strategy Annual Return % (arith)  |    3.2716 |
| Strategy Volatility               |    0.0255 |
| Strategy Max Drawdown %           |      -2.0 |
| Sharp Ratio                       |    2.1368 |
| Downside Risk                     |    0.0013 |
| Sortino Ratio                     |   40.7727 |
| Tracking Error                    |    0.1625 |
| Information Ratio                 |   -0.1842 |
+-----------------------------------------------+

五、其他



