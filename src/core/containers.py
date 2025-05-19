# src/core/containers.py (修正后)
from dependency_injector import containers, providers

from src.config.llm_config_manager import LLMConfigManager
 # 修正导入
from src.storage.news_storage import NewsStorage
from src.llm.llm_service import LLMService
from src.core.source_manager import SourceManager
from src.core.app_service import AppService


class Container(containers.DeclarativeContainer):
    """
    主依赖注入容器。
    """
    # 配置
    config = providers.Configuration()

    # 服务
    llm_config_manager = providers.Singleton(
 # 重命名 provider
        LLMConfigManager,
 # 指向正确的类
        # Pass config parameters if needed, e.g., config_path=config.paths.config
        # Assuming ConfigManager doesn't need explicit config path here,
        # or it reads from a default location. Adjust if necessary.
    )

    news_storage = providers.Singleton(
        NewsStorage,
        # Provide a default value in case config is not set during test collection/override
        # data_dir=config.paths.data_dir.provide(default="data"), # 移除依赖，让 NewsStorage 使用默认值
        # Inject database path from config
    )

    llm_service = providers.Singleton(
        LLMService,
# Corrected indentation
        # config_manager=llm_config_manager, # LLMService creates its own manager
        # Inject ConfigManager
    )

    source_manager = providers.Singleton(
        SourceManager,
        storage=news_storage, # SourceManager requires NewsStorage instance
    )

    app_service = providers.Singleton(
        AppService,
# Corrected indentation
        llm_config_manager=llm_config_manager,
 # 注入正确的 provider
        # Inject ConfigManager
        storage=news_storage,
        # Inject NewsStorage
        source_manager=source_manager,
        # Inject SourceManager
        llm_service=llm_service,
        # Inject LLMService
    )