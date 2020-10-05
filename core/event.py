# -*- coding: utf-8 -*-
"""
事件定义
"""
from typing import Any


class Event(object):
    def __init__(self, type_: str, dt=None, data: Any = None):
        """"""
        self.type_ = type_
        self.dt = dt    # datetime
        self.data = data

