import pytest
from unittest.mock import MagicMock
from src.ui.viewmodels.source_viewmodel import SourceViewModel

# ---- Fixtures ----
@pytest.fixture
def mock_source_manager():
    manager = MagicMock()
    manager.get_sources.return_value = [
        {'name': 'A', 'url': 'http://a.com'},
        {'name': 'B', 'url': 'http://b.com'}
    ]
    return manager

@pytest.fixture
def viewmodel(mock_source_manager):
    return SourceViewModel(source_manager=mock_source_manager)

# ---- 测试用例 ----
def test_add_source(viewmodel, mock_source_manager, qtbot):
    """
    测试添加新闻源，sources_changed 信号应被发射。
    """
    source = {'name': 'C', 'url': 'http://c.com'}
    with qtbot.waitSignal(viewmodel.sources_changed, timeout=1000):
        viewmodel.add_source(source)
    mock_source_manager.add_source.assert_called_with(source)

def test_remove_source(viewmodel, mock_source_manager, qtbot):
    """
    测试删除新闻源，sources_changed 信号应被发射。
    """
    source = {'name': 'A', 'url': 'http://a.com'}
    with qtbot.waitSignal(viewmodel.sources_changed, timeout=1000):
        viewmodel.remove_source(source)
    mock_source_manager.remove_source.assert_called_with(source)

def test_update_source(viewmodel, mock_source_manager, qtbot):
    """
    测试更新新闻源，sources_changed 信号应被发射。
    """
    old = {'name': 'A', 'url': 'http://a.com'}
    new = {'name': 'A', 'url': 'http://a2.com'}
    with qtbot.waitSignal(viewmodel.sources_changed, timeout=1000):
        viewmodel.update_source(old, new)
    mock_source_manager.update_source.assert_called_with(old, new)

def test_get_sources_exception(viewmodel, mock_source_manager):
    """
    测试获取新闻源异常分支。
    """
    mock_source_manager.get_sources.side_effect = Exception('load error')
    result = viewmodel.get_sources()
    assert result == []

def test_add_source_manager_none(qtbot):
    """
    manager 为 None 时，add_source 不抛异常，sources_changed 信号正常发射。
    """
    vm = SourceViewModel(source_manager=None)
    with qtbot.waitSignal(vm.sources_changed, timeout=1000):
        vm.add_source({'name': 'X', 'url': 'http://x.com'})

def test_remove_source_manager_none(qtbot):
    """
    manager 为 None 时，remove_source 不抛异常，sources_changed 信号正常发射。
    """
    vm = SourceViewModel(source_manager=None)
    with qtbot.waitSignal(vm.sources_changed, timeout=1000):
        vm.remove_source({'name': 'X', 'url': 'http://x.com'})

def test_update_source_manager_none(qtbot):
    """
    manager 为 None 时，update_source 不抛异常，sources_changed 信号正常发射。
    """
    vm = SourceViewModel(source_manager=None)
    with qtbot.waitSignal(vm.sources_changed, timeout=1000):
        vm.update_source({'name': 'X'}, {'name': 'Y'})

def test_get_sources_manager_none():
    """
    manager 为 None 时，get_sources 返回空列表。
    """
    vm = SourceViewModel(source_manager=None)
    assert vm.get_sources() == []

def test_add_source_edge_cases(viewmodel, qtbot):
    """
    add_source 传入 None、空 dict 等边界情况不抛异常。
    """
    with qtbot.waitSignal(viewmodel.sources_changed, timeout=1000):
        viewmodel.add_source(None)
    with qtbot.waitSignal(viewmodel.sources_changed, timeout=1000):
        viewmodel.add_source({})

def test_remove_source_edge_cases(viewmodel, qtbot):
    """
    remove_source 传入 None、空 dict 等边界情况不抛异常。
    """
    with qtbot.waitSignal(viewmodel.sources_changed, timeout=1000):
        viewmodel.remove_source(None)
    with qtbot.waitSignal(viewmodel.sources_changed, timeout=1000):
        viewmodel.remove_source({})

def test_update_source_edge_cases(viewmodel, qtbot):
    """
    update_source 传入 None、空 dict 等边界情况不抛异常。
    """
    with qtbot.waitSignal(viewmodel.sources_changed, timeout=1000):
        viewmodel.update_source(None, None)
    with qtbot.waitSignal(viewmodel.sources_changed, timeout=1000):
        viewmodel.update_source({}, {}) 