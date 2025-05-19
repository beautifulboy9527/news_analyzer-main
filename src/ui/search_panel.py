"""
搜索面板

实现搜索功能界面，包括搜索框和相关控件。
"""

import logging
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLineEdit,
                             QPushButton, QComboBox, QLabel) # Use PySide6
from PySide6.QtCore import Signal as pyqtSignal, Qt, Slot as pyqtSlot # Use PySide6, alias Signal/Slot
from PySide6.QtGui import QIcon # Use PySide6


class SearchPanel(QWidget):
    """搜索面板组件"""

    # 自定义信号：搜索请求 (传递包含查询文本、字段的字典)
    search_requested = pyqtSignal(dict)
    # 新增信号：当搜索被清除时发射
    search_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.logger = logging.getLogger('news_analyzer.ui.search_panel')

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 创建主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 5, 10, 5)

        # 第一行布局 - 搜索框和按钮
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)

        # 搜索标签
        search_label = QLabel("关键词搜索:")
        search_layout.addWidget(search_label)

        # 搜索输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入搜索关键词...")
        self.search_input.setObjectName("searchInput") # Add objectName
        self.search_input.returnPressed.connect(self._on_search)
        self.search_input.textChanged.connect(self._on_text_changed) # 连接 textChanged 信号 (修正缩进)
        search_layout.addWidget(self.search_input, 1)  # 搜索框占据主要空间

        # 搜索按钮
        self.search_button = QPushButton("搜索")
        self.search_button.setObjectName("searchButton") # Add objectName
        self.search_button.clicked.connect(self._on_search)
        search_layout.addWidget(self.search_button)

        # 高级搜索选项（可选）
        self.advanced_options = QComboBox()
        self.advanced_options.addItem("标题和内容")
        self.advanced_options.addItem("仅标题")
        self.advanced_options.addItem("仅内容")
        self.advanced_options.setObjectName("searchOptionsCombo") # Add objectName
        search_layout.addWidget(self.advanced_options)

        # 将搜索行添加到主布局
        self.main_layout.addLayout(search_layout)

        # 移除了日期筛选布局和滑块

    # 移除了 _update_date_range_label 方法

    def _on_search(self):
        """处理搜索请求"""
        query = self.search_input.text().strip()

        # 只在 query 不为空时发出搜索请求
        if query:
            # 如果有搜索词，正常发出搜索请求
            search_field = self.advanced_options.currentText()
            search_params = {
                "query": query,
                "field": search_field,
            }
            self.search_requested.emit(search_params)
            self.logger.debug(f"搜索请求: {search_params}")
        # else: # 空查询时不再触发清除，由 _on_text_changed 处理
        #     self.logger.debug("搜索框为空，未发出搜索请求。")

    @pyqtSlot(str) # 修正缩进
    def _on_text_changed(self, text: str): # 修正缩进
        """处理搜索框文本变化"""
        if not text.strip(): # 修正缩进
            # 如果文本变为空，发出清除信号
            self.search_cleared.emit() # 修正缩进
            self.logger.debug("搜索框文本已清空，发出清除请求") # 修正字符串和括号
