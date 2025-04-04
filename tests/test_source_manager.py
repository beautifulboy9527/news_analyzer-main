# tests/test_source_manager.py
import pytest
from unittest.mock import patch, MagicMock, call
from PyQt5.QtCore import QSettings, QObject # QObject needed for QSignalSpy
from PyQt5.QtTest import QSignalSpy # Import QSignalSpy from QtTest

from src.core.source_manager import SourceManager
from src.models import NewsSource

# 模拟 QSettings
@pytest.fixture
def mock_qsettings(mocker):
    """Fixture to mock QSettings."""
    # 使用 MagicMock 模拟 QSettings 实例
    mock = MagicMock(spec=QSettings)
    # 存储模拟的数据
    settings_data = {}

    # 模拟 value() 方法
    def mock_value(key, default=None, type=None):
        # print(f"Mock QSettings: Getting value for key '{key}', default: {default}")
        return settings_data.get(key, default)

    # 模拟 setValue() 方法
    def mock_set_value(key, value):
        # print(f"Mock QSettings: Setting value for key '{key}': {value}")
        settings_data[key] = value

    mock.value.side_effect = mock_value
    mock.setValue.side_effect = mock_set_value
    # 模拟 clear() 方法，用于测试
    mock.clear = settings_data.clear

    # 使用 patch 来替换 QSettings 的构造函数
    # 注意：这里 patch 的目标是 'src.core.source_manager.QSettings'
    # 因为 SourceManager 在其模块内部导入了 QSettings
    mocker.patch('src.core.source_manager.QSettings', return_value=mock)
    # print("Mock QSettings initialized and patched.")
    return mock, settings_data # 返回 mock 和 data 以便在测试中设置值

# 模拟 get_default_rss_sources
@pytest.fixture
def mock_get_default_sources(mocker):
    """Fixture to mock get_default_rss_sources."""
    # print("Mocking get_default_rss_sources.")
    mock = mocker.patch('src.core.source_manager.get_default_rss_sources', return_value=[])
    return mock

# --- 测试用例 ---

def test_source_manager_initialization_empty(mock_qsettings, mock_get_default_sources):
    """测试 SourceManager 初始化时，在没有用户源和预设源的情况下的状态"""
    mock_settings_obj, settings_storage = mock_qsettings
    # 确保 QSettings 开始是空的
    settings_storage.clear()
    # 确保预设源返回空列表
    mock_get_default_sources.return_value = []

    manager = SourceManager() # 初始化会调用 _load_sources_config

    # 验证是否调用了 QSettings 的 value 方法来加载配置
    mock_settings_obj.value.assert_any_call(SourceManager.USER_RSS_SOURCES_KEY, []) # Match the actual call signature
    # 注意：由于 PENGPAI_NAME 不在 loaded_sources_dict 中，会尝试加载其启用状态
    mock_settings_obj.value.assert_any_call(SourceManager.PENGPAI_ENABLED_KEY, True, type=bool)
    # 验证是否调用了 get_default_rss_sources
    mock_get_default_sources.assert_called_once()

    # 验证初始状态（只有内置的澎湃源）
    assert len(manager.news_sources) == 1
    pengpai_source = manager.news_sources[0]
    assert pengpai_source.name == SourceManager.PENGPAI_NAME
    assert pengpai_source.type == SourceManager.PENGPAI_TYPE
    assert pengpai_source.enabled is True # 默认启用
    assert pengpai_source.is_user_added is False

