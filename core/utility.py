# -*- coding: utf-8 -*-
"""
各类常用的工具函数
"""

import time
import logging
from typing import Dict, Tuple, Union
from decimal import Decimal
from math import floor, ceil
from functools import wraps
from csv import DictReader
from re import findall
from random import sample

import numpy as np
import talib

from .object import BarData
from .const import *

log_formatter = logging.Formatter('[%(asctime)s] %(message)s')
file_handlers: Dict[str, logging.FileHandler] = {}


def get_file_logger(filename: str) -> logging.Logger:
    """返回一个将记录写入文件中的记录器"""
    logger = logging.getLogger(filename)
    handler = file_handlers.get(filename, None)
    if handler is None:
        handler = logging.FileHandler(filename)
        file_handlers[filename] = handler
    handler.setFormatter(log_formatter)
    logger.addHandler(handler)  # each handler will be added only once.
    return logger


class Timer(object):
    """计算代码运行所耗时间"""
    def __init__(self, verbose=False):
        self.verbose = verbose

    def __enter__(self):
        self.start = time.process_time()
        return self

    def __exit__(self, *args):
        self.end = time.process_time()
        self.secs = self.end - self.start
        self.millisecond = self.secs * 1000  # millisecond
        if self.verbose:
            print('elapsed time: %f ms' % self.millisecond)


def singleton(cls):
    """单例模式的装饰器，保证被装饰的类只能生成一个实例，适用于网络连接的实例化等"""
    instances = {}

    @wraps(cls)
    def get_instance(*args, **kw):
        if cls not in instances:
            instances[cls] = cls(*args, **kw)
        return instances[cls]

    return get_instance


def extract_symbol_full(symbol_full: str) -> Tuple[str, str]:
    """
    返回值: (symbol, exchange)
    """
    symbol, exchange_str = symbol_full.split(".")
    return symbol, exchange_str


def generate_symbol_full(symbol: str, exchange: str) -> str:
    """
    返回值 symbol.exchange(symbol_full)
    """
    return f"{symbol}.{exchange.value}"


def round_to(value: float, target: float) -> float:
    """对浮点数据向下取整"""
    value = Decimal(str(value))
    target = Decimal(str(target))
    rounded = float(int(round(value / target)) * target)
    return rounded


def floor_to(value: float, target: float) -> float:
    """带小数位的向下取整"""
    value = Decimal(str(value))
    target = Decimal(str(target))
    result = float(int(floor(value / target)) * target)
    return result


def ceil_to(value: float, target: float) -> float:
    """带小数位的向上取整"""
    value = Decimal(str(value))
    target = Decimal(str(target))
    result = float(int(ceil(value / target)) * target)
    return result


def get_digits(value: float) -> int:
    """
    Get number of digits after decimal point.
    """
    value_str = str(value)

    if "e-" in value_str:
        _, buf = value_str.split("e-")
        return int(buf)
    elif "." in value_str:
        _, buf = value_str.split(".")
        return len(buf)
    else:
        return 0


