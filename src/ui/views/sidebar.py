"""
分类侧边栏组件

实现左侧分类标签导航栏，用于按类别筛选新闻。
"""

import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QListWidget,
                             QListWidgetItem, QPushButton) # Use PySide6 - Added QPushButton
from PySide6.QtCore import Signal as pyqtSignal, Qt # Use PySide6, alias Signal
from PySide6.QtGui import QPalette, QColor # Use PySide6
# Adjusted import for collectors being one level up from src/ui/views/
from ...collectors.categories import STANDARD_CATEGORIES, get_category_name # Import get_category_name
from src.core.source_manager import SourceManager # Import for type hinting
from typing import List


class CategorySidebar(QWidget):
    """分类侧边栏组件"""

    # 自定义信号：分类被选中
    category_selected = pyqtSignal(str)
    # 自定义信号：更新按钮被点击
    update_news_requested = pyqtSignal()

    def __init__(self, source_manager: SourceManager, parent=None):
        """
        Initializes the CategorySidebar.

        Args:
            source_manager: The SourceManager instance.
            parent: The parent widget (optional).
        """
        super().__init__(parent) # Call QWidget constructor
        self.source_manager = source_manager # Store source manager
        self.setObjectName("Sidebar") # 添加 objectName

        self.logger = logging.getLogger('news_analyzer.ui.sidebar') # Keep logger name for now
        self.categories = set() # Store added category names (中文)
        self.update_news_button: QPushButton = None # Add button instance variable

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5) # Add some margins back
        layout.setSpacing(8) # Reset spacing

        # --- 更新新闻按钮 --- (Moved here)
        self.update_news_button = QPushButton("更新新闻")
        self.update_news_button.setToolTip("获取最新新闻 (F5)")
        self.update_news_button.setObjectName("update_news_button")
        # Connect the button's clicked signal to the sidebar's signal
        self.update_news_button.clicked.connect(self.update_news_requested)
        layout.addWidget(self.update_news_button) # Add button to the top

        # 分类列表
        self.category_list = QListWidget()
        self.category_list.setObjectName("sidebarList") # 设置 objectName
        self.category_list.setAlternatingRowColors(False) # 禁用交替行颜色
        self.category_list.itemClicked.connect(self._on_category_clicked)
        # --- 移除焦点虚线框 (样式移至 QSS) ---
         #self.category_list.setStyleSheet("QListWidget { outline: none; } QListWidget::item:selected { border: none; }")

        # --- 通过 Palette 设置深色背景 (如果需要，否则由主题QSS控制) ---
        # palette = self.category_list.palette()
        # palette.setColor(QPalette.Base, QColor("#1a1a1a")) # 列表背景
        # palette.setColor(QPalette.Highlight, QColor("#2c2c2c")) # 选中背景
        # self.category_list.setPalette(palette)
        # self.category_list.viewport().setAutoFillBackground(True) # 确保 viewport 使用 Palette 填充
        # --- Palette 设置结束 ---

        layout.addWidget(self.category_list)

        # Initial population using the passed source_manager
        # Ensure sources are loaded before calling update_categories if needed elsewhere
        # For now, assume source_manager is ready or call happens later
        if self.source_manager:
             all_sources = self.source_manager.get_sources()
             # Extract category IDs from all sources that have a category defined
             active_cat_ids = list(set(source.category for source in all_sources if source.category))
             self.logger.debug(f"Sidebar _init_ui: Extracted {len(active_cat_ids)} unique category IDs for initial population: {active_cat_ids}")
             self.update_categories(active_cat_ids)
        else:
             self.logger.warning("SourceManager not provided during init, categories might be empty initially.")
             self._populate_default_categories() # Populate with defaults if no manager

        # 设置默认选中项 (确保列表不为空)
        if self.category_list.count() > 0:
            # --- Block signals to prevent premature filtering --- 
            self.category_list.blockSignals(True)
            self.category_list.setCurrentRow(0)
            self.category_list.blockSignals(False)
            self.logger.debug("Set default sidebar selection to row 0 without emitting signal.")
            # --- End block signals ---

    def _populate_default_categories(self):
        """Populate with default '所有' and standard categories if source manager is unavailable."""
        self.logger.debug("Populating sidebar with default categories.")
        self.category_list.clear()
        self.categories.clear()
        self.add_category("所有")
        for category_id in STANDARD_CATEGORIES:
            self.add_category(STANDARD_CATEGORIES[category_id]["name"])


    def add_category(self, category_name):
        """添加分类 (使用中文名)

        Args:
            category_name: 分类名称 (中文)
        """
        if category_name in self.categories:
            self.logger.debug(f"分类 '{category_name}' 已存在，跳过添加。")
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
        self.category_selected.emit(category) # 发射中文分类名
        self.logger.debug(f"选择分类: {category}")

    def get_current_category(self):
        """获取当前选中的分类名称 (中文)"""
        current_item = self.category_list.currentItem()
        if current_item:
            return current_item.text()
        return "所有" # 默认返回 "所有"

    def update_categories(self, active_category_ids: List[str]):
        """根据活动的新闻源分类ID列表更新分类列表。
        "所有" 和 "未分类" 会被固定显示。

        Args:
            active_category_ids: 一个包含实际被新闻源使用的标准分类ID的列表。
        """
        self.logger.debug(f"Updating categories based on {len(active_category_ids)} active category IDs.")
        current_selection = self.get_current_category() # Store current selection (中文名)

        self.category_list.clear()
        self.categories.clear()

        # 1. 固定添加 "所有"
        self.add_category("所有")

        # 2. 添加活动的标准分类
        active_category_names = set()
        for cat_id in active_category_ids:
            if cat_id and cat_id != "uncategorized": # 确保 ID 有效且不是未分类ID
                category_name_zh = get_category_name(cat_id)
                if category_name_zh != "未分类": # 再次确认获取的名称不是"未分类"的字面量
                    active_category_names.add(category_name_zh)
        
        for name in sorted(list(active_category_names)):
            self.add_category(name)

        # 3. 固定添加 "未分类" (如果它不在已添加的活动分类中)
        uncategorized_name = get_category_name("uncategorized") # 通常是 "未分类"
        if uncategorized_name not in self.categories:
            self.add_category(uncategorized_name)

        # 尝试恢复之前的选中项，否则默认选中 "所有"
        self.category_list.blockSignals(True) # Block signals before setting item
        try:
            items = self.category_list.findItems(current_selection, Qt.MatchExactly)
            if items:
                self.category_list.setCurrentItem(items[0])
                self.logger.debug(f"Restored sidebar selection to: {current_selection}")
            elif self.category_list.count() > 0: # Ensure list is not empty before setting row
                self.category_list.setCurrentRow(0) # Default to "所有"
                self.logger.debug(f"Could not restore '{current_selection}', defaulted sidebar selection to row 0.")
        finally:
            self.category_list.blockSignals(False) # Unblock signals

        self.logger.info("Categories updated (Standard Chinese only).") 