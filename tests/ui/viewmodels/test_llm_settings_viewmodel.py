import pytest
from unittest.mock import MagicMock, patch, call
from PyQt5.QtCore import QObject, pyqtSignal # Use real Qt objects

# Now import the ViewModel and other necessary modules
from src.ui.viewmodels.llm_settings_viewmodel import LLMSettingsViewModel
# LLMConfig is not a class, the manager uses dicts
from src.config.llm_config_manager import LLMConfigManager
from src.llm.llm_service import LLMService

# --- Fixtures ---

@pytest.fixture
def mock_config_manager():
    """Fixture for a mocked LLMConfigManager."""
    mock = MagicMock(spec=LLMConfigManager)
    # Store initial configs for potential reset/lookup
    initial_configs_data = {
        "config1": {"name": "config1", "api_url": "url1", "model": "model1", "api_key": "key1", "temperature": 0.7, "max_tokens": 2048, "system_prompt": "", "timeout": 60},
        "config2": {"name": "config2", "api_url": "url2", "model": "model2", "api_key": "key2", "temperature": 0.7, "max_tokens": 2048, "system_prompt": "", "timeout": 60},
    }
    # Use a mutable dict to simulate the underlying storage for get_config
    underlying_configs_data = initial_configs_data.copy()
    # Use a mutable list for names to simulate updates
    current_config_names = list(underlying_configs_data.keys())
    current_active_config = "config1"

    mock.get_all_configs.return_value = underlying_configs_data.copy()
    # Make get_config_names return the *current* list
    mock.get_config_names.side_effect = lambda: current_config_names.copy()
    # Make get_active_config_name return the *current* active name
    mock.get_active_config_name.side_effect = lambda: current_active_config

    # Simulate get_config returning a copy (dict) from the *current* underlying data
    mock.get_config.side_effect = lambda name: underlying_configs_data.get(name, None).copy() if underlying_configs_data.get(name) else None

    # Simulate add_or_update_config modifying the internal state for subsequent calls
    # Default side effect simulates success
    def add_update_side_effect_success(name, config_data):
        # Simulate adding/updating the underlying data store
        if name not in underlying_configs_data:
             underlying_configs_data[name] = {"name": name, "api_url": "", "model": "", "api_key": "", "temperature": 0.7, "max_tokens": 2048, "system_prompt": "", "timeout": 60}
        underlying_configs_data[name].update(config_data)
        if name not in current_config_names:
            current_config_names.append(name)
            current_config_names.sort() # Keep it sorted like the real manager might
        # Update the mock's return value for get_config
        mock.get_config.side_effect = lambda n: underlying_configs_data.get(n, None).copy() if underlying_configs_data.get(n) else None
        return True # Simulate success
    mock.add_or_update_config.side_effect = add_update_side_effect_success

    # Simulate delete_config modifying the internal state
    def delete_side_effect_success(name):
        nonlocal current_active_config
        if name in current_config_names:
            current_config_names.remove(name)
            if name in underlying_configs_data:
                del underlying_configs_data[name]
            if name == current_active_config:
                current_active_config = None # Clear active if deleted
            # Update the mock's return value for get_config
            mock.get_config.side_effect = lambda n: underlying_configs_data.get(n, None).copy() if underlying_configs_data.get(n) else None
            return True
        return False # Simulate failure if not found
    mock.delete_config.side_effect = delete_side_effect_success

    # Simulate set_active_config_name modifying the internal state
    def set_active_side_effect_success(name):
        nonlocal current_active_config
        if name is None or name in current_config_names:
            current_active_config = name
            return True
        return False # Fail if name doesn't exist
    mock.set_active_config_name.side_effect = set_active_side_effect_success

    # Add original data access for tests needing the real key (using the initial state)
    mock._initial_configs_data = initial_configs_data.copy() # Keep a non-mutable copy
    return mock

