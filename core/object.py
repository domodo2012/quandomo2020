# -*- coding: utf-8 -*-
"""
常用的数据对象
"""

from dataclasses import dataclass
from datetime import datetime
from logging import INFO

from .const import *

ACTIVE_STATUSES = {Status_SUBMITTING, Status_NOT_TRADED, Status_PART_TRADED}


@dataclass
class BaseData:
    """基类"""
    gateway: str = EMPTY_STRING


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
    bar_index: int = EMPTY_INT

    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange}"


class OrderData(BaseData):
    """委托订单类"""
    def __init__(self,
                 symbol=None,
                 exchange=None,
                 order_id=None,
                 order_type=OrderType_LIMIT,
                 direction=None,
                 offset=None,
                 price=None,
                 order_volume=None,
                 filled_volume=None,
                 status=None,
                 account=None,
                 gateway=None,
                 order_datetime=None,
                 comments=None
                 ):
        # 代码信息
        self.symbol = symbol
        self.exchange = exchange
        self.order_id = order_id

        # 报单信息
        self.order_type = order_type            # 报单类型
        self.direction = direction                         # 报单方向
        self.offset = offset                  # 报单开平仓
        self.price = price          # 报单价格
        self.order_volume = order_volume         # 报单数量
        self.filled_volume = filled_volume         # 报单成交数量
        self.status = status           # 报单状态
        self.order_datetime = order_datetime                     # 报单时间
        self.cancel_datetime = None                    # 撤单时间
        self.filled_datetime = None
        self.comments = comments
        self.gateway = gateway
        self.account = account

        # 实际交易时信息
        self.front_id = EMPTY_STRING        # 前置机编号，实际交易用
        self.session_id = EMPTY_STRING      # 连接编号，实际交易用

    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange}"
        self.order_id_full = f"{self.gateway}.{self.order_id}"

    def is_active(self) -> bool:
        """委托订单还未成交吗？"""
        if self.status in ACTIVE_STATUSES:
            return True
        else:
            return False


class StopOrder(OrderData):
    def __init__(self, symbol=None, exchange=None, order_id=None,
                 order_type=OrderType_STOP, direction=None, offset=None,
                 price=None, order_volume=None, account=None,
                 gateway=None, order_datetime=None, comments=None):
        # 代码信息
        super().__init__(symbol, exchange, order_id,
                         order_type, direction, offset,
                         price, order_volume, account,
                         gateway, order_datetime, comments)

        # 补充报单信息
        self.filled_datetime = None
        self.cancel_datetime = None  # 撤单时间

        # 实际交易时信息
        self.front_id = EMPTY_STRING  # 前置机编号，实际交易用
        self.session_id = EMPTY_STRING  # 连接编号，实际交易用

    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange}"
        self.order_id_full = f"{self.gateway}.{self.order_id}"

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
    order_id: str = EMPTY_STRING                            # 订单编号
    trade_id: str = EMPTY_STRING                            # 成交单编号

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
    comments: str = EMPTY_STRING
    account: str = EMPTY_STRING
    frozen: int = EMPTY_INT


    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange}"
        self.order_id_full = f"{self.gateway}.{self.order_id}"
        self.trade_id_full = f"{self.gateway}.{self.trade_id}"


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
    average_price: float = EMPTY_FLOAT        # 持仓价格
    position_pnl: float = EMPTY_FLOAT          # 持仓盈亏
    yd_volume: float = EMPTY_FLOAT    # 昨持数量（期货）
    multiplier: int = EMPTY_INT      # 合约乘数
    price_tick: float = EMPTY_FLOAT   # 最小价格跳动
    margin: float = EMPTY_FLOAT       # 保证金率

    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange}"
        self.position_id_full = f"{self.symbol_full}.{self.direction}"


@dataclass
class AccountData(BaseData):
    """账户信息，包含总资产、冻结资产、可用资金（现金）"""
    account_id: str = EMPTY_STRING                                  # 资金账号代码
    pre_balance: float = EMPTY_FLOAT      # 昨日账户总资产
    total_balance: float = EMPTY_FLOAT    # 今日账户总资产
    frozen: float = EMPTY_FLOAT           # 冻结资产

    def __post_init__(self):
        """"""
        self.available = self.total_balance - self.frozen       # 可用资金
        self.account_id_full = f"{self.gateway}.{self.account_id}"


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
