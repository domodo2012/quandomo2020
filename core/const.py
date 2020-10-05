# -*- coding: utf-8 -*-
"""
常用的常量
"""

# 策略运行模式
RunMode_BACKTESTING = "backtesting"
RunMode_LIVE = "live"

# 市场数据的周期级别/时间间隔
Interval_MIN = "1m"
Interval_HOUR = "1h"
Interval_DAILY = "d"
Interval_WEEKLY = "w"

# 除复权方式
RightsAdjustment_NONE = "none"
RightsAdjustment_FROWARD = "forward"
RightsAdjustment_BACKWARD = "backward"

# 事件类别
EVENT_TIMER = "event_timer"                         # 定时事件
EVENT_MARKET = "event_market"                       # 市场数据事件
EVENT_ORDER = "event_order"                         # 委托订单事件
EVENT_RISK_MANAGEMENT = "event_risk_management"     # 事前风控事件
EVENT_TRADE = "event_trade"                         # 成交/交易事件
EVENT_RECORD = "update_bar_info"                       # 数据记录事件
EVENT_ONBAR = "event_on_bar"                        # 对bar的响应事件
EVENT_LOG = "event_log"                             # 日志记录事件
EVENT_ACCOUNT = "event_account"                     # 账户事件
EVENT_RIGHTS = "event_rights"                       # 股票的分配送转事件
EVENT_DELIVERY = "event_delivery"                   # 期货交割事件
EVENT_STRATEGY = "event_strategy"                   # 组合管理器对所管策略的调整事件

Record_ORDER_DATA = "order_data"
Record_TRADE_DATA = "trade_data"
Record_POSITION_DATA = "position_data"
Record_ACCOUNT_DATA = "account_data"

# 零值
EMPTY_STRING = ""
EMPTY_INT = 0
EMPTY_FLOAT = 0.0

# 订单/交易/持仓的方向
Direction_NONE = "None"
Direction_LONG = "long"       # 做多
Direction_SHORT = "short"     # 做空

# 开平仓状态
Offset_NONE = ""
Offset_OPEN = "open"
Offset_CLOSE = "close"
Offset_CLOSETODAY = "close_today"  # 平今
Offset_CLOSEYESTERDAY = "close_yesterday"  # 平昨

# 委托单状态
Status_SUBMITTING = "submitting"           # 待提交
Status_WITHDRAW = "withdraw"               # 已撤销
Status_NOT_TRADED = "pending"              # 未成交
Status_PART_TRADED = "partial filled"      # 部分成交
Status_ALL_TRADED = "filled"               # 全部成交
Status_CANCELLED = "cancelled"             # 已取消
Status_REJECTED = "rejected"               # 已拒绝
Status_UNKNOWN = "unknown"                 # 未知

# 委托单类型
OrderType_LIMIT = "limit"         # 限价单
OrderType_MARKET = "market"       # 市价单
OrderType_STOP = "stop"           # 止损单
OrderType_FAK = "FAK"             # 立即成交，剩余的自动撤销的限价单
OrderType_FOK = "FOK"             # 立即全部成交否则自动撤销的限价单

# 止损单状态
StopOrderStatus_WAITING = "等待中"
StopOrderStatus_CANCELLED = "已撤销"
StopOrderStatus_TRIGGERED = "已触发"

# 滑点类型
SLIPPAGE_FIX = "slippage_fix"           # 固定值滑点
SLIPPAGE_PERCENT = "slippage_percent"   # 比例值滑点

# 交易所
Exchange_CFFEX = "CFFEX"         # China Financial Futures Exchange
Exchange_SHFE = "SHFE"           # Shanghai Futures Exchange
Exchange_CZCE = "CZCE"           # Zhengzhou Commodity Exchange
Exchange_DCE = "DCE"             # Dalian Commodity Exchange
Exchange_INE = "INE"             # Shanghai International Energy Exchange
Exchange_SSE = "SSE"             # Shanghai Stock Exchange
Exchange_SZSE = "SZSE"           # Shenzhen Stock Exchange
Exchange_SGE = "SGE"             # Shanghai Gold Exchange

# 产品类别
Product_STOCK = "stock"         # 股票
Product_STOCK_SH = "stock_sh"         # 股票
Product_STOCK_SZ = "stock_sz"         # 股票
Product_FUTURES = "futures"     # 期货
Product_INDEX = "index"         # 指数

# 数据库名（主要是mongodb里的）"""
MongoDbName_MARKET_DATA_DAILY = "market_data_daily"
MongoDbName_FINANCIAL_DATA = "financial_data"
MongoDbName_MARKET_DATA_1_MIN = "market_data_1min"
MongoDbName_DAILY_DB_NAME = 'market_data_daily'
MongoDbName_MINUTE_DB_NAME = 'Min_Db'

Futures_contracts = {
    'SHFE': ['cu', 'al', 'zn', 'ni', 'sn', 'au', 'ag', 'rb', 'wr', 'hc', 'ss',
             'fu', 'bu', 'ru', 'sp'],
    'DCE': ['a', 'b', 'm', 'y', 'p', 'c', 'cs', 'jd', 'rr',
            'l', 'v', 'pp', 'eb', 'j', 'jm', 'i', 'eg', 'pg'],
    'CZCE': ['AP', 'CF', 'CJ', 'CY', 'FG', 'JR', 'LR', 'MA', 'OI', 'RM', 'SA', 'SF', 'SM', 'SR',
             'TA', 'UR', 'ZC'],
    'CFFEX': ['IC', 'IF', 'IH', 'TS', 'TF', 'T'],
    'INE': ['sc', 'lu', 'nr']
}
