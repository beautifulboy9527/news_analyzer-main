# src/ui/managers/dialog_manager.py
from PySide6.QtCore import Slot as pyqtSlot # Ensure Slot is imported

import logging
from PySide6.QtWidgets import QMessageBox, QDialog # Use PySide6
from typing import TYPE_CHECKING, Optional # Import Optional
from PySide6.QtCore import Slot as pyqtSlot # Import Slot for decorator
from PySide6.QtCore import Qt # Make sure Qt is imported for WA_DeleteOnClose
import os # ADDED for os.path.join in open_import_export_dialog
from functools import partial

# --- ADDED: Import NewsArticle directly for runtime --- 
from src.models import NewsArticle
from src.ui.viewmodels.llm_settings_viewmodel import LLMSettingsViewModel # ADDED IMPORT

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
# try:
#     # from src.ui.history_panel import HistoryPanel # 旧的，错误的面板
#     from src.ui.browsing_history_panel import BrowsingHistoryPanel # 新的，正确的面板
# except ImportError:
#     BrowsingHistoryPanel = None # Corrected variable name
#     logging.getLogger(__name__).warning("BrowsingHistoryPanel not found, history dialog disabled.")
# --- End Corrected Import Block ---

# +++ NEW History Panel Imports (MODIFIED TO USE BROWSING VERSIONS) +++
try:
    # from src.ui.views.history_panel import HistoryPanel # OLD, to be replaced
    # from src.ui.viewmodels.history_viewmodel import HistoryViewModel # OLD, to be replaced
    from src.ui.browsing_history_panel import BrowsingHistoryPanel # USE THIS
    from src.ui.viewmodels.browsing_history_viewmodel import BrowsingHistoryViewModel # USE THIS
except ImportError as e:
    BrowsingHistoryPanel = None # Ensure correct variable name if import fails
    BrowsingHistoryViewModel = None # Ensure correct variable name if import fails
    logging.getLogger(__name__).error(f"BrowsingHistoryPanel or BrowsingHistoryViewModel import failed: {e}", exc_info=True)
    logging.getLogger(__name__).warning("Browsing history panel functionality will be disabled.")
# +++ END NEW History Panel Imports +++

# --- Import News Similarity Panel ---
try:
    from src.ui.news_similarity_panel import NewsSimilarityPanel
except ImportError:
    NewsSimilarityPanel = None
    logging.getLogger(__name__).warning("NewsSimilarityPanel not found, news similarity analysis dialog disabled.")
# --- End Import ---

try:
    from src.ui.news_detail_dialog import NewsDetailDialog
except ImportError:
    NewsDetailDialog = None
    logging.getLogger(__name__).warning("NewsDetailDialog not found, news detail dialog disabled.")

try:
    from src.ui.managers.integrated_panel_manager import IntegratedPanelManager
except ImportError as e:
    IntegratedPanelManager = None
    logging.getLogger(__name__).error(f"IntegratedPanelManager导入失败: {e}")
    logging.getLogger(__name__).warning("整合分析面板功能已禁用。")

# --- Import Settings Dialog ---
try:
    from src.ui.views.settings_dialog import SettingsDialog # Import the new settings dialog
except ImportError:
    SettingsDialog = None
    logging.getLogger(__name__).warning("SettingsDialog not found, settings dialog disabled.")
# --- End Import ---

# --- Import Automation Settings Dialog ---
try:
    from src.ui.views.automation_settings_dialog import AutomationSettingsDialog
except ImportError:
    AutomationSettingsDialog = None
    logging.getLogger(__name__).warning("AutomationSettingsDialog not found, automation settings dialog disabled.")
# --- End Import ---


# Import other necessary dialogs if they exist
# from src.ui.import_export_dialog import ImportExportDialog # Already imported in MainWindow temp wrapper

