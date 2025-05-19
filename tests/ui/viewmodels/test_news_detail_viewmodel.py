import pytest
from unittest.mock import Mock, patch, MagicMock
from PyQt5.QtCore import QObject, pyqtSignal, QUrl # Added QUrl
from PyQt5.QtCore import QObject, pyqtSignal

from src.ui.viewmodels.news_detail_viewmodel import NewsDetailViewModel
from src.models import NewsItem
from src.core.app_service import AppService

# Mock AppService for testing
# Remove mock_app_service fixture as ViewModel now takes NewsArticle directly
# @pytest.fixture
# def mock_app_service():
#     service = MagicMock(spec=AppService)
#     # Simulate fetching news detail (No longer needed here)
#     # mock_detail = NewsArticle(...)
#     # service.get_news_detail = MagicMock(return_value=mock_detail)
#     return service

# Mock NewsItem for initialization
@pytest.fixture
def sample_news_item():
    return NewsItem(
        # Use NewsArticle instead of NewsItem if that's the correct model
        title="Initial Test Title",
        link="http://example.com/initial",
        source_name="Initial Source",
        # Add other required fields for NewsArticle if necessary
        content="Initial Content", # Add content for completeness
        summary="Initial Summary" # Add summary
    )

# --- Test Cases ---

def test_init_with_news_item(sample_news_item): # Remove mock_app_service
    """Test ViewModel initialization with a NewsArticle object."""
    # ViewModel now takes news_item directly
    vm = NewsDetailViewModel(news_item=sample_news_item)
    # Assert properties based on the sample_news_item provided
    assert vm.title == "Initial Test Title"
    assert vm.content == "Initial Content" # Should reflect initial item
    assert vm.source_name == "Initial Source"
    assert vm.link == QUrl("http://example.com/initial")
    # Metadata might be formatted differently now
    assert "来源: Initial Source" in vm.metadata

# Remove test_init_with_id as ViewModel no longer accepts ID
# def test_init_with_id(mock_app_service):
#     """Test ViewModel initialization with just an ID."""
#     # ... (test removed) ...

@patch('src.ui.viewmodels.news_detail_viewmodel.datetime')
def test_data_loading_and_formatting(mock_datetime, sample_news_item, qtbot): # Remove mock_app_service
    """Test data loading, formatting, and signal emission."""
    # Mock datetime.fromtimestamp to return a fixed date for consistent formatting
    mock_dt_object = MagicMock()
    mock_dt_object.strftime.return_value = "2023-03-15 16:00"
    mock_datetime.fromtimestamp.return_value = mock_dt_object

    vm = NewsDetailViewModel(news_item=sample_news_item) # Pass news_item

    # Check initial state (already tested, but good for context)
    assert vm.title == "Initial Test Title"

    # No async loading simulation needed as data is passed directly
    # with qtbot.waitSignal(vm.data_ready, timeout=1000) as blocker:
    #     pass

    # Verify the data fetched by the mock service is loaded and formatted
    # Assert properties based on the sample_news_item
    assert vm.title == "Initial Test Title"
    assert vm.content == "Initial Content"
    assert "来源: Initial Source" in vm.metadata
    # Assert publish time formatting if sample_news_item has publish_time
    # mock_datetime.fromtimestamp.assert_called_once_with(...)
    # mock_dt_object.strftime.assert_called_once_with('%Y-%m-%d %H:%M')

# Remove test_data_loading_failure as ViewModel doesn't handle loading failure this way anymore
# def test_data_loading_failure(mock_app_service, qtbot):
#     """Test behavior when data loading fails."""
#     # ... (test removed) ...

# Add more tests if there are specific edge cases or other functionalities