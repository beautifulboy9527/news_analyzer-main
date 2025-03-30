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
                             QSpacerItem, QSizePolicy, QDialogButtonBox,
                             QTextEdit, QAbstractItemView) # 导入 QTextEdit 和 QAbstractItemView
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from typing import List # 确保导入 List

# 假设 AppService 和 NewsSource 模型可以通过某种方式访问
from ..core.app_service import AppService # 导入 AppService
from ..models import NewsSource # 实际路径可能需要调整

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
        self.setMinimumWidth(400)
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
        self.notes_input.setFixedHeight(80) # 设置一个合适的高度
        layout.addRow("备注:", self.notes_input)

        # 按钮布局
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def get_values(self):
        """获取对话框修改后的值"""
        values = {
            'name': self.name_input.text().strip(),
            'category': self.category_input.text().strip() or "未分类",
            'notes': self.notes_input.toPlainText().strip() # 获取备注信息
        }
        # 如果是 RSS 源，包含 URL
        if self.url_input is not None:
            values['url'] = self.url_input.text().strip()
        return values

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

        # 标题
        title_label = QLabel("新闻源管理")
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        main_layout.addWidget(title_label)

        # 新闻源列表
        self.source_list_widget = QListWidget()
        self.source_list_widget.setStyleSheet("QListWidget::item { padding: 5px; }")
        self.source_list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection) # 启用多选
        main_layout.addWidget(self.source_list_widget, 1) # 占据主要空间

        # 按钮行
        button_layout = QHBoxLayout()
        main_layout.addLayout(button_layout)

        # --- 添加按钮 ---
        self.add_rss_button = QPushButton("添加 RSS 源")
        # self.add_rss_button.setIcon(QIcon(":/icons/add.png")) # 可选图标
        button_layout.addWidget(self.add_rss_button)

        # --- 编辑按钮 ---
        self.edit_source_button = QPushButton("编辑选中源")
        # self.edit_source_button.setIcon(QIcon(":/icons/edit.png")) # 可选图标
        self.edit_source_button.setEnabled(False) # 默认禁用
        button_layout.addWidget(self.edit_source_button)

        # --- 移除按钮 ---
        self.remove_source_button = QPushButton("删除选中") # 修改按钮文本
        # self.remove_source_button.setIcon(QIcon(":/icons/remove.png")) # 可选图标
        self.remove_source_button.setEnabled(False) # 默认禁用
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
        # 使用 itemSelectionChanged 信号，更适合处理选择状态的变化
        self.source_list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        # self.source_list_widget.currentItemChanged.connect(self._on_selection_changed) # REMOVED

        self.edit_source_button.clicked.connect(self._show_edit_source_dialog)
    def update_sources(self): # 移除 sources 参数
        """从 AppService 获取最新数据并更新列表显示"""
        if not self.app_service:
             self.logger.warning("AppService 不可用，无法更新新闻源列表")
             self.source_list_widget.clear()
             self.source_list_widget.addItem("错误：应用程序服务不可用")
             return

        sources = self.app_service.get_sources() # 从 AppService 获取数据
        self.logger.info(f"更新新闻源列表，共 {len(sources)} 个源")
        self.source_list_widget.clear()
        if not sources:
            self.source_list_widget.addItem("没有配置的新闻源")
            return

        for source in sources:
            item_widget = self._create_source_item_widget(source)
            list_item = QListWidgetItem(self.source_list_widget)
            list_item.setSizeHint(item_widget.sizeHint())
            # 将 NewsSource 对象存储在列表项中，方便后续操作
            list_item.setData(Qt.UserRole, source)
            self.source_list_widget.addItem(list_item)
            self.source_list_widget.setItemWidget(list_item, item_widget)

        self._on_selection_changed() # 更新按钮状态 (不再传递参数)

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

        name_label = QLabel(f"<b>{source.name}</b>")
        info_layout.addWidget(name_label)

        detail_text = f"类型: {source.type}"
        if source.type == 'rss' and source.url:
            detail_text += f" | URL: {source.url}"
        if source.category:
            detail_text += f" | 分类: {source.category}"
        if source.notes: # 如果有备注，也添加到详情中
            detail_text += f"\n备注: {source.notes}" # 换行显示备注
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

    def _show_edit_source_dialog(self):
        """显示编辑选中新闻源的对话框"""
        current_item = self.source_list_widget.currentItem()
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

            try:
                self.logger.info(f"UI 请求: 更新新闻源 '{original_name}' 的信息为: {updated_values}")
                self.app_service.update_source(original_name, updated_values)
                # AppService 会发出 sources_updated 信号，自动更新列表
                self.logger.info(f"已调用 AppService.update_source 更新 '{original_name}'")
            except Exception as e:
                self.logger.error(f"更新新闻源 '{original_name}' 失败: {e}", exc_info=True)
                QMessageBox.warning(self, "更新失败", f"无法更新新闻源 '{original_name}': {e}")

            if not values['url']:
                QMessageBox.warning(self, "输入错误", "请输入有效的 RSS URL")
                return

            new_source = NewsSource(
                name=values['name'] or values['url'].split("//")[-1].split("/")[0],
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

    def _remove_selected_source(self):
        """移除当前选中的一个或多个新闻源"""
        selected_items = self.source_list_widget.selectedItems()
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

    def _on_selection_changed(self): # 移除 current_item 参数，因为 itemSelectionChanged 信号不传递参数
        """当列表选中项改变时调用"""
        selected_items = self.source_list_widget.selectedItems()
        can_remove = bool(selected_items) # 如果有任何选中项，则允许删除
        can_edit = False # 编辑按钮状态变量

        # 编辑按钮逻辑：只有当选中了 *单个* 源时才启用
        if len(selected_items) == 1:
            source: NewsSource = selected_items[0].data(Qt.UserRole)
            can_edit = True # 允许编辑任何单个选中的源

        self.remove_source_button.setEnabled(can_remove) # 根据是否有选中项启用删除按钮
        self.edit_source_button.setEnabled(can_edit) # 根据是否选中单个项启用编辑按钮