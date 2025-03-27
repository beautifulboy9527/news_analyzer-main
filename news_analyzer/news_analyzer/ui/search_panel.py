"""
搜索面板

实现搜索功能界面，包括搜索框和相关控件。
"""

import logging
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QLineEdit, 
                            QPushButton, QComboBox, QLabel)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon


class SearchPanel(QWidget):
    """搜索面板组件"""
    
    # 自定义信号：搜索请求
    search_requested = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.logger = logging.getLogger('news_analyzer.ui.search_panel')
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        # 创建水平布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 搜索标签
        search_label = QLabel("关键词搜索:")
        layout.addWidget(search_label)
        
        # 搜索输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入搜索关键词...")
        self.search_input.returnPressed.connect(self._on_search)
        layout.addWidget(self.search_input, 1)  # 搜索框占据主要空间
        
        # 搜索按钮
        self.search_button = QPushButton("搜索")
        self.search_button.clicked.connect(self._on_search)
        layout.addWidget(self.search_button)
        
        # 高级搜索选项（可选）
        self.advanced_options = QComboBox()
        self.advanced_options.addItem("标题和内容")
        self.advanced_options.addItem("仅标题")
        self.advanced_options.addItem("仅内容")
        layout.addWidget(self.advanced_options)
    
    def _on_search(self):
        """处理搜索请求"""
        query = self.search_input.text().strip()
        self.search_requested.emit(query)
        self.logger.debug(f"搜索请求: {query}")