class TimeSeriesContainer(object):
    """时间序列数据容器及技术指标计算"""

    def __init__(self, size: int = 10):
        """Constructor"""
        self.count: int = 0
        self.size: int = size
        self.inited: bool = False

        self.open_array: np.ndarray = np.zeros(size)
        self.high_array: np.ndarray = np.zeros(size)
        self.low_array: np.ndarray = np.zeros(size)
        self.close_array: np.ndarray = np.zeros(size)
        self.volume_array: np.ndarray = np.zeros(size)
        self.open_interest_array: np.ndarray = np.zeros(size)

    def update_bar(self, bar: BarData) -> None:
        """
        Update new bar data into array manager.
        """
        self.count += 1
        if not self.inited and self.count >= self.size:
            self.inited = True

        self.open_array[:-1] = self.open_array[1:]
        self.high_array[:-1] = self.high_array[1:]
        self.low_array[:-1] = self.low_array[1:]
        self.close_array[:-1] = self.close_array[1:]
        self.volume_array[:-1] = self.volume_array[1:]
        self.open_interest_array[:-1] = self.open_interest_array[1:]

        self.open_array[-1] = bar.open
        self.high_array[-1] = bar.high
        self.low_array[-1] = bar.low
        self.close_array[-1] = bar.close
        self.volume_array[-1] = bar.volume
        self.open_interest_array[-1] = bar.open_interest

    @property
    def open(self) -> np.ndarray:
        """
        Get open price time series.
        """
        return self.open_array

    @property
    def high(self) -> np.ndarray:
        """
        Get high price time series.
        """
        return self.high_array

    @property
    def low(self) -> np.ndarray:
        """
        Get low price time series.
        """
        return self.low_array

    @property
    def close(self) -> np.ndarray:
        """
        Get close price time series.
        """
        return self.close_array

    @property
    def volume(self) -> np.ndarray:
        """
        Get trading order_volume time series.
        """
        return self.volume_array

    @property
    def open_interest(self) -> np.ndarray:
        """
        Get trading order_volume time series.
        """
        return self.open_interest_array

    def sma(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Simple moving average.
        """
        result = talib.SMA(self.close, n)
        if array:
            return result
        return result[-1]

    def ema(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Exponential moving average.
        """
        result = talib.EMA(self.close, n)
        if array:
            return result
        return result[-1]

    def kama(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        KAMA.
        """
        result = talib.KAMA(self.close, n)
        if array:
            return result
        return result[-1]

    def wma(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        WMA.
        """
        result = talib.WMA(self.close, n)
        if array:
            return result
        return result[-1]

    def apo(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        APO.
        """
        result = talib.APO(self.close, n)
        if array:
            return result
        return result[-1]

    def cmo(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        CMO.
        """
        result = talib.CMO(self.close, n)
        if array:
            return result
        return result[-1]

    def mom(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        MOM.
        """
        result = talib.MOM(self.close, n)
        if array:
            return result
        return result[-1]

    def ppo(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        PPO.
        """
        result = talib.PPO(self.close, n)
        if array:
            return result
        return result[-1]

    def roc(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        ROC.
        """
        result = talib.ROC(self.close, n)
        if array:
            return result
        return result[-1]

    def rocr(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        ROCR.
        """
        result = talib.ROCR(self.close, n)
        if array:
            return result
        return result[-1]

    def rocp(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        ROCP.
        """
        result = talib.ROCP(self.close, n)
        if array:
            return result
        return result[-1]

    def rocr_100(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        ROCR100.
        """
        result = talib.ROCR100(self.close, n)
        if array:
            return result
        return result[-1]

    def trix(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        TRIX.
        """
        result = talib.TRIX(self.close, n)
        if array:
            return result
        return result[-1]

    def std(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Standard deviation.
        """
        result = talib.STDDEV(self.close, n)
        if array:
            return result
        return result[-1]

    def obv(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        OBV.
        """
        result = talib.OBV(self.close, self.volume)
        if array:
            return result
        return result[-1]

    def cci(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Commodity Channel Index (CCI).
        """
        result = talib.CCI(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def atr(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Average True Range (ATR).
        """
        result = talib.ATR(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def natr(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        NATR.
        """
        result = talib.NATR(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def rsi(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Relative Strenght Index (RSI).
        """
        result = talib.RSI(self.close, n)
        if array:
            return result
        return result[-1]

    def macd(
        self,
        fast_period: int,
        slow_period: int,
        signal_period: int,
        array: bool = False
    ) -> Union[
        Tuple[np.ndarray, np.ndarray, np.ndarray],
        Tuple[float, float, float]
    ]:
        """
        MACD.
        """
        macd, signal, hist = talib.MACD(
            self.close, fast_period, slow_period, signal_period
        )
        if array:
            return macd, signal, hist
        return macd[-1], signal[-1], hist[-1]

    def adx(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        ADX.
        """
        result = talib.ADX(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def adxr(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        ADXR.
        """
        result = talib.ADXR(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def dx(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        DX.
        """
        result = talib.DX(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def minus_di(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        MINUS_DI.
        """
        result = talib.MINUS_DI(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def plus_di(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        PLUS_DI.
        """
        result = talib.PLUS_DI(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def willr(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        WILLR.
        """
        result = talib.WILLR(self.high, self.low, self.close, n)
        if array:
            return result
        return result[-1]

    def ultosc(self, array: bool = False) -> Union[float, np.ndarray]:
        """
        Ultimate Oscillator.
        """
        result = talib.ULTOSC(self.high, self.low, self.close)
        if array:
            return result
        return result[-1]

    def trange(self, array: bool = False) -> Union[float, np.ndarray]:
        """
        TRANGE.
        """
        result = talib.TRANGE(self.high, self.low, self.close)
        if array:
            return result
        return result[-1]

    def boll(
        self,
        n: int,
        dev: float,
        array: bool = False
    ) -> Union[
        Tuple[np.ndarray, np.ndarray],
        Tuple[float, float]
    ]:
        """
        Bollinger Channel.
        """
        mid = self.sma(n, array)
        std = self.std(n, array)

        up = mid + std * dev
        down = mid - std * dev

        return up, down

    def keltner(
        self,
        n: int,
        dev: float,
        array: bool = False
    ) -> Union[
        Tuple[np.ndarray, np.ndarray],
        Tuple[float, float]
    ]:
        """
        Keltner Channel.
        """
        mid = self.sma(n, array)
        atr = self.atr(n, array)

        up = mid + atr * dev
        down = mid - atr * dev

        return up, down

    def donchian(
        self, n: int, array: bool = False
    ) -> Union[
        Tuple[np.ndarray, np.ndarray],
        Tuple[float, float]
    ]:
        """
        Donchian Channel.
        """
        up = talib.MAX(self.high, n)
        down = talib.MIN(self.low, n)

        if array:
            return up, down
        return up[-1], down[-1]

    def aroon(
        self,
        n: int,
        array: bool = False
    ) -> Union[
        Tuple[np.ndarray, np.ndarray],
        Tuple[float, float]
    ]:
        """
        Aroon indicator.
        """
        aroon_up, aroon_down = talib.AROON(self.high, self.low, n)

        if array:
            return aroon_up, aroon_down
        return aroon_up[-1], aroon_down[-1]

    def aroonosc(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Aroon Oscillator.
        """
        result = talib.AROONOSC(self.high, self.low, n)

        if array:
            return result
        return result[-1]

    def minus_dm(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        MINUS_DM.
        """
        result = talib.MINUS_DM(self.high, self.low, n)

        if array:
            return result
        return result[-1]

    def plus_dm(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        PLUS_DM.
        """
        result = talib.PLUS_DM(self.high, self.low, n)

        if array:
            return result
        return result[-1]

    def mfi(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        Money Flow Index.
        """
        result = talib.MFI(self.high, self.low, self.close, self.volume, n)
        if array:
            return result
        return result[-1]

    def ad(self, array: bool = False) -> Union[float, np.ndarray]:
        """
        AD.
        """
        result = talib.AD(self.high, self.low, self.close, self.volume)
        if array:
            return result
        return result[-1]

    def adosc(self, n: int, array: bool = False) -> Union[float, np.ndarray]:
        """
        ADOSC.
        """
        result = talib.ADOSC(self.high, self.low, self.close, self.volume, n)
        if array:
            return result
        return result[-1]

    def bop(self, array: bool = False) -> Union[float, np.ndarray]:
        """
        BOP.
        """
        result = talib.BOP(self.open, self.high, self.low, self.close)

        if array:
            return result
        return result[-1]


def timestamp_to_datetime(timestamp, format):
    return time.strftime(format, time.localtime(timestamp))


def datetime_to_timestamp(date="20100101", format='%Y%m%d'):
    return int(time.mktime(time.strptime(date, format)))


def date_str_to_int(date="2010-01-01"):
    return int(date.replace("-", ""))


def read_symbol_settings(filename: str):
    """从配置文件中读取合约信息"""
    settings = {'symbol_list': [],
                'size_dict': {},
                'price_tick_dict': {},
                'variable_commission_dict': {},
                'fixed_commission_dict': {},
                'slippage_dict': {}
                }

    with open(filename) as f:
        r = DictReader(f)
        for d in r:
            settings['symbol_list'].append(d['symbol'])

            settings['size_dict'][d['symbol']] = int(d['size'])
            settings['price_tick_dict'][d['symbol']] = float(d['price_tick'])
            settings['variable_commission_dict'][d['symbol']] = float(d['variable_commission'])
            settings['fixed_commission_dict'][d['symbol']] = float(d['fixed_commission'])
            settings['slippage_dict'][d['symbol']] = float(d['slippage'])

    return settings


def get_contract_params(symbol_code: str) -> Dict:
    """输入symbol_full 格式的合约代码，输出对应的合约乘数、最小变动单位等参数 """

    symbol, exchg = symbol_code.split('.')
    if exchg == 'SH':
        symbol_type = 'STOCK_SH'
    elif exchg == 'SZ':
        symbol_type = 'STOCK_SZ'
    else:
        symbol_type = ''.join(findall(r'[A-Za-z]', symbol)).upper()

    params_dict = {
        "STOCK_SH": {'multiplier': 1,
                     'price_tick': 0.01,
                     'margin': 1.,
                     'tax': 0.001,
                     'commission_open_pct': 0.0003,
                     'commission_close_pct': 0.0005,
                     'commission_close_today_pct': None,
                     'commission_fixed': None,
                     'commission_min': 5},
        "STOCK_SZ": {'multiplier': 1,
                     'price_tick': 0.01,
                     'margin': 1.,
                     'tax': 0.001,
                     'commission_open_pct': 0.0003,
                     'commission_close_pct': 0.0003,
                     'commission_close_today_pct': None,
                     'commission_fixed': None,
                     'commission_min': 5},
        "IF":       {'multiplier': 300,
                     'price_tick': 0.2,
                     'margin': 0.2,
                     'tax': 0.0,
                     'commission_open_pct': 0.00005,
                     'commission_close_pct': 0.00005,
                     'commission_close_today_pct': 0.0005,
                     'commission_fixed': None,
                     'commission_min': 5},
        "IC":       {'multiplier': 200,
                     'price_tick': 0.2,
                     'margin': 0.2,
                     'tax': 0.0,
                     'commission_open_pct': 0.00005,
                     'commission_close_pct': 0.00005,
                     'commission_close_today_pct': 0.0005,
                     'commission_fixed': None,
                     'commission_min': 5},
        "RB":       {'multiplier': 10,
                     'price_tick': 1,
                     'margin': 0.2,
                     'tax': 0.0,
                     'commission_open_pct': 0.0002,
                     'commission_close_pct': 0.0002,
                     'commission_close_today_pct': 0.0002,
                     'commission_fixed': None,
                     'commission_min': 5},
        "TA":       {'multiplier': 10,
                     'price_tick': 1,
                     'margin': 0.2,
                     'tax': 0.0,
                     'commission_open_pct': None,
                     'commission_close_pct': None,
                     'commission_close_today_pct': None,
                     'commission_fixed': None,
                     'commission_min': 5},

    }
    if symbol_type not in params_dict:
        return {}
    else:
        return params_dict[symbol_type]


def get_exchange(symbol):
    sec_code, exchge_code = symbol.split('.')
    if exchge_code.upper() == 'SH':
        exchange = Exchange_SSE
    elif exchge_code.upper() == 'SZ':
        exchange = Exchange_SZSE
    else:
        exchange = exchge_code
    return exchange


def generate_random_id(topic, lens=8):
    _list = [str(i) for i in range(10)]
    num = sample(_list, lens)
    return "{}_{}".format(topic, "".join(num))

