# -*- coding: utf-8 -*-
"""
常用的数据对象
"""

from dataclasses import dataclass
from datetime import datetime

from .const import Empty, Status, OrderType, Exchange

ACTIVE_STATUSES = {Status.SUBMITTING, Status.NOT_TRADED, Status.PART_TRADED}


@dataclass
class BaseData:
    """基类"""
    gateway: str = Empty.eSTRING.value


@dataclass
class BarData(BaseData):
    """K线数据类"""
    symbol: str = Empty.eSTRING.value
    exchange: str = Empty.eSTRING.value
    datetime: datetime = None

    interval: str = None
    open: float = Empty.eFLOAT.value
    high: float = Empty.eFLOAT.value
    low: float = Empty.eFLOAT.value
    close: float = Empty.eFLOAT.value
    volume: float = Empty.eFLOAT.value
    open_interest: float = Empty.eFLOAT.value
    amount: float = Empty.eFLOAT.value
    bar_index: int = Empty.eINT.value


class OrderData(BaseData):
    """委托订单类"""
    def __init__(self,
                 symbol=None,
                 exchange=None,
                 order_id=None,
                 order_type=OrderType.LIMIT,
                 direction=None,
                 offset=None,
                 price=None,
                 filled_price=None,
                 order_volume=None,
                 filled_volume=None,
                 status=None,
                 account=None,
                 gateway=None,
                 order_datetime=None,
                 comments=None,
                 symbol_type=None
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
        self.filled_price = filled_price    # 成交价格
        self.order_volume = order_volume         # 报单数量
        self.filled_volume = filled_volume         # 报单成交数量
        self.status = status           # 报单状态
        self.order_datetime = order_datetime                     # 报单时间
        self.cancel_datetime = None                    # 撤单时间
        self.filled_datetime = None
        self.comments = comments
        self.gateway = gateway
        self.account = account
        self.symbol_type = symbol_type

        # 实际交易时信息
        self.front_id = Empty.eSTRING.value        # 前置机编号，实际交易用
        self.session_id = Empty.eSTRING.value      # 连接编号，实际交易用

    def is_active(self) -> bool:
        """委托订单还未成交吗？"""
        if self.status in ACTIVE_STATUSES:
            return True
        else:
            return False


class StopOrder(OrderData):
    def __init__(self, symbol=None, exchange=None, order_id=None,
                 order_type=OrderType.STOP, direction=None, offset=None,
                 price=None, order_volume=None, account=None,
                 gateway=None, order_datetime=None, comments=None, symbol_type=None):
        # 代码信息
        super().__init__(symbol, exchange, order_id,
                         order_type, direction, offset,
                         price, order_volume, account,
                         gateway, order_datetime, comments, symbol_type)

        # 补充报单信息
        self.filled_datetime = None
        self.cancel_datetime = None  # 撤单时间

        # 实际交易时信息
        self.front_id = Empty.eSTRING.value  # 前置机编号，实际交易用
        self.session_id = Empty.eSTRING.value  # 连接编号，实际交易用

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
    symbol: str = Empty.eSTRING.value                             # 合约代码
    exchange: str = Exchange.SSE                     # 交易所代码
    order_id: str = Empty.eSTRING.value                            # 订单编号
    trade_id: str = Empty.eSTRING.value                            # 成交单编号

    # 成交相关
    direction: str = None                 # 交易方向
    offset: str = None               # 成交开平
    order_price: float = Empty.eFLOAT.value  # 委托价格
    price: float = Empty.eFLOAT.value        # 成交价格
    volume: float = Empty.eFLOAT.value       # 成交数量
    datetime: datetime = None                   # 成交时间
    multiplier: int = Empty.eINT.value      # 合约乘数
    price_tick: float = Empty.eFLOAT.value   # 最小价格跳动
    margin: float = Empty.eFLOAT.value       # 保证金率
    slippage: float = Empty.eFLOAT.value     # 滑点值
    commission: float = Empty.eFLOAT.value   # 手续费率
    comments: str = Empty.eSTRING.value
    account: str = Empty.eSTRING.value
    frozen: int = Empty.eINT.value
    symbol_type: str = Empty.eSTRING.value


@dataclass
class PositionData(BaseData):
    """持仓数据，跟踪每一个持仓头寸"""
    # 编号代码信息
    symbol: str = Empty.eSTRING.value                                 # 合约代码
    exchange: str = Exchange.SSE                         # 交易所代码
    account: str = Empty.eSTRING.value                             # 资金账号代码
    trade_id: str = Empty.eSTRING.value
    order_id: str = Empty.eSTRING.value

    # 持仓信息
    init_datetime = None                    # 建仓时间
    datetime: str = None
    direction: str = None                       # 持仓方向
    offset: str = None
    init_volume: float = Empty.eFLOAT.value       # 初始持仓数量
    volume: float = Empty.eFLOAT.value       # 除权除息/换月移仓之后的持仓数量
    frozen: float = Empty.eFLOAT.value       # 冻结数量
    init_price: float = Empty.eFLOAT.value        # 初始持仓价格
    price: float = Empty.eFLOAT.value        # 除权除息/换月移仓之后的持仓价格
    position_pnl: float = Empty.eFLOAT.value          # 持仓盈亏
    position_value: float = Empty.eFLOAT.value          # 持仓市值
    position_value_pre: float = Empty.eFLOAT.value          # 上个bar的持仓市值
    yd_volume: float = Empty.eFLOAT.value    # 昨持数量（期货）
    multiplier: int = Empty.eINT.value      # 合约乘数
    price_tick: float = Empty.eFLOAT.value   # 最小价格跳动
    margin: float = Empty.eFLOAT.value       # 保证金率
    symbol_type: str = Empty.eSTRING.value


@dataclass
class AccountData(BaseData):
    """账户信息，包含总资产、冻结资产、可用资金（现金）"""
    account_id: str = Empty.eSTRING.value                                  # 资金账号代码
    datetime = None
    pre_balance: float = Empty.eFLOAT.value      # 昨日账户总资产
    total_balance: float = Empty.eFLOAT.value    # 今日账户总资产
    holding: float = Empty.eFLOAT.value          # 今日账户总持仓
    frozen: float = Empty.eFLOAT.value           # 今日账户总冻结资产（持仓中冻结的部分）
    gateway: str = Empty.eSTRING.value
    available: float = Empty.eFLOAT.value        # 今日可用资金
