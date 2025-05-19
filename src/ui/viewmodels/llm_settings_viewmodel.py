# src/ui/viewmodels/llm_settings_viewmodel.py
import logging
from typing import List, Dict, Optional, Any
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

# 假设的依赖项导入 - 需要根据实际项目结构调整
from src.config.llm_config_manager import LLMConfigManager
from src.llm.llm_service import LLMService # 假设 LLMService 在 llm 包下

class LLMSettingsViewModel(QObject):
    """
    ViewModel for the LLM Settings Dialog.

    Manages the state and logic for configuring LLM providers.
    """

    # --- Signals for View updates ---
    config_list_changed = pyqtSignal(list) # List of config names (str)
    active_config_changed = pyqtSignal(str) # Active config name (str)
    current_config_loaded = pyqtSignal(dict) # Current config details (dict, API Key masked)
    config_cleared = pyqtSignal() # When no config is selected
    save_enabled_changed = pyqtSignal(bool)
    activate_enabled_changed = pyqtSignal(bool)
    test_enabled_changed = pyqtSignal(bool)
    delete_enabled_changed = pyqtSignal(bool)
    test_result_received = pyqtSignal(bool, str) # Success (bool), Message (str)
    save_status_received = pyqtSignal(bool, str) # Success (bool), Message (str)
    delete_status_received = pyqtSignal(bool, str) # Success (bool), Message (str)
    add_status_received = pyqtSignal(bool, str) # Success (bool), Message (str)
    activate_status_received = pyqtSignal(bool, str) # Success (bool), Message (str)
    error_occurred = pyqtSignal(str) # General error message

    def __init__(self, config_manager: LLMConfigManager, llm_service: LLMService, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing LLMSettingsViewModel...")
        self._config_manager = config_manager
        self._llm_service = llm_service

        self._config_names: List[str] = []
        self._active_config_name: Optional[str] = None
        self._current_config_name: Optional[str] = None
        self._original_current_config_data: Optional[Dict[str, Any]] = None
        self._current_config_data: Optional[Dict[str, Any]] = None
        self._is_dirty = False

    def get_config_names(self) -> List[str]:
        """Returns the list of known configuration names."""
        return self._config_names

    def get_active_config_name(self) -> Optional[str]:
        """Returns the name of the currently active configuration, or None."""
        return self._active_config_name

    @pyqtSlot()
    def load_initial_data(self):
        """Loads the initial list of configurations and the active one."""
        self.logger.debug("Loading initial LLM configurations...")
        try:
            self._config_names = self._config_manager.get_config_names()
            self._active_config_name = self._config_manager.get_active_config_name()
            self.config_list_changed.emit(self._config_names)
            self.active_config_changed.emit(self._active_config_name if self._active_config_name else "")
            self.logger.info(f"Loaded {len(self._config_names)} configurations. Active: '{self._active_config_name if self._active_config_name else "None"}'")
            
            # If there's an active config, select it to populate the form
            if self._active_config_name:
                self.logger.info(f"Initial load: Active config is '{self._active_config_name}'. Selecting it.")
                self.select_config(self._active_config_name)
            else:
                self.logger.info("Initial load: No active config. Clearing current config selection.")
                self._clear_current_config()

        except Exception as e:
            self.logger.error(f"Error loading initial LLM configurations: {e}", exc_info=True)
            self.error_occurred.emit(f"加载配置列表时出错: {e}")

    @pyqtSlot(str)
    def select_config(self, config_name: str):
        """Handles selection of a configuration from the list."""
        self.logger.debug(f"Configuration selected in ViewModel: '{config_name}'")
        if config_name == self._current_config_name and not self._is_dirty:
            self.logger.debug(f"Config '{config_name}' already current and not dirty, no full reload.")
            self._update_button_states()
            return

        try:
            config_data = self._config_manager.get_config(config_name)
            if config_data:
                self._current_config_name = config_name
                self._original_current_config_data = config_data.copy()
                self._current_config_data = config_data.copy()

                self._is_dirty = False
                self.current_config_loaded.emit(self._current_config_data)
                self._update_button_states()
                self.logger.info(f"Loaded details for configuration: '{config_name}'. Data for UI: {self._current_config_data}")
            else:
                self.logger.warning(f"Could not find configuration data for '{config_name}'")
                self._clear_current_config()
        except Exception as e:
            self.logger.error(f"Error loading configuration '{config_name}': {e}", exc_info=True)
            self._clear_current_config()
            self.error_occurred.emit(f"加载配置 '{config_name}' 时出错: {e}")

    @pyqtSlot()
    def clear_selection(self):
        """Clears the current selection and edit fields."""
        self.logger.debug("ViewModel clear_selection called.")
        self._clear_current_config()

    @pyqtSlot(str)
    def add_new_config(self, name: str):
        """Adds a new, empty configuration."""
        self.logger.debug(f"Attempting to add new configuration: '{name}'")
        if not name:
             self.logger.warning("Add new config: Name cannot be empty.")
             self.add_status_received.emit(False, "配置名称不能为空。")
             return
        if name in self._config_names:
            self.logger.warning(f"Add new config: Name '{name}' already exists.")
            self.add_status_received.emit(False, f"配置名称 '{name}' 已存在。")
            return

        try:
            default_new_config = {
                'provider': 'openai',
                'api_url': '', 
                'model': '',
                'temperature': 0.7,
                'max_tokens': 2048,
                'timeout': 60,
            }
            self.logger.debug(f"Adding new config '{name}' with default data: {default_new_config}")
            success = self._config_manager.add_or_update_config(name, default_new_config)
            if success:
                self._config_names = self._config_manager.get_config_names()
                self.config_list_changed.emit(self._config_names)
                self.add_status_received.emit(True, f"已添加配置 '{name}'。请填写详细信息并保存。")
                self.logger.info(f"Successfully added new config: '{name}'")
                self.select_config(name)
            else:
                 self.logger.error(f"Failed to add new config '{name}' via ConfigManager.")
                 self.add_status_received.emit(False, f"添加配置 '{name}' 失败。")
        except Exception as e:
            self.logger.error(f"Error adding configuration '{name}': {e}", exc_info=True)

    @pyqtSlot(str)
    def delete_selected_config(self, name: str):
        """Deletes the specified configuration."""
        self.logger.debug(f"Attempting to delete configuration: '{name}'")
        if not name:
            self.logger.warning("Delete config: No name provided.")
            self.delete_status_received.emit(False, "没有要删除的配置。")
            return

        try:
            was_active = (name == self._active_config_name)
            was_current = (name == self._current_config_name)
            self.logger.debug(f"Deleting config '{name}'. Was active: {was_active}, Was current: {was_current}")

            success = self._config_manager.delete_config(name)
            if success:
                self.logger.info(f"Successfully deleted config '{name}' via ConfigManager.")
                self._config_names = self._config_manager.get_config_names()
                new_active_config = self._config_manager.get_active_config_name()
                
                active_changed = (self._active_config_name != new_active_config)
                self._active_config_name = new_active_config

                self.config_list_changed.emit(self._config_names)
                if active_changed:
                    self.logger.info(f"Active config changed to '{new_active_config if new_active_config else "None"}' after deletion.")
                    self.active_config_changed.emit(self._active_config_name if self._active_config_name else "")

                if was_current:
                    self.logger.debug(f"Deleted config '{name}' was the current selection. Clearing current config.")
                    self._clear_current_config()
                else:
                    self.logger.debug(f"Deleted config '{name}' was not current. Current is '{self._current_config_name}'. Updating button states.")
                    self._update_button_states()

                self.delete_status_received.emit(True, f"配置 '{name}' 已删除。")
            else:
                self.logger.error(f"Failed to delete config '{name}' via ConfigManager.")
                self.delete_status_received.emit(False, f"删除配置 '{name}' 失败。")
        except Exception as e:
            self.logger.error(f"Error deleting configuration '{name}': {e}", exc_info=True)

    @pyqtSlot(dict)
    def save_current_config(self, updated_data_from_view: Dict[str, Any]):
        """Saves the currently edited configuration data."""
        if not self._current_config_name:
            self.logger.warning("Save attempt: No current config selected.")
            self.save_status_received.emit(False, "没有选中的配置可供保存。")
            return
        if not self._is_dirty:
             self.logger.info(f"Save attempt for '{self._current_config_name}': No changes to save (not dirty).")
             self.save_status_received.emit(False, "配置未更改，无需保存。")
             return

        self.logger.debug(f"Attempting to save configuration: '{self._current_config_name}'. Data from view: {updated_data_from_view}")
        try:
            config_to_save = updated_data_from_view.copy()

            self.logger.debug(f"API key from view for saving: '{config_to_save.get('api_key')}'")

            try:
                original_temp = self._original_current_config_data.get('temperature', 0.7) if self._original_current_config_data else 0.7
                original_tokens = self._original_current_config_data.get('max_tokens', 2048) if self._original_current_config_data else 2048
                original_timeout = self._original_current_config_data.get('timeout', 60) if self._original_current_config_data else 60
                config_to_save['provider'] = str(config_to_save.get('provider', self._original_current_config_data.get('provider', 'openai'))).strip()

                temp_str = str(config_to_save.get('temperature', original_temp)).strip()
                config_to_save['temperature'] = float(temp_str) if temp_str else original_temp
                tokens_str = str(config_to_save.get('max_tokens', original_tokens)).strip()
                config_to_save['max_tokens'] = int(tokens_str) if tokens_str else original_tokens
                timeout_str = str(config_to_save.get('timeout', original_timeout)).strip()
                config_to_save['timeout'] = int(timeout_str) if timeout_str else original_timeout

                self.logger.debug(f"Processed numeric and provider fields for saving: {config_to_save}")

            except (ValueError, TypeError) as e:
                 self.logger.error(f"Error processing numeric fields for saving config '{self._current_config_name}': {e}", exc_info=True)
                 self.save_status_received.emit(False, f"高级参数格式错误: {e}")
                 return

            success = self._config_manager.add_or_update_config(self._current_config_name, config_to_save)

            if success:
                self.logger.info(f"Successfully saved config '{self._current_config_name}' via ConfigManager.")
                self._is_dirty = False
                self._original_current_config_data = config_to_save.copy()
                
                # Prepare data for UI emission, ensuring temperature is well-formatted string if float
                ui_display_data = config_to_save.copy()
                if isinstance(ui_display_data.get('temperature'), float):
                    ui_display_data['temperature'] = f"{ui_display_data['temperature']:.1f}"
                else: # Ensure it's a string if not already (e.g. from user input)
                    ui_display_data['temperature'] = str(ui_display_data.get('temperature', '0.7'))

                self._current_config_data = ui_display_data.copy() # Update internal current with UI-friendly format
                
                self.current_config_loaded.emit(self._current_config_data)

                self.save_status_received.emit(True, f"配置 '{self._current_config_name}' 已保存。")
                self._update_button_states()
                
                if self._current_config_name == self._active_config_name:
                     self.logger.info(f"Active config '{self._active_config_name}' was saved. Emitting active_config_changed.")
                     self.active_config_changed.emit(self._active_config_name)
            else:
                self.logger.error(f"Failed to save config '{self._current_config_name}' via ConfigManager.")
                self.save_status_received.emit(False, f"保存配置 '{self._current_config_name}' 失败。")
        except Exception as e:
            self.logger.error(f"Error saving configuration '{self._current_config_name}': {e}", exc_info=True)
            self.save_status_received.emit(False, f"保存配置 '{self._current_config_name}' 时出错: {e}")

    @pyqtSlot()
    def activate_selected_config(self):
        """Activates the currently selected configuration."""
        if not self._current_config_name:
            self.logger.warning("Activate attempt: No current config selected to activate.")
            self.activate_status_received.emit(False, "没有选中的配置可供激活。")
            return

        config_name_to_activate = self._current_config_name
        self.logger.info(f"Attempting to activate LLM config: '{config_name_to_activate}'")

        # Call set_active_config_name
        raw_success_value = self._config_manager.set_active_config_name(config_name_to_activate)
        self.logger.debug(f"Raw return value from _config_manager.set_active_config_name for '{config_name_to_activate}': {raw_success_value} (type: {type(raw_success_value)})")

        # Ensure it's a boolean, though it should be.
        # In Python, non-empty strings, non-zero numbers, non-empty collections are True.
        # The method is typed to return bool, so direct use should be fine.
        success = bool(raw_success_value) 
        self.logger.debug(f"Boolean cast of success value for '{config_name_to_activate}': {success}")


        if success:
            self.logger.info(f"ViewModel confirms: Successfully set '{config_name_to_activate}' as active in ConfigManager (set_active_config_name returned True or truthy value).")
            # Notify LLMService to reload its configuration
            if self._llm_service:
                self._llm_service.reload_active_config()
                self.logger.info(f"LLMService reload_active_config called for '{config_name_to_activate}'.")
            else:
                self.logger.warning("LLMService instance is not available in ViewModel to reload config for activation.")
            
            old_active_name = self._active_config_name
            self._active_config_name = config_name_to_activate
            
            message = f"配置 '{config_name_to_activate}' 已激活。"
            self.logger.info(message)
            self.activate_status_received.emit(True, message)
            
            # Emit active_config_changed only if it actually changed, and after status
            if old_active_name != self._active_config_name:
                 self.active_config_changed.emit(self._active_config_name)
            
            # Also emit config_list_changed so the UI list can update its active marker
            self.config_list_changed.emit(self.get_config_names())
            self.logger.debug(f"Emitted config_list_changed after activating '{self._active_config_name}'.")

            self._update_button_states() # Active status might change delete/activate button states
        else:
            message = f"设置活动配置 '{config_name_to_activate}' 失败。"
            # Log includes the raw value for better debugging if it wasn't a clean False
            self.logger.error(f"ViewModel reports: Failed to activate config '{config_name_to_activate}' via ConfigManager. `set_active_config_name` returned '{raw_success_value}'.")
            self.activate_status_received.emit(False, message)
            # No need to update button states if activation failed, current selection remains.

    @pyqtSlot(dict)
    def test_current_config(self, config_data_from_view: Dict[str, Any]):
        """Tests the connection using the configuration data currently in the view's edit fields,
        but uses the original/stored API key.
        """
        if not self._current_config_name:
             self.logger.warning("Test connection: No current config selected.")
             self.test_result_received.emit(False, "请先选择一个配置。")
             return

        self.logger.debug(f"Testing connection for '{self._current_config_name}'. Data from view (key might be present): {config_data_from_view}")

        config_to_test = config_data_from_view.copy()

        # Ensure the API key from the view (user input) is explicitly used for the test.
        # The _get_form_data in the View should already provide the current api_key from the input field.
        # No need to fetch from _original_current_config_data unless we want to test 'saved' key specifically.
        current_api_key_from_view = config_data_from_view.get('api_key')
        config_to_test['api_key'] = current_api_key_from_view # Ensure it's set

        self.logger.debug(f"API key explicitly set for test from form data: '{self._mask_api_key(current_api_key_from_view) if hasattr(self, '_mask_api_key') else "<masking_unavailable>"}'")
        
        if 'provider' not in config_to_test and self._original_current_config_data:
            config_to_test['provider'] = self._original_current_config_data.get('provider')
            self.logger.debug(f"Added provider '{config_to_test['provider']}' from original data for test.")

        try:
            original_temp = self._original_current_config_data.get('temperature', 0.7) if self._original_current_config_data else 0.7
            original_tokens = self._original_current_config_data.get('max_tokens', 2048) if self._original_current_config_data else 2048
            original_timeout = self._original_current_config_data.get('timeout', 60) if self._original_current_config_data else 60

            temp_str = str(config_to_test.get('temperature', original_temp)).strip()
            config_to_test['temperature'] = float(temp_str) if temp_str else original_temp
            tokens_str = str(config_to_test.get('max_tokens', original_tokens)).strip()
            config_to_test['max_tokens'] = int(tokens_str) if tokens_str else original_tokens
            timeout_str = str(config_to_test.get('timeout', original_timeout)).strip()
            config_to_test['timeout'] = int(timeout_str) if timeout_str else original_timeout
            self.logger.debug(f"Numeric fields processed for test. Final config for LLMService: {self._log_config_data_safely(config_to_test)}") # Logging with masking
        except (ValueError, TypeError) as e:
            self.logger.error(f"Error processing numeric fields for test config '{self._current_config_name}': {e}", exc_info=True)
            self.test_result_received.emit(False, f"高级参数格式错误: {e}")
            return

        try:
            self.logger.info(f"Calling LLMService.test_connection_with_config for '{self._current_config_name}'")
            success, message = self._llm_service.test_connection_with_config(config_to_test)
            self.logger.info(f"Test connection result received from LLMService for '{self._current_config_name}': Success={success}, Message='{message}'") # ADDED log before emit
            self.test_result_received.emit(success, message)

        except AttributeError as e: # Specific catch for missing method
             self.logger.error(f"LLMService does not have a 'test_connection_with_config' method or related attribute error: {e}", exc_info=True)
             self.test_result_received.emit(False, "测试失败：LLM服务缺少测试功能。")
        except Exception as e:
            self.logger.error(f"Error testing connection for '{self._current_config_name}': {e}", exc_info=True)
            self.test_result_received.emit(False, f"测试连接时发生意外错误: {e}")

        self._update_button_states()

    @pyqtSlot(str, object)
    def update_current_config_field(self, field_name: str, value: Any):
        """Updates a field in the current configuration data and handles dirty state."""
        if self._current_config_data is None:
            self.logger.warning(f"Attempted to update field '{field_name}' but no config is currently loaded.")
            return

        # Make a shallow copy to avoid modifying the original dict directly if it's complex
        # or to ensure signal emission logic works correctly if it relies on old vs new dicts.
        # For simple flat dicts, direct modification might be fine.
        # updated_config = self._current_config_data.copy()

        self.logger.debug(f"Updating field '{field_name}' in ViewModel to '{value}' (type: {type(value)})")

        # Clean the API key if it's the field being updated
        if field_name == 'api_key' and isinstance(value, str):
            original_value = value
            value = value.strip()
            if value != original_value:
                self.logger.info(f"API key stripped. Original: '{self._mask_api_key(original_value)}', Stripped: '{self._mask_api_key(value)}'")

        if field_name in self._current_config_data and self._current_config_data[field_name] == value:
            self.logger.debug(f"Field '{field_name}' already has value '{value}'. No change.")
            return

        if field_name in self._current_config_data:
            self._current_config_data[field_name] = value
        else:
            self._current_config_data[field_name] = value

        self._is_dirty = True
        self.logger.debug(f"Config '{self._current_config_name}' is now dirty.")

        self._update_button_states()

    def is_dirty(self) -> bool:
        """Returns True if the current configuration has unsaved changes."""
        return self._is_dirty

    def _clear_current_config(self):
        """Clears the currently selected/edited configuration state."""
        self.logger.debug("Clearing current config data, name, and dirty status.")
        self._current_config_name = None
        self._original_current_config_data = None
        self._current_config_data = None
        self._is_dirty = False
        self.config_cleared.emit()
        self._update_button_states()

    def _update_button_states(self):
        """Updates the enabled/disabled state of buttons based on current state."""
        can_save = bool(self._current_config_name and self._is_dirty)
        can_activate = bool(self._current_config_name and self._current_config_name != self._active_config_name)
        can_test = bool(self._current_config_name)
        can_delete = bool(self._current_config_name)

        self.logger.debug(f"Updating button states for '{self._current_config_name}': Save={can_save}, Activate={can_activate}, Test={can_test}, Delete={can_delete}, Dirty={self._is_dirty}, Active='{self._active_config_name}'")

        self.save_enabled_changed.emit(can_save)
        self.activate_enabled_changed.emit(can_activate)
        self.test_enabled_changed.emit(can_test)
        self.delete_enabled_changed.emit(can_delete)

    def _mask_api_key(self, api_key: Optional[str]) -> str:
        """Masks an API key for safe logging."""
        if not api_key:
            return "<Not Set>"
        if len(api_key) > 8:
            return f"***{api_key[-4:]}"
        return "***"

    def _log_config_data_safely(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Returns a copy of config data with API key masked for logging."""
        safe_data = config_data.copy()
        if 'api_key' in safe_data:
            safe_data['api_key'] = self._mask_api_key(safe_data['api_key'])
        return safe_data