@pytest.fixture
def mock_llm_service():
    """Fixture for a mocked LLMService."""
    mock = MagicMock(spec=LLMService)
    mock.test_connection_with_config.return_value = (True, "连接成功!")
    return mock

@pytest.fixture
def view_model(mock_config_manager, mock_llm_service):
    """Fixture for the LLMSettingsViewModel instance using real Qt objects."""
    vm = LLMSettingsViewModel(mock_config_manager, mock_llm_service)
    return vm

# --- Test Cases ---

def test_initialization_loads_data(view_model, mock_config_manager):
    """Test that ViewModel initialization loads configs and sets initial state."""
    view_model.load_initial_data()
    mock_config_manager.get_config_names.assert_called_once()
    mock_config_manager.get_active_config_name.assert_called_once()
    assert view_model._config_names == ["config1", "config2"]
    assert view_model._active_config_name == "config1"
    assert view_model._current_config_data is None
    assert view_model._current_config_name is None
    assert not view_model._is_dirty


def test_initialization_emits_signals(qtbot, mock_config_manager, mock_llm_service):
    """Test signals emitted during/after initialization."""
    vm = LLMSettingsViewModel(mock_config_manager, mock_llm_service)
    with qtbot.waitSignal(vm.config_list_changed, raising=True) as config_list_blocker, \
         qtbot.waitSignal(vm.active_config_changed, raising=True) as active_config_blocker:
        vm.load_initial_data()
    assert config_list_blocker.args == [["config1", "config2"]]
    assert active_config_blocker.args == ["config1"]
    with qtbot.waitSignal(vm.save_enabled_changed, raising=True) as save_blocker, \
         qtbot.waitSignal(vm.activate_enabled_changed, raising=True) as activate_blocker, \
         qtbot.waitSignal(vm.test_enabled_changed, raising=True) as test_blocker, \
         qtbot.waitSignal(vm.config_cleared, raising=True):
         vm.clear_selection()
    assert save_blocker.args == [False]
    assert activate_blocker.args == [False]
    assert test_blocker.args == [False]


def test_select_config_loads_details_and_emits_signals(view_model, mock_config_manager, qtbot):
    """Test selecting a configuration loads its details and updates UI state."""
    config_name_to_select = "config2"
    expected_config = mock_config_manager._initial_configs_data[config_name_to_select]
    view_model.load_initial_data()
    with qtbot.waitSignal(view_model.current_config_loaded, raising=True) as config_loaded_blocker, \
         qtbot.waitSignal(view_model.save_enabled_changed, raising=True) as save_blocker, \
         qtbot.waitSignal(view_model.activate_enabled_changed, raising=True) as activate_blocker, \
         qtbot.waitSignal(view_model.test_enabled_changed, raising=True) as test_blocker:
        view_model.select_config(config_name_to_select)
    assert view_model._current_config_name == config_name_to_select
    assert view_model._current_config_data is not None
    assert view_model._current_config_data['name'] == expected_config['name']
    assert view_model._current_config_data['api_url'] == expected_config['api_url']
    assert view_model._current_config_data['model'] == expected_config['model']
    assert view_model._current_config_data['api_key'] == "******"
    assert not view_model._is_dirty
    mock_config_manager.get_config.assert_called_once_with(config_name_to_select)
    emitted_config = config_loaded_blocker.args[0]
    assert emitted_config['name'] == expected_config['name']
    assert emitted_config['api_url'] == expected_config['api_url']
    assert emitted_config['model'] == expected_config['model']
    assert emitted_config['api_key'] == "******"
    assert save_blocker.args == [False]
    assert activate_blocker.args == [True]
    assert test_blocker.args == [True]


def test_select_active_config_disables_activate_button(view_model, mock_config_manager, qtbot):
    """Test selecting the already active config disables the activate button."""
    active_config_name = mock_config_manager.get_active_config_name()
    view_model.load_initial_data()
    with qtbot.waitSignal(view_model.activate_enabled_changed, raising=True) as activate_blocker:
        view_model.select_config(active_config_name)
    assert activate_blocker.args == [False]
    assert view_model._current_config_name == active_config_name


