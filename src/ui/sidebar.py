"""
分类侧边栏组件

实现左侧分类标签导航栏，用于按类别筛选新闻。
"""

import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QListWidget,
                             QListWidgetItem)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPalette, QColor
from collectors.categories import STANDARD_CATEGORIES, get_category_name # Import get_category_name
from src.core.source_manager import SourceManager # Import for type hinting


class CategorySidebar(QWidget):
    """分类侧边栏组件"""

    # 自定义信号：分类被选中
    category_selected = pyqtSignal(str)

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

        self.logger = logging.getLogger('news_analyzer.ui.sidebar')
        self.categories = set() # Store added category names (中文)

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 0) # 调整边距，顶部留5px
        layout.setSpacing(5) # 减小控件间距

        # 标题标签 (已注释掉)
        # title_label = QLabel("新闻分类")
        # title_label.setStyleSheet("font-weight: bold; font-size: 14px;") # 移除内联样式
        # layout.addWidget(title_label)

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
             self.update_categories(self.source_manager.get_sources())
        else:
             self.logger.warning("SourceManager not provided during init, categories might be empty initially.")
             self._populate_default_categories() # Populate with defaults if no manager

        # 设置默认选中项 (确保列表不为空)
        if self.category_list.count() > 0:
            self.category_list.setCurrentRow(0)

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

    def update_categories(self, sources):
        """根据新闻源列表更新分类列表 (只显示标准中文分类)"""
        self.logger.debug(f"Updating categories based on {len(sources)} sources (Standard Chinese only).")
        current_selection = self.get_current_category() # Store current selection (中文名)

        # 清空现有分类（保留 '所有'）
        self.category_list.clear()
        self.categories.clear()
        self.add_category("所有") # 重新添加 "所有"

        # 添加标准分类 (中文名)
        for category_id in STANDARD_CATEGORIES:
            self.add_category(STANDARD_CATEGORIES[category_id]["name"])

        # --- 移除添加自定义分类的逻辑 ---
        # custom_categories = set()
        # for source in sources:
        #     # Check if the source category ID corresponds to a standard category
        #     # and if its Chinese name is not already added
        #     category_name_zh = get_category_name(source.category)
        #     if source.category and category_name_zh != "未分类" and category_name_zh not in self.categories:
        #          # We only care about standard categories now, so this check might be redundant
        #          # If we wanted to add *non-standard* categories from sources, the logic would be different
        #          pass # Do nothing, only standard categories are added above
        #     elif source.category and category_name_zh == "未分类":
        #          # Handle potential non-standard categories if needed in the future
        #          self.logger.debug(f"Source '{source.name}' has non-standard category ID: {source.category}")

        # for category_name in sorted(list(custom_categories)):
        #     # This loop is now effectively empty as we don't add to custom_categories
        #     self.add_category(category_name) # This would have added English IDs before
        # --- 移除结束 ---


        # 尝试恢复之前的选中项，否则默认选中 "所有"
        items = self.category_list.findItems(current_selection, Qt.MatchExactly)
        if items:
            self.category_list.setCurrentItem(items[0])
        elif self.category_list.count() > 0: # Ensure list is not empty before setting row
            self.category_list.setCurrentRow(0) # Default to "所有"

        self.logger.info("Categories updated (Standard Chinese only).")
