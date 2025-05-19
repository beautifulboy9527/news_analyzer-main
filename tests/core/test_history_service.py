import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from src.core.history_service import HistoryService, HistoryEntry

# ---- Fixtures ----
@pytest.fixture
def mock_storage():
    return MagicMock()

@pytest.fixture
def service(mock_storage):
    return HistoryService(storage=mock_storage)

# ---- 测试用例 ----
def test_is_read_and_mark_as_read(service, mock_storage):
    """
    测试 is_read 和 mark_as_read 方法的基本行为。
    """
    mock_storage.is_item_read.return_value = False
    assert not service.is_read('link1')
    service.mark_as_read('link1')
    mock_storage.add_read_item.assert_called_with('link1')


def test_mark_as_unread(service, mock_storage):
    """
    测试 mark_as_unread 能正确调用存储层。
    """
    service.mark_as_unread('link2')
    mock_storage.mark_item_as_unread.assert_called_with('link2')


def test_get_all_history_items(service, mock_storage):
    """
    测试 get_all_history_items 能返回历史记录列表。
    """
    now = datetime.now()
    now_minus_1_hr = datetime.now()

    mock_storage.get_browsing_history.return_value = [
        {'article_id': '1', 'article_title': 'Title 1', 'article_link': 'link1', 'viewed_at': now, 'id': 'h1'},
        {'article_id': '2', 'article_title': 'Title 2', 'article_link': 'link2', 'viewed_at': now_minus_1_hr, 'id': 'h2'}
    ]

    expected_history_entries = [
        HistoryEntry(id='h1', article_id='1', article_title='Title 1', article_link='link1', viewed_at=now),
        HistoryEntry(id='h2', article_id='2', article_title='Title 2', article_link='link2', viewed_at=now_minus_1_hr)
    ]

    history = service.get_all_history_items()

    mock_storage.get_browsing_history.assert_called_once()
    assert len(history) == 2
    assert history == expected_history_entries, \
        f"Expected {expected_history_entries}, but got {history}"


def test_get_all_history_items_empty(service, mock_storage):
    """Test get_all_history_items when storage returns empty list."""
    mock_storage.get_browsing_history.return_value = []
    history = service.get_all_history_items()
    mock_storage.get_browsing_history.assert_called_once()
    assert history == []


def test_clear_all_history_items_success(service, mock_storage, qtbot):
    """Test clearing all history items successfully."""
    with qtbot.waitSignal(service.browsing_history_updated, timeout=1000) as blocker:
        service.clear_all_history_items()
    mock_storage.clear_all_browsing_history.assert_called_once()
    assert blocker.signal_triggered


def test_is_read_storage_none():
    """
    测试 storage 为 None 时 is_read 的健壮性。
    """
    hs = HistoryService(storage=None)
    assert hs.is_read('link') is False


def test_mark_as_read_storage_none():
    """
    测试 storage 为 None 时 mark_as_read 不抛异常。
    """
    hs = HistoryService(storage=None)
    try:
        hs.mark_as_read('link')
    except Exception as e:
        pytest.fail(f"storage 为 None 时 mark_as_read 抛异常: {e}")


def test_clear_all_history_items_failure(service, mock_storage, qtbot):
    """Test clearing all history items when storage operation fails."""
    mock_storage.clear_all_browsing_history.side_effect = Exception("Clear failed")
    
    with qtbot.waitSignal(service.browsing_history_updated, timeout=1000, raising=False) as blocker:
        service.clear_all_history_items()
        
    mock_storage.clear_all_browsing_history.assert_called_once()
    assert not blocker.signal_triggered


@patch('src.core.history_service.datetime')
def test_add_history_item_success(mock_dt, service, mock_storage, qtbot):
    """Test adding a history item successfully."""
    mock_now = datetime(2023, 1, 1, 12, 0, 0)
    mock_dt.now.return_value = mock_now

    article_link = 'http://example.com/article1'
    mock_article_from_db = MagicMock()
    mock_article_from_db.id = 'db_article_id_123'
    mock_article_from_db.title = 'Test Article For History'
    mock_storage.get_article_by_link.return_value = mock_article_from_db
    
    with qtbot.waitSignal(service.browsing_history_updated, timeout=1000) as blocker:
        service.add_history_item(article_link)
        
    mock_storage.get_article_by_link.assert_called_once_with(article_link)
    mock_storage.add_browsing_history.assert_called_once_with(
        article_id='db_article_id_123', 
        viewed_at=mock_now
    )
    assert blocker.signal_triggered


def test_add_history_item_article_not_found(service, mock_storage, qtbot):
    """Test adding a history item when the article is not found in DB."""
    article_link = 'http://nonexistent.com/article'
    mock_storage.get_article_by_link.return_value = None

    with qtbot.waitSignal(service.browsing_history_updated, timeout=100, raising=False) as blocker:
        service.add_history_item(article_link)
    
    mock_storage.get_article_by_link.assert_called_once_with(article_link)
    mock_storage.add_browsing_history.assert_not_called()
    assert not blocker.signal_triggered


def test_add_history_item_storage_error(service, mock_storage, qtbot):
    """Test adding a history item when storage operation fails."""
    article_link = 'http://example.com/article_error'
    mock_storage.get_article_by_link.side_effect = Exception("DB error")

    with qtbot.waitSignal(service.browsing_history_updated, timeout=100, raising=False) as blocker:
        service.add_history_item(article_link)
        
    mock_storage.get_article_by_link.assert_called_once_with(article_link)
    mock_storage.add_browsing_history.assert_not_called()
    assert not blocker.signal_triggered


def test_remove_history_item_success(service, mock_storage, qtbot):
    """Test removing a history item successfully."""
    history_item_id_str = "123"
    with qtbot.waitSignal(service.browsing_history_updated, timeout=1000) as blocker:
        service.remove_history_item(history_item_id_str)
    
    mock_storage.delete_browsing_history_item.assert_called_once_with(history_id=123)
    assert blocker.signal_triggered


def test_remove_history_item_invalid_id_format(service, mock_storage, qtbot):
    """Test removing a history item with an invalid ID format."""
    with qtbot.waitSignal(service.browsing_history_updated, timeout=100, raising=False) as blocker:
        service.remove_history_item("not_an_int")
    
    mock_storage.delete_browsing_history_item.assert_not_called()
    assert not blocker.signal_triggered


def test_remove_history_item_storage_error(service, mock_storage, qtbot):
    """Test removing a history item when storage fails."""
    history_item_id_str = "456"
    mock_storage.delete_browsing_history_item.side_effect = Exception("Deletion failed")
    with qtbot.waitSignal(service.browsing_history_updated, timeout=100, raising=False) as blocker:
        service.remove_history_item(history_item_id_str)
        
    mock_storage.delete_browsing_history_item.assert_called_once_with(history_id=456)
    assert not blocker.signal_triggered
    
# Placeholder for other tests if needed 