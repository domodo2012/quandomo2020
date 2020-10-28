# -*- coding: utf-8 -*-
"""
常用的常量
"""
from enum import Enum


# 策略运行模式
class RunMode(Enum):
    BACKTESTING = "backtesting"
    LIVE = "live"


# 市场数据的周期级别/时间间隔
class Interval(Enum):
    MIN = "1m"
    HOUR = "1h"
    DAILY = "d"
    WEEKLY = "w"


# 除复权方式
class RightsAdjustment(Enum):
    NONE = "none"
    FROWARD = "forward"
    BACKWARD = "backward"


# 事件类别
class Event(Enum):
    TIMER = "event_timer"                         # 定时事件
    BAR = "event_bar"                             # 市场 bar 数据事件
    ORDER = "event_order"                         # 委托订单事件
    PORTFOLIO = "event_portfolio"                 # 投资组合层面的风控事件
    TRADE = "event_trade"                         # 成交/交易事件
    RECORD = "update_bar_info"                    # 数据记录事件
    LOG = "event_log"                             # 日志记录事件
    ACCOUNT = "event_account"                     # 账户事件
    RIGHTS = "event_rights"                       # 股票的分配送转事件
    DELIVERY = "event_delivery"                   # 期货交割事件
    STRATEGY = "event_strategy"                   # 组合管理器对所管策略的调整事件
    POOL = "event_pool"                           # 股票池更新事件
    BLACK_LIST = "event_black_list"               # 黑名单更新事件


# 零值
class Empty(Enum):
    eSTRING = ""
    eINT = 0
    eFLOAT = 0.0


# 订单/交易/持仓的方向
class Direction(Enum):
    LONG = "long"       # 做多
    SHORT = "short"     # 做空


# 开平仓状态
class Offset(Enum):
    OPEN = "open"
    CLOSE = "close"
    CLOSETODAY = "close_today"  # 平今
    CLOSEYESTERDAY = "close_yesterday"  # 平昨


# 委托单状态
class Status(Enum):
    SUBMITTING = "submitting"           # 待提交
    WITHDRAW = "withdraw"               # 已撤销
    NOT_TRADED = "pending"              # 未成交
    PART_TRADED = "partial filled"      # 部分成交
    ALL_TRADED = "filled"               # 全部成交
    CANCELLED = "cancelled"             # 已取消
    REJECTED = "rejected"               # 已拒绝
    UNKNOWN = "unknown"                 # 未知


# 委托单类型
class OrderType(Enum):
    LIMIT = "limit"         # 限价单
    MARKET = "market"       # 市价单
    STOP = "stop"           # 止损单
    FAK = "FAK"             # 立即成交，剩余的自动撤销的限价单
    FOK = "FOK"             # 立即全部成交否则自动撤销的限价单


# 止损单状态
class StopOrderStatus(Enum):
    WAITING = "等待中"
    CANCELLED = "已撤销"
    TRIGGERED = "已触发"


# 滑点类型
class Slippage(Enum):
    FIX = "slippage_fix"           # 固定值滑点
    PERCENT = "slippage_percent"   # 比例值滑点


# 交易所
class Exchange(Enum):
    CFFEX = "CFFEX"         # China Financial Futures Exchange
    SHFE = "SHFE"           # Shanghai Futures Exchange
    CZCE = "CZCE"           # Zhengzhou Commodity Exchange
    DCE = "DCE"             # Dalian Commodity Exchange
    INE = "INE"             # Shanghai International Energy Exchange
    SSE = "SSE"             # Shanghai Stock Exchange
    SZSE = "SZSE"           # Shenzhen Stock Exchange
    SGE = "SGE"             # Shanghai Gold Exchange


# 产品类别
class Product(Enum):
    STOCK = "stock"         # 股票
    STOCK_SH = "stock_sh"         # 上海股票
    STOCK_SZ = "stock_sz"         # 深圳股票
    FUTURES = "futures"     # 期货
    INDEX = "index"         # 指数


# mongodb 数据库名
class MongoDbName(Enum):
    MARKET_DATA_DAILY = "market_data_daily"
    FINANCIAL_DATA = "financial_data"
    MARKET_DATA_1_MIN = "market_data_1min"
    DAILY_DB_NAME = 'market_data_daily'
    MINUTE_DB_NAME = 'Min_Db'


# sqlite 数据库名
class SqliteDbName(Enum):
    DB = "quandomo_data.db"
    BASE = "base_data.db"
    MARKET = "market_data.db"
    FACTOR = "factor_data.db"


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

