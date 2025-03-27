"""
分类侧边栏组件

实现左侧分类标签导航栏，用于按类别筛选新闻。
"""

import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QListWidget, 
                            QListWidgetItem)
from PyQt5.QtCore import pyqtSignal, Qt


class CategorySidebar(QWidget):
    """分类侧边栏组件"""
    
    # 自定义信号：分类被选中
    category_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.logger = logging.getLogger('news_analyzer.ui.sidebar')
        self.categories = set()
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        # 创建主布局
        layout = QVBoxLayout(self)
        
        # 标题标签
        title_label = QLabel("新闻分类")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)
        
        # 分类列表
        self.category_list = QListWidget()
        self.category_list.setAlternatingRowColors(True)
        self.category_list.itemClicked.connect(self._on_category_clicked)
        layout.addWidget(self.category_list)
        
        # 添加默认分类
        self.add_category("所有")
        
        # 设置默认选中项
        self.category_list.setCurrentRow(0)
    
    def add_category(self, category_name):
        """添加分类
        
        Args:
            category_name: 分类名称
        """
        if category_name in self.categories:
            return
        
        # 如果是新分类，则添加到列表
        self.categories.add(category_name)
        item = QListWidgetItem(category_name)
        self.category_list.addItem(item)
        
        self.logger.debug(f"添加分类: {category_name}")
    
    def _on_category_clicked(self, item):
        """处理分类点击事件
        
        Args:
            item: 被点击的列表项
        """
        category = item.text()
        self.category_selected.emit(category)
        self.logger.debug(f"选择分类: {category}")
