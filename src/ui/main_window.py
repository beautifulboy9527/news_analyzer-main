#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主窗口模块 - 包含应用程序主界面 (Refactored)

该模块实现了应用程序的主窗口，作为顶层协调者，
将 UI 组件的创建、布局和管理委托给专门的 Manager 类。
"""

import os
import logging
import threading
import queue
import sys
import subprocess
from datetime import datetime, timedelta
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QMenuBar, QStatusBar,
                             QToolBar, QMessageBox, QDialog, QLabel,
                             QLineEdit, QPushButton, QFormLayout, QTabWidget, QDockWidget,
                             QApplication, QProgressBar) # Removed QAction, QActionGroup (now in QtGui)
# Removed Animation classes: QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup
from PySide6.QtCore import Qt, QSize, QSettings, QTimer, Slot as pyqtSlot # Use Slot alias for compatibility if needed elsewhere
from PySide6.QtGui import QIcon, QFont, QPalette, QColor, QAction, QActionGroup # Added QAction, QActionGroup here
from typing import Optional, TYPE_CHECKING # Import Optional for type hinting

# --- Managed by PanelManager ---
# These panels are now likely created within PanelManager using their new paths

# --- Managed by DialogManager ---
# Dialogs are likely created within DialogManager using their new paths
from src.ui.dialogs.import_export_dialog import ImportExportDialog # Corrected import path
from src.ui.dialogs.news_detail_dialog import NewsDetailDialog # Corrected import path

# --- Core & ViewModels ---
from src.ui.managers.theme_manager import ThemeManager # Corrected import path
from src.ui.managers.ui_settings_manager import UISettingsManager # Corrected import path
from src.ui.viewmodels.news_list_viewmodel import NewsListViewModel # Absolute import
from src.ui.viewmodels.llm_panel_viewmodel import LLMPanelViewModel # Absolute import
from src.ui.viewmodels.chat_panel_viewmodel import ChatPanelViewModel


# --- Managers ---
from src.ui.managers.dialog_manager import DialogManager
from src.ui.managers.panel_manager import PanelManager
from src.ui.managers.window_state_manager import WindowStateManager
from src.ui.managers.menu_manager import MenuManager
from src.ui.managers.status_bar_manager import StatusBarManager
from src.ui.managers.similarity_panel_manager import SimilarityPanelManager
from src.ui.managers.analysis_panel_manager import AnalysisPanelManager # Add this import
from src.ui.managers.menu_prompt_manager import MenuPromptManager


# --- Type Hinting ---
if TYPE_CHECKING:
    from src.core.app_service import AppService
    from src.core.scheduler_service import SchedulerService
    from src.containers import Container # ADDED FOR TYPE HINTING
    from src.ui.viewmodels.browsing_history_viewmodel import BrowsingHistoryViewModel # For type hint

class MainWindow(QMainWindow):
    """
    应用程序主窗口类 (Refactored).
    Acts as a coordinator, delegating UI setup and management to Manager classes.
    """

    def __init__(self, app_service: 'AppService', scheduler_service: 'SchedulerService', container: 'Container'):
        super().__init__()
        self.logger = logging.getLogger('news_analyzer.ui.main_window') # Keep logger name for now
        self.logger.info("开始初始化主窗口 (Refactored)...")

        # 验证AppService实例
        if not isinstance(app_service, app_service.__class__): # More robust type check
            self.logger.error("传入的app_service不是AppService实例")
            raise ValueError("需要有效的AppService实例")

        self.app_service = app_service # 保存 AppService 实例
        self.scheduler_service = scheduler_service # Store SchedulerService instance
        self.container = container # STORED container
        self.logger.info(f"AppService初始化完成: {hasattr(self.app_service, 'storage')}")

        # --- 创建核心服务/管理器实例 ---
        self.settings = QSettings("YourCompany", "NewsAnalyzer") # Use QSettings
        self.logger.info("QSettings instance created.")
        self.theme_manager = ThemeManager() # 创建 ThemeManager 实例
        self.ui_settings_manager = UISettingsManager() # 创建 UI 设置管理器实例
        self.logger.info("ThemeManager and UISettingsManager instances created.")

        # --- 创建 ViewModel 实例 ---
        self.news_list_view_model = NewsListViewModel(self.app_service, self)
        self.llm_panel_view_model = LLMPanelViewModel(self.app_service, self.app_service.llm_service, self)
        self.chat_panel_view_model = ChatPanelViewModel(self.app_service, self.app_service.llm_service, self)
        self.logger.info("ViewModels created.")

        # --- Instantiate Managers ---
        # Instantiate managers with fewer dependencies first
        self.dialog_manager = DialogManager(self, self.app_service, self.scheduler_service, self.app_service.history_service, self.container)
        self.panel_manager = PanelManager(self, self.app_service)
        self.window_state_manager = WindowStateManager(self, self.settings)
        # Instantiate MenuManager last as it might depend on others
        self.menu_manager = MenuManager(self)
        # StatusBarManager will be instantiated in _setup_ui_managers
        self.status_bar_manager: Optional[StatusBarManager] = None # Initialize as None
        self.similarity_panel_manager = SimilarityPanelManager(self, self.app_service)
        self.analysis_panel_manager = AnalysisPanelManager(self, self.app_service)
        self.logger.info("All managers instantiated.")
        # 初始化提示词管理菜单，以便在菜单栏展示提示词管理功能
        try:
            self.menu_prompt_manager = MenuPromptManager(self, self.app_service.llm_service.prompt_manager)
        except Exception as e:
            self.logger.error(f"初始化提示词管理菜单失败: {e}")
        self.import_export_dialog: Optional[ImportExportDialog] = None # Add instance variable

        # --- ADDED: Connect to DialogManager's new signal ---
        if self.dialog_manager:
            try:
                self.dialog_manager.history_view_model_activated.connect(self._connect_to_history_vm)
                self.logger.info("Successfully connected to DialogManager.history_view_model_activated signal.")
            except AttributeError:
                self.logger.error("DialogManager does not have 'history_view_model_activated' signal. Double click to open detail might not work.")
            except Exception as e:
                self.logger.error(f"Error connecting to DialogManager.history_view_model_activated: {e}", exc_info=True)
        else:
            self.logger.error("DialogManager not initialized, cannot connect history_view_model_activated signal.")
        # --- END ADDED ---

        # 设置窗口基本属性
        self.setWindowTitle("讯析 v1.0.0")
        # self.setMinimumSize(1200, 800) # Let WindowStateManager handle size restoration

        # --- Setup UI using Managers ---
        self._setup_ui_managers()

        # --- 连接核心信号 ---
        self._connect_core_signals()

        # --- Trigger initial news load AFTER signals are connected ---
        self.logger.info("Triggering initial news load from AppService...")
        try:
            self.app_service._load_initial_news() # This triggers ViewModel update and signal
            self.logger.info("Initial news load triggered successfully.")

            # --- ADDED: Explicitly trigger UI update via timer AFTER initial load ---
            # Access the panel via the PanelManager
            news_list_panel = self.panel_manager.news_list_panel
            if news_list_panel:
                 self.logger.info("Scheduling explicit UI update for NewsListPanel shortly after startup.")
                 # Use a small delay (e.g., 100ms) to allow the window event loop to settle
                 # Call the slot that handles the ViewModel's signal
                 QTimer.singleShot(100, news_list_panel._on_news_list_changed)
            else:
                 self.logger.warning("Could not get NewsListPanel from PanelManager to schedule explicit update.")
            # --- END ADDED ---

        except Exception as e:
            self.logger.error(f"Error triggering initial news load: {e}", exc_info=True)

        # Restore window state AFTER UI is set up and managers are ready
        self.window_state_manager.restore_state()

        # Restore panel state AFTER panels are created
        self.panel_manager.restore_state(self.settings)

        # 在显示窗口前应用主题和字体大小，避免界面跳动
        self._apply_initial_theme()  # Re-enabled: Apply initial theme
        self.logger.info("Applying initial theme...")

        # 应用初始字体大小
        self.ui_settings_manager.apply_saved_font_size() # Correct way to apply font size

        self.logger.debug("Applied theme and font size before showing window to prevent UI jumping.")

        # 强制显示窗口
        self.show()
        self.raise_()
        self.activateWindow()

        # --- Animation related ---
        # self._theme_animation_group = QSequentialAnimationGroup(self) # Removed animation group

        self.logger.info("主窗口已初始化 (Refactored)")

    def _setup_ui_managers(self):
        """Initializes UI components using the respective managers."""
        self.logger.info("Setting up UI using managers...")

        # Setup panels (creates central widget and layout within PanelManager)
        self.panel_manager.setup_panels(
            self.news_list_view_model,
            self.llm_panel_view_model,
            self.chat_panel_view_model
        )

        # Setup menu bar (gets menu bar from self, populates it)
        self.menu_manager.setup_menu_bar()

        # Instantiate and setup StatusBarManager here
        self.status_bar_manager = StatusBarManager(self)
        self.logger.info("StatusBarManager instantiated and status bar set up.")
        # 主题和字体大小将在__init__方法中统一应用，避免重复应用导致界面跳动
        # Font size will be applied later in __init__ using a similar mechanism

        # Connect signals AFTER UI elements are created by managers
        self._connect_manager_signals()
        self.logger.info("UI setup via managers complete.")

    def _connect_core_signals(self):
        """Connect signals from AppService and core components."""
        self.logger.info("Connecting core signals...")
        # --- AppService Signals ---
        self.app_service.sources_updated.connect(self._on_sources_updated)
        # self.app_service.refresh_started.connect(self._on_refresh_started) # Connected via NewsUpdateService
        # self.app_service.refresh_complete.connect(self._on_refresh_finished) # Connected via NewsUpdateService

        # --- NewsUpdateService Signals (forwarded by AppService or direct if needed) ---
        # Ensure AppService correctly forwards these or connect directly if AppService doesn't handle them
        news_update_service = self.app_service.news_update_service # Get from AppService
        if news_update_service:
            news_update_service.refresh_started.connect(self._on_refresh_started)
            news_update_service.refresh_complete.connect(self._on_refresh_finished)
            news_update_service.source_refresh_progress.connect(self._on_source_refresh_progress) # Connect progress
            news_update_service.status_message_updated.connect(self._on_status_message_updated) # Connect status message
            news_update_service.error_occurred.connect(self._on_source_fetch_error) # Connect error
        else:
            self.logger.error("NewsUpdateService is not available in AppService to connect signals.")


        # --- Connect StatusBarManager Signals ---
        if self.status_bar_manager:
             self.status_bar_manager.connect_signals(self.app_service) # AppService still useful for general status
        else:
            self.logger.error("StatusBarManager not initialized before connecting core signals!")
        # --- End StatusBarManager Signals ---


        self.app_service.selected_news_changed.connect(self.llm_panel_view_model.set_current_article)
        self.app_service.selected_news_changed.connect(self.chat_panel_view_model.set_current_news)

        # --- Theme/Font Signals (Connect actions created by MenuManager) ---
        # Connections are now handled in MenuManager for individual theme actions
        theme_group = self.menu_manager.get_action_group('theme_group')
        if theme_group:
             # Set initial check state
             current_theme = self.theme_manager.get_current_theme() # Corrected method name
             for action in theme_group.actions():
                 if action.data() == current_theme:
                     action.setChecked(True)
                     break
        else:
             self.logger.warning("Could not get theme_action_group from MenuManager to set initial state.")

        increase_font_action = self.menu_manager.get_action('increase_font')
        if increase_font_action:
            increase_font_action.triggered.connect(self.ui_settings_manager.increase_font)
        decrease_font_action = self.menu_manager.get_action('decrease_font')
        if decrease_font_action:
            decrease_font_action.triggered.connect(self.ui_settings_manager.decrease_font)
        reset_font_action = self.menu_manager.get_action('reset_font')
        if reset_font_action:
            reset_font_action.triggered.connect(self.ui_settings_manager.reset_font)

        self.logger.info("Core signals connected.")


    def _connect_manager_signals(self):
        """Connect signals from UI Managers (DialogManager, PanelManager, etc.)."""
        self.logger.info("Connecting manager signals...")
        # --- DialogManager Signals (if any global ones) ---
        # Example: self.dialog_manager.some_global_signal.connect(self._handle_global_dialog_event)

        # --- PanelManager Signals ---
        if self.panel_manager:
            # Connect signals from panels created by PanelManager if needed directly by MainWindow
            # Example: if self.panel_manager.news_list_panel:
            # self.panel_manager.news_list_panel.some_signal.connect(self._some_handler)
            pass

        # --- MenuManager Signals (actions are already connected in _connect_core_signals) ---
        # Add any other specific signals from MenuManager itself if needed.

        # --- Status Bar Manager Signals ---
        # Signals for status bar updates are typically handled within StatusBarManager or AppService

        # --- Connect BrowsingHistoryViewModel signal when history panel is shown ---
        # This is now handled within _show_history_dialog to ensure ViewModel exists
        pass

        self.logger.info("Manager signals connected.")

    @pyqtSlot()
    def _on_panels_ready(self):
        """Called when PanelManager signals that all panels are created and laid out."""
        self.logger.debug("MainWindow received panels_ready signal.")
        # Restore panel visibility/state if needed
        self.panel_manager.restore_state(self.settings)
        # Connect any signals that depend on panels existing

    @pyqtSlot(dict)
    def _handle_search_request(self, params: dict):
        """Handles search requests from panels (like NewsListPanel or SearchPanel)."""
        self.logger.debug(f"MainWindow received search request: {params}")
        term = params.get('query', '')
        field = params.get('field', '标题和内容') # Default to '标题和内容'
        # Delegate search to the appropriate ViewModel (NewsListViewModel)
        self.news_list_view_model.search_news(term, field)

    @pyqtSlot()
    def _on_sources_updated(self):
        """Handles signal indicating news sources have been updated."""
        self.logger.info("MainWindow: Sources updated signal received.")
        # Update sidebar
        sidebar = self.panel_manager.get_sidebar()
        if sidebar:
            try:
                # Get sources from source_manager
                all_sources = self.app_service.source_manager.get_sources()
                # Extract unique category IDs
                unique_category_ids = sorted(list(set(s.category for s in all_sources if s.category)))
                # Pass the list of category IDs to the sidebar
                sidebar.update_categories(unique_category_ids)
                self.logger.info(f"Sidebar categories updated with {len(unique_category_ids)} unique category IDs.")
            except AttributeError as e:
                # Keep specific error logging
                self.logger.error(f"Failed to get categories: {e}. Check if AppService has source_manager and if source_manager provides sources correctly.", exc_info=True)
            except Exception as e:
                 self.logger.error(f"Error updating sidebar categories: {e}", exc_info=True)
        else:
            self.logger.warning("Sidebar not found in PanelManager to update categories.")

    @pyqtSlot(NewsArticle)
    def _on_news_selected(self, news_article: NewsArticle):
        """Handles signal when a news item is selected in the list."""
        self.logger.debug(f"MainWindow: _on_news_selected received: '{news_article.title[:30]}...'")
        # --- Notify AppService ---
        # Important: Only update selected news in AppService here.
        # ViewModel updates (like marking read) happen in NewsListPanel's slot.
        self.app_service.set_selected_news(news_article)

    def _update_chat_panel_news(self, news_items: list[NewsArticle]):
        """(DEPRECATED - Handled by ViewModel connection) Update ChatPanel with available news."""
        # chat_panel = self.panel_manager.get_panel('chat')
        # if chat_panel:
        #     chat_panel.set_available_news_items(news_items)
        pass

    @pyqtSlot() # Keep decorator but use sender()
    def _apply_selected_theme(self):
        """Applies the theme selected from the menu."""
        sender = self.sender() # Get the action that triggered the slot
        if isinstance(sender, QAction) and sender.data():
            theme_name = sender.data()
            self.logger.info(f"Applying theme: {theme_name}")
            # Delegate theme application entirely to ThemeManager
            if not self.theme_manager.apply_theme(theme_name):
                self.logger.error(f"Failed to apply theme '{theme_name}' via ThemeManager.")
                QMessageBox.warning(self, "主题错误", f"应用主题 '{theme_name}' 失败。")
            # The ThemeManager's apply_theme should handle logging success/failure and setting palette

    @pyqtSlot()
    def _on_refresh_started(self):
        """Updates UI when news refresh starts."""
        self.logger.info("MainWindow._on_refresh_started called. Updating UI elements...")
        refresh_action = self.menu_manager.get_action('refresh')
        if refresh_action:
            refresh_action.setEnabled(False)
            refresh_action.setText("正在刷新...")
            refresh_action.setToolTip("正在从所有来源获取最新新闻")
            self.logger.debug("Refresh action disabled and text updated.")
        else:
            self.logger.warning("Could not find 'refresh' action to update UI on refresh start.")
        # Update status bar via StatusBarManager
        if self.status_bar_manager:
            self.status_bar_manager.show_progress()
            self.logger.debug("Status bar manager notified to show refresh progress.")
        else:
            self.logger.warning("StatusBarManager not available in _on_refresh_started.")

    @pyqtSlot(bool, str)
    def _on_refresh_finished(self, success: bool, message: str):
        """Updates UI when news refresh finishes or is cancelled."""
        self.logger.info(f"MainWindow._on_refresh_finished called. Success: {success}, Message: '{message}'. Updating UI...")
        refresh_action = self.menu_manager.get_action('refresh')
        if refresh_action:
            refresh_action.setEnabled(True)
            refresh_action.setText("刷新新闻")
            refresh_action.setToolTip("从所有启用的来源获取最新新闻")
            self.logger.debug("Refresh action enabled and text reset.")
        else:
            self.logger.warning("Could not find 'refresh' action to update UI on refresh finish.")

        # Update status bar via StatusBarManager
        if self.status_bar_manager:
            self.status_bar_manager.hide_progress()
            self.status_bar_manager.show_message(message)
            self.logger.debug(f"Status bar manager notified to hide progress and show message: '{message}'.")
        else:
            self.logger.warning("StatusBarManager not available in _on_refresh_finished.")

        # --- Removed manual status bar update ---

    # --- NewsUpdateService Signal Handlers (Directly connected in _connect_core_signals) ---
    @pyqtSlot(str, int, int, int)
    def _on_source_refresh_progress(self, source_name: str, progress_percent: int, total_sources: int, processed_sources: int):
        self.logger.info(f"MainWindow._on_source_refresh_progress: Received progress for '{source_name}', {progress_percent}%, processed {processed_sources}/{total_sources}") # ADDED LOG
        if self.status_bar_manager:
            self.status_bar_manager.update_progress(progress_percent, f"正在刷新: {source_name} ({processed_sources}/{total_sources})")

    @pyqtSlot(str)
    def _on_status_message_updated(self, message: str):
        if self.status_bar_manager:
            self.status_bar_manager.show_message(message, is_permanent=False, timeout=5000) # Show temporary messages

    @pyqtSlot(str, str)
    def _on_source_fetch_error(self, source_name: str, error_message: str):
        self.logger.error(f"MainWindow: Received fetch error for source '{source_name}': {error_message}")
        if self.status_bar_manager:
            self.status_bar_manager.show_message(f"错误: {source_name} - {error_message}", is_permanent=False, timeout=8000, is_error=True)
    # --- END NewsUpdateService Signal Handlers ---

    def _apply_font_to_all_widgets(self, font_size_pt: int):
        """Applies the specified font size to all relevant widgets."""
        # Now delegates to UISettingsManager
        self.ui_settings_manager.apply_font_size(font_size_pt)


    def _apply_initial_theme(self):
        """Applies the last saved theme or default theme on startup using ThemeManager."""
        self.logger.debug("Applying initial theme via ThemeManager...")
        theme_name = self.theme_manager.get_current_theme() # Gets saved theme or default
        if not self.theme_manager.apply_theme(theme_name):
             self.logger.warning(f"Failed to apply initial theme '{theme_name}' via ThemeManager. Using default style.")
             # Fallback handled within ThemeManager's apply_theme or implicitly by Qt

    def _show_source_management_dialog(self):
        """(DEPRECATED) Use DialogManager."""
        self.dialog_manager.open_source_manager()

    def _show_history_dialog(self):
        """显示浏览历史对话框，并连接必要的信号。"""
        self.logger.info("Main_Window: _show_history_dialog called")
        if not self.dialog_manager:
            self.logger.error("DialogManager is not initialized!")
            QMessageBox.critical(self, "错误", "无法打开历史记录，对话框管理器未准备好。")
            print("DEBUG_PRINT: MAIN_WINDOW: DialogManager not initialized in _show_history_dialog.") # DEBUG
            return

        self.dialog_manager.open_history_panel() # This will create/show the panel and VM

        # The connection logic is now primarily handled by _connect_to_history_vm slot
        # which is triggered by DialogManager's history_view_model_activated signal.
        # We can leave this method simpler or remove the direct connection attempts from here
        # to avoid redundancy if the signal mechanism is reliable.
        
        # For robustness, we could still attempt to get the VM and connect,
        # but it might lead to multiple connections if not careful.
        # The signal-slot mechanism is cleaner.
        
        # history_vm = self.dialog_manager.get_active_browsing_history_view_model()
        # if history_vm:
        #     self.logger.info(f"MAIN_WINDOW: _show_history_dialog: Ensuring connection for VM: {history_vm} (ID: {id(history_vm)})")
        #     self._connect_to_history_vm(history_vm) # Call the common connection logic
        # else:
        #     self.logger.warning("MAIN_WINDOW: _show_history_dialog: Could not get BrowsingHistoryViewModel from DialogManager immediately after open_history_panel.")
        #     print("DEBUG_PRINT: MAIN_WINDOW: _show_history_dialog: Failed to get BrowsingHistoryViewModel from DialogManager. NO CONNECTION MADE here.")

    @pyqtSlot(int)
    def _show_news_detail_from_history(self, article_id: int):
        """Handles the request to show news detail from browsing history."""
        print(f"DEBUG_PRINT: MAIN_WINDOW: Slot _show_news_detail_from_history called with article_id: {article_id}") # ADDED PRINT
        self.logger.info(f"MainWindow: Received request to show news detail for article_id: {article_id} from history.")
        if not self.app_service or not self.dialog_manager:
            self.logger.error("AppService or DialogManager is not available.")
            QMessageBox.critical(self, "错误", "应用核心服务未准备好，无法打开新闻详情。")
            return

        try:
            article_dict = self.app_service.storage.get_article_by_id(article_id)
            
            if article_dict:
                news_article_obj = self.app_service._convert_dict_to_article(article_dict)
                if news_article_obj:
                    self.logger.debug(f"Opening NewsDetailDialog via DialogManager for article ID: {article_id}")
                    self.dialog_manager.open_news_detail(news_article_obj) # Use DialogManager
                else:
                    self.logger.error(f"Failed to convert article dictionary to NewsArticle object for ID: {article_id}")
                    QMessageBox.warning(self, "转换错误", f"无法为文章 {article_id} 准备详情视图数据。")
            else:
                self.logger.warning(f"Article with ID {article_id} not found in storage.")
                QMessageBox.warning(self, "未找到文章", f"无法找到ID为 {article_id} 的文章详情。")
        except Exception as e:
            self.logger.error(f"Error showing news detail for article ID {article_id}: {e}", exc_info=True)
            QMessageBox.critical(self, "显示错误", f"打开新闻详情时发生错误: {e}")

    def _show_import_export_dialog(self):
        """显示导入/导出对话框 (临时保留 - 应移至 DialogManager)"""
        # Check if already open
        if self.import_export_dialog and self.import_export_dialog.isVisible():
            self.import_export_dialog.activateWindow()
            self.import_export_dialog.raise_()
            return

        # Create if not exists or closed
        self.import_export_dialog = ImportExportDialog(self.app_service, self)
        self.import_export_dialog.finished.connect(self._on_import_export_closed) # Connect finished signal
        self.import_export_dialog.show()

        # Old implementation:
        # dialog = ImportExportDialog(self.app_service, self)
        # result = dialog.exec()
        # if result == QDialog.Accepted:
        #     self.logger.info("Import/Export operation completed.")
        #     # Optionally trigger a refresh or update if data changed
        #     # self._on_sources_updated() # Example: Update sidebar if sources changed
        # else:
        #     self.logger.info("Import/Export dialog cancelled.")

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于 讯析",
                          "讯析 News Analyzer v1.0.0\n\n" # <-- Update version
                          "一个用于聚合、分析和处理新闻信息的工具。\n"
                          "由 AI 驱动，提供摘要、翻译和聊天互动功能。")

    def show_settings(self):
        """(DEPRECATED) Use DialogManager."""
        self.dialog_manager.open_settings_dialog()

    def _show_logs(self):
        """在默认文本编辑器中打开日志文件目录。"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
        if os.path.exists(log_dir):
            try:
                if sys.platform == "win32":
                    os.startfile(log_dir)
                elif sys.platform == "darwin": # macOS
                    subprocess.Popen(["open", log_dir])
                else: # Linux and other UNIX-like
                    subprocess.Popen(["xdg-open", log_dir])
                self.logger.info(f"已尝试打开日志目录: {log_dir}")
            except Exception as e:
                self.logger.error(f"无法打开日志目录 {log_dir}: {e}")
                QMessageBox.warning(self, "错误", f"无法打开日志目录：{log_dir}\n{e}")
        else:
            self.logger.warning(f"日志目录未找到: {log_dir}")
            QMessageBox.warning(self, "错误", f"日志目录未找到：{log_dir}")


    @pyqtSlot()
    def _on_import_export_closed(self):
        """Slot called when the ImportExportDialog is closed."""
        self.logger.debug("Import/Export dialog closed.")
        # Clean up the reference
        if self.import_export_dialog:
            self.import_export_dialog.deleteLater() # Ensure proper cleanup
            self.import_export_dialog = None

    # Add a placeholder slot for the missing settings dialog
    @pyqtSlot()
    def _handle_missing_settings_dialog(self):
        self.logger.warning("Attempted to open settings dialog, but it's currently unavailable (file deleted?).")
        QMessageBox.information(self, "功能不可用", "应用程序设置对话框当前不可用。")

    # --- ADDED: New slot to connect to History ViewModel ---
    @pyqtSlot(object) # Use 'object' or 'BrowsingHistoryViewModel' if imported
    def _connect_to_history_vm(self, history_vm_object):
        # Cast to BrowsingHistoryViewModel if using 'object' and type checking is needed
        history_vm: Optional['BrowsingHistoryViewModel'] = history_vm_object
        
        if history_vm:
            self.logger.info(f"MAIN_WINDOW: _connect_to_history_vm: Received history_vm (ID: {id(history_vm)}). Attempting to connect news_detail_requested.")
            print(f"DEBUG_PRINT: MAIN_WINDOW: _connect_to_history_vm called with VM: {history_vm} (ID: {id(history_vm)})")
            try:
                # Disconnect first to prevent multiple connections if the signal is emitted multiple times for the same VM
                history_vm.news_detail_requested.disconnect(self._show_news_detail_from_history)
                self.logger.debug("MAIN_WINDOW: _connect_to_history_vm: Disconnected any previous news_detail_requested connection for this VM.")
            except (TypeError, RuntimeError) as e:
                self.logger.debug(f"MAIN_WINDOW: _connect_to_history_vm: No previous news_detail_requested connection to disconnect or already disconnected for this VM: {e}")
            
            history_vm.news_detail_requested.connect(self._show_news_detail_from_history)
            self.logger.info("MAIN_WINDOW: _connect_to_history_vm: Successfully connected news_detail_requested signal from history_vm.")
        else:
            self.logger.warning("MAIN_WINDOW: _connect_to_history_vm: Received a null history_vm object.")
            print("DEBUG_PRINT: MAIN_WINDOW: _connect_to_history_vm: Received null VM object. No connection made.")
    # --- END ADDED ---

    def closeEvent(self, event):
        """处理窗口关闭事件，保存状态。"""
        self.logger.info("接收到关闭事件，开始保存状态...")
        # Save window state using WindowStateManager
        self.window_state_manager.save_state()
        # Save panel state using PanelManager
        self.panel_manager.save_state(self.settings)
        # Save theme
        self.theme_manager.save_settings()

        # Shutdown AppService gracefully
        self.logger.info("Requesting AppService shutdown...")
        try:
            self.app_service.shutdown()
            self.logger.info("AppService shutdown requested successfully.")
        except Exception as e:
            self.logger.error(f"Error during AppService shutdown: {e}", exc_info=True)

        # Stop SchedulerService gracefully
        self.logger.info("Requesting SchedulerService shutdown...")
        try:
            self.scheduler_service.stop() # Changed from shutdown()
            self.logger.info("SchedulerService shutdown requested successfully.")
        except Exception as e:
            self.logger.error(f"Error during SchedulerService shutdown: {e}", exc_info=True)


        self.logger.info("状态保存完成，接受关闭事件")
        event.accept()

