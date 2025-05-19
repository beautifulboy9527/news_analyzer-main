import pytest
from unittest.mock import Mock, patch, call
from PySide6.QtCore import QSettings

from src.services.scheduler_service import SchedulerService
from apscheduler.triggers.interval import IntervalTrigger

# Constants for settings keys from SchedulerService (consider importing if they become public)
SETTINGS_KEY_ENABLED = "scheduler/enabled"
SETTINGS_KEY_INTERVAL = "scheduler/interval_minutes"
DEFAULT_REFRESH_INTERVAL_MINUTES = 60 # Default from SchedulerService

@pytest.fixture
def mock_qsettings(tmp_path):
    """Fixture to create a mock QSettings object backed by a temporary file."""
    # Using a real QSettings with a temporary file can be more robust for testing QSettings interaction
    # However, for strict mocking of return_value, a simple Mock might suffice.
    # Here, we'll mock the QSettings methods used by the service.
    settings = Mock(spec=QSettings)
    settings.value.side_effect = lambda key, default, type: {
        SETTINGS_KEY_ENABLED: False, # Default to disabled for most tests
        SETTINGS_KEY_INTERVAL: DEFAULT_REFRESH_INTERVAL_MINUTES
    }.get(key, default)
    settings.setValue = Mock()
    settings.sync = Mock()
    return settings

@pytest.fixture
def mock_app_service():
    """Fixture for a mock AppService."""
    service = Mock()
    service.refresh_all_sources = Mock()
    return service

@pytest.fixture
@patch('src.services.scheduler_service.BackgroundScheduler')
def scheduler_service(mock_bg_scheduler_class, mock_qsettings, mock_app_service):
    """Fixture for SchedulerService with mocked BackgroundScheduler."""
    # Mock the BackgroundScheduler instance
    mock_scheduler_instance = mock_bg_scheduler_class.return_value
    mock_scheduler_instance.add_job = Mock()
    mock_scheduler_instance.remove_job = Mock()
    mock_scheduler_instance.get_job = Mock()
    mock_scheduler_instance.start = Mock()
    mock_scheduler_instance.shutdown = Mock()
    mock_scheduler_instance.running = False # Default to not running

    service = SchedulerService(settings=mock_qsettings)
    service.set_app_service(mock_app_service)
    # Attach the instance mock for assertions if needed directly on the scheduler
    service._scheduler_mock = mock_scheduler_instance 
    return service

def test_scheduler_service_initialization(scheduler_service, mock_qsettings):
    assert scheduler_service.settings == mock_qsettings
    assert scheduler_service._app_service is not None
    assert scheduler_service._scheduler_mock is not None # Check if internal mock is set up

def test_start_scheduler_disabled_by_default(scheduler_service, mock_qsettings):
    """Test that scheduler doesn't start if disabled in settings."""
    # Default mock_qsettings has enabled = False
    scheduler_service.start()
    scheduler_service._scheduler_mock.add_job.assert_not_called()
    scheduler_service._scheduler_mock.start.assert_not_called()

def test_start_scheduler_enabled_in_settings(scheduler_service, mock_qsettings, mock_app_service):
    """Test scheduler starts and adds job if enabled in settings."""
    test_interval = 30
    mock_qsettings.value.side_effect = lambda key, default, type: {
        SETTINGS_KEY_ENABLED: True,
        SETTINGS_KEY_INTERVAL: test_interval
    }.get(key, default)

    scheduler_service.start()

    assert scheduler_service._scheduler_mock.add_job.call_count == 1
    args, kwargs = scheduler_service._scheduler_mock.add_job.call_args
    assert args[0] == scheduler_service._run_refresh_job
    assert isinstance(kwargs['trigger'], IntervalTrigger)
    assert kwargs['trigger'].interval.total_seconds() == test_interval * 60
    assert kwargs['id'] == scheduler_service._refresh_job_id
    assert kwargs['replace_existing'] is True
    scheduler_service._scheduler_mock.start.assert_called_once()

def test_start_scheduler_no_app_service(mock_qsettings):
    """Test scheduler doesn't start if AppService is not set."""
    # Re-patch BackgroundScheduler for this specific test setup
    with patch('src.services.scheduler_service.BackgroundScheduler') as mock_bg_scheduler_class_local:
        mock_scheduler_instance_local = mock_bg_scheduler_class_local.return_value
        
        service_no_app = SchedulerService(settings=mock_qsettings)
        # DO NOT call set_app_service
        service_no_app.start()
        
        mock_scheduler_instance_local.add_job.assert_not_called()
        mock_scheduler_instance_local.start.assert_not_called()


def test_run_refresh_job_calls_app_service(scheduler_service, mock_app_service):
    """Test that _run_refresh_job calls app_service.refresh_all_sources."""
    scheduler_service._run_refresh_job()
    mock_app_service.refresh_all_sources.assert_called_once()

def test_run_refresh_job_no_app_service(mock_qsettings, mock_app_service):
    """Test _run_refresh_job does nothing if app_service is missing (e.g., cleared)."""
    service = SchedulerService(settings=mock_qsettings)
    # AppService is set, then cleared
    service.set_app_service(mock_app_service)
    service._app_service = None 
    
    service._run_refresh_job()
    mock_app_service.refresh_all_sources.assert_not_called()


