"""
语言模型设置对话框 (支持多配置)

提供管理和配置多个LLM API的界面。
配置使用 QSettings 存储。
"""

import logging
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                            QLineEdit, QPushButton, QLabel, QMessageBox,
                            QGroupBox, QListWidget, QListWidgetItem,
                            QWidget, QSplitter, QInputDialog, QApplication,
                            QSizePolicy) # 添加 QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QFont
from .ui_utils import create_standard_button, add_form_row # <-- 添加 add_form_row 导入

# --- 修改 LLMConfigManager 导入 ---
from config.llm_config_manager import LLMConfigManager
# --- 导入结束 ---

# LLMClient import removed, using LLMService now


class LLMSettingsDialog(QDialog):
    """语言模型设置对话框 (支持多配置, 使用 QSettings)"""

    # 定义信号，当设置被保存或激活配置改变时发射
    settings_changed = pyqtSignal()

    # 修改 __init__ 以接收 llm_service
    def __init__(self, llm_service: 'LLMService', parent=None): # 添加类型提示
        super().__init__(parent)

        self.logger = logging.getLogger('news_analyzer.ui.llm_settings')
        self.config_manager = LLMConfigManager()
        self.llm_service = llm_service # 存储 llm_service 实例
        self.current_config_name = None
        self._api_key_modified = False

        self.setWindowTitle("语言模型配置管理")
        self.setMinimumWidth(750)
        self.setMinimumHeight(500) # 增加高度以容纳更多控件
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()
        self._load_settings() # 加载列表和活动配置

        # 连接编辑框的 textChanged 信号以标记修改
        self._connect_dirty_signals()

    def _init_ui(self):
        """初始化UI (恢复编辑功能)"""
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

        # --- 使用辅助函数创建添加/删除按钮 ---
        list_button_layout = QHBoxLayout()
        add_button = create_standard_button(
            text="添加",
            icon_path="list-add", # 使用主题图标名称
            tooltip="添加一个新的 LLM 配置"
        )
        add_button.clicked.connect(self._add_config)

        delete_button = create_standard_button(
            text="删除",
            icon_path="list-remove", # 使用主题图标名称
            tooltip="删除选中的 LLM 配置"
        )
        delete_button.clicked.connect(self._delete_config)

        list_button_layout.addWidget(add_button)
        list_button_layout.addWidget(delete_button)
        list_button_layout.addStretch()
        left_layout.addLayout(list_button_layout)
        # --- 添加结束 ---

        splitter.addWidget(left_widget)

        # --- 右侧：配置编辑区域 ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)
        right_layout.setSpacing(15)

        self.edit_group = QGroupBox("配置详情")
        self.edit_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        self.edit_group.setEnabled(False) # 初始禁用，选中后启用
        edit_form_layout = QFormLayout()
        edit_form_layout.setSpacing(10)
        edit_form_layout.setHorizontalSpacing(15) # 增加水平间距
        edit_form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # 配置名称 (不可编辑，通过添加/重命名修改 - 暂时只支持添加/删除)
        self.config_name_label = QLabel("<i>未选择配置</i>")
        self.config_name_label.setWordWrap(True) # 允许标签文本换行
        self.config_name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # 使用辅助函数添加行 (注意：add_form_row 尚未导入，稍后添加)
        add_form_row(edit_form_layout, "配置名称:", self.config_name_label)

        # API URL (可编辑)
        self.api_url_edit = QLineEdit()
        add_form_row(edit_form_layout, "API端点URL:", self.api_url_edit)

        # API 密钥 (可编辑，带可见性切换)
        api_key_layout = QHBoxLayout()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password) # 默认隐藏
        self.api_key_edit.textChanged.connect(self._mark_api_key_modified) # 连接特定信号
        api_key_layout.addWidget(self.api_key_edit)

        # 使用辅助函数创建显示/隐藏按钮
        self.show_key_button = create_standard_button(
            text="", # 无文本
            icon_path="view-reveal", # 尝试加载主题图标
            tooltip="显示/隐藏 API 密钥",
            fixed_size=QSize(24, 24) # 保持小尺寸
        )
        self.show_key_button.setCheckable(True)
        self.show_key_button.setIconSize(QSize(16, 16))
        # 如果主题图标加载失败，设置备用文本
        if self.show_key_button.icon().isNull():
            self.show_key_button.setText("[👁]") # 使用 Emoji 或简单字符

        self.show_key_button.toggled.connect(self._toggle_key_visibility)
        api_key_layout.addWidget(self.show_key_button)
        api_key_layout.setContentsMargins(0,0,0,0) # 移除布局边距
        add_form_row(edit_form_layout, "API密钥:", api_key_layout)

        # 模型名称 (可编辑)
        self.model_name_edit = QLineEdit()
        add_form_row(edit_form_layout, "默认模型:", self.model_name_edit)

        # --- 高级参数编辑 ---
        adv_label = QLabel("--- 高级参数 (可选) ---")
        # addRow can take a single widget spanning both columns
        edit_form_layout.addRow(adv_label) # Keep original addRow for single widget span

        self.temperature_edit = QLineEdit("0.7") # 提供默认值
        add_form_row(edit_form_layout, "温度 (Temperature):", self.temperature_edit)

        self.max_tokens_edit = QLineEdit("2048") # 提供默认值
        add_form_row(edit_form_layout, "最大Token数 (Max Tokens):", self.max_tokens_edit)

        self.system_prompt_edit = QLineEdit()
        add_form_row(edit_form_layout, "系统提示 (System Prompt):", self.system_prompt_edit)

        self.timeout_edit = QLineEdit("60") # 提供默认值
        add_form_row(edit_form_layout, "超时 (Timeout, 秒):", self.timeout_edit)
        # --- 高级参数结束 ---

        self.edit_group.setLayout(edit_form_layout)
        right_layout.addWidget(self.edit_group)

        # 使用辅助函数创建右侧按钮
        edit_button_layout = QHBoxLayout()
        self.save_config_button = create_standard_button(
            text="保存当前配置",
            icon_path="document-save",
            tooltip="保存对当前选中配置的修改"
        )
        self.save_config_button.setEnabled(False) # 初始禁用
        self.save_config_button.clicked.connect(self._save_current_config)

        self.activate_button = create_standard_button(
            text="设为活动配置",
            icon_path="emblem-ok",
            tooltip="将当前选中的配置设为应用程序使用的活动配置"
        )
        self.activate_button.setEnabled(False) # 初始禁用
        self.activate_button.clicked.connect(self._activate_config)

        self.test_button = create_standard_button(
            text="测试当前配置",
            icon_path="network-transmit-receive",
            tooltip="使用当前编辑框中的设置测试与 LLM 服务的连接"
        )
        self.test_button.setEnabled(False) # 初始禁用
        self.test_button.clicked.connect(self._test_connection)

        edit_button_layout.addWidget(self.save_config_button)
        edit_button_layout.addWidget(self.activate_button)
        edit_button_layout.addWidget(self.test_button)
        edit_button_layout.addStretch()

        right_layout.addLayout(edit_button_layout)
        right_layout.addStretch() # 将编辑区推到顶部

        splitter.addWidget(right_widget)

        # 设置分割器初始比例
        splitter.setSizes([250, 500])

        main_layout.addWidget(splitter)

        # --- 底部按钮布局 (OK/Cancel) ---
        bottom_button_layout = QHBoxLayout()
        bottom_button_layout.addStretch()

        # 使用辅助函数创建关闭按钮
        close_button = create_standard_button(text="关闭", tooltip="关闭设置对话框")
        close_button.clicked.connect(self.reject)
        bottom_button_layout.addWidget(close_button)

        main_layout.addLayout(bottom_button_layout)

    def _connect_dirty_signals(self):
        """连接编辑框信号以标记修改 (简化，只用于保存按钮状态)"""
        # 简单的实现：任何编辑框内容改变都启用保存按钮
        # 注意：这可能不够精确，更好的方法是比较初始值和当前值
        self.api_url_edit.textChanged.connect(lambda: self.save_config_button.setEnabled(True))
        # api_key_edit 的修改由 _mark_api_key_modified 处理
        self.model_name_edit.textChanged.connect(lambda: self.save_config_button.setEnabled(True))
        self.temperature_edit.textChanged.connect(lambda: self.save_config_button.setEnabled(True))
        self.max_tokens_edit.textChanged.connect(lambda: self.save_config_button.setEnabled(True))
        self.system_prompt_edit.textChanged.connect(lambda: self.save_config_button.setEnabled(True))
        self.timeout_edit.textChanged.connect(lambda: self.save_config_button.setEnabled(True))

    def _mark_api_key_modified(self):
        """当 API Key 编辑框内容改变时调用"""
        self._api_key_modified = True
        self.save_config_button.setEnabled(True) # 同时启用保存按钮

    def _load_settings(self):
        """加载配置列表和活动配置"""
        self._populate_config_list()
        # 选中项改变会自动调用 _on_config_selected 来处理按钮状态

    def _populate_config_list(self):
        """填充左侧的配置列表"""
        current_selection_name = self.current_config_name # 保存当前选中项
        self.config_list_widget.clear()
        config_names = self.config_manager.get_config_names()
        active_config_name = self.config_manager.get_active_config_name()
        item_to_select = None
        for name in config_names: # get_config_names 已排序
            item_text = name
            item = QListWidgetItem()
            if name == active_config_name:
                item_text += " (活动)"
                font = QFont()
                font.setBold(True)
                item.setFont(font)
                # 尝试加载图标，如果失败则忽略
                try:
                    icon = QIcon.fromTheme("emblem-default", QIcon(":/icons/active.png"))
                    if not icon.isNull():
                        item.setIcon(icon)
                except Exception as e:
                    self.logger.warning(f"Failed to load icon for active item: {e}")

            item.setText(item_text)
            self.config_list_widget.addItem(item)
            # 恢复之前的选中项
            if name == current_selection_name:
                item_to_select = item

        if item_to_select:
            self.config_list_widget.setCurrentItem(item_to_select)
        elif self.config_list_widget.count() > 0:
             self.config_list_widget.setCurrentRow(0) # 选中第一个
        else:
             # 如果列表为空，确保编辑区被清空和禁用
             self._clear_edit_fields()
             self.edit_group.setEnabled(False)
             self.save_config_button.setEnabled(False)
             self.activate_button.setEnabled(False)
             self.test_button.setEnabled(False)


    def _on_config_selected(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        """当列表选中项改变时，加载配置到右侧编辑区"""
        # 简单的未保存更改检查 (可以改进)
        if self.save_config_button.isEnabled() and previous_item:
             prev_name = previous_item.text().replace(" (活动)", "")
             reply = QMessageBox.question(self, "未保存更改",
                                          f"配置 '{prev_name}' 已被修改但未保存。\n"
                                          "要放弃更改并切换吗？",
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
             if reply == QMessageBox.No:
                 # 阻止切换，恢复选中上一个项目
                 self.config_list_widget.blockSignals(True)
                 self.config_list_widget.setCurrentItem(previous_item)
                 self.config_list_widget.blockSignals(False)
                 return

        # 重置保存按钮状态和 API Key 修改标记
        self.save_config_button.setEnabled(False)
        self._api_key_modified = False
        # 重置 API Key 可见性按钮状态
        self.show_key_button.setChecked(False) # 确保切换时总是隐藏

        if current_item:
            config_name_with_marker = current_item.text()
            config_name = config_name_with_marker.replace(" (活动)", "")
            self.current_config_name = config_name
            config = self.config_manager.get_config(config_name)

            if config:
                # --- 阻止信号 ---
                self.api_url_edit.blockSignals(True)
                self.api_key_edit.blockSignals(True)
                self.model_name_edit.blockSignals(True)
                self.temperature_edit.blockSignals(True)
                self.max_tokens_edit.blockSignals(True)
                self.system_prompt_edit.blockSignals(True)
                self.timeout_edit.blockSignals(True)

                # --- 填充编辑控件 ---
                self.config_name_label.setText(f"<b>{config_name}</b>")
                self.api_url_edit.setText(config.get('api_url', ''))

                # API Key: 如果存在，显示 ******
                if config.get('api_key'):
                    self.api_key_edit.setText("******") # 显示占位符
                    self.api_key_edit.setPlaceholderText("输入新密钥以覆盖，或留空")
                else:
                    self.api_key_edit.setText("")
                    self.api_key_edit.setPlaceholderText("请输入API密钥")
                # 确保 EchoMode 是 Password
                self.api_key_edit.setEchoMode(QLineEdit.Password)

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

                # --- 启用/禁用按钮 ---
                self.edit_group.setEnabled(True)
                self.save_config_button.setEnabled(False) # 刚加载，未修改，禁用保存
                self.activate_button.setEnabled(True)
                self.test_button.setEnabled(True)
            else:
                # 配置获取失败
                self.logger.warning(f"Could not retrieve config details for '{config_name}' even though it's in the list.")
                self._clear_edit_fields()
                self.edit_group.setEnabled(False)
                self.save_config_button.setEnabled(False)
                self.activate_button.setEnabled(False)
                self.test_button.setEnabled(False)
        else:
            # 没有选中项
            self.current_config_name = None
            self._clear_edit_fields()
            self.edit_group.setEnabled(False)
            self.save_config_button.setEnabled(False)
            self.activate_button.setEnabled(False)
            self.test_button.setEnabled(False)

    def _clear_edit_fields(self):
        """清除右侧编辑区域的内容"""
        # --- 阻止信号 ---
        self.api_url_edit.blockSignals(True)
        self.api_key_edit.blockSignals(True)
        self.model_name_edit.blockSignals(True)
        self.temperature_edit.blockSignals(True)
        self.max_tokens_edit.blockSignals(True)
        self.system_prompt_edit.blockSignals(True)
        self.timeout_edit.blockSignals(True)
        # --- 清除 ---
        self.config_name_label.setText("<i>未选择配置</i>")
        self.api_url_edit.clear()
        self.api_key_edit.clear()
        self.api_key_edit.setPlaceholderText("")
        self.model_name_edit.clear()
        self.temperature_edit.setText("0.7") # 恢复默认值
        self.max_tokens_edit.setText("2048") # 恢复默认值
        self.system_prompt_edit.clear()
        self.timeout_edit.setText("60")     # 恢复默认值
        # --- 恢复信号 ---
        self.api_url_edit.blockSignals(False)
        self.api_key_edit.blockSignals(False)
        self.model_name_edit.blockSignals(False)
        self.temperature_edit.blockSignals(False)
        self.max_tokens_edit.blockSignals(False)
        self.system_prompt_edit.blockSignals(False)
        self.timeout_edit.blockSignals(False)
        # --- 重置状态 ---
        self.current_config_name = None
        self._api_key_modified = False
        self.save_config_button.setEnabled(False) # 清空后禁用保存

    def _add_config(self):
        """添加新配置"""
        name, ok = QInputDialog.getText(self, "添加新配置", "请输入配置名称:")
        if ok and name:
            if name in self.config_manager.get_config_names():
                QMessageBox.warning(self, "名称已存在", f"配置名称 '{name}' 已存在，请使用其他名称。")
                return
            # 添加一个空配置
            if self.config_manager.add_or_update_config(name): # 提供默认值
                self._populate_config_list()
                # 选中新添加的项
                items = self.config_list_widget.findItems(name, Qt.MatchExactly)
                if items:
                    self.config_list_widget.setCurrentItem(items[0])
                    # 新添加的项，启用编辑和保存
                    self.edit_group.setEnabled(True)
                    self.save_config_button.setEnabled(True) # 允许立即保存空配置或编辑后保存
                    self.activate_button.setEnabled(True)
                    self.test_button.setEnabled(True) # 允许测试（可能失败）
                QMessageBox.information(self, "提示", f"已添加配置 '{name}'，请在右侧填写详细信息并保存。")
            else:
                 QMessageBox.critical(self, "错误", f"添加配置 '{name}' 失败。")

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
                self._populate_config_list() # 列表刷新后会自动处理选中和编辑区状态
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
            api_key_to_save = old_config.get('api_key', '') if old_config else ''

        # 再次检查 api_key_to_save 是否为 None (理论上不应该)
        if api_key_to_save is None:
            api_key_to_save = "" # 保证至少是空字符串

        # 如果用户清空了密钥，提醒一下 (仅当之前有密钥时)
        if self._api_key_modified and not api_key_to_save:
             old_config = self.config_manager.get_config(name)
             if old_config and old_config.get('api_key'):
                 reply = QMessageBox.question(self, "确认清空密钥", f"您似乎已清空配置 '{name}' 的API密钥，确定要保存吗？",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                 if reply == QMessageBox.No:
                     return # 用户取消

        # 基本验证 (可以添加更严格的 URL 验证等)
        # if not api_url:
        #     QMessageBox.warning(self, "输入不完整", "API端点URL不能为空。")
        #     return

        # 获取高级参数，提供默认值并进行类型转换
        try:
            temperature = float(self.temperature_edit.text() or 0.7)
            max_tokens = int(self.max_tokens_edit.text() or 2048)
            system_prompt = self.system_prompt_edit.text() # 已经是字符串
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

        if self.config_manager.add_or_update_config(name, api_key_to_save, api_url, model_name, **extra_args):
            self._api_key_modified = False # 保存成功后重置密钥修改标记
            self.save_config_button.setEnabled(False) # 保存成功后禁用保存按钮

            # 如果保存了密钥（无论是新输入的还是保留旧的），显示 ******
            if api_key_to_save:
                # 阻止信号避免触发 modified 标记
                self.api_key_edit.blockSignals(True)
                self.api_key_edit.setText("******")
                self.api_key_edit.setPlaceholderText("输入新密钥以覆盖，或留空")
                self.api_key_edit.blockSignals(False)
            else:
                self.api_key_edit.blockSignals(True)
                self.api_key_edit.setText("")
                self.api_key_edit.setPlaceholderText("请输入API密钥")
                self.api_key_edit.blockSignals(False)

            # 确保 EchoMode 是 Password (如果之前切换过)
            self.show_key_button.setChecked(False) # 取消选中状态
            self.api_key_edit.setEchoMode(QLineEdit.Password)

            # 可能需要重新填充列表以更新显示（例如粗体）- 如果名称或活动状态改变
            # self._populate_config_list() # 保存操作不改变名称或活动状态，通常不需要
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

        # 检查是否有未保存的更改
        if self.save_config_button.isEnabled():
             reply = QMessageBox.question(self, "未保存更改",
                                          f"当前配置已被修改但未保存。\n"
                                          "要放弃更改并激活吗？",
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
             if reply == QMessageBox.No:
                 return # 用户取消激活

        config_name = current_item.text().replace(" (活动)", "") # 获取真实名称
        self.config_manager.set_active_config_name(config_name)
        self._populate_config_list() # 更新列表显示（粗体和图标）
        self.settings_changed.emit() # 发射信号通知主窗口
        # 激活后，当前配置没有变化，保存按钮状态不变（如果之前禁用则保持禁用）
        # QMessageBox.information(self, "已激活", f"配置 '{config_name}' 已被设为活动配置。") # 可以省略提示

    def _test_connection(self):
        """使用当前编辑框中的设置测试与 LLM 服务的连接 (使用 LLMService)"""
        if not self.current_config_name:
            QMessageBox.warning(self, "未选择", "请先选择一个配置进行测试。")
            return

        if not self.llm_service:
             QMessageBox.critical(self, "错误", "LLM 服务不可用，无法执行测试。")
             return

        # 从编辑框收集配置
        name_to_test = self.current_config_name
        api_url = self.api_url_edit.text().strip()
        model_name = self.model_name_edit.text().strip()

        # 处理 API Key (与保存逻辑类似，但获取当前输入)
        api_key_to_test = ""
        current_key_text = self.api_key_edit.text()
        if current_key_text != "******": # 如果不是占位符，使用当前文本
            api_key_to_test = current_key_text.strip()
        else: # 如果是占位符，尝试获取已保存的密钥
            saved_config = self.config_manager.get_config(name_to_test)
            if saved_config:
                api_key_to_test = saved_config.get('api_key', '')

        # 获取高级参数
        try:
            temperature = float(self.temperature_edit.text().strip() or 0.7)
            max_tokens = int(self.max_tokens_edit.text().strip() or 2048)
            timeout = int(self.timeout_edit.text().strip() or 60)
        except ValueError:
            QMessageBox.warning(self, "输入错误", "高级参数（温度、最大Token、超时）必须是有效的数字。")
            return

        # 准备配置字典
        config_to_test = {
            'name': name_to_test, # 用于 Provider 类型推断
            'api_url': api_url,
            'api_key': api_key_to_test,
            'model': model_name,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'timeout': timeout
            # system_prompt 不直接用于连接测试
        }

        # 禁用按钮，显示等待光标
        self.test_button.setEnabled(False)
        self.test_button.setText("正在测试...") # 更新按钮文本
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents() # 强制处理事件

        try:
            # 调用 LLMService 的新测试方法
            success, message = self.llm_service.test_connection_with_config(config_to_test)

            if success:
                QMessageBox.information(self, "连接测试成功", message)
            else:
                QMessageBox.critical(self, "连接测试失败", message)

        except Exception as e:
            self.logger.error(f"调用 LLMService 测试连接时发生意外错误: {e}", exc_info=True)
            QMessageBox.critical(self, "测试出错", f"执行测试时发生意外错误:\n{e}")
        finally:
            # 恢复光标和按钮状态
            QApplication.restoreOverrideCursor()
            self.test_button.setEnabled(True)
            self.test_button.setText("测试当前配置") # 恢复按钮文本

    def _toggle_key_visibility(self, checked):
        """切换API密钥的可见性"""
        if checked:
            # --- 显示明文 ---
            key_to_show = ""
            # 优先使用用户当前输入的内容（如果不是占位符）
            current_text = self.api_key_edit.text()
            if self._api_key_modified and current_text != "******":
                key_to_show = current_text # 显示用户输入的（无需 strip）
            # 否则，尝试从配置管理器获取已保存的密钥
            elif self.current_config_name:
                config = self.config_manager.get_config(self.current_config_name)
                if config:
                    key_to_show = config.get('api_key', '') # 获取原始密钥

            # 设置为 Normal 模式并显示获取到的密钥
            self.api_key_edit.setEchoMode(QLineEdit.Normal)
            # 阻止信号，避免 setText 触发 modified 标记
            self.api_key_edit.blockSignals(True)
            self.api_key_edit.setText(key_to_show)
            self.api_key_edit.blockSignals(False)


            # 更新图标/文字为“隐藏”状态
            conceal_icon = QIcon.fromTheme("view-conceal")
            if conceal_icon.isNull(): conceal_icon = self.style().standardIcon(QApplication.style().SP_DialogNoButton)
            self.show_key_button.setIcon(conceal_icon)
            if conceal_icon.isNull(): self.show_key_button.setText("[隐藏]")
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
                # 阻止信号，避免 setText 触发 modified 标记
                self.api_key_edit.blockSignals(True)
                # 即使之前显示的是明文，现在也强制设为 ******
                self.api_key_edit.setText("******")
                self.api_key_edit.blockSignals(False)
            # else: # 如果没有密钥，保持当前文本（可能是空）

            # 更新图标/文字为“显示”状态
            reveal_icon = QIcon.fromTheme("view-reveal")
            if reveal_icon.isNull(): reveal_icon = self.style().standardIcon(QApplication.style().SP_DialogYesButton)
            self.show_key_button.setIcon(reveal_icon)
            if reveal_icon.isNull(): self.show_key_button.setText("[显示]")

    # --- 重写 accept 和 reject 以处理未保存的更改 ---
    def accept(self):
        """尝试保存并关闭"""
        if self.save_config_button.isEnabled():
             reply = QMessageBox.question(self, "未保存更改",
                                          f"当前配置已被修改但未保存。\n"
                                          "是否保存更改？",
                                          QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                          QMessageBox.Cancel) # 默认取消
             if reply == QMessageBox.Save:
                 self._save_current_config()
                 # 检查保存是否成功 (如果保存失败，不应关闭)
                 if self.save_config_button.isEnabled(): # 如果保存后按钮仍启用，说明可能失败或逻辑问题
                      return # 不关闭对话框
                 super().accept() # 保存成功，关闭
             elif reply == QMessageBox.Discard:
                 super().accept() # 放弃更改，关闭
             else: # Cancel
                 return # 不关闭对话框
        else:
            super().accept() # 没有未保存更改，直接关闭

    def reject(self):
        """关闭或取消"""
        if self.save_config_button.isEnabled():
             reply = QMessageBox.question(self, "未保存更改",
                                          f"当前配置已被修改但未保存。\n"
                                          "要放弃更改并关闭吗？",
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
             if reply == QMessageBox.Yes:
                 super().reject() # 放弃更改，关闭
             else:
                 return # 不关闭对话框
        else:
            super().reject() # 没有未保存更改，直接关闭


# --- 用于独立测试对话框 ---
if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG) # 启用日志记录

    # 使用真实的 LLMConfigManager (它现在使用 QSettings)
    # 清理之前的 QSettings 测试数据
    settings = QSettings("NewsAnalyzer", "NewsAggregator")
    settings.remove("llm_configs")
    settings.remove("llm/active_config_name")
    print("--- Cleared previous QSettings test data ---")


    # 模拟 LLMClient 用于测试连接
    class MockLLMClient:
        def __init__(self, provider, api_key, api_url, model, **kwargs):
            print(f"MockLLMClient initialized with provider={provider}, url={api_url}, key={api_key}, model={model}, kwargs={kwargs}")
            self.api_key = api_key
            self.api_url = api_url
            self.model = model
            self.provider = provider

        def test_connection(self):
            print(f"MockLLMClient: Testing connection for {self.provider}...")
            # 模拟 Ollama 成功条件
            if "ollama" in self.provider.lower() and "localhost" in self.api_url:
                 print("MockLLMClient: Ollama connection successful.")
                 return True, "模拟 Ollama 连接成功"
            # 模拟其他需要 Key 的成功条件
            elif self.api_key and self.api_url:
                 print(f"MockLLMClient: Connection successful for {self.provider}.")
                 return True, f"模拟 {self.provider} 连接成功"
            else:
                print("MockLLMClient: Connection failed.")
                return False, "模拟连接失败：URL 或 API Key 无效"

    # 替换真实的 LLMClient
    if LLMClient is not None:
        LLMClient_real = LLMClient
    LLMClient = MockLLMClient


    app = QApplication(sys.argv)
    dialog = LLMSettingsDialog()

    # 连接信号以打印消息
    def on_settings_changed():
        print(">>> Settings Changed signal received!")
    dialog.settings_changed.connect(on_settings_changed)

    dialog.show()
    sys.exit(app.exec_())
