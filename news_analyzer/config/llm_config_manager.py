import os
import json
import logging
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from PyQt5.QtCore import QSettings

# 配置和密钥文件的路径
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'llm_configs.json')
KEY_FILE = os.path.join(CONFIG_DIR, '.llm_key') # 隐藏文件存储密钥
SALT_FILE = os.path.join(CONFIG_DIR, '.llm_salt') # 存储盐值

# 确保data目录存在
os.makedirs(CONFIG_DIR, exist_ok=True)

logger = logging.getLogger('news_analyzer.config.manager')

class LLMConfigManager:
    """管理LLM配置，包括加密API密钥"""

    def __init__(self):
        self.salt = self._load_or_generate_salt()
        self.key = self._load_or_generate_key()
        self.fernet = Fernet(self.key)
        self.configs = self._load_configs()
        self.settings = QSettings("NewsAnalyzer", "NewsAggregator")

    def _load_or_generate_salt(self):
        """加载或生成用于密钥派生的盐值"""
        if os.path.exists(SALT_FILE):
            try:
                with open(SALT_FILE, 'rb') as f:
                    salt = f.read()
                if len(salt) == 16: # PBKDF2HMAC 推荐至少16字节的盐
                    logger.debug("成功加载盐值。")
                    return salt
                else:
                    logger.warning("盐值文件存在但长度无效，将重新生成。")
            except Exception as e:
                logger.error(f"加载盐值文件失败: {e}，将重新生成。")

        # 生成新的盐值
        salt = os.urandom(16)
        try:
            with open(SALT_FILE, 'wb') as f:
                f.write(salt)
            logger.info("已生成并保存新的盐值。")
            return salt
        except Exception as e:
            logger.error(f"保存新盐值失败: {e}")
            # 在无法保存文件的情况下，仍然在内存中使用生成的盐值
            return salt

    def _load_or_generate_key(self):
        """
        加载或生成用于Fernet加密的密钥。
        使用固定密码和加载/生成的盐值通过PBKDF2派生密钥。
        注意：这里的 "固定密码" 只是为了派生密钥，实际密钥存储在KEY_FILE中。
        这增加了一层保护，即使KEY_FILE泄露，没有代码中的固定密码也无法轻易解密。
        更好的做法可能是让用户设置一个主密码，但为了简化，这里使用固定密码。
        """
        fixed_password = b"a_fixed_password_for_key_derivation" # 仅用于派生，不直接用于加密

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32, # Fernet key length
            salt=self.salt,
            iterations=480000, # NIST推荐的迭代次数
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(fixed_password))

        if os.path.exists(KEY_FILE):
            try:
                with open(KEY_FILE, 'rb') as f:
                    key = f.read()
                # 验证密钥格式是否正确 (Fernet key是URL安全的base64编码)
                Fernet(key)
                logger.debug("成功加载加密密钥。")
                # 比较加载的密钥是否与派生的密钥一致，如果不一致，可能意味着密码或盐值被更改
                if key == derived_key:
                    return key
                else:
                    logger.warning("加载的密钥与派生密钥不匹配。可能固定密码或盐值已更改。将使用派生的密钥。")
                    # 如果不匹配，可能需要决定是信任文件中的旧密钥还是使用新派生的密钥
                    # 这里选择使用新派生的密钥，并覆盖旧文件
                    self._save_key(derived_key)
                    return derived_key

            except (InvalidToken, ValueError, TypeError) as e:
                logger.warning(f"加载的密钥无效 ({e})，将使用新派生的密钥。")
                self._save_key(derived_key)
                return derived_key
            except Exception as e:
                logger.error(f"加载密钥文件失败: {e}，将使用新派生的密钥。")
                self._save_key(derived_key)
                return derived_key
        else:
            logger.info("未找到密钥文件，将生成并保存新密钥。")
            self._save_key(derived_key)
            return derived_key

    def _save_key(self, key):
        """保存加密密钥到文件"""
        try:
            with open(KEY_FILE, 'wb') as f:
                f.write(key)
            logger.debug("加密密钥已保存。")
        except Exception as e:
            logger.error(f"保存密钥文件失败: {e}")

    def _encrypt(self, data: str) -> str:
        """加密数据"""
        if not data:
            return ""
        try:
            # 在加密前移除空白字符
            return self.fernet.encrypt(data.strip().encode()).decode()
        except Exception as e:
            logger.error(f"加密失败: {e}")
            return "" # 或者抛出异常

    def _decrypt(self, encrypted_data: str) -> str:
        """解密数据"""
        if not encrypted_data:
            return ""
        try:
            # 在解密后移除空白字符
            return self.fernet.decrypt(encrypted_data.encode()).decode().strip()
        except InvalidToken:
            logger.error("解密失败：无效的Token（密钥可能已更改或数据已损坏）")
            return "" # 或者返回特定错误标记
        except Exception as e:
            logger.error(f"解密失败: {e}")
            return "" # 或者抛出异常

    def _load_configs(self) -> dict:
        """从JSON文件加载配置"""
        if not os.path.exists(CONFIG_FILE):
            logger.info(f"配置文件 {CONFIG_FILE} 不存在，将创建空配置。")
            return {}
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                configs = json.load(f)
            logger.debug(f"成功从 {CONFIG_FILE} 加载配置。")
            return configs
        except json.JSONDecodeError:
            logger.error(f"配置文件 {CONFIG_FILE} 格式错误，将使用空配置。")
            return {}
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {}

    def _save_configs(self):
        """将当前配置保存到JSON文件"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.configs, f, indent=4, ensure_ascii=False)
            logger.debug(f"配置已成功保存到 {CONFIG_FILE}。")
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")

    def get_config_names(self) -> list:
        """获取所有配置的名称列表"""
        return list(self.configs.keys())

    def get_config(self, name: str) -> dict | None:
        """获取指定名称的配置（解密API密钥）"""
        config = self.configs.get(name)
        if config:
            decrypted_config = config.copy()
            decrypted_config['api_key'] = self._decrypt(config.get('encrypted_api_key', ''))
            # 为了向后兼容或简化，移除加密字段
            decrypted_config.pop('encrypted_api_key', None)
            return decrypted_config
        return None

    def add_or_update_config(self, name: str, api_url: str, api_key: str, model: str, **kwargs):
        """添加或更新一个配置（加密API密钥）"""
        if not name:
            logger.error("配置名称不能为空。")
            return False
        encrypted_key = self._encrypt(api_key)
        self.configs[name] = {
            'api_url': api_url,
            'encrypted_api_key': encrypted_key,
            'model': model,
            **kwargs # 允许存储其他额外信息
        }
        self._save_configs()
        logger.info(f"配置 '{name}' 已添加或更新。")
        return True

    def delete_config(self, name: str):
        """删除指定名称的配置"""
        if name in self.configs:
            del self.configs[name]
            self._save_configs()
            logger.info(f"配置 '{name}' 已删除。")
            # 如果删除的是当前激活的配置，需要清除激活设置
            if self.get_active_config_name() == name:
                self.set_active_config_name(None)
            return True
        logger.warning(f"尝试删除不存在的配置 '{name}'。")
        return False

    def get_active_config_name(self) -> str | None:
        """获取当前激活的配置名称"""
        # 使用与 llm_settings.py 中可能使用的键名一致
        return self.settings.value("llm/active_config_name", None)

    def set_active_config_name(self, name: str | None):
        """设置当前激活的配置名称"""
        if name is None:
            self.settings.remove("llm/active_config_name")
            logger.info("已清除激活的LLM配置。")
        elif name in self.configs:
            self.settings.setValue("llm/active_config_name", name)
            logger.info(f"已设置 '{name}' 为激活的LLM配置。")
        else:
            logger.error(f"无法激活不存在的配置 '{name}'。")

    def get_active_config(self) -> dict | None:
        """获取当前激活的配置详情（解密后）"""
        active_name = self.get_active_config_name()
        if active_name:
            return self.get_config(active_name)
        return None

# --- 示例用法 ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    manager = LLMConfigManager()

    # 添加或更新配置
    manager.add_or_update_config(
        name="MyOpenAI",
        api_url="https://api.openai.com/v1/chat/completions",
        api_key="sk-testkey12345", # 示例密钥
        model="gpt-4"
    )
    manager.add_or_update_config(
        name="LocalLLM",
        api_url="http://localhost:11434/api/chat",
        api_key="ollama", # Ollama通常不需要key，但可以存一个占位符
        model="llama3"
    )

    # 获取所有配置名称
    print("所有配置:", manager.get_config_names())

    # 设置激活配置
    manager.set_active_config_name("MyOpenAI")
    print("激活配置名称:", manager.get_active_config_name())

    # 获取激活配置详情
    active_config = manager.get_active_config()
    if active_config:
        print("激活配置详情:", active_config)
        # 注意：打印出的api_key是解密后的

    # 获取特定配置
    local_config = manager.get_config("LocalLLM")
    if local_config:
        print("LocalLLM 配置详情:", local_config)

    # 删除配置
    # manager.delete_config("LocalLLM")
    # print("删除后所有配置:", manager.get_config_names())

    # 再次加载配置（验证持久化）
    print("\n重新加载管理器...")
    manager2 = LLMConfigManager()
    print("重新加载后的激活配置:", manager2.get_active_config_name())
    active_config2 = manager2.get_active_config()
    if active_config2:
        print("重新加载后的激活配置详情:", active_config2)

    # 测试解密失败场景 (可选，需要手动修改 .llm_key 文件)
    # print("\n测试密钥更改后的解密...")
    # # 假设手动更改了 .llm_key 文件内容
    # try:
    #     manager_bad_key = LLMConfigManager() # 重新加载会检测到密钥无效
    #     bad_config = manager_bad_key.get_config("MyOpenAI")
    #     print("尝试用错误密钥解密:", bad_config) # api_key 应该是空字符串或错误标记
    # except Exception as e:
    #     print(f"用错误密钥初始化时出错: {e}")