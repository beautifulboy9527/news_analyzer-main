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
from typing import Optional # Import Optional for type hinting

# --- Managed by PanelManager ---
# These panels are now likely created within PanelManager using their new paths

# --- Managed by DialogManager ---
# Dialogs are likely created within DialogManager using their new paths
from ..import_export_dialog import ImportExportDialog # Keep for temporary _show_import_export_dialog
from ..news_detail_dialog import NewsDetailDialog # Keep for _on_news_selected -> dialog_manager call

# --- Core & ViewModels ---
from ..theme_manager import ThemeManager # Relative import
from ..ui_settings_manager import UISettingsManager # Relative import
from src.ui.viewmodels.news_list_viewmodel import NewsListViewModel # Absolute import
from src.ui.viewmodels.llm_panel_viewmodel import LLMPanelViewModel # Absolute import
from src.ui.viewmodels.chat_panel_viewmodel import ChatPanelViewModel # Absolute import
from src.core.app_service import AppService
from src.models import NewsSource, NewsArticle

# --- Import Managers ---
from ..managers.menu_manager import MenuManager # Relative import
from ..managers.dialog_manager import DialogManager # Relative import
from ..managers.panel_manager import PanelManager # Relative import
from ..managers.window_state_manager import WindowStateManager # Relative import
from ..managers.status_bar_manager import StatusBarManager # Relative import
from ..managers.similarity_panel_manager import SimilarityPanelManager # Relative import
from ..managers.analysis_panel_manager import AnalysisPanelManager # Relative import
from ..managers.menu_prompt_manager import MenuPromptManager  # Relative import
# --- End Import Managers ---

# Core services and config
from src.core.history_service import HistoryService # ADDED
from src.storage.news_storage import NewsStorage # Needed for HistoryService and AnalysisStorageService
# from src.storage.analysis_storage_service import AnalysisStorageService # ADDED # REMOVED

from src.containers import Container # ADDED FOR TYPE HINTING

