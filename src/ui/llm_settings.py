"""
语言模型设置对话框 (支持多配置)

提供管理和配置多个LLM API的界面。
配置元数据使用 QSettings 存储，密钥通过环境加载。
"""

import logging
import os # Needed for os.getenv if used directly (though config_manager handles it)
from typing import Dict, Any, Optional, Callable, Iterator, List, Union # ADDED Optional, List, Union here for comprehensive type hinting
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox,
    QGroupBox, QListWidget, QListWidgetItem,
    QWidget, QSplitter, QInputDialog, QApplication,
    QStyle, QSizePolicy, QComboBox
)
from PySide6.QtCore import Qt, Signal as pyqtSignal, QSize, Slot as pyqtSlot
from PySide6.QtGui import QIcon, QFont
from src.ui.ui_utils import create_standard_button, add_form_row

from src.ui.viewmodels.llm_settings_viewmodel import LLMSettingsViewModel
from src.llm.llm_service import LLMService


class LLMSettingsDialog(QDialog):
    """语言模型设置对话框 (支持多配置, 使用 ViewModel)"""

    settings_changed = pyqtSignal() # Emitted when active config changes or metadata saved
    rejected_and_deleted = pyqtSignal() # Example signal, maybe not needed

    def __init__(self, view_model: LLMSettingsViewModel, parent=None):
        super().__init__(parent)

        self.logger = logging.getLogger('news_analyzer.ui.llm_settings')
        self.logger.info("Initializing LLMSettingsDialog...")
        self.view_model = view_model # Store the ViewModel instance
        self._current_provider_type = None
        self.is_loading_config = False

        self.setWindowTitle("语言模型配置管理")
        self.setMinimumWidth(750)
        self.setMinimumHeight(500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint | Qt.WindowCloseButtonHint)

        self._init_ui()
        self._connect_viewmodel_signals()
        self._connect_dirty_signals()

        # Trigger initial data load from ViewModel
        self.view_model.load_initial_data()
        self.logger.info("LLMSettingsDialog initialized and initial data load triggered.")

    def _init_ui(self):
        """Initializes the UI components."""
        self.logger.debug("Initializing UI components for LLMSettingsDialog...")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal)

        # --- Left Panel: Config List & Buttons ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        list_label = QLabel("可用配置:")
        self.config_list_widget = QListWidget()
        self.config_list_widget.currentItemChanged.connect(self._on_config_selected)
        self.config_list_widget.itemDoubleClicked.connect(self._activate_selected_config_from_ui)
        left_layout.addWidget(list_label)
        left_layout.addWidget(self.config_list_widget)
        list_button_layout = QHBoxLayout()
        self.add_button = create_standard_button(text="添加", icon_path="list-add", tooltip="添加一个新的 LLM 配置")
        self.add_button.clicked.connect(self._add_config)
        self.delete_button = create_standard_button(text="删除", icon_path="list-remove", tooltip="删除选中的 LLM 配置")
        self.delete_button.clicked.connect(self._delete_config)
        self.delete_button.setEnabled(False) # Ensure delete button is disabled initially
        list_button_layout.addWidget(self.add_button)
        list_button_layout.addWidget(self.delete_button)
        list_button_layout.addStretch()
        left_layout.addLayout(list_button_layout)
        splitter.addWidget(left_widget)

        # --- Right Panel: Config Editor ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)
        right_layout.setSpacing(15)

        self.edit_group = QGroupBox("")
        self.edit_group.setStyleSheet("")
        self.edit_group.setEnabled(False)
        edit_form_layout = QFormLayout()
        edit_form_layout.setContentsMargins(0, 10, 0, 0)
        edit_form_layout.setSpacing(10)
        edit_form_layout.setHorizontalSpacing(15)
        edit_form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.config_name_label = QLabel("<i>未选择配置</i>")
        self.config_name_label.setWordWrap(True)
        self.config_name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        _config_name_desc_label = QLabel("配置名称:")
        edit_form_layout.addRow(_config_name_desc_label, self.config_name_label)

        # --- API URL ---
        self.api_url_label = QLabel("API端点URL:")
        self.api_url_edit = QLineEdit()
        edit_form_layout.addRow(self.api_url_label, self.api_url_edit)

        # --- API Key Input ---
        self.api_key_label = QLabel("API密钥:")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("如果需要，请输入API密钥")
        edit_form_layout.addRow(self.api_key_label, self.api_key_edit)
        
        # --- ENSURE Ollama API Key Message Label is INITIALIZED CORRECTLY ---
        self.ollama_api_key_message_label = QLabel("Ollama 通常在本地运行，不需要 API 密钥。")
        self.ollama_api_key_message_label.setStyleSheet("font-style: italic; color: gray;")
        self.ollama_api_key_message_label.setWordWrap(True)
        self.ollama_api_key_message_label.hide() # Initially hidden
        # Add this label to the form layout with a dummy label for alignment.
        # Ensure 'edit_form_layout' is the correct QFormLayout instance.
        edit_form_layout.addRow(QLabel(" "), self.ollama_api_key_message_label)
        # --- END Ollama Label INITIALIZATION ---

        # --- Model Selection --- (Logic remains similar)
        self.model_name_edit = QLineEdit()
        self.gemini_model_combo = QComboBox()
        self._populate_gemini_models_combo()
        self._model_name_label = QLabel("模型名称:")
        self._gemini_model_label = QLabel("Gemini 模型:")
        edit_form_layout.addRow(self._model_name_label, self.model_name_edit)
        edit_form_layout.addRow(self._gemini_model_label, self.gemini_model_combo)
        self._model_name_label.setVisible(False)
        self.model_name_edit.setVisible(False)
        self._gemini_model_label.setVisible(False)
        self.gemini_model_combo.setVisible(False)

        # --- Advanced Parameters --- (Logic remains similar)
        adv_label = QLabel("--- 高级参数 (可选) ---")
        edit_form_layout.addRow(adv_label)
        self.temperature_edit = QLineEdit("0.7")
        add_form_row(edit_form_layout, "温度 (Temperature):", self.temperature_edit)
        self.max_tokens_edit = QLineEdit("2048")
        add_form_row(edit_form_layout, "最大Token数 (Max Tokens):", self.max_tokens_edit)
        self.timeout_edit = QLineEdit("60")
        add_form_row(edit_form_layout, "超时 (Timeout, 秒):", self.timeout_edit)

        self.edit_group.setLayout(edit_form_layout)
        right_layout.addWidget(self.edit_group)

        # --- Right Side Buttons --- (Adjust tooltips/text slightly)
        edit_button_layout = QHBoxLayout()
        self.save_config_button = create_standard_button(text="保存配置", icon_path="document-save", tooltip="保存对当前配置元数据（URL、模型等，非密钥）的修改")
        self.save_config_button.setEnabled(False)
        self.save_config_button.clicked.connect(self._save_current_config)
        self.activate_button = create_standard_button(text="设为活动配置", icon_path="emblem-ok", tooltip="将当前选中的配置设为应用程序使用的活动配置")
        self.activate_button.setEnabled(False)
        self.activate_button.clicked.connect(self._activate_selected_config_from_ui)
        self.test_button = create_standard_button(text="测试连接", icon_path="network-transmit-receive", tooltip="使用来自环境的密钥或临时输入的密钥测试连接")
        self.test_button.setEnabled(False)
        self.test_button.clicked.connect(self._test_connection)
        edit_button_layout.addWidget(self.save_config_button)
        edit_button_layout.addWidget(self.activate_button)
        edit_button_layout.addWidget(self.test_button)
        edit_button_layout.addStretch()
        right_layout.addLayout(edit_button_layout)
        right_layout.addStretch()
        splitter.addWidget(right_widget)
        splitter.setSizes([250, 500])
        main_layout.addWidget(splitter)
        self.logger.debug("UI components initialized.")

    def _connect_viewmodel_signals(self):
        """Connects to signals from the ViewModel."""
        self.logger.debug("Connecting ViewModel signals...")
        self.view_model.config_list_changed.connect(self._on_config_list_updated)
        self.view_model.active_config_changed.connect(self._on_active_config_updated) # This will also trigger list re-population with markers
        self.view_model.current_config_loaded.connect(self._on_current_config_loaded)
        self.view_model.config_cleared.connect(self._on_config_cleared)

        self.view_model.save_enabled_changed.connect(self.save_config_button.setEnabled)
        self.view_model.activate_enabled_changed.connect(self.activate_button.setEnabled)
        self.view_model.test_enabled_changed.connect(self.test_button.setEnabled)
        self.view_model.delete_enabled_changed.connect(self.delete_button.setEnabled)

        self.view_model.test_result_received.connect(self._on_test_result_received)
        self.view_model.save_status_received.connect(self._on_save_status_received)
        self.view_model.delete_status_received.connect(self._on_delete_status_received)
        self.view_model.add_status_received.connect(self._on_add_status_received)
        self.view_model.activate_status_received.connect(self._on_activate_status_received)
        self.view_model.error_occurred.connect(self._on_error_occurred)
        self.logger.debug("ViewModel signals connected.")

    def _connect_dirty_signals(self):
        """Connects signals for metadata changes to notify the ViewModel."""
        self.logger.debug("Connecting dirty signals for form fields...")
        # Now these will call the ViewModel's method to update its internal state and dirty flag.
        # The ViewModel will then emit save_enabled_changed.
        self.api_url_edit.textChanged.connect(
            lambda text: self.view_model.update_current_config_field('api_url', text)
        )
        self.api_key_edit.textChanged.connect(
            lambda text: self.view_model.update_current_config_field('api_key', text)
        )
        self.model_name_edit.textChanged.connect(
            lambda text: self.view_model.update_current_config_field('model', text)
        )
        self.gemini_model_combo.currentTextChanged.connect( # Use currentTextChanged for QComboBox
            lambda text: self.view_model.update_current_config_field('model', text)
        )
        self.temperature_edit.textChanged.connect(
            lambda text: self.view_model.update_current_config_field('temperature', text)
        )
        self.max_tokens_edit.textChanged.connect(
            lambda text: self.view_model.update_current_config_field('max_tokens', text)
        )
        self.timeout_edit.textChanged.connect(
            lambda text: self.view_model.update_current_config_field('timeout', text)
        )
        # The api_key_edit_for_test does not affect the dirty state for saving permanent config. (REMOVED COMMENT AS FIELD IS REMOVED)
        self.logger.debug("Dirty signals connected.")

    @pyqtSlot(list) # Slot for config_list_changed signal
    def _on_config_list_updated(self, config_names: list):
        """Fills the list widget when the ViewModel signals a change in config names."""
        self.logger.debug(f"Received config_list_changed signal with names: {config_names}")
        current_selection_name_text = self.config_list_widget.currentItem().text().replace(" (活动)", "") if self.config_list_widget.currentItem() else None
        
        self.config_list_widget.clear()
        active_config_name_from_vm = self.view_model.get_active_config_name()
        self.logger.info(f"_on_config_list_updated: Active config name from ViewModel for marking list: '{active_config_name_from_vm}'")
        item_to_select = None

        for name in config_names:
            item_text = name
            item = QListWidgetItem()
            if name == active_config_name_from_vm:
                item_text += " (活动)"
                font = QFont(); font.setBold(True); item.setFont(font)
                try:
                    icon = QIcon.fromTheme("emblem-default", QIcon(":/icons/active.png"))
                    if not icon.isNull(): item.setIcon(icon)
                except Exception as e:
                    self.logger.warning(f"Failed to load icon for active item: {e}")
            item.setText(item_text)
            self.config_list_widget.addItem(item)
            if name == current_selection_name_text: # Try to reselect previous item
                item_to_select = item
        
        if item_to_select:
            self.config_list_widget.setCurrentItem(item_to_select)
        elif self.config_list_widget.count() > 0:
            self.config_list_widget.setCurrentRow(0) # Select first if nothing else, triggers _on_config_selected
        else:
            self._clear_edit_fields() # This already handles button states for empty list
            self.edit_group.setEnabled(False) # Ensure group is disabled
            # Buttons should be handled by ViewModel signals or _update_button_states_based_on_vm

    @pyqtSlot(str) # Slot for active_config_changed signal
    def _on_active_config_updated(self, active_config_name: str):
        """当活动配置通过 ViewModel 更改时，更新列表中的 '(活动)' 标记。"""
        # This can be simplified if _on_config_list_updated is robust enough
        # to handle active config name changes by re-rendering the list.
        # For now, just log and rely on list_updated to refresh.
        self.logger.info(f"Active configuration updated in ViewModel to: '{active_config_name}'. List will be refreshed.")
        # No direct UI update here, _on_config_list_updated handles the visual state.
        # However, we might want to ensure the list is explicitly told to re-render
        # or that the viewmodel emits config_list_changed. The current VM logic seems to do this.

    def _on_config_selected(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        """Handles selection change in the config list and informs ViewModel."""
        prev_text = previous_item.text() if previous_item else "None"
        curr_text = current_item.text() if current_item else "None"
        self.logger.debug(f"Config selection changed. Previous: '{prev_text}', Current: '{curr_text}'")

        if self.is_loading_config: # Prevent re-entry or unwanted calls during load
            self.logger.debug("_on_config_selected: Skipping due to is_loading_config flag.")
            return

        if self.save_config_button.isEnabled() and previous_item: # Check local save button state
            prev_name_text = prev_text.replace(" (活动)", "")
            # prev_config_data = self._get_form_data() # Need to implement this if we check against form data
            # For now, rely on save button enabled state.
            # Or, ViewModel can manage a dirty flag for the loaded config.

            reply = QMessageBox.question(self, "未保存更改", f"配置元数据 \'{prev_name_text}\' 的表单已修改但未保存。\\n要放弃更改并切换吗？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                self.config_list_widget.blockSignals(True)
                self.config_list_widget.setCurrentItem(previous_item)
                self.config_list_widget.blockSignals(False)
                return
        
        # self.save_config_button.setEnabled(False) # ViewModel will control this via save_enabled_changed
        self.logger.debug(f"UI selected config: {curr_text}. Notifying ViewModel.")
        self.view_model.select_config(curr_text.replace(" (活动)", "")) # Inform ViewModel of selection

    @pyqtSlot(dict)
    def _on_current_config_loaded(self, config_data: dict):
        """当 ViewModel 加载完当前配置数据后调用此槽函数。"""
        self.logger.info(f"_on_current_config_loaded received for config: '{config_data.get('name', 'N/A')}'")
        actual_provider_from_data = config_data.get('provider')
        self.logger.info(f"In _on_current_config_loaded: Raw provider from data: '{actual_provider_from_data}' (type: {type(actual_provider_from_data)})")

        self.is_loading_config = True
        self.edit_group.setEnabled(True)

        # --- BEGIN ADDED: Block signals to prevent premature dirty state ---
        self.api_url_edit.blockSignals(True)
        self.api_key_edit.blockSignals(True)
        self.model_name_edit.blockSignals(True)
        self.gemini_model_combo.blockSignals(True)
        self.temperature_edit.blockSignals(True)
        self.max_tokens_edit.blockSignals(True)
        self.timeout_edit.blockSignals(True)
        # --- END ADDED ---

        try:
            name_to_display = config_data.get('name', "")
            self.logger.info(f"_on_current_config_loaded processing config: '{name_to_display}'")

            is_active = (name_to_display == self.view_model.get_active_config_name())
            is_default = False # Placeholder

            formatted_name_for_label = self._format_config_name_for_display(name_to_display, is_active, is_default)
            self.logger.info(f"Setting config_name_label text to: '{formatted_name_for_label}'")
            self.config_name_label.setText(formatted_name_for_label)

            raw_provider = config_data.get('provider')
            provider_type = str(raw_provider).strip().lower() if raw_provider is not None else "" # Ensure lowercase for comparison
            self.logger.info(f"In _on_current_config_loaded: Processed provider_type: '{provider_type}'")
            
            self.api_url_edit.setText(config_data.get('api_url', ''))
            
            api_key_value = config_data.get('api_key', '')
            if isinstance(api_key_value, list):
                self.api_key_edit.setText(str(api_key_value[0]) if api_key_value else '')
            else:
                self.api_key_edit.setText(str(api_key_value))
            
            # --- MODIFIED: Model field population ---
            model_value = config_data.get('model', '')
            self._update_provider_specific_controls(provider_type) # Update visibility for model input type first
            self._update_visibility(provider_type) # THEN update general visibility for API key fields etc.

            if provider_type == 'google': # Assuming 'google' is the key for Gemini
                self.gemini_model_combo.setCurrentText(model_value)
                self.model_name_edit.setText('') # Clear the other one
                self.logger.debug(f"Set Gemini model combo to '{model_value}', cleared generic model edit.")
            else:
                self.model_name_edit.setText(model_value)
                self.gemini_model_combo.setCurrentIndex(-1) # Clear selection or set to a placeholder
                self.logger.debug(f"Set generic model edit to '{model_value}', cleared Gemini combo.")
            # --- END MODIFIED ---

            temperature_value = config_data.get('temperature', 0.7)
            if isinstance(temperature_value, float):
                self.temperature_edit.setText(f"{temperature_value:.1f}")
            else:
                self.temperature_edit.setText(str(temperature_value)) 
            
            self.max_tokens_edit.setText(str(config_data.get('max_tokens', 2048)))
            self.timeout_edit.setText(str(config_data.get('timeout', 60)))

            self._current_provider_type = provider_type
            self.logger.debug(f"Set _current_provider_type to: {self._current_provider_type}")

            if is_active:
                self.logger.info(f"Active configuration '{name_to_display}' loaded. Emitting settings_changed.")
                self.settings_changed.emit()

            self.logger.info(f"Finished loading config '{name_to_display}' into UI form.")

        except Exception as e:
            self.logger.error(f"Error in _on_current_config_loaded: {e}", exc_info=True)
            self.edit_group.setEnabled(False) # Disable group on error
            # self.is_loading_config = False # Already in finally
            self.logger.error("Failed to load config into UI form due to an exception.") # MODIFIED: More specific log
        finally:
            # --- BEGIN ADDED: Unblock signals ---
            self.api_url_edit.blockSignals(False)
            self.api_key_edit.blockSignals(False)
            self.model_name_edit.blockSignals(False)
            self.gemini_model_combo.blockSignals(False)
            self.temperature_edit.blockSignals(False)
            self.max_tokens_edit.blockSignals(False)
            self.timeout_edit.blockSignals(False)
            # --- END ADDED ---
            self.is_loading_config = False

    @pyqtSlot() # Slot for config_cleared signal
    def _on_config_cleared(self):
        """当 ViewModel 通知配置选择已清除时调用。"""
        self.logger.info("Received config_cleared signal from ViewModel. Clearing edit fields and disabling group.")
        self._clear_edit_fields()
        self.edit_group.setEnabled(False)
        # Button states should be updated by ViewModel via their specific 'enabled_changed' signals

    # --- UI Action Handlers (now mostly delegate to ViewModel) ---

    def _get_form_data(self) -> dict:
        """收集当前表单中的所有元数据，用于保存。
        API Key 将通过 ViewModel 从原始数据或 QSettings 获取，这里不直接处理永久 API Key。
        """
        # Ensure _current_provider_type is up-to-date, especially if provider can be changed in UI
        # For now, it's set when a config is loaded. If a provider_combo is added, it should update _current_provider_type.
        provider_type_to_save = self._current_provider_type
        
        # Determine which model value to use based on visibility
        model_value = ""
        if self.gemini_model_combo.isVisible():
            model_value = self.gemini_model_combo.currentText()
        elif self.model_name_edit.isVisible(): # Check generic model edit visibility
            model_value = self.model_name_edit.text().strip()
        # Add other provider-specific combo boxes here if they are introduced
        # elif self.some_other_provider_combo.isVisible():
        # model_value = self.some_other_provider_combo.currentText()
        else:
            # Fallback or if no model field is visible for the current provider (might indicate an issue)
            self.logger.warning(f"No visible model input field for provider '{provider_type_to_save}'. Model value will be empty in form data.")

        data = {
            'name': self.config_name_label.text().replace(" (活动)", "").replace("<i>", "").replace("</i>", "").strip(), # 从标签获取名称
            'api_url': self.api_url_edit.text().strip(),
            'api_key': self.api_key_edit.text().strip(), # STRIPPED API KEY HERE
            'model': model_value,
            'temperature': self.temperature_edit.text().strip(),
            'max_tokens': self.max_tokens_edit.text().strip(),
            'timeout': self.timeout_edit.text().strip(),
            'provider': provider_type_to_save # Ensure this is set when a config is loaded or provider changed
        }
        self.logger.debug(f"_get_form_data collected: {data}")
        return data

    def _get_form_data_for_test(self) -> dict:
        """收集当前表单中的所有元数据，用于测试连接。
        API Key 不从此表单获取，ViewModel会从原始配置中获取。
        """
        # This method now simply returns the same data as _get_form_data.
        # The ViewModel's test_current_config method will be responsible for
        # fetching the actual API key from its _original_current_config_data.
        data = self._get_form_data()
        self.logger.debug(f"_get_form_data_for_test collected (API key to be handled by ViewModel): {data}")
        return data

    def _add_config(self):
        """Handles the 'Add New Configuration' action."""
        self.logger.debug("Add config button clicked.")
        name, ok = QInputDialog.getText(self, "添加新配置", "输入新配置的名称:")
        if ok and name:
            self.logger.info(f"User initiated add new config with name: '{name}'")
            self.view_model.add_new_config(name)
        elif ok and not name:
             self.logger.warning("User tried to add config with empty name.")
             QMessageBox.warning(self, "输入错误", "配置名称不能为空。")
        else:
            self.logger.debug("Add new config dialog cancelled.")

    def _delete_config(self):
        """Handles the 'Delete Configuration' action."""
        self.logger.debug("Delete config button clicked.")
        current_item = self.config_list_widget.currentItem()
        if not current_item:
            self.logger.warning("Delete config attempted without selection.")
            QMessageBox.warning(self, "操作无效", "请先在列表中选择一个配置。")
            return

        config_name_to_delete = current_item.text().replace(" (活动)", "")
        
        reply = QMessageBox.question(self, "确认删除", 
                                     f"确定要删除配置 '{config_name_to_delete}' 吗?\\n此操作无法撤销。",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logger.info(f"User confirmed deletion of config: '{config_name_to_delete}'")
            self.view_model.delete_selected_config(config_name_to_delete)
        else:
            self.logger.debug(f"User cancelled deletion of config: '{config_name_to_delete}'")

    def _save_current_config(self):
        """Saves the currently displayed configuration metadata (excluding direct API key input)."""
        self.logger.debug("Save config button clicked.")
        # ViewModel will check if a config is selected and if it's dirty
        # if not self.view_model.current_config_name: # REMOVED - ViewModel handles this
        #     self.logger.warning("Save config attempted without a selected config in ViewModel.")
        #     QMessageBox.warning(self, "无选中配置", "请先选择一个配置或确保配置已加载。")
        #     return
        
        updated_data = self._get_form_data()
        # Use a temporary variable for the config name for logging, if available from label or a robust source
        # current_config_name_for_log = self.config_name_label.text().replace(" (活动)", "").replace("<i>", "").replace("</i>", "").strip()
        # self.logger.info(f"Attempting to save config '{current_config_name_for_log}' with data: {updated_data}")
        # The ViewModel knows its current config name, so direct logging of name here is less critical if VM logs it.
        self.view_model.save_current_config(updated_data)

    def _activate_selected_config_from_ui(self): # Renamed from _activate_config
        """Activates the currently selected configuration via the ViewModel."""
        self.logger.debug("Activate config button/double-click action triggered.")
        # ViewModel will use its internally stored _current_config_name
        # selected_item = self.config_list_widget.currentItem() # Redundant check
        # config_name_from_item = selected_item.text().replace(" (活动)", "") if selected_item else None

        # if not self.view_model.current_config_name: # REMOVED - ViewModel handles this
        #      self.logger.warning(f"Activate config attempted but ViewModel has no current selection. UI item: {config_name_from_item}")
        #      QMessageBox.warning(self, "无选中配置", "请在列表中选择一个配置以激活。")
        #      return

        self.logger.info(f"Requesting ViewModel to activate its current selected config.")
        self.view_model.activate_selected_config()

    def _test_connection(self):
        """Tests the connection for the currently displayed configuration."""
        self.logger.debug("Test connection button clicked.")
        # ViewModel will use its internally stored _current_config_name
        # if not self.view_model.current_config_name: # REMOVED - ViewModel handles this
        #     self.logger.warning("Test connection attempted without a selected config in ViewModel.")
        #     QMessageBox.warning(self, "无选中配置", "请先在列表中选择一个配置以进行测试。")
        #     return

        config_to_test = self._get_form_data_for_test()
        self.logger.info(f"Requesting ViewModel to test its current config with form data: {config_to_test}")
        self.view_model.test_current_config(config_to_test)

    @pyqtSlot(bool, str)
    def _on_test_result_received(self, success: bool, message: str):
        """Handles test result from ViewModel."""
        self.logger.info(f"UI received test_result_received signal: Success={success}, Message='{message}'")
        if success:
            QMessageBox.information(self, "测试连接", f"连接成功！\n{message}")
        else:
            # For consistency, use warning for failure messages from test
            QMessageBox.warning(self, "测试连接失败", f"连接测试失败。\n原因: {message}")

    @pyqtSlot(bool, str)
    def _on_save_status_received(self, success: bool, message: str):
        """Handles save status from ViewModel."""
        self.logger.info(f"Received save status: Success={success}, Message='{message}'")
        if success:
            QMessageBox.information(self, "保存配置", message)
        else:
            QMessageBox.warning(self, "保存失败", message)

    @pyqtSlot(bool, str)
    def _on_delete_status_received(self, success: bool, message: str):
        """Handles delete status from ViewModel."""
        self.logger.info(f"Received delete status: Success={success}, Message='{message}'")
        if success:
            QMessageBox.information(self, "删除配置", message)
            # self._clear_edit_fields() # ViewModel now emits config_cleared if needed
            # self.edit_group.setEnabled(False) # ViewModel handles this via button states / config_cleared
        else:
            QMessageBox.warning(self, "删除失败", message)

    @pyqtSlot(bool, str)
    def _on_add_status_received(self, success: bool, message: str):
        """Handles add status from ViewModel."""
        self.logger.info(f"Received add status: Success={success}, Message='{message}'")
        if success:
            QMessageBox.information(self, "添加配置", message)
            # The new config should be auto-selected by ViewModel, triggering _on_current_config_loaded
        else:
            QMessageBox.warning(self, "添加失败", message)

    @pyqtSlot(bool, str)
    def _on_activate_status_received(self, success: bool, message: str):
        """Handles activate status from ViewModel."""
        self.logger.info(f"Received activate status: Success={success}, Message='{message}'")
        if success:
            # Update list display for active marker handled by _on_config_list_updated via ViewModel signal
            QMessageBox.information(self, "激活配置", message)
            self.settings_changed.emit() # Also emit general settings_changed on activation
        else:
            QMessageBox.warning(self, "激活失败", message)

    @pyqtSlot(str)
    def _on_error_occurred(self, error_message: str):
        """Handles general errors from ViewModel."""
        self.logger.error(f"Received error from ViewModel: '{error_message}'")
        QMessageBox.critical(self, "发生错误", error_message)

    def _clear_edit_fields(self):
        """Clears the editor fields and resets status."""
        self.logger.debug("Clearing edit fields.")
        # --- Block Signals ---
        self.api_url_edit.blockSignals(True)
        self.api_key_edit.blockSignals(True)
        self.model_name_edit.blockSignals(True)
        self.gemini_model_combo.blockSignals(True)
        self.temperature_edit.blockSignals(True)
        self.max_tokens_edit.blockSignals(True)
        self.timeout_edit.blockSignals(True)
        # self.api_key_edit_for_test.blockSignals(True) # REMOVED
        # --- Clear Controls ---
        self.config_name_label.setText("<i>未选择配置</i>")
        self.api_url_edit.clear()
        self.api_key_edit.clear()
        self.model_name_edit.clear()
        # Reset Gemini combo to the first item (placeholder or actual first model)
        if self.gemini_model_combo.count() > 0:
             self.gemini_model_combo.setCurrentIndex(0)
        self._model_name_label.setVisible(False) # Hide all model related fields initially
        self.model_name_edit.setVisible(False)
        self._gemini_model_label.setVisible(False)
        self.gemini_model_combo.setVisible(False)
        # Add similar logic for other provider-specific model combos if they exist

        self.temperature_edit.setText("0.7") # Reset to default
        self.max_tokens_edit.setText("2048") # Reset to default
        self.timeout_edit.setText("60") # Reset to default
        self._current_provider_type = None # Reset current provider
        self.logger.debug("Edit fields cleared and provider type reset.")
        # --- Unblock Signals ---
        self.api_url_edit.blockSignals(False)
        self.api_key_edit.blockSignals(False)
        self.model_name_edit.blockSignals(False)
        self.gemini_model_combo.blockSignals(False)
        self.temperature_edit.blockSignals(False)
        self.max_tokens_edit.blockSignals(False)
        self.timeout_edit.blockSignals(False)
        # self.api_key_edit_for_test.blockSignals(False) # REMOVED

    def _populate_gemini_models_combo(self):
        """Populates the Gemini models dropdown."""
        # This should ideally come from a config or the llm_service/provider
        self.logger.debug("Populating Gemini models combo box.")
        # Placeholder, actual models should be fetched if dynamic
        # Example from llm_service.py (if it has such a list)
        # try:
        #     gemini_models = LLMService.get_available_models(provider='google') # Hypothetical
        # except Exception as e:
        #     self.logger.warning(f"Could not fetch Gemini models: {e}")
        #     gemini_models = ["gemini-pro", "gemini-1.5-pro-latest", "gemini-ultra"] # Fallback
        
        # For now, using a static list as was implicitly there
        gemini_models = [
            "gemini-1.5-pro-latest",
            "gemini-pro",
            "gemini-1.0-pro", # common alias
            "gemini-pro-vision", # if vision capabilities are relevant
            # Add other relevant Gemini models
        ]
        self.gemini_model_combo.clear()
        self.gemini_model_combo.addItems(gemini_models)
        self.logger.debug(f"Gemini models combo populated with: {gemini_models}")

    def accept(self):
        """Overrides QDialog's accept. Typically for OK/Save actions.
        In this dialog, saving is explicit via 'Save' button.
        This dialog is more for management, so 'accept' might not be directly used,
        or could signify closing and applying the active config if that's the desired UX.
        For now, let's assume close is handled by QDialog default or closeEvent.
        """
        self.logger.debug("Accept (OK) button pressed. Current implementation: default QDialog.accept()")
        super().accept()

    def reject(self):
        """Overrides QDialog's reject. Typically for Cancel/Close actions."""
        self.logger.debug("Reject (Cancel) button pressed. Checking for unsaved changes...")
        # Check for unsaved changes, similar to closeEvent
        if hasattr(self.view_model, 'is_dirty') and self.view_model.is_dirty(): # Check if is_dirty exists
            reply = QMessageBox.question(self, "未保存的更改",
                                         "当前配置有未保存的更改。您确定要关闭并丢弃这些更改吗？",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                self.logger.debug("User chose not to discard unsaved changes on reject.")
                return # Do not close
            else:
                self.logger.info("User chose to discard unsaved changes on reject.")
        super().reject()

    def closeEvent(self, event):
        """Handle unsaved changes before closing."""
        self.logger.debug("Close event triggered for LLMSettingsDialog.")
        if hasattr(self.view_model, 'is_dirty') and self.view_model.is_dirty(): # Check if is_dirty exists
            self.logger.info("Unsaved changes detected on close event.")
            reply = QMessageBox.question(self, "未保存的更改",
                                         "当前配置有未保存的更改。您确定要关闭并丢弃这些更改吗？",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.logger.info("User chose to discard unsaved changes. Accepting close event.")
                event.accept()
            else:
                self.logger.debug("User chose not to discard unsaved changes. Ignoring close event.")
                event.ignore()
        else:
            self.logger.debug("No unsaved changes. Accepting close event.")
            event.accept()

    def _format_config_name_for_display(self, name: str, is_active: bool, is_default: bool) -> str:
        """Formats the configuration name for display, adding markers for active/default status."""
        display_name = name
        if is_active:
            display_name += " (活动)"
        return display_name

    def _update_provider_specific_controls(self, provider_type: Optional[str]):
        """根据提供者类型更新特定于提供者的控件的可见性和内容。"""
        self.logger.debug(f"Updating provider-specific controls for: {provider_type}")

        # Default states
        is_gemini = (provider_type == 'google')
        is_ollama = (provider_type == 'ollama')
        # More providers can be added here

        # Gemini specific controls
        self._gemini_model_label.setVisible(is_gemini)
        self.gemini_model_combo.setVisible(is_gemini)
        if is_gemini and self.gemini_model_combo.count() == 0:
            self._populate_gemini_models_combo() # Populate if not already done

        # Generic model name edit (show if NOT Gemini)
        # For Ollama, we DO want the generic model edit.
        show_generic_model_edit = not is_gemini or is_ollama
        if is_ollama: # Explicitly show for Ollama
            show_generic_model_edit = True
            
        self._model_name_label.setVisible(show_generic_model_edit)
        self.model_name_edit.setVisible(show_generic_model_edit)

        # API Key related messages/statuses
        self.ollama_api_key_message_label.setVisible(is_ollama)
        # self.api_key_status_label.setVisible(not is_ollama and not is_gemini) # Example more complex logic

        # Ensure QFormLayout updates row visibility correctly
        # This is often handled automatically if all widgets in a row are hidden.
        # For explicit control (if needed, usually not for simple cases):
        # self.edit_form_layout.setRowVisible(self.edit_form_layout.getWidgetRow(self._gemini_model_label), is_gemini)
        # self.edit_form_layout.setRowVisible(self.edit_form_layout.getWidgetRow(self._model_name_label), show_generic_model_edit)
        # self.edit_form_layout.setRowVisible(self.edit_form_layout.getWidgetRow(self.ollama_api_key_message_label), is_ollama)


        self.logger.debug(f"Provider specific controls updated for '{provider_type}'. Generic model edit visible: {show_generic_model_edit}, Gemini combo visible: {is_gemini}")

    def _update_visibility(self, provider_type: Optional[str]):
        """根据提供者类型更新UI字段的可见性。"""
        self.logger.info(f"Updating UI field visibility for provider type: '{provider_type}'")

        # Default visibility: show most common fields
        # These should now be instance attributes
        if hasattr(self, 'api_url_label'): self.api_url_label.show()
        self.api_url_edit.show()
        if hasattr(self, 'api_key_label'): self.api_key_label.show()
        self.api_key_edit.show()
        
        # Assuming api_key_status_label is handled correctly if it exists and is an instance attribute
        if hasattr(self, 'api_key_status_label'):
             self.api_key_status_label.show() 
        
        self.ollama_api_key_message_label.hide() # Hide by default

        if provider_type == 'google':
            if hasattr(self, 'api_key_status_label'): self.api_key_status_label.hide()

        elif provider_type == 'ollama':
            if hasattr(self, 'api_key_label'): self.api_key_label.hide()
            self.api_key_edit.hide()
            if hasattr(self, 'api_key_status_label'): self.api_key_status_label.hide()
            self.ollama_api_key_message_label.show()

        elif provider_type == 'volcengine_ark':
            if hasattr(self, 'api_key_status_label'): self.api_key_status_label.show()
            
        elif provider_type == 'openai_compatible': # Should match provider name from config
            if hasattr(self, 'api_key_status_label'): self.api_key_status_label.show()

        else: 
            if hasattr(self, 'api_key_status_label'): self.api_key_status_label.show() 

        # This function now primarily handles API key related field visibility.
        # Model name/combo visibility is delegated to _update_provider_specific_controls.
        # _on_current_config_loaded should call both this and _update_provider_specific_controls.

        # To avoid抖动, DO NOT call self.adjustSize() here.
        # Let the layout manage itself. If QFormLayout rows are entirely hidden, they should collapse.

# --- Example Usage / Test (Keep commented out) ---
# if __name__ == '__main__':
# ... (rest of example code) ...
