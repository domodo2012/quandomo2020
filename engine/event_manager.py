# -*- coding: utf-8 -*-
"""
事件驱动引擎核心
"""
from const import *
from queue import Queue
from threading import Thread, RLock
from time import sleep
from collections import defaultdict

from core.event import MakeEvent


class EventManager:
    def __init__(self):
        """初始化事件管理器"""
        # 事件对象列表
        self._eventQueue = Queue()

        # 事件管理器开关
        self._active = False

        # 事件处理线程
        # self._thread = Thread(target=self._run)

        # 这里的_handlers是一个字典，用来保存对应的事件的响应函数
        # 其中每个键对应的值是一个列表，列表中保存了对该事件监听的响应函数，一对多
        self._handlers = defaultdict(list)
        self._handlers_general = []

        # 线程锁
        # self._lock = RLock()

        # 计时器，用于触发计时器事件
        # self._timer = Thread(target=self._run_timer)
        # self._timer_active = False  # 计时器工作状态
        # self._timer_sleep = 1  # 计时器触发间隔（默认1秒）

    # def _run(self):
    #     """引擎运行"""
    #     while self._active:
    #         try:
    #             # 获取事件的阻塞时间设为1秒
    #             event = self.get(True, 1)
    #             self.event_process(event)
    #         except Empty:
    #             # pass
    #             break

    def event_process(self, event):
        """处理事件"""
        # 检查是否存在对该事件进行监听的处理函数
        if event.type_ in self._handlers:
            # 若存在，则按顺序将事件传递给处理函数执行
            for handler in self._handlers[event.type_]:
                handler(event)

        if event.type_ != 'event_timer':
            for handler in self._handlers_general:
                handler(event)

    # def _run_timer(self):
    #     """运行在计时器线程中的循环函数"""
    #     while self._timer_active:
    #         # 创建计时器事件
    #         event = MakeEvent(Event.TIMER)
    #
    #         # 向队列中存入计时器事件
    #         self.put(event)
    #
    #         # 等待
    #         sleep(self._timer_sleep)

    # def start(self, timer=True):
    #     """启动"""
    #     # 将事件管理器设为启动
    #     self._active = True
    #     # 启动事件处理线程
    #     self._thread.start()
    #
    #     # 启动计时器，计时器事件间隔默认设定为1秒
    #     if timer:
    #         self._timer_active = True
    #         self._timer.start()
    #         pass

    # def stop(self):
    #     """停止"""
    #     # 将事件管理器设为停止
    #     self._active = False
    #     # 等待事件处理线程退出
    #     self._thread.join()

    def register(self, type_, handler):
        """绑定事件和监听器处理函数"""
        # 尝试获取该事件类型对应的处理函数列表，若无则创建
        try:
            handler_list = self._handlers[type_]
        except KeyError:
            handler_list = []

        self._handlers[type_] = handler_list
        # 若要注册的处理器不在该事件的处理器列表中，则注册该事件
        if handler not in handler_list:
            handler_list.append(handler)

    def unregister(self, type_, handler):
        """移除监听器的处理函数"""
        # 读者自己试着实现

    def register_general(self, handler):
        """注册通用事件处理函数监听"""
        if handler not in self._handlers_general:
            self._handlers_general.append(handler)

    def unregister_general(self, handler):
        """注销通用事件处理函数监听"""
        if handler in self._handlers_general:
            self._handlers_general.remove(handler)

    def put(self, event):
        """发送事件，向事件队列中存入事件"""
        self._eventQueue.put(event)

    def get(self, is_block: bool = False, time_out: float = 1):
        """从队列中取事件"""
        return self._eventQueue.get(block=is_block, timeout=time_out)
