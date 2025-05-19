import pytest
from unittest.mock import MagicMock
from src.core.news_update_service import NewsUpdateService

# ---- Fixtures ----
@pytest.fixture
def mock_dependencies():
    return {
        'source_manager': MagicMock(),
        'storage': MagicMock(),
    }

# ---- 测试用例 ----
def test_refresh_all_sources_signals(mock_dependencies, qtbot):
    """
    测试 refresh_all_sources 能正确发射 refresh_complete 信号。
    """
    service = NewsUpdateService(**mock_dependencies)
    # 模拟 source_manager.get_sources 返回空，直接完成
    mock_dependencies['source_manager'].get_sources.return_value = []
    with qtbot.waitSignal(service.refresh_complete, timeout=1000) as blocker:
        service.refresh_all_sources()
    assert blocker.args[0] is True  # 成功状态


def test_refresh_all_sources_with_sources(mock_dependencies, qtbot):
    """
    测试有启用源时的刷新流程（主流程分支）。
    """
    service = NewsUpdateService(**mock_dependencies)
    # 构造一个启用的源
    mock_source = MagicMock()
    mock_source.enabled = True
    mock_source.name = 'test_source'
    mock_source.type = 'rss'
    mock_dependencies['source_manager'].get_sources.return_value = [mock_source]
    # patch _async_refresh 只做信号发射模拟
    service._async_refresh = MagicMock()
    with qtbot.waitSignal(service.refresh_started, timeout=1000):
        service.refresh_all_sources()
    service._async_refresh.assert_called_once()


def test_cancel_refresh_no_op(mock_dependencies):
    """
    测试 cancel_refresh 在未刷新时不会异常。
    """
    service = NewsUpdateService(**mock_dependencies)
    try:
        service.cancel_refresh()
    except Exception as e:
        pytest.fail(f"cancel_refresh 未刷新时抛异常: {e}") 