import logging
from PyQt5.QtCore import QSettings

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
        logger.debug("LLMConfigManager initialized (QSettings Mode).")

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

    def get_config(self, name: str) -> dict | None:
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

        config = {
            "name": name,
            "api_key": self.settings.value("api_key", "", type=str),
            "api_url": self.settings.value("api_url", "", type=str),
            "model": self.settings.value("model", "", type=str),
            # 添加其他参数，例如：
            "temperature": self.settings.value("temperature", 0.7, type=float),
            "max_tokens": self.settings.value("max_tokens", 2048, type=int),
            "system_prompt": self.settings.value("system_prompt", "", type=str),
            "timeout": self.settings.value("timeout", 60, type=int),
        }
        self.settings.endGroup()
        # 日志中隐藏密钥
        log_config = {k: v for k, v in config.items() if k != 'api_key'}
        log_config['api_key'] = '******' if config.get('api_key') else '<Not Set>'
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

    def add_or_update_config(self, name: str, api_key: str = "", api_url: str = "", model: str = "", **kwargs):
        """添加新配置或更新现有指定名称的 LLM 配置。

        将配置信息保存到 QSettings 中对应的分组下。

        Args:
            name (str): 要添加或更新的配置的名称。不能为空。
            api_key (str, optional): API 密钥。默认为 ""。
            api_url (str, optional): API 端点 URL。默认为 ""。
            model (str, optional): 模型名称。默认为 ""。
            **kwargs: 其他可选配置参数，例如:
                temperature (float): 控制生成文本的随机性，默认为 0.7。
                max_tokens (int): 生成文本的最大长度，默认为 2048。
                system_prompt (str): 系统提示词，默认为 ""。
                timeout (int): API 请求超时时间（秒），默认为 60。

        Returns:
            bool: 如果操作成功则返回 True，如果名称为空则返回 False。
        """
        """
        添加新配置或更新现有配置。
        kwargs 可以包含 temperature, max_tokens, system_prompt, timeout 等。
        """
        if not name:
            logger.error("Cannot add/update config: Name cannot be empty.")
            return False

        config_path = f"{CONFIG_GROUP_PREFIX}/{name}"
        self.settings.beginGroup(config_path)
        self.settings.setValue("api_key", api_key)
        self.settings.setValue("api_url", api_url)
        self.settings.setValue("model", model)
        # 保存其他参数，确保类型正确
        self.settings.setValue("temperature", float(kwargs.get('temperature', 0.7)))
        self.settings.setValue("max_tokens", int(kwargs.get('max_tokens', 2048)))
        self.settings.setValue("system_prompt", str(kwargs.get('system_prompt', '')))
        self.settings.setValue("timeout", int(kwargs.get('timeout', 60)))
        self.settings.endGroup()
        logger.info(f"Configuration '{name}' added or updated in QSettings.")
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
            logger.info(f"Configuration '{name}' deleted from QSettings.")
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


    def get_active_config_name(self) -> str | None:
        """获取当前激活的 LLM 配置的名称。

        从 QSettings 中读取存储的活动配置名称。

        Returns:
            Optional[str]: 当前活动配置的名称，如果未设置则返回 None。
        """
        """从QSettings获取当前激活的配置名称。"""
        return self.settings.value(ACTIVE_CONFIG_KEY, None)

    def set_active_config_name(self, name: str | None):
        """设置当前激活的 LLM 配置名称。

        将指定的名称保存到 QSettings 中作为活动配置。
        如果 `name` 为 None，则清除活动配置设置。
        如果 `name` 指定的配置不存在，则记录错误。

        Args:
            name (Optional[str]): 要设置为活动配置的名称，或 None 以清除设置。
        """
        """在QSettings中设置激活的配置名称。"""
        available_names = self.get_config_names() # 现在从 QSettings 获取
        if name is None:
            self.settings.remove(ACTIVE_CONFIG_KEY)
            logger.info("Cleared active LLM configuration.")
        elif name in available_names:
            self.settings.setValue(ACTIVE_CONFIG_KEY, name)
            logger.info(f"Set '{name}' as active LLM configuration.")
        else:
            # 如果尝试激活一个不存在于 QSettings 中的配置
            logger.error(f"Cannot activate configuration '{name}': Not found in saved configurations.")
            # 可以选择自动清除激活设置
            # self.settings.remove(ACTIVE_CONFIG_KEY)

    def get_active_config(self) -> dict | None:
        """获取当前激活的 LLM 配置的详细信息。

        首先获取活动配置名称，然后调用 get_config 获取该配置的详情。
        如果活动配置名称无效或对应的配置不存在，则清除活动配置设置并返回 None。

        Returns:
            Optional[Dict[str, Any]]: 当前活动配置的详情字典，如果无活动配置或配置无效则返回 None。
        """
        """获取当前激活配置的详细信息。"""
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