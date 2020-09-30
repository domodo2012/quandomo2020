# -*- coding: utf-8 -*-
"""
常用的常量
"""

from enum import Enum, unique


@unique
class RunMode(Enum):
    """策略运行模式"""
    BACKTESTING = "backtesting"
    TRADE = "trade"


@unique
class Interval(Enum):
    """市场数据的周期级别/时间间隔"""
    MIN = "1m"
    HOUR = "1h"
    DAILY = "d"
    WEEKLY = "w"


@unique
class RightsAdjustment(Enum):
    """除复权方式"""
    NONE = "none"
    FROWARD = "forward"
    BACKWARD = "backward"


@unique
class DatabaseName(Enum):
    """数据库名（主要是mongodb里的）"""
    MARKET_DATA_DAILY = "market_data_daily"
    FINANCIAL_DATA = "financial_data"
    MARKET_DATA_ONE_MIN = "market_data_1min"


@unique
class EventType(Enum):
    """事件类别"""
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


@unique
class ID(Enum):
    BROKER_ID = "broker"
    FRONT_ID = "front"
    ORDER_ID = "order"
    DEAL_ID = "deal"


@unique
class RecordDataType(Enum):
    ORDER_DATA = "order_data"
    DEAL_DATA = "deal_data"
    POSITION_DATA = "position_data"
    ACCOUNT_DATA = "account_data"


class EmptyType(Enum):
    """零值"""
    EMPTY_STRING = ""
    EMPTY_INT = 0
    EMPTY_FLOAT = 0.0


@unique
class Direction(Enum):
    """订单/交易/持仓的方向
    """
    NONE = "None"
    LONG = "long"       # 做多
    SHORT = "short"     # 做空


@unique
class Offset(Enum):
    """开平仓状态"""
    NONE = ""
    OPEN = "open"
    CLOSE = "close"
    CLOSETODAY = "close_today"  # 平今
    CLOSEYESTERDAY = "close_yesterday"  # 平昨


@unique
class Status(Enum):
    """委托单状态"""
    SUBMITTING = "submitting"           # 待提交
    WITHDRAW = "withdraw"               # 已撤销
    NOT_TRADED = "pending"              # 未成交
    PART_TRADED = "partial filled"      # 部分成交
    ALL_TRADED = "filled"               # 全部成交
    CANCELLED = "cancelled"             # 已取消
    REJECTED = "rejected"               # 已拒绝
    UNKNOWN = "unknown"                 # 未知


@unique
class OrderType(Enum):
    """委托单类型"""
    LIMIT = "limit"         # 限价单
    MARKET = "market"       # 市价单
    STOP = "STOP"           # 止损单
    FAK = "FAK"             # 立即成交，剩余的自动撤销的限价单
    FOK = "FOK"             # 立即全部成交否则自动撤销的限价单


@unique
class SlippageType(Enum):
    """滑点类型"""
    SLIPPAGE_FIX = "slippage_fix"           # 固定值滑点
    SLIPPAGE_PERCENT = "slippage_percent"   # 比例值滑点


@unique
class Exchange(Enum):
    """交易所"""
    # Chinese
    CFFEX = "CFFEX"         # China Financial Futures Exchange
    SHFE = "SHFE"           # Shanghai Futures Exchange
    CZCE = "CZCE"           # Zhengzhou Commodity Exchange
    DCE = "DCE"             # Dalian Commodity Exchange
    INE = "INE"             # Shanghai International Energy Exchange
    SSE = "SSE"             # Shanghai Stock Exchange
    SZSE = "SZSE"           # Shenzhen Stock Exchange
    SGE = "SGE"             # Shanghai Gold Exchange


@unique
class Product(Enum):
    """产品类别"""
    STOCK = "Stock"         # 股票
    FUTURES = "futures"     # 期货
    INDEX = "index"         # 指数


@unique
class StockType(Enum):
    """"""
    pass

@unique
class MongoDbName(Enum):
    """mongodb中的数据库名"""
    DAILY_DB_NAME = 'market_data_daily'
    MINUTE_DB_NAME = 'Min_Db'
