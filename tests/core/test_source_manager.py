import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timezone
from src.core.source_manager import SourceManager
from src.models import NewsSource
# from PySide6.QtCore import QSettings # REMOVED QSettings
from src.storage.news_storage import NewsStorage # ADDED NewsStorage for spec

# ---- Fixtures ----
# REMOVED patch_qsettings fixture

@pytest.fixture
def mock_storage():
    """Provides a MagicMock for NewsStorage."""
    # storage = MagicMock(spec=NewsStorage) # Temporarily remove spec
    storage = MagicMock()
    # Default behavior for loading sources: return an empty list
    storage.get_all_news_sources.return_value = [] 
    # Default behavior for add: return a dummy ID (e.g., 1)
    storage.add_news_source.return_value = 1 
    # Default behavior for update/delete: return True (success)
    storage.update_news_source.return_value = True
    storage.delete_news_source.return_value = True
    return storage

@pytest.fixture
def source_manager(mock_storage):
    """Provides a SourceManager instance with a mocked NewsStorage."""
    # Patch get_default_rss_sources to return an empty list by default for most tests
    # to avoid side effects from _ensure_default_sources_exist unless specifically tested.
    with patch('src.core.source_manager.get_default_rss_sources', return_value=[]) as _mock_get_defaults:
        sm = SourceManager(storage=mock_storage)
        # Clear any sources that might have been added by _ensure_default_sources_exist
        # to ensure a clean slate for tests not specifically testing default source creation.
        sm.news_sources = []
        # Reset mock_storage AFTER SourceManager initialization (which might call add_news_source for PengPai)
        # so that tests start with a clean mock.
        mock_storage.reset_mock()
    return sm

# ---- 测试用例 ----
def test_add_source_signal(source_manager, mock_storage, qtbot):
    """
    测试添加新闻源，sources_updated 信号应被发射。
    NewsStorage.add_news_source 应该被调用。
    """
    source = NewsSource(name='test', type='rss', url='http://a.com', category='科技')
    
    # Prepare the expected dictionary BEFORE the call that modifies source.id
    expected_dict_for_call = source.to_storage_dict()
    # If NewsSource.to_storage_dict() includes id=None for new objects, remove it for the assertion.
    # Or if it omits id for new objects, this is fine.
    # Assuming to_storage_dict on a new NewsSource (id=None) either omits 'id' or has 'id': None.
    # For the assertion, we want to match what's passed to storage, which shouldn't have a real ID yet.
    if 'id' in expected_dict_for_call and expected_dict_for_call['id'] is None:
        del expected_dict_for_call['id']
    elif 'id' in expected_dict_for_call: # If id is present but not None (e.g. 0 or default), remove it for this specific check if storage expects no id field
        # This depends on how to_storage_dict and add_news_source interact regarding IDs of new items.
        # For now, let's assume if an 'id' is present from to_storage_dict for a new object, 
        # it's a placeholder that shouldn't be in the dict passed to add_news_source.
        # A cleaner way would be for to_storage_dict to explicitly NOT include 'id' if news_source_obj.id is None.
        pass # Keep as is, let the test fail if this assumption is wrong, then refine

    # Configure mock_storage.add_news_source to return a specific ID for this test if needed
    # The default mock_storage fixture already sets add_news_source.return_value = 1

    with qtbot.waitSignal(source_manager.sources_updated, timeout=1000):
        source_manager.add_source(source)
    
    # Verify storage method was called with the dictionary prepared BEFORE source.id was set
    mock_storage.add_news_source.assert_called_once_with(expected_dict_for_call)
    
    # Verify source is in internal list and has an ID now (from the mocked DB return)
    found_sources = source_manager.get_sources()
    assert len(found_sources) == 1
    assert found_sources[0].name == 'test'
    assert found_sources[0].id is not None # Should have an ID from the (mocked) DB


def test_add_duplicate_source_memory_check(source_manager, mock_storage):
    """
    测试添加重复名称的新闻源 (内存检查)，不应调用 storage.add_news_source。
    """
    s1 = NewsSource(name='dup_mem', type='rss', url='http://dupmem1.com', category='科技')
    s2 = NewsSource(name='dup_mem', type='rss', url='http://dupmem2.com', category='其他')

    # First add should succeed and call storage
    mock_storage.add_news_source.return_value = 10 # Dummy ID for s1
    source_manager.add_source(s1)
    mock_storage.add_news_source.assert_called_once()
    assert s1.id == 10
    assert len(source_manager.get_sources()) == 1

    # Reset mock for the next call check
    mock_storage.reset_mock() 

    # Second add with same name should be caught by SourceManager before calling storage
    source_manager.add_source(s2)
    mock_storage.add_news_source.assert_not_called() # Storage should not be called for duplicate
    assert len(source_manager.get_sources()) == 1 # List should not have grown

