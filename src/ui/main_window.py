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
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QAction, QMenuBar, QStatusBar,
                             QToolBar, QMessageBox, QDialog, QLabel,
                             QLineEdit, QPushButton, QFormLayout, QTabWidget, QDockWidget,
                             QApplication, QProgressBar, QActionGroup)
# Removed Animation classes: QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup
from PyQt5.QtCore import Qt, QSize, QSettings, QTimer, pyqtSlot
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor
from typing import Optional # Import Optional for type hinting

# --- Managed by PanelManager ---
# from .sidebar import CategorySidebar
# from .news_list import NewsListPanel
# from .search_panel import SearchPanel
# from .llm_panel import LLMPanel
# from .chat_panel import ChatPanel

# --- Managed by DialogManager ---
# from .llm_settings import LLMSettingsDialog
# from .source_management_panel import SourceManagementPanel
from .import_export_dialog import ImportExportDialog # Keep for temporary _show_import_export_dialog
from .news_detail_dialog import NewsDetailDialog # Keep for _on_news_selected -> dialog_manager call

# --- Core & ViewModels ---
from .theme_manager import ThemeManager
from .ui_settings_manager import UISettingsManager
 # Keep relative for now
from src.ui.viewmodels.news_list_viewmodel import NewsListViewModel
 # Use absolute import
from src.ui.viewmodels.llm_panel_viewmodel import LLMPanelViewModel
 # Use absolute import
from src.ui.viewmodels.chat_panel_viewmodel import ChatPanelViewModel
 # Use absolute import
from src.core.app_service import AppService
from src.models import NewsSource, NewsArticle

# --- Import Managers ---
from .managers.menu_manager import MenuManager
from .managers.dialog_manager import DialogManager
from .managers.panel_manager import PanelManager
from .managers.window_state_manager import WindowStateManager
from .managers.status_bar_manager import StatusBarManager
# --- End Import Managers ---


