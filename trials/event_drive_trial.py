from queue import Queue, Empty
from threading import *

# from engine.event_engine_base import EventEngineBase
# from core.const import EventType
# from core.event import Event


class EventManager:
    # ----------------------------------------------------------------------
    def __init__(self):
        """初始化事件管理器"""
        # 事件对象列表
        self._eventQueue = Queue()
        # 事件管理器开关
        self._active = False
        # 事件处理线程
        self._thread = Thread(target=self._run)

        # 这里的_handlers是一个字典，用来保存对应的事件的响应函数
        # 其中每个键对应的值是一个列表，列表中保存了对该事件监听的响应函数，一对多
        self._handlers = {}
        self._handlers_general = []

    # ----------------------------------------------------------------------
    def _run(self):
        """引擎运行"""
        while self._active:
            try:
                # 获取事件的阻塞时间设为1秒
                event = self._eventQueue.get(block=True, timeout=1)
                self._process(event)
            except Empty:
                break

    # ----------------------------------------------------------------------
    def _process(self, event):
        """处理事件"""
        # 检查是否存在对该事件进行监听的处理函数
        if event.type_ in self._handlers:
            # 若存在，则按顺序将事件传递给处理函数执行
            for handler in self._handlers[event.type_]:
                handler(event)

        for handler in self._handlers_general:
            handler(event)

    # ----------------------------------------------------------------------
    def start(self):
        """启动"""
        # 将事件管理器设为启动
        self._active = True
        # 启动事件处理线程
        self._thread.start()

    # ----------------------------------------------------------------------
    def stop(self):
        """停止"""
        # 将事件管理器设为停止
        self._active = False
        # 等待事件处理线程退出
        self._thread.join()

    # ----------------------------------------------------------------------
    def register(self, type_, handler):
        """绑定事件和监听器处理函数"""
        # 尝试获取该事件类型对应的处理函数列表，若无则创建
        try:
            handlerList = self._handlers[type_]
        except KeyError:
            handlerList = []

        self._handlers[type_] = handlerList
        # 若要注册的处理器不在该事件的处理器列表中，则注册该事件
        if handler not in handlerList:
            handlerList.append(handler)

    # ----------------------------------------------------------------------
    def unregister(self, type_, handler):
        """移除监听器的处理函数"""
        # 读者自己试着实现

    def register_general(self, handler):
        """注册通用事件处理函数监听"""
        if handler not in self._handlers_general:
            self._handlers_general.append(handler)

    # ----------------------------------------------------------------------
    def put(self, event):
        """发送事件，向事件队列中存入事件"""
        self._eventQueue.put(event)


def new_bar(event):
    """"""
    print('new_bar method deals {0}'.format(event.data))
    print('### event data saved')

    if event.data % 2 == 0:
        handle_order(event)


def handle_order(event):
    print('handle_order() method {0}'.format(event.data))
    print('### event data saved')

    handle_risk(event)
    pass


def handle_risk(event):
    print('handle_risk() method {0}'.format(event.data))
    print('### event data saved')

    if event.data % 3 == 0:
        handle_trade(event)
    pass


def handle_trade(event):
    if event.data % 4 == 0:
        print('handle_trade() method {0}'.format(event.data))
        print('### event data saved')
    pass


def update_bar_info(event):
    print('-- run update_bar_info() method {0}'.format(event.data))
    pass


class Event:
    """事件对象"""
    def __init__(self, type_, data=None):
        self.type_ = type_  # 事件类型
        self.data = data  # 字典用于保存具体的事件数据


if __name__ == '__main__':
    # dd1 = {111: {'aa': 'a1', 'bb': 'b1'},
    #        112: {'aa': 'a2', 'bb': 'b2'},
    #        113: {'aa': 'a3', 'bb': 'b3'}}

    dd1 = [i for i in range(1, 30)]
    dd2 = iter(dd1)

    # trial_engine = EventEngineBase(1)
    trial_engine = EventManager()

    # 市场事件的监听/回调函数注册
    trial_engine.register('event_market', new_bar)

    # 订单委托事件的监听/回调函数注册
    trial_engine.register('event_order', handle_order)

    # 事前风控事件的监听/回调函数注册
    trial_engine.register('event_risk', handle_risk)

    trial_engine.register_general(update_bar_info)

    trial_engine.start()

    while True:
        try:
            x = next(dd2)
            # cur_index = x
        except Exception:
            print('data over')
            break
        else:
            event = Event('event_market', x)
            trial_engine.put(event)

    pass


    # while True:
    #     try:
    #         x = next(dd2)
    #         count += 1
    #     except StopIteration:
    #         print("no data!")
    #         break
    #     else:
    #         cur_index = x
    #         cur_event = Event(EventType.EVENT_MARKET.value, cur_index)
    #         trial_engine.put(cur_event)
    #         pass