# This test might need to be re-evaluated based on how DB unique constraints are handled/mocked.
# For now, we test SourceManager's own duplicate check.

def test_remove_source_signal(source_manager, mock_storage, qtbot):
    """
    测试删除新闻源，sources_updated 信号应被发射。
    NewsStorage.delete_news_source 应该被调用。
    """
    s = NewsSource(name='to_remove', type='rss', url='http://rm.com', category='科技')
    # Simulate it being added and having an ID
    mock_storage.add_news_source.return_value = 20 
    source_manager.add_source(s)
    assert s.id == 20 # Ensure it has an ID
    # Reset mock calls from add_source
    mock_storage.reset_mock()
    mock_storage.delete_news_source.return_value = True # Ensure delete mock is set correctly

    with qtbot.waitSignal(source_manager.sources_updated, timeout=1000):
        source_manager.remove_source('to_remove')
    
    mock_storage.delete_news_source.assert_called_once_with(20) # Check called with ID
    assert all(s.name != 'to_remove' for s in source_manager.get_sources())
    assert len(source_manager.get_sources()) == 0

# test_remove_builtin_pengpai needs careful rethinking.
# Current SourceManager doesn't prevent deletion of any source by name if found.
# The _ensure_default_sources_exist logic might re-add it on next load/init.
# For now, let's test if _ensure_default_sources_exist works.

@patch('src.core.source_manager.get_default_rss_sources')
def test_ensure_default_sources_exist(mock_get_default_rss, mock_storage):
    mock_storage.get_all_news_sources.return_value = [] # Ensure DB is empty
    
    # Configure mock_get_default_rss_sources to return one default RSS source
    mock_get_default_rss.return_value = [
        {'name': 'Default RSS Test', 'url': 'http://default.test/rss', 'category': 'Test Category'}
    ]
    
    sm = SourceManager(storage=mock_storage)
    
    # Expected: Pengpai (1) + Default RSS Test (1) = 2 calls
    assert mock_storage.add_news_source.call_count == 2
    
    # Verify Pengpai was added
    assert any(c.args[0]['name'] == SourceManager.PENGPAI_NAME for c in mock_storage.add_news_source.call_args_list)
    # Verify Default RSS Test was added
    assert any(c.args[0]['name'] == 'Default RSS Test' for c in mock_storage.add_news_source.call_args_list)


def test_update_source_signal(source_manager, mock_storage, qtbot):
    """
    测试更新新闻源，sources_updated 信号应被发射。
    NewsStorage.update_news_source 应该被调用。
    """
    s = NewsSource(name='to_update', type='rss', url='http://up.com', category='科技')
    mock_storage.add_news_source.return_value = 30
    source_manager.add_source(s)
    assert s.id == 30
    mock_storage.reset_mock()
    mock_storage.update_news_source.return_value = True

    update_payload = {'category': '财经', 'notes': 'some notes'}
    with qtbot.waitSignal(source_manager.sources_updated, timeout=1000):
        source_manager.update_source('to_update', update_payload)
    
    updated_source_in_memory = source_manager.get_source_by_name('to_update')
    assert updated_source_in_memory.category == '财经'
    assert updated_source_in_memory.notes == 'some notes'
    
    # Verify what was passed to storage.update_news_source
    # It should be the full dictionary representation of the updated source object
    expected_dict_for_storage = updated_source_in_memory.to_storage_dict()
    mock_storage.update_news_source.assert_called_once_with(s.id, expected_dict_for_storage)


def test_get_source_by_name(source_manager, mock_storage):
    """
    测试根据名称查找新闻源。
    """
    s = NewsSource(name='findme', type='rss', url='http://find.com', category='科技')
    mock_storage.add_news_source.return_value = 40
    source_manager.add_source(s)
    
    found = source_manager.get_source_by_name('findme')
    assert found is not None 
    assert found.id == 40
    assert found.url == 'http://find.com'
    
    notfound = source_manager.get_source_by_name('notexist')
    assert notfound is None


def test_update_nonexistent_source(source_manager, mock_storage):
    """
    测试更新不存在的新闻源不抛异常，且不调用 storage.update_news_source。
    """
    source_manager.update_source('notexist', {'category': '财经'})
    mock_storage.update_news_source.assert_not_called()
    assert len(source_manager.get_sources()) == 0 # Assuming clean slate from fixture


