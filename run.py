# -*- coding: utf-8 -*-
"""
交易的入口文件
"""
from strategy.trial_strategy import TrialStrategy

# 实例化策略
strategy = TrialStrategy()

strategy.init_strategy()     # 初始化交易策略
# strategy.load_data_from_mongo()  # 调用数据
strategy.run_backtesting()    # 运行回测
strategy.strategy_analysis()    # 绩效分析
strategy.show_results()     # 运行结果展示

