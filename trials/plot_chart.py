# -*- coding: utf-8 -*-
import importlib
import sys
import talib
import numpy as np
import pandas as pd
import tushare as ts
import datetime as dt
import pyqtgraph as pg
from qtpy.QtGui import *
from qtpy.QtWidgets import *
from functools import partial
from collections import deque
from qtpy import QtGui, QtCore
from pyqtgraph.Point import Point

importlib.reload(sys)

# 字符串转换
# ---------------------------------------------------------------------------------------
# try:
#     _fromUtf8 = QtCore.QString.fromUtf8
# except AttributeError:
#     def _fromUtf8(s):
#         return s


########################################################################
# 键盘鼠标功能
########################################################################
class KeyWraper(QWidget):
    """键盘鼠标功能支持的元类"""

    # 初始化
    # ----------------------------------------------------------------------
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setMouseTracking(True)

    # 重载方法keyPressEvent(self,event),即按键按下事件方法
    # ----------------------------------------------------------------------
    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Up:
            self.onUp()
        elif event.key() == QtCore.Qt.Key_Down:
            self.onDown()
        elif event.key() == QtCore.Qt.Key_Left:
            self.onLeft()
        elif event.key() == QtCore.Qt.Key_Right:
            self.onRight()
        elif event.key() == QtCore.Qt.Key_PageUp:
            self.onPre()
        elif event.key() == QtCore.Qt.Key_PageDown:
            self.onNxt()

    # 重载方法mousePressEvent(self,event),即鼠标点击事件方法
    # ----------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self.onRClick(event.pos())
        elif event.button() == QtCore.Qt.LeftButton:
            self.onLClick(event.pos())

    # 重载方法mouseReleaseEvent(self,event),即鼠标点击事件方法
    # ----------------------------------------------------------------------
    def mouseRelease(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self.onRRelease(event.pos())
        elif event.button() == QtCore.Qt.LeftButton:
            self.onLRelease(event.pos())
        self.releaseMouse()

    # 重载方法wheelEvent(self,event),即滚轮事件方法
    # ----------------------------------------------------------------------
    def wheelEvent(self, event):
        return

    # 重载方法paintEvent(self,event),即拖动事件方法
    # ----------------------------------------------------------------------
    def paintEvent(self, event):
        self.onPaint()

    # PgDown键
    # ----------------------------------------------------------------------
    def onNxt(self):
        pass

    # PgUp键
    # ----------------------------------------------------------------------
    def onPre(self):
        pass

    # 向上键和滚轮向上
    # ----------------------------------------------------------------------
    def onUp(self):
        pass

    # 向下键和滚轮向下
    # ----------------------------------------------------------------------
    def onDown(self):
        pass

    # 向左键
    # ----------------------------------------------------------------------
    def onLeft(self):
        pass

    # 向右键
    # ----------------------------------------------------------------------
    def onRight(self):
        pass

    # 鼠标左单击
    # ----------------------------------------------------------------------
    def onLClick(self, pos):
        pass

    # 鼠标右单击
    # ----------------------------------------------------------------------
    def onRClick(self, pos):
        pass

    # 鼠标左释放
    # ----------------------------------------------------------------------
    def onLRelease(self, pos):
        pass

    # 鼠标右释放
    # ----------------------------------------------------------------------
    def onRRelease(self, pos):
        pass

    # 画图
    # ----------------------------------------------------------------------
    def onPaint(self):
        pass


########################################################################
# 选择缩放功能支持
########################################################################
class CustomViewBox(pg.ViewBox):
    # ----------------------------------------------------------------------
    def __init__(self, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
        # 拖动放大模式
        self.setMouseMode(self.RectMode)

    ## 右键自适应
    # ----------------------------------------------------------------------
    def mouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.RightButton:
            self.autoRange()


########################################################################
# 时间序列，横坐标支持
########################################################################
class MyStringAxis(pg.AxisItem):
    """时间序列横坐标支持"""

    # 初始化
    # ----------------------------------------------------------------------
    def __init__(self, xdict, *args, **kwargs):
        pg.AxisItem.__init__(self, *args, **kwargs)
        self.minVal = 0
        self.maxVal = 0
        self.xdict = xdict
        self.x_values = np.asarray(xdict.keys())
        self.x_strings = xdict.values()
        self.setPen(color=(255, 255, 255, 255), width=0.8)
        self.setStyle(tickFont=QFont("Roman times", 10, QFont.Bold), autoExpandTextSpace=True)

    # 更新坐标映射表
    # ----------------------------------------------------------------------
    def update_xdict(self, xdict):
        self.xdict.update(xdict)
        self.x_values = np.asarray(self.xdict.keys())
        self.x_strings = self.xdict.values()

    # 将原始横坐标转换为时间字符串,第一个坐标包含日期
    # ----------------------------------------------------------------------
    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            vs = v * scale
            if vs in self.x_values:
                vstr = self.x_strings[np.abs(self.x_values - vs).argmin()]
                vstr = vstr.strftime('%Y-%m-%d %H:%M:%S')
            else:
                vstr = ""
            strings.append(vstr)
        return strings


########################################################################
# K线图形对象
########################################################################
class CandlestickItem(pg.GraphicsObject):
    """K线图形对象"""

    # 初始化
    # ----------------------------------------------------------------------
    def __init__(self, data):
        """初始化"""
        pg.GraphicsObject.__init__(self)
        # 数据格式: [ (time, open, close, low, high),...]
        self.data = data
        # 只重画部分图形，大大提高界面更新速度
        self.rect = None
        self.picture = None
        self.setFlag(self.ItemUsesExtendedStyleOption)
        # 画笔和画刷
        w = 0.4
        self.offset = 0
        self.low = 0
        self.high = 1
        self.picture = QtGui.QPicture()
        self.pictures = []
        self.bPen = pg.mkPen(color=(0, 240, 240, 255), width=w * 2)
        self.bBrush = pg.mkBrush((0, 240, 240, 255))
        self.rPen = pg.mkPen(color=(255, 60, 60, 255), width=w * 2)
        self.rBrush = pg.mkBrush((255, 60, 60, 255))
        # self.rBrush.setStyle(Qt.NoBrush) # 控制阳线是否空心
        # 刷新K线
        self.generatePicture(self.data)

    # 画K线
    # ----------------------------------------------------------------------
    def generatePicture(self, data=None, redraw=False):
        """重新生成图形对象"""
        # 重画或者只更新最后一个K线
        if redraw:
            self.pictures = []
        elif self.pictures:
            self.pictures.pop()  # pop()函数用于移除列表中的一个元素（默认最后一个元素），并且返回该元素的值。
        w = 0.4
        bPen = self.bPen
        bBrush = self.bBrush
        rPen = self.rPen
        rBrush = self.rBrush
        self.low, self.high = (np.min(data['low']), np.max(data['high'])) if len(data) > 0 else (0, 1)
        npic = len(self.pictures)
        pltMa = False  # 是否绘制ma均线
        pltBoll = True  # 是否绘制boll线
        prema5, prema10, prema20 = (0, 0, 0)
        preBoll_Up, preBoll_Mid, preBoll_Down = (0, 0, 0)
        for (t, open0, close0, low0, high0, ma5, ma10, ma20, Boll_Up, Boll_Mid, Boll_Down) in data:
            if t >= npic:
                picture = QtGui.QPicture()
                p = QtGui.QPainter(picture)
                # 下跌蓝色（实心）, 上涨红色（空心）
                pen, brush, pmin, pmax = (bPen, bBrush, close0, open0) \
                    if open0 > close0 else (rPen, rBrush, open0, close0)
                p.setPen(pen)
                p.setBrush(brush)
                # 画K线方块和上下影线
                if open0 == close0:
                    p.drawLine(QtCore.QPointF(t - w, open0), QtCore.QPointF(t + w, close0))
                else:
                    p.drawRect(QtCore.QRectF(t - w, open0, w * 2, close0 - open0))
                if pmin > low0:
                    p.drawLine(QtCore.QPointF(t, low0), QtCore.QPointF(t, pmin))
                if high0 > pmax:
                    p.drawLine(QtCore.QPointF(t, pmax), QtCore.QPointF(t, high0))
                if (open0 != 0 and low0 != 0) or (close0 != 0 and low0 != 0):
                    # 绘制主图MA均线
                    if pltMa:
                        if prema5 != 0:
                            p.setPen(pg.mkPen('y'))
                            p.setBrush(pg.mkBrush('y'))
                            p.drawLine(QtCore.QPointF(t - 1, prema5), QtCore.QPointF(t, ma5))
                        prema5 = ma5
                        if prema10 != 0:
                            p.setPen(pg.mkPen('c'))
                            p.setBrush(pg.mkBrush('c'))
                            p.drawLine(QtCore.QPointF(t - 1, prema10), QtCore.QPointF(t, ma10))
                        prema10 = ma10
                        if prema20 != 0:
                            p.setPen(pg.mkPen('m'))
                            p.setBrush(pg.mkBrush('m'))
                            p.drawLine(QtCore.QPointF(t - 1, prema20), QtCore.QPointF(t, ma20))
                        prema20 = ma20
                    # 绘制主图Boll线
                    if pltBoll:
                        if preBoll_Up != 0:
                            p.setPen(pg.mkPen('m'))
                            p.setBrush(pg.mkBrush('m'))
                            p.drawLine(QtCore.QPointF(t - 1, preBoll_Up), QtCore.QPointF(t, Boll_Up))
                        preBoll_Up = Boll_Up
                        if preBoll_Mid != 0:
                            p.setPen(pg.mkPen('y'))
                            p.setBrush(pg.mkBrush('y'))
                            p.drawLine(QtCore.QPointF(t - 1, preBoll_Mid), QtCore.QPointF(t, Boll_Mid))
                        preBoll_Mid = Boll_Mid
                        if preBoll_Down != 0:
                            p.setPen(pg.mkPen('c'))
                            p.setBrush(pg.mkBrush('c'))
                            p.drawLine(QtCore.QPointF(t - 1, preBoll_Down), QtCore.QPointF(t, Boll_Down))
                        preBoll_Down = Boll_Down
                p.end()
                self.pictures.append(picture)

    # 手动重画
    # ----------------------------------------------------------------------
    def update(self):
        if not self.scene() is None:
            self.scene().update()

    # 自动重画
    # ----------------------------------------------------------------------
    def paint(self, painter, opt, w):
        rect = opt.exposedRect
        xmin, xmax = (max(0, int(rect.left())), min(int(len(self.pictures)), int(rect.right())))
        if not self.rect == (rect.left(), rect.right()) or self.picture is None:
            self.rect = (rect.left(), rect.right())
            self.picture = self.createPic(xmin, xmax)
            self.picture.play(painter)
        elif not self.picture is None:
            self.picture.play(painter)

    # 缓存图片
    # ----------------------------------------------------------------------
    def createPic(self, xmin, xmax):
        picture = QPicture()
        p = QPainter(picture)
        [pic.play(p) for pic in self.pictures[xmin:xmax]]
        p.end()
        return picture

    # 定义边界
    # ----------------------------------------------------------------------
    def boundingRect(self):
        return QtCore.QRectF(0, self.low, len(self.pictures), (self.high - self.low))


########################################################################
class KLineWidget(KeyWraper):
    """用于显示价格走势图"""

    # 窗口标识
    clsId = 0

    # 保存K线数据的列表和Numpy Array对象
    listBar = []
    listVol = []
    listHigh = []
    listLow = []
    listSig = []
    listOpenInterest = []
    arrows = []

    # 是否完成了历史数据的读取
    initCompleted = False

    # ----------------------------------------------------------------------
    def __init__(self, parent=None):
        """Constructor"""
        self.parent = parent
        super(KLineWidget, self).__init__(parent)

        # 当前序号
        self.index = None  # 下标
        self.countK = 200  # 显示的Ｋ线范围

        KLineWidget.clsId += 1
        self.windowId = str(KLineWidget.clsId)

        # 缓存数据
        self.datas = []
        self.listBar = []
        self.listVol = []
        self.listHigh = []
        self.listLow = []
        self.listSig = []
        self.listOpenInterest = []
        self.arrows = []

        # 所有K线上信号图
        self.allColor = deque(['blue', 'green', 'yellow', 'white'])
        self.sigData = {}
        self.sigColor = {}
        self.sigPlots = {}

        # 所有副图上信号图
        self.allSubColor = deque(['blue', 'green', 'yellow', 'white'])
        self.subSigData = {}
        self.subSigColor = {}
        self.subSigPlots = {}

        # 初始化完成
        self.initCompleted = False

        # 调用函数
        self.initUi()

    # ----------------------------------------------------------------------
    #  初始化相关
    # ----------------------------------------------------------------------
    def initUi(self):
        """初始化界面"""
        self.setWindowTitle(u'行情走势图')
        # 主图
        self.pw = pg.PlotWidget()
        # 界面布局
        self.lay_KL = pg.GraphicsLayout(border=(100, 100, 100, 100))
        self.lay_KL.setContentsMargins(0, 0, 0, 0)  # 外层边框留白
        self.lay_KL.setSpacing(0)
        self.lay_KL.setBorder(color=(160, 160, 160, 255), width=0.0)
        self.lay_KL.setZValue(0)
        # self.KLtitle = self.lay_KL.addLabel(u'')
        self.pw.setCentralItem(self.lay_KL)
        # 设置横坐标
        xdict = {}
        self.axisTime = MyStringAxis(xdict, orientation='bottom')
        # 初始化子图
        self.initplotKline()
        self.initplotVol()
        self.initplotOI()
        # 注册十字光标
        self.crosshair = Crosshair(self.pw, self)
        # 设置界面
        self.vb = QVBoxLayout()
        self.vb.addWidget(self.pw)
        self.vb.setContentsMargins(0, 0, 0, 0)  # 绘图边框留白
        self.setLayout(self.vb)
        # 初始化完成
        self.initCompleted = True

        # ----------------------------------------------------------------------

    def makePI(self, name):
        """生成PlotItem对象"""
        vb = CustomViewBox()
        plotItem = pg.PlotItem(viewBox=vb, name=name, axisItems={'bottom': self.axisTime})
        plotItem.setMenuEnabled(False)
        plotItem.setClipToView(True)
        plotItem.hideAxis('left')
        plotItem.showAxis('right')
        plotItem.setDownsampling(mode='peak')
        plotItem.setRange(xRange=(0, 1), yRange=(0, 1))
        plotItem.getAxis('right').setWidth(48)
        plotItem.getAxis('right').setStyle(tickFont=QFont("Roman times", 10, QFont.Bold))
        plotItem.getAxis('right').setPen(color=(255, 255, 255, 255), width=0.5)  # 图标Y轴水平线样式
        plotItem.showGrid(True, True)
        plotItem.hideButtons()
        return plotItem

    # ----------------------------------------------------------------------
    def initplotVol(self):
        """初始化成交量子图"""
        self.pwVol = self.makePI('_'.join([self.windowId, 'PlotVOL']))
        self.volume = CandlestickItem(self.listVol)
        self.pwVol.addItem(self.volume)
        self.pwVol.setMaximumHeight(150)
        self.pwVol.setXLink('_'.join([self.windowId, 'PlotOI']))
        self.pwVol.hideAxis('bottom')

        self.lay_KL.nextRow()
        self.lay_KL.addItem(self.pwVol)

    # ----------------------------------------------------------------------
    def initplotKline(self):
        """初始化K线子图"""
        self.pwKL = self.makePI('_'.join([self.windowId, 'PlotKL']))
        self.candle = CandlestickItem(self.listBar)
        self.pwKL.addItem(self.candle)
        self.pwKL.setMinimumHeight(350)
        self.pwKL.setXLink('_'.join([self.windowId, 'PlotOI']))
        self.pwKL.hideAxis('bottom')

        self.lay_KL.nextRow()
        self.lay_KL.addItem(self.pwKL)

    # ----------------------------------------------------------------------
    def initplotOI(self):
        """初始化持仓量子图"""
        self.pwOI = self.makePI('_'.join([self.windowId, 'PlotOI']))
        self.curveOI = self.pwOI.plot()

        self.lay_KL.nextRow()
        self.lay_KL.addItem(self.pwOI)

    # ----------------------------------------------------------------------
    #  画图相关
    # ----------------------------------------------------------------------
    def plotVol(self, redraw=False, xmin=0, xmax=-1):
        """重画成交量子图"""
        if self.initCompleted:
            self.volume.generatePicture(self.listVol[xmin:xmax], redraw)  # 画成交量子图

    # ----------------------------------------------------------------------
    def plotKline(self, redraw=False, xmin=0, xmax=-1):
        """重画K线子图"""
        if self.initCompleted:
            self.candle.generatePicture(self.listBar[xmin:xmax], redraw)  # 画K线
            self.plotMark()  # 显示开平仓信号位置

    # ----------------------------------------------------------------------
    def plotOI(self, xmin=0, xmax=-1):
        """重画持仓量子图"""
        if self.initCompleted:
            self.curveOI.setData(np.append(self.listOpenInterest[xmin:xmax], 0), pen='w', name="OpenInterest")

    # ----------------------------------------------------------------------
    def addSig(self, sig, main=True):
        """新增信号图"""
        if main:
            if sig in self.sigPlots:
                self.pwKL.removeItem(self.sigPlots[sig])
            self.sigPlots[sig] = self.pwKL.plot()
            self.sigColor[sig] = self.allColor[0]
            self.allColor.append(self.allColor.popleft())
        else:
            if sig in self.subSigPlots:
                self.pwOI.removeItem(self.subSigPlots[sig])
            self.subSigPlots[sig] = self.pwOI.plot()
            self.subSigColor[sig] = self.allSubColor[0]
            self.allSubColor.append(self.allSubColor.popleft())

    # ----------------------------------------------------------------------
    def showSig(self, datas, main=True, clear=False):
        """刷新信号图"""
        if clear:
            self.clearSig(main)
            if datas and not main:
                sigDatas = np.array(datas.values()[0])
                self.listOpenInterest = sigDatas
                self.datas['openInterest'] = sigDatas
                self.plotOI(0, len(sigDatas))
        if main:
            for sig in datas:
                self.addSig(sig, main)
                self.sigData[sig] = datas[sig]
                self.sigPlots[sig].setData(np.append(datas[sig], 0), pen=self.sigColor[sig][0], name=sig)
        else:
            for sig in datas:
                self.addSig(sig, main)
                self.subSigData[sig] = datas[sig]
                self.subSigPlots[sig].setData(np.append(datas[sig], 0), pen=self.subSigColor[sig][0], name=sig)

    # ----------------------------------------------------------------------
    def plotMark(self):
        """显示开平仓信号"""
        # 检查是否有数据
        if len(self.datas) == 0:
            return
        for arrow in self.arrows:
            self.pwKL.removeItem(arrow)
        # 画买卖信号
        for i in range(len(self.listSig)):
            # 无信号
            if self.listSig[i] == 0:
                continue
            # 买信号
            elif self.listSig[i] > 0:
                arrow = pg.ArrowItem(pos=(i, self.datas[i]['low']), angle=90, brush=(255, 0, 0))
            # 卖信号
            elif self.listSig[i] < 0:
                arrow = pg.ArrowItem(pos=(i, self.datas[i]['high']), angle=-90, brush=(0, 255, 0))
            self.pwKL.addItem(arrow)
            self.arrows.append(arrow)

    # ----------------------------------------------------------------------
    def updateAll(self):
        """
        手动更新所有K线图形，K线播放模式下需要
        """
        datas = self.datas
        self.volume.pictrue = None
        self.candle.pictrue = None
        self.volume.update()
        self.candle.update()

        def update(view, low, high):
            vRange = view.viewRange()
            xmin = max(0, int(vRange[0][0]))
            xmax = max(0, int(vRange[0][1]))
            try:
                xmax = min(xmax, len(datas) - 1)
            except:
                xmax = xmax
            if len(datas) > 0 and xmax > xmin:
                ymin = min(datas[xmin:xmax][low])
                ymax = max(datas[xmin:xmax][high])
                view.setRange(yRange=(ymin, ymax))
            else:
                view.setRange(yRange=(0, 1))

        update(self.pwKL.getViewBox(), 'low', 'high')
        update(self.pwVol.getViewBox(), 'volume', 'volume')

    # ----------------------------------------------------------------------
    def plotAll(self, redraw=True, xMin=0, xMax=-1):
        """
        重画所有界面
        redraw ：False=重画最后一根K线; True=重画所有
        xMin,xMax : 数据范围
        """
        xMax = len(self.datas) - 1 if xMax < 0 else xMax
        # self.countK = xMax-xMin
        # self.index = int((xMax+xMin)/2)
        self.pwOI.setLimits(xMin=xMin, xMax=xMax)
        self.pwKL.setLimits(xMin=xMin, xMax=xMax)
        self.pwVol.setLimits(xMin=xMin, xMax=xMax)
        self.plotKline(redraw, xMin, xMax)  # K线图
        self.plotVol(redraw, xMin, xMax)  # K线副图，成交量
        self.plotOI(0, len(self.datas))  # K线副图，持仓量
        self.refresh()

    # ----------------------------------------------------------------------
    def refresh(self):
        """
        刷新三个子图的现实范围
        """
        datas = self.datas
        minutes = int(self.countK / 2)
        xmin = max(0, self.index - minutes)
        try:
            xmax = min(xmin + 2 * minutes, len(self.datas) - 1) if self.datas else xmin + 2 * minutes
        except:
            xmax = xmin + 2 * minutes
        self.pwOI.setRange(xRange=(xmin, xmax))
        self.pwKL.setRange(xRange=(xmin, xmax))
        self.pwVol.setRange(xRange=(xmin, xmax))

    # ----------------------------------------------------------------------
    #  快捷键相关
    # ----------------------------------------------------------------------
    def onNxt(self):
        """跳转到下一个开平仓点"""
        if len(self.listSig) > 0 and not self.index is None:
            datalen = len(self.listSig)
            if self.index < datalen - 2: self.index += 1
            while self.index < datalen - 2 and self.listSig[self.index] == 0:
                self.index += 1
            self.refresh()
            x = self.index
            y = self.datas[x]['close']
            self.crosshair.signal.emit((x, y))

    # ----------------------------------------------------------------------
    def onPre(self):
        """跳转到上一个开平仓点"""
        if len(self.listSig) > 0 and not self.index is None:
            if self.index > 0: self.index -= 1
            while self.index > 0 and self.listSig[self.index] == 0:
                self.index -= 1
            self.refresh()
            x = self.index
            y = self.datas[x]['close']
            self.crosshair.signal.emit((x, y))

    # ----------------------------------------------------------------------
    def onDown(self):
        """放大显示区间"""
        self.countK = min(len(self.datas), int(self.countK * 1.2) + 1)
        self.refresh()
        if len(self.datas) > 0:
            x = self.index - self.countK / 2 + 2 if int(
                self.crosshair.xAxis) < self.index - self.countK / 2 + 2 else int(self.crosshair.xAxis)
            x = self.index + self.countK / 2 - 2 if x > self.index + self.countK / 2 - 2 else x
            x = len(self.datas) - 1 if x > len(self.datas) - 1 else int(x)
            y = self.datas[x][2]
            self.crosshair.signal.emit((x, y))

    # ----------------------------------------------------------------------
    def onUp(self):
        """缩小显示区间"""
        self.countK = max(3, int(self.countK / 1.2) - 1)
        self.refresh()
        if len(self.datas) > 0:
            x = self.index - self.countK / 2 + 2 if int(
                self.crosshair.xAxis) < self.index - self.countK / 2 + 2 else int(self.crosshair.xAxis)
            x = self.index + self.countK / 2 - 2 if x > self.index + self.countK / 2 - 2 else x
            x = len(self.datas) - 1 if x > len(self.datas) - 1 else int(x)
            y = self.datas[x]['close']
            self.crosshair.signal.emit((x, y))

    # ----------------------------------------------------------------------
    def onLeft(self):
        """向左移动"""
        if len(self.datas) > 0 and int(self.crosshair.xAxis) > 2:
            x = int(self.crosshair.xAxis) - 1
            x = len(self.datas) - 1 if x > len(self.datas) - 1 else int(x)
            y = self.datas[x]['close']
            if x <= self.index - self.countK / 2 + 2 and self.index > 1:
                self.index -= 1
                self.refresh()
            self.crosshair.signal.emit((x, y))

    # ----------------------------------------------------------------------
    def onRight(self):
        """向右移动"""
        if len(self.datas) > 0 and int(self.crosshair.xAxis) < len(self.datas) - 1:
            x = int(self.crosshair.xAxis) + 1
            x = len(self.datas) - 1 if x > len(self.datas) - 1 else int(x)
            y = self.datas[x]['close']
            if x >= self.index + int(self.countK / 2) - 2:
                self.index += 1
                self.refresh()
            self.crosshair.signal.emit((x, y))

    # ----------------------------------------------------------------------
    # 界面回调相关
    # ----------------------------------------------------------------------
    def onPaint(self):
        """界面刷新回调"""
        view = self.pwKL.getViewBox()
        vRange = view.viewRange()
        xmin = max(0, int(vRange[0][0]))
        xmax = max(0, int(vRange[0][1]))
        self.index = int((xmin + xmax) / 2) + 1

    # ----------------------------------------------------------------------
    def resignData(self, datas):
        """更新数据，用于Y坐标自适应"""
        self.crosshair.datas = datas

        def viewXRangeChanged(low, high, self):
            vRange = self.viewRange()
            xmin = max(0, int(vRange[0][0]))
            xmax = max(0, int(vRange[0][1]))
            xmax = min(xmax, len(datas))
            if len(datas) > 0 and xmax > xmin:
                ymin = min(datas[xmin:xmax][low])
                ymax = max(datas[xmin:xmax][high])
                ymin, ymax = (-1, 1) if ymin == ymax else (ymin, ymax)
                self.setRange(yRange=(ymin, ymax))
            else:
                self.setRange(yRange=(0, 1))

        view = self.pwKL.getViewBox()
        view.sigXRangeChanged.connect(partial(viewXRangeChanged, 'low', 'high'))

        view = self.pwVol.getViewBox()
        view.sigXRangeChanged.connect(partial(viewXRangeChanged, 'volume', 'volume'))

        view = self.pwOI.getViewBox()
        view.sigXRangeChanged.connect(partial(viewXRangeChanged, 'openInterest', 'openInterest'))

    # ----------------------------------------------------------------------
    # 数据相关
    # ----------------------------------------------------------------------
    def clearData(self):
        """清空数据"""
        # 清空数据，重新画图
        self.time_index = []
        self.listBar = []
        self.listVol = []
        self.listLow = []
        self.listHigh = []
        self.listOpenInterest = []
        self.listSig = []
        self.sigData = {}
        self.datas = None

    # ----------------------------------------------------------------------
    def clearSig(self, main=True):
        """清空信号图形"""
        # 清空信号图
        if main:
            for sig in self.sigPlots:
                self.pwKL.removeItem(self.sigPlots[sig])
            self.sigData = {}
            self.sigPlots = {}
        else:
            for sig in self.subSigPlots:
                self.pwOI.removeItem(self.subSigPlots[sig])
            self.subSigData = {}
            self.subSigPlots = {}

    # ----------------------------------------------------------------------
    def updateSig(self, sig):
        """刷新买卖信号"""
        self.listSig = sig
        self.plotMark()

    # ----------------------------------------------------------------------
    def onBar(self, bar):
        """
        新增K线数据,K线播放模式
        """
        # 是否需要更新K线
        newBar = False if len(self.datas) > 0 and bar.datetime == self.datas[-1].datetime else True
        nrecords = len(self.datas) if newBar else len(self.datas) - 1
        bar.openInterest = np.random.randint(0,
                                             3) if bar.openInterest == np.inf or bar.openInterest == -np.inf else bar.openInterest
        recordVol = (nrecords, abs(bar.volume), 0, 0, abs(bar.volume)) if bar.close < bar.open else (
            nrecords, 0, abs(bar.volume), 0, abs(bar.volume))

        if newBar and any(self.datas):
            self.datas.resize(nrecords + 1, refcheck=0)
            self.listBar.resize(nrecords + 1, refcheck=0)
            self.listVol.resize(nrecords + 1, refcheck=0)
        elif any(self.datas):
            self.listLow.pop()
            self.listHigh.pop()
            self.listOpenInterest.pop()
        if any(self.datas):
            self.datas[-1] = (bar.datetime, bar.open, bar.close, bar.low, bar.high, bar.volume, bar.openInterest)
            self.listBar[-1] = (nrecords, bar.open, bar.close, bar.low, bar.high)
            self.listVol[-1] = recordVol
        else:
            self.datas = np.rec.array(
                [(bar.datetime, bar.open, bar.close, bar.low, bar.high, bar.volume, bar.openInterest)], \
                names=('datetime', 'open', 'close', 'low', 'high', 'volume', 'openInterest'))
            self.listBar = np.rec.array([(nrecords, bar.open, bar.close, bar.low, bar.high)], \
                                        names=('time_int', 'open', 'close', 'low', 'high'))
            self.listVol = np.rec.array([recordVol], names=('time_int', 'open', 'close', 'low', 'high'))
            self.resignData(self.datas)

        self.axisTime.update_xdict({nrecords: bar.datetime})
        self.listLow.append(bar.low)
        self.listHigh.append(bar.high)
        self.listOpenInterest.append(bar.openInterest)
        self.resignData(self.datas)
        return newBar

    # ----------------------------------------------------------------------
    def loadData(self, datas, sigs=None):
        """
        载入pandas.DataFrame数据
        datas : 数据格式，cols : datetime, open, close, low, high
        """
        # 设置中心点时间
        # 绑定数据，更新横坐标映射，更新Y轴自适应函数，更新十字光标映射
        datas['time_int'] = np.array(range(len(datas.index)))
        self.datas = datas[
            ['open', 'close', 'low', 'high', 'volume', 'openInterest', 'ma5', 'ma10', 'ma20']].to_records()
        self.axisTime.xdict = {}
        xdict = dict(enumerate(datas.index.tolist()))
        self.axisTime.update_xdict(xdict)
        self.resignData(self.datas)
        # 更新画图用到的数据
        self.listBar = datas[['time_int', 'open', 'close', 'low', 'high', 'ma5', 'ma10', 'ma20', 'Boll_Up', 'Boll_Mid',
                              'Boll_Down']].to_records(False)
        self.listHigh = list(datas['high'])
        self.listLow = list(datas['low'])
        self.listOpenInterest = list(datas['openInterest'])
        self.listSig = [0] * (len(self.datas) - 1) if sigs is None else sigs
        # 成交量颜色和涨跌同步，K线方向由涨跌决定
        datas0 = pd.DataFrame()
        datas0['open'] = datas.apply(lambda x: 0 if x['close'] >= x['open'] else x['volume'], axis=1)
        datas0['close'] = datas.apply(lambda x: 0 if x['close'] < x['open'] else x['volume'], axis=1)
        datas0['low'] = 0
        datas0['high'] = datas['volume']
        datas0['time_int'] = np.array(range(len(datas.index)))
        datas0['ma5'] = datas['ma5']
        datas0['ma10'] = datas['ma10']
        datas0['ma20'] = datas['ma20']
        datas0['Boll_Up'] = datas['Boll_Up']
        datas0['Boll_Mid'] = datas['Boll_Mid']
        datas0['Boll_Down'] = datas['Boll_Down']
        self.listVol = datas0[['time_int', 'open', 'close', 'low', 'high', 'ma5', 'ma10', 'ma20', 'Boll_Up', 'Boll_Mid',
                               'Boll_Down']].to_records(False)

    # ----------------------------------------------------------------------
    def refreshAll(self, redraw=True, update=False):
        """
        更新所有界面
        """
        # 调用画图函数
        self.index = len(self.datas)
        self.plotAll(redraw, 0, len(self.datas))
        if not update:
            self.updateAll()
        self.crosshair.signal.emit((None, None))

    def setCrosshairInfo(self, code, ktype):
        self.crosshair.setInfo(code, ktype)


########################################################################
# 十字光标支持
########################################################################
class Crosshair(QtCore.QObject):
    """
    此类给pg.PlotWidget()添加crossHair功能,PlotWidget实例需要初始化时传入
    """
    signal = QtCore.Signal(type(tuple([])))
    signalInfo = QtCore.Signal(float, float)

    # ----------------------------------------------------------------------
    def __init__(self, parent, master):
        """Constructor"""
        self.__view = parent
        self.master = master
        super(Crosshair, self).__init__()

        self.xAxis = 0
        self.yAxis = 0

        self.datas = None

        self.code = None
        self.cycle = None

        self.yAxises = [0 for i in range(3)]
        self.leftX = [0 for i in range(3)]
        self.showHLine = [False for i in range(3)]
        self.textPrices = [pg.TextItem('', anchor=(1, 1)) for i in range(3)]
        # self.mousePrices = [pg.TextItem('', anchor=(1,0),color=(255, 255, 0, 255)) for i in range(3)]
        self.views = [parent.centralWidget.getItem(i + 1, 0) for i in range(3)]
        self.rects = [self.views[i].sceneBoundingRect() for i in range(3)]
        self.vLines = [pg.InfiniteLine(angle=90, movable=False) for i in range(3)]
        self.hLines = [pg.InfiniteLine(angle=0, movable=False) for i in range(3)]

        # mid 在y轴动态跟随最新价显示最新价和最新时间
        self.__textDate = pg.TextItem('date', anchor=(1, 1))
        self.__textInfo = pg.TextItem('lastBarInfo')
        self.__textSig = pg.TextItem('lastSigInfo', anchor=(1, 0))
        self.__textSubSig = pg.TextItem('lastSubSigInfo', anchor=(1, 0))
        self.__textVolume = pg.TextItem('lastBarVolume', anchor=(1, 0))

        self.__textDate.setZValue(2)
        self.__textInfo.setZValue(2)
        self.__textSig.setZValue(2)
        self.__textSubSig.setZValue(2)
        self.__textVolume.setZValue(2)
        # self.__textInfo.border = pg.mkPen(color=(230, 255, 0, 255), width=0.8) # y轴动态跟随数据边框样式控制

        for i in range(3):
            self.textPrices[i].setZValue(2)
            # self.mousePrices[i].setZValue(2)
            self.vLines[i].setPos(0)
            self.hLines[i].setPos(0)
            self.vLines[i].setZValue(0)
            self.hLines[i].setZValue(0)
            self.views[i].addItem(self.vLines[i])
            self.views[i].addItem(self.hLines[i])
            self.views[i].addItem(self.textPrices[i])
            # self.views[i].addItem(self.mousePrices[i])

        self.views[0].addItem(self.__textInfo, ignoreBounds=True)
        self.views[0].addItem(self.__textSig, ignoreBounds=True)
        self.views[1].addItem(self.__textVolume, ignoreBounds=True)
        self.views[2].addItem(self.__textDate, ignoreBounds=True)
        self.views[2].addItem(self.__textSubSig, ignoreBounds=True)
        self.proxy = pg.SignalProxy(self.__view.scene().sigMouseMoved, rateLimit=360, slot=self.__mouseMoved)
        # 跨线程刷新界面支持
        self.signal.connect(self.update)
        self.signalInfo.connect(self.plotInfo)

    # ----------------------------------------------------------------------
    def update(self, pos):
        """刷新界面显示"""
        xAxis, yAxis = pos
        xAxis, yAxis = (self.xAxis, self.yAxis) if xAxis is None else (xAxis, yAxis)
        self.moveTo(xAxis, yAxis)

    # ----------------------------------------------------------------------
    def __mouseMoved(self, evt):
        """鼠标移动回调"""
        pos = evt[0]
        self.rects = [self.views[i].sceneBoundingRect() for i in range(3)]
        for i in range(3):
            self.showHLine[i] = False
            if self.rects[i].contains(pos):
                mousePoint = self.views[i].vb.mapSceneToView(pos)
                xAxis = mousePoint.x()
                yAxis = mousePoint.y()
                self.yAxises[i] = yAxis
                self.showHLine[i] = True
                self.moveTo(xAxis, yAxis)

    # ----------------------------------------------------------------------
    def moveTo(self, xAxis, yAxis):
        xAxis, yAxis = (self.xAxis, self.yAxis) if xAxis is None else (int(xAxis), yAxis)
        self.rects = [self.views[i].sceneBoundingRect() for i in range(3)]
        if not xAxis or not yAxis:
            return
        self.xAxis = xAxis
        self.yAxis = yAxis
        self.vhLinesSetXY(xAxis, yAxis)
        self.plotInfo(xAxis, yAxis)
        self.master.volume.update()

    # ----------------------------------------------------------------------
    def vhLinesSetXY(self, xAxis, yAxis):
        """水平和竖线位置设置"""
        for i in range(3):
            self.vLines[i].setPos(xAxis)
            if self.showHLine[i]:
                self.hLines[i].setPos(yAxis if i == 0 else self.yAxises[i])
                self.hLines[i].show()
            else:
                self.hLines[i].hide()

    # ----------------------------------------------------------------------
    def plotInfo(self, xAxis, yAxis):
        """
        被嵌入的plotWidget在需要的时候通过调用此方法显示K线信息
        """
        if self.datas is None:
            return
        try:
            # 获取K线数据
            data = self.datas[xAxis]
            lastdata = self.datas[xAxis - 1]
            tickDatetime = data['datetime']
            openPrice = data['open']
            closePrice = data['close']
            lowPrice = data['low']
            highPrice = data['high']
            volume = int(data['volume'])
            openInterest = int(data['openInterest'])
            preClosePrice = lastdata['close']
            tradePrice = abs(self.master.listSig[xAxis])
            code = self.code
            cycle = self.cycle
            ma5 = data['ma5']
            ma10 = data['ma10']
            ma20 = data['ma20']
        except Exception as e:
            return

        if (isinstance(tickDatetime, np.datetime64)):
            ns = 1e-9
            tickDatetime = dt.datetime.utcfromtimestamp(tickDatetime.astype(int) * ns)

        if (isinstance(tickDatetime, dt.datetime)):
            datetimeText = dt.datetime.strftime(tickDatetime, '%Y-%m-%d %H:%M:%S')
            dateText = dt.datetime.strftime(tickDatetime, '%Y-%m-%d')
            timeText = dt.datetime.strftime(tickDatetime, '%H:%M:%S')
        else:
            datetimeText = ""
            dateText = ""
            timeText = ""

        # 显示所有的主图技术指标
        html = u'<div style="text-align: right">'
        for sig in self.master.sigData:
            val = self.master.sigData[sig][xAxis]
            col = self.master.sigColor[sig]
            html += u'<span style="color: %s;  font-size: 12px;">&nbsp;&nbsp;%s：%.2f</span>' % (col, sig, val)
        html += u'</div>'
        self.__textSig.setHtml(html)

        # 显示所有的主图技术指标
        html = u'<div style="text-align: right">'
        for sig in self.master.subSigData:
            val = self.master.subSigData[sig][xAxis]
            col = self.master.subSigColor[sig]
            html += u'<span style="color: %s;  font-size: 12px;">&nbsp;&nbsp;%s：%.2f</span>' % (col, sig, val)
        html += u'</div>'
        self.__textSubSig.setHtml(html)

        # 和上一个收盘价比较，决定K线信息的字符颜色
        cOpen = 'red' if openPrice > preClosePrice else 'green'
        cClose = 'red' if closePrice > preClosePrice else 'green'
        cHigh = 'red' if highPrice > preClosePrice else 'green'
        cLow = 'red' if lowPrice > preClosePrice else 'green'

        self.__textInfo.setHtml(
            u'<div style="text-align: center<!--; background-color:#000-->">\
                <!--<span style="color: white;  font-size: 10px;">代码:</span>-->\
                <span style="color: yellow; font-size: 10px;">%s</span>\
                <!--<span style="color: white;  font-size: 10px;">日期:</span>\
                <span style="color: yellow; font-size: 10px;">%s</span>-->\
                <!--<span style="color: white;  font-size: 10px;">周期:</span>-->\
                <span style="color: cyan; font-size: 10px;">%s</span>\
                <!--<span style="color: white;  font-size: 10px;">价格:</span>-->\
                <span style="color: %s;     font-size: 10px;">开 %.3f</span>\
                <span style="color: %s;     font-size: 10px;">高 %.3f</span>\
                <span style="color: %s;     font-size: 10px;">低 %.3f</span>\
                <span style="color: %s;     font-size: 10px;">收 %.3f</span>\
                <!--<span style="color: white;  font-size: 10px;">成交量:</span>\
                <span style="color: white; font-size: 10px;">%d</span>\
                <span style="color: white;  font-size: 10px;">成交价:</span>\
                <span style="color: white; font-size: 10px;">%.3f</span>-->\
                <span style="color: yellow;  font-size: 10px;">MA5:</span>\
                <span style="color: yellow; font-size: 10px;">%.2f</span>\
                <span style="color: cyan;  font-size: 10px;">MA10:</span>\
                <span style="color: cyan; font-size: 10px;">%.2f</span>\
                <span style="color: magenta;  font-size: 10px;">MA20:</span>\
                <span style="color: magenta; font-size: 10px;">%.2f</span>\
            </div>' \
            % (code, datetimeText, cycle, cOpen, openPrice, cHigh, highPrice, \
               cLow, lowPrice, cClose, closePrice, volume, tradePrice, ma5, ma10, ma20))  # ,ma5,ma10,ma20
        self.__textDate.setHtml(
            '<div style="text-align: center">\
                <span style="color: white; font-size: 10px;">%s</span>\
            </div>' \
            % (datetimeText))

        self.__textVolume.setHtml(
            '<div style="text-align: right">\
                <span style="color: white; font-size: 10px;">VOL: %.3f</span>\
            </div>' \
            % (volume))
        # 坐标轴宽度
        rightAxisWidth = self.views[0].getAxis('right').width()
        bottomAxisHeight = self.views[2].getAxis('bottom').height()
        offset = QtCore.QPointF(rightAxisWidth, bottomAxisHeight)

        # 各个顶点
        tl = [self.views[i].vb.mapSceneToView(self.rects[i].topLeft()) for i in range(3)]
        br = [self.views[i].vb.mapSceneToView(self.rects[i].bottomRight() - offset) for i in range(3)]

        # 显示价格
        for i in range(3):
            if self.showHLine[i]:
                self.textPrices[i].setHtml(
                    '<div style="text-align: right">\
                         <span style="color: white; font-size: 10px;">\
                           %0.3f\
                         </span>\
                     </div>' \
                    % (yAxis if i == 0 else self.yAxises[i]))
                self.textPrices[i].setPos(br[i].x(), yAxis if i == 0 else self.yAxises[i])
                self.textPrices[i].show()
            else:
                self.textPrices[i].hide()

        # 设置坐标
        self.__textInfo.setPos(tl[0])
        self.__textSig.setPos(br[0].x(), tl[0].y())
        self.__textSubSig.setPos(br[2].x(), tl[2].y())
        self.__textVolume.setPos(br[1].x(), tl[1].y())  # br[1].x(),tl[1].y()

        # 修改对称方式防止遮挡
        self.__textDate.anchor = Point((1, 1)) if xAxis > self.master.index else Point((0, 1))
        self.__textDate.setPos(xAxis, br[2].y())

    # ----------------------------------------------------------------------
    def setInfo(self, code, cycle):
        """
        传入K线代码、周期等信息
        """
        self.code = code.upper()
        switcher = {
            '1': "1分钟",
            '5': "5分钟",
            '15': "15分钟",
            '30': "30分钟",
            '60': "60分钟",
            '120': "120分钟",
            'D': "日线",
            'W': "周线",
            'M': "月线",
        }
        self.cycle = switcher.get(cycle)


########################################################################
# 数据支持
########################################################################
class GetData():
    def __init__(self, *arg):
        pass

    def getData(self, code, ktype):
        self.code = code
        self.ktype = ktype
        return self.getData_Tushare(self.code, self.ktype)

    def getData_Tushare(self, code, ktype='5', start=str(dt.date.today() - dt.timedelta(days=1000)),
                        end=str(dt.date.today() + dt.timedelta(days=1))):
        try:
            pro = ts.pro_api('9cbff072025ae17a12e05b84235202a7af807f3a3e074124c8a0aae0')
            # self.k_data = ts.get_k_data(code, ktype=ktype)
            self.k_data = pro.daily(ts_code=code)
            self.k_data.rename(columns={'trade_date': 'datetime', 'vol': 'volume'}, inplace=True)
            self.k_data.drop(columns={'ts_code'}, inplace=True)
            self.k_data['openInterest'] = (self.k_data['close'] - self.k_data['open']) / self.k_data['open']
            self.k_data['ma5'] = talib.EMA(self.k_data['close'], timeperiod=5)
            self.k_data['ma10'] = talib.EMA(self.k_data['close'], timeperiod=10)
            self.k_data['ma20'] = talib.EMA(self.k_data['close'], timeperiod=20)
            self.k_data['Boll_Up'], self.k_data['Boll_Mid'], self.k_data['Boll_Down'] = \
                talib.BBANDS(self.k_data['close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
            self.k_data.index = pd.to_datetime(self.k_data['datetime'])
            self.k_data.dropna(axis=0, inplace=True)
            return self.k_data
        except:
            print('getData_Tushare except')
            return


########################################################################
# 功能测试
########################################################################
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ui = KLineWidget()
    ui.show()
    data = GetData()
    ui.setCrosshairInfo('贵州茅台', '30')
    ui.loadData(data.getData('600519.SH', '30'))
    ui.refreshAll()
    app.exec_()
