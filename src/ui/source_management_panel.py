#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
新闻源管理面板 UI 模块
"""

print("--- DIAGNOSTIC PRINT: src/ui/source_management_panel.py MODULE IS BEING LOADED ---") # +++ DIAGNOSTIC +++

from typing import List, Optional, Dict, TYPE_CHECKING # MODIFIED: Added TYPE_CHECKING

import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QPushButton, QLabel, QCheckBox,
                             QMessageBox, QDialog, QLineEdit, QFormLayout,
                             QSpacerItem, QSizePolicy, QDialogButtonBox, QTabWidget, # Use PySide6
                             QTextEdit, QAbstractItemView, QFileDialog, QStatusBar, QApplication, # Added QApplication
                             QStyle # Import QStyle for standard icons
                             ) # Use PySide6
from PySide6.QtCore import Qt, Signal as pyqtSignal, Slot as pyqtSlot # Use PySide6, alias Signal
from PySide6.QtGui import QIcon, QAction, QColor, QPalette # Use PySide6, Import QColor, QPalette

# Conditional import for type hinting to prevent circular imports
if TYPE_CHECKING:
    from src.core.app_service import AppService
    from src.models import NewsSource
    from src.ui.theme_manager import ThemeManager

# 假设 AppService 和 NewsSource 模型可以通过某种方式访问
from datetime import datetime # 导入 datetime 用于时间格式化
from src.core.app_service import AppService # 导入 AppService
from src.models import NewsSource # 恢复原始导入路径
from .ui_utils import create_standard_button, create_title_label, add_form_row, setup_list_widget # <-- 添加导入
from src.utils.date_utils import format_datetime_friendly # Import the friendly date formatter
from src.core.news_update_service import NewsUpdateService # ADDED FOR TYPE HINTING

# --- Constants for status text ---\nSOURCE_STATUS_CHECKING = "检查中..." # 新增
SOURCE_STATUS_UNCHECKED = "未检查"
SOURCE_STATUS_OK = "ok" # MODIFIED from "正常"
SOURCE_STATUS_ERROR = "error" # MODIFIED from "错误"

class AddRssDialog(QDialog):
    """添加 RSS 新闻源对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加 RSS 新闻源")
        self.setMinimumWidth(400)
        layout = QFormLayout(self)
        self.url_input = QLineEdit()
        layout.addRow("RSS URL:", self.url_input)
        self.name_input = QLineEdit()
        layout.addRow("名称 (可选):", self.name_input)
        self.category_input = QLineEdit()
        layout.addRow("分类:", self.category_input)
        button_layout = QHBoxLayout()
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        self.add_button = QPushButton("添加")
        self.add_button.setDefault(True)
        self.add_button.clicked.connect(self.accept)
        button_layout.addWidget(self.add_button)
        layout.addRow("", button_layout)

    def get_values(self):
        return {
            'url': self.url_input.text().strip(),
            'name': self.name_input.text().strip(),
            'category': self.category_input.text().strip() or "未分类"
        }


