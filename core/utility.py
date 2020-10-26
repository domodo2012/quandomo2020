# -*- coding: utf-8 -*-
"""
各类常用的工具函数
"""

import time
import colorlog  # 控制台日志输入颜色
import logging
from logging.handlers import RotatingFileHandler  # 按文件大小滚动备份
from typing import Dict, Tuple, Union
from decimal import Decimal
from math import floor, ceil, isnan
from functools import wraps
from csv import DictReader
from re import findall
from random import sample
from os import path, mkdir

import numpy as np
import talib

from .object import BarData
from .const import *

log_formatter = logging.Formatter('[%(asctime)s] %(message)s')
file_handlers: Dict[str, logging.FileHandler] = {}


class ColorLogger(object):
    def __init__(self, log_name):
        self.logName = log_name
        self.log_colors_config = {
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red',
        }
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        self.formatter = colorlog.ColoredFormatter(
            '%(log_color)s[%(asctime)s] '
            '[%(filename)s:%(lineno)d] '
            '[%(module)s:%(funcName)s] '
            '[%(levelname)s]- %(message)s',
            log_colors=self.log_colors_config)  # 日志输出格式

    def timestamp_to_time(self, timestamp):
        """格式化时间"""
        timeStruct = time.localtime(timestamp)
        return str(time.strftime('%Y-%m-%d', timeStruct))

    def __console(self, level, message):
        # 创建一个FileHandler，用于写到本地
        fh = RotatingFileHandler(filename=self.logName, mode='a', maxBytes=1024 * 1024 * 5, backupCount=5,
                                 encoding='utf-8')  # 使用RotatingFileHandler类，滚动备份日志
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(self.formatter)
        self.logger.addHandler(fh)

        # 创建一个StreamHandler,用于输出到控制台
        ch = colorlog.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(self.formatter)
        self.logger.addHandler(ch)

        if level == 'info':
            self.logger.info(message)
        elif level == 'debug':
            self.logger.debug(message)
        elif level == 'warning':
            self.logger.warning(message)
        elif level == 'error':
            self.logger.error(message)
        # 这两行代码是为了避免日志输出重复问题
        self.logger.removeHandler(ch)
        self.logger.removeHandler(fh)
        fh.close()  # 关闭打开的文件

    def debug(self, message):
        self.__console('debug', message)

    def info(self, message):
        self.__console('info', message)

    def warning(self, message):
        self.__console('warning', message)

    def error(self, message):
        self.__console('error', message)


class Logger(object):
    def __init__(self, logger_dir, set_level='DEBUG', filemode='w'):
        self.logger = logging.getLogger(logger_dir)
        # 设置输出的等级
        level_dict = {'NOSET': logging.NOTSET,
                      'DEBUG': logging.DEBUG,
                      'INFO': logging.INFO,
                      'WARNING': logging.WARNING,
                      'ERROR': logging.ERROR,
                      'CRITICAL': logging.CRITICAL}
        # 创建文件目录
        if path.exists(logger_dir):
            pass
        else:
           mkdir(logger_dir)

        cur_datetime = time.strftime("%Y-%m-%d_%H%M%S", time.localtime())
        file_name = '{0}log_{1}.csv'.format(logger_dir, cur_datetime)
        logging.basicConfig(level=level_dict[set_level],
                            format='%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            filename=file_name,
                            filemode=filemode)
        file_handler = logging.FileHandler(filename=file_name, encoding='utf-8')

        # 控制台句柄
        console = logging.StreamHandler()

        # 添加内容到日志句柄中
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console)
        self.logger.removeHandler(file_handler)

    def info(self, *message):
        self.logger.info(message)

    def debug(self, *message):
        self.logger.debug(message)

    def warning(self, *message):
        self.logger.warning(message)

    def error(self, *message):
        self.logger.error(message)


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


def get_symbol_params(symbol_code: str) -> Dict:
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


def dict_to_output_table(results: dict):
    col_width_keys = max([len(key) for key in results.keys()])
    col_width_values = max([len(str(value)) for value in results.values()])
    table_end_str = ("+-" + (col_width_keys + col_width_values + 3) * "-" + "-+")
    data_strs = []

    for key, value in results.items():
        data_strs.append("| " +
                         " | ".join(["{:{}}".format(key, col_width_keys), "{:{}}".format(value, col_width_values)]) +
                         " |\n")

    return "%s\n%s%s" % (table_end_str, "".join(data_strs), table_end_str)

