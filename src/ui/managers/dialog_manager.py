# src/ui/managers/dialog_manager.py
import logging
from PyQt5.QtWidgets import QMessageBox, QDialog
from typing import TYPE_CHECKING, Optional # Import Optional

# Import dialog classes (adjust paths as necessary)
# Need to ensure these dialogs exist and are importable
try:
    from src.ui.source_management_panel import SourceManagementPanel # Assuming it's a QDialog or similar
except ImportError:
    SourceManagementPanel = None
    logging.getLogger(__name__).warning("SourceManagementPanel not found, source management dialog disabled.")

try:
    from src.ui.llm_settings import LLMSettingsDialog
except ImportError:
    LLMSettingsDialog = None
    logging.getLogger(__name__).warning("LLMSettingsDialog not found, LLM settings dialog disabled.")

# --- Corrected Import Block for History ---
try:
    # from src.ui.history_panel import HistoryPanel # 旧的，错误的面板
    from src.ui.browsing_history_panel import BrowsingHistoryPanel # 新的，正确的面板
except ImportError:
    BrowsingHistoryPanel = None # Corrected variable name
    logging.getLogger(__name__).warning("BrowsingHistoryPanel not found, history dialog disabled.")
# --- End Corrected Import Block ---

try:
    from src.ui.news_detail_dialog import NewsDetailDialog
except ImportError:
    NewsDetailDialog = None
    logging.getLogger(__name__).warning("NewsDetailDialog not found, news detail dialog disabled.")

# --- Import Settings Dialog ---
try:
    from src.ui.settings_dialog import SettingsDialog # Import the new settings dialog
except ImportError:
    SettingsDialog = None
    logging.getLogger(__name__).warning("SettingsDialog not found, settings dialog disabled.")
# --- End Import ---


# Import other necessary dialogs if they exist
# from src.ui.import_export_dialog import ImportExportDialog # Already imported in MainWindow temp wrapper

# Forward declare AppService for type hinting to avoid circular import
if TYPE_CHECKING:
    from src.core.app_service import AppService
    from src.ui.main_window import MainWindow # Assuming MainWindow is the parent type

