import logging
import os
from PySide6.QtCore import QSettings
from typing import List, Union, Optional, Dict, Any

# Attempt to import dotenv, handle if not installed
try:
    from dotenv import load_dotenv, find_dotenv
    # Load environment variables from .env file if it exists
    # find_dotenv() will search for .env in current dir and parent dirs
    dotenv_path = find_dotenv()
    if dotenv_path:
        print(f"Loading environment variables from: {dotenv_path}") # Use print for early feedback
        load_dotenv(dotenv_path=dotenv_path, override=True) # Override allows updating existing env vars
    else:
        print("No .env file found.")
except ImportError:
    print("python-dotenv not installed. Cannot load configuration from .env file.")
    load_dotenv = None # Set to None to indicate it's unavailable

logger = logging.getLogger('news_analyzer.config.manager')

# 配置存储在 QSettings 中的分组路径
CONFIG_GROUP_PREFIX = "llm_configs"
ACTIVE_CONFIG_KEY = "llm/active_config_name"

class LLMConfigManager:
    """
    管理LLM配置，使用 QSettings 进行存储。

    配置信息（包括API密钥）直接存储在应用程序设置中。
    注意：直接存储 API 密钥可能存在安全风险。
    """

    def __init__(self):
        self.settings = QSettings("NewsAnalyzer", "NewsAggregator")
        self.logger = logging.getLogger(__name__) # Use module name for logger
        logger.debug("LLMConfigManager initialized (QSettings Mode + Env Loading).")
        self._ensure_default_configs_exist()

    def get_config_names(self) -> list:
        """获取所有已保存配置的名称列表。

        从 QSettings 中读取所有 LLM 配置分组的名称。

        Returns:
            List[str]: 包含所有配置名称的列表，按字母顺序排序。
        """
        """获取所有已保存配置的名称列表。"""
        self.settings.beginGroup(CONFIG_GROUP_PREFIX)
        names = self.settings.childGroups()
        self.settings.endGroup()
        logger.debug(f"Found config names in QSettings: {names}")
        return sorted(names) # 返回排序后的列表

    def _get_env_var_name(self, config_name: str, key_type: str = "api_key") -> str:
        """Generates a standardized environment variable name for a given config.
           Example: config 'My Gemini' -> GEMINI_API_KEY_MY_GEMINI
                    config 'Volcano Prod' -> VOLC_ACCESS_KEY_VOLCANO_PROD or VOLC_SECRET_KEY_VOLCANO_PROD
        """
        # Normalize config name: uppercase, replace spaces/hyphens with underscores
        normalized_name = config_name.upper().replace(" ", "_").replace("-", "_")
        # Basic provider prefix detection (can be improved)
        prefix = "LLM"
        if "GEMINI" in normalized_name or "GOOGLE" in normalized_name:
            prefix = "GEMINI"
        elif "VOLC" in normalized_name or "火山" in config_name: # Check original name too
            prefix = "VOLC"
        elif "OPENAI" in normalized_name:
            prefix = "OPENAI"
        # ... add more providers as needed ...

        # Determine key suffix based on key_type
        key_suffix = "API_KEY" # Default
        if prefix == "VOLC":
             key_suffix = "ACCESS_KEY" if key_type == "access_key" else "SECRET_KEY"
        # Add more specific key types if needed

        return f"{prefix}_{key_suffix}_{normalized_name}"

    def get_config(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定名称的 LLM 配置详情。

        从 QSettings 中读取指定名称的配置分组下的所有键值对。

        Args:
            name (str): 要获取的配置的名称。

        Returns:
            Optional[Dict[str, Any]]: 包含配置信息的字典，如果找不到或配置为空，则返回 None。
                                      字典包含 'name', 'api_key', 'api_url', 'model',
                                      'temperature', 'max_tokens', 'system_prompt', 'timeout' 等键。
        """
        """
        获取指定名称的配置详情。
        返回包含配置信息的字典，如果找不到则返回 None。
        """
        config_path = f"{CONFIG_GROUP_PREFIX}/{name}"
        # 检查分组是否存在，避免 beginGroup 创建空分组
        all_groups = []
        self.settings.beginGroup(CONFIG_GROUP_PREFIX)
        all_groups = self.settings.childGroups()
        self.settings.endGroup()
        if name not in all_groups:
            logger.warning(f"Config group '{config_path}' not found in QSettings.")
            return None

        self.settings.beginGroup(config_path)
        # 检查分组内是否有键, 如果没有则认为配置无效
        if not self.settings.allKeys():
             self.settings.endGroup()
             logger.warning(f"Config group '{config_path}' exists but is empty.")
             # 可以选择删除空分组 self.settings.remove(config_path)
             return None

        # Load non-secret values from QSettings
        config = {
            "name": name,
            "api_url": self.settings.value("api_url", "", type=str),
            "model": self.settings.value("model", "", type=str),
            "temperature": self.settings.value("temperature", 0.7, type=float),
            "max_tokens": self.settings.value("max_tokens", 2048, type=int),
            "system_prompt": self.settings.value("system_prompt", "", type=str), # Kept for now, UI might re-add
            "timeout": self.settings.value("timeout", 60, type=int),
            "api_key": None, # Initialize API key as None
            "provider": None # Initialize provider as None
        }
        
        # Explicitly load or infer provider
        provider_from_settings = self.settings.value("provider", "", type=str)
        if provider_from_settings:
            config["provider"] = provider_from_settings.lower()
            logger.debug(f"[{name}] Provider type loaded from settings: '{config['provider']}'")
        else:
            inferred_provider = self._determine_provider_type_string(name, config.get('api_url'))
            config["provider"] = inferred_provider if inferred_provider else 'generic' # Default to 'generic' if cannot infer
            logger.debug(f"[{name}] Provider type inferred as '{config['provider']}' (was empty in settings).")

        self.settings.endGroup()

        # --- Load API Key securely from Environment/.env --- MODIFIED
        api_key = None
        # Use the now-populated config['provider'] for provider_type_hint
        provider_type_hint = config.get('provider') 
        
        if provider_type_hint == 'volcengine_ark':
            # VolcEngine needs AK and SK
            ak_env_var = self._get_env_var_name(name, key_type="access_key")
            sk_env_var = self._get_env_var_name(name, key_type="secret_key")
            access_key = os.getenv(ak_env_var)
            secret_key = os.getenv(sk_env_var)
            
            if access_key and secret_key:
                # Store AK,SK pair. Provider needs to handle this dict format.
                api_key = {"access_key": access_key.strip(), "secret_key": secret_key.strip()} # STRIPPED
                logger.debug(f"Loaded VolcEngine keys for '{name}' from env vars: {ak_env_var}, {sk_env_var}")
            else:
                 logger.warning(f"Could not load VolcEngine keys for '{name}'. Checked env vars: {ak_env_var}, {sk_env_var}. Trying QSettings fallback for 'api_key' field.") # MODIFIED: Log message
                 # Fallback to QSettings for a single 'api_key' field, even if it's not ideal for AK/SK pair.
                 # This is to ensure that if something was saved from a single input field, it can be retrieved.
                 current_group = self.settings.group() # Get current group before changing
                 self.settings.beginGroup(f"{CONFIG_GROUP_PREFIX}/{name}")
                 # Use _load_api_keys_for_provider which handles string conversion and stripping
                 qsettings_api_key = self._load_api_keys_for_provider(provider_type_hint, name, self.settings)
                 if qsettings_api_key:
                     api_key = qsettings_api_key # This will be a single string
                     logger.info(f"Loaded single 'api_key' for VolcEngine config '{name}' from QSettings as fallback: '{self._mask_api_key(api_key)}'")
                 else:
                     logger.warning(f"No 'api_key' found in QSettings for VolcEngine config '{name}' as fallback.")
                 if current_group: # Restore previous group if any
                    self.settings.beginGroup(current_group)
                 else:
                    self.settings.endGroup() # Ensure group is ended if we started one

        elif provider_type_hint == 'google':
            # --- Logic for Gemini: API keys directly from QSettings ---
            config_path = f"{CONFIG_GROUP_PREFIX}/{name}" # Define config_path for QSettings
            self.settings.beginGroup(config_path) # Begin group to read api_key
            # api_key_from_qsettings = self.settings.value("api_key", None) # Read api_key - MOVED to _load_api_keys_for_provider
            
            # Use _load_api_keys_for_provider for Gemini as well, ensuring consistent string/None output
            api_key = self._load_api_keys_for_provider(provider_type_hint, name, self.settings)
            
            self.settings.endGroup() # End group after reading

            # The _load_api_keys_for_provider will return a string or None.
            # The original Gemini logic expected a list if multiple keys were comma-separated.
            # For now, we adhere to the new single string model. If UI shows a list, it's from an old save.
            if isinstance(api_key, str) and api_key: # Ensure it's a non-empty string
                logger.info(f"Loaded API key for Gemini config '{name}' (unified string): '{self._mask_api_key(api_key)}'")
            elif api_key is None:
                logger.warning(f"No API key loaded from QSettings for Gemini config '{name}' (unified string).")
            else: # Should not happen if _load_api_keys_for_provider works as expected
                logger.warning(f"API key for Gemini config '{name}' is unexpected type: {type(api_key)} (unified string).")


            # ---- Start: Original Gemini multi-key loading logic (NOW MOSTLY OBSOLETE DUE TO _load_api_keys_for_provider) ---
            # The _load_api_keys_for_provider should handle returning a single string key.
            # The UI now expects a single string input.
            # If old configurations had a list of keys, _load_api_keys_for_provider would convert it to a string (likely the first key or joined).
            # This section is largely bypassed or simplified.
            
            # loaded_keys = []
            # api_key_from_qsettings = self.settings.value("api_key", None) # This was already read by _load_api_keys_for_provider essentially
            #
            # if isinstance(api_key_from_qsettings, str):
            #    logger.info(f"[Config:'{name}'] Found 'api_key' as string in QSettings for Gemini. Parsing comma-separated keys.")
            #    potential_keys = api_key_from_qsettings.split(',')
            #    for key_candidate in potential_keys:
            #        stripped_key = key_candidate.strip() # STRIPPED here
            #        if stripped_key:
            #            logger.info(f"[Config:'{name}']   Adding key (len: {len(stripped_key)}): ends with '...{stripped_key[-4:] if len(stripped_key) >= 4 else stripped_key}'")
            #            loaded_keys.append(stripped_key)
            #        else:
            #            logger.info(f"[Config:'{name}']   Skipping empty key part from comma-separated string.")
            # elif isinstance(api_key_from_qsettings, list):
            #    logger.info(f"[Config:'{name}'] Found 'api_key' as list in QSettings for Gemini. Processing list.")
            #    for idx, key_candidate in enumerate(api_key_from_qsettings):
            #        if isinstance(key_candidate, str):
            #            stripped_key = key_candidate.strip() # STRIPPED here
            #            if stripped_key:
            #                logger.info(f"[Config:'{name}']   Adding key from list (index {idx}, len: {len(stripped_key)}): ends with '...{stripped_key[-4:] if len(stripped_key) >= 4 else stripped_key}'")
            #                loaded_keys.append(stripped_key)
            #            else:
            #                logger.info(f"[Config:'{name}']   Skipping empty string key from list at index {idx}.")
            #        else:
            #            logger.warning(f"[Config:'{name}']   Skipping non-string item in api_key list at index {idx}: {type(key_candidate)}")
            # elif api_key_from_qsettings is not None: # Handle cases where it's neither string nor list but not None
            #    logger.warning(f"[Config:'{name}'] 'api_key' for Gemini in QSettings is neither string nor list, but {type(api_key_from_qsettings)}. Trying to convert to string and parse.")
            #    try:
            #        potential_keys = str(api_key_from_qsettings).split(',')
            #        for key_candidate in potential_keys:
            #            stripped_key = key_candidate.strip()
            #            if stripped_key:
            #                logger.info(f"[Config:'{name}']   Adding key (fallback conversion, len: {len(stripped_key)}): ends with '...{stripped_key[-4:] if len(stripped_key) >= 4 else stripped_key}'")
            #                loaded_keys.append(stripped_key)
            #    except Exception as e:
            #        logger.error(f"[Config:'{name}'] Error during fallback conversion/parsing of api_key: {e}")
            #
            #
            # if loaded_keys:
            #    # If we want to revert to list behavior for Gemini internally for some reason:
            #    # api_key = loaded_keys
            #    # For single string model:
            #    api_key = loaded_keys[0] if loaded_keys else None # Take the first key if list was loaded
            #    logger.info(f"Final API keys for Gemini config '{name}' from QSettings (count: {len(loaded_keys) if isinstance(loaded_keys, list) else 1 if loaded_keys else 0}). Selected: '{self._mask_api_key(api_key)}'")
            # else:
            #    api_key = None # Ensure api_key is None if no valid keys were loaded from QSettings
            #    logger.warning(f"No valid API keys loaded from QSettings for Gemini config '{name}'.")
            # --- End Gemini Logic --- (Simplified/unified via _load_api_keys_for_provider)

        elif provider_type_hint == 'azure':
            # Ensure there's some code here or a pass statement if it's intentionally blank for now
            logger.debug(f"Processing Azure provider type for '{name}'...")
            # ... (existing Azure key loading logic would go here)
            # Example:
            azure_api_key_env_var = self._get_env_var_name(name, key_type="api_key")
            azure_api_key = os.getenv(azure_api_key_env_var)
            if azure_api_key:
                config['api_key'] = azure_api_key.strip() # STRIPPED
                logger.info(f"Loaded Azure API key for '{name}'.")
            else:
                logger.warning(f"Azure API key not found for '{name}' in env var '{azure_api_key_env_var}'.")
            
            azure_endpoint_env_var = self._get_env_var_name(name, key_type="api_base")
            azure_endpoint = os.getenv(azure_endpoint_env_var)
            if azure_endpoint:
                config['api_base'] = azure_endpoint
                logger.info(f"Loaded Azure API base/endpoint for '{name}'.")
            else:
                logger.warning(f"Azure API base/endpoint not found for '{name}' in env var '{azure_endpoint_env_var}'.")
            # ... (add other Azure specific params like api_version, deployment_id)

        else: # Other providers expecting a single string key
            env_var_name = self._get_env_var_name(name, key_type="api_key")
            api_key_from_env = os.getenv(env_var_name)
            if api_key_from_env:
                api_key = api_key_from_env.strip() # STRIPPED
                logger.debug(f"Loaded API key for '{name}' from env var: {env_var_name}")
            else:
                 logger.warning(f"Could not load API key for '{name}'. Checked env var: {env_var_name}. Trying QSettings.")
                 # Fallback to QSettings (less secure) if not in env
                 # This now uses the unified _load_api_keys_for_provider
                 self.settings.beginGroup(f"{CONFIG_GROUP_PREFIX}/{name}")
                 api_key = self._load_api_keys_for_provider(provider_type_hint, name, self.settings)
                 self.settings.endGroup()
                 if api_key:
                     logger.debug(f"Loaded API key for '{name}' from QSettings as fallback: '{self._mask_api_key(api_key)}'")
                 else:
                     logger.warning(f"No API key for '{name}' in QSettings fallback either.")


        config['api_key'] = api_key # Assign loaded key (should be str, dict for Volc, or None)
        # --- End Secure Loading --- 

        # Log retrieved config (key already handled/masked if needed)
        log_config = {k: v for k, v in config.items() if k != 'api_key'}
        key_status = "<Not Set>"
        if isinstance(api_key, dict): key_status = "<Keys Loaded>" # For Volc
        elif isinstance(api_key, list): key_status = f"<Loaded {len(api_key)} Key(s)>"
        elif isinstance(api_key, str) and api_key: key_status = "<Loaded>"
        log_config['api_key_status'] = key_status 
        logger.debug(f"Retrieved config for '{name}': {log_config}")
        return config

    def get_all_configs(self) -> dict:
        """获取所有已保存的 LLM 配置。

        遍历所有配置名称并调用 get_config 获取每个配置的详情。

        Returns:
            Dict[str, Dict[str, Any]]: 一个字典，键是配置名称，值是对应的配置详情字典。
        """
        """获取所有已保存的配置。"""
        configs = {}
        names = self.get_config_names()
        for name in names:
            config = self.get_config(name)
            if config:
                configs[name] = config
        return configs

    def add_or_update_config(self, name: str, config_data: Dict[str, Any]) -> bool:
        """Adds a new LLM configuration or updates an existing one."""
        self.logger.info(f"Attempting to add/update LLM config: '{name}' with data: {config_data}")
        if not name:
            self.logger.error("Configuration name cannot be empty.")
            return False

        # Ensure 'provider' is determined and present before saving if possible
        # This helps in cases where 'provider' might not be in config_data yet.
        
        # Robustly get api_url for provider detection, ensuring it's a string
        raw_api_url_for_detection = config_data.get('api_url')
        api_url_for_detection_str = ""
        if isinstance(raw_api_url_for_detection, str):
            api_url_for_detection_str = raw_api_url_for_detection
        elif raw_api_url_for_detection is not None:
            self.logger.warning(
                f"Config '{name}': api_url for provider detection was not a string (type: {type(raw_api_url_for_detection)}). "
                f"Value: {raw_api_url_for_detection}. Converting to string."
            )
            api_url_for_detection_str = str(raw_api_url_for_detection)

        provider_type_hint = self._determine_provider_type_string(name, api_url_for_detection_str)
        self.logger.debug(f"Determined provider type hint for '{name}' as '{provider_type_hint}' based on api_url: '{api_url_for_detection_str}'")

        # Prepare a copy of the data to save, ensuring critical fields are strings or appropriate types
        data_to_save = config_data.copy()

        # Ensure essential string fields are indeed strings before saving
        for key in ['api_url', 'model', 'api_key']: # api_key can be None, but if present, should be string
            if key in data_to_save and data_to_save[key] is not None and not isinstance(data_to_save[key], str):
                self.logger.warning(f"Config '{name}': Converting field '{key}' to string before saving. Original type: {type(data_to_save[key])}, Value: {data_to_save[key]}")
                data_to_save[key] = str(data_to_save[key])
            elif key == 'api_key' and data_to_save.get(key) is None: # Explicitly handle None for api_key for clarity
                 data_to_save[key] = "" # Store as empty string if None, QSettings might prefer this

        # Ensure 'provider' field in data_to_save is set, using hint if not present
        if 'provider' not in data_to_save or not data_to_save['provider']:
            self.logger.debug(f"Config '{name}': 'provider' not in data_to_save or is empty. Using hint: '{provider_type_hint}'")
            data_to_save['provider'] = provider_type_hint
        elif not isinstance(data_to_save['provider'], str):
            self.logger.warning(f"Config '{name}': 'provider' field was not a string (type: {type(data_to_save['provider'])}). Converting to string. Value: {data_to_save['provider']}")
            data_to_save['provider'] = str(data_to_save['provider'])


        self.logger.debug(f"Final data to save for '{name}': {data_to_save}")

        return self._save_config_to_settings(name, data_to_save, provider_type_hint)

    def _save_config_to_settings(self, name: str, data_to_save: Dict[str, Any], provider_type_hint: str) -> bool:
        """Saves configuration data to QSettings."""
        config_path = f"{CONFIG_GROUP_PREFIX}/{name}"
        self.settings.beginGroup(config_path)
        
        # Save all data to QSettings
        for key, value in data_to_save.items():
            self.settings.setValue(key, value)

        self.settings.endGroup()
        
        logger.info(f"Configuration metadata for '{name}' (type: {provider_type_hint}) added or updated in QSettings.")
        return True

    def delete_config(self, name: str) -> bool:
        """删除指定名称的 LLM 配置。

        从 QSettings 中移除对应的配置分组。
        如果删除的是当前活动的配置，则会清除活动配置设置。

        Args:
            name (str): 要删除的配置的名称。

        Returns:
            bool: 如果成功删除则返回 True，如果配置不存在或删除失败则返回 False。
        """
        """删除指定名称的配置。"""
        config_path = f"{CONFIG_GROUP_PREFIX}/{name}"
        # 检查分组是否存在
        all_groups = []
        self.settings.beginGroup(CONFIG_GROUP_PREFIX)
        all_groups = self.settings.childGroups()
        self.settings.endGroup()
        if name not in all_groups:
             logger.warning(f"Cannot delete config '{name}': Not found in QSettings.")
             return False

        # 检查是否是活动配置，如果是，则清除活动配置设置
        active_name = self.get_active_config_name()
        if active_name == name:
            self.set_active_config_name(None)
            logger.info(f"Cleared active config because '{name}' was deleted.")

        # QSettings 没有直接删除 group 的方法，需要移除 group 前缀
        self.settings.beginGroup(CONFIG_GROUP_PREFIX)
        self.settings.remove(name) # 移除该 group 下所有键值
        self.settings.endGroup()
        # 确认是否真的移除了 (QSettings 的 remove 行为有时不直观)
        # 再次检查确认
        self.settings.beginGroup(CONFIG_GROUP_PREFIX)
        remaining_groups = self.settings.childGroups()
        self.settings.endGroup()
        if name not in remaining_groups:
            logger.info(f"Configuration metadata for '{name}' deleted from QSettings.")
            return True
        else:
            # 如果 remove('') 失败，尝试手动清除键值
            self.settings.beginGroup(config_path)
            for key in self.settings.allKeys():
                self.settings.remove(key)
            self.settings.endGroup()
            # 再次检查
            self.settings.beginGroup(config_path)
            keys_left = self.settings.allKeys()
            self.settings.endGroup()
            if not keys_left:
                 logger.info(f"Configuration '{name}' keys cleared from QSettings (group might persist if empty).")
                 # 尝试移除空组，但这可能不被所有后端支持
                 self.settings.remove(config_path)
                 return True
            else:
                 logger.error(f"Failed to fully delete configuration '{name}' from QSettings.")
                 return False


    def get_active_config_name(self) -> Optional[str]:
        """获取当前激活的 LLM 配置的名称。

        从 QSettings 中读取存储的活动配置名称。

        Returns:
            Optional[str]: 当前活动配置的名称，如果未设置则返回 None。
        """
        """从QSettings获取当前激活的配置名称。"""
        return self.settings.value(ACTIVE_CONFIG_KEY, None)

    def set_active_config_name(self, name: Optional[str]) -> bool:
        """设置当前激活的 LLM 配置名称。

        将指定的名称保存到 QSettings 中作为活动配置。
        如果 `name` 为 None，则清除活动配置设置。
        如果 `name` 指定的配置不存在，则记录错误。

        Args:
            name (Optional[str]): 要设置为活动配置的名称，或 None 以清除设置。
        Returns:
            bool: True if the operation was successful (set or cleared), False if the name was invalid.
        """
        available_names = self.get_config_names()
        if name is None:
            self.settings.remove(ACTIVE_CONFIG_KEY)
            self.settings.sync()
            logger.info("Cleared active LLM configuration.")
            return True
        elif name in available_names:
            self.settings.setValue(ACTIVE_CONFIG_KEY, name)
            self.settings.sync()
            logger.info(f"Set '{name}' as active LLM configuration.")
            return True
        else:
            logger.error(f"Cannot activate configuration '{name}': Not found in saved configurations. Available names: {available_names}")
            return False

    def get_active_config(self) -> Optional[Dict[str, Any]]:
        """获取当前激活的 LLM 配置的详细信息。

        首先获取活动配置名称，然后调用 get_config 获取该配置的详情。
        如果活动配置名称无效或对应的配置不存在，则清除活动配置设置并返回 None。

        Returns:
            Optional[Dict[str, Any]]: 当前活动配置的详情字典，如果无活动配置或配置无效则返回 None。
        """
        active_name = self.get_active_config_name()
        if active_name:
            config = self.get_config(active_name)
            if config:
                return config
            else:
                # 活动配置名称存在，但配置本身找不到了（可能被异常删除）
                logger.warning(f"Active config name '{active_name}' is set, but the configuration itself was not found. Clearing active config.")
                self.set_active_config_name(None)
                return None
        logger.debug("No active LLM configuration set.")
        return None

    def _ensure_default_configs_exist(self):
        """Checks for essential default configs and adds them if missing."""
        existing_names = self.get_config_names()
        
        # Define desired default configurations
        default_configs_to_ensure = {
            "Google Gemini (Flash)": {
                "provider": "google",
                "api_key": [ 
                    "AIzaSyCmQjGoeOVBJaiPEktFXxRzeOGUPk4LgRM", "AIzaSyDmtrtbNxrtWowHd11Ky10p4TuSKvt9D4Q", "AIzaSyCQdn2IMX_sWoNkiFA-C2vsbcdmgFas7p0",
                    "AIzaSyCj0UK-sPz4bK_ZkZveeG2GaW6rVhgQ5x8", "AIzaSyDMrciRS7CoHjOkacMfMpZtQVIqmlS_rRQ", "AIzaSyCQPLMdeP_FAdD382W9vrG_3XXQVT8tzfE",
                    "AIzaSyAG1A-AycNyxqR8E_K3YOf8KXSKldwNAWY", "AIzaSyBOO4e1zPrrTyCmSCRcVata7zGBQhaZYxg", "AIzaSyBtMggcYq4pmq29J-WiCxU8IldGe_tzaY8",
                    "AIzaSyDYbeB8szSwlFXUU5hNKLgmxs8Tl0sB5Hs", "AIzaSyDpsScOZy20ZQx6ZaDcPyyRgOa2SjZ927A", "AIzaSyAoZgiB_4nfIkp5Ms05cC2UvehcWlfknbU",
                    "AIzaSyDeH1jXiGeFXYRWJub5JbCYcq2aAdjXjRU", "AIzaSyAv-EXJqNg0RKBe7E7EVHQJieifNcDCuKg", "AIzaSyD7HslOl3En5nvRePQIw62Fj_TFRQFEWv0",
                    "AIzaSyDvsyLupmOR6Xzp5eh7XS_RQCd6taTL-cY", "AIzaSyANyp1Fh0jIXfsApVivLlGXuFqmHHvT4vQ", "AIzaSyDwEm5dAXWx_zvG1oTKg0pJdl-wiFD8Ie8",
                    "AIzaSyDiVU5i9WlPw_ibmhQ0-tPLE9oh9nmvzc0", "AIzaSyDvS1QuDHDZd9OL72Vt1hh_0I_gkCElS5k", "AIzaSyDOcyP9dAhv0hM-RWGGBIcObICOdzPHmTs",
                    "AIzaSyCt3uHkoTj1f48HEljouYmSB_bTIqvGg_c", "AIzaSyBBZu5oaRhFgftvKWpU1mTfZxSe2yqWY8k", "AIzaSyAs7X9ge_W4xocuQ0ZiPxk6P9_3gsq5Aaw",
                    "AIzaSyCcdB8fdB5w9dh-S2DmyA6OqTyIfsTu1ZI", "AIzaSyCPZykZ0yqNrE4vfayAkg18RrdlbiPF4fU", "AIzaSyD4kB9K8NUWBqT47J137_HDj6Bo1fo8INY",
                    "AIzaSyC4E7vSRHM_TSUwYjH4Yd5tkakQ8fJCF_4", "AIzaSyBkox5_GnXNrFfNABULUJvfdqQJJXou40A", "AIzaSyAu2IZqQUOw9CShCH2bOTETpVf3bYImxqs",
                    "AIzaSyAgT7YokoGD3e9qLFzcqYwo4NcOB6nrOwk", "AIzaSyCMtkBoXF-dSA_-lFzBYeHT8O9D6u8nkGw", "AIzaSyDzXkY5QEYNOHf4uoGuy0PMupig3_4Kf7M",
                    "AIzaSyBbG8Pw7CKiO5G5A23b9x2HS4Atk5gsYag", "AIzaSyAZ8Q0cLB1cXN6ZEQcy1-DzwyfpGjhZyfg", "AIzaSyA2ntEay86JHXYzLjTnZV6VNlrpLFvpiW0",
                    "AIzaSyA2QHmAsNGqXwYSM_he9EYIHgGksWpl_ck", "AIzaSyBt1evFHtHh-RJlF3RYn09Ogxz4etSGskg", "AIzaSyBV6--klHxDz1EIVvRHVWRNuiSInnFvVK8",
                    "AIzaSyACl5B0imWRyxP49r7dS98IaX9yeOXxFbk", "AIzaSyAMom_b42e6S6UuG1RyVsLbEp5eD2IK348", "AIzaSyC1-SIllWqFcpwJamkymI1y3WcvZYqQIGo",
                    "AIzaSyCrrKUUPxCe7H9yJOiHNBLfw8jY1pmojZ8", "AIzaSyCLdXNY3siNdB6Pv9fHtL4nCoVIgklxX10", "AIzaSyApidRFMZYilhmcBtADgHQromeWMPzMSNo",
                    "AIzaSyCNi6fZAoQ6r0vgeWLsd5Z2_l2HrBisRK4", "AIzaSyB3qq-EG5D9kJqTCZYlHDeQP-CvOR5zK38", "AIzaSyAb8qYQT18dJ2cIXUYZypk3i2UvExNRHTM",
                    "AIzaSyD0v70DNQCjveTwRaig3zPZw_WO4JVho9c", "AIzaSyDp40PU5NeHyQ0OuchUR1TMjxxSek2AhPE", "AIzaSyD78Tgpkx8tw0Z8qvrlILCq2itkel3-d58",
                    "AIzaSyBlNJabfuUB8zlUMHbybgIZwuALL4E8Ibg", "AIzaSyD3SHth2dmZ_gZ8ZWicxreg9YCxhbnzcLo", "AIzaSyBqhtO8KEOq1LKq1RWQ3ngFS3OPe7l4Rto",
                    "AIzaSyCnSSZ3tdkPgWB2h-eFw5THqnovHRgZhIc", "AIzaSyAGedAF8rAdkcvgsY7Uyc-JJebp9abIOVo", "AIzaSyCyvokmANz_nfSJhLIzpMEnvB1_UfRnmFE",
                    "AIzaSyBJbbUlyIZAj0xdAR26lSv6yAvvQ-s8M_s", "AIzaSyD6BLzUK6tmuGLYuW-374zd1l_VeHy7mAk", "AIzaSyCevMGzBLQGHD426-HaEy6Y3jHnUnB4WBI",
                    "AIzaSyDOzx0ztUYH7D0pHN7wMVZRZA8aB6G3YVE", "AIzaSyD6Ur6r5WlJdpmZXxVg31pEmYuds-dp9yg", "AIzaSyB_I-hW3E8EtvhJ41K5reyLELwMvMJfo_4",
                    "AIzaSyD9m1g6xHtzHanNKqizp-_omXUCRudCntU", "AIzaSyAqU6N6NADk_TMMArCWBzc4qi-c_igVcB4", "AIzaSyCt095tT7BnkDss7DO9XtndgkJfT1EpLyM",
                    "AIzaSyBDbUCmRd4m9LdI43csXG7JVCOwlx99wos", "AIzaSyBl9HnlM8nlagXXMIpgwooKcHAJh43ewpI", "AIzaSyCW0NiebHisGseAJwocGBNhDTMdyYE-HjQ",
                    "AIzaSyDjIaGu924DJs6z603AtaqOT501guxAnLM", "AIzaSyClhQBdEX1AKzM4w7Tvw83NQYw7fH8ToEw", "AIzaSyBoG9G4ehMx35wq8W-ePjc2YwpbsDa6izE",
                    "AIzaSyDepYWj7La9aizSYgziA1N437dgNhU6Lb0", "AIzaSyBE5Uwtrym-Srhp7AUyFWN_18zYYnpSCTE", "AIzaSyC3I9WKkr2SRc0W-sHqXMoCk6R6o_0vihk",
                    "AIzaSyDVjv89vgKx8maACde9qkJTG4TGkvXjdgA", "AIzaSyA6fWTPUxMZ6TkCbIuXgdxU1ZpmOOZa81Y", "AIzaSyCN_Ptp-778oc28v8sgWk0qkMPLOCqit9M",
                    "AIzaSyBYCIGg4ZtoaXf_w4Brs7qtKVkG0gHVH8w", "AIzaSyDDPCWUmtcFkIxBc6FXxvcBFZql5fp7aso", "AIzaSyBCNzSJl8lkRpVcknljKTaHj772jF_iHmg",
                    "AIzaSyBIFqrOmnH3W9mWv98YknJ0TzsIcQdaWZY", "AIzaSyALuX_GCth-ZmO1zhwU02ehAaEznWtfCJk", "AIzaSyBom2CnQsnjbTMcrz8KKxytdnUIoeTD1LE",
                    "AIzaSyAsyojhnQpBVstuZ-gVdPRAWqcR18d1AGk", "AIzaSyCoTexsrMvR2XheZerV3mNwLyAi14KJR4o", "AIzaSyBPq9x7-QKBNYmFTVwSoQe3pCZosVox-nM",
                    "AIzaSyBKLWcDmmxCxO-6TKPqTdiwgSanMDTjBdM", "AIzaSyAqwj0Bo8yOy9g5ezdY5F2N7-ruAAasXoE", "AIzaSyC-ZMulBk9Ajl-eXu1UmkbHn1fQ3Cv8Aps",
                    "AIzaSyDQGRubx9rjBP2upAM4M-WZq9g_TyHPkts", "AIzaSyAtucgXq6cjwlPOu1_luJuwdHPSYmtyUhA", "AIzaSyAYHyVm0Rb41EqxV-tiORK8tHrBZH9A61Q",
                    "AIzaSyAucysD5qkuicuo6SPW5viJHyhRMZnm0fU", "AIzaSyBoCqYUBKEHyZQ3oiuL-kSM6d5Nwdo419Y", "AIzaSyDuzw7pl_9Y4UUf-6ZwnZCwqsI0f7BObhU",
                    "AIzaSyDk0OV0O_ALCvWWQ5It8ZemrGkQslSXzas", "AIzaSyBUd57LeQmShKI2uYY8YNrHBJPSpyOHnrE", "AIzaSyBunroxtNmHba1hlqpA8ybAXv2Pochrp0s",
                    "AIzaSyB-di9nn-OyoH0QX_xwB2Qs30okGgX1wYw", "AIzaSyBtYC4fSf1DYbm8fgV44gmGynv7Y9va41A", "AIzaSyAsWT3LVu8mCkmj-PGQQ0wnEqtd8ekTJXU",
                    "AIzaSyAbK-75k9lCLyaVKYikdH_Yq5WKU2Ldr0s", "AIzaSyBIIZ9B7n6gDxiulH4YdaDhYopksQhspaw", "AIzaSyDbnvnJ3b6Z6bhbM1qzlqJamjFkFzMYKyk",
                    "AIzaSyAh6s5e-f7k_duUAiP7ormSb1nU_XYIprI", "AIzaSyDpS69bRoxELsScqhyn7uVkAr9Nv9-dgwg", "AIzaSyBvCiCfJxFfvLX3P0R67074QTWFBB_O4-0",
                    "AIzaSyApzqieoo1UWkAnGOn6TDTBUFEYJwo2lPo", "AIzaSyCeVZ85pGIIR9VLRxCze-Y9Gdfm_l-LWnM", "AIzaSyDrxb6ePWWUwggEq3W0QQKq_uJIDv8k5ro",
                    "AIzaSyC7ccAp1odjiW8OwqCR-wpdSZtbObHqNBU", "AIzaSyAO9jSkWPnRrMliEgjyAZr7pmjPvzRYd3g", "AIzaSyAsa38ID9lIbhUSvPchj7lvDbEX7xRkptk",
                    "AIzaSyA-DuicUfIpsaiFvKIEBHFH1zj_U4tC4Ss", "AIzaSyBwJhYv6kZFoDu-jtOvVyNgOtYuDxMd59Q", "AIzaSyBAcwUYQU8Xo9YG9BV1DRlBkT2_n6yLNos",
                    "AIzaSyBAzeKIwpwVORQy1MigyiXu--6EyVqa2_c", "AIzaSyDRYLin7rypyelfEdXadIrxUwSa7lBPYjI", "AIzaSyBgg9fkdf8JF9qVeHfGdF3pCXzBdpFQxOs",
                    "AIzaSyB2UJTdcjs4Te7vwhbAP56SiqjWDY0WbMA", "AIzaSyBeV5xYRfsG_1qxZABCY9KF0-wyM6JKRjY", "AIzaSyAvcnwVINqWxVJSxqI-Qv2PTVLCp0Y6JLE",
                    "AIzaSyA3gOkc8nbtP7TWtre-foEUoIgSibI0nOs", "AIzaSyDJ0K5maPPlLeK53qIpZIEqWPLH2KIrytg", "AIzaSyCJAttUU-ewhwAi1wNv6EN6ZMe8t0PXOsM",
                    "AIzaSyBIu9YnUnnntK3U4VmU9EkJieeWdFZ5Da8", "AIzaSyBHlau9XElHmkVal0Ot3QnzpV52gfWOBIM", "AIzaSyAt0kehyl8z9VBLe9IJA83n_tEei9hZajs",
                    "AIzaSyBwI09Je-iYRu9J9rPzqLWFNsCt9Vzgn9A", "AIzaSyAZeaOdovxRhV52d79OAvLbFaWdWHHYC5s", "AIzaSyBrsQ8SSKsYg5F-9hTlK48M33A60VCPd1M",
                    "AIzaSyDS2pxclCIzI_snQdCqNoT6NBJtUGq2ASo", "AIzaSyBagdGjTIL4rMmx2KHauqvkUBszrud5zyA", "AIzaSyCAxGSfZYKXgQtBc8YeuKbijtDRTbyuKsE",
                    "AIzaSyB0vfFjDGSFpMTXCR6-0Hvf0LX1lweGBAQ", "AIzaSyBxWTWy5R_bZK4KaWhByaE6810uHXiGFek", "AIzaSyDZHityhGkNeZWv1czUocgWzGn8B7LsUFQ",
                    "AIzaSyAEll2w6nINd5fLpILjAFhHXS3XMNfNBEQ", "AIzaSyCu1qftjnBtzikC8xJ3VrCDm4RdydaO2xQ", "AIzaSyA3WHBA_a7SLAhlxpX-gYZAHxCSbBK_9q0",
                    "AIzaSyD-J2heddkNJ-uT7RoxhiZvP-mLWc4g4TI", "AIzaSyBlTv95-XHoQZuT3B7XZp9oF0V4_bXSRRY", "AIzaSyBRFTiNmIayoGn4P9f4GH--i1c2pFSrXQI",
                    "AIzaSyBsmdCg2RsWoRKXtHkQPwQwCJotWLPcO2U", "AIzaSyAWzQKAWd_FoPTJ9WfOrausrVEz3PymGPo", "AIzaSyCdVDXBwySpudRWnH8rGXzWs1B9YY-rpLg",
                    "AIzaSyDn0KKTW9osgkigXgbQvITz5EK57_K_SCQ", "AIzaSyD7oOPstmXGx137-KsZk4OClUaCTb9U_80", "AIzaSyDKHRM6BlEY_I3RKOzjcLj3G8PN5lqzvk8",
                    "AIzaSyD3DrCqvCTejkpz0GYakpu44HHby1UhWCo", "AIzaSyAWeka3BM3qxl5ZchPMS8O2x1TzMPtCNw8", "AIzaSyBHv3PGFjG4DI-s__hUKpGXoUbr8dQp3rg",
                    "AIzaSyAFrSSSfjrhaNBGFIJVmWsmAtMrFOaYVww", "AIzaSyCdTFTCW-2EUryLdSxHz-i12684FLxgSGI", "AIzaSyB8UDU_5RPnB592C2JBcXMqXuhUKnuCLdE",
                    "AIzaSyDS9xfYfRkm5KgHmBeb5dHhoRbNCap5ABU", "AIzaSyCwKglKfndGOnCu-4jBdsyv1T-bqP3Uor0", "AIzaSyD_wHGxiFvq5VuqW8g7mgouDn5QzydkXdk",
                    "AIzaSyCHhoytrTzeQ8iFGk-NdQ_o01A7EU121GA", "AIzaSyChd7orMPK_pdMIeyUaLfuEJNTw2oE0jLE", "AIzaSyDdfuDbvAjMxWMamgvBLYgWGrznYdfhcXQ",
                    "AIzaSyB14e0ZBkbF1zs-uHM6QaCP-lRf7Z7B4xw", "AIzaSyBuJ9yZsGsp33QKYNFV24bUz3RNF6JIbiY", "AIzaSyDmXhNVbaW55Zv_cZdruCOkCkuSNUeKP1o",
                    "AIzaSyDfFYanBF-lgeQn7QDUbq_yyfCMw6INuNQ", "AIzaSyCaQwXt8-Xmrja8lIwdU_iHYBDXcgGtmpM", "AIzaSyCOleGN0KGzWmCAv2dBbJ3lATDXQShFCtM",
                    "AIzaSyDXlxuG8vVKs5RLjBXByIGmJRpABfr5AO8", "AIzaSyAauH9brbha6oZ2xar-fYITKiEllsAi-xw", "AIzaSyAsowLDE9RZXNVbk0i_RAEyGwejqUHLEhU",
                    "AIzaSyAGntFu67yGt9eyZhvDVTPZyrvxNqbKUGg", "AIzaSyDzww-CHzJK2LeksSzIXD-CVasnTM7wkX8", "AIzaSyA72E2ZiWrIqmJWroalYiV4CfrcPvKQ5Gw",
                    "AIzaSyDkFALUjoYPkthPB2tDWoDv-1vW_zbTZiQ", "AIzaSyDj7a-8mOWOVt-bxVx7jeniZmjwof7pjS8", "AIzaSyAZ9a12eQL0eHS4PJReOCLeFwpt-f9XH4I",
                    "AIzaSyAly_K_Kh_47a8fhFuFASM5CPjB1BUur8g", "AIzaSyB5Fnn-duCRfarS6ABNa5dl1RDmb_DGzVE", "AIzaSyA6cdeZRbNSjhYL5lpBYcJ1Et5b2yduTIk",
                    "AIzaSyBif6Id0nRDDkZ-uwTVc0Tw9FJeh4li7Ng", "AIzaSyCs_yabMVob4Ej3hnj3Ide5jgAsmfK_pnE", "AIzaSyB3mls_XwMrNqaEtfDNicjVIEyD8SFvtxQ",
                    "AIzaSyCtfWzZKxuGmAPgrB86NPOI0URy9yQqkcA", "AIzaSyDcL4TiDdmi83rjjvUaE8WeDCR6N_r0hxI", "AIzaSyDo6bKAC7iSTNwB-Yv29uzRH8Kja1rMJHE",
                    "AIzaSyAlFz1gisbE04AgTbR_qWxM3V_1vlv2aEE", "AIzaSyAr31SW3m1kD6jgrXSgVgW-5pHIqx18PHY", "AIzaSyDQM4A9FYAh-gxI_8StwN4N3Zb6sgDeZvI",
                    "AIzaSyDksrea_IlbLvthHkbk3uMGoQaDeQc3Pf0", "AIzaSyBNoDcY5HhlBcn_ZAPw1HviIEAQAlfclRE", "AIzaSyAHYQ2XpXhjuONS1-SM6nlbjZUhYH78nic",
                    "AIzaSyAqmT9EwtTYwNO7lP2VvCeyyi39ocsPZZg", "AIzaSyCO2XbW7N0qFEgV-dJ8B9W5WowFdgh_K4Q", "AIzaSyAoi_WLbgylGV2XgB-AcukZIaKDstMgXkg",
                    "AIzaSyAkWJZ67G9__XETRLRwaY9PEXbDxBZPWwM", "AIzaSyA5vxHdWLM_Ls4Rp1EIg7YUctuMcQkYijo", "AIzaSyAJx75PkqEdjys4GXbh-86AtBZAurTYKXY",
                    "AIzaSyC_-58x16UII3wO6JxrzB6ARiaXh080jik", "AIzaSyA1Apm83V_ldw0pPiPAp7VI6U8DohCFgaA", "AIzaSyDNNRpvDO9qvv3hFKjebgqyLzXWEQGd_48",
                    "AIzaSyAeK2HyDlwumVRaA1dItY4UXILAwZV9wfI", "AIzaSyCwKr53oqisZAsvIgpgIOuHkjafh9QYADI", "AIzaSyA-1omWRVFSNzj2xT5D7VgTYYryNKii41c",
                    "AIzaSyAz_Z3xZMbE9gg63QA089KxA2-SLZ08Bu8", "AIzaSyBudlhcfVqhvgj92VSpIRr2tjE8Gr8X1zc", "AIzaSyCoeSxy0UkXp9MuK7FCK6pPvH9r-gAZ5W4",
                    "AIzaSyCmYkUFR7AWF4mzWY3iVSF2PgTedRV2SQ4", "AIzaSyABTMaQbkUXewk3KFljt-NnsNNgvKw73-0", "AIzaSyC4k8GhDBKq1bJtrxgLNL8zTvw9dLjzOks",
                    "AIzaSyA8P_pIt6OnpiB_OGpoX5oxUPq4p9zxn9s", "AIzaSyAdpxpJtBkqiFwVGtMpfaqTonHCxBrHY34", "AIzaSyC-P3WjAZfrO-JnuyR0I7Bc9H-a5Xyp1Yc",
                    "AIzaSyCRlahnJSCZXoQ4-cV_XhEZf3ea9elAjWQ", "AIzaSyCJCmX1OFvnU4p1-l9Z7utKx_YFgaMcnys", "AIzaSyCoraA6ISWfGR0LblFUd5gsTKzFkV7W5rI",
                    "AIzaSyBQNjMuoMOK4DXQMr7PUt8cmrE0M5rpe0s", "AIzaSyDvA_TYHIJ6OaLtEmpH2vmTXjKSoASRUZc", "AIzaSyDLB_ryWx9cvt8M4AUGV4ODqCPAnoh3oiA",
                    "AIzaSyCuCpf6_JBFzrLlZPpeQscV9hYN0Eja4cI", "AIzaSyDfM-KfnCcZ7Nd8V4gqKS_s9FMwlG1ebCs", "AIzaSyB30eCVCvdtciP4DNfauiu5Xrpk0a6hlTA",
                    "AIzaSyBSN5Ah80gVdZfQIdp56ZMltDNNyEouaAM", "AIzaSyCUXOn38nZJplR9BIjLjnEisCspf_U5kV4", "AIzaSyAd_i0cqQ1JiSF-x7uHtnM69qmPqe-ePfo",
                    "AIzaSyDrTtgWPSxRnWsvGrzSio1dGH1KNCf3kso", "AIzaSyBDh9ah5oT56ySC01MCjS8v4Sv0O3201pc", "AIzaSyDjaxLJoE1KXzAgLyOYbDeOOVHqqN7s8AE",
                    "AIzaSyAnxohUilcbBy__DOaOFbMCH75D6UwabSk", "AIzaSyC5KWG0O_osfiTF_ADnrbOfv2nBmr6XwSM", "AIzaSyC8hSpXK9WSWum0BlvhjkKJM-0pri6VXmA",
                    "AIzaSyD0VJ-O1aRfGAdFDSP9L6UjfMZw7tTW6OE", "AIzaSyCfcRyhqcFw4C8hq2F18BKtklgbXSSLRlc", "AIzaSyD2QzIlqpmgFiuTFAVWtjjek8zpjgU5TIA",
                    "AIzaSyDn-Mgh-L4FCK78HIx43-OfPcHbrvmoOPc", "AIzaSyANkpKqeJBPl1NrMRR4mdiP_xc_wWboCNw", "AIzaSyB4p7exzjcJkJn_VUfZVRIaLtPISJK0468",
                    "AIzaSyDWOOl2gZiX79Sge1P2_nUaLjsv4lDAQbs", "AIzaSyBX_46WskvMm1_cxn-E2VGvDePJjYcIqgI", "AIzaSyDTLrTYvT_oGDTi639N_XdyBVyRUltwbYI",
                    "AIzaSyDDf1b7TuZZznMi5PFSGvHEjrPMXH4cUHY", "AIzaSyBK_el6CbIhgduqdLbe9JVj5igsKr1mL9U", "AIzaSyAknSI263GBcjAtnvSXlL4iSQUVMOBYWAs",
                    "AIzaSyBujMsRhJqvtLV4tCgc84F4JR9JMMj4azI", "AIzaSyBpGRzeU7GZ-MfMB_wIQzNB9J6ZbUQTstM", "AIzaSyBpzsomOq73DYSgkHSC-aNt_dOIlKw2yJ0",
                    "AIzaSyA6Z72wy94BmdntVVnwarCjlJJGJQ9fDD8", "AIzaSyAO2-GhDaHLkvQB6ZPshiPapgo4iwg5p-g", "AIzaSyAx3Ji0TX2DlXzJwCQ32lBEE5dslU7LC6g",
                    "AIzaSyBQTIpqQIfb_KW1FViDyBnYt6aL0sjECp8", "AIzaSyAPM77jcK5ncrv2lGpvs4ZsBadFNt19K9s", "AIzaSyDy3xmljfzeL97tsf4cJ12mesXEWYAObuM",
                    "AIzaSyD7TPfx5Tlcypt-cljeiIqPSVNnU04Nixw", "AIzaSyDfpiVX8tOXRuEHeTN4SvMEfxKF2YERbzg", "AIzaSyDe3pFht_9E_IfQ4nAf24aTTPvWGSmXbDc",
                    "AIzaSyDEOWNn7jidYjHMu6jU9LfwfJIZohrBKbI", "AIzaSyBcYHh70SEf2ufGIAKKwaZWLsgJl3KC4SY", "AIzaSyCT0DeXZ6F8OA2kXeGsvbl-3fUP9B7V56I",
                    "AIzaSyCzC6YKqUWy8z0hB3tSC7Xr2JYxeaTtfEM", "AIzaSyBv9C6V6Ysjwln4erfTkCMi1jq6VpeKncA", "AIzaSyAPeKwt_3bqejhu9Jg95HNxa1lVb8NpOt0",
                    "AIzaSyDdJvP3Bx3WCxGpJBpVMZh2p_K1QxBGMjg", "AIzaSyC2xLi6fRgTHt1iVxX1PLZ_esxio-DUEn4", "AIzaSyCEoARjmnZfz1ITbvtCzI8x2YIFzsKqoBY",
                    "AIzaSyD-mxg9woX79fAGvfkQ-yeODHfRxvUDX_4", "AIzaSyBPSegLJFXe7i_eBDW9hVI5vrNB56IREwI", "AIzaSyCJA4CeYZhx6swRoQoYM8KGlr_W59c2JyY",
                    "AIzaSyAUrxCwMiKpRVzWgClLAhNd7xO8PRJsFtg", "AIzaSyD5BqOSjK49ZtazVs40IMGUxmgCPxZBKR4", "AIzaSyAvUtH4pLtjeqriu2yxxBWkxu4I64G2xdc",
                    "AIzaSyDcIGk2i5KTChkSYu8Nx37RDnVG_h98XhM", "AIzaSyDFNITnfaQZ_bAk3qsWfOAbH_nLyIeycBk", "AIzaSyDhG60k5Ks2oqLmlBlzuwpiMA1FAxuDtEo",
                    "AIzaSyA_AJhpt3ottqbIcc1jPabvqWNPhJzw9ms", "AIzaSyB0K5VHBP4yZRN---pb6ulqYECuXAIlaIg", "AIzaSyBGbc4fLnF7RO_C-CRtVcH11QgVjORv2KE",
                    "AIzaSyAA8k0HNLtYU5njy49cm93LegHwDfaCtkA", "AIzaSyDTeU7P2Lj_WO3Dez752hjQ_jlvFGpnC-I", "AIzaSyD-N4PvSQFgFqh-uTDpx95c59a1fDeZ6Zk",
                    "AIzaSyD5Hgtbf4ep2Uwj6L1Sy7ExcfAM0V-fzBQ", "AIzaSyBh0Sl2PAgKYWVBij8sMwg3RxapLRhXmZM", "AIzaSyC0-3wNqMprX1FxRnw0uBv-pSx4Bd8v-yg",
                    "AIzaSyAGj1SnD4Z4SE3evTsdH2nj6JLcJLIXlV0", "AIzaSyDN3YtQfJxiyaSm-76oVCwPmFoXi6y4jOU", "AIzaSyCS6R-Bx925EXNKGGTNyaG5k3gPB56FSMI",
                    "AIzaSyA_Zqh2xXDBDLjEKFvnR2EAfqnrtKPAUz0", "AIzaSyClTz2RjIY2SArTxMirzDm_EXVv-eSd94g", "AIzaSyCXkpnT_pcRXdDwxVWSboEKcOayoBtAyto",
                    "AIzaSyA1k09YJfT1zrSnsmwE-kadq-kBnQtic5A", "AIzaSyDTMbpZq5UcxpbyTQHMfUYgHh_m6rDfNFU", "AIzaSyC9ldzDYliq_kbWOqUgVypYhWyUNqenBcg",
                    "AIzaSyDxw4wSPQDU3_GQGr_TzdypigFwXDxKqAA", "AIzaSyBgRug7UyrokLfVy2WL-uR_YzW7gHTQ2VY", "AIzaSyDbhddLimM22eoJ5sV9dRfHnnZDY48uSC4",
                    "AIzaSyCHfWGpoIdvdKY7Or5znZs6Q3GYZcpMkXo", "AIzaSyAOrxj-OBHuZVewRrNJ_BN2Jm5pZp0pluM", "AIzaSyAA0F4UhuHfoVJai6ldeul40dOiubxHGWo",
                    "AIzaSyCBgp9Cza2nh9JVVo3NM1Q9b-r8Ns27g10", "AIzaSyCQ8B-c2g2n5t3eez1oyR545_6vA0h6BFA"
                ],
                "api_url": "https://generativelanguage.googleapis.com",
                "model": "gemini-1.5-flash-latest",
                "temperature": 0.7,
                "max_tokens": 2048,
                "timeout": 60
            },
            # --- REMOVED PLACEHOLDER --- 
            # "Placeholder (Please Configure)": { ... }
            # --------------------------
        }
        
        added_defaults = False
        for name, config_details in default_configs_to_ensure.items():
            if name not in existing_names:
                self.logger.info(f"Default configuration '{name}' not found. Adding it.")
                # Prepare kwargs, removing 'provider' as it's handled by type determination
                # kwargs_for_add = {k: v for k, v in config_details.items() if k not in ['name', 'provider']}
                # self.add_or_update_config(name=name, **kwargs_for_add)
                self.add_or_update_config(name=name, config_data=config_details) # MODIFIED: Pass dict directly
                added_defaults = True

        if not existing_names and not added_defaults:
             # If no configs existed AND no defaults were added (e.g., Gemini also existed)
             # Now we don't force add anything if no defaults were needed.
             logger.info("No configurations found and no default configurations needed to be added.")
             # --- REMOVED FORCING PLACEHOLDER --- 
             # placeholder_details = default_configs_to_ensure.get("Placeholder (Please Configure)")
             # if placeholder_details:
             #      kwargs_for_add = {k: v for k, v in placeholder_details.items() if k not in ['name', 'provider']}
             #      self.add_or_update_config(name="Placeholder (Please Configure)", **kwargs_for_add)
            # -------------------------------------
        elif not added_defaults:
            logger.debug("All default configurations already exist or were not needed.")

    # Add the static method helper if it doesn't exist (or import if moved)
    @staticmethod
    def _determine_provider_type_string(config_name: Optional[str], api_url: Optional[str]) -> str:
        """Determines the provider type string based on config name or URL."""
        name_lower = config_name.lower() if config_name else ""
        url_lower = api_url.lower() if api_url else ""

        if "gemini" in name_lower or "google" in url_lower:
            return "google"
        if "volcengine" in url_lower or "volces" in url_lower or "火山" in name_lower:
            return "volcengine_ark"
        if "openai" in url_lower:
            return "openai"
        if "anthropic" in url_lower:
            return "anthropic"
        if "ollama" in url_lower:
            return "ollama"
        if "xai" in url_lower or "xai" in name_lower:
             return "xai"
        if "mistral" in url_lower or "mistral" in name_lower:
             return "mistral"
        if "fireworks" in url_lower:
             return "fireworks"
        # Add Kimi, Ernie checks here
        if "kimi" in name_lower or "moonshot" in url_lower:
            return "moonshot" # Assuming Kimi uses Moonshot API
        if "ernie" in name_lower or "aip.baidubce.com" in url_lower:
            return "baidu" # Assuming Ernie uses Baidu Cloud

        # Fallback
        return "generic" # Or raise an error/log warning

    @staticmethod
    def _mask_api_key(api_key: Optional[str]) -> str:
        """Masks the API key for safe logging."""
        if not api_key:
            return "<Not Set>"
        if len(api_key) > 8:
            return f"***{api_key[-4:]}"
        return "***" # For very short keys, or to indicate it's masked

    def _load_api_keys_for_provider(self, provider_type: str, config_name: str, settings: QSettings) -> Optional[str]:
        """
        Loads API key(s) for the given provider and configuration name.
        Now always loads 'api_key' as a single string and strips whitespace.
        The UI is responsible for handling this string (displaying it, allowing user to edit to a single key).
        """
        self.logger.debug(f"Loading API key for provider '{provider_type}', config '{config_name}' (unified single key loading).")
        
        api_key_value = settings.value("api_key", None) 

        if api_key_value is not None:
            if not isinstance(api_key_value, str):
                self.logger.warning(f"[{config_name}] API key loaded from QSettings was not a string (type: {type(api_key_value)}). Converting to string. Value: '{api_key_value}'")
                api_key_value = str(api_key_value)
            
            stripped_api_key = api_key_value.strip() # STRIPPED
            if stripped_api_key != api_key_value:
                self.logger.info(f"[{config_name}] API key from QSettings stripped. Original: '{self._mask_api_key(api_key_value)}', Stripped: '{self._mask_api_key(stripped_api_key)}'")
            
            self.logger.debug(f"[{config_name}] Loaded and stripped 'api_key' from QSettings: '{self._mask_api_key(stripped_api_key)}'")
            return stripped_api_key
        else:
            self.logger.debug(f"[{config_name}] No 'api_key' found in QSettings or it was None.")
            return None

    def _load_config_data_from_settings(self, name: str, settings: QSettings) -> Optional[Dict[str, Any]]:
        """Loads configuration data for a specific config name from QSettings group."""
        config_path = f"{CONFIG_GROUP_PREFIX}/{name}"
        # 检查分组是否存在，避免 beginGroup 创建空分组
        all_groups = []
        settings.beginGroup(CONFIG_GROUP_PREFIX)
        all_groups = settings.childGroups()
        settings.endGroup()
        if name not in all_groups:
             logger.warning(f"Config group '{config_path}' not found in QSettings.")
             return None

        settings.beginGroup(config_path)
        # 检查分组内是否有键, 如果没有则认为配置无效
        if not settings.allKeys():
             settings.endGroup()
             logger.warning(f"Config group '{config_path}' exists but is empty.")
             # 可以选择删除空分组 settings.remove(config_path)
             return None

        # Load non-secret values from QSettings
        data = {
            "name": name,
            "api_url": settings.value("api_url", "", type=str),
            "model": settings.value("model", "", type=str),
            "temperature": settings.value("temperature", 0.7, type=float),
            "max_tokens": settings.value("max_tokens", 2048, type=int),
            "system_prompt": settings.value("system_prompt", "", type=str),
            "timeout": settings.value("timeout", 60, type=int),
            "api_key": None # Initialize API key as None
        }
        settings.endGroup()

        # Determine provider type: use stored, else infer, else from default.
        provider_type_from_settings = settings.value("provider", "")
        if provider_type_from_settings and isinstance(provider_type_from_settings, str):
            data['provider'] = provider_type_from_settings.lower()
            self.logger.debug(f"[{name}] Provider type from settings: '{data['provider']}'")
        else:
            # Infer provider type if not explicitly set or not a string in settings
            inferred_provider = self._determine_provider_type_string(name, data.get('api_url', ''))
            data['provider'] = inferred_provider if inferred_provider else 'generic'
            self.logger.debug(f"[{name}] Provider type inferred or from default: '{data['provider']}' (From settings: '{provider_type_from_settings}')")

        # Load API key(s) using the determined provider type
        # This will now always return a single string or None.
        api_key_value = self._load_api_keys_for_provider(data['provider'], name, settings)
        data['api_key'] = api_key_value # api_key_value is already a string or None

        data['temperature'] = settings.value("temperature", 0.7)
        data['max_tokens'] = settings.value("max_tokens", 2048)
        data['system_prompt'] = settings.value("system_prompt", "")
        data['timeout'] = settings.value("timeout", 60)

        # This ensures the structure matches what _get_default_config_for_provider might return.
        # It's important for consistency, especially if merging or comparing.
        
        final_data = {k: v for k, v in data.items() if k in ['name', 'provider', 'api_key', 'temperature', 'max_tokens', 'system_prompt', 'timeout']}
        
        self.logger.debug(f"Final loaded and merged data for '{name}': Provider='{final_data.get('provider')}'. Keys: {list(final_data.keys())}")
        return final_data

    def _get_default_config_for_provider(self, provider_name: Optional[str]) -> Dict[str, Any]:
        """Returns a default configuration for a given provider."""
        if provider_name == "google":
            return {
                "provider": "google",
                "api_key": None,
                "api_url": "https://generativelanguage.googleapis.com",
                "model": "gemini-1.5-flash-latest",
                "temperature": 0.7,
                "max_tokens": 2048,
                "timeout": 60
            }
        elif provider_name == "volcengine_ark":
            return {
                "provider": "volcengine_ark",
                "api_key": None,
                "api_url": "",
                "model": "",
                "temperature": 0.7,
                "max_tokens": 2048,
                "timeout": 60
            }
        elif provider_name == "openai":
            return {
                "provider": "openai",
                "api_key": None,
                "api_url": "",
                "model": "",
                "temperature": 0.7,
                "max_tokens": 2048,
                "timeout": 60
            }
        else:
            return {
                "provider": "generic",
                "api_key": None,
                "api_url": "",
                "model": "",
                "temperature": 0.7,
                "max_tokens": 2048,
                "timeout": 60
            }

# --- 示例用法 (用于独立测试此模块) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    # 清理旧设置以进行测试
    settings = QSettings("NewsAnalyzer", "NewsAggregator")
    settings.remove(CONFIG_GROUP_PREFIX)
    settings.remove(ACTIVE_CONFIG_KEY)
    print("--- Cleared previous test settings ---")

    manager = LLMConfigManager()

    print("\n--- Initial State ---")
    print("Available Config Names:", manager.get_config_names()) # 应为空
    print("Active Config Name:", manager.get_active_config_name()) # 应为 None

    # 添加配置
    print("\n--- Adding configurations ---")
    manager.add_or_update_config("OpenAI_Test", api_key="sk-test1", api_url="url1", model="gpt-test", temperature=0.8)
    manager.add_or_update_config("Ollama_Test", api_url="http://localhost:11434", model="llama-test") # Ollama 通常没有 key
    manager.add_or_update_config("Anthropic_Test", api_key="ak-test2", api_url="url2")

    print("Available Config Names after add:", manager.get_config_names())

    # 获取配置
    print("\n--- Getting configurations ---")
    openai_conf = manager.get_config("OpenAI_Test")
    ollama_conf = manager.get_config("Ollama_Test")
    print("OpenAI Config:", {k:v for k,v in openai_conf.items() if k!='api_key'}, "API Key:", openai_conf.get('api_key'))
    print("Ollama Config:", {k:v for k,v in ollama_conf.items() if k!='api_key'}, "API Key:", ollama_conf.get('api_key')) # Key 应为空

    # 更新配置
    print("\n--- Updating configuration ---")
    manager.add_or_update_config("OpenAI_Test", api_key="sk-updated", api_url="url1_new", model="gpt-test-upd", temperature=0.9)
    updated_openai_conf = manager.get_config("OpenAI_Test")
    print("Updated OpenAI Config:", {k:v for k,v in updated_openai_conf.items() if k!='api_key'}, "API Key:", updated_openai_conf.get('api_key'))

    # 设置激活配置
    print("\n--- Setting active config ---")
    manager.set_active_config_name("Ollama_Test")
    print("Active Config Name:", manager.get_active_config_name())
    active_conf = manager.get_active_config()
    print("Active Config Details:", {k:v for k,v in active_conf.items() if k!='api_key'}, "API Key:", active_conf.get('api_key'))

    # 删除配置
    print("\n--- Deleting configuration ---")
    manager.delete_config("Anthropic_Test")
    print("Available Config Names after delete:", manager.get_config_names())
    print("Trying to get deleted config:", manager.get_config("Anthropic_Test")) # 应为 None

    # 删除活动配置
    print("\n--- Deleting active configuration ---")
    manager.delete_config("Ollama_Test")
    print("Available Config Names after deleting active:", manager.get_config_names())
    print("Active Config Name after deleting active:", manager.get_active_config_name()) # 应为 None

    # 清理测试设置
    print("\n--- Cleaning up test settings ---")
    settings.remove(CONFIG_GROUP_PREFIX)
    settings.remove(ACTIVE_CONFIG_KEY)
    print("Test settings removed.")
    print("------------------------------------------")