class MainWindow(QMainWindow):
    """
    应用程序主窗口类 (Refactored).
    Acts as a coordinator, delegating UI setup and management to Manager classes.
    """

    def __init__(self, app_service: AppService, scheduler_service: 'SchedulerService', container: 'Container'):
        super().__init__()
        self.logger = logging.getLogger('news_analyzer.ui.main_window') # Keep logger name for now
        self.logger.info("开始初始化主窗口 (Refactored)...")

        # 验证AppService实例
        if not isinstance(app_service, AppService):
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
        self.app_service.refresh_started.connect(self._on_refresh_started)
        self.app_service.refresh_complete.connect(self._on_refresh_finished)
        # self.app_service.refresh_cancelled.connect(self._on_refresh_finished) # Removed: Redundant, handled by refresh_complete(False, ...)

        # --- Connect StatusBarManager Signals ---
        if self.status_bar_manager:
             self.status_bar_manager.connect_signals(self.app_service)
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
        """Connect signals between managers, viewmodels, and MainWindow."""
        self.logger.info("Connecting manager/panel signals...")

        # --- Connect Menu Actions to Managers/Dialogs ---
        # File Menu
        manage_sources_action = self.menu_manager.get_action('manage_sources')
        if manage_sources_action:
            manage_sources_action.triggered.connect(self.dialog_manager.open_source_manager)
        import_export_action = self.menu_manager.get_action('import_export')
        if import_export_action:
            import_export_action.triggered.connect(self._show_import_export_dialog) # Keep temp wrapper
        exit_action = self.menu_manager.get_action('exit')
        if exit_action:
            exit_action.triggered.connect(self.close) # Close MainWindow directly

        llm_settings_action = self.menu_manager.get_action('llm_settings') # Use action from Edit menu
        if llm_settings_action:
            llm_settings_action.triggered.connect(self.dialog_manager.open_llm_settings)


        # View Menu
        refresh_action = self.menu_manager.get_action('refresh')
        if refresh_action:
            # Use a lambda to log immediately upon trigger, before calling the actual method
            refresh_action.triggered.connect(
                lambda: (self.logger.debug("<<< Refresh action triggered >>>"), self.app_service.refresh_all_sources())
            )
            self.logger.debug("Connected refresh_action trigger (with lambda log) to app_service.refresh_all_sources") # Updated log message
        else:
            self.logger.warning("Refresh action not found in MenuManager.")

        # Connect theme actions (handled in MenuManager)

        # Tools Menu
        history_action = self.menu_manager.get_action('history')
        if history_action:
            history_action.triggered.connect(self.dialog_manager.open_history_panel)
        manage_prompts_action = self.menu_manager.get_action('manage_prompts') # New action
        if manage_prompts_action:
            manage_prompts_action.triggered.connect(self.dialog_manager.open_prompt_manager_dialog)

        # Window Menu (Panel toggles)
        # Get panels from PanelManager and connect toggle actions
        news_list_panel = self.panel_manager.get_news_list_panel()
        if news_list_panel:
             toggle_news_list_action = self.menu_manager.get_action('toggle_news_list')
             if toggle_news_list_action:
                 toggle_news_list_action.triggered.connect(news_list_panel.setVisible)
                 news_list_panel.visibilityChanged.connect(toggle_news_list_action.setChecked)
                 toggle_news_list_action.setChecked(news_list_panel.isVisible())
        else:
            self.logger.warning("NewsListPanel not found in PanelManager for toggle action connection.")

        chat_panel = self.panel_manager.get_chat_panel()
        if chat_panel:
             toggle_chat_action = self.menu_manager.get_action('toggle_chat')
             if toggle_chat_action:
                 toggle_chat_action.triggered.connect(chat_panel.setVisible)
                 chat_panel.visibilityChanged.connect(toggle_chat_action.setChecked)
                 toggle_chat_action.setChecked(chat_panel.isVisible())
        else:
            self.logger.warning("ChatPanel not found in PanelManager for toggle action connection.")

        llm_panel = self.panel_manager.get_llm_panel()
        if llm_panel:
            toggle_llm_action = self.menu_manager.get_action('toggle_llm')
            if toggle_llm_action:
                toggle_llm_action.triggered.connect(llm_panel.setVisible)
                llm_panel.visibilityChanged.connect(toggle_llm_action.setChecked)
                toggle_llm_action.setChecked(llm_panel.isVisible())
        else:
             self.logger.warning("LLMPanel not found in PanelManager for toggle action connection.")

        similarity_panel = self.similarity_panel_manager.get_panel()
        if similarity_panel:
            toggle_similarity_action = self.menu_manager.get_action('toggle_similarity')
            if toggle_similarity_action:
                # Connect to the manager's show method, which handles creation/showing/raising
                toggle_similarity_action.triggered.connect(self.similarity_panel_manager.show_similarity_panel)
                # visibilityChanged is unreliable for toggling dialogs this way
                # similarity_panel.visibilityChanged.connect(toggle_similarity_action.setChecked) # REMOVED
                toggle_similarity_action.setChecked(similarity_panel.isVisible()) # Set initial check state
        else:
            self.logger.warning("SimilarityPanel not found for toggle action connection.")

        # analysis_panel = self.analysis_panel_manager.get_panel() # REMOVED - Panel file missing
        # if analysis_panel:
        #     toggle_analysis_action = self.menu_manager.get_action('toggle_analysis')
        #     if toggle_analysis_action:
        #         toggle_analysis_action.triggered.connect(analysis_panel.setVisible)
        #         analysis_panel.visibilityChanged.connect(toggle_analysis_action.setChecked)
        #         toggle_analysis_action.setChecked(analysis_panel.isVisible())
        # else:
        #     self.logger.warning("AnalysisPanel not found for toggle action connection.") # Keep warning, manager still exists

        # Help Menu
        about_action = self.menu_manager.get_action('about')
        if about_action:
            about_action.triggered.connect(self.show_about)
        show_logs_action = self.menu_manager.get_action('show_logs')
        if show_logs_action:
            show_logs_action.triggered.connect(self._show_logs)
        else:
            self.logger.warning("Show logs action not found.")

        # --- Connect PanelManager signals (Panels Ready) ---
        # self.panel_manager.panels_ready.connect(self._on_panels_ready) # REMOVED - PanelManager doesn't emit this signal

        # --- Connect Panel specific signals (if needed) ---
        # Example: Connect NewsListPanel selection to MainWindow slot
        if news_list_panel:
            news_list_panel.item_selected.connect(self._on_news_selected)
            # --- Connect double-click to open detail dialog --- Added
            news_list_panel.item_double_clicked_signal.connect(self.dialog_manager.open_news_detail)
            # -------------------------------------------------
        else:
            self.logger.warning("NewsListPanel not found in PanelManager for item_selected/double_clicked connection.")

        # --- Connect Sidebar category selection to ViewModel --- Added
        sidebar_panel = self.panel_manager.get_sidebar()
        if sidebar_panel:
            if hasattr(sidebar_panel, 'category_selected'):
                sidebar_panel.category_selected.connect(self.news_list_view_model.filter_by_category)
                self.logger.info("Connected SidebarPanel.category_selected to NewsListViewModel.filter_by_category.")
                # Connect sidebar's update request signal to AppService refresh
                sidebar_panel.update_news_requested.connect(self.app_service.refresh_all_sources)
                self.logger.debug("Connected sidebar update_news_requested to app_service.refresh_all_sources")
            else:
                self.logger.error("SidebarPanel instance found, but it lacks the 'category_selected' signal.")
        else:
            self.logger.warning("SidebarPanel not found in PanelManager for category_selected connection.")

        # --- Connect UI Settings signals ---
        self.ui_settings_manager.font_size_changed.connect(self._apply_font_to_all_widgets) # Connect font change

        # --- Connect SearchPanel Signals --- Added
        search_panel = self.panel_manager.get_search_panel()
        if search_panel:
            search_panel.search_requested.connect(self._handle_search_request)
            # Connect search_cleared to NewsListViewModel's clear_search slot
            search_panel.search_cleared.connect(self.news_list_view_model.clear_search) # Ensure this slot exists
            self.logger.info("Connected SearchPanel signals to MainWindow and NewsListViewModel.")
        else:
            self.logger.warning("SearchPanel not found in PanelManager for signal connection.")
        # --- End Connect SearchPanel Signals ---

        self.logger.info("Manager/panel signals connected.")

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

        self.dialog_manager.open_history_panel() # MODIFIED: Corrected method name

        # The connection logic is now primarily handled by _connect_to_history_vm slot
        # which is triggered by DialogManager's history_view_model_activated signal.

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

    def _show_llm_settings(self):
        """(DEPRECATED) Use DialogManager."""
        self.dialog_manager.open_llm_settings()

    def _show_logs(self):
        """在默认文本编辑器中打开日志文件。"""
        log_dir = os.path.join(os.path.dirname(sys.argv[0]), "logs")
        log_file_name = "news_analyzer.log"
        log_file_path = os.path.join(log_dir, log_file_name)

        self.logger.info(f"Attempting to open log file: {log_file_path}")

        if not os.path.exists(log_file_path):
            self.logger.warning("Log file does not exist.")
            QMessageBox.warning(self, "日志文件未找到", f"日志文件不存在于：\n{log_file_path}")
            return

        try:
            if sys.platform == "win32":
                os.startfile(log_file_path) # More reliable on Windows
            elif sys.platform == "darwin":
                subprocess.Popen(["open", log_file_path])
            else: # Linux and other Unix-like
                subprocess.Popen(["xdg-open", log_file_path])
            self.logger.info("Log file opened successfully.")
        except FileNotFoundError:
             self.logger.error(f"'open' or 'xdg-open' command not found. Cannot open log file automatically.")
             QMessageBox.warning(self, "无法打开日志", "无法自动打开日志文件。请手动导航到日志目录。")
        except Exception as e:
            self.logger.error(f"Error opening log file: {e}", exc_info=True)
            QMessageBox.warning(self, "打开日志时出错", f"打开日志文件时发生错误：\n{e}")


    def _manage_chat_history(self): # 保留的占位符
        """占位符：未来可能用于管理聊天历史记录"""
        QMessageBox.information(self, "功能待开发", "聊天历史管理功能正在开发中。")
        self.logger.info("_manage_chat_history called (placeholder)")

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