def test_source_manager_initialization_with_user_sources(mock_qsettings, mock_get_default_sources):
    """测试 SourceManager 初始化时正确加载用户配置的 RSS 源"""
    mock_settings_obj, settings_storage = mock_qsettings
    settings_storage.clear()
    mock_get_default_sources.return_value = []

    user_sources_data = [
        {'name': '用户源1', 'url': 'http://user1.com/rss', 'category': '科技', 'enabled': True, 'notes': '测试笔记'},
        {'name': '用户源2', 'url': 'http://user2.com/rss', 'category': '财经', 'enabled': False},
        {'name': '用户源1', 'url': 'http://user1-dup.com/rss'}, # 重复名称，应忽略
        {'url': 'http://no-name.com/rss'}, # 格式无效，应忽略
        'invalid_data' # 格式无效，应忽略
    ]
    settings_storage[SourceManager.USER_RSS_SOURCES_KEY] = user_sources_data
    settings_storage[SourceManager.PENGPAI_ENABLED_KEY] = False # 设置澎湃为禁用

    manager = SourceManager()

    # 验证加载的用户源数量（忽略重复名称和无效格式）+ 澎湃源
    assert len(manager.news_sources) == 3 # 用户源1, 用户源2, 澎湃

    # 验证用户源1
    user_source1 = next(s for s in manager.news_sources if s.name == '用户源1')
    assert user_source1.type == 'rss'
    assert user_source1.url == 'http://user1.com/rss'
    assert user_source1.category == '科技'
    assert user_source1.enabled is True
    assert user_source1.is_user_added is True
    assert user_source1.notes == '测试笔记'

    # 验证用户源2
    user_source2 = next(s for s in manager.news_sources if s.name == '用户源2')
    assert user_source2.type == 'rss'
    assert user_source2.url == 'http://user2.com/rss'
    assert user_source2.category == '财经'
    assert user_source2.enabled is False
    assert user_source2.is_user_added is True
    assert user_source2.notes is None

    # 验证澎湃源状态
    pengpai_source = next(s for s in manager.news_sources if s.name == SourceManager.PENGPAI_NAME)
    assert pengpai_source.enabled is False # 应从设置加载

def test_source_manager_initialization_with_preset_sources(mock_qsettings, mock_get_default_sources):
    """测试 SourceManager 初始化时正确加载预设 RSS 源"""
    mock_settings_obj, settings_storage = mock_qsettings
    settings_storage.clear()

    preset_sources_data = [
        {'name': '预设源A', 'url': 'http://preset-a.com/rss', 'category': '默认'},
        {'name': '预设源B', 'url': 'http://preset-b.com/rss'}, # 无分类
    ]
    mock_get_default_sources.return_value = preset_sources_data

    manager = SourceManager()

    # 验证加载的预设源数量 + 澎湃源
    assert len(manager.news_sources) == 3 # 预设A, 预设B, 澎湃

    # 验证预设源A
    preset_source_a = next(s for s in manager.news_sources if s.name == '预设源A')
    assert preset_source_a.type == 'rss'
    assert preset_source_a.url == 'http://preset-a.com/rss'
    assert preset_source_a.category == '默认'
    assert preset_source_a.enabled is True # 预设默认启用
    assert preset_source_a.is_user_added is False

    # 验证预设源B
    preset_source_b = next(s for s in manager.news_sources if s.name == '预设源B')
    assert preset_source_b.category == '未分类' # 默认分类
    assert preset_source_b.is_user_added is False

def test_source_manager_initialization_preset_conflict(mock_qsettings, mock_get_default_sources):
    """测试初始化时，预设源与用户源冲突（名称或URL）的处理"""
    mock_settings_obj, settings_storage = mock_qsettings
    settings_storage.clear()

    user_sources_data = [
        {'name': '冲突源名称', 'url': 'http://user-conflict.com/rss'},
        {'name': '用户源URL冲突', 'url': 'http://preset-conflict.com/rss'},
    ]
    settings_storage[SourceManager.USER_RSS_SOURCES_KEY] = user_sources_data

    preset_sources_data = [
        {'name': '冲突源名称', 'url': 'http://preset-name-conflict.com/rss'}, # 名称冲突
        {'name': '预设源URL冲突', 'url': 'http://preset-conflict.com/rss'}, # URL冲突
        {'name': '正常预设源', 'url': 'http://preset-ok.com/rss'},
    ]
    mock_get_default_sources.return_value = preset_sources_data

    manager = SourceManager()

    # 验证加载的源：用户源(2) + 正常预设源(1) + 澎湃(1) = 4
    assert len(manager.news_sources) == 4

    source_names = {s.name for s in manager.news_sources}
    assert '冲突源名称' in source_names # 应该是用户添加的版本
    assert '用户源URL冲突' in source_names
    assert '正常预设源' in source_names
    assert SourceManager.PENGPAI_NAME in source_names

    # 验证冲突源名称是用户添加的版本
    conflict_name_source = next(s for s in manager.news_sources if s.name == '冲突源名称')
    assert conflict_name_source.url == 'http://user-conflict.com/rss'
    assert conflict_name_source.is_user_added is True

    # 验证 URL 冲突的源是用户添加的版本
    conflict_url_source = next(s for s in manager.news_sources if s.name == '用户源URL冲突')
    assert conflict_url_source.url == 'http://preset-conflict.com/rss'
    assert conflict_url_source.is_user_added is True

    # 验证正常预设源被添加
    ok_preset_source = next(s for s in manager.news_sources if s.name == '正常预设源')
    assert ok_preset_source.is_user_added is False