class DialogManager:
    """
    Manages the creation and display of various dialogs in the application.
    """
    def __init__(self, parent_window: 'MainWindow', app_service: 'AppService'):
        """
        Initializes the DialogManager.

        Args:
            parent_window: The main window instance, used as parent for dialogs.
            app_service: The application service instance for data access.
        """
        self.window = parent_window
        self.app_service = app_service
        self.logger = logging.getLogger(__name__)
        # Store dialog instances if they should persist or be reused
        self.source_manager_dialog: Optional[SourceManagementPanel] = None
        self.history_dialog: Optional[BrowsingHistoryPanel] = None
        self.llm_settings_dialog: Optional[LLMSettingsDialog] = None
        self.settings_dialog: Optional[SettingsDialog] = None # Add instance variable for settings

    def open_source_manager(self):
        """Opens the news source management dialog (non-modal)."""
        self.logger.debug("Attempting to open Source Manager dialog...")
        if not SourceManagementPanel:
             self.show_error_message("新闻源管理对话框组件未找到或加载失败。")
             return
        try:
            # Check if dialog exists and is visible
            if self.source_manager_dialog and self.source_manager_dialog.isVisible():
                self.logger.debug("Source Manager dialog already visible, bringing to front.")
                self.source_manager_dialog.raise_()
                self.source_manager_dialog.activateWindow()
                return

            # Create a new instance if it doesn't exist or was closed
            self.logger.debug("Creating new SourceManagementPanel instance.")
            self.source_manager_dialog = SourceManagementPanel(self.app_service, self.window)
            # Refresh content if needed (assuming the dialog has a refresh method)
            if hasattr(self.source_manager_dialog, 'refresh_source_list'): # Example refresh method name
                 self.logger.debug("Refreshing source list in SourceManagementPanel.")
                 self.source_manager_dialog.refresh_source_list()
            self.source_manager_dialog.show() # Show non-modally
            # sources_updated signal from AppService will handle UI updates if dialog is open

        except Exception as e:
            self.logger.error(f"Error opening Source Manager: {e}", exc_info=True)
            self.show_error_message(f"无法打开新闻源管理：{e}")
            self.source_manager_dialog = None # Reset on error

    def open_settings_dialog(self):
        """Opens the application settings dialog (non-modal).""" # Updated docstring
        self.logger.debug("Attempting to open Settings dialog...")
        if not SettingsDialog:
             self.show_error_message("设置对话框组件未找到或加载失败。")
             return
        try:
            # Check if dialog exists and is visible
            if self.settings_dialog and self.settings_dialog.isVisible():
                self.logger.debug("Settings dialog already visible, bringing to front.")
                self.settings_dialog.raise_()
                self.settings_dialog.activateWindow()
                return

            # Create a new instance if it doesn't exist or was closed
            self.logger.debug("Creating new SettingsDialog instance.")
            # Pass necessary managers from the main window
            self.settings_dialog = SettingsDialog(
                self.window.theme_manager,
                self.window.ui_settings_manager,
                self.window # Parent
            )
            # Connect the signal if needed (e.g., for live font updates)
            # self.settings_dialog.settings_applied.connect(self.window.handle_settings_applied)
            self.settings_dialog.show() # Show non-modally

        except Exception as e:
            self.logger.error(f"Error opening Settings Dialog: {e}", exc_info=True)
            self.show_error_message(f"无法打开设置：{e}")
            self.settings_dialog = None # Reset on error


    def open_llm_settings(self):
        """Opens the LLM settings dialog (non-modal)."""
        self.logger.debug("Attempting to open LLM Settings dialog...")
        if not LLMSettingsDialog:
             self.show_error_message("LLM 设置对话框组件未找到或加载失败。")
             return
        try:
            # Check if dialog exists and is visible
            if self.llm_settings_dialog and self.llm_settings_dialog.isVisible():
                self.logger.debug("LLM Settings dialog already visible, bringing to front.")
                self.llm_settings_dialog.raise_()
                self.llm_settings_dialog.activateWindow()
                return

            # Create a new instance if it doesn't exist or was closed
            self.logger.debug("Creating new LLMSettingsDialog instance.")
            # 传递 llm_service 和 parent
            self.llm_settings_dialog = LLMSettingsDialog(self.app_service.llm_service, self.window)
            self.llm_settings_dialog.show() # Show non-modally
        except Exception as e:
            self.logger.error(f"Error opening LLM Settings: {e}", exc_info=True)
            self.show_error_message(f"无法打开LLM设置：{e}")
            self.llm_settings_dialog = None # Reset on error

    def open_history(self):
        """Opens the browsing history dialog (non-modal)."""
        self.logger.debug("Attempting to open Browsing History dialog...")
        if not BrowsingHistoryPanel:
             self.show_error_message("浏览历史对话框组件未找到或加载失败。")
             return

        try:
            # Check if dialog exists and is visible
            if self.history_dialog and self.history_dialog.isVisible():
                self.logger.debug("History dialog already visible, bringing to front.")
                self.history_dialog.raise_()
                self.history_dialog.activateWindow()
                return

            # Create a new instance if it doesn't exist or was closed
            self.logger.debug("Creating new BrowsingHistoryPanel instance.")
            self.history_dialog = BrowsingHistoryPanel(self.app_service.storage, self.window) # Pass parent
            # The dialog's __init__ now handles the initial refresh
            self.history_dialog.show() # Show as non-modal dialog

        except Exception as e:
            self.logger.error(f"Error opening Browsing History Dialog: {e}", exc_info=True)
            self.show_error_message(f"无法打开浏览历史记录：{e}")
            self.history_dialog = None # Reset instance if creation failed


    def open_news_detail(self, news_article: 'NewsArticle'):
        """Opens the news detail dialog for a specific news item (non-modal, new instance)."""
        self.logger.debug(f"Attempting to open News Detail for: {news_article.title}")
        if not NewsDetailDialog:
             self.show_error_message("新闻详情对话框组件未找到或加载失败。")
             return
        try:
            # Always create a new instance for detail view
            dialog = NewsDetailDialog(news_article, self.window) # Pass article and parent
            dialog.show() # Show non-modally
        except Exception as e:
            self.logger.error(f"Error opening News Detail: {e}", exc_info=True)
            self.show_error_message(f"打开新闻详情时出错: {e}")

    def about(self):
        """Shows the About application dialog."""
        self.logger.debug("Showing About Box...")
        # Use the content from the original MainWindow.show_about
        QMessageBox.about(self.window, "关于 讯析", # Updated title
                          f"""<b>讯析 v1.0.0</b>
                          <p>一个基于 PyQt5 的桌面应用程序，用于聚合、阅读和分析来自不同来源的新闻。</p>
                          <p><b>核心功能:</b></p>
                          <ul>
                              <li>聚合 RSS 和其他新闻源</li>
                              <li>按分类、日期和关键词筛选新闻</li>
                              <li>使用 LLM (大型语言模型) 进行新闻摘要和分析</li>
                              <li>聊天助手功能</li>
                              <li>主题和字体大小切换</li>
                          </ul>
                          <p>开发者: 一辉 (GitHub: beautifulboy9527)</p>
                          <p>版本: 1.0.0 (开发中)</p>""") # Updated developer info

    def show_error_message(self, message: str, title: str = "错误"):
        """Displays an error message box."""
        self.logger.error(f"Showing Error Dialog: [{title}] {message}")
        QMessageBox.critical(self.window, title, message)

    def show_info_message(self, message: str, title: str = "信息"):
        """Displays an informational message box."""
        self.logger.info(f"Showing Info Dialog: [{title}] {message}")
        QMessageBox.information(self.window, title, message)

    def ask_question(self, message: str, title: str = "确认") -> bool:
        """Asks a question with Yes/No buttons."""
        self.logger.debug(f"Asking Question: [{title}] {message}")
        return QMessageBox.question(self.window, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    # --- Methods for dialogs called from MenuManager but logic still in MainWindow ---
    # These can be moved here fully later if needed

    def open_import_export(self):
        """Placeholder to call MainWindow's temporary implementation."""
        # This method exists so MenuManager can connect to DialogManager.
        # The actual logic is temporarily kept in MainWindow._show_import_export_dialog
        # until ImportExportDialog is potentially refactored further.
        self.window._show_import_export_dialog() # Call the method on the parent window instance