# -*- coding: utf-8 -*-
"""
常用的数据对象
"""

from dataclasses import dataclass
from datetime import datetime
from logging import INFO

from .const import Direction, Exchange, Interval, Offset, Status, Product, OrderType, EmptyType

ACTIVE_STATUSES = {Status.SUBMITTING, Status.NOT_TRADED, Status.PART_TRADED}


@dataclass
class BaseData:
    """基类"""
    gateway_name: str


@dataclass
class BarData(BaseData):
    """K线数据类"""
    symbol: str
    exchange: Exchange
    datetime: datetime

    interval: Interval = None
    volume: float = EmptyType.EMPTY_FLOAT.value
    open_interest: float = EmptyType.EMPTY_FLOAT.value
    open_price: float = EmptyType.EMPTY_FLOAT.value
    high_price: float = EmptyType.EMPTY_FLOAT.value
    low_price: float = EmptyType.EMPTY_FLOAT.value
    close_price: float = EmptyType.EMPTY_FLOAT.value

    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange.value}"


@dataclass
class OrderData(BaseData):
    """委托订单类"""
    # 代码信息
    symbol: str
    exchange: Exchange
    orderid: str

    # 报单信息
    type: OrderType = OrderType.LIMIT.value             # 报单类型
    direction: Direction = None                         # 报单方向（期货）
    offset: Offset = Offset.NONE.value                  # 报单开平仓
    price: float = EmptyType.EMPTY_FLOAT.value          # 报单价格
    volume: float = EmptyType.EMPTY_FLOAT.value         # 报单数量
    traded: float = EmptyType.EMPTY_FLOAT.value         # 报单成交数量
    status: Status = Status.SUBMITTING.value            # 报单状态
    order_datetime: datetime = None                     # 报单时间
    cancel_datetime: datetime = None                    # 撤单时间

    # 实际交易时信息
    front_id: str = EmptyType.EMPTY_STRING.value        # 前置机编号，实际交易用
    session_id: str = EmptyType.EMPTY_STRING.value      # 连接编号，实际交易用

    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange.value}"
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
    symbol: str
    exchange: Exchange
    orderid: str
    tradeid: str
    direction: Direction = None

    # 成交相关
    offset: Offset = Offset.NONE
    price: float = EmptyType.EMPTY_FLOAT
    volume: float = EmptyType.EMPTY_FLOAT
    datetime: datetime = None

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"
        self.vt_orderid = f"{self.gateway_name}.{self.orderid}"
        self.vt_tradeid = f"{self.gateway_name}.{self.tradeid}"


@dataclass
class PositionData(BaseData):
    """
    Positon data is used for tracking each individual position holding.
    """

    symbol: str
    exchange: Exchange
    direction: Direction

    volume: float = EmptyType.EMPTY_FLOAT
    frozen: float = EmptyType.EMPTY_FLOAT
    price: float = EmptyType.EMPTY_FLOAT
    pnl: float = EmptyType.EMPTY_FLOAT
    yd_volume: float = EmptyType.EMPTY_FLOAT

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"
        self.vt_positionid = f"{self.vt_symbol}.{self.direction.value}"


@dataclass
class AccountData(BaseData):
    """
    Account data contains information about balance, frozen and
    available.
    """

    accountid: str

    balance: float = 0
    frozen: float = 0

    def __post_init__(self):
        """"""
        self.available = self.balance - self.frozen
        self.vt_accountid = f"{self.gateway_name}.{self.accountid}"


@dataclass
class LogData(BaseData):
    """
    Log data is used for recording log messages on GUI or in log files.
    """

    msg: str
    level: int = INFO

    def __post_init__(self):
        """"""
        self.time = datetime.now()


@dataclass
class ContractData(BaseData):
    """
    Contract data contains basic information about each contract traded.
    """

    symbol: str
    exchange: Exchange
    name: str
    product: Product
    size: int
    pricetick: float

    min_volume: float = 1           # minimum trading volume of the contract
    stop_supported: bool = False    # whether server supports stop order
    net_position: bool = False      # whether gateway uses net position volume
    history_data: bool = False      # whether gateway provides bar history data

    option_strike: float = 0
    option_underlying: str = ""     # vt_symbol of underlying contract
    option_expiry: datetime = None
    option_portfolio: str = ""
    option_index: str = ""          # for identifying options with same strike price

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"


@dataclass
class SubscribeRequest:
    """
    Request sending to specific gateway for subscribing tick data update.
    """

    symbol: str
    exchange: Exchange

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"


@dataclass
class OrderRequest:
    """
    Request sending to specific gateway for creating a new order.
    """

    symbol: str
    exchange: Exchange
    direction: Direction
    type: OrderType
    volume: float
    price: float = 0
    offset: Offset = Offset.NONE
    reference: str = ""

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

    def create_order_data(self, orderid: str, gateway_name: str) -> OrderData:
        """
        Create order data from request.
        """
        order = OrderData(
            symbol=self.symbol,
            exchange=self.exchange,
            orderid=orderid,
            type=self.type,
            direction=self.direction,
            offset=self.offset,
            price=self.price,
            volume=self.volume,
            gateway_name=gateway_name,
        )
        return order


@dataclass
class CancelRequest:
    """
    Request sending to specific gateway for canceling an existing order.
    """

    orderid: str
    symbol: str
    exchange: Exchange

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"


@dataclass
class HistoryRequest:
    """
    Request sending to specific gateway for querying history data.
    """

    symbol: str
    exchange: Exchange
    start: datetime
    end: datetime = None
    interval: Interval = None

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"