def test_source_manager_initialization_pengpai_user_conflict(mock_qsettings, mock_get_default_sources):
    """测试初始化时，用户添加了与内置澎湃同名的源"""
    mock_settings_obj, settings_storage = mock_qsettings
    settings_storage.clear()
    mock_get_default_sources.return_value = []

    user_sources_data = [
        {'name': SourceManager.PENGPAI_NAME, 'url': 'http://user-pengpai.com/rss', 'category': '用户自定义澎湃'},
    ]
    settings_storage[SourceManager.USER_RSS_SOURCES_KEY] = user_sources_data
    # 即使设置了澎湃启用，也应该被用户源覆盖
    settings_storage[SourceManager.PENGPAI_ENABLED_KEY] = True

    manager = SourceManager()

    # 验证加载的源：只有用户添加的那个 "澎湃新闻" 源
    assert len(manager.news_sources) == 1
    user_pengpai = manager.news_sources[0]
    assert user_pengpai.name == SourceManager.PENGPAI_NAME
    assert user_pengpai.type == 'rss' # 用户添加的是 RSS 类型
    assert user_pengpai.url == 'http://user-pengpai.com/rss'
    assert user_pengpai.category == '用户自定义澎湃'
    assert user_pengpai.is_user_added is True

    # 验证 QSettings 中 PENGPAI_ENABLED_KEY 没有被读取（因为被用户源覆盖了）
    # 这有点难直接验证，但可以通过检查最终源列表来间接确认
    # 也可以检查 mock_settings_obj.value 的调用次数或参数，但可能比较脆弱
    # 确保没有调用 PENGPAI_ENABLED_KEY 的 value
    calls = mock_settings_obj.value.call_args_list
    pengpai_key_called = any(c.args[0] == SourceManager.PENGPAI_ENABLED_KEY for c in calls)
    # 在这种冲突情况下，不应该去读取 PENGPAI_ENABLED_KEY
    assert not pengpai_key_called


def test_source_manager_save_config(mock_qsettings, mock_get_default_sources):
    """测试 _save_sources_config 是否正确保存用户源和澎湃状态"""
    mock_settings_obj, settings_storage = mock_qsettings
    settings_storage.clear()
    mock_get_default_sources.return_value = [] # 没有预设源

    manager = SourceManager() # 初始化，只有澎湃

    # 添加一个用户源
    user_source = NewsSource(name='用户源A', type='rss', url='http://a.com', category='测试', enabled=False, is_user_added=True, notes="笔记")
    manager.news_sources.append(user_source)
    # 修改澎湃状态
    pengpai_source = next(s for s in manager.news_sources if s.name == SourceManager.PENGPAI_NAME)
    pengpai_source.enabled = False

    # 手动调用保存
    manager._save_sources_config()

    # 验证 QSettings 的 setValue 调用
    # 1. 验证用户 RSS 源的保存
    expected_user_data = [{
        'name': '用户源A',
        'url': 'http://a.com',
        'category': '测试',
        'enabled': False,
        'is_user_added': True,
        'notes': '笔记'
    }]
    mock_settings_obj.setValue.assert_any_call(SourceManager.USER_RSS_SOURCES_KEY, expected_user_data)

    # 2. 验证澎湃新闻状态的保存
    mock_settings_obj.setValue.assert_any_call(SourceManager.PENGPAI_ENABLED_KEY, False)

