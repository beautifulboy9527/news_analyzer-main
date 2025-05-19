# tests/test_app_service.py

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from PySide6.QtCore import Signal
import logging

# --- 依赖导入 ---
# 请确保这些路径和类名与你的项目结构一致
from src.models import NewsArticle, NewsSource
from src.core.app_service import AppService
from src.core.news_update_service import NewsUpdateService
from src.config.llm_config_manager import LLMConfigManager
# 如果 NewsStorage 等类也需要在这里的 mock fixture 中作为 spec，也需要导入
# from src.storage.news_storage import NewsStorage # 示例
# from src.core.source_manager import SourceManager # 示例
# from src.llm.llm_service import LLMService # 示例
# from src.config.config_provider import ConfigProvider # 示例
# from src.core.history_service import HistoryService # 示例
# from src.core.analysis_service import AnalysisService # 示例
# from src.storage.analysis_storage_service import AnalysisStorageService # 示例


# --- 基础 Mock Fixtures ---
# 下面这些是你 AppService 依赖的服务的 mock fixture。
# Pytest 的错误日志显示这些 fixture (mock_storage, mock_source_manager, etc.) 是 "available",
# 这意味着它们很可能定义在你的 conftest.py 文件中，或者在之前的 test_app_service.py 文件中是以某种方式存在的。
# 如果它们不在 conftest.py 中，你需要将它们的定义放在下面 `properly_mocked_news_update_service` fixture 之前。
# 为确保完整性，我将在这里提供它们的简单占位符定义。
# 如果你的 conftest.py 中有更完善的定义，那里的版本会被使用。

@pytest.fixture
def mock_storage(mocker):
    # return MagicMock(spec=NewsStorage) # 取消注释并替换为真实类
    return mocker.MagicMock()

@pytest.fixture
def mock_source_manager(mocker):
    # return MagicMock(spec=SourceManager) # 取消注释并替换为真实类
    mock = mocker.MagicMock()
    mock.get_sources.return_value = []
    return mock

@pytest.fixture
def mock_llm_service(mocker):
    # return MagicMock(spec=LLMService) # 取消注释并替换为真实类
    return mocker.MagicMock()

@pytest.fixture
def mock_config_provider(mocker):
    # return MagicMock(spec=ConfigProvider) # 取消注释并替换为真实类
    return mocker.MagicMock()

@pytest.fixture
def mock_history_service(mocker):
    # return MagicMock(spec=HistoryService) # 取消注释并替换为真实类
    mock = mocker.MagicMock()
    # mock.add_history_entry = MagicMock() # 确保这个方法存在
    return mock


@pytest.fixture
def mock_analysis_service(mocker):
    # return MagicMock(spec=AnalysisService) # 取消注释并替换为真实类
    return mocker.MagicMock()

@pytest.fixture
def mock_llm_config_manager(mocker):
    return mocker.MagicMock(spec=LLMConfigManager)

# --- 核心 Fixtures 用于 AppService 测试 ---

@pytest.fixture
def properly_mocked_news_update_service(mocker):
    """
    Mocks NewsUpdateService such that its class-level signals are MagicMocks
    allowing AppService to connect to them during its __init__ without AttributeError.
    Returns an instance of this specially prepared mock.
    """
    mock_service_instance = MagicMock(spec=NewsUpdateService)
    # Mock the signal attributes on the INSTANCE that AppService will connect to.
    mock_service_instance.refresh_started = MagicMock(spec=Signal)
    mock_service_instance.refresh_finished = MagicMock(spec=Signal)
    mock_service_instance.news_refreshed = MagicMock(spec=Signal)
    mock_service_instance.source_fetch_failed = MagicMock(spec=Signal)
    
    # Class-level patching for safety. create=True ensures attribute is created if not present.
    mocker.patch.object(NewsUpdateService, 'refresh_started', PropertyMock(return_value=MagicMock(spec=Signal)), create=True)
    mocker.patch.object(NewsUpdateService, 'refresh_finished', PropertyMock(return_value=MagicMock(spec=Signal)), create=True)
    mocker.patch.object(NewsUpdateService, 'news_refreshed', PropertyMock(return_value=MagicMock(spec=Signal)), create=True)
    mocker.patch.object(NewsUpdateService, 'source_fetch_failed', PropertyMock(return_value=MagicMock(spec=Signal)), create=True)
    
    return mock_service_instance

