from queue import Queue, Empty
from threading import Thread, RLock
from time import sleep
from collections import defaultdict

# from engine.event_engine_base import EventEngineBase
# from core.const import EventType
# from core.event import Event


class EventManager:
    # ----------------------------------------------------------------------
    def __init__(self, timer_interval):
        """初始化事件管理器"""
        # 事件对象列表
        self._eventQueue = Queue()
        # 事件管理器开关
        self._active = False
        # 事件处理线程
        self._thread = Thread(target=self._run)

        # 这里的_handlers是一个字典，用来保存对应的事件的响应函数
        # 其中每个键对应的值是一个列表，列表中保存了对该事件监听的响应函数，一对多
        self._handlers = defaultdict(list)
        self._handlers_general = []

        # 线程锁
        self._lock = RLock()

        # 计时器，用于触发计时器事件
        self._timer = Thread(target=self._run_timer)
        self._timer_active = False  # 计时器工作状态
        self._timer_sleep = timer_interval  # 计时器触发间隔（默认1秒）

    # ----------------------------------------------------------------------
    def _run(self):
        """引擎运行"""
        while self._active:
            try:
                # 获取事件的阻塞时间设为1秒
                event = self._eventQueue.get(block=True, timeout=1)
                self._process(event)
            except Empty:
                pass

    # ----------------------------------------------------------------------
    def _process(self, event):
        """处理事件"""
        # 检查是否存在对该事件进行监听的处理函数
        if event.type_ in self._handlers:
            # 若存在，则按顺序将事件传递给处理函数执行
            for handler in self._handlers[event.type_]:
                handler(event)

        if event.type_ != 'event_timer':
            for handler in self._handlers_general:
                handler(event)

    def _run_timer(self):
        """运行在计时器线程中的循环函数"""
        while self._timer_active:
            # 创建计时器事件
            event = Event('event_timer')

            # 向队列中存入计时器事件
            self.put(event)

            # 等待
            sleep(self._timer_sleep)

    # ----------------------------------------------------------------------
    def start(self, timer=True):
        """启动"""
        # 将事件管理器设为启动
        self._active = True
        # 启动事件处理线程
        self._thread.start()

        # 启动计时器，计时器事件间隔默认设定为1秒
        if timer:
            self._timer_active = True
            self._timer.start()

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
    print('update_bar method deals {0}'.format(event.data))
    print('### event data saved')

    if event.data % 2 == 0:
        handle_order(event)


def handle_order(event):
    print('handle_order_() method {0}'.format(event.data))
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


def handle_timer(event):
    print('... di da di, {0} goes'.format(event.type_))
    pass


def update_bar_info(event):
    print('-- run update_bar_info() method {0}'.format(event.data))
    pass


class Event:
    """事件对象"""
    def __init__(self, type_, data=None):
        self.type_ = type_  # 事件类型
        self.data = data  # 字典用于保存具体的事件数据


EVENT_TIMER = "event_timer"                         # 定时事件
EVENT_MARKET = "event_bar"                       # 市场数据事件
EVENT_ORDER = "event_order"                         # 委托订单事件
EVENT_RISK = "event_risk_management"     # 事前风控事件
EVENT_TRADE = "event_trade"                         # 成交/交易事件
EVENT_RECORD = "update_bar_info"                       # 数据记录事件


if __name__ == '__main__':
    # dd1 = {111: {'aa': 'a1', 'bb': 'b1'},
    #        112: {'aa': 'a2', 'bb': 'b2'},
    #        113: {'aa': 'a3', 'bb': 'b3'}}

    dd1 = [i for i in range(1, 30)]
    dd2 = iter(dd1)

    # trial_engine = EventEngineBase(1)
    trial_engine = EventManager(1)

    # 市场事件的监听/回调函数注册
    trial_engine.register(EVENT_MARKET, new_bar)

    # 订单委托事件的监听/回调函数注册
    trial_engine.register(EVENT_ORDER, handle_order)

    # 事前风控事件的监听/回调函数注册
    trial_engine.register(EVENT_RISK, handle_risk)

    # 时间事件的监听/回调函数注册
    trial_engine.register(EVENT_TIMER, handle_timer)

    trial_engine.register_general(update_bar_info)

    trial_engine.start(timer=False)

    while True:
        try:
            x = next(dd2)
            # cur_index = x
        except Exception:
            print('data over')
            break
        else:
            event = Event('event_bar', x)
            trial_engine.put(event)

    pass


