#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
新闻源管理面板 UI 模块
"""

from typing import List # 导入 List 用于类型提示

import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QPushButton, QLabel, QCheckBox,
                             QMessageBox, QDialog, QLineEdit, QFormLayout,
                             QSpacerItem, QSizePolicy, QDialogButtonBox, QTabWidget, # 添加 QTabWidget
                             QTextEdit, QAbstractItemView) # 导入 QTextEdit 和 QAbstractItemView
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from typing import List # 确保导入 List

# 假设 AppService 和 NewsSource 模型可以通过某种方式访问
from core.app_service import AppService # 导入 AppService
from models import NewsSource # 恢复原始导入路径
from .ui_utils import create_standard_button, create_title_label, add_form_row, setup_list_widget # <-- 添加导入

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
            self.add_pengpai_selector_fields(layout, source.selector_config or {})

        # --- 按钮布局 ---

        # 按钮布局
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
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
            values['selector_config'] = selector_config # 将选择器字典添加到返回值

    def _show_selector_help(self):
        """显示 CSS 选择器帮助信息"""
        help_text = """
        <h2>澎湃新闻 CSS 选择器帮助</h2>
        <p>这些选择器用于告诉程序如何在澎湃新闻网站上找到需要的信息。您需要使用浏览器的开发者工具来获取它们。</p>
        <p><b>基本步骤:</b></p>
        <ol>
            <li>在澎湃新闻网站上，右键点击您想提取的信息（如标题、正文区域）。</li>
            <li>选择“检查”或“Inspect Element”。</li>
            <li>在弹出的开发者工具中，找到对应的 HTML 代码。</li>
            <li>右键点击该 HTML 代码，选择“复制” -> “复制选择器”(Copy -> Copy Selector)。</li>
            <li>将复制的选择器粘贴到下面的输入框中。<b>注意：</b>有时需要手动简化或调整选择器。</li>
        </ol>
        <hr>
        <p><b>选择器详解:</b></p>
        <ul>
            <li><b>列表 - 新闻项:</b> (必需) 在新闻列表页（如首页、频道页）上，框选单条新闻信息的那个 HTML 块。后续的“列表-”选择器都在这个块内部查找。</li>
            <li><b>列表 - 标题:</b> (必需) 在“新闻项”内部，定位新闻标题。</li>
            <li><b>列表 - 链接:</b> (必需) 在“新闻项”内部，定位指向详情页的链接 (a 标签)，并提取其 'href' 属性 (通常以 <code>::attr(href)</code> 结尾)。</li>
            <li><b>列表 - 摘要:</b> (可选) 在“新闻项”内部，定位新闻摘要。</li>
            <li><b>详情 - 正文容器:</b> (必需) 在新闻详情页上，定位包含<b>主要正文内容</b>的那个 HTML 容器 (通常是 div 或 article)。</li>
            <li><b>详情 - 作者:</b> (可选) 在新闻详情页上，定位包含作者名字的元素。</li>
            <li><b>详情/列表 - 时间:</b> (可选) 在新闻详情页或列表页的“新闻项”内部，定位包含发布时间的元素。</li>
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

    def __init__(self, app_service: AppService, parent=None): # 接收 AppService 实例
        super().__init__(parent) # 调用 QDialog 的构造函数
        self.setWindowTitle("新闻源管理") # 设置对话框标题
        self.setMinimumSize(600, 400) # 设置最小尺寸

        self.logger = logging.getLogger('news_analyzer.ui.source_management_panel')
        self.app_service = app_service # 保存 AppService 引用

        self._init_ui()
        self._connect_signals()

        # 初始加载数据
        if self.app_service:
            self.update_sources() # 不再传递参数
            # 连接 AppService 的更新信号
            self.app_service.sources_updated.connect(self.update_sources)
        else:
             self.logger.warning("AppService 未提供，面板无法加载数据或连接信号")


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
        button_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # --- 对话框关闭按钮 ---
        button_box = QDialogButtonBox(QDialogButtonBox.Close) # 只添加关闭按钮
        button_box.rejected.connect(self.reject) # 连接到 reject 槽
        main_layout.addWidget(button_box) # 将关闭按钮添加到主垂直布局


    def _connect_signals(self):
        """连接内部信号和槽"""
        self.add_rss_button.clicked.connect(self._show_add_rss_dialog)
        self.remove_source_button.clicked.connect(self._remove_selected_source)
        self.edit_source_button.clicked.connect(self._show_edit_source_dialog)

        # 连接两个列表的 itemSelectionChanged 信号
        self.rss_list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.crawler_list_widget.itemSelectionChanged.connect(self._on_selection_changed)

        # 连接 TabWidget 的 currentChanged 信号
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

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
            elif source.type == 'pengpai': # 或者其他爬虫类型
                self.crawler_list_widget.addItem(list_item)
                self.crawler_list_widget.setItemWidget(list_item, item_widget)
                crawler_count += 1
            else:
                 self.logger.warning(f"未知的源类型 '{source.type}' for source '{source.name}'，未添加到列表。")

        self.logger.info(f"填充完成：RSS 源 {rss_count} 个，爬虫源 {crawler_count} 个。")
        # 确保在填充后更新按钮状态
        self._on_selection_changed() # 更新按钮状态
        self._on_tab_changed(self.tab_widget.currentIndex()) # 根据当前标签页调整按钮可见性

    def _create_source_item_widget(self, source: NewsSource) -> QWidget:
        """为单个新闻源创建一个自定义的 QWidget"""
        item_widget = QWidget()
        item_layout = QHBoxLayout(item_widget)
        item_layout.setContentsMargins(5, 5, 5, 5)

        # 复选框 (启用/禁用)
        enable_checkbox = QCheckBox()
        enable_checkbox.setChecked(source.enabled)
        enable_checkbox.stateChanged.connect(lambda state, s=source: self._toggle_source_enabled(s, state == Qt.Checked))
        item_layout.addWidget(enable_checkbox)

        # 名称和类型/URL
        info_layout = QVBoxLayout()
        item_layout.addLayout(info_layout, 1) # 占据主要空间

        # 添加类型前缀到名称标签
        type_prefix = "[RSS]" if source.type == 'rss' else "[爬虫]" if source.type == 'pengpai' else f"[{source.type}]"
        name_label = QLabel(f"{type_prefix} <b>{source.name}</b>")
        info_layout.addWidget(name_label)

        # 不再在详情中显示类型，因为已加到名称前
        # detail_text = f"类型: {source.type}"
        detail_text = "" # 初始化为空字符串
        if source.type == 'rss' and source.url:
            detail_text += f" | URL: {source.url}"
        if source.category:
            detail_text += f" | 分类: {source.category}"
        if source.notes: # 如果有备注，也添加到详情中
            detail_text += f"\n备注: {source.notes}" # 换行显示备注
        # 调整 detail_text 的拼接逻辑
        details = []
        if source.type == 'rss' and source.url:
            details.append(f"URL: {source.url}")
        if source.category:
            details.append(f"分类: {source.category}")
        if source.notes:
            details.append(f"备注: {source.notes}") # 换行显示备注

        detail_text = " | ".join(details) # 使用分隔符连接详情

        detail_label = QLabel(detail_text)
        detail_label.setStyleSheet("color: gray;")
        detail_label.setWordWrap(True) # 启用自动换行
        info_layout.addWidget(detail_label)

        # TODO: 可以添加最后更新时间、错误状态等显示

        # 对于非 RSS 源（如澎湃），禁用复选框外的编辑/删除功能 (如果需要)
        if source.type != 'rss':
             # 可以考虑隐藏移除按钮或禁用复选框外的交互
             pass

        return item_widget

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
        """切换新闻源的启用/禁用状态"""
        if not self.app_service:
            self.logger.warning("尝试切换源状态但 AppService 不可用")
            return
        self.logger.info(f"UI 请求: 切换新闻源 '{source.name}' 启用状态为: {enabled}")
        try:
            self.app_service.update_source(source.name, {'enabled': enabled})
            self.logger.info(f"已调用 AppService.update_source 更新 '{source.name}'")
            # AppService 会发出 sources_updated 信号，理论上会自动刷新列表
            # 或者依赖 update_sources 重新绘制整个列表
        except Exception as e:
             QMessageBox.warning(self, "更新失败", f"无法更新新闻源 '{source.name}' 状态: {e}")
             # 可能需要恢复复选框状态
             # TODO: 找到对应的 item widget 并恢复 checkbox 状态


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