# --- Entry Point / For Testing (if needed) ---
if __name__ == '__main__':
    # This part is for direct execution/testing of this file,
    # usually the main application is started from main.py
    # Ensure you have a QApplication instance
    app = QApplication(sys.argv)

    # Mock services or use dummy implementations for testing
    class MockAppService:
        def __init__(self):
            self.news_cache_updated = pyqtSignal(list)
            self.sources_updated = pyqtSignal()
            self.refresh_started = pyqtSignal()
            self.refresh_complete = pyqtSignal(bool, str)
            self.selected_news_changed = pyqtSignal(object)
            self.news_update_service = MockNewsUpdateService()
            self.history_service = None # Mock if needed
            self.llm_service = MockLLMService() # Mock if needed
            self.source_manager = MockSourceManager() # Mock if needed

        def _load_initial_news(self): print("MockAppService: _load_initial_news")
        def refresh_all_sources(self): print("MockAppService: refresh_all_sources")
        def shutdown(self): print("MockAppService: shutdown")
        def set_selected_news(self, article): print(f"MockAppService: set_selected_news with {article}")

    class MockNewsUpdateService:
        def __init__(self):
            self.refresh_started = pyqtSignal()
            self.refresh_complete = pyqtSignal(bool, str)
            self.source_refresh_progress = pyqtSignal(str, int, int, int)
            self.status_message_updated = pyqtSignal(str)
            self.error_occurred = pyqtSignal(str, str)

    class MockLLMService:
        def __init__(self):
            self.prompt_manager = None # Mock if needed

    class MockSourceManager:
        def get_sources(self): return []


    class MockSchedulerService:
        def stop(self): print("MockSchedulerService: stop")

    class MockContainer:
        pass # Mock if needed


    mock_app_service = MockAppService()
    mock_scheduler_service = MockSchedulerService()
    mock_container = MockContainer()


    # Create and show the main window
    main_window = MainWindow(app_service=mock_app_service, scheduler_service=mock_scheduler_service, container=mock_container)
    main_window.show()

    sys.exit(app.exec()) 