def test_get_sources_returns_copy(mock_qsettings, mock_get_default_sources):
    """测试 get_sources() 返回的是列表的副本"""
    mock_settings_obj, _ = mock_qsettings
    manager = SourceManager() # 初始化

    sources_list1 = manager.get_sources()
    sources_list2 = manager.get_sources()

    assert sources_list1 is not sources_list2 # 应该是不同的列表对象
    assert sources_list1 == sources_list2 # 内容应该相同

    # 修改返回的列表，不应影响内部列表
    if sources_list1:
        sources_list1.pop()
        assert len(manager.get_sources()) == len(sources_list2) # 内部列表长度不变

# --- 后续添加 add, remove, update 的测试 ---

# --- add_source Tests ---

def test_add_source_success(mock_qsettings, mock_get_default_sources):
    """测试成功添加一个新的 RSS 源"""
    mock_settings_obj, settings_storage = mock_qsettings
    settings_storage.clear()
    mock_get_default_sources.return_value = []
    manager = SourceManager()
    initial_count = len(manager.news_sources)

    # 监听信号
    spy = QSignalSpy(manager.sources_updated)

    new_source = NewsSource(name="新RSS源", type="rss", url="http://new.com/rss", category="新闻", enabled=True)

    manager.add_source(new_source)

    # 验证数量增加
    assert len(manager.news_sources) == initial_count + 1
    # 验证源已添加且标记为用户添加
    added = next(s for s in manager.news_sources if s.name == "新RSS源")
    assert added is not None
    assert added.url == "http://new.com/rss"
    assert added.category == "新闻"
    assert added.is_user_added is True
    # 验证保存被调用
    mock_settings_obj.setValue.assert_called() # 至少被调用一次（初始化+添加）
    # 验证信号被发射
    assert len(spy) == 1

def test_add_source_duplicate_name(mock_qsettings, mock_get_default_sources):
    """测试添加重名源时抛出 ValueError"""
    mock_settings_obj, _ = mock_qsettings
    manager = SourceManager() # 初始化，包含澎湃
    initial_count = len(manager.news_sources)

    # 尝试添加与澎湃同名的源
    duplicate_source = NewsSource(name=SourceManager.PENGPAI_NAME, type="rss", url="http://duplicate.com/rss")

    # 修正 match 字符串以匹配 add_source 的实际错误信息
    with pytest.raises(ValueError, match=f"已存在相同名称的源: {SourceManager.PENGPAI_NAME}"):
        manager.add_source(duplicate_source)

    # 确认源列表未改变，未调用保存，未发射信号
    assert len(manager.news_sources) == initial_count
    # 确认 setValue 在 add_source 内部没有被再次调用 (相对于初始化)
    initial_setvalue_calls = mock_settings_obj.setValue.call_count
    try:
        manager.add_source(duplicate_source)
    except ValueError:
        assert mock_settings_obj.setValue.call_count == initial_setvalue_calls
    else:
        pytest.fail("ValueError not raised for duplicate name")

def test_add_source_duplicate_url(mock_qsettings, mock_get_default_sources):
    """测试添加重复 URL 的 RSS 源时抛出 ValueError"""
    mock_settings_obj, settings_storage = mock_qsettings
    settings_storage.clear()
    settings_storage[SourceManager.USER_RSS_SOURCES_KEY] = [
        {'name': '现有源', 'url': 'http://existing.com/rss', 'type': 'rss'}
    ]
    manager = SourceManager()
    initial_count = len(manager.news_sources)

    duplicate_source = NewsSource(name="新名称", type="rss", url="http://existing.com/rss")

    with pytest.raises(ValueError, match=f"已存在相同 URL 的 RSS 源: {duplicate_source.url}"):
        manager.add_source(duplicate_source)

    assert len(manager.news_sources) == initial_count

