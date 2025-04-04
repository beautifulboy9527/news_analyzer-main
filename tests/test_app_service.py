# tests/test_app_service.py (修正 test_do_refresh 逻辑)
import pytest
from unittest.mock import MagicMock, patch # 导入 patch
import sys
import os
from datetime import datetime, timedelta
import logging

# 添加src目录到Python路径
# # 添加项目根目录到Python路径 (已移至 conftest.py)
# project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# sys.path.insert(0, project_root)

from src.core.app_service import AppService
from src.storage.news_storage import NewsStorage
from src.llm.llm_service import LLMService
from src.core.source_manager import SourceManager # 导入 SourceManager
from src.models import NewsSource # 导入 NewsSource
from src.models import NewsArticle # 导入 NewsArticle

# 导入容器
from src.core.containers import Container

class TestAppService:
    @pytest.fixture
    def mock_storage(self):
        return MagicMock(spec=NewsStorage)

    @pytest.fixture
    def mock_llm(self):
        return MagicMock(spec=LLMService)

    @pytest.fixture
    def mock_source_manager(self):
        # 创建 SourceManager 的 mock，并模拟其方法
        mock = MagicMock(spec=SourceManager)
        mock.get_sources.return_value = []
        return mock

    @pytest.fixture
    def caplog(self, request):
        # Ensure the logger level is set low enough for tests
        logger = logging.getLogger('news_analyzer.core.app_service')
        original_level = logger.level
        logger.setLevel(logging.INFO) # Ensure INFO logs are captured
        yield request.getfixturevalue("caplog")
        logger.setLevel(original_level) # Restore original level

    # 将以下测试方法移入类定义内
    def test_init(self, mock_storage, mock_llm, mock_source_manager): # 添加 mock_source_manager
        """测试AppService初始化"""
        container = Container()
        mock_config_manager = MagicMock()
        # # 先设置配置 (不再需要)
        # container.config.from_dict({"paths": {"data_dir": "mock/test/data"}})
        with container.llm_config_manager.override(mock_config_manager), \
             container.news_storage.override(mock_storage), \
             container.source_manager.override(mock_source_manager), \
             container.llm_service.override(mock_llm):
            service = AppService()
            # 手动注入依赖进行测试
            service.llm_config_manager = mock_config_manager
            service.storage = mock_storage
            service.source_manager = mock_source_manager
            service.llm_service = mock_llm
            service._initialize_dependencies() # 调用依赖初始化

            # 断言
            assert service.storage == mock_storage
            assert service.llm_service == mock_llm
            assert service.source_manager == mock_source_manager
            assert service.llm_config_manager == mock_config_manager

    def test_get_sources(self, mock_storage, mock_llm, mock_source_manager):
 # 需要 mock_config_manager
        """测试 get_sources 方法调用 SourceManager"""
        container = Container()
        mock_config_manager = MagicMock()
        # # 先设置配置 (不再需要)
        # container.config.from_dict({"paths": {"data_dir": "mock/test/data"}})
        with container.llm_config_manager.override(mock_config_manager), \
             container.news_storage.override(mock_storage), \
             container.source_manager.override(mock_source_manager), \
             container.llm_service.override(mock_llm):
            service = AppService() # Initialize AppService
            # 手动注入依赖进行测试
            service.llm_config_manager = mock_config_manager
            service.storage = mock_storage
            service.source_manager = mock_source_manager
            service.llm_service = mock_llm
            service._initialize_dependencies() # 调用依赖初始化

            mock_source_manager.reset_mock()
            result = service.get_sources() # 调用我们想要测试的方法
            # 断言
            mock_source_manager.get_sources.assert_called_once()
            assert result == []

    def test_add_source(self, mock_storage, mock_llm, mock_source_manager):
 # 需要 mock_config_manager
        """测试 add_source 方法调用 SourceManager"""
        container = Container()
        mock_config_manager = MagicMock()
        # # 先设置配置 (不再需要)
        # container.config.from_dict({"paths": {"data_dir": "mock/test/data"}})
        with container.llm_config_manager.override(mock_config_manager), \
             container.news_storage.override(mock_storage), \
             container.source_manager.override(mock_source_manager), \
             container.llm_service.override(mock_llm):
            service = AppService()
            # 手动注入依赖进行测试
            service.llm_config_manager = mock_config_manager
            service.storage = mock_storage
            service.source_manager = mock_source_manager
            service.llm_service = mock_llm
            service._initialize_dependencies() # 调用依赖初始化
            test_source = NewsSource(name="Test", url="http://test.com", type="rss")
            service.add_source(test_source) # 调用方法
            # 断言
            mock_source_manager.add_source.assert_called_once_with(test_source)

    def test_remove_source(self, mock_storage, mock_llm, mock_source_manager):
 # 需要 mock_config_manager
        """测试 remove_source 方法调用 SourceManager"""
        container = Container()
        mock_config_manager = MagicMock()
        # # 先设置配置 (不再需要)
        # container.config.from_dict({"paths": {"data_dir": "mock/test/data"}})
        with container.llm_config_manager.override(mock_config_manager), \
             container.news_storage.override(mock_storage), \
             container.source_manager.override(mock_source_manager), \
             container.llm_service.override(mock_llm):
            service = AppService()
            # 手动注入依赖进行测试
            service.llm_config_manager = mock_config_manager
            service.storage = mock_storage
            service.source_manager = mock_source_manager
            service.llm_service = mock_llm
            service._initialize_dependencies() # 调用依赖初始化
            service.remove_source("Test") # 调用方法
            # 断言
            mock_source_manager.remove_source.assert_called_once_with("Test")

    def test_update_source(self, mock_storage, mock_llm, mock_source_manager):
 # 需要 mock_config_manager
        """测试 update_source 方法调用 SourceManager"""
        container = Container()
        mock_config_manager = MagicMock()
        # # 先设置配置 (不再需要)
        # container.config.from_dict({"paths": {"data_dir": "mock/test/data"}})
        with container.llm_config_manager.override(mock_config_manager), \
             container.news_storage.override(mock_storage), \
             container.source_manager.override(mock_source_manager), \
             container.llm_service.override(mock_llm):
            service = AppService()
            # 手动注入依赖进行测试
            service.llm_config_manager = mock_config_manager
            service.storage = mock_storage
            service.source_manager = mock_source_manager
            service.llm_service = mock_llm
            service._initialize_dependencies() # 调用依赖初始化
            update_data = {"enabled": False}
            service.update_source("Test", update_data) # 调用方法
            # 断言
            mock_source_manager.update_source.assert_called_once_with("Test", update_data)

    def test_close_resources(self, mock_storage, mock_llm, mock_source_manager): # 需要 mock_config_manager
        """测试资源关闭方法"""
        container = Container()
        mock_config_manager = MagicMock()
        # # 先设置配置 (不再需要)
        # container.config.from_dict({"paths": {"data_dir": "mock/test/data"}})
        with container.llm_config_manager.override(mock_config_manager), \
             container.news_storage.override(mock_storage), \
             container.source_manager.override(mock_source_manager), \
             container.llm_service.override(mock_llm):
            service = AppService()
            # 手动注入依赖进行测试
            service.llm_config_manager = mock_config_manager
            service.storage = mock_storage
            service.source_manager = mock_source_manager
            service.llm_service = mock_llm
            service._initialize_dependencies() # 调用依赖初始化
            mock_collector = MagicMock()
            service.collectors = {"mock": mock_collector}
            service.close_resources() # 调用方法
            # 断言 (如果需要)
            # mock_source_manager.close.assert_called_once()

    def test_load_initial_news(self, mock_storage, mock_llm, mock_source_manager):
 # 需要 mock_config_manager
        """测试加载初始新闻数据"""
        container = Container()
        mock_config_manager = MagicMock()
        # # 先设置配置 (不再需要)
        # container.config.from_dict({"paths": {"data_dir": "mock/test/data"}})
        with container.llm_config_manager.override(mock_config_manager), \
             container.news_storage.override(mock_storage), \
             container.source_manager.override(mock_source_manager), \
             container.llm_service.override(mock_llm):

            # 模拟存储返回测试数据 (添加 link)
            test_data = [{"title": "Test", "source_name": "Test", "link": "http://example.com/test"}]
            mock_storage.load_news.return_value = test_data
            # 模拟source_manager返回源配置
            mock_source = MagicMock()
            mock_source_manager.get_sources.return_value = [mock_source]

            # 在这里实例化
            service = AppService()
            # 手动注入依赖进行测试
            service.llm_config_manager = mock_config_manager
            service.storage = mock_storage
            service.source_manager = mock_source_manager
            service.llm_service = mock_llm
            # _load_initial_news 在 __init__ 中调用，但我们需要确保 mock 生效
            # 所以在调用 _initialize_dependencies 之前设置 mock 返回值
            service._initialize_dependencies() # 调用依赖初始化

            # 断言
            assert mock_storage.load_news.call_count >= 1
            assert len(service.news_cache) == 1 # 现在应该有一条记录了

    def test_refresh_all_sources(self, mock_storage, mock_llm, mock_source_manager, caplog): # 添加 caplog
        """测试刷新所有新闻源"""
 # 需要 mock_config_manager, caplog
        container = Container()
        mock_config_manager = MagicMock()
        # # 先设置配置 (不再需要)
        # container.config.from_dict({"paths": {"data_dir": "mock/test/data"}})
        with container.llm_config_manager.override(mock_config_manager), \
             container.news_storage.override(mock_storage), \
             container.source_manager.override(mock_source_manager), \
             container.llm_service.override(mock_llm):
            service = AppService()
            # 手动注入依赖进行测试
            service.llm_config_manager = mock_config_manager
            service.storage = mock_storage
            service.source_manager = mock_source_manager
            service.llm_service = mock_llm
            service._initialize_dependencies() # 调用依赖初始化

            # 情况1: 已经在刷新中
            service._is_refreshing = True
            service.refresh_all_sources()
            assert "忽略重复请求" in caplog.text

            # 清除日志，准备测试下一种情况
            caplog.clear()

            # 情况2: 没有启用的新闻源
            service._is_refreshing = False
            mock_source_manager.get_sources.return_value = []
            service.refresh_all_sources()
            # 检查 AppService.refresh_all_sources 中源列表为空时的日志
            assert "没有启用的新闻源需要刷新" in caplog.text # 修正预期的日志信息

            # 情况3: 正常刷新流程
            mock_source = MagicMock()
            mock_source.enabled = True
            mock_source_manager.get_sources.return_value = [mock_source]

            with patch.object(service, '_async_refresh') as mock_async:
                service.refresh_all_sources()
                mock_async.assert_called_once_with([mock_source])
                assert service._is_refreshing is True

    def test_search_news(self, mock_storage, mock_llm, mock_source_manager):
        """测试新闻搜索功能"""
 # 需要 mock_config_manager
        container = Container()
        mock_config_manager = MagicMock()
        # # 先设置配置 (不再需要)
        # container.config.from_dict({"paths": {"data_dir": "mock/test/data"}})
        with container.llm_config_manager.override(mock_config_manager), \
             container.news_storage.override(mock_storage), \
             container.source_manager.override(mock_source_manager), \
             container.llm_service.override(mock_llm):
            service = AppService()
            # 手动注入依赖进行测试
            service.llm_config_manager = mock_config_manager
            service.storage = mock_storage
            service.source_manager = mock_source_manager
            service.llm_service = mock_llm
            service._initialize_dependencies() # 调用依赖初始化

            now = datetime.now()
            test_articles = [
                MagicMock(title="Test1", content="Content1", publish_time=now - timedelta(days=1)),
                MagicMock(title="Test2", summary="Summary2", publish_time=now - timedelta(days=3)),
                MagicMock(title="Old", content="Old content", publish_time=now - timedelta(days=10))
            ]
            service.news_cache = test_articles

            results = service.search_news("")
            assert len(results) == 3
            results = service.search_news("", days=2)
            assert len(results) == 1
            results = service.search_news("test", field="仅标题")
            assert len(results) == 2
            results = service.search_news("content", field="仅内容")
 # 应该匹配 "Content1" 和 "Old content"
            assert len(results) == 2 # 修正断言
            results = service.search_news("test", field="标题和内容")
            assert len(results) == 2

    def test_do_refresh(self, mock_storage, mock_llm, mock_source_manager, caplog): # 添加 caplog
        """测试实际刷新逻辑"""
 # 需要 mock_config_manager, caplog
        # 显式设置日志级别以确保捕获 ERROR
        caplog.set_level(logging.DEBUG, logger='news_analyzer.core.app_service')

        container = Container()
        mock_config_manager = MagicMock()
        # # 先设置配置 (不再需要)
        # container.config.from_dict({"paths": {"data_dir": "mock/test/data"}})
        with container.llm_config_manager.override(mock_config_manager), \
             container.news_storage.override(mock_storage), \
             container.source_manager.override(mock_source_manager), \
             container.llm_service.override(mock_llm):
            service = AppService()
            # 手动注入依赖进行测试
            service.llm_config_manager = mock_config_manager
            service.storage = mock_storage
            service.source_manager = mock_source_manager
            service.llm_service = mock_llm
            service._initialize_dependencies() # 调用依赖初始化

            test_source = MagicMock()
            test_source.enabled = True
            test_source.type = "rss"
            test_source.name = "Test"

            test_collector = MagicMock()
            test_collector.collect.return_value = [{"title": "Test", "link": "http://test.com"}]
            service.collectors = {"rss": test_collector}

            # 情况1: 正常刷新流程
            with patch.object(service, '_convert_dict_to_article') as mock_convert:
                mock_convert.return_value = MagicMock(link="http://test.com")
                service._do_refresh([test_source])

                # 断言
                test_collector.collect.assert_called_once()
                mock_storage.save_news.assert_called_once()
                assert len(service.news_cache) == 1

            # 情况2: 刷新被取消 (移出 patch 块)
            caplog.clear()
            # 重置 mock 调用次数
            test_collector.collect.reset_mock()
            mock_storage.save_news.reset_mock()
            service._cancel_refresh = True
            service._do_refresh([test_source])
            assert "刷新操作在循环中被取消" in caplog.text # 修正期望的日志

            # 情况3: 收集器抛出异常 (移出 patch 块)
            caplog.clear()
            # 重置 mock 调用次数
            test_collector.collect.reset_mock()
            mock_storage.save_news.reset_mock()
            service._cancel_refresh = False # 确保不是取消状态
            test_collector.collect.side_effect = Exception("Test error")
            service._do_refresh([test_source])
            assert "刷新来源 Test 失败" in caplog.text # 移到触发异常后立即断言

    def test_get_news_by_category(self, mock_storage, mock_llm, mock_source_manager, caplog):
        """测试按分类获取新闻"""
 # 需要 mock_config_manager, caplog
        container = Container()
        mock_config_manager = MagicMock()
        # # 先设置配置 (不再需要)
        # container.config.from_dict({"paths": {"data_dir": "mock/test/data"}})
        with container.llm_config_manager.override(mock_config_manager), \
             container.news_storage.override(mock_storage), \
             container.source_manager.override(mock_source_manager), \
             container.llm_service.override(mock_llm):
            service = AppService()
            # 手动注入依赖进行测试
            service.llm_config_manager = mock_config_manager
            service.storage = mock_storage
            service.source_manager = mock_source_manager
            service.llm_service = mock_llm
            service._initialize_dependencies() # 调用依赖初始化

            test_articles = [
                MagicMock(category="tech"),
                MagicMock(category="sports"),
                MagicMock(category="tech")
            ]
            service.news_cache = test_articles

            with patch('src.collectors.categories.STANDARD_CATEGORIES', # 添加 src. 前缀
                      {'tech': {'name': '技术'}, 'sports': {'name': '体育'}}):

                results = service.get_news_by_category("所有")
                assert len(results) == 3
                results = service.get_news_by_category("技术")
                assert len(results) == 2
                results = service.get_news_by_category("不存在")
                assert len(results) == 0
                assert "未找到显示名称" in caplog.text

    def test_record_browsing_history(self, mock_storage, mock_llm, mock_source_manager, caplog): # 添加 caplog
        """测试记录浏览历史"""
 # 需要 mock_config_manager, caplog
        container = Container()
        mock_config_manager = MagicMock()
        # # 先设置配置 (不再需要)
        # container.config.from_dict({"paths": {"data_dir": "mock/test/data"}})
        with container.llm_config_manager.override(mock_config_manager), \
             container.news_storage.override(mock_storage), \
             container.source_manager.override(mock_source_manager), \
             container.llm_service.override(mock_llm):
            service = AppService()
            # 手动注入依赖进行测试
            service.llm_config_manager = mock_config_manager
            service.storage = mock_storage
            service.source_manager = mock_source_manager
            service.llm_service = mock_llm
            service._initialize_dependencies() # 调用依赖初始化

            test_article = MagicMock(spec=NewsArticle)
            test_article.title = "Test Article"
            test_article.link = "http://test.com"
            test_article.publish_time = datetime.now()
            test_article.summary = "Test summary"
            # 添加缺失的 source_name 属性
            test_article.source_name = "Test Source"

            mock_storage.save_history_entry = MagicMock()  # 添加方法
            service.record_browsing_history(test_article)
            # 断言
            mock_storage.save_history_entry.assert_called_once()

            service.record_browsing_history("invalid")
            assert "invalid data type" in caplog.text

            del mock_storage.save_history_entry
            service.record_browsing_history(test_article)
            assert "does not have" in caplog.text