class EditSourceDialog(QDialog):
    """编辑 RSS 新闻源对话框"""
    def __init__(self, source: NewsSource, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"编辑新闻源: {source.name}")
        self.setMinimumWidth(450) # 稍微加宽以容纳更多字段
        self.source = source # 保存源对象引用
        self.source_name_to_edit = source.name # 保存原始名称，用于更新

        layout = QFormLayout(self)

        # URL (仅对 RSS 源显示和编辑)
        self.url_input = None # 初始化为 None
        if source.type == 'rss':
            self.url_input = QLineEdit(source.url or "") # 改为 QLineEdit
            layout.addRow("RSS URL:", self.url_input)
        # 对于非 RSS 源，不显示 URL 行

        # 名称输入 (允许编辑)
        self.name_input = QLineEdit(source.name)
        layout.addRow("名称:", self.name_input)

        # 分类输入 (允许编辑)
        self.category_input = QLineEdit(source.category)
        layout.addRow("分类:", self.category_input)

        # 备注输入 (允许编辑) - 使用 QTextEdit 以支持多行
        self.notes_input = QTextEdit(source.notes or "")
        self.notes_input.setPlaceholderText("输入备注信息...")
        self.notes_input.setFixedHeight(80)
        layout.addRow("备注:", self.notes_input)

        # --- 澎湃新闻 CSS 选择器编辑 ---
        self.selector_inputs = {} # 用于存储选择器输入框
        if source.type == 'pengpai':
            self.add_pengpai_selector_fields(layout, source.custom_config or {})

        # --- 按钮布局 ---

        # 按钮布局
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # --- 手动设置按钮文本为中文 ---
        ok_button = button_box.button(QDialogButtonBox.Ok)
        if ok_button:
            ok_button.setText("确定")
        cancel_button = button_box.button(QDialogButtonBox.Cancel)
        if cancel_button:
            cancel_button.setText("取消")
        # --- 中文按钮文本设置结束 ---

        layout.addRow(button_box)

    def add_pengpai_selector_fields(self, layout: QFormLayout, current_selectors: dict):
        """为澎湃新闻源添加 CSS 选择器编辑字段"""
        # 定义需要配置的选择器及其标签 (区分列表页和详情页)
        selector_definitions = {
            # --- 列表页选择器 ---
            'news_list_selector': "列表 - 新闻项:",
            'title_selector': "列表 - 标题:",
            'link_selector': "列表 - 链接:",
            'summary_selector': "列表 - 摘要:",
            # --- 详情页选择器 ---
            'content_selector': "详情 - 正文容器:",
            'author_selector': "详情 - 作者:",
            'time_selector': "详情/列表 - 时间:", # 时间可能在列表或详情页
        }

        # 创建标签和输入框
        # --- 添加带帮助按钮的标签 ---
        selector_group_layout = QHBoxLayout()
        selector_group_label = QLabel("澎湃新闻 CSS 选择器:")
        selector_group_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        selector_group_layout.addWidget(selector_group_label)
        help_button = QPushButton("?")
        help_button.setFixedSize(20, 20)
        help_button.setToolTip("点击查看 CSS 选择器帮助信息")
        help_button.clicked.connect(self._show_selector_help)
        selector_group_layout.addWidget(help_button)
        selector_group_layout.addStretch() # 将按钮推到右侧（如果需要）
        layout.addRow(selector_group_layout) # 使用布局作为标签行

        for key, label in selector_definitions.items():
            input_widget = QLineEdit(current_selectors.get(key, "")) # 从当前配置或空字符串获取值
            # 更新工具提示以反映新标签和用途
            if key == 'news_list_selector':
                input_widget.setToolTip("【列表页】定位包含单条新闻信息的 HTML 块的选择器。\n示例: div.news_item")
            elif key == 'title_selector':
                input_widget.setToolTip("【列表页】在'新闻项'内部，定位标题元素的选择器。\n示例: h2 a")
            elif key == 'link_selector':
                input_widget.setToolTip("【列表页】在'新闻项'内部，定位链接<a>标签并提取href属性的选择器。\n示例: a::attr(href)")
            elif key == 'summary_selector':
                input_widget.setToolTip("【列表页】【可选】在'新闻项'内部，定位摘要元素的选择器。\n示例: p.summary")
            elif key == 'content_selector':
                input_widget.setToolTip("【详情页】定位包含新闻正文主要内容的容器元素的选择器。\n示例: div.article-content")
            elif key == 'author_selector':
                input_widget.setToolTip("【详情页】【可选】定位包含作者信息的元素的选择器。\n示例: span.author")
            elif key == 'time_selector':
                input_widget.setToolTip("【详情页/列表页】【可选】定位包含发布时间的元素的选择器。\n示例: span.publish-time")
            # --- 添加 Placeholder Text ---
            input_widget.setPlaceholderText("留空将使用内置默认值")
            # --- Placeholder Text 结束 ---

            layout.addRow(label, input_widget)
            self.selector_inputs[key] = input_widget # 存储输入框引用

    def get_values(self):
        """获取对话框修改后的值"""
        values = {
            'name': self.name_input.text().strip(),
            'category': self.category_input.text().strip() or "未分类",
            'notes': self.notes_input.toPlainText().strip()
        }
        # 如果是 RSS 源，包含 URL
        if self.url_input is not None:
            values['url'] = self.url_input.text().strip()

        # 如果是澎湃新闻源，包含 CSS 选择器配置
        if self.source.type == 'pengpai':
            selector_config = {}
            for key, input_widget in self.selector_inputs.items():
                selector_config[key] = input_widget.text().strip()
            values['custom_config'] = selector_config # MODIFIED: 'selector_config' -> 'custom_config'

        return values

    def _show_selector_help(self):
        """显示 CSS 选择器帮助信息"""
        help_text = """
        <h2>澎湃新闻 CSS 选择器帮助</h2>
        <p>这些选择器用于告诉程序如何在澎湃新闻网站上找到需要的信息。您需要使用浏览器的开发者工具来获取它们。</p>
        <p><b>基本步骤:</b></p>
        <ol>
            <li>在澎湃新闻网站上，右键点击您想提取的信息（如标题、正文区域）。</li>
            <li>选择"检查"或"Inspect Element"。</li>
            <li>在弹出的开发者工具中，找到对应的 HTML 代码。</li>
            <li>右键点击该 HTML 代码，选择"复制" -> "复制选择器"(Copy -> Copy Selector)。</li>
            <li>将复制的选择器粘贴到下面的输入框中。<b>注意：</b>有时需要手动简化或调整选择器。</li>
        </ol>
        <hr>
        <p><b>选择器详解:</b></p>
        <ul>
            <li><b>列表 - 新闻项:</b> (必需) 在新闻列表页（如首页、频道页）上，框选单条新闻信息的那个 HTML 块。后续的"列表-"选择器都在这个块内部查找。</li>
            <li><b>列表 - 标题:</b> (必需) 在"新闻项"内部，定位新闻标题。</li>
            <li><b>列表 - 链接:</b> (必需) 在"新闻项"内部，定位指向详情页的链接 (a 标签)，并提取其 'href' 属性 (通常以 <code>::attr(href)</code> 结尾)。</li>
            <li><b>列表 - 摘要:</b> (可选) 在"新闻项"内部，定位新闻摘要。</li>
            <li><b>详情 - 正文容器:</b> (必需) 在新闻详情页上，定位包含<b>主要正文内容</b>的那个 HTML 容器 (通常是 div 或 article)。</li>
            <li><b>详情 - 作者:</b> (可选) 在新闻详情页上，定位包含作者名字的元素。</li>
            <li><b>详情/列表 - 时间:</b> (可选) 在新闻详情页或列表页的"新闻项"内部，定位包含发布时间的元素。</li>
        </ul>
        <p><b>重要提示:</b> 澎湃新闻网站结构可能会变化，导致选择器失效。如果采集失败，请尝试使用开发者工具重新获取并更新这些选择器。</p>
        """
        QMessageBox.information(self, "CSS 选择器帮助", help_text)


    def get_original_name(self):
        """获取要编辑的源的原始名称"""
        return self.source_name_to_edit


