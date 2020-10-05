# -*- coding: utf-8 -*-
"""
常用的数据对象
"""

from dataclasses import dataclass
from datetime import datetime
from logging import INFO

from const import *

ACTIVE_STATUSES = {Status_SUBMITTING, Status_NOT_TRADED, Status_PART_TRADED}


@dataclass
class BaseData:
    """基类"""
    gateway_name: str = EMPTY_STRING


@dataclass
class BarData(BaseData):
    """K线数据类"""
    symbol: str = EMPTY_STRING
    exchange: str = EMPTY_STRING
    datetime: datetime = None

    interval: str = None
    open: float = EMPTY_FLOAT
    high: float = EMPTY_FLOAT
    low: float = EMPTY_FLOAT
    close: float = EMPTY_FLOAT
    volume: float = EMPTY_FLOAT
    open_interest: float = EMPTY_FLOAT
    amount: float = EMPTY_FLOAT

    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange}"


@dataclass
class OrderData(BaseData):
    """委托订单类"""
    # 代码信息
    symbol: str = EMPTY_STRING
    exchange: str = Exchange_SSE
    orderid: str = EMPTY_STRING

    # 报单信息
    type: str = OrderType_LIMIT            # 报单类型
    direction: str = None                         # 报单方向（期货）
    offset: str = Offset_NONE                  # 报单开平仓
    price: float = EMPTY_FLOAT          # 报单价格
    volume: float = EMPTY_FLOAT         # 报单数量
    traded: float = EMPTY_FLOAT         # 报单成交数量
    status: str = Status_SUBMITTING           # 报单状态
    order_datetime: datetime = None                     # 报单时间
    cancel_datetime: datetime = None                    # 撤单时间

    # 实际交易时信息
    front_id: str = EMPTY_STRING        # 前置机编号，实际交易用
    session_id: str = EMPTY_STRING      # 连接编号，实际交易用

    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange}"
        self.orderid_full = f"{self.gateway_name}.{self.orderid}"

    def is_active(self) -> bool:
        """委托订单还未成交吗？"""
        if self.status in ACTIVE_STATUSES:
            return True
        else:
            return False


@dataclass
class TradeData(BaseData):
    """交易/成交数据用于保存委托订单的成交情况，一笔委托可能有多笔成交数据"""
    # 代码编号信息
    symbol: str = EMPTY_STRING                             # 合约代码
    exchange: str = Exchange_SSE                     # 交易所代码
    orderid: str = EMPTY_STRING                            # 订单编号
    tradeid: str = EMPTY_STRING                            # 成交单编号

    # 成交相关
    direction: str = None                 # 交易方向
    offset: str = Offset_NONE               # 成交开平
    price: float = EMPTY_FLOAT        # 成交价格
    volume: float = EMPTY_FLOAT       # 成交数量
    datetime: datetime = None                   # 成交时间
    multiplier: int = EMPTY_INT      # 合约乘数
    price_tick: float = EMPTY_FLOAT   # 最小价格跳动
    margin: float = EMPTY_FLOAT       # 保证金率
    tax: float = EMPTY_FLOAT          # 印花税率
    slippage: float = EMPTY_FLOAT     # 滑点值
    commission: float = EMPTY_FLOAT   # 手续费率

    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange}"
        self.orderid_full = f"{self.gateway_name}.{self.orderid}"
        self.tradeid_full = f"{self.gateway_name}.{self.tradeid}"


@dataclass
class PositionData(BaseData):
    """持仓数据，跟踪每一个持仓头寸"""
    # 编号代码信息
    symbol: str = EMPTY_STRING                                 # 合约代码
    exchange: str = Exchange_SSE                         # 交易所代码
    account_id: str = EMPTY_STRING                             # 资金账号代码

    # 持仓信息
    direction: str = Direction_NONE                       # 持仓方向
    volume: float = EMPTY_FLOAT       # 持仓数量
    frozen: float = EMPTY_FLOAT       # 冻结数量
    price: float = EMPTY_FLOAT        # 持仓价格
    pnl: float = EMPTY_FLOAT          # 持仓盈亏
    yd_volume: float = EMPTY_FLOAT    # 昨持数量（期货）
    multiplier: int = EMPTY_INT      # 合约乘数
    price_tick: float = EMPTY_FLOAT   # 最小价格跳动
    margin: float = EMPTY_FLOAT       # 保证金率

    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange}"
        self.positionid_full = f"{self.symbol_full}.{self.direction}"


@dataclass
class AccountData(BaseData):
    """账户信息，包含总资产、冻结资产、可用资金（现金）"""
    accountid: str = EMPTY_STRING                                  # 资金账号代码
    pre_balance: float = EMPTY_FLOAT      # 昨日账户总资产
    total_balance: float = EMPTY_FLOAT    # 今日账户总资产
    frozen: float = EMPTY_FLOAT           # 冻结资产

    def __post_init__(self):
        """"""
        self.available = self.total_balance - self.frozen       # 可用资金
        self.accountid_full = f"{self.gateway_name}.{self.accountid}"


@dataclass
class LogData(BaseData):
    """日志数据"""
    msg: str = EMPTY_STRING
    level: int = INFO

    def __post_init__(self):
        """"""
        self.time = datetime.now()


@dataclass
class ContractData(BaseData):
    """合约数据"""
    symbol: str = EMPTY_STRING
    exchange: str = Exchange_SSE
    name: str = EMPTY_STRING
    product: str = Product_STOCK
    size: int = EMPTY_INT
    pricetick: float = EMPTY_FLOAT

    min_volume: float = 1           # minimum trading order_volume of the contract
    stop_supported: bool = False    # whether server supports stop order

    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange}"
