"""依赖注入容器定义"""

from dependency_injector import containers, providers

# --- 导入配置和服务类 ---
# from src.config.settings_manager import SettingsManager
 # Removed import
from src.config.llm_config_manager import LLMConfigManager
from src.storage.news_storage import NewsStorage
from src.llm.prompt_manager import PromptManager
from src.utils.api_client import ApiClient
from src.llm.llm_service import LLMService
from src.core.source_manager import SourceManager
from src.core.app_service import AppService
from src.core.news_update_service import NewsUpdateService # Import NewsUpdateService
from src.utils.logger import get_logger # Import get_logger instead
from src.services.scheduler_service import SchedulerService # Correct path
from src.core.analysis_service import AnalysisService # Import new service
from src.core.event_analyzer import EventAnalyzer # Import EventAnalyzer
from src.core.history_service import HistoryService # Import HistoryService
from src.ui.viewmodels.llm_settings_viewmodel import LLMSettingsViewModel # CORRECTED IMPORT
# from src.storage.analysis_storage_service import AnalysisStorageService # Import AnalysisStorageService # REMOVED
# --- ADD COLLECTOR FACTORY IMPORT --- 
# from src.collectors import CollectorFactory # --- 移除此导入 ---
# --- 导入结束 ---

class Container(containers.DeclarativeContainer):
    """应用程序依赖注入容器"""

    # --- 配置 ---
    # 使用 Configuration Provider，允许从字典、文件等加载配置
    config = providers.Configuration()

    # 日志服务: 同样使用 Singleton 模式，并将配置注入给 setup_logger 函数
    # setup_logging is called once in main.py. Here we provide the configured logger instance.
    logger = providers.Singleton(get_logger) # Use get_logger to retrieve the configured logger

    # --- 核心服务 ---

    # 数据存储: Singleton，注入数据目录路径 (从 config 获取)
    # 使用 .provided 访问 Singleton 实例的属性
    news_storage = providers.Singleton(
        NewsStorage,
        data_dir=config.paths.data_dir # Configuration provider 直接通过属性访问
    )

    # LLM 配置管理: Singleton
    llm_config_manager = providers.Singleton(LLMConfigManager)

    # Prompt 管理: Singleton
    prompt_manager = providers.Singleton(PromptManager)

    # API 客户端: Singleton
    api_client = providers.Singleton(ApiClient)

    # LLM 服务: Singleton，注入其依赖项
    llm_service = providers.Singleton(
        LLMService,
        config_manager=llm_config_manager,
        prompt_manager=prompt_manager,
        api_client=api_client
        # override_* 参数可以在需要时通过 wiring 或直接调用 container.llm_service.override(...) 设置
    )

    # 新闻源管理: Singleton
    source_manager = providers.Singleton(
        SourceManager,
        storage=news_storage  # 注入 NewsStorage
    )

    # --- ADD COLLECTOR FACTORY PROVIDER --- 
    # collector_factory = providers.Singleton(CollectorFactory) # --- 移除此提供者 ---

    # --- 新闻更新服务: Singleton --- 
    news_update_service = providers.Singleton(
        NewsUpdateService,
        source_manager=source_manager,
        storage=news_storage
        # --- INJECT COLLECTOR FACTORY --- 
        # collector_factory=collector_factory # --- 移除此行 ---
    )

    # --- 历史记录服务: Singleton --- 
    history_service = providers.Singleton(
        HistoryService,
        storage=news_storage
    )

    # --- 分析存储服务 ---
    # REMOVED analysis_storage_service provider
    # analysis_storage_service = providers.Singleton(
    #     AnalysisStorageService,  # <--- 类名
    #     data_dir=config.paths.data_dir
    # )

    # Event Analyzer (Needs LLMService and PromptManager)
    event_analyzer = providers.Singleton(
        EventAnalyzer,
        llm_service=llm_service,
        prompt_manager=prompt_manager
    )

    analysis_service = providers.Singleton( # Add AnalysisService
        AnalysisService,
        llm_service=llm_service,
        news_storage=news_storage,
        event_analyzer=event_analyzer # Inject EventAnalyzer
    )

    # 应用服务层: 不再由容器管理，将在 main.py 中手动创建
    # 但我们可以在这里定义它，以便在 main.py 中获取，它会自动获取下面的依赖
    # If AppService is manually created in main.py, no need to define it here.
    # If we want the container to create it for main.py, define it:
    app_service = providers.Singleton(
        AppService,
        config_provider=config,  # <--- 注入 config provider
        llm_config_manager=llm_config_manager,
        storage=news_storage,
        source_manager=source_manager,
        llm_service=llm_service,
        news_update_service=news_update_service,
        analysis_service=analysis_service,
        history_service=history_service
        # analysis_storage_service=analysis_storage_service # REMOVED
    )

    # --- UI ViewModels (if managed by container) ---
    llm_settings_view_model = providers.Factory(
        LLMSettingsViewModel,
        config_manager=llm_config_manager,
        llm_service=llm_service
    )

# --- Wiring ---
# 为了让 @inject 装饰器能够工作，需要将模块连接到容器
# 通常在应用程序入口处执行 wiring
# 例如: container.wire(modules=[sys.modules[__name__], src.core.app_service, ...])

# --- 使用示例 (通常在 main.py) ---
# container = Container()
# # 获取配置实例
# settings = container.config()
# # 获取日志实例
# log = container.logger()
# # 获取 AppService 实例 (其依赖项会被自动注入)
# service = container.app_service()
# # 调用 AppService 的初始化方法（如果需要）
# service._initialize_dependencies() # 确保依赖注入完成后再初始化依赖组件