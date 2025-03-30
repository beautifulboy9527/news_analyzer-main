"""
分类侧边栏组件

实现左侧分类标签导航栏，用于按类别筛选新闻。
"""

import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QListWidget,
                             QListWidgetItem) # Remove QPalette, QColor
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPalette, QColor # Import from QtGui
from news_analyzer.collectors.categories import STANDARD_CATEGORIES


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
        # title_label.setStyleSheet("font-weight: bold; font-size: 14px;") # 移除内联样式
        layout.addWidget(title_label)

        # 分类列表
        self.category_list = QListWidget()
        self.category_list.setObjectName("sidebarList") # 设置 objectName
        self.category_list.setAlternatingRowColors(False) # 禁用交替行颜色
        self.category_list.itemClicked.connect(self._on_category_clicked)
        # --- 移除焦点虚线框 ---
        self.category_list.setStyleSheet("QListWidget { outline: none; } QListWidget::item:selected { border: none; }")

        # --- 通过 Palette 设置深色背景 ---
        # from PyQt5.QtGui import QPalette, QColor # 已在文件顶部导入
        palette = self.category_list.palette()
        # 使用更符合优雅黑的颜色
        palette.setColor(QPalette.Base, QColor("#1a1a1a")) # 列表背景
        palette.setColor(QPalette.Text, QColor("#e8e8e8")) # 列表文字
        palette.setColor(QPalette.Highlight, QColor("#2c2c2c")) # 选中背景
        palette.setColor(QPalette.HighlightedText, QColor("#f5f5f5")) # 选中文字
        # 可以尝试设置交替行颜色
        # palette.setColor(QPalette.AlternateBase, QColor("#1e1e1e"))
        self.category_list.setPalette(palette)
        self.category_list.viewport().setAutoFillBackground(True) # 确保 viewport 使用 Palette 填充
        # --- Palette 设置结束 ---

        layout.addWidget(self.category_list)

        # 添加默认分类
        self.add_category("所有")
        
        # 添加标准分类
        for category_id in STANDARD_CATEGORIES:
            self.add_category(STANDARD_CATEGORIES[category_id]["name"])
        
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

    def get_current_category(self):
        """获取当前选中的分类名称"""
        current_item = self.category_list.currentItem()
        if current_item:
            return current_item.text()
        return "所有" # 默认返回 "所有"