def test_select_non_existent_config(view_model, mock_config_manager, qtbot):
    """Test selecting a non-existent config name clears the selection."""
    view_model.load_initial_data()
    view_model.select_config("config1")
    assert view_model._current_config_name == "config1"
    with qtbot.waitSignal(view_model.config_cleared, raising=True) as clear_blocker, \
         qtbot.waitSignal(view_model.save_enabled_changed, raising=True) as save_blocker, \
         qtbot.waitSignal(view_model.activate_enabled_changed, raising=True) as activate_blocker, \
         qtbot.waitSignal(view_model.test_enabled_changed, raising=True) as test_blocker:
        view_model.select_config("non_existent_config")
    assert view_model._current_config_name is None
    assert view_model._current_config_data is None
    assert not view_model._is_dirty
    assert mock_config_manager.get_config.call_count == 2
    mock_config_manager.get_config.assert_called_with("non_existent_config")
    assert clear_blocker.args == []
    assert save_blocker.args == [False]
    assert activate_blocker.args == [False]
    assert test_blocker.args == [False]


def test_clear_selection_resets_state_and_emits_signals(view_model, qtbot):
    """Test clearing the selection resets state and disables buttons."""
    view_model.load_initial_data()
    view_model.select_config("config1")
    assert view_model._current_config_data is not None
    with qtbot.waitSignal(view_model.config_cleared, raising=True) as clear_blocker, \
         qtbot.waitSignal(view_model.save_enabled_changed, raising=True) as save_blocker, \
         qtbot.waitSignal(view_model.activate_enabled_changed, raising=True) as activate_blocker, \
         qtbot.waitSignal(view_model.test_enabled_changed, raising=True) as test_blocker:
        view_model.clear_selection()
    assert view_model._current_config_name is None
    assert view_model._current_config_data is None
    assert not view_model._is_dirty
    assert clear_blocker.args == []
    assert save_blocker.args == [False]
    assert activate_blocker.args == [False]
    assert test_blocker.args == [False]


@pytest.mark.parametrize("field, value, expected_dirty, expected_save_enabled", [
    ("name", "new_name", True, True),
    ("api_url", "new_url", True, True),
    ("model", "new_model", True, True),
    ("api_key", "new_key", True, True),
    ("api_key", "******", False, False),
    ("invalid_field", "some_value", False, False),
])
def test_update_field_changes_state_and_enables_save(view_model, qtbot, field, value, expected_dirty, expected_save_enabled):
    """Test updating config fields marks ViewModel as dirty and enables save."""
    view_model.load_initial_data()
    view_model.select_config("config1")
    initial_config = view_model._current_config_data.copy()
    assert not view_model._is_dirty
    if expected_save_enabled:
        with qtbot.waitSignal(view_model.save_enabled_changed, raising=True) as save_blocker:
            view_model.update_current_config_field(field, value)
        assert save_blocker.args == [True]
    else:
        view_model.update_current_config_field(field, value)
    if field in initial_config and field != "api_key":
        assert view_model._current_config_data[field] == value
    elif field == "api_key" and value != "******":
        assert view_model._current_config_data[field] == value
    elif field == "api_key" and value == "******":
        assert view_model._current_config_data[field] == "******"
    elif field in initial_config:
         assert view_model._current_config_data[field] == initial_config[field]
    else:
        assert field not in view_model._current_config_data
    assert view_model._is_dirty == expected_dirty


def test_update_field_no_config_selected(view_model):
    """Test that updating fields does nothing if no config is selected."""
    view_model.load_initial_data()
    view_model.clear_selection()
    assert view_model._current_config_data is None
    view_model.update_current_config_field("name", "should_not_work")
    assert view_model._current_config_data is None
    assert not view_model._is_dirty


