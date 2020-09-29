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
    gateway_name: str = EmptyType.EMPTY_STRING.value


@dataclass
class BarData(BaseData):
    """K线数据类"""
    symbol: str = EmptyType.EMPTY_STRING.value
    exchange: Exchange = EmptyType.EMPTY_STRING.value
    datetime: datetime = None

    interval: Interval = None
    open: float = EmptyType.EMPTY_FLOAT.value
    high: float = EmptyType.EMPTY_FLOAT.value
    low: float = EmptyType.EMPTY_FLOAT.value
    close: float = EmptyType.EMPTY_FLOAT.value
    volume: float = EmptyType.EMPTY_FLOAT.value
    open_interest: float = EmptyType.EMPTY_FLOAT.value
    amount: float = EmptyType.EMPTY_FLOAT.value

    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange}"


@dataclass
class OrderData(BaseData):
    """委托订单类"""
    # 代码信息
    symbol: str = EmptyType.EMPTY_STRING.value
    exchange: Exchange = Exchange.SSE.value
    orderid: str = EmptyType.EMPTY_STRING.value

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
    symbol: str = EmptyType.EMPTY_STRING.value                             # 合约代码
    exchange: Exchange = Exchange.SSE.value                      # 交易所代码
    orderid: str = EmptyType.EMPTY_STRING.value                            # 订单编号
    tradeid: str = EmptyType.EMPTY_STRING.value                            # 成交单编号

    # 成交相关
    direction: Direction = None                 # 交易方向
    offset: Offset = Offset.NONE.value                # 成交开平
    price: float = EmptyType.EMPTY_FLOAT.value        # 成交价格
    volume: float = EmptyType.EMPTY_FLOAT.value       # 成交数量
    datetime: datetime = None                   # 成交时间
    multiplier: int = EmptyType.EMPTY_INT.value       # 合约乘数
    price_tick: float = EmptyType.EMPTY_FLOAT.value   # 最小价格跳动
    margin: float = EmptyType.EMPTY_FLOAT.value       # 保证金率
    tax: float = EmptyType.EMPTY_FLOAT.value          # 印花税率
    slippage: float = EmptyType.EMPTY_FLOAT.value     # 滑点值
    commission: float = EmptyType.EMPTY_FLOAT.value   # 手续费率

    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange}"
        self.orderid_full = f"{self.gateway_name}.{self.orderid}"
        self.tradeid_full = f"{self.gateway_name}.{self.tradeid}"


@dataclass
class PositionData(BaseData):
    """持仓数据，跟踪每一个持仓头寸"""
    # 编号代码信息
    symbol: str = EmptyType.EMPTY_STRING.value                                 # 合约代码
    exchange: Exchange = Exchange.SSE.value                          # 交易所代码
    account_id: str = EmptyType.EMPTY_STRING.value                             # 资金账号代码

    # 持仓信息
    direction: Direction = Direction.NONE.value                        # 持仓方向
    volume: float = EmptyType.EMPTY_FLOAT.value       # 持仓数量
    frozen: float = EmptyType.EMPTY_FLOAT.value       # 冻结数量
    price: float = EmptyType.EMPTY_FLOAT.value        # 持仓价格
    pnl: float = EmptyType.EMPTY_FLOAT.value          # 持仓盈亏
    yd_volume: float = EmptyType.EMPTY_FLOAT.value    # 昨持数量（期货）
    multiplier: int = EmptyType.EMPTY_INT.value       # 合约乘数
    price_tick: float = EmptyType.EMPTY_FLOAT.value   # 最小价格跳动
    margin: float = EmptyType.EMPTY_FLOAT.value       # 保证金率

    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange}"
        self.positionid_full = f"{self.symbol_full}.{self.direction}"


@dataclass
class AccountData(BaseData):
    """账户信息，包含总资产、冻结资产、可用资金（现金）"""
    accountid: str = EmptyType.EMPTY_STRING.value                                  # 资金账号代码
    pre_balance: float = EmptyType.EMPTY_FLOAT.value      # 昨日账户总资产
    total_balance: float = EmptyType.EMPTY_FLOAT.value    # 今日账户总资产
    frozen: float = EmptyType.EMPTY_FLOAT.value           # 冻结资产

    def __post_init__(self):
        """"""
        self.available = self.total_balance - self.frozen       # 可用资金
        self.accountid_full = f"{self.gateway_name}.{self.accountid}"


@dataclass
class LogData(BaseData):
    """日志数据"""
    msg: str = EmptyType.EMPTY_STRING.value
    level: int = INFO

    def __post_init__(self):
        """"""
        self.time = datetime.now()


@dataclass
class ContractData(BaseData):
    """合约数据"""
    symbol: str = EmptyType.EMPTY_STRING.value
    exchange: Exchange = Exchange.SSE.value
    name: str = EmptyType.EMPTY_STRING.value
    product: Product = Product.STOCK.value
    size: int = EmptyType.EMPTY_INT.value
    pricetick: float = EmptyType.EMPTY_FLOAT.value

    min_volume: float = 1           # minimum trading volume of the contract
    stop_supported: bool = False    # whether server supports stop order

    def __post_init__(self):
        """"""
        self.symbol_full = f"{self.symbol}.{self.exchange}"
