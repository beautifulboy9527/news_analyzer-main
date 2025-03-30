"""
语言模型设置对话框 (支持多配置)

提供管理和配置多个LLM API的界面。
"""

import os
import logging
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                            QLineEdit, QPushButton, QLabel, QMessageBox,
                            QGroupBox, QCheckBox, QListWidget, QListWidgetItem,
                            QWidget, QSplitter, QInputDialog, QApplication)
from PyQt5.QtCore import QSettings, Qt, pyqtSignal, QSize # 添加 QSize 导入
from PyQt5.QtGui import QIcon, QFont

# --- 添加 LLMConfigManager 导入 ---
from ..config.llm_config_manager import LLMConfigManager
# --- 导入结束 ---

class LLMSettingsDialog(QDialog):
    """语言模型设置对话框 (支持多配置)"""

    # 定义信号，当设置被保存或激活配置改变时发射
    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.logger = logging.getLogger('news_analyzer.ui.llm_settings')
        self.config_manager = LLMConfigManager()
        self.current_config_name = None # 当前在编辑区域显示的配置名称
        self._api_key_modified = False # 标记API Key是否被用户修改过
        # self._is_dirty = False # 不再需要 dirty 标记

        self.setWindowTitle("语言模型配置管理")
        self.setMinimumWidth(750) # 增加宽度以容纳左右布局
        self.setMinimumHeight(450) # 增加高度
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()
        self._load_settings() # 加载列表和活动配置

    def _init_ui(self):
        """初始化UI (重构为左右布局)"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- 创建左右分割器 ---
        splitter = QSplitter(Qt.Horizontal)

        # --- 左侧：配置列表和管理按钮 ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        list_label = QLabel("可用配置:")
        self.config_list_widget = QListWidget()
        self.config_list_widget.currentItemChanged.connect(self._on_config_selected)
        self.config_list_widget.itemDoubleClicked.connect(self._activate_config) # 双击激活

        left_layout.addWidget(list_label)
        left_layout.addWidget(self.config_list_widget)

        list_button_layout = QHBoxLayout()
        add_button = QPushButton("添加")
        add_button.setIcon(QIcon.fromTheme("list-add"))
        add_button.clicked.connect(self._add_config)
        delete_button = QPushButton("删除")
        delete_button.setIcon(QIcon.fromTheme("list-remove"))
        delete_button.clicked.connect(self._delete_config)
        list_button_layout.addWidget(add_button)
        list_button_layout.addWidget(delete_button)
        list_button_layout.addStretch()

        left_layout.addLayout(list_button_layout)
        splitter.addWidget(left_widget)

        # --- 右侧：配置编辑区域 ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0) # 右侧稍微留点边距
        right_layout.setSpacing(15)

        self.edit_group = QGroupBox("配置详情")
        self.edit_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        self.edit_group.setEnabled(False) # 初始禁用，选中后启用
        edit_form_layout = QFormLayout()
        edit_form_layout.setSpacing(10)
        edit_form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # 配置名称 (不可编辑，通过添加/重命名修改)
        self.config_name_label = QLabel("<i>未选择配置</i>")
        self.config_name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        edit_form_layout.addRow("配置名称:", self.config_name_label)

        # API URL
        self.api_url_edit = QLineEdit()
        self.api_url_edit.setPlaceholderText("例如: https://api.openai.com/v1/chat/completions")
        # self.api_url_edit.textChanged.connect(self._mark_dirty) # 不再需要标记 dirty
        edit_form_layout.addRow("API端点URL:", self.api_url_edit)

        # API 密钥 (特殊处理)
        api_key_layout = QHBoxLayout()
        api_key_layout.setSpacing(5) # 减小间距
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("输入新密钥或留空以保留现有密钥")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        # 当用户开始编辑时，标记密钥已被修改
        self.api_key_edit.textChanged.connect(lambda: setattr(self, '_api_key_modified', True))
        # self.api_key_edit.textChanged.connect(self._mark_dirty) # 不再需要标记 dirty
        api_key_layout.addWidget(self.api_key_edit)
        # 添加显示/隐藏按钮
        self.show_key_button = QPushButton()
        # 尝试主题图标，然后尝试标准图标，最后用文字
        reveal_icon = QIcon.fromTheme("view-reveal")
        if reveal_icon.isNull():
            reveal_icon = self.style().standardIcon(QApplication.style().SP_DialogYesButton) # 备选标准图标
        self.show_key_button.setIcon(reveal_icon)
        # 总是设置初始文本为 [显示]
        self.show_key_button.setText("[显示]")
        if reveal_icon.isNull(): # 如果图标加载失败，确保文字可见
             pass # 文字已设置
        else: # 如果图标加载成功，清空文字
             self.show_key_button.setText("")


        self.show_key_button.setCheckable(True)
        self.show_key_button.setToolTip("显示/隐藏 API 密钥")
        self.show_key_button.setFixedSize(QSize(60, 30)) # 调整大小以适应文字
        self.show_key_button.setStyleSheet("QPushButton { border: 1px solid #ccc; padding: 2px; }") # 恢复一点边框
        self.show_key_button.clicked.connect(self._toggle_key_visibility) # 连接到正确的方法
        api_key_layout.addWidget(self.show_key_button)
        edit_form_layout.addRow("API密钥:", api_key_layout)

        # 模型名称
        self.model_name_edit = QLineEdit()
        self.model_name_edit.setPlaceholderText("例如: gpt-3.5-turbo, claude-3-opus-20240229")
        # self.model_name_edit.textChanged.connect(self._mark_dirty) # 不再需要标记 dirty
        edit_form_layout.addRow("模型名称:", self.model_name_edit)

        # --- 高级参数 ---
        adv_label = QLabel("--- 高级参数 (可选) ---")
        adv_label.setStyleSheet("color: gray; margin-top: 10px;")
        edit_form_layout.addRow(adv_label)

        # 温度参数
        self.temperature_edit = QLineEdit()
        self.temperature_edit.setPlaceholderText("默认 0.7, 范围: 0.0-2.0")
        # self.temperature_edit.textChanged.connect(self._mark_dirty) # 不再需要标记 dirty
        edit_form_layout.addRow("温度:", self.temperature_edit)

        # 最大Token
        self.max_tokens_edit = QLineEdit()
        self.max_tokens_edit.setPlaceholderText("默认 2048 或 4096")
        # self.max_tokens_edit.textChanged.connect(self._mark_dirty) # 不再需要标记 dirty
        edit_form_layout.addRow("最大生成长度:", self.max_tokens_edit)

        # 系统提示
        self.system_prompt_edit = QLineEdit()
        self.system_prompt_edit.setPlaceholderText("可选：为模型设置默认行为")
        # self.system_prompt_edit.setToolTip(...) # 移除 Tooltip
        # self.system_prompt_edit.textChanged.connect(self._mark_dirty) # 不再需要标记 dirty
        edit_form_layout.addRow("系统提示:", self.system_prompt_edit)
        # 添加说明标签
        system_prompt_label = QLabel("设置模型的初始指令或角色，例如 '你是一个专业的新闻分析助手'。")
        system_prompt_label.setStyleSheet("color: gray; font-size: 11px;")
        system_prompt_label.setWordWrap(True)
        edit_form_layout.addRow("", system_prompt_label) # 添加到下一行

        # 超时设置
        self.timeout_edit = QLineEdit()
        self.timeout_edit.setPlaceholderText("默认 60 秒")
        # self.timeout_edit.textChanged.connect(self._mark_dirty) # 不再需要标记 dirty
        edit_form_layout.addRow("请求超时(秒):", self.timeout_edit)

        self.edit_group.setLayout(edit_form_layout)
        right_layout.addWidget(self.edit_group)

        # 右侧按钮布局
        edit_button_layout = QHBoxLayout()
        self.save_config_button = QPushButton("保存当前配置")
        self.save_config_button.setIcon(QIcon.fromTheme("document-save"))
        self.save_config_button.setEnabled(False)
        self.save_config_button.clicked.connect(self._save_current_config)

        self.activate_button = QPushButton("设为活动配置")
        self.activate_button.setIcon(QIcon.fromTheme("emblem-ok")) # 使用 'ok' 图标表示激活
        self.activate_button.setEnabled(False)
        self.activate_button.clicked.connect(self._activate_config)

        self.test_button = QPushButton("测试当前配置")
        self.test_button.setIcon(QIcon.fromTheme("network-transmit-receive"))
        self.test_button.setEnabled(False)
        self.test_button.clicked.connect(self._test_connection) # 连接到新的测试函数

        edit_button_layout.addWidget(self.save_config_button)
        edit_button_layout.addWidget(self.activate_button)
        edit_button_layout.addWidget(self.test_button)
        edit_button_layout.addStretch()

        right_layout.addLayout(edit_button_layout)
        right_layout.addStretch() # 将编辑区推到顶部

        splitter.addWidget(right_widget)

        # 设置分割器初始比例 (例如，左侧占1/3)
        splitter.setSizes([250, 500]) # 调整比例

        main_layout.addWidget(splitter)

        # --- 底部按钮布局 (OK/Cancel) ---
        bottom_button_layout = QHBoxLayout()
        bottom_button_layout.addStretch()

        close_button = QPushButton("关闭") # 改为关闭
        close_button.clicked.connect(self.reject) # reject 通常用于取消/关闭
        bottom_button_layout.addWidget(close_button)

        main_layout.addLayout(bottom_button_layout)

    def _load_settings(self):
        """加载配置列表和活动配置"""
        self._populate_config_list() # 这会填充列表并触发 _on_config_selected
        # _on_config_selected 会根据是否有选中项来启用/禁用编辑区和按钮
        # 因此这里不再需要手动禁用
        # self._clear_edit_fields() # _populate_config_list 会触发选中，进而调用 _clear 或填充
        # self.edit_group.setEnabled(False)
        # self.save_config_button.setEnabled(False)
        # self.activate_button.setEnabled(False)
        # self.test_button.setEnabled(False)

    def _populate_config_list(self):
        """填充左侧的配置列表"""
        self.config_list_widget.clear()
        config_names = self.config_manager.get_config_names()
        active_config_name = self.config_manager.get_active_config_name()
        selected_item = None
        for name in sorted(config_names): # 按名称排序
            item_text = name
            item = QListWidgetItem() # 创建空 item
            if name == active_config_name:
                item_text += " (活动)" # 添加活动标识
                font = QFont()
                font.setBold(True)
                item.setFont(font)
                item.setIcon(QIcon.fromTheme("emblem-default", QIcon(":/icons/active.png"))) # 标记活动项
                selected_item = item # 默认选中活动项
            item.setText(item_text) # 设置文本
            self.config_list_widget.addItem(item)
        if selected_item:
            self.config_list_widget.setCurrentItem(selected_item)
        elif self.config_list_widget.count() > 0:
             self.config_list_widget.setCurrentRow(0) # 选中第一个

    def _on_config_selected(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        """当列表选中项改变时，加载配置到右侧编辑区"""
        # --- 移除未保存更改检查 ---
        # (之前的检查逻辑已移除)
        # 切换时总是重置 dirty 标记，因为未保存的更改会被覆盖
        # self._is_dirty = False # 不再需要
        # --- 移除结束 ---

        if current_item:
            config_name_with_marker = current_item.text()
            config_name = config_name_with_marker.replace(" (活动)", "") # 移除活动标记获取真实名称
            self.current_config_name = config_name
            config = self.config_manager.get_config(config_name)
            if config:
                # --- 阻止信号触发 dirty 标记 ---
                self.api_url_edit.blockSignals(True)
                self.api_key_edit.blockSignals(True)
                self.model_name_edit.blockSignals(True)
                self.temperature_edit.blockSignals(True)
                self.max_tokens_edit.blockSignals(True)
                self.system_prompt_edit.blockSignals(True)
                self.timeout_edit.blockSignals(True)
                # --- 填充数据 ---
                self.config_name_label.setText(f"<b>{config_name}</b>")
                self.api_url_edit.setText(config.get('api_url', ''))
                # API Key: 如果存在，显示 ******，否则提示输入
                if config.get('api_key'):
                    self.api_key_edit.setText("******") # 显示占位符
                    self.api_key_edit.setPlaceholderText("输入新密钥以覆盖，或留空")
                else:
                    self.api_key_edit.setText("")
                    self.api_key_edit.setPlaceholderText("未设置API密钥，请输入")
                self._api_key_modified = False # 重置修改标记
                self.model_name_edit.setText(config.get('model', ''))
                # 加载高级参数
                self.temperature_edit.setText(str(config.get('temperature', '0.7')))
                self.max_tokens_edit.setText(str(config.get('max_tokens', '2048')))
                self.system_prompt_edit.setText(config.get('system_prompt', ''))
                self.timeout_edit.setText(str(config.get('timeout', '60')))
                # --- 恢复信号 ---
                self.api_url_edit.blockSignals(False)
                self.api_key_edit.blockSignals(False)
                self.model_name_edit.blockSignals(False)
                self.temperature_edit.blockSignals(False)
                self.max_tokens_edit.blockSignals(False)
                self.system_prompt_edit.blockSignals(False)
                self.timeout_edit.blockSignals(False)
                # --- 重置 dirty 标记 ---
                self._is_dirty = False # 确保在所有 setText 完成后重置
                # --- 重置结束 ---

                self.edit_group.setEnabled(True)
                self.save_config_button.setEnabled(True)
                self.activate_button.setEnabled(True)
                self.test_button.setEnabled(True)
            else:
                self._clear_edit_fields()
                self.edit_group.setEnabled(False)
                self.save_config_button.setEnabled(False)
                self.activate_button.setEnabled(False)
                self.test_button.setEnabled(False)
        else:
            self.current_config_name = None
            self._clear_edit_fields()
            self.edit_group.setEnabled(False)
            self.save_config_button.setEnabled(False)
            self.activate_button.setEnabled(False)
            self.test_button.setEnabled(False)

    def _clear_edit_fields(self):
        """清空右侧编辑区域的字段"""
        self.config_name_label.setText("<i>未选择配置</i>")
        self.api_url_edit.clear()
        self.api_key_edit.clear()
        self.api_key_edit.setPlaceholderText("输入API密钥")
        self.model_name_edit.clear()
        self.temperature_edit.clear()
        self.max_tokens_edit.clear()
        self.system_prompt_edit.clear()
        self.timeout_edit.clear()
        self.current_config_name = None
        self._api_key_modified = False
        # self._is_dirty = False # 清空时也重置 (不再需要)

    def _add_config(self):
        """添加新配置"""
        name, ok = QInputDialog.getText(self, "添加新配置", "请输入配置名称:")
        if ok and name:
            if name in self.config_manager.get_config_names():
                QMessageBox.warning(self, "名称已存在", f"配置名称 '{name}' 已存在，请使用其他名称。")
                return
            # 添加一个空配置，让用户在右侧编辑
            self.config_manager.add_or_update_config(name, "", "", "")
            self._populate_config_list()
            # 选中新添加的项
            items = self.config_list_widget.findItems(name, Qt.MatchExactly)
            if items:
                self.config_list_widget.setCurrentItem(items[0])
            QMessageBox.information(self, "提示", f"已添加配置 '{name}'，请在右侧填写详细信息并保存。")
        elif ok and not name:
             QMessageBox.warning(self, "输入错误", "配置名称不能为空。")


    def _delete_config(self):
        """删除选中的配置"""
        current_item = self.config_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "未选择", "请先在左侧列表中选择要删除的配置。")
            return

        config_name = current_item.text().replace(" (活动)", "") # 获取真实名称
        reply = QMessageBox.question(self, "确认删除", f"确定要删除配置 '{config_name}' 吗？",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            if self.config_manager.delete_config(config_name):
                self._populate_config_list()
                self._clear_edit_fields()
                self.edit_group.setEnabled(False)
                self.save_config_button.setEnabled(False)
                self.activate_button.setEnabled(False)
                self.test_button.setEnabled(False)
                self.settings_changed.emit() # 发射信号通知主窗口可能需要更新
                QMessageBox.information(self, "已删除", f"配置 '{config_name}' 已被删除。")
            else:
                QMessageBox.critical(self, "删除失败", f"删除配置 '{config_name}' 失败。")

    def _save_current_config(self):
        """保存右侧编辑区域的配置"""
        if not self.current_config_name:
            QMessageBox.warning(self, "未选择", "没有选中的配置可供保存。")
            return

        name = self.current_config_name
        api_url = self.api_url_edit.text().strip()
        model_name = self.model_name_edit.text().strip()

        # 处理API Key：如果用户修改过，则使用新输入的；否则保留旧的
        api_key_to_save = None
        current_text = self.api_key_edit.text() # 获取当前编辑框文本
        if self._api_key_modified:
            # 如果修改过，且不是占位符，保存当前文本（去除空白）
            if current_text != "******":
                api_key_to_save = current_text.strip()
            else:
                # 如果是占位符，说明用户没输入新密钥，尝试保留旧的
                old_config = self.config_manager.get_config(name)
                api_key_to_save = old_config.get('api_key', '') if old_config else ''
        else:
            # 用户未修改，获取旧配置以保留密钥
            old_config = self.config_manager.get_config(name)
            if old_config:
                api_key_to_save = old_config.get('api_key') # 传入解密后的旧密钥

        # 再次检查 api_key_to_save 是否为 None (理论上不应该，除非 get_config 失败)
        if api_key_to_save is None:
            api_key_to_save = "" # 保证至少是空字符串

        # 如果用户清空了密钥，提醒一下 (仅当之前有密钥时)
        if self._api_key_modified and not api_key_to_save:
             old_config = self.config_manager.get_config(name)
             if old_config and old_config.get('api_key'):
                 reply = QMessageBox.question(self, "确认清空密钥", f"您已清空配置 '{name}' 的API密钥，确定要保存吗？",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                 if reply == QMessageBox.No:
                     return # 用户取消

        if not api_url or not model_name:
            QMessageBox.warning(self, "输入不完整", "API端点URL和模型名称不能为空。")
            return

        # 获取高级参数，提供默认值
        try:
            temperature = float(self.temperature_edit.text() or 0.7)
            max_tokens = int(self.max_tokens_edit.text() or 2048)
            system_prompt = self.system_prompt_edit.text()
            timeout = int(self.timeout_edit.text() or 60)
        except ValueError:
            QMessageBox.warning(self, "输入错误", "高级参数格式不正确（温度应为数字，最大长度和超时应为整数）。")
            return

        # 准备要传递给管理器的额外参数
        extra_args = {
            'temperature': temperature,
            'max_tokens': max_tokens,
            'system_prompt': system_prompt,
            'timeout': timeout
        }

        if self.config_manager.add_or_update_config(name, api_url, api_key_to_save, model_name, **extra_args):
            # self._is_dirty = False # 不再需要
            self._api_key_modified = False # 保存成功后重置密钥修改标记
            # 如果保存了密钥（无论是新输入的还是保留旧的），显示 ******
            if api_key_to_save:
                self.api_key_edit.setText("******")
                self.api_key_edit.setPlaceholderText("输入新密钥以覆盖，或留空")
            else:
                self.api_key_edit.setText("")
                self.api_key_edit.setPlaceholderText("未设置API密钥，请输入")
            # 可能需要重新填充列表以更新显示（例如粗体）
            self._populate_config_list()
            self.settings_changed.emit() # 发射信号
            QMessageBox.information(self, "保存成功", f"配置 '{name}' 已成功保存。")
        else:
            QMessageBox.critical(self, "保存失败", f"保存配置 '{name}' 失败。")


    def _activate_config(self):
        """激活选中的配置"""
        current_item = self.config_list_widget.currentItem()
        if not current_item:
             # 如果是通过双击触发，可能没有选中项，尝试从事件获取
             sender = self.sender()
             if isinstance(sender, QListWidget):
                 current_item = sender.currentItem()

        if not current_item:
            QMessageBox.warning(self, "未选择", "请先在左侧列表中选择要激活的配置。")
            return

        config_name = current_item.text().replace(" (活动)", "") # 获取真实名称
        self.config_manager.set_active_config_name(config_name)
        self._populate_config_list() # 更新列表显示（粗体和图标）
        self.settings_changed.emit() # 发射信号通知主窗口
        QMessageBox.information(self, "已激活", f"配置 '{config_name}' 已被设为活动配置。")

    def _test_connection(self):
        """测试当前编辑区域显示的配置"""
        if not self.current_config_name:
            QMessageBox.warning(self, "未选择", "请先选择一个配置进行测试。")
            return

        api_url = self.api_url_edit.text().strip()
        model_name = self.model_name_edit.text().strip()

        # 获取API Key进行测试
        api_key_to_test = None
        current_key_text = self.api_key_edit.text()
        if self._api_key_modified and current_key_text != "******":
            # 如果用户修改过且不是占位符，使用编辑框内容（去除空白）
            api_key_to_test = current_key_text.strip()
        else:
            # 否则，从管理器获取已保存的key（已经是strip过的）
            config = self.config_manager.get_config(self.current_config_name)
            if config:
                api_key_to_test = config.get('api_key') # 获取解密后的密钥

        if not api_url or not api_key_to_test:
            QMessageBox.warning(self, "输入不完整", "测试连接需要有效的API URL和API密钥。请确保已输入或保存密钥。")
            return

        self.test_button.setEnabled(False)
        self.test_button.setText("正在测试...")
        QApplication.processEvents() # 强制处理事件，更新按钮文本

        try:
            # 导入LLMClient（可能需要调整导入路径）
            # 假设LLMClient在llm模块下
            from ..llm.llm_client import LLMClient

            # 创建临时客户端进行测试，传入当前编辑框的值
            client = LLMClient(api_key=api_key_to_test, api_url=api_url, model=model_name)
            # 可以选择性地传递高级参数给测试客户端
            # client.temperature = float(self.temperature_edit.text() or 0.7)
            # client.max_tokens = int(self.max_tokens_edit.text() or 2048)
            # client.timeout = int(self.timeout_edit.text() or 60)

            result = client.test_connection()

            if result:
                QMessageBox.information(self, "连接成功", f"配置 '{self.current_config_name}' 连接测试成功！")
            else:
                QMessageBox.warning(self, "连接失败", f"配置 '{self.current_config_name}' 无法连接到API服务，请检查URL、密钥和模型名称。")

        except ImportError:
             # 正确缩进
             QMessageBox.critical(self, "导入错误", "无法导入 LLMClient，请检查项目结构。")
        except Exception as e:
            # 正确缩进
            self.logger.error(f"测试连接时发生错误: {e}", exc_info=True)
            QMessageBox.critical(self, "连接错误", f"测试连接时发生错误:\n{str(e)}")
        finally:
            # 正确缩进
            self.test_button.setEnabled(True)
            self.test_button.setText("测试当前配置")

    # --- 将新方法移到这里 ---
    # def _mark_dirty(self): # 不再需要
    #     ...

    def _toggle_key_visibility(self, checked):
        """切换API密钥的可见性"""
        if checked:
            # --- 显示明文 ---
            key_to_show = ""
            # 优先使用用户当前输入的内容（如果不是占位符）
            current_text = self.api_key_edit.text()
            if self._api_key_modified and current_text != "******":
                key_to_show = current_text.strip() # 显示用户输入的（去除空白）
            # 否则，尝试从配置管理器获取已保存的密钥
            elif self.current_config_name:
                config = self.config_manager.get_config(self.current_config_name)
                if config:
                    key_to_show = config.get('api_key', '') # 获取解密后的密钥

            # 设置为 Normal 模式并显示获取到的密钥
            self.api_key_edit.setEchoMode(QLineEdit.Normal)
            self.api_key_edit.setText(key_to_show)

            # 更新图标/文字为“隐藏”状态
            conceal_icon = QIcon.fromTheme("view-conceal")
            if conceal_icon.isNull():
                conceal_icon = self.style().standardIcon(QApplication.style().SP_DialogNoButton) # 备选标准图标
            self.show_key_button.setIcon(conceal_icon)
            if conceal_icon.isNull():
                self.show_key_button.setText("[隐藏]") # 使用文字
        else:
            # --- 隐藏明文 ---
            # 设置为 Password 模式
            self.api_key_edit.setEchoMode(QLineEdit.Password)

            # 检查实际是否有密钥（无论是已保存的还是刚输入的）
            key_exists = False
            current_text = self.api_key_edit.text() # 获取当前显示的文本（可能是明文）
            # 如果用户修改过且当前文本非空，则认为有密钥
            if self._api_key_modified and current_text:
                key_exists = True
            # 如果用户未修改，检查存储中是否有密钥
            elif not self._api_key_modified and self.current_config_name:
                config = self.config_manager.get_config(self.current_config_name)
                if config and config.get('api_key'):
                    key_exists = True

            # 如果确定有密钥，则显示 ******
            if key_exists:
                # 即使之前显示的是明文，现在也强制设为 ******
                self.api_key_edit.setText("******")
            else:
                # 如果没有密钥（或者用户输入为空），则清空
                self.api_key_edit.setText("")

            # 更新图标/文字为“显示”状态
            reveal_icon = QIcon.fromTheme("view-reveal")
            if reveal_icon.isNull():
                reveal_icon = self.style().standardIcon(QApplication.style().SP_DialogYesButton) # 备选标准图标
            self.show_key_button.setIcon(reveal_icon)
            if reveal_icon.isNull():
                self.show_key_button.setText("[显示]") # 使用文字
    # --- 新方法结束 ---

    # --- 移除或注释掉不再使用的方法 ---
    # def save_settings(self): ...
    # def get_settings(self): ...
    # def _use_openai_preset(self): ... (可以保留作为快速填充编辑区的辅助功能)
    # def _use_openai_4_preset(self): ...
    # def _use_claude_preset(self): ...
    # def _use_local_preset(self): ...

    # accept() 和 reject() 通常由 QDialog 自动处理关闭，
    # 但如果需要在关闭前做特定操作（如确认未保存更改），可以重写它们。
    # def accept(self):
    #     # 可以在这里添加检查是否有未保存的更改
    #     super().accept()

    # def reject(self):
    #     # 可以在这里添加检查是否有未保存的更改
    #     super().reject()

# --- 用于独立测试对话框 ---
if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG) # 启用日志记录

    # 创建一个虚拟的 LLMConfigManager 用于测试，避免真的读写文件
    class MockLLMConfigManager:
        def __init__(self):
            self.configs = {
                "OpenAI-GPT4": {"api_url": "https://api.openai.com/v1/chat/completions", "encrypted_api_key": "enc_key1", "model": "gpt-4", "temperature": 0.6},
                "Local Llama": {"api_url": "http://localhost:11434/api/chat", "encrypted_api_key": "enc_key2", "model": "llama3"}
            }
            self.active_config = "OpenAI-GPT4"
        def get_config_names(self): return list(self.configs.keys())
        def get_config(self, name):
            cfg = self.configs.get(name)
            if cfg:
                d_cfg = cfg.copy()
                d_cfg['api_key'] = f"decrypted_{cfg['encrypted_api_key']}" # 模拟解密
                d_cfg.pop('encrypted_api_key', None)
                return d_cfg
            return None
        def add_or_update_config(self, name, api_url, api_key, model, **kwargs):
            print(f"Mock: Adding/Updating {name} with key: {api_key}")
            self.configs[name] = {"api_url": api_url, "encrypted_api_key": f"enc_{api_key}", "model": model, **kwargs}
            return True
        def delete_config(self, name):
            if name in self.configs: del self.configs[name]; return True
            return False
        def get_active_config_name(self): return self.active_config
        def set_active_config_name(self, name): self.active_config = name
        def get_active_config(self): return self.get_config(self.active_config)
        def _decrypt(self, data): return f"decrypted_{data}" # Mock decrypt

    # 替换真实的管理器为Mock对象
    LLMConfigManager = MockLLMConfigManager

    # 模拟 LLMClient 用于测试连接
    class MockLLMClient:
        def __init__(self, api_key, api_url, model):
            print(f"MockLLMClient initialized with url={api_url}, key={api_key}, model={model}")
            self.api_key = api_key
            self.api_url = api_url
            self.model = model
        def test_connection(self):
            print("MockLLMClient: Testing connection...")
            if "openai" in self.api_url and self.api_key and "gpt" in self.model:
                print("MockLLMClient: OpenAI connection successful.")
                return True
            elif "localhost" in self.api_url and "llama" in self.model:
                 print("MockLLMClient: Localhost connection successful.")
                 return True
            else:
                print("MockLLMClient: Connection failed.")
                return False

    # 在测试环境中，需要确保能找到这个模拟类
    # 这通常通过修改 sys.path 或更复杂的 mocking 框架完成
    # 这里简单地在全局作用域定义它，并在 _test_connection 中直接使用
    # 注意：这会覆盖真实的 LLMClient 导入，仅用于此测试脚本
    # from ..llm.llm_client import LLMClient # 注释掉真实导入
    LLMClient_real = LLMClient # 保存真实的类以防万一
    LLMClient = MockLLMClient # 用Mock替换

    app = QApplication(sys.argv)
    dialog = LLMSettingsDialog()

    # 连接信号以打印消息
    def on_settings_changed():
        print(">>> Settings Changed signal received!")
    dialog.settings_changed.connect(on_settings_changed)

    dialog.show()
    sys.exit(app.exec_())