def test_save_config_calls_manager_and_emits_status(view_model, mock_config_manager, qtbot):
    """Test saving the current configuration."""
    view_model.load_initial_data()
    view_model.select_config("config1")
    original_name = view_model._current_config_name
    view_model.update_current_config_field("model", "updated_model")
    view_model.update_current_config_field("api_key", "new_secret_key")
    assert view_model._is_dirty
    updated_data_from_view = view_model._current_config_data.copy()
    updated_data_from_view['api_key'] = "new_secret_key" # View sends real key

    # Simulate get_config returning the *saved* state after save
    saved_config_state = updated_data_from_view.copy()
    def side_effect_get_config(name):
        if name == original_name:
            return saved_config_state.copy()
        return mock_config_manager._initial_configs_data.get(name, None).copy() if mock_config_manager._initial_configs_data.get(name) else None
    mock_config_manager.get_config.side_effect = side_effect_get_config

    with qtbot.waitSignal(view_model.save_status_received, raising=True) as status_blocker, \
         qtbot.waitSignal(view_model.save_enabled_changed, raising=True) as save_blocker, \
         qtbot.waitSignal(view_model.current_config_loaded, raising=True) as loaded_blocker:
        view_model.save_current_config(updated_data_from_view)

    mock_config_manager.add_or_update_config.assert_called_once()
    call_args, call_kwargs = mock_config_manager.add_or_update_config.call_args
    assert call_args[0] == original_name
    passed_config_data = call_args[1]
    assert passed_config_data.get('model') == "updated_model"
    assert passed_config_data.get('api_key') == "new_secret_key"

    assert not view_model._is_dirty
    assert view_model._current_config_data['api_key'] == "******" # Masked after reload

    assert status_blocker.args == [True, f"配置 '{original_name}' 已保存。"]
    assert save_blocker.args == [False]
    assert loaded_blocker.args[0]['api_key'] == "******"
    assert loaded_blocker.args[0]['model'] == "updated_model"


def test_save_config_api_key_unchanged(view_model, mock_config_manager, qtbot):
    """Test saving when the API key field was not modified (kept as '******')."""
    view_model.load_initial_data()
    config_name = "config1"
    original_key = mock_config_manager._initial_configs_data[config_name]['api_key']
    view_model.select_config(config_name)
    view_model.update_current_config_field("model", "updated_model_only")
    assert view_model._is_dirty
    updated_data_from_view = view_model._current_config_data.copy()
    assert updated_data_from_view['api_key'] == "******"

    with qtbot.waitSignal(view_model.save_status_received):
        view_model.save_current_config(updated_data_from_view)

    mock_config_manager.add_or_update_config.assert_called_once()
    call_args, call_kwargs = mock_config_manager.add_or_update_config.call_args
    assert call_args[0] == config_name
    passed_config_data = call_args[1]
    assert passed_config_data.get('api_key') == original_key
    assert passed_config_data.get('model') == "updated_model_only"


def test_save_config_failure(view_model, mock_config_manager, qtbot):
    """Test saving configuration when the manager reports failure."""
    view_model.load_initial_data()
    view_model.select_config("config1")
    original_name = view_model._current_config_name
    view_model.update_current_config_field("model", "updated_model")
    # Ensure add_or_update_config returns False for this test
    mock_config_manager.add_or_update_config.side_effect = lambda name, data: False

    with qtbot.waitSignal(view_model.save_status_received, raising=True) as status_blocker:
        updated_data_for_save = view_model._current_config_data.copy()
        # Pass the actual key if it was changed
        updated_data_for_save['api_key'] = view_model._original_current_config_data['api_key'] if updated_data_for_save.get('api_key') == '******' else updated_data_for_save.get('api_key')
        view_model.save_current_config(updated_data_for_save)

    mock_config_manager.add_or_update_config.assert_called_once()
    assert view_model._is_dirty # Should remain dirty on failure
    assert status_blocker.args == [False, f"保存配置 '{original_name}' 失败。"]


