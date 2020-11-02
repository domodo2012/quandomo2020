from PyQt5.Qt import QApplication, QWidget, QLabel
import sys

if __name__ == '__main__':
    # 创建QApplication类的实例
    app = QApplication(sys.argv)
    # 创建一个窗口
    window = QWidget()
    # 设置窗口标题
    window.setWindowTitle('Hello World!')
    # 设置窗口尺寸
    window.resize(400, 400)
    # 移动窗口位置
    window.move(1000, 300)
    # 创建label控件
    label = QLabel(window)
    # 为控件设置文本
    label.setText('Hello World!')
    # 移动空间的位置
    label.move(160, 160)
    # 显示窗口
    window.show()
    # 进入程序的主循环，并通过exit函数确保主循环安全结束
    sys.exit(app.exec_())
