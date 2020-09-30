# -*- coding: utf-8 -*-
"""
事件定义
"""
from typing import Any


class Event(object):
    """事件定义，属性包括事件类型和具体的事件数据"""

    def __init__(self, event_type: str, data: Any = None):
        """"""
        self.event_type: str = event_type
        self.data: Any = data