# --- 修改基类为 QDialog ---
class SourceManagementPanel(QDialog):
    """新闻源管理对话框"""

    # 定义信号，用于通知 AppService 进行操作
    # (或者直接调用 AppService 的方法，取决于设计选择)
    # add_source_requested = pyqtSignal(NewsSource)
    # remove_source_requested = pyqtSignal(str)
    # update_source_requested = pyqtSignal(str, dict)

    # 添加状态消息信号
    status_message = pyqtSignal(str)

    def __init__(self,
                 app_service: 'AppService', # MODIFIED: String type hint
                 theme_manager: 'ThemeManager', # MODIFIED: String type hint
                 parent: Optional[QWidget] = None):
        print("--- DIAGNOSTIC PRINT: SourceManagementPanel __init__ IS BEING CALLED ---") # +++ DIAGNOSTIC +++
        super().__init__(parent)
        self.app_service = app_service
        self.news_update_service = self.app_service.news_update_service
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle("新闻源管理")
        self.setMinimumSize(800, 600)

        self._rss_list_widget: Optional[QListWidget] = None
        self._crawler_list_widget: Optional[QListWidget] = None
        self.tab_widget: Optional[QTabWidget] = None
        self.refresh_button: Optional[QPushButton] = None # Ensure declaration before _init_ui
        self.add_rss_button: Optional[QPushButton] = None
        self.edit_source_button: Optional[QPushButton] = None
        self.remove_source_button: Optional[QPushButton] = None
        self.export_opml_button: Optional[QPushButton] = None
        self.import_opml_button: Optional[QPushButton] = None  

        self.theme_manager = theme_manager

        self._init_ui() # self.refresh_button and others are assigned here
        self._connect_signals()
        self.update_sources()

        self._checking_source_ids = set() 
        self._is_batch_checking = False   
        
        if self.refresh_button: # Check if it was successfully created in _init_ui
            self.refresh_button.setObjectName("refreshStatusButton")

    def _init_ui(self):
        """初始化面板 UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 使用辅助函数创建标题
        title_label = create_title_label("新闻源管理")
        main_layout.addWidget(title_label)

        # --- 创建 TabWidget ---
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget, 1) # 占据主要空间

        # --- RSS 订阅源标签页 ---
        rss_tab = QWidget()
        rss_layout = QVBoxLayout(rss_tab)
        rss_layout.setContentsMargins(0, 5, 0, 0) # 移除顶部边距，由 TabWidget 处理
        self.rss_list_widget = QListWidget()
        # 使用辅助函数配置列表
        setup_list_widget(
            self.rss_list_widget,
            object_name="rssSourceList",
            selection_mode=QAbstractItemView.ExtendedSelection
        )
        rss_layout.addWidget(self.rss_list_widget)
        self.tab_widget.addTab(rss_tab, "RSS 订阅源")

        # --- 网页爬虫标签页 ---
        crawler_tab = QWidget()
        crawler_layout = QVBoxLayout(crawler_tab)
        crawler_layout.setContentsMargins(0, 5, 0, 0)
        self.crawler_list_widget = QListWidget()
        # 使用辅助函数配置列表
        setup_list_widget(
            self.crawler_list_widget,
            object_name="crawlerSourceList",
            selection_mode=QAbstractItemView.ExtendedSelection
        )
        crawler_layout.addWidget(self.crawler_list_widget)
        self.tab_widget.addTab(crawler_tab, "网页爬虫")

        # --- 按钮行 ---
        button_layout = QHBoxLayout()
        # 将按钮行放在 TabWidget 下方
        main_layout.addLayout(button_layout)

        # --- 使用辅助函数创建按钮 ---
        self.add_rss_button = create_standard_button(
            text="添加 RSS 源",
            # icon_path=":/icons/add.png", # 示例图标路径
            tooltip="添加一个新的 RSS 订阅源"
        )
        button_layout.addWidget(self.add_rss_button)

        self.edit_source_button = create_standard_button(
            text="编辑选中源",
            # icon_path=":/icons/edit.png",
            tooltip="编辑当前选中的新闻源"
        )
        self.edit_source_button.setEnabled(False) # 初始禁用
        button_layout.addWidget(self.edit_source_button)

        self.remove_source_button = create_standard_button(
            text="删除选中",
            # icon_path=":/icons/remove.png",
            tooltip="删除选中的一个或多个新闻源"
        )
        self.remove_source_button.setEnabled(False) # 初始禁用
        button_layout.addWidget(self.remove_source_button)
        
        button_layout.addStretch(1) # 添加弹性空间

        # --- 添加导入/导出 OPML 按钮 ---
        self.import_opml_button = create_standard_button(
            text="导入 OPML",
            tooltip="从 OPML 文件导入新闻源"
            # icon_name="document-open" # 如果 ui_utils 支持图标名称
        )
        button_layout.addWidget(self.import_opml_button)

        self.export_opml_button = create_standard_button(
            text="导出 OPML",
            tooltip="将所有新闻源导出到 OPML 文件"
            # icon_name="document-save" # 如果 ui_utils 支持图标名称
        )
        button_layout.addWidget(self.export_opml_button)
        
        button_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)) # 缩小间隔

        # --- 添加刷新状态按钮 ---
        self.refresh_button = QPushButton("刷新状态")
        self.refresh_button.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        button_layout.addWidget(self.refresh_button)
        button_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)) # 再添加一个间隔

        # 添加状态栏
        self.status_bar = QStatusBar(self)
        main_layout.addWidget(self.status_bar)


    def _connect_signals(self):
        """连接内部信号和槽"""
        if self.add_rss_button:
            self.add_rss_button.clicked.connect(self._show_add_rss_dialog)
        if self.edit_source_button:
            self.edit_source_button.clicked.connect(self._show_edit_source_dialog)
        if self.remove_source_button:
            self.remove_source_button.clicked.connect(self._remove_selected_source)
        if self.refresh_button: 
            self.refresh_button.clicked.connect(self._refresh_source_status)

        # Connect to AppService signals
        self.app_service.sources_updated.connect(self.update_sources) 
        self.app_service.source_fetch_failed.connect(self._on_source_fetch_error)
        # Connect to the new signal for single item UI updates
        self.app_service.single_source_gui_update.connect(self._on_single_source_check_complete)

        # Connect to NewsUpdateService signals for status check lifecycle (button state)
        if self.news_update_service:
            self.logger.info("Connecting to NewsUpdateService status check signals for button state management.")
            self.news_update_service.status_check_started.connect(self._on_status_check_started)
            self.news_update_service.status_check_finished.connect(self._on_status_check_finished)
            # Connection for source_status_checked will be handled in the next step for item updates
            self.logger.info("Successfully connected status_check_started and status_check_finished signals.")
        else:
            self.logger.error("NewsUpdateService instance is None, cannot connect status check signals for button state.")

        # 连接两个列表的 itemSelectionChanged 信号
        self.rss_list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.crawler_list_widget.itemSelectionChanged.connect(self._on_selection_changed)

        # 连接 TabWidget 的 currentChanged 信号
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # 连接状态消息信号到状态栏
        self.status_message.connect(self.status_bar.showMessage)

    def _on_tab_changed(self, index):
        """处理标签页切换事件"""
        is_rss_tab = (index == 0) # 假设 RSS 是第一个标签页 (index 0)
        is_crawler_tab = (index == 1) # 假设爬虫是第二个标签页 (index 1)

        # 控制按钮可见性/状态
        self.add_rss_button.setVisible(is_rss_tab)
        # 未来可以添加 "添加爬虫" 按钮
        # self.add_crawler_button.setVisible(is_crawler_tab)

        # 清除非当前标签页列表的选中状态
        if is_rss_tab:
            self.crawler_list_widget.clearSelection()
        elif is_crawler_tab:
            self.rss_list_widget.clearSelection()

        # 更新按钮启用状态
        self._on_selection_changed()
        self.logger.debug(f"Tab changed to index {index} ({'RSS' if is_rss_tab else 'Crawler'})")

    def update_sources(self): # 移除 sources 参数
        """从 AppService 获取最新数据并更新列表显示"""
        self.logger.info(">>> SourceManagementPanel.update_sources STARTING...") # ADDED LOG
        active_list = self._get_current_active_list()
        # 记录当前选中的项，尝试在刷新后恢复
        selected_source_name = None

        if not self.app_service:
             self.logger.warning("AppService 不可用，无法更新新闻源列表")
             # 清空两个列表并显示错误
             self.rss_list_widget.clear()
             self.crawler_list_widget.clear()
             self.rss_list_widget.addItem("错误：应用程序服务不可用")
             self.crawler_list_widget.addItem("错误：应用程序服务不可用")
             return

        sources = self.app_service.get_sources() # 从 AppService 获取数据
        self.logger.info(f"更新新闻源列表，共 {len(sources)} 个源")

        # 清空两个列表
        self.rss_list_widget.clear()
        self.crawler_list_widget.clear()

        rss_count = 0
        crawler_count = 0

        if not sources:
            # 可以在两个标签页都显示提示
            self.rss_list_widget.addItem("没有配置的 RSS 源")
            self.crawler_list_widget.addItem("没有配置的爬虫源")
            # 确保在没有源时也更新按钮状态
            self._on_selection_changed() # 更新按钮状态
            self._on_tab_changed(self.tab_widget.currentIndex()) # 根据当前标签页调整按钮可见性
            return

        for source in sources:
            item_widget = self._create_source_item_widget(source)
            list_item = QListWidgetItem() # 创建空的 QListWidgetItem
            list_item.setSizeHint(item_widget.sizeHint())
            list_item.setData(Qt.UserRole, source) # 存储 NewsSource 对象

            # 根据类型添加到对应的列表
            if source.type == 'rss':
                self.rss_list_widget.addItem(list_item)
                self.rss_list_widget.setItemWidget(list_item, item_widget)
                rss_count += 1
            elif source.type in ['pengpai', 'crawler']: # 接受 'crawler' 类型
                self.crawler_list_widget.addItem(list_item)
                self.crawler_list_widget.setItemWidget(list_item, item_widget)
                crawler_count += 1
            else:
                 self.logger.warning(f"未知的源类型 '{source.type}' for source '{source.name}'，未添加到列表。")

        self.logger.info(f"填充完成：RSS 源 {rss_count} 个，爬虫源 {crawler_count} 个。")
        self.tab_widget.setTabText(0, f"RSS 源 ({rss_count})")
        self.tab_widget.setTabText(1, f"爬虫源 ({crawler_count})")

        # 刷新完成后，更新按钮状态
        self._on_selection_changed()
        self.logger.info("<<< SourceManagementPanel.update_sources FINISHED.") # ADDED LOG

    def _create_source_item_widget(self, source: NewsSource) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 4) # 调整边距
        layout.setSpacing(8) # 设置元素间距

        # 1. 复选框 (启用/禁用)
        enabled_checkbox = QCheckBox()
        enabled_checkbox.setObjectName("enabled_checkbox") # Set object name
        enabled_checkbox.setChecked(source.enabled)
        enabled_checkbox.setToolTip("启用/禁用此源")
        enabled_checkbox.stateChanged.connect(
            lambda state, s=source: self._toggle_source_enabled(s, state == Qt.Checked)
        )
        layout.addWidget(enabled_checkbox)

        # 2. 状态指示器 (图标)
        status_indicator_label = QLabel()
        status_indicator_label.setObjectName("status_indicator_label")
        status_indicator_label.setFixedSize(18, 18) # 稍微大一点以便图标清晰
        layout.addWidget(status_indicator_label)

        # 3. 源名称
        name_label = QLabel(source.name)
        name_label.setObjectName("name_label")
        name_label.setStyleSheet("font-weight: bold;") # 加粗显示
        layout.addWidget(name_label, 1) # 名称占据主要空间

        # 4. 简化状态文本
        status_text_label = QLabel()
        status_text_label.setObjectName("status_text_label")
        layout.addWidget(status_text_label)

        layout.addStretch(1) # 添加弹性空间将后续元素推到右侧

        # 5. 上次检查时间
        time_label = QLabel()
        time_label.setObjectName("time_label")
        time_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(time_label)

        # --- 初始化 UI 元素状态 --- 
        self._update_widget_status(widget, source) # 使用新的辅助函数初始化

        widget.setLayout(layout)
        return widget

    def _show_add_rss_dialog(self):
        """显示添加 RSS 源对话框"""
        if not self.app_service:
            QMessageBox.warning(self, "错误", "应用程序服务不可用")
            return

        dialog = AddRssDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            values = dialog.get_values()
            # 检查 URL 是否为空
            if not values['url']:
                QMessageBox.warning(self, "输入错误", "请输入有效的 RSS URL")
                return
            # 检查名称是否为空，如果为空则尝试从 URL 生成
            if not values['name']:
                 try:
                      # 尝试从 URL 提取域名作为名称
                      from urllib.parse import urlparse
                      parsed_url = urlparse(values['url'])
                      if parsed_url.netloc:
                           values['name'] = parsed_url.netloc
                      else: # 如果无法解析域名，使用部分 URL
                           values['name'] = values['url'].split("//")[-1].split("/")[0]
                 except Exception:
                      values['name'] = "未命名 RSS 源" # 兜底名称

            new_source = NewsSource(
                name=values['name'],
                type='rss',
                url=values['url'],
                category=values['category'],
                enabled=True,
                is_user_added=True
            )
            try:
                self.app_service.add_source(new_source)
                # AppService 会发出 sources_updated 信号，自动更新列表
            except Exception as e:
                QMessageBox.warning(self, "添加失败", f"无法添加 RSS 源: {e}")


    def _show_edit_source_dialog(self):
        """显示编辑选中新闻源的对话框"""
        active_list = self._get_current_active_list()
        current_item = active_list.currentItem() if active_list else None
        if not current_item or not self.app_service:
            return

        source: NewsSource = current_item.data(Qt.UserRole)
        if not source:
            return

        # --- 移除阻止编辑非用户添加 RSS 源的检查 ---
        # if not (source.type == 'rss' and source.is_user_added):
        #     QMessageBox.warning(self, "无法编辑", "只能编辑用户添加的 RSS 新闻源。")
        #     return
        # --- 检查移除结束 ---

        dialog = EditSourceDialog(source, self)
        if dialog.exec_() == QDialog.Accepted:
            updated_values = dialog.get_values()
            original_name = dialog.get_original_name()

            # 检查名称是否为空
            # 添加检查：确保 updated_values 不是 None
            if updated_values is None:
                self.logger.error("EditSourceDialog.get_values() 在对话框接受后意外返回 None。")
                QMessageBox.critical(self, "内部错误", "编辑对话框未能返回有效值，无法更新。")
                return # 安全退出


            if not updated_values['name']:
                QMessageBox.warning(self, "输入错误", "新闻源名称不能为空。")
                return

            # 如果是 RSS 源，检查 URL 是否为空
            if source.type == 'rss' and 'url' in updated_values and not updated_values['url']:
                 QMessageBox.warning(self, "输入错误", "RSS URL 不能为空。")
                 return

            try:
                self.logger.info(f"UI 请求: 更新新闻源 '{original_name}' 的信息为: {updated_values}")
                self.app_service.update_source(original_name, updated_values)
                # AppService 会发出 sources_updated 信号，自动更新列表
                self.logger.info(f"已调用 AppService.update_source 更新 '{original_name}'")
            except Exception as e:
                self.logger.error(f"更新新闻源 '{original_name}' 失败: {e}", exc_info=True)
                QMessageBox.warning(self, "更新失败", f"无法更新新闻源 '{original_name}': {e}")

            # --- 移除错误的代码块 (这部分属于添加逻辑) ---

    def _remove_selected_source(self):
        """移除当前选中的一个或多个新闻源"""
        active_list = self._get_current_active_list()
        selected_items = active_list.selectedItems() if active_list else []
        if not selected_items or not self.app_service:
            return

        sources_to_remove = []
        source_names_to_remove = []
        for item in selected_items:
            source: NewsSource = item.data(Qt.UserRole)
            if source:
                sources_to_remove.append(source)
                source_names_to_remove.append(source.name)

        if not sources_to_remove:
            return

        # 构建确认消息
        count = len(sources_to_remove)
        if count == 1:
            message = f"确定要删除新闻源 '{sources_to_remove[0].name}' 吗?"
        else:
            message = f"确定要删除选中的 {count} 个新闻源吗?\n\n" + "\n".join([f"- {name}" for name in source_names_to_remove[:5]]) # 最多显示前5个名称
            if count > 5:
                message += "\n- ..."

        reply = QMessageBox.question(self, '确认删除',
                                     message,
                                     QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.No)
        if reply == QMessageBox.Yes:
            errors = []
            for source_name in source_names_to_remove:
                try:
                    self.app_service.remove_source(source_name)
                    # AppService 会发出 sources_updated 信号，自动更新列表 (每次删除都会触发，可能有点低效，但简单)
                except Exception as e:
                    self.logger.error(f"删除新闻源 '{source_name}' 时出错: {e}", exc_info=True)
                    errors.append(f"'{source_name}': {e}")

            if errors:
                 QMessageBox.warning(self, "部分删除失败", f"以下新闻源删除失败:\n" + "\n".join(errors))

    def _toggle_source_enabled(self, source: NewsSource, enabled: bool):
        """切换新闻源的启用/禁用状态，并更新 UI。"""
        if not self.app_service:
            self.logger.warning("尝试切换源状态但 AppService 不可用")
            return
        self.logger.info(f"UI 请求: 切换新闻源 '{source.name}' 启用状态为: {enabled}")
        try:
            # 更新数据库和内存
            self.app_service.source_manager.update_source(source.name, {'enabled': enabled}, emit_signal=False) # 禁用 SourceManager 的信号发射
            # 手动更新内存中的对象 (如果 update_source 不更新内存)
            source.enabled = enabled
            
            # --- 手动更新 UI --- 
            list_widget = self.rss_list_widget if source.type == 'rss' else self.crawler_list_widget
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item and item.data(Qt.UserRole) == source:
                    widget = list_widget.itemWidget(item)
                    if widget:
                        checkbox = widget.findChild(QCheckBox, "enabled_checkbox")
                        if checkbox:
                            checkbox.setChecked(enabled) # 更新复选框状态
                        self._update_widget_status(widget, source) # 更新整个 widget 显示
                        QApplication.processEvents()
                        break
            # --- UI 更新结束 --- 
            
            self.logger.info(f"已更新 '{source.name}' 的启用状态为 {enabled} (数据库+内存+UI)。")
            # 不需要 AppService 发射 sources_updated，因为我们手动更新了 UI
            # 也许需要发射一个特定信号？或者依赖 selection changed？
            self._on_selection_changed() # 更新按钮状态可能受启用状态影响
        except Exception as e:
             QMessageBox.warning(self, "更新失败", f"无法更新新闻源 '{source.name}' 状态: {e}")
             # TODO: 恢复复选框和 widget 状态？


    def _get_current_active_list(self) -> QListWidget:
        """获取当前激活的标签页对应的列表控件"""
        current_index = self.tab_widget.currentIndex()
        if current_index == 0:
            return self.rss_list_widget
        elif current_index == 1:
            return self.crawler_list_widget
        else:
            # 理论上不应发生，但返回一个默认值或引发错误
            self.logger.error(f"未知的标签页索引: {current_index}")
            return self.rss_list_widget # 或者返回 None

    def _on_selection_changed(self):
        """当任一列表选中项改变时调用"""
        active_list = self._get_current_active_list()
        selected_items = active_list.selectedItems() if active_list else []

        can_remove = bool(selected_items)
        can_edit = False

        # 编辑按钮逻辑：只有当选中了 *单个* 源时才启用
        if len(selected_items) == 1:
            source: NewsSource = selected_items[0].data(Qt.UserRole)
            can_edit = True # 允许编辑任何单个选中的源

        self.remove_source_button.setEnabled(can_remove) # 根据是否有选中项启用删除按钮
        self.edit_source_button.setEnabled(can_edit) # 根据是否选中单个项启用编辑按钮

    def _update_widget_status(self, widget: QWidget, source: NewsSource):
        """根据 NewsSource 对象的当前状态更新对应 QWidget 的显示元素。"""
        if not widget:
            return

        self.logger.debug(f"_update_widget_status for '{source.name}': "
                         f"Initial source.status='{source.status}', "
                         f"source.last_checked_time='{source.last_checked_time}', "
                         f"source.last_error='{source.last_error}', "
                         f"source.enabled='{source.enabled}'")

        status_indicator = widget.findChild(QLabel, "status_indicator_label")
        status_text_label = widget.findChild(QLabel, "status_text_label")
        time_label = widget.findChild(QLabel, "time_label")
        name_label = widget.findChild(QLabel, "name_label") # 获取名称标签用于设置 ToolTip

        if not (status_indicator and status_text_label and time_label and name_label):
            self.logger.warning(f"无法找到源 '{source.name}' Widget 中的所有必要子控件。")
            return

        icon = None
        status_text = ""

        # --- Temporary color definitions based on theme name ---
        current_theme_name = self.theme_manager.get_current_theme()
        if current_theme_name == "dark":
            TEXT_COLOR = "white"
            SUCCESS_COLOR = "lightgreen"
            ERROR_COLOR = "salmon"
            WARNING_COLOR = "orange"
        else: # Default to light theme colors
            TEXT_COLOR = "black"
            SUCCESS_COLOR = "green"
            ERROR_COLOR = "red"
            WARNING_COLOR = "darkorange"
        # --- End of temporary color definitions ---

        status_color = TEXT_COLOR # Default color

        if source.status == 'ok':
            status_text = "状态正常"
            status_color = SUCCESS_COLOR
        elif source.status == 'error':
            status_text = "失败"
            # MODIFIED: Only show error count for RSS sources
            if source.type == 'rss':
                 if source.consecutive_error_count and source.consecutive_error_count > 0:
                    status_text += f"({source.consecutive_error_count}次)"
            status_color = ERROR_COLOR
        elif source.status == 'checking':
            status_text = "检查中..."
            status_color = WARNING_COLOR
        elif source.status == 'checking_individual': # This is the temporary status set by the panel
            icon = self.style().standardIcon(QStyle.SP_ArrowRight) # Running icon (or a specific pending icon)
            status_text = "检查中..."
            status_color = "darkorange" # Use a distinct color for "queued for check"
        elif source.status == 'unknown': # +++ ADDED explicit check for 'unknown' +++
            icon = self.style().standardIcon(QStyle.SP_DialogHelpButton) # 未知/帮助图标
            status_text = "未知" # +++ Set text to "未知" +++
            status_color = "gray"
            self.logger.warning(f"Source '{source.name}' has an unexpected status '{source.status}' with last_checked_time. Displaying as '{status_text}'.")
        else: # 处理其他任何意外的 status 值 (e.g. 'unchecked' if it somehow still appears)
            icon = self.style().standardIcon(QStyle.SP_DialogHelpButton) # <--- Use SP_DialogHelpButton instead
            status_text = f"状态: {source.status if source.status else '异常值'}" # 显示原始状态或标记为异常
            status_color = "purple" # 使用紫色等特殊颜色标记
            self.logger.warning(f"Source '{source.name}' has an unexpected status '{source.status}' with last_checked_time. Displaying as '{status_text}'.")

        # 应用更新
        if icon:
            status_indicator.setPixmap(icon.pixmap(16, 16)) # 设置图标
        else:
            status_indicator.clear()
        status_text_label.setText(status_text)
        status_text_label.setStyleSheet(f"color: {status_color};")
        time_text = format_datetime_friendly(source.last_checked_time)
        time_label.setText(time_text)
        
        self.logger.debug(f"_update_widget_status for '{source.name}': "
                         f"Set status_text_label to '{status_text}', "
                         f"time_label to '{time_text}'")

        # 设置整个 Widget 的 ToolTip
        full_tooltip = f"名称: {source.name}\n状态: {status_text}\n上次检查: {time_text}"
        widget.setToolTip(full_tooltip)
        # 也可以单独给重要元素设置
        # name_label.setToolTip(full_tooltip)
        # status_indicator.setToolTip(full_tooltip)
        # status_text_label.setToolTip(full_tooltip)

    def _refresh_source_status(self):
        """刷新所有新闻源的状态显示。"""
        self.logger.info("SourceManagementPanel: '_refresh_source_status' slot triggered.")
        enabled_item_widgets = []
        for i in range(self.rss_list_widget.count()):
            item = self.rss_list_widget.item(i)
            widget = self.rss_list_widget.itemWidget(item)
            if widget:
                source_obj = item.data(Qt.UserRole)  # type: NewsSource
                if source_obj and source_obj.enabled and source_obj.type == 'rss': # <<< MODIFIED: Added source_obj.type == 'rss'
                    enabled_item_widgets.append((item, widget, source_obj))

        if not enabled_item_widgets:
            self.logger.info("没有启用的RSS新闻源可刷新状态。")
            self._show_temporary_tooltip("没有启用的RSS新闻源可刷新状态。")
            return

        self.logger.info(f"准备刷新 {len(enabled_item_widgets)} 个已启用RSS源的状态 (UI)")

        # 1. Update UI immediately to 'checking_individual' for RSS sources
        for item, widget, source_obj in enabled_item_widgets:
            self.logger.debug(f"Setting '{source_obj.name}' to 'checking_individual' for immediate UI feedback.")
            source_obj.status = 'checking_individual' # Temporary status
            self._update_widget_status(widget, source_obj) # Update one widget

        # 2. Call the service to actually check statuses
        # The service will eventually emit signals that _on_single_source_check_complete will catch
        self.logger.info("Calling NewsUpdateService.check_all_sources_status() for RSS sources.")
        self.news_update_service.check_all_sources_status() # This service method will also be filtered for RSS

    # --- 新增槽函数：处理单源检查结果 --- 
    @pyqtSlot(dict)
    def _on_single_source_check_complete(self, result: dict):
        """处理从 NewsUpdateService 收到的单个源状态检查结果。"""
        source_name = result.get('source_name')
        self.logger.info(f"_on_single_source_check_complete received for '{source_name}'. Result: {result}")

        if not source_name:
            self.logger.warning("收到缺少 source_name 的检查结果，无法更新 UI。")
            return

        # Find the item in the list first
        list_widget_to_search = None
        # Determine which list widget to search based on some logic or store type with item
        # For now, we will search both. This is inefficient but will work for debugging.
        # A better way would be if NewsSource object itself had its type, or if the signal indicated it.
        
        found_item = None
        target_list_widget = None

        for lw in [self.rss_list_widget, self.crawler_list_widget]:
            for i in range(lw.count()):
                item = lw.item(i)
                if not item:
                    continue
                item_data = item.data(Qt.UserRole)
                if isinstance(item_data, NewsSource) and item_data.name == source_name:
                    found_item = item
                    target_list_widget = lw
                    break
            if found_item:
                break

        if not found_item or not target_list_widget:
            self.logger.warning(f"在 UI 列表中未找到名称为 '{source_name}' 的源，无法更新其 UI 状态。")
            return

        item_source_obj: NewsSource = found_item.data(Qt.UserRole)
        if not isinstance(item_source_obj, NewsSource):
            self.logger.error(f"Item data for '{source_name}' is not a NewsSource object. Cannot update.")
            return

        self.logger.debug(f"Source '{source_name}' (from item data) BEFORE update: "
                         f"status='{item_source_obj.status}', "
                         f"last_checked='{item_source_obj.last_checked_time}', "
                         f"last_error='{item_source_obj.last_error}'")

        # Update the NewsSource instance stored with the item directly
        check_time_dt = None
        check_time_str = result.get('check_time')
        if check_time_str:
            try:
                # Ensure check_time_str is a string before calling fromisoformat
                if isinstance(check_time_str, datetime):
                    check_time_dt = check_time_str
                elif isinstance(check_time_str, str):
                    check_time_dt = datetime.fromisoformat(check_time_str)
                else:
                    self.logger.warning(f"Unsupported type for check_time: {type(check_time_str)}")
            except ValueError:
                self.logger.warning(f"无法解析来自信号的时间戳字符串: {check_time_str}")
            except TypeError:
                self.logger.error(f"Invalid type passed to datetime.fromisoformat: {check_time_str}")

        item_source_obj.status = 'ok' if result.get('success', False) else 'error'
        item_source_obj.last_error = result.get('message', '')
        item_source_obj.consecutive_error_count = result.get('error_count', 0)
        item_source_obj.last_checked_time = check_time_dt
        
        self.logger.debug(f"Source '{source_name}' (item data) AFTER update: "
                         f"status='{item_source_obj.status}', "
                         f"last_checked='{item_source_obj.last_checked_time}', "
                         f"last_error='{item_source_obj.last_error}'")

        # Now update the widget associated with this item
        widget = target_list_widget.itemWidget(found_item)
        if widget:
            self.logger.debug(f"Calling _update_widget_status for '{source_name}' with its direct item_source_obj.")
            self._update_widget_status(widget, item_source_obj) # Pass the updated item_source_obj
            QApplication.processEvents() # Ensure timely UI update
            self.logger.debug(f"UI for source '{source_name}' updated using its direct item data.")
        else:
            self.logger.warning(f"找到源 '{source_name}' 的列表项，但无法获取其 Widget for direct update.")

    # --- 新增槽函数结束 ---

    def _handle_import_opml(self):
        """处理 OPML 文件导入"""
        self.logger.debug("Import OPML button clicked")
        # 使用 QFileDialog 获取文件路径
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入 OPML 文件",
            "",  # 默认目录
            "OPML 文件 (*.opml *.xml);;所有文件 (*)"
        )

        if file_path and self.app_service:
            self.logger.info(f"Attempting to import OPML from: {file_path}")
            success, message = self.app_service.import_sources_from_opml(file_path)
            if success:
                QMessageBox.information(self, "导入成功", message or "OPML 文件已成功导入。")
                # self.update_sources() # AppService 会发射 sources_updated 信号
            else:
                QMessageBox.warning(self, "导入失败", message or "导入 OPML 文件时发生错误。")
        elif not file_path:
            self.logger.info("OPML import cancelled by user.")


    def _handle_export_opml(self):
        """处理 OPML 文件导出"""
        self.logger.debug("Export OPML button clicked")
        # 使用 QFileDialog 获取保存文件路径
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 OPML 文件",
            "news_sources.opml",  # 默认文件名
            "OPML 文件 (*.opml *.xml);;所有文件 (*)"
        )

        if file_path and self.app_service:
            self.logger.info(f"Attempting to export OPML to: {file_path}")
            success, message = self.app_service.export_sources_to_opml(file_path)
            if success:
                QMessageBox.information(self, "导出成功", message or "新闻源已成功导出到 OPML 文件。")
            else:
                QMessageBox.warning(self, "导出失败", message or "导出新闻源到 OPML 文件时发生错误。")
        elif not file_path:
            self.logger.info("OPML export cancelled by user.")

    # +++ NEW SLOTS FOR BUTTON STATE +++
    @pyqtSlot()
    def _on_status_check_started(self):
        """Slot for when NewsUpdateService starts checking all source statuses."""
        self._is_batch_checking = True # Manage this flag here as well
        if self.refresh_button:
            self.refresh_button.setText("刷新中...")
            self.refresh_button.setEnabled(False)
        self.logger.info("Batch status check started (from _on_status_check_started). Refresh button updated and disabled.")

    @pyqtSlot()
    def _on_status_check_finished(self):
        """Slot for when NewsUpdateService finishes checking all source statuses."""
        self._is_batch_checking = False # Manage this flag here as well
        if self.refresh_button:
            self.refresh_button.setText("刷新状态")
            self.refresh_button.setEnabled(True)
        # self._checking_source_ids.clear() # We will manage this later
        self.logger.info("Batch status check finished (from _on_status_check_finished). Refresh button restored.")
        # self.update_sources() # We will manage the final update later

    # +++ ADDED Missing Slot +++
    @pyqtSlot(str, str)
    def _on_source_fetch_error(self, source_name: str, error_message: str):
        """处理从 AppService.source_fetch_failed 信号传来的错误。"""
        self.logger.error(f"SourceManagementPanel: Received source_fetch_failed for source '{source_name}'. Error: {error_message}")
        QMessageBox.warning(self, f"源 '{source_name}' 错误", f"获取新闻源 '{source_name}' 时发生错误:\\n{error_message}")
    # +++ End of Added Slot +++