# --- remove_source Tests ---

def test_remove_source_success(mock_qsettings, mock_get_default_sources):
    """测试成功移除一个用户添加的源"""
    mock_settings_obj, settings_storage = mock_qsettings
    settings_storage.clear()
    user_sources_data = [
        {'name': '待删除源', 'url': 'http://delete.me/rss', 'type': 'rss', 'is_user_added': True}
    ]
    settings_storage[SourceManager.USER_RSS_SOURCES_KEY] = user_sources_data
    manager = SourceManager()
    initial_count = len(manager.news_sources)
    assert any(s.name == '待删除源' for s in manager.news_sources)

    spy = QSignalSpy(manager.sources_updated)

    manager.remove_source('待删除源')

    assert len(manager.news_sources) == initial_count - 1
    assert not any(s.name == '待删除源' for s in manager.news_sources)
    # 验证保存被调用
    # 预期调用：初始化加载1次，移除时保存1次
    assert mock_settings_obj.setValue.call_count >= 1 # 至少调用了一次保存
    # 验证信号被发射
    assert len(spy) == 1

def test_remove_source_not_found(mock_qsettings, mock_get_default_sources):
    """测试移除不存在的源"""
    mock_settings_obj, _ = mock_qsettings
    manager = SourceManager()
    initial_count = len(manager.news_sources)
    initial_setvalue_calls = mock_settings_obj.setValue.call_count
    spy = QSignalSpy(manager.sources_updated)

    # 尝试移除不存在的源，不应抛出异常，但也不应有任何效果
    manager.remove_source('不存在的源')

    assert len(manager.news_sources) == initial_count
    assert mock_settings_obj.setValue.call_count == initial_setvalue_calls # 未调用保存
    assert len(spy) == 0 # 未发射信号

def test_remove_source_cannot_remove_builtin_pengpai(mock_qsettings, mock_get_default_sources):
    """测试尝试移除内置澎湃源时抛出 ValueError"""
    mock_settings_obj, _ = mock_qsettings
    manager = SourceManager() # 初始化，包含澎湃
    initial_count = len(manager.news_sources)
    initial_setvalue_calls = mock_settings_obj.setValue.call_count
    spy = QSignalSpy(manager.sources_updated)

    with pytest.raises(ValueError, match="不能直接删除内置的澎湃新闻源，请禁用它"):
        manager.remove_source(SourceManager.PENGPAI_NAME)

    assert len(manager.news_sources) == initial_count
    assert mock_settings_obj.setValue.call_count == initial_setvalue_calls
    assert len(spy) == 0

# --- update_source Tests ---

@pytest.fixture
def manager_with_sources(mock_qsettings, mock_get_default_sources):
    """提供一个包含多种类型源的 SourceManager 实例"""
    mock_settings_obj, settings_storage = mock_qsettings
    settings_storage.clear()
    user_sources_data = [
        {'name': '用户RSS-1', 'url': 'http://user1.com', 'category': '科技', 'enabled': True, 'is_user_added': True, 'notes': '笔记1'},
        {'name': '用户RSS-2', 'url': 'http://user2.com', 'category': '财经', 'enabled': False, 'is_user_added': True},
    ]
    settings_storage[SourceManager.USER_RSS_SOURCES_KEY] = user_sources_data
    settings_storage[SourceManager.PENGPAI_ENABLED_KEY] = True # 澎湃启用
    mock_get_default_sources.return_value = [
        {'name': '预设RSS-A', 'url': 'http://presetA.com', 'category': '默认', 'is_user_added': False}
    ]
    manager = SourceManager()
    # 清除初始化时的 setValue 调用记录，以便后续精确计数
    mock_settings_obj.setValue.reset_mock()
    return manager, mock_settings_obj