class MainWindow(QMainWindow):
    """
    应用程序主窗口类 (Refactored).
    Acts as a coordinator, delegating UI setup and management to Manager classes.
    """

    def __init__(self, app_service: AppService):
        super().__init__()
        self.logger = logging.getLogger('news_analyzer.ui.main_window')
        self.logger.info("开始初始化主窗口 (Refactored)...")

        # 验证AppService实例
        if not isinstance(app_service, AppService):
            self.logger.error("传入的app_service不是AppService实例")
            raise ValueError("需要有效的AppService实例")

        self.app_service = app_service # 保存 AppService 实例
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
        self.dialog_manager = DialogManager(self, self.app_service)
        self.panel_manager = PanelManager(self, self.app_service)
        self.window_state_manager = WindowStateManager(self, self.settings)
        self.status_bar_manager = StatusBarManager(self) # Initializes status bar itself
        # Instantiate MenuManager last as it might depend on others
        self.menu_manager = MenuManager(self)
        self.logger.info("All managers instantiated.")
        self.import_export_dialog: Optional[ImportExportDialog] = None # Add instance variable


        # 设置窗口基本属性
        self.setWindowTitle("讯析 v1.0.0")
        # self.setMinimumSize(1200, 800) # Let WindowStateManager handle size restoration

        # --- Setup UI using Managers ---
        self._setup_ui_managers()

        # --- 连接核心信号 ---
        self._connect_core_signals()

        # Restore window state AFTER UI is set up and managers are ready
        self.window_state_manager.restore_state()

        # Restore panel state AFTER panels are created
        self.panel_manager.restore_state(self.settings)

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

        # Status bar is already set up by its manager's __init__

        # Apply theme and font size AFTER UI elements are created
        self.theme_manager.apply_saved_theme() # Use the correct method name
        self.ui_settings_manager.apply_saved_font_size() # Use the correct method name

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

        # Edit Menu
        settings_action = self.menu_manager.get_action('app_settings') # Use renamed action
        if settings_action:
            settings_action.triggered.connect(self.dialog_manager.open_settings_dialog)
        llm_settings_action = self.menu_manager.get_action('llm_settings') # Use action from Edit menu
        if llm_settings_action:
            llm_settings_action.triggered.connect(self.dialog_manager.open_llm_settings)


        # View Menu
        refresh_action = self.menu_manager.get_action('refresh')
        if refresh_action:
            refresh_action.triggered.connect(self.app_service.refresh_all_sources) # Trigger AppService
        toggle_sidebar_action = self.menu_manager.get_action('toggle_sidebar')
        if toggle_sidebar_action:
            toggle_sidebar_action.triggered.connect(lambda checked: self.panel_manager.toggle_sidebar(checked))
            # Set initial check state based on PanelManager (after setup)
            toggle_sidebar_action.setChecked(self.panel_manager.get_sidebar_visibility())
        toggle_statusbar_action = self.menu_manager.get_action('toggle_statusbar')
        if toggle_statusbar_action:
            # Assuming StatusBarManager gets a set_visibility method
            # toggle_statusbar_action.triggered.connect(lambda checked: self.status_bar_manager.set_visibility(checked))
            # toggle_statusbar_action.setChecked(self.status_bar_manager.get_visibility()) # Assuming get_visibility
            pass # Placeholder until StatusBarManager has visibility control

        # Tools Menu
        history_action = self.menu_manager.get_action('browsing_history') # Use renamed action
        if history_action:
            history_action.triggered.connect(self.dialog_manager.open_history)
        show_logs_action = self.menu_manager.get_action('show_logs')
        if show_logs_action:
            show_logs_action.triggered.connect(self._show_logs) # Keep log showing logic here for now

        # Help Menu
        about_action = self.menu_manager.get_action('about')
        if about_action:
            about_action.triggered.connect(self.dialog_manager.about)

        # --- Connect Panel Signals ---
        search_panel = self.panel_manager.get_search_panel()
        if search_panel:
            search_panel.search_requested.connect(self._handle_search_request)
            search_panel.search_cleared.connect(self.news_list_view_model.clear_search)

        sidebar = self.panel_manager.get_sidebar()
        if sidebar:
            sidebar.category_selected.connect(self.news_list_view_model.filter_by_category)
            sidebar.category_selected.connect(self.chat_panel_view_model.set_current_category)

        news_list_panel = self.panel_manager.get_news_list_panel()
        if news_list_panel:
            news_list_panel.item_double_clicked_signal.connect(self._on_news_selected) # For detail dialog
            # Connect news update signal if chat panel needs it
            news_list_panel.news_updated.connect(self._update_chat_panel_news)

        # Connect Update News button
        update_button = self.panel_manager.get_update_news_button()
        if update_button:
            update_button.clicked.connect(self.app_service.refresh_all_sources)
            self.logger.debug("Connected update_news_button.clicked to app_service.refresh_all_sources")
        else:
            self.logger.warning("Could not find update_news_button in PanelManager to connect signal.")


        # --- Connect ViewModel Signals (if needed) ---
        # Example: self.news_list_view_model.request_details_dialog.connect(self.dialog_manager.open_news_detail)

        self.logger.info("Manager/panel signals connected.")

    # --- Slot Methods (Responding to signals) ---

    @pyqtSlot(dict)
    def _handle_search_request(self, params):
        """处理搜索面板发出的搜索请求信号"""
        self.logger.debug(f"Received search params: {params}")
        try:
            self.news_list_view_model.search_news(params['query'], params['field'])
        except KeyError as e:
            self.logger.error(f"KeyError accessing params in _handle_search_request: {e} - Params: {params}")
            self.dialog_manager.show_error_message(f"搜索参数错误: {e}", "搜索错误")

    @pyqtSlot()
    def _on_sources_updated(self):
        """处理新闻源更新信号, 更新侧边栏"""
        self.logger.info("接收到新闻源更新信号")
        sidebar = self.panel_manager.get_sidebar()
        if sidebar:
            sidebar.update_categories(self.app_service.get_sources())
        else:
            self.logger.warning("Sidebar not available in PanelManager to update categories.")

    @pyqtSlot(NewsArticle)
    def _on_news_selected(self, news_article: NewsArticle):
        """处理新闻列表项双击事件，弹出新闻详情对话框"""
        if news_article and self.app_service:
            self.logger.info(f"News item double-clicked for: {news_article.title}. Requesting detailed content...")
            # 调用 AppService 获取详细内容
            # 注意：这个调用目前是同步的，如果获取详情耗时较长（例如需要启动 WebDriver），
            # UI 可能会卡顿。后续可以考虑改为异步处理。
            try:
                detailed_article = self.app_service.get_detailed_article(news_article)
                self.logger.info(f"Obtained detailed article (content length: {len(detailed_article.content) if detailed_article.content else 'None'}). Opening dialog...")
                self.dialog_manager.open_news_detail(detailed_article) # 使用获取到的详细文章对象
            except Exception as e:
                 self.logger.error(f"获取详细文章内容时出错: {e}", exc_info=True)
                 # 获取详情失败时，仍然显示基础信息，并可能提示用户
                 self.dialog_manager.show_error_message(f"无法获取新闻 '{news_article.title}' 的详细内容。\n错误: {e}", "获取详情失败")
                 # 或者选择仍然打开对话框，但内容可能不完整
                 # self.dialog_manager.open_news_detail(news_article)

    # Removed @pyqtSlot(list) decorator
    def _update_chat_panel_news(self, news_items: list[NewsArticle]):
        """更新聊天面板中的可用新闻标题 (由 NewsListPanel 信号触发)"""
        chat_panel = self.panel_manager.get_chat_panel() if self.panel_manager else None
        if chat_panel and hasattr(chat_panel, 'set_available_news_titles'):
            chat_panel.set_available_news_titles(news_items) # Pass the list directly
            self.logger.debug(f"更新聊天面板可用新闻标题，共 {len(news_items)} 条")

    @pyqtSlot() # Keep decorator but use sender()
    def _apply_selected_theme(self):
        """应用用户从菜单中选择的主题 (无动画)。"""
        self.logger.debug("_apply_selected_theme slot triggered.")
        action = self.sender() # Get the action that triggered the slot
        if isinstance(action, QAction):
            theme_name = action.data()
            self.logger.debug(f"_apply_selected_theme: Received theme name '{theme_name}' from action data.")

            # --- Prevent re-applying the same theme ---
            if theme_name == self.theme_manager.get_current_theme():
                self.logger.debug(f"Theme '{theme_name}' is already active. Skipping.")
                action.setChecked(True) # Ensure it stays checked
                return
            # --- End Prevent ---

            if theme_name and self.theme_manager:
                self.logger.info(f"用户选择应用主题: {theme_name}")
                # --- Apply theme directly ---
                apply_success = self.theme_manager.apply_theme(theme_name)
                self.logger.debug(f"_apply_selected_theme: self.theme_manager.apply_theme('{theme_name}') returned {apply_success}")
                # --- End Apply ---

                if not apply_success:
                    self.dialog_manager.show_error_message(f"无法应用主题 '{theme_name}'。将尝试恢复默认主题。", "主题错误")
                    self.theme_manager.apply_theme(ThemeManager.DEFAULT_THEME)
                    # Update menu check state (get group from menu manager)
                    theme_group = self.menu_manager.get_action_group('theme_group')
                    for act in theme_group.actions() if theme_group else []:
                        if act.data() == ThemeManager.DEFAULT_THEME:
                            act.setChecked(True) # Ensure default is checked if fallback occurs
                            break
                else:
                     # Ensure the correct action remains checked after applying
                     action.setChecked(True)
            else:
                 self.logger.warning(f"_apply_selected_theme: Invalid theme name ('{theme_name}') or theme_manager not available.")
        else:
            self.logger.warning(f"_apply_selected_theme: Sender is not a QAction or action is invalid. Sender: {action}")

    # Removed _finalize_theme_change method as animation is removed

    @pyqtSlot()
    def _on_refresh_started(self):
        """处理刷新开始信号"""
        self.logger.info("News refresh started.")
        # Optionally disable refresh action/button via MenuManager/PanelManager
        refresh_action = self.menu_manager.get_action('refresh')
        if refresh_action:
            refresh_action.setEnabled(False)
        # Connect to StatusBarManager to show progress
        if self.status_bar_manager:
            self.status_bar_manager.show_progress()


    @pyqtSlot(bool, str)
    def _on_refresh_finished(self, success: bool, message: str):
        """处理刷新完成/取消信号"""
        self.logger.info(f"News refresh finished. Success: {success}, Message: {message}")
        # Re-enable refresh action/button
        refresh_action = self.menu_manager.get_action('refresh')
        if refresh_action:
            refresh_action.setEnabled(True)
        # Update status bar via StatusBarManager
        self.status_bar_manager.show_message(message, 5000) # Show message for 5 seconds
        # Connect to StatusBarManager to hide progress
        if self.status_bar_manager:
            self.status_bar_manager.hide_progress()


    # --- Methods Delegated to DialogManager (or kept temporarily) ---

    def _show_source_management_dialog(self):
        """显示新闻源管理对话框 (Delegated)"""
        self.logger.debug("Triggering DialogManager to open source manager.")
        self.dialog_manager.open_source_manager()

    def _show_history_dialog(self):
        """显示历史记录管理对话框 (Delegated)"""
        self.logger.debug("Triggering DialogManager to open history.")
        self.dialog_manager.open_history()

    def _show_import_export_dialog(self):
        """显示导入/导出批次对话框 (非模态)"""
        self.logger.debug("Triggering to open import/export dialog (non-modal).")
        try:
            # Check if dialog exists and is visible
            if self.import_export_dialog and self.import_export_dialog.isVisible():
                self.logger.debug("Import/Export dialog already visible, bringing to front.")
                self.import_export_dialog.raise_()
                self.import_export_dialog.activateWindow()
                return

            # Create a new instance if it doesn't exist or was closed
            if not self.import_export_dialog:
                 if hasattr(self, 'app_service') and hasattr(self.app_service, 'storage'):
                      self.logger.debug("Creating new ImportExportDialog instance.")
                      self.import_export_dialog = ImportExportDialog(self.app_service.storage, self)
                 else:
                      self.dialog_manager.show_error_message("应用程序服务或存储未初始化，无法打开导入/导出功能。")
                      self.logger.error("无法创建导入/导出对话框：app_service 或 storage 不可用")
                      return

            # Refresh content if needed (assuming the dialog has a refresh method)
            if hasattr(self.import_export_dialog, '_refresh_export_combo'):
                 self.logger.debug("Refreshing export combo in ImportExportDialog.")
                 self.import_export_dialog._refresh_export_combo()

            self.import_export_dialog.show() # Show non-modally

        except ImportError as e:
             self.dialog_manager.show_error_message(f"无法加载导入/导出模块: {e}")
             self.logger.error(f"导入 ImportExportDialog 失败: {e}", exc_info=True)
             self.import_export_dialog = None # Reset instance on error
        except Exception as e:
             self.dialog_manager.show_error_message(f"打开导入/导出对话框时出错: {e}")
             self.logger.error(f"打开导入/导出对话框时出错: {e}", exc_info=True)
             self.import_export_dialog = None # Reset instance on error


    def show_about(self):
        """显示关于对话框 (Delegated)"""
        self.logger.debug("Triggering DialogManager to show about box.")
        self.dialog_manager.about()

    def show_settings(self):
        """显示设置对话框 (Delegated)"""
        self.logger.debug("Triggering DialogManager to open settings.")
        self.dialog_manager.open_settings_dialog()

    def _show_llm_settings(self):
        """显示LLM设置对话框 (Delegated)"""
        self.logger.debug("Triggering DialogManager to open LLM settings.")
        self.dialog_manager.open_llm_settings()

    # --- Utility/Internal Methods ---

    def _show_logs(self):
        """打开应用程序日志文件"""
        log_file_path = None
        # Find the FileHandler to get the log file path
        for handler in logging.getLogger('news_analyzer').handlers:
            if isinstance(handler, logging.FileHandler):
                log_file_path = handler.baseFilename
                break

        if log_file_path and os.path.exists(log_file_path):
            self.logger.info(f"尝试打开日志文件: {log_file_path}")
            try:
                if sys.platform == "win32":
                    os.startfile(log_file_path)
                elif sys.platform == "darwin": # macOS
                    subprocess.Popen(["open", log_file_path])
                else: # Linux and other Unix-like
                    subprocess.Popen(["xdg-open", log_file_path])
            except Exception as e:
                self.logger.error(f"无法自动打开日志文件 '{log_file_path}': {e}")
                self.dialog_manager.show_error_message(f"无法自动打开日志文件。\n请手动查找：\n{log_file_path}\n错误：{e}", "打开日志失败")
        else:
            self.logger.warning("未找到日志文件或文件处理器")
            self.dialog_manager.show_info_message("未找到日志文件。", "日志文件")


    def _manage_chat_history(self): # 保留的占位符
        """管理聊天历史 (占位符)"""
        self.logger.warning("聊天历史管理功能尚未实现")
        self.dialog_manager.show_info_message("聊天历史管理功能正在开发中...", "功能未实现")


    # --- Event Handlers ---

    def closeEvent(self, event):
        """处理窗口关闭事件, 保存状态"""
        self.logger.info("接收到关闭事件，开始保存状态...")

        # Save window geometry and state (docks, toolbars) via WindowStateManager
        if self.window_state_manager:
            self.window_state_manager.save_state()

        # Save panel state (splitters) via PanelManager
        if self.panel_manager:
            self.panel_manager.save_state(self.settings) # Pass settings for splitters

        # Theme and font size are saved by their managers when changed

        # Ensure background tasks can shut down gracefully
        if hasattr(self.app_service, 'shutdown'):
            self.logger.info("Requesting AppService shutdown...")
            self.app_service.shutdown()

        self.logger.info("状态保存完成，接受关闭事件")
        event.accept()

    # --- Deprecated/Removed Methods ---
    # def _init_ui(self): pass
    # def _create_actions(self): pass
    # def _create_menus(self): pass
    # def _create_statusbar(self): pass
    # def _load_settings(self): pass
    # def _save_settings(self): pass
    # def _toggle_sidebar(self): pass
    # def _toggle_statusbar(self): pass
    # def _update_side_panels(self, news_article: NewsArticle): pass
    # def _update_llm_client(self): pass
    # def _save_theme_setting(self): pass
    # def _update_status_message(self): pass # Replaced by direct status_bar_manager calls