def test_update_schedule_enable_and_set_interval(scheduler_service, mock_qsettings):
    """Test updating schedule to enable it with a new interval."""
    new_interval = 15
    scheduler_service._scheduler_mock.running = False # Assume not running initially

    scheduler_service.update_schedule(enabled=True, interval_minutes=new_interval)

    mock_qsettings.setValue.assert_any_call(SETTINGS_KEY_ENABLED, True)
    mock_qsettings.setValue.assert_any_call(SETTINGS_KEY_INTERVAL, new_interval)
    mock_qsettings.sync.assert_called_once()

    # Check add_job call
    assert scheduler_service._scheduler_mock.add_job.call_count == 1
    args, kwargs = scheduler_service._scheduler_mock.add_job.call_args
    assert args[0] == scheduler_service._run_refresh_job
    assert isinstance(kwargs['trigger'], IntervalTrigger)
    assert kwargs['trigger'].interval.total_seconds() == new_interval * 60
    
    # Check scheduler starts if it wasn't running
    scheduler_service._scheduler_mock.start.assert_called_once()

def test_update_schedule_disable_running_scheduler(scheduler_service, mock_qsettings):
    """Test updating schedule to disable a currently running scheduler."""
    scheduler_service._scheduler_mock.running = True
    scheduler_service._scheduler_mock.get_job.return_value = Mock() # Simulate job exists

    scheduler_service.update_schedule(enabled=False, interval_minutes=10) # Interval doesn't matter

    mock_qsettings.setValue.assert_any_call(SETTINGS_KEY_ENABLED, False)
    scheduler_service._scheduler_mock.remove_job.assert_called_once_with(scheduler_service._refresh_job_id)
    scheduler_service._scheduler_mock.shutdown.assert_called_once_with(wait=False)
    # add_job should not be called again
    scheduler_service._scheduler_mock.add_job.assert_not_called()


def test_update_schedule_change_interval_when_enabled_and_running(scheduler_service, mock_qsettings):
    """Test changing interval for an already enabled and running scheduler."""
    new_interval = 45
    scheduler_service._scheduler_mock.running = True
    scheduler_service._scheduler_mock.get_job.return_value = Mock() # Simulate job exists

    scheduler_service.update_schedule(enabled=True, interval_minutes=new_interval)

    mock_qsettings.setValue.assert_any_call(SETTINGS_KEY_ENABLED, True)
    mock_qsettings.setValue.assert_any_call(SETTINGS_KEY_INTERVAL, new_interval)
    
    scheduler_service._scheduler_mock.remove_job.assert_called_once_with(scheduler_service._refresh_job_id)
    
    assert scheduler_service._scheduler_mock.add_job.call_count == 1
    args, kwargs = scheduler_service._scheduler_mock.add_job.call_args
    assert isinstance(kwargs['trigger'], IntervalTrigger)
    assert kwargs['trigger'].interval.total_seconds() == new_interval * 60
    
    # Start should not be called again if already running
    scheduler_service._scheduler_mock.start.assert_not_called() 

def test_update_schedule_invalid_interval_uses_default(scheduler_service, mock_qsettings):
    """Test that an invalid interval (e.g., 0 or negative) uses the default."""
    scheduler_service.update_schedule(enabled=True, interval_minutes=0)
    
    args, kwargs = scheduler_service._scheduler_mock.add_job.call_args
    assert isinstance(kwargs['trigger'], IntervalTrigger)
    assert kwargs['trigger'].interval.total_seconds() == DEFAULT_REFRESH_INTERVAL_MINUTES * 60

    scheduler_service._scheduler_mock.reset_mock() # Reset for next part of test
    scheduler_service.update_schedule(enabled=True, interval_minutes=-10)
    args, kwargs = scheduler_service._scheduler_mock.add_job.call_args
    assert isinstance(kwargs['trigger'], IntervalTrigger)
    assert kwargs['trigger'].interval.total_seconds() == DEFAULT_REFRESH_INTERVAL_MINUTES * 60


def test_stop_scheduler(scheduler_service):
    """Test stopping the scheduler."""
    scheduler_service._scheduler_mock.running = True
    scheduler_service.stop()
    scheduler_service._scheduler_mock.shutdown.assert_called_once_with(wait=False)

def test_stop_scheduler_already_stopped(scheduler_service):
    """Test stopping a scheduler that is already stopped."""
    scheduler_service._scheduler_mock.running = False
    scheduler_service.stop()
    scheduler_service._scheduler_mock.shutdown.assert_not_called()

def test_get_schedule_config(scheduler_service, mock_qsettings):
    """Test retrieving schedule configuration."""
    expected_enabled = True
    expected_interval = 25
    mock_qsettings.value.side_effect = lambda key, default, type: {
        SETTINGS_KEY_ENABLED: expected_enabled,
        SETTINGS_KEY_INTERVAL: expected_interval
    }.get(key, default)

    enabled, interval = scheduler_service.get_schedule_config()
    assert enabled == expected_enabled
    assert interval == expected_interval

    # Verify QSettings.value was called correctly for both keys
    mock_qsettings.value.assert_any_call(SETTINGS_KEY_ENABLED, False, type=bool)
    mock_qsettings.value.assert_any_call(SETTINGS_KEY_INTERVAL, DEFAULT_REFRESH_INTERVAL_MINUTES, type=int) 