def test_update_source_success_simple_fields(manager_with_sources):
    """测试成功更新源的简单字段（category, enabled, notes）"""
    manager, mock_settings_obj = manager_with_sources
    spy = QSignalSpy(manager.sources_updated)

    update_data = {'category': '新分类', 'enabled': False, 'notes': '新笔记'}
    manager.update_source('用户RSS-1', update_data)

    updated_source = next(s for s in manager.news_sources if s.name == '用户RSS-1')
    assert updated_source.category == '新分类'
    assert updated_source.enabled is False
    assert updated_source.notes == '新笔记'

    mock_settings_obj.setValue.assert_called() # 验证保存被调用
    assert len(spy) == 1 # 验证信号被发射

def test_update_source_success_rename(manager_with_sources):
    """测试成功重命名源"""
    manager, mock_settings_obj = manager_with_sources
    spy = QSignalSpy(manager.sources_updated)

    manager.update_source('用户RSS-1', {'name': ' 新名称 '}) # 带空格，应被去除

    assert not any(s.name == '用户RSS-1' for s in manager.news_sources)
    updated_source = next(s for s in manager.news_sources if s.name == '新名称')
    assert updated_source is not None
    assert updated_source.url == 'http://user1.com' # 其他属性不变

    mock_settings_obj.setValue.assert_called()
    assert len(spy) == 1

def test_update_source_fail_rename_conflict(manager_with_sources):
    """测试重命名为已存在的名称时失败"""
    manager, mock_settings_obj = manager_with_sources
    spy = QSignalSpy(manager.sources_updated)

    with pytest.raises(ValueError, match="名称 '用户RSS-2' 已被其他源使用"):
        manager.update_source('用户RSS-1', {'name': '用户RSS-2'})

    # 验证源未被修改，未保存，未发信号
    source1 = next(s for s in manager.news_sources if s.name == '用户RSS-1')
    assert source1.name == '用户RSS-1'
    mock_settings_obj.setValue.assert_not_called()
    assert len(spy) == 0

def test_update_source_fail_rename_empty(manager_with_sources):
    """测试重命名为空字符串时失败"""
    manager, mock_settings_obj = manager_with_sources
    spy = QSignalSpy(manager.sources_updated)

    with pytest.raises(ValueError, match="新闻源名称不能为空"):
        manager.update_source('用户RSS-1', {'name': '  '}) # 空格也算空

    mock_settings_obj.setValue.assert_not_called()
    assert len(spy) == 0

def test_update_source_success_change_url(manager_with_sources):
    """测试成功更改 RSS 源的 URL"""
    manager, mock_settings_obj = manager_with_sources
    spy = QSignalSpy(manager.sources_updated)

    manager.update_source('用户RSS-1', {'url': ' http://new-url.com '})

    updated_source = next(s for s in manager.news_sources if s.name == '用户RSS-1')
    assert updated_source.url == 'http://new-url.com'

    mock_settings_obj.setValue.assert_called()
    assert len(spy) == 1

def test_update_source_fail_change_url_conflict(manager_with_sources):
    """测试更改 URL 为已存在的 URL 时失败"""
    manager, mock_settings_obj = manager_with_sources
    spy = QSignalSpy(manager.sources_updated)

    with pytest.raises(ValueError, match="URL 'http://user2.com' 已被其他 RSS 源使用"):
        manager.update_source('用户RSS-1', {'url': 'http://user2.com'})

    mock_settings_obj.setValue.assert_not_called()
    assert len(spy) == 0

def test_update_source_fail_change_url_empty(manager_with_sources):
    """测试更改 URL 为空字符串时失败"""
    manager, mock_settings_obj = manager_with_sources
    spy = QSignalSpy(manager.sources_updated)

    with pytest.raises(ValueError, match="RSS URL 不能为空"):
        manager.update_source('用户RSS-1', {'url': '   '})

    mock_settings_obj.setValue.assert_not_called()
    assert len(spy) == 0

def test_update_source_category_empty_becomes_default(manager_with_sources):
    """测试更新分类为空字符串时，应变为'未分类'"""
    manager, mock_settings_obj = manager_with_sources
    spy = QSignalSpy(manager.sources_updated)

    # 先确保初始分类不是 '未分类'
    source1 = next(s for s in manager.news_sources if s.name == '用户RSS-1')
    assert source1.category == '科技'

    manager.update_source('用户RSS-1', {'category': '  '}) # 更新为空格

    updated_source = next(s for s in manager.news_sources if s.name == '用户RSS-1')
    assert updated_source.category == '未分类'

    mock_settings_obj.setValue.assert_called()
    assert len(spy) == 1