# Forward declare AppService for type hinting to avoid circular import
if TYPE_CHECKING:
    from src.core.app_service import AppService
    from src.ui.main_window import MainWindow # Assuming MainWindow is the parent type
    from src.services.scheduler_service import SchedulerService # Added import
    # NewsArticle is now imported globally, can be removed from here or kept for explicitness for type checkers
    # from src.models import NewsArticle # <--- 同样修正这里的注释（如果保留）
    from src.config import AppConfig
    from src.core.history_service import HistoryService
    from src.storage.analysis_storage_service import AnalysisStorageService
    from src.containers import Container # ADDED IMPORT FOR TYPE HINTING
    # ADDED for type hint if BrowsingHistoryViewModel is used here for the attribute
    from src.ui.viewmodels.browsing_history_viewmodel import BrowsingHistoryViewModel 

class DialogManager:
    """
    Manages the creation and display of various dialogs in the application.
    """
    def __init__(self, parent_window: 'MainWindow', app_service: 'AppService', scheduler_service: 'SchedulerService', history_service: 'HistoryService', container: 'Container'): # ADDED container
        """
        Initializes the DialogManager.

        Args:
            parent_window: The main window instance, used as parent for dialogs.
            app_service: The application service instance for data access.
            scheduler_service: The scheduler service instance.
            history_service: The history service instance.
            container: The dependency injection container.
        """
        self.window = parent_window
        self.app_service = app_service
        self.config = app_service.config # Standardized config access
        self.scheduler_service = scheduler_service
        self.history_service = history_service
        self.container = container # STORED container
        self.logger = logging.getLogger(__name__)
        # Store dialog instances if they should persist or be reused
        self.source_manager_dialog: Optional[SourceManagementPanel] = None
        # self.history_dialog: Optional[BrowsingHistoryPanel] = None # REMOVED Old history dialog
        self.llm_settings_dialog: Optional[LLMSettingsDialog] = None
        self.settings_dialog: Optional[SettingsDialog] = None
        self.similarity_panel: Optional[NewsSimilarityPanel] = None
        self.integrated_panel_manager = None
        self.automation_settings_dialog: Optional[AutomationSettingsDialog] = None
        self.browsing_history_panel_instance: Optional[BrowsingHistoryPanel] = None # MODIFIED: New name for the instance
        self.active_browsing_history_view_model: Optional[BrowsingHistoryViewModel] = None # ADDED
        self.import_export_dialog_instance: Optional[ImportExportDialog] = None
        self.about_dialog: Optional[AboutDialog] = None
        self.prompt_manager_dialog: Optional[PromptManagerDialog] = None
        self.active_dialogs = set()

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
            self.source_manager_dialog = SourceManagementPanel(
                app_service=self.app_service,
                theme_manager=self.window.theme_manager,
                parent=self.window
            )
            # Refresh content if needed (assuming the dialog has a refresh method)
            if hasattr(self.source_manager_dialog, 'refresh_source_list'): # Example refresh method name
                 self.logger.debug("Refreshing source list in SourceManagementPanel.")
                 self.source_manager_dialog.refresh_source_list()
            self.source_manager_dialog.show() # Show non-modally
            # sources_updated signal from AppService will handle UI updates if dialog is open

        except Exception as e:
            # self.logger.error(f"Error opening Source Manager: {e}", exc_info=True) # Redundant logging removed
            self.show_error_message(f"无法打开新闻源管理：{e}")
            self.source_manager_dialog = None # Reset on error

    def open_settings_dialog(self):
        """Opens the application settings dialog (non-modal).""" # Updated docstring
        self.logger.debug("Attempting to open Settings dialog...")
        if not SettingsDialog:
             self.show_error_message("设置对话框组件未找到或加载失败。")
             return
        if not self.scheduler_service: # Add check for scheduler service
            self.show_error_message("调度器服务未初始化，无法打开设置对话框。")
            self.logger.error("SchedulerService not available in DialogManager, cannot open SettingsDialog.")
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
            # Pass necessary managers from the main window AND scheduler_service
            self.settings_dialog = SettingsDialog(
                theme_manager=self.window.theme_manager,             # Pass ThemeManager
                ui_settings_manager=self.window.ui_settings_manager, # Pass UISettingsManager
                scheduler_service=self.scheduler_service,          # Pass SchedulerService
                parent=self.window                                     # Pass Parent
            )
            # Connect the signal if needed (e.g., for live font updates)
            # self.settings_dialog.settings_applied.connect(self.window.handle_settings_applied) # Connect to a handler in MainWindow if needed
            self.settings_dialog.show() # Show non-modally

        except Exception as e:
            # self.logger.error(f"Error opening Settings Dialog: {e}", exc_info=True) # Redundant logging removed
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
            
            # Create ViewModel using the container
            try:
                view_model = self.container.llm_settings_view_model() # Resolve from container
            except Exception as e_resolve:
                self.logger.error(f"Failed to resolve LLMSettingsViewModel from container: {e_resolve}", exc_info=True)
                self.show_error_message("无法打开LLM设置：初始化ViewModel失败。")
                return
            
            # Pass ViewModel to Dialog
            self.llm_settings_dialog = LLMSettingsDialog(view_model, parent=self.window)
            
            # self.llm_settings_dialog.rejected_and_deleted.connect(self._on_llm_settings_closed) # Keep if still relevant

            # --- Connect settings_changed signal to LLMService reload --- Added
            # This connection might now be managed within ViewModel or still be relevant here
            # If ViewModel's activate_selected_config emits a signal that AppService listens to, that would be cleaner.
            # For now, let's assume this direct connection is still needed for immediate effect.
            # If llm_service is needed here, it should be resolved from the container too, or ViewModel should handle this.
            # For now, commenting out direct llm_service access if ViewModel manages its effects.
            # llm_service = self.container.llm_service() # Example if needed
            # self.llm_settings_dialog.settings_changed.connect(llm_service.reload_active_config)
            # --- End Connection ---

            self.llm_settings_dialog.show() # Show non-modally
        except Exception as e:
            # self.logger.error(f"Error opening LLM Settings: {e}", exc_info=True) # Redundant logging removed
            self.show_error_message(f"无法打开LLM设置：{e}")
            self.llm_settings_dialog = None # Reset on error

    def open_history_panel(self):
        """Opens the browsing history panel (non-modal)."""
        self.logger.debug("Attempting to open Browsing History panel...")
        
        if not BrowsingHistoryPanel or not BrowsingHistoryViewModel:
            self.show_error_message("浏览历史面板组件未找到或加载失败。")
            return
            
        if not self.history_service:
            self.show_error_message("历史服务未初始化，无法打开浏览历史。")
            return

        try:
            # Check if panel exists and is visible
            if self.browsing_history_panel_instance and self.browsing_history_panel_instance.isVisible():
                self.logger.debug("Browsing History panel already visible, bringing to front.")
                self.browsing_history_panel_instance.raise_()
                self.browsing_history_panel_instance.activateWindow()
                return

            # Create new ViewModel and Panel instances
            self.logger.debug("Creating new BrowsingHistoryViewModel and Panel instances.")
            
            # Create the ViewModel first
            view_model = BrowsingHistoryViewModel(
                history_service=self.history_service,
                app_service=self.app_service
            )
            
            # Create the Panel with the ViewModel
            self.browsing_history_panel_instance = BrowsingHistoryPanel(
                view_model=view_model,
                parent=self.window
            )
            
            # Connect cleanup slot
            self.browsing_history_panel_instance.destroyed.connect(self._on_browsing_history_panel_destroyed)
            
            # Show the panel
            self.browsing_history_panel_instance.show()
            self.logger.info("Successfully opened Browsing History panel.")

        except Exception as e:
            self.logger.error(f"Error opening Browsing History panel: {e}", exc_info=True)
            self.show_error_message(f"无法打开浏览历史：{e}")
            self.browsing_history_panel_instance = None  # Reset on error

    # +++ ADDED: Slot to handle news reopening request (IF PANEL/VM SUPPORTS IT) +++
    # This slot might need to be connected to a signal from BrowsingHistoryPanel if it handles item double-clicks for reopening.
    @pyqtSlot(str) # Or pyqtSlot(NewsArticle) depending on what panel emits
    def _handle_reopen_news_request(self, article_link: str):
        self.logger.info(f"Received request to reopen news article with link: {article_link}")
        if not hasattr(self.app_service, 'get_article_by_link'):
            self.logger.error("AppService does not have 'get_article_by_link' method.")
            self.show_error_message("无法获取文章详情以重新打开。")
            return

        article = self.app_service.get_article_by_link(article_link)
        if article:
            self.logger.debug(f"Article found for link {article_link}. Opening detail view.")
            self.open_news_detail(article) # This method already exists
        else:
            self.logger.warning(f"Could not find article with link: {article_link} to reopen.")
            self.show_error_message(f"未能在缓存中找到链接为 {article_link} 的文章。可能已被清除或来自非常旧的批次。")

    # +++ ADDED: Slot to clear panel reference when destroyed +++
    @pyqtSlot()
    # MODIFIED: Slot name to match instance
    def _on_browsing_history_panel_destroyed(self):
        self.logger.debug("BrowsingHistoryPanel instance destroyed, clearing reference in DialogManager.")
        self.browsing_history_panel_instance = None
    # +++ END ADDED +++

    def open_integrated_panel(self):
        """打开整合后的新闻分析与整合面板（包含相似度分析、重要程度和立场分析等功能）"""
        self.logger.debug("Attempting to open Integrated Analysis panel...")
        if not IntegratedPanelManager:
             self.show_error_message("整合分析面板组件未找到或加载失败。")
             return
        try:
            # Initialize the integrated panel manager if it doesn't exist
            if not self.integrated_panel_manager:
                self.logger.debug("Creating new IntegratedPanelManager instance.")
                self.integrated_panel_manager = IntegratedPanelManager(self.window, self.app_service)
            
            # Show the integrated panel
            self.integrated_panel_manager.show_integrated_panel()
            
        except Exception as e:
            self.show_error_message(f"无法打开新闻分析与整合面板：{e}")
            self.integrated_panel_manager = None # Reset on error


    def open_news_detail(self, news_article: NewsArticle):
        """打开新闻详情对话框。"""
        if not news_article:
            self.logger.warning("尝试打开详情但 news_article 为空")
            return

        # --- 记录浏览历史 (在打开详情之前) ---
        if self.history_service and hasattr(news_article, 'link') and news_article.link:
            try:
                self.logger.debug(f"调用 HistoryService.add_history_item for article: {news_article.title} (Link: {news_article.link}, ID: {getattr(news_article, 'id', 'N/A')})") # MODIFIED Log
                self.history_service.add_history_item(news_article) # MODIFIED: Pass NewsArticle object
            except AttributeError as e:
                # This specific AttributeError for record_browsing_history is now fixed.
                # Keep general error logging for other potential issues.
                self.logger.error(f"记录浏览历史时出错 {news_article.link}: {e}", exc_info=True)
        # --- 记录历史结束 ---

        try:
            self.logger.debug(f"DialogManager: Opening NewsDetailDialog for: {news_article.title}")
            # 确保只传递 NewsDetailDialog 定义的参数
            detail_dialog = NewsDetailDialog(news_article, parent=self.window)
            # detail_dialog.finished.connect(lambda: self._on_dialog_finished(detail_dialog))
            # 使用 functools.partial 来确保 dialog 对象在槽函数中可用
            detail_dialog.finished.connect(partial(self._on_dialog_finished, detail_dialog))
            detail_dialog.show() # 使用 show() 而不是 exec() 以允许非模态行为
            self.active_dialogs.add(detail_dialog)
            self.logger.debug(f"NewsDetailDialog for '{news_article.title}' shown. Active dialogs: {len(self.active_dialogs)}")
        except Exception as e:
            self.logger.error(f"Error creating or showing NewsDetailDialog: {e}", exc_info=True)
            QMessageBox.critical(self.window, "错误", f"无法打开新闻详情：{e}")

    def about(self):
        """Shows the About application dialog."""
        self.logger.debug("Showing About Box...")
        # Use the content from the original MainWindow.show_about
        QMessageBox.about(self.window, "关于 讯析", # Updated title
                          f"""<b>讯析 v1.0.0</b>
                          <p>一个基于 PyQt5 的桌面应用程序，用于聚合、阅读和分析来自不同来源的新闻。</p>
                          <p><b>核心功能:</b></p>
                          <ul>
                              <li>新闻源管理 (RSS, 澎湃)</li>
                              <li>新闻列表展示与分类</li>
                              <li>新闻详情阅读</li>
                              <li>LLM 新闻分析 (摘要、关键词、情感)</li>
                              <li>LLM 对话互动</li>
                              <li>界面主题切换</li>
                              <li>字体大小调整</li>
                          </ul>
                          <p>版权所有 © 2024 YourCompany</p>""")

    def show_error_message(self, message: str, title: str = "错误"):
        """Displays an error message box."""
        self.logger.error(f"显示错误消息: {title} - {message}") # Log the error
        QMessageBox.critical(self.window, title, message)

    def show_info_message(self, message: str, title: str = "信息"):
        """Displays an informational message box."""
        QMessageBox.information(self.window, title, message)

    def ask_question(self, message: str, title: str = "确认") -> bool:
        """Asks a confirmation question and returns True if Yes, False otherwise."""
        reply = QMessageBox.question(self.window, title, message,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return reply == QMessageBox.Yes

    def open_import_export(self):
        """Opens the Import/Export dialog (Placeholder - currently handled in MainWindow)."""
        # This method might replace the direct call in MainWindow eventually
        self.show_info_message("导入/导出功能暂未移至 DialogManager。")

    @pyqtSlot()
    def _on_llm_settings_closed(self):
        """Slot to handle cleanup when LLM settings dialog is closed."""
        self.logger.debug("LLM Settings dialog closed signal received.")
        self.llm_settings_dialog = None # Allow re-creation

    # @pyqtSlot()
    # def _on_history_closed(self): # REMOVED/COMMENTED - Slot for the old history dialog
    #     self.logger.debug("Old BrowsingHistoryPanel closed and deleted.")
    #     self.history_dialog = None # Clear the reference

    def open_news_similarity_panel(self):
        """打开新闻相似度分析面板（非模态）"""
        self.logger.debug("Attempting to open News Similarity panel...")
        if not NewsSimilarityPanel:
            self.show_error_message("新闻相似度分析面板组件未找到或加载失败。")
            return
        try:
            # 如果面板已存在且可见，则置于顶层
            if self.similarity_panel and self.similarity_panel.isVisible():
                self.logger.debug("News Similarity panel already visible, bringing to front.")
                self.similarity_panel.raise_()
                self.similarity_panel.activateWindow()
                return

            # 创建新实例
            self.logger.debug("Creating new NewsSimilarityPanel instance.")
            self.similarity_panel = NewsSimilarityPanel(self.app_service, self.window)
            # 连接关闭信号以进行清理
            if hasattr(self.similarity_panel, 'closed'): # Assuming a standard QDialog closed signal or custom
                self.similarity_panel.closed.connect(self._on_similarity_panel_closed)
            elif hasattr(self.similarity_panel, 'rejected'): # QDialog uses rejected
                 self.similarity_panel.rejected.connect(self._on_similarity_panel_closed)
            else:
                 self.logger.warning("Could not find a suitable close/reject signal on NewsSimilarityPanel.")

            self.similarity_panel.show()
        except Exception as e:
            self.show_error_message(f"无法打开新闻相似度分析面板：{e}")
            self.similarity_panel = None # Reset on error

    @pyqtSlot()
    def _on_similarity_panel_closed(self):
        """处理新闻相似度面板关闭时的清理工作。"""
        self.logger.debug("News Similarity panel closed signal received.")
        self.similarity_panel = None # 允许重新创建

    def open_automation_settings(self):
        """Opens the automation settings dialog (non-modal)."""
        self.logger.debug("Attempting to open Automation Settings dialog...")
        if not AutomationSettingsDialog:
            self.show_error_message("自动化设置对话框组件未找到或加载失败。")
            self.logger.error("AutomationSettingsDialog component not found or failed to load.")
            return
        if not self.scheduler_service: 
            self.show_error_message("调度器服务未初始化，无法打开自动化设置对话框。")
            self.logger.error("SchedulerService not available in DialogManager, cannot open AutomationSettingsDialog.")
            return
        try:
            if self.automation_settings_dialog and self.automation_settings_dialog.isVisible():
                self.logger.debug("Automation Settings dialog already visible, bringing to front.")
                self.automation_settings_dialog.raise_()
                self.automation_settings_dialog.activateWindow()
                return

            self.logger.debug("Creating new AutomationSettingsDialog instance.")
            self.automation_settings_dialog = AutomationSettingsDialog(
                scheduler_service=self.scheduler_service,
                parent=self.window
            )
            # self.automation_settings_dialog.accepted.connect(self._on_automation_settings_applied) # Optional: if specific actions needed on OK
            self.automation_settings_dialog.show() 
        except Exception as e:
            self.show_error_message(f"无法打开自动化设置：{e}")
            self.logger.error(f"Error opening Automation Settings Dialog: {e}", exc_info=True)
            self.automation_settings_dialog = None 

    def open_prompt_manager_dialog(self):
        if not PromptManagerDialog:
            self.show_error_message("Prompt 管理器对话框未能加载。")
            return
        if not self.prompt_manager_dialog or not self.prompt_manager_dialog.isVisible():
            self.prompt_manager_dialog = PromptManagerDialog(self.app_service.llm_service.prompt_manager, self.window)
            self.prompt_manager_dialog.show()
        else:
            self.prompt_manager_dialog.activateWindow()

    def open_import_export_dialog(self):
        if not ImportExportDialog:
            self.show_error_message("导入/导出对话框加载失败。")
            return
        
        # Determine analysis_data_dir using the service if available
        analysis_data_dir_path = os.path.join(self.config.data_dir, 'analysis') # Default
        if self.analysis_storage_service and hasattr(self.analysis_storage_service, 'DEFAULT_SUBDIR'):
            analysis_data_dir_path = os.path.join(self.config.data_dir, self.analysis_storage_service.DEFAULT_SUBDIR)
        
        dialog = ImportExportDialog(
            news_data_dir=os.path.join(self.config.data_dir, 'news'),
            analysis_data_dir=analysis_data_dir_path,
            app_service=self.app_service,
            parent=self.window
        )
        dialog.exec() 
        self.logger.debug("Import/Export dialog closed.")
        
    def about(self):
        if not AboutDialog:
            self.show_error_message("关于对话框加载失败。")
            return
        if self.about_dialog is None or not self.about_dialog.isVisible():
            self.about_dialog = AboutDialog(self.window)
            self.about_dialog.show()
        else:
            self.about_dialog.activateWindow()

    @pyqtSlot()
    def _on_import_export_closed(self):
        """Slot to handle cleanup when Import/Export dialog is closed."""
        self.logger.debug("Import/Export dialog closed signal received.")
        self.import_export_dialog_instance = None # Reset instance variable

    @pyqtSlot(object, int)
    def _on_dialog_finished(self, dialog, result_code: int):
        """Slot to handle cleanup when a dialog is finished."""
        self.logger.debug(f"Dialog finished: {dialog} with result code: {result_code}")
        if dialog in self.active_dialogs:
            self.active_dialogs.remove(dialog)
        else:
             self.logger.warning(f"Dialog {dialog} finished but was not found in active_dialogs set.")
        self.logger.debug(f"Active dialogs remaining: {len(self.active_dialogs)}")

    def get_active_browsing_history_view_model(self) -> Optional['BrowsingHistoryViewModel']:
        """Returns the active BrowsingHistoryViewModel instance, if any."""
        return self.active_browsing_history_view_model
