import pytest
from unittest.mock import MagicMock, patch
from src.core.app_service import AppService

# ---- Fixtures ----
@pytest.fixture
def mock_dependencies():
    # 构造所有依赖的 mock
    return {
        'config_provider': MagicMock(),
        'llm_config_manager': MagicMock(),
        'storage': MagicMock(),
        'source_manager': MagicMock(),
        'llm_service': MagicMock(),
        'news_update_service': MagicMock(),
        'analysis_service': MagicMock(),
        'history_service': MagicMock(),
    }

# ---- 测试用例 ----
def test_init_with_all_dependencies(mock_dependencies):
    """测试 AppService 初始化及依赖注入"""
    app_service = AppService(**mock_dependencies)
    assert app_service.storage is mock_dependencies['storage']
    assert app_service.history_service is mock_dependencies['history_service']
    assert hasattr(app_service, 'news_cache')


def test_load_initial_news_success(mock_dependencies):
    """测试初始新闻加载成功"""
    # 模拟 storage.load_news 返回新闻数据
    mock_news = [{'id': 1, 'title': '新闻A', 'link': 'a', 'source_name': '源1'}]
    mock_dependencies['storage'].load_news.return_value = mock_news

    app_service = AppService(**mock_dependencies)

    # 调用加载方法
    app_service._load_initial_news()
    assert len(app_service.news_cache) == 1, f"Cache length error. Expected 1, got {len(app_service.news_cache)}. Cache: {app_service.news_cache}" # 添加更详细的断言信息
    assert app_service.news_cache[0].title == '新闻A'


def test_load_initial_news_empty(mock_dependencies):
    """测试初始新闻加载为空"""
    mock_dependencies['storage'].load_news.return_value = []
    app_service = AppService(**mock_dependencies)
    app_service._load_initial_news()
    assert app_service.news_cache == []


def test_set_selected_news(mock_dependencies, qtbot):
    """
    测试选中新闻的管理及信号发射。
    不能 patch Qt 信号的 emit，需用 qtbot.waitSignal 监听信号。
    """
    app_service = AppService(**mock_dependencies)
    news_article = MagicMock()
    # 监听信号是否被发射
    with qtbot.waitSignal(app_service.selected_news_changed, timeout=1000) as blocker:
        app_service.set_selected_news(news_article)
    # 可选：检查信号参数
    # assert blocker.args[0] == news_article


def test_news_cache_updated_signal(mock_dependencies, qtbot):
    """
    测试新闻缓存更新信号发射。
    不能 patch Qt 信号的 emit，需用 qtbot.waitSignal 监听信号。
    """
    app_service = AppService(**mock_dependencies)
    # 监听信号并调用 _load_initial_news
    with qtbot.waitSignal(app_service.news_cache_updated, timeout=1000) as blocker:
        app_service._load_initial_news()
    # 可选：assert isinstance(blocker.args[0], list)


def test_dependency_none_behavior():
    """测试部分依赖为 None 时的健壮性"""
    # 只省略 history_service
    deps = {
        'config_provider': MagicMock(),
        'llm_config_manager': MagicMock(),
        'storage': MagicMock(),
        'source_manager': MagicMock(),
        'llm_service': MagicMock(),
        'news_update_service': MagicMock(),
        'analysis_service': MagicMock(),
        'history_service': None,
    }
    app_service = AppService(**deps)
    # 调用依赖 history_service 的方法不应抛异常
    try:
        app_service._load_initial_news()
    except Exception as e:
        pytest.fail(f"history_service 为 None 时抛异常: {e}") 