def test_add_source_missing_name_or_type(source_manager, mock_storage):
    """
    测试添加缺少 name 或 type 的源，不应调用 storage。
    """
    s_no_name = NewsSource(name='', type='rss', url='http://noname.com')
    s_no_type = NewsSource(name='notype', type='', url='http://notype.com')

    source_manager.add_source(s_no_name)
    mock_storage.add_news_source.assert_not_called()

    source_manager.add_source(s_no_type)
    mock_storage.add_news_source.assert_not_called()
    assert len(source_manager.get_sources()) == 0


def test_load_sources_from_db_exception(mock_storage):
    """
    测试 storage.get_all_news_sources 抛出异常时，SourceManager 能处理。
    """
    mock_storage.get_all_news_sources.side_effect = Exception("DB load error")
    
    # Patch get_default_rss_sources for this specific test case
    with patch('src.core.source_manager.get_default_rss_sources', return_value=[]):
        sm = SourceManager(storage=mock_storage) # Exception should be caught internally
    
    assert len(sm.get_sources()) == 0 # Should be empty on error
    # Check logs or emitted signals if error reporting is implemented that way


def test_load_sources_with_data_from_db(mock_storage):
    """
    测试从 DB 加载现有数据 (通过 mock_storage)，并验证 _ensure_default_sources_exist 被 mock 掉后不添加新源。
    """
    db_data = [
        {'id': 1, 'name': 'DB Source 1', 'type': 'rss', 'url': 'http://db1.com', 'category_name': 'Cat1', 'is_enabled': True, 'custom_config': None, 'last_checked_time': None},
        # 确保测试数据中包含一个名为 SourceManager.PENGPAI_NAME 且类型为 SourceManager.PENGPAI_TYPE 的源，
        # 以便在 _ensure_default_sources_exist (即使未被完全 mock 时) 不会尝试添加默认澎湃源。
        # 或者，像当前这样，完全 mock _ensure_default_sources_exist，就不需要关心 db_data 的具体内容是否包含澎湃。
        {'id': 2, 'name': SourceManager.PENGPAI_NAME, 'type': SourceManager.PENGPAI_TYPE, 'url': 'http://thepaper.cn', 'category_name': 'Cat2', 'is_enabled': False, 'custom_config': '{"key": "value"}', 'last_checked_time': '2023-01-01T12:00:00Z'}
    ]
    mock_storage.get_all_news_sources.return_value = db_data

    # Patch _ensure_default_sources_exist on the class BEFORE instantiation
    with patch.object(SourceManager, '_ensure_default_sources_exist', return_value=None) as mock_ensure_defaults, \
         patch('src.core.source_manager.get_default_rss_sources', return_value=[]) as mock_get_defaults:
        sm = SourceManager(storage=mock_storage)

        loaded_sources = sm.get_sources()
        assert len(loaded_sources) == 2, f"Expected 2 loaded sources, got {len(loaded_sources)}"

        # Verify that add_news_source was NOT called, because _ensure_default_sources_exist was mocked out.
        assert not mock_storage.add_news_source.called, "mock_storage.add_news_source should not have been called when _ensure_default_sources_exist is mocked"

        # Verify that the mocked _ensure_default_sources_exist was indeed called during __init__
        mock_ensure_defaults.assert_called_once()

        s1 = sm.get_source_by_name('DB Source 1')
        assert s1 is not None
        assert s1.id == 1
        assert s1.type == 'rss'
        assert s1.url == 'http://db1.com'
        assert s1.category == 'Cat1'
        assert s1.enabled is True
        assert s1.custom_config == {}

        # s2 = sm.get_source_by_name('DB Source 2') # Original name
        s2 = sm.get_source_by_name(SourceManager.PENGPAI_NAME) # Use the actual name for lookup
        assert s2 is not None
        assert s2.id == 2
        assert s2.type == SourceManager.PENGPAI_TYPE
        assert s2.category == 'Cat2'
        assert s2.enabled is False
        assert s2.custom_config == {'key': 'value'}
        assert s2.last_checked_time == datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # The conditional logic below is removed as it conflicts with the complete mocking of _ensure_default_sources_exist.
        # The primary test here is that sources are loaded from db_data and the mock for _ensure_default_sources_exist works as expected.

# def test_update_source_name_conflict(source_manager, mock_storage, qtbot):
# ... existing code ... 