def test_save_config_no_config_selected(view_model, mock_config_manager):
    """Test that save does nothing if no config is selected."""
    view_model.load_initial_data()
    assert view_model._current_config_data is None
    view_model.save_current_config({})
    mock_config_manager.add_or_update_config.assert_not_called()
    assert not view_model._is_dirty


def test_add_new_config_calls_manager_and_updates_list(view_model, mock_config_manager, qtbot):
    """Test adding a new default configuration."""
    view_model.load_initial_data()
    initial_config_names = list(view_model._config_names)
    new_config_name = "New Config 3"
    new_config_dict = {"name": new_config_name, "api_url": "", "model": "", "api_key": "", "temperature": 0.7, "max_tokens": 2048, "system_prompt": "", "timeout": 60}
    updated_names = sorted(initial_config_names + [new_config_name])

    # Reset side effect for get_config_names to use the updated list after add
    mock_config_manager.get_config_names.side_effect = lambda: updated_names

    # Mock get_config to return the new empty dict when requested after add
    # Ensure the fixture's side effect is updated to reflect the added config
    original_get_config_side_effect = mock_config_manager.get_config.side_effect
    def side_effect_get_config_after_add(name):
        if name == new_config_name:
            # Simulate the manager now having this config in its internal store
            # (This should be handled by the add_update_side_effect in the fixture)
            return new_config_dict.copy()
        # Fallback to the original side effect logic for existing configs
        return mock_config_manager._initial_configs_data.get(name, None).copy() if mock_config_manager._initial_configs_data.get(name) else None
    mock_config_manager.get_config.side_effect = side_effect_get_config_after_add


    with qtbot.waitSignal(view_model.add_status_received, raising=True) as status_blocker, \
         qtbot.waitSignal(view_model.config_list_changed, raising=True) as list_blocker, \
         qtbot.waitSignal(view_model.current_config_loaded, raising=True) as loaded_blocker:
        view_model.add_new_config(new_config_name)

    mock_config_manager.add_or_update_config.assert_called_once()
    call_args, call_kwargs = mock_config_manager.add_or_update_config.call_args
    added_name = call_args[0]
    passed_config_data = call_args[1]
    assert added_name == new_config_name
    assert isinstance(passed_config_data, dict)
    assert passed_config_data == {}

    # Assert internal state *after* the operation completes
    assert view_model._config_names == updated_names
    assert view_model._current_config_name == new_config_name
    assert view_model._current_config_data['api_key'] == "******" # Key should be masked

    assert status_blocker.args[0] is True
    assert status_blocker.args[1] == f"已添加配置 '{new_config_name}'。请填写详细信息并保存。"
    assert list_blocker.args == [updated_names]
    assert loaded_blocker.args[0]['name'] == new_config_name
    assert loaded_blocker.args[0]['api_key'] == "******"


def test_add_new_config_failure(view_model, mock_config_manager, qtbot):
    """Test adding a new configuration when the manager reports failure."""
    view_model.load_initial_data()
    # Ensure add_or_update_config returns False for this test
    mock_config_manager.add_or_update_config.side_effect = lambda name, data: False
    initial_call_count = mock_config_manager.get_config_names.call_count
    with qtbot.waitSignal(view_model.add_status_received, raising=True) as status_blocker:
        view_model.add_new_config("Failing Add")
    mock_config_manager.add_or_update_config.assert_called_once()
    # get_config_names should NOT be called again on failure
    assert mock_config_manager.get_config_names.call_count == initial_call_count
    assert status_blocker.args == [False, "添加配置 'Failing Add' 失败。"]


