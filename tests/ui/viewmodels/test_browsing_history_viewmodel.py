import pytest
from unittest.mock import MagicMock
from src.ui.viewmodels.browsing_history_viewmodel import BrowsingHistoryViewModel

# ---- Fixtures ----
@pytest.fixture
def mock_history_service():
    service = MagicMock()
    service.get_browsing_history.return_value = [
        {'id': 1, 'title': 'A'},
        {'id': 2, 'title': 'B'}
    ]
    return service

@pytest.fixture
def viewmodel(mock_history_service):
    return BrowsingHistoryViewModel(history_service=mock_history_service)

# ---- 测试用例 ----
def test_load_history(viewmodel, mock_history_service, qtbot):
    """
    测试历史加载，history_changed 信号应被发射。
    """
    # mock 数据加 access_time 字段，且在7天内
    mock_history_service.get_browsing_history.return_value = [
        {'id': 1, 'title': 'A', 'access_time': '2099-01-01T12:00:00'},
        {'id': 2, 'title': 'B', 'access_time': '2099-01-02T12:00:00'}
    ]
    viewmodel.set_filter_days(0)  # 关闭天数过滤，确保不过滤
    with qtbot.waitSignal(viewmodel.history_changed, timeout=1000) as blocker:
        viewmodel.load_history()
    assert blocker.args[0] == mock_history_service.get_browsing_history.return_value

def test_clear_history(viewmodel, mock_history_service, qtbot):
    """
    测试清空历史，history_changed 或 error_occurred 信号应被发射。
    """
    # 清空成功
    mock_history_service.clear_browse_history.return_value = True
    with qtbot.waitSignal(viewmodel.history_changed, timeout=1000):
        viewmodel.clear_history()
    mock_history_service.clear_browse_history.assert_called()

    # 清空失败
    mock_history_service.clear_browse_history.return_value = None
    with qtbot.waitSignal(viewmodel.error_occurred, timeout=1000):
        viewmodel.clear_history()
    mock_history_service.clear_browse_history.assert_called()

def test_load_history_exception(viewmodel, mock_history_service):
    """
    测试加载历史异常分支。
    """
    mock_history_service.get_browsing_history.side_effect = Exception('load error')
    result = viewmodel.load_history()
    assert result == [] 