def test_update_source_no_change(manager_with_sources):
    """测试更新数据与当前值相同时，不应触发保存和信号"""
    manager, mock_settings_obj = manager_with_sources
    spy = QSignalSpy(manager.sources_updated)

    source1 = next(s for s in manager.news_sources if s.name == '用户RSS-1')
    update_data = {'category': source1.category, 'enabled': source1.enabled}

    manager.update_source('用户RSS-1', update_data)

    mock_settings_obj.setValue.assert_not_called()
    assert len(spy) == 0

def test_update_source_not_found(manager_with_sources):
    """测试更新不存在的源"""
    manager, mock_settings_obj = manager_with_sources
    spy = QSignalSpy(manager.sources_updated)

    # 尝试更新不存在的源，不应抛异常，无效果
    manager.update_source('不存在的源', {'enabled': False})

    mock_settings_obj.setValue.assert_not_called()
    assert len(spy) == 0

def test_update_source_invalid_attribute(manager_with_sources):
    """测试尝试更新源不存在的属性"""
    manager, mock_settings_obj = manager_with_sources
    spy = QSignalSpy(manager.sources_updated)

    # 尝试更新不存在的属性，不应抛异常，无效果
    manager.update_source('用户RSS-1', {'invalid_field': 'some_value'})

    mock_settings_obj.setValue.assert_not_called()
    assert len(spy) == 0

def test_update_source_pengpai_enabled(manager_with_sources):
    """测试更新内置澎湃源的启用状态"""
    manager, mock_settings_obj = manager_with_sources
    spy = QSignalSpy(manager.sources_updated)

    # 初始状态是启用
    pengpai = next(s for s in manager.news_sources if s.name == SourceManager.PENGPAI_NAME)
    assert pengpai.enabled is True

    manager.update_source(SourceManager.PENGPAI_NAME, {'enabled': False})

    pengpai_updated = next(s for s in manager.news_sources if s.name == SourceManager.PENGPAI_NAME)
    assert pengpai_updated.enabled is False

    # 验证保存时 PENGPAI_ENABLED_KEY 被设置为 False
    # 需要检查 setValue 的调用参数
    found_pengpai_save = False
    for call_args in mock_settings_obj.setValue.call_args_list:
        if call_args.args[0] == SourceManager.PENGPAI_ENABLED_KEY and call_args.args[1] is False:
            found_pengpai_save = True
            break
    assert found_pengpai_save, "Pengpai enabled status was not saved correctly"

    assert len(spy) == 1

def test_update_source_cannot_change_pengpai_type_or_url(manager_with_sources):
    """测试不能修改内置澎湃源的类型或 URL (因为它没有URL)"""
    manager, mock_settings_obj = manager_with_sources
    spy = QSignalSpy(manager.sources_updated)

    # 尝试修改类型
    manager.update_source(SourceManager.PENGPAI_NAME, {'type': 'rss'})
    pengpai = next(s for s in manager.news_sources if s.name == SourceManager.PENGPAI_NAME)
    assert pengpai.type == SourceManager.PENGPAI_TYPE # 类型未改变

    # 尝试添加 URL (update_source 逻辑会跳过不存在的属性，但这里是检查是否会意外成功)
    manager.update_source(SourceManager.PENGPAI_NAME, {'url': 'http://some.url'})
    pengpai = next(s for s in manager.news_sources if s.name == SourceManager.PENGPAI_NAME)
    # 检查 pengpai 对象上是否没有 url 属性，或者 url 属性是 None
    assert not hasattr(pengpai, 'url') or getattr(pengpai, 'url', None) is None

    # 验证没有触发保存和信号 (因为没有有效更新)
    mock_settings_obj.setValue.assert_not_called()
    assert len(spy) == 0