def test_delete_selected_config_calls_manager_and_updates_list(view_model, mock_config_manager, qtbot):
    """Test deleting the currently selected configuration."""
    view_model.load_initial_data()
    config_to_delete = "config2"
    view_model.select_config(config_to_delete)
    assert view_model._current_config_name == config_to_delete

    initial_names = mock_config_manager.get_config_names().copy()
    updated_names = [name for name in initial_names if name != config_to_delete]
    # Reset side effect for get_config_names
    mock_config_manager.get_config_names.side_effect = lambda: updated_names
    # Reset side effect for get_active_config_name
    mock_config_manager.get_active_config_name.side_effect = lambda: "config1"

    with qtbot.waitSignal(view_model.delete_status_received, raising=True) as status_blocker, \
         qtbot.waitSignal(view_model.config_list_changed, raising=True) as list_blocker, \
         qtbot.waitSignal(view_model.config_cleared, raising=True):
        view_model.delete_selected_config(config_to_delete)

    mock_config_manager.delete_config.assert_called_once_with(config_to_delete)
    # Check internal state *after* operation
    assert view_model._config_names == updated_names
    assert view_model._current_config_data is None
    assert view_model._current_config_name is None
    assert status_blocker.args == [True, f"配置 '{config_to_delete}' 已删除。"]
    assert list_blocker.args == [updated_names]


def test_delete_selected_config_failure(view_model, mock_config_manager, qtbot):
    """Test deleting configuration when the manager reports failure."""
    view_model.load_initial_data()
    config_to_delete = "config2"
    view_model.select_config(config_to_delete)
    # Ensure delete_config returns False for this test
    mock_config_manager.delete_config.side_effect = lambda name: False
    initial_call_count = mock_config_manager.get_config_names.call_count
    with qtbot.waitSignal(view_model.delete_status_received, raising=True) as status_blocker:
        view_model.delete_selected_config(config_to_delete)
    mock_config_manager.delete_config.assert_called_once_with(config_to_delete)
    # get_config_names should NOT be called again on failure
    assert mock_config_manager.get_config_names.call_count == initial_call_count
    assert view_model._current_config_name == config_to_delete
    assert status_blocker.args == [False, f"删除配置 '{config_to_delete}' 失败。"]


def test_delete_config_no_config_selected(view_model, mock_config_manager):
    """Test that delete does nothing if no config is selected."""
    view_model.load_initial_data()
    assert view_model._current_config_data is None
    view_model.delete_selected_config("")
    mock_config_manager.delete_config.assert_not_called()


def test_activate_selected_config_calls_manager_and_emits_signals(view_model, mock_config_manager, qtbot):
    """Test activating the currently selected configuration."""
    view_model.load_initial_data()
    config_to_activate = "config2"
    assert view_model._active_config_name == "config1"
    view_model.select_config(config_to_activate)
    assert view_model._current_config_name == config_to_activate

    # Simulate manager updating active config name *after* set is called
    def set_active_side_effect(name):
        mock_config_manager.get_active_config_name.return_value = name
        return True
    mock_config_manager.set_active_config_name.side_effect = set_active_side_effect

    with qtbot.waitSignal(view_model.activate_status_received, raising=True) as status_blocker, \
         qtbot.waitSignal(view_model.active_config_changed, raising=True) as active_blocker, \
         qtbot.waitSignal(view_model.activate_enabled_changed, raising=True) as activate_enabled_blocker, \
         qtbot.waitSignal(view_model.config_list_changed, raising=True):
        view_model.activate_selected_config()

    mock_config_manager.set_active_config_name.assert_called_once_with(config_to_activate)
    assert view_model._active_config_name == config_to_activate
    assert status_blocker.args == [True, f"配置 '{config_to_activate}' 已设为活动配置。"]
    assert active_blocker.args == [config_to_activate]
    assert activate_enabled_blocker.args == [False]


def test_activate_selected_config_failure(view_model, mock_config_manager, qtbot):
    """Test activating configuration when the manager reports failure."""
    view_model.load_initial_data()
    config_to_activate = "config2"
    view_model.select_config(config_to_activate)
    # Ensure set_active_config_name returns False for this test
    mock_config_manager.set_active_config_name.side_effect = lambda name: False

    with qtbot.waitSignal(view_model.activate_status_received, raising=True) as status_blocker:
        view_model.activate_selected_config()

    mock_config_manager.set_active_config_name.assert_called_once_with(config_to_activate)
    assert view_model._active_config_name == "config1" # Should not change on failure
    assert status_blocker.args == [False, f"设置活动配置 '{config_to_activate}' 失败。"]


