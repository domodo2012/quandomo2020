# encoding: UTF-8
# 系统模块
import sys
from datetime import datetime
from threading import *
from queue import Queue, Empty
from threading import *


########################################################################
class EventManager:
    # ----------------------------------------------------------------------
    def __init__(self):
        """初始化事件管理器"""
        # 事件对象列表
        self.__eventQueue = Queue()
        # 事件管理器开关
        self.__active = False
        # 事件处理线程
        self.__thread = Thread(target=self.__Run)

        # 这里的__handlers是一个字典，用来保存对应的事件的响应函数
        # 其中每个键对应的值是一个列表，列表中保存了对该事件监听的响应函数，一对多
        self.__handlers = {}

    # ----------------------------------------------------------------------
    def __Run(self):
        """引擎运行"""
        while self.__active == True:
            try:
                # 获取事件的阻塞时间设为1秒
                event = self.__eventQueue.get(block=True, timeout=1)
                self.__EventProcess(event)
            except Empty:
                pass

    # ----------------------------------------------------------------------
    def __EventProcess(self, event):
        """处理事件"""
        # 检查是否存在对该事件进行监听的处理函数
        if event.type_ in self.__handlers:
            # 若存在，则按顺序将事件传递给处理函数执行
            for handler in self.__handlers[event.type_]:
                handler(event)

    # ----------------------------------------------------------------------
    def Start(self):
        """启动"""
        # 将事件管理器设为启动
        self.__active = True
        # 启动事件处理线程
        self.__thread.start()

    # ----------------------------------------------------------------------
    def Stop(self):
        """停止"""
        # 将事件管理器设为停止
        self.__active = False
        # 等待事件处理线程退出
        self.__thread.join()

    # ----------------------------------------------------------------------
    def register(self, type_, handler):
        """绑定事件和监听器处理函数"""
        # 尝试获取该事件类型对应的处理函数列表，若无则创建
        try:
            handlerList = self.__handlers[type_]
        except KeyError:
            handlerList = []

        self.__handlers[type_] = handlerList
        # 若要注册的处理器不在该事件的处理器列表中，则注册该事件
        if handler not in handlerList:
            handlerList.append(handler)

    # ----------------------------------------------------------------------
    def unregister(self, type_, handler):
        """移除监听器的处理函数"""
        # 读者自己试着实现

    # ----------------------------------------------------------------------
    def put(self, event):
        """发送事件，向事件队列中存入事件"""
        self.__eventQueue.put(event)


class Event:
    """事件对象"""
    def __init__(self, type_, data=None):
        self.type_ = type_  # 事件类型
        self.data = data  # 字典用于保存具体的事件数据


# 事件名称  新文章
EVENT_ARTICAL = "Event_Artical"


# 监听器 订阅者
def Listener1(event):
    print(u'listen1 收到新文章 {0}, 并发给 watch1'.format(event.type_))
    watcher1(event)


def watcher1(event):
    print(u'-- watcher1 收到新文章'.format(event.type_))


if __name__ == '__main__':
    eventManager = EventManager()

    # 绑定事件和监听器响应函数(新文章)
    eventManager.register(EVENT_ARTICAL, Listener1)
    # eventManager.register(EVENT_ARTICAL, watcher1)
    eventManager.Start()

    count = 1
    while count <= 5:
        event = Event(type_=EVENT_ARTICAL)
        eventManager.put(event)

        count += 1

