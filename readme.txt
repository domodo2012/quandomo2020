quandomo 框架概述
一、数据存贮与使用
1、数据存贮
做3个接口，分别能把数据从远程oracle数据库取到之后，存入本地的bcolz库、mongodb、sqlite中。以后使用是时候以用bcolz为主，因为它的效率最高。
加入mongdb接口是因为它的代码是最齐全的，初期以它为主。
加入sqlite接口是因为它的学习与使用门槛最低，因为代码需要修改，以后再说。

	例程来源：我的python projects中的AmazingQuant_v2中有远程读取量价数据并存入本地mongodb的代码，最近5年的数据存入也已经完成。可以作为初步的基础，以后再补充完整。

2、数据使用
	目前将数据读取后直接推送入队列。
	下一个版本，数据从数据库读取后，或者从行情源接收到数据之后，先送入一个DataManager对象中，该对象根据要求可以输出不同周期的K线，然后再推入队列，这样就可以实现同一个行情源，不同周期数据的输出。

二、整体框架
	提供类似vnpy_noui的“面板文件”管理交易策略的通用参数，和通过对象方法分步骤控制策略的执行过程，大概是这样：

# run.py
Import …
from … import ExampleStrategy

# 参数
start_date = datetime(2013, 1, 4)
end_date = datetime(2018, 11, 9)
init_portfolio_capital = 10000000
settings = read_setting('symbol_setting.csv')

# 初始化引擎
engine = BacktestEngine(start_date,
                        end_date,
                        init_portfolio_capital,
                        settings)
engine.add_strategy(ExampleStrategy)	插入策略
engine.load_data_from_db()  # 调用数据
engine.init_portfolio_strategy()     # 初始化组合，载入交易策略
engine.run_backtesting()    # 运行回测
engine.show_performance()		# 显式绩效结果
engine.show_chart()        # 将交易标识在K线图上


三、事件驱动框架与交易流程
1、事件驱动引擎与策略基类耦合。
1）本版先只考虑单个策略的情况，下一版考虑多策略组合的情况。
2、策略运行之前就完成所有事件监听/回调函数的注册。其中：
1）类似AQ v1，委托单发出之前要先经过风控审核，而不是vnpy那样直接发出去。
2）在下一个版本中，实现对不同市场数据周期属性，回调不同的交易策略。
3、在while循环中以观察者模式为核心进行事件驱动。当数据源不是本地数据文件而是经纪商转发的行情数据时，策略能无缝进入paper trading甚至real trading的状态。。
4、回测时在最新bar上发出交易委托（不一定是该bar的close），在下个bar上以过价原则判断是否能成交。
5、交易运行过程中产生的委托、成交、持仓、账户信息都存入一个独立于交易策略的Context类中。
6、股票的分送转配、期货的换月都归属到一类事件中，当捕捉到这类事件，就进行持仓的相应变动，以及账户资金的变动计算（手续费率等）。

四、结果展示
1、采用AQ v1的界面显式绩效指标的情况，用vnpy2.1.6的新版界面显式K线和交易信号。