def test_activate_config_no_config_selected(view_model, mock_config_manager):
    """Test that activate does nothing if no config is selected."""
    view_model.load_initial_data()
    assert view_model._current_config_data is None
    view_model.activate_selected_config()
    mock_config_manager.set_active_config_name.assert_not_called()


def test_test_connection_calls_service_and_emits_result_success(view_model, mock_llm_service, qtbot):
    """Test testing connection for the current config (success)."""
    view_model.load_initial_data()
    view_model.select_config("config1")
    view_model.update_current_config_field("model", "updated_model")
    view_model.update_current_config_field("api_key", "new_secret_key")
    current_config_data = view_model._current_config_data.copy()
    mock_llm_service.test_connection_with_config.return_value = (True, "连接成功!")

    with qtbot.waitSignal(view_model.test_result_received, raising=True) as result_blocker:
        config_data_from_view = current_config_data.copy()
        config_data_from_view['api_key'] = "new_secret_key"
        view_model.test_current_config(config_data_from_view)

    mock_llm_service.test_connection_with_config.assert_called_once()
    call_args, _ = mock_llm_service.test_connection_with_config.call_args
    config_sent_to_service = call_args[0]
    assert isinstance(config_sent_to_service, dict)
    assert config_sent_to_service['name'] == current_config_data['name']
    assert config_sent_to_service['model'] == "updated_model"
    assert config_sent_to_service['api_key'] == "new_secret_key"
    assert result_blocker.args == [True, "连接成功!"]


def test_test_connection_api_key_unchanged(view_model, mock_llm_service, mock_config_manager, qtbot):
    """Test testing connection when API key is '******' (should use original key)."""
    view_model.load_initial_data()
    config_name = "config1"
    original_key = mock_config_manager._initial_configs_data[config_name]['api_key']
    view_model.select_config(config_name)
    assert view_model._current_config_data['api_key'] == "******"
    mock_llm_service.test_connection_with_config.return_value = (True, "OK")

    with qtbot.waitSignal(view_model.test_result_received):
        config_data_from_view = view_model._current_config_data.copy()
        view_model.test_current_config(config_data_from_view)

    mock_llm_service.test_connection_with_config.assert_called_once()
    call_args, _ = mock_llm_service.test_connection_with_config.call_args
    config_sent_to_service = call_args[0]
    assert isinstance(config_sent_to_service, dict)
    assert config_sent_to_service['api_key'] == original_key


def test_test_connection_calls_service_and_emits_result_failure(view_model, mock_config_manager, mock_llm_service, qtbot):
    """Test testing connection for the current config (failure)."""
    view_model.load_initial_data()
    view_model.select_config("config1")
    error_message = "连接失败：无效的 API Key"
    mock_llm_service.test_connection_with_config.return_value = (False, error_message)

    with qtbot.waitSignal(view_model.test_result_received, raising=True) as result_blocker:
        config_data_from_view = view_model._current_config_data.copy()
        # Retrieve original key directly from the mock fixture's stored data
        config_data_from_view['api_key'] = mock_config_manager._initial_configs_data['config1']['api_key']
        view_model.test_current_config(config_data_from_view)

    mock_llm_service.test_connection_with_config.assert_called_once()
    assert result_blocker.args == [False, error_message]


def test_test_connection_no_config_selected(view_model, mock_llm_service):
    """Test that test connection does nothing if no config is selected."""
    view_model.load_initial_data()
    assert view_model._current_config_data is None
    view_model.test_current_config({})
    mock_llm_service.test_connection_with_config.assert_not_called()