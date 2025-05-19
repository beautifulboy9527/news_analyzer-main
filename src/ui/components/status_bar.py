#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
状态栏组件

封装应用程序状态栏功能，包括：
- 状态消息显示
- 进度条显示
- 取消按钮（用于长时间操作）
- 与主窗口的信号通信
"""

import logging
from PyQt5.QtWidgets import QStatusBar, QLabel, QProgressBar, QPushButton, QWidget, QHBoxLayout
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QTimer, QEvent, QPoint, QSize, QRect # 确保导入 QSize, QRect

class StatusBar(QStatusBar):
    """
    自定义状态栏组件

    信号:
    - status_message_changed(str): 当状态消息改变时发出
    - cancel_requested(): 当取消按钮被点击时发出
    """
    status_message_changed = pyqtSignal(str)
    cancel_requested = pyqtSignal() # 添加取消信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('ui.components.status_bar')

        # 初始化UI组件
        self._init_ui()

        # 连接信号
        self.status_message_changed.connect(self._on_status_message_changed)

        self.logger.info("状态栏组件初始化完成")

    def _init_ui(self):
        """初始化状态栏UI"""
        # 状态标签
        self.status_label = QLabel("就绪")
        self.addWidget(self.status_label, 1)  # 让标签占据主要空间

        # 进度条 - 设置 self 为父控件
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMaximumSize(150, 15) # 调整大小
        self.progress_bar.setTextVisible(False) # 通常不需要显示百分比文本
        self.progress_bar.setVisible(False) # 初始隐藏

        # 取消按钮 - 设置 self 为父控件
        self.cancel_button = QPushButton("取消", self)
        self.cancel_button.setFlat(True) # 使按钮看起来更像状态栏的一部分
        self.cancel_button.setStyleSheet("padding: 0px 5px;") # 减小内边距
        self.cancel_button.clicked.connect(self.cancel_requested.emit) # 连接信号
        self.cancel_button.setVisible(False) # 初始隐藏
        # 调整按钮大小以适应内容
        self.cancel_button.adjustSize()

        # 不再使用 addPermanentWidget
        # self.addPermanentWidget(self.progress_bar)
        # self.addPermanentWidget(self.cancel_button)

        self.set_status_message("应用程序已就绪")

    @pyqtSlot(str)
    def _on_status_message_changed(self, message: str):
        """处理状态消息改变"""
        self.status_label.setText(message)
        self.logger.debug(f"状态消息更新: {message}")

    def set_status_message(self, message: str):
        """设置状态栏消息"""
        self.status_message_changed.emit(message)

    def show_progress_bar(self, current: int = 0, total: int = 100):
        """显示进度条和取消按钮，并设置初始值"""
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.progress_bar.setVisible(True)
        self.cancel_button.setVisible(True)
        self.logger.debug(f"显示进度条和取消按钮: {current}/{total}")
        # 初始显示时也需要调整位置
        self.adjust_widget_positions()

    def hide_progress_bar(self):
        """隐藏进度条和取消按钮"""
        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)
        self.logger.debug("隐藏进度条和取消按钮")

    def update_progress(self, current: int, total: int):
        """更新进度条状态"""
        if not self.progress_bar.isVisible():
            self.logger.debug(f"更新进度时进度条不可见，准备显示。 Current: {current}/{total}")
            self.show_progress_bar(current, total) # 如果容器不可见则显示它
        else: # 如果可见，确保位置正确
             self.adjust_widget_positions()
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def adjust_widget_positions(self):
        """计算并设置进度条和按钮的位置"""
        # 计算按钮位置 (最右侧)
        # 使用 sizeHint() 获取建议大小，如果按钮可见则使用实际大小
        button_size = self.cancel_button.size() if self.cancel_button.isVisible() else self.cancel_button.sizeHint()
        button_x = self.width() - button_size.width() - 5 # 5px 右边距
        button_y = (self.height() - button_size.height()) // 2 # 垂直居中
        self.cancel_button.move(button_x, button_y)

        # 计算进度条位置 (在按钮左侧)
        bar_max_width = self.progress_bar.maximumWidth()
        bar_height = self.progress_bar.maximumHeight()
        bar_x = button_x - bar_max_width - 5 # 5px 间距
        bar_y = (self.height() - bar_height) // 2 # 垂直居中
        # 设置固定大小和位置
        self.progress_bar.setGeometry(bar_x, bar_y, bar_max_width, bar_height)


    def resizeEvent(self, event: QEvent):
        """在状态栏大小改变时重新定位进度条和按钮"""
        super().resizeEvent(event) # 调用父类的实现
        self.adjust_widget_positions() # 调用调整位置的方法

    def event(self, event: QEvent) -> bool:
        """重写事件处理函数"""
        # 可以选择性地在这里处理特定事件，但 resizeEvent 通常足够
        return super().event(event)

if __name__ == '__main__':
    # 测试代码
    from PyQt5.QtWidgets import QApplication, QMainWindow
    import sys
    import time

    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)
    window = QMainWindow()

    # 创建状态栏
    status_bar = StatusBar()
    window.setStatusBar(status_bar)

    # 测试功能
    status_bar.set_status_message("测试状态消息")
    status_bar.show_progress_bar(0, 100)

    # 模拟进度更新
    def update():
        for i in range(101):
            status_bar.update_progress(i, 100)
            QApplication.processEvents() # 处理事件以更新UI
            time.sleep(0.05)
        status_bar.hide_progress_bar()
        status_bar.set_status_message("进度完成")

    # 连接取消信号
    def on_cancel():
        print("取消按钮被点击!")
        status_bar.set_status_message("操作已取消")
        # 在实际应用中，这里应该通知后台任务停止

    status_bar.cancel_requested.connect(on_cancel)

    # 使用 QTimer 延迟启动进度更新，以便窗口先显示
    QTimer.singleShot(1000, update)


    window.show()
    sys.exit(app.exec_())