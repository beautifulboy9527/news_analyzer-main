import pytest
from unittest.mock import patch, MagicMock, ANY

# Use PySide6 imports
from PySide6.QtWidgets import QApplication, QDialog, QTextBrowser, QLabel, QTextEdit, QCheckBox, QPushButton
from PySide6.QtCore import Qt, Signal as pyqtSignal, Signal, QObject

# Import the class to be tested
from src.ui.news_detail_dialog import NewsDetailDialog
# ViewModel is no longer defined here
# from src.ui.news_detail_dialog import NewsDetailViewModel # Incorrect
from src.models import NewsArticle # Needed for test data
from datetime import datetime

# --- Fixtures ---

@pytest.fixture(scope="module")
def qt_app():
    """Create a single QApplication instance for the module."""
    app = QApplication.instance() or QApplication([])
    yield app

# Remove mock_view_model fixture as it's no longer used by the dialog directly
# @pytest.fixture
# def mock_view_model(mocker):
#     ...

@pytest.fixture
def news_article_data():
    """Fixture for sample NewsArticle data."""
    return NewsArticle(
        id="test1", # Keep id as string for consistency if models.py uses Optional[int] but tests use string
        title="Test Article Title",
        link="http://example.com/test",
        source_name="Test Source",
        # Pass datetime object directly as per NewsArticle definition
        publish_time=datetime(2023, 1, 1, 12, 0, 0), 
        content="<p>This is the <b>HTML</b> content.</p>",
        summary="Test summary."
    )

# Patch decorator removed, mock_vm_cls and mock_view_model arguments removed
@pytest.fixture
def dialog(qtbot, news_article_data): # Removed mock_vm_cls and mock_view_model
    """Provides an instance of NewsDetailDialog with news_article_data."""
    # Directly instantiate with news_article_data
    dialog_instance = NewsDetailDialog(news_article=news_article_data, parent=None)
    qtbot.addWidget(dialog_instance)
    return dialog_instance

# --- Test Cases ---

def test_dialog_initialization_and_load(dialog, qtbot, news_article_data): # Changed mock_view_model to news_article_data
    """Test dialog initialization and that content_browser displays article data."""
    # print(f"DEBUG: Fixture news_article_data.summary: '{news_article_data.summary}'") # Removed debug print
    # print(f"DEBUG: Dialog's self.news_article.summary: '{dialog.news_article.summary}'") # Removed debug print
    
    assert isinstance(dialog, QDialog)
    
    content_browser = dialog.findChild(QTextBrowser, "NewsDetailContentBrowser")
    assert content_browser is not None, "QTextBrowser 'NewsDetailContentBrowser' not found"
    
    # Wait for events to process, especially setHtml
    QApplication.processEvents()
    qtbot.wait(50)

    html_content = content_browser.toHtml()

    # Check for key pieces of information from news_article_data in the HTML
    assert news_article_data.title in html_content
    assert news_article_data.source_name in html_content
    assert news_article_data.summary in html_content # Summary should be present
    assert news_article_data.content not in html_content # Content should NOT be present if summary is shown
    assert news_article_data.link in html_content
    
    # Example for formatted date - this might need adjustment based on actual strftime in dialog
    formatted_date = news_article_data.publish_time.strftime('%Y-%m-%d %H:%M:%S')
    assert formatted_date in html_content

# Remove test_read_checkbox_toggle_calls_viewmodel as the checkbox doesn't exist
# def test_read_checkbox_toggle_calls_viewmodel(dialog, qtbot, mock_view_model):
#     ...

# Remove test_analyze_button_calls_viewmodel as the button doesn't exist
# def test_analyze_button_calls_viewmodel(dialog, qtbot, mock_view_model):
#     ...

# Remove test_analysis_updated_signal_updates_ui as analysis edit and VM interaction don't exist
# def test_analysis_updated_signal_updates_ui(dialog, qtbot, mock_view_model):
#     ...

# Remove test_close_requested_signal_closes_dialog as VM interaction doesn't exist
# Dialog uses a standard close button. Its functionality is implicitly tested by qtbot.addWidget cleanup.
# def test_close_requested_signal_closes_dialog(dialog, qtbot, mock_view_model):
#     ...

# Remove test_status_updated_signal_updates_status_bar as status_label and VM interaction don't exist
# def test_status_updated_signal_updates_status_bar(dialog, qtbot, mock_view_model):
#     ...

# TODO: Add new tests for existing functionality:
# - Font increase/decrease buttons
# - Copy button
# - Link opening (might be harder to test without heavier mocking)

# Example of a test for an existing button (e.g., copy button)
# This is a placeholder and needs actual implementation of _copy_content to be testable,
# or mocking clipboard.
@patch('PySide6.QtGui.QGuiApplication.clipboard') # QGuiApplication for clipboard
def test_copy_button_copies_to_clipboard(mock_clipboard_method, dialog, qtbot, news_article_data):
    copy_button = dialog.findChild(QPushButton, "copy_button") # Assuming it's named "copy_button"
    if not copy_button: # The button has no object name in current code
        copy_buttons = dialog.findChildren(QPushButton)
        # Try to find by text if no objectName (less robust)
        for btn in copy_buttons:
            if btn.text() == "复制":
                copy_button = btn
                break
    assert copy_button is not None, "Copy button not found"

    # Get the mock clipboard object returned by the patched method
    mock_clipboard_instance = mock_clipboard_method.return_value
    
    qtbot.mouseClick(copy_button, Qt.LeftButton)
    
    # Assert that clipboard.setText was called with the plain text content
    expected_text = dialog.content_browser.toPlainText() # Get expected text AFTER dialog init
    mock_clipboard_instance.setText.assert_called_once_with(expected_text)

# --- Keep other test structure if needed, or remove all old tests and write new ones based on UI ---