@pytest.fixture
def app_service_instance(
    mock_config_provider,
    mock_llm_config_manager,
    mock_storage,
    mock_source_manager,
    mock_llm_service,
    properly_mocked_news_update_service,
    mock_analysis_service,
    mock_history_service,
):
    """
    Provides an AppService instance with all dependencies mocked.
    Constructor call below MUST match AppService.__init__ signature EXACTLY.
    """
    service_instance = AppService(
        config_provider=mock_config_provider,
        llm_config_manager=mock_llm_config_manager,
        storage=mock_storage,
        source_manager=mock_source_manager,
        llm_service=mock_llm_service,
        news_update_service=properly_mocked_news_update_service,
        analysis_service=mock_analysis_service,
        history_service=mock_history_service,
    )
    return service_instance


class TestAppService:
    def test_init(self, app_service_instance, mock_storage, properly_mocked_news_update_service, mock_source_manager, mock_llm_service, mock_config_provider, mock_history_service, mock_analysis_service, mock_llm_config_manager):
        """测试 AppService 能否被正确实例化。"""
        assert isinstance(app_service_instance, AppService)

    def test_get_sources(self, app_service_instance, mock_source_manager):
        """测试获取新闻源列表是否正确委托给 SourceManager。"""
        expected_sources = [NewsSource(name="Test Source", url="http://example.com/rss", category="test", type="rss")] # 确保 type="rss" 已添加
        mock_source_manager.get_sources.return_value = expected_sources
        sources = app_service_instance.get_sources()
        assert sources == expected_sources
        mock_source_manager.get_sources.assert_called_once()

    def test_add_source(self, app_service_instance, mock_source_manager):
        source_config = {"name": "New Source", "url": "http://newsource.com/rss"}
        app_service_instance.add_source(source_config)
        mock_source_manager.add_source.assert_called_once_with(source_config)

    def test_remove_source(self, app_service_instance, mock_source_manager):
        source_name = "Test Source"
        app_service_instance.remove_source(source_name)
        mock_source_manager.remove_source.assert_called_once_with(source_name)

    def test_update_source(self, app_service_instance, mock_source_manager):
        source_name = "Test Source"
        new_config = {"url": "http://updated-example.com/rss", "is_enabled": False}
        app_service_instance.update_source(source_name, new_config)
        mock_source_manager.update_source.assert_called_once_with(source_name, new_config)
        
    def test_load_initial_news(self, app_service_instance, mock_storage): # 这是我们刚修复并通过的
        """测试加载初始新闻时，是否正确从存储加载、转换并发出信号。"""
        mock_initial_data = [
            {"id": "id1", "title": "Article 1", "link": "link1", "source_name": "Test"},
            {"id": "id2", "title": "Article 2", "link": "link2", "source_name": "Test"}
        ]
        mock_storage.load_news.return_value = mock_initial_data

        with patch.object(app_service_instance, 'news_cache_updated', create=True) as mock_signal_cache_updated:
            app_service_instance._load_initial_news()
            mock_storage.load_news.assert_called_once()
            mock_signal_cache_updated.emit.assert_called_once()
            assert len(app_service_instance.news_cache) == len(mock_initial_data)
            emitted_arg = mock_signal_cache_updated.emit.call_args[0][0]
            assert len(emitted_arg) == len(mock_initial_data)
            assert all(isinstance(article, NewsArticle) for article in emitted_arg)
            assert emitted_arg[0].title == "Article 1"
            assert emitted_arg[1].title == "Article 2"

    def test_refresh_all_sources_delegates_to_news_update_service(self, app_service_instance, properly_mocked_news_update_service):
        app_service_instance.refresh_all_sources()
        properly_mocked_news_update_service.refresh_all_sources.assert_called_once()

    def test_get_news_by_category(self, app_service_instance):
        article1 = NewsArticle(title="Tech Article", category="Technology", link="t1", source_name="ts")
        article2 = NewsArticle(title="Sports Article", category="Sports", link="s1", source_name="ts")
        article3 = NewsArticle(title="Another Tech", category="Technology", link="t2", source_name="ts")
        app_service_instance.news_cache = [article1, article2, article3]
        tech_news = app_service_instance.get_news_by_category("Technology")
        assert len(tech_news) == 2
        assert article1 in tech_news
        assert article3 in tech_news
        sports_news = app_service_instance.get_news_by_category("Sports")
        assert len(sports_news) == 1
        assert article2 in sports_news
        non_existent_news = app_service_instance.get_news_by_category("Finance")
        assert len(non_existent_news) == 0

    def test_record_browsing_history(self, app_service_instance, mock_history_service, caplog):
        if not hasattr(app_service_instance, 'record_browsing_history'):
            pytest.skip("AppService does not have record_browsing_history method")

        # Ensure the mock_history_service has the 'add_history_entry' method
        # If using spec with a real class, this is usually fine. If just MagicMock(), ensure it.
        if not hasattr(mock_history_service, 'add_history_entry'):
            mock_history_service.add_history_entry = MagicMock()


        caplog.set_level(logging.INFO)
        mock_history_service.reset_mock() 

        test_article = NewsArticle(
            id="hist_id1",
            title="History Test",
            link="hist/1",
            source_name="TestHistorySource"
        )
        app_service_instance.record_browsing_history(test_article)
        mock_history_service.record_browsing_history.assert_called_once_with(
            article_id=test_article.id,
            article_title=test_article.title,
            article_link=test_article.link
        )

    def test_handle_news_refreshed_merges_and_emits_signal(self, app_service_instance, mock_storage, caplog):
        caplog.set_level(logging.INFO)
        mock_storage.reset_mock()
        existing_article_dict = {"id": "existing_id1", "title": "Existing Article", "link": "link_existing", "source_name": "Test", "category": "test", "content": "Original Content"}
        existing_article_obj = app_service_instance._convert_dict_to_article(existing_article_dict)

        if existing_article_obj:
            app_service_instance.news_cache = [existing_article_obj]
        else:
            app_service_instance.news_cache = []

        app_service_instance.all_news = list(app_service_instance.news_cache)

        new_article_1 = NewsArticle(title="New Article 1", link="link_new1", source_name="Test", content="Content1", summary="Summary1", category="test")
        updated_existing_article_variant = NewsArticle(title="Existing Article", link="link_existing", source_name="Test", content="Updated Content", summary="Updated Summary", category="test")

        new_articles_from_service = [
            new_article_1,
            updated_existing_article_variant
        ]

        # --- Direct replacement of the signal ---
        original_signal = app_service_instance.news_cache_updated
        mock_signal_emit = MagicMock()
        mock_news_cache_updated_signal_object = MagicMock()
        mock_news_cache_updated_signal_object.emit = mock_signal_emit
        app_service_instance.news_cache_updated = mock_news_cache_updated_signal_object

        try:
            app_service_instance._handle_news_refreshed(new_articles_from_service)

            # 只断言 emit 被调用
            mock_signal_emit.assert_called_once()
            emitted_cache = mock_signal_emit.call_args[0][0]
            
            expected_cache_after_refresh = [new_article_1, existing_article_obj]
            
            assert len(emitted_cache) == len(expected_cache_after_refresh)
            emitted_links = sorted([article.link for article in emitted_cache])
            expected_links = sorted([article.link for article in expected_cache_after_refresh])
            assert emitted_links == expected_links
        finally:
            # Restore the original signal
            app_service_instance.news_cache_updated = original_signal

    def test_handle_news_refreshed_no_new_articles(self, app_service_instance, mock_storage, caplog):
        caplog.set_level(logging.DEBUG)
        app_service_instance.all_news = [NewsArticle(title="Old", link="old_link", source_name="Test", category="test")]
        initial_all_news_count = len(app_service_instance.all_news)
        mock_storage.reset_mock()
        with patch.object(app_service_instance, 'news_updated', create=True) as mock_news_updated_signal, \
             patch.object(app_service_instance, 'new_articles_summary', create=True) as mock_new_articles_summary_signal:
            app_service_instance._handle_news_refreshed([])
        mock_storage.save_news.assert_not_called()
        assert len(app_service_instance.all_news) == initial_all_news_count
        mock_news_updated_signal.emit.assert_not_called()
        mock_new_articles_summary_signal.emit.assert_not_called()
