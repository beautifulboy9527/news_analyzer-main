# src/ui/managers/menu_manager.py
# Use PySide6 consistently
from PySide6.QtWidgets import QMenuBar, QMenu, QApplication, QWidget
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtCore import Qt, Slot
from typing import TYPE_CHECKING, Optional
import logging

# Imports related to the removed SourceManagementDialog are deleted.

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow  # Avoid circular import
    from src.core.app_service import AppService
    from .dialog_manager import DialogManager
    from .panel_manager import PanelManager
    from src.ui.theme_manager import ThemeManager
    from src.ui.ui_settings_manager import UISettingsManager


class MenuManager:
    """
    Manages the creation and setup of the main menu bar, menus, and actions.
    Connects actions to appropriate handlers in other managers or the main window.
    """
    def __init__(self, parent_window: 'MainWindow'):
        """
        Initializes the MenuManager.

        Args:
            parent_window: The main window instance (MainWindow).
        """
        self.window = parent_window
        # Access other managers/services via the parent window instance
        self.app_service: 'AppService' = parent_window.app_service
        self.dialog_manager: 'DialogManager' = parent_window.dialog_manager # Assumes dialog_manager is created before menu_manager connects signals
        self.panel_manager: 'PanelManager' = parent_window.panel_manager # Assumes panel_manager is created
        self.theme_manager: 'ThemeManager' = parent_window.theme_manager
        self.ui_settings_manager: 'UISettingsManager' = parent_window.ui_settings_manager
        self.logger = logging.getLogger(__name__) # Add logger

        self.menu_bar: QMenuBar = None
        self.menus: dict[str, QMenu] = {}
        self.actions: dict[str, QAction] = {}
        self.action_groups: dict[str, QActionGroup] = {}


    def setup_menu_bar(self):
        """
        Creates the main menu bar and populates it with menus and actions.
        This method should be called after the main window and other managers are initialized.
        """
        self.menu_bar = self.window.menuBar() # Get menu bar from main window

        # Create all actions first
        self._create_all_actions()

        # Then create menus and add actions
        self._create_file_menu()
        self._create_edit_menu()
        self._create_view_menu()
        self._create_tools_menu()
        self._create_prompt_menu()  # 添加提示词菜单
        self._create_help_menu()

        # Connect signals (now done within _create_all_actions)

    def get_action(self, name: str) -> QAction | None:
        """Gets a specific action by name."""
        return self.actions.get(name)

    def get_action_group(self, name: str) -> QActionGroup | None:
        """Gets a specific action group by name."""
        return self.action_groups.get(name)

    def _add_action(self, name: str, action: QAction):
        """Helper to add action to the dictionary."""
        self.actions[name] = action

    def _create_all_actions(self):
        """Creates all QAction objects and connects their signals."""
        # --- File Menu Actions ---
        manage_sources_action = QAction("管理新闻源...") # Create without parent
        manage_sources_action.setStatusTip("添加、编辑或删除新闻源")
        manage_sources_action.triggered.connect(self.dialog_manager.open_source_manager)
        self._add_action('manage_sources', manage_sources_action)

        import_export_action = QAction("导入/导出批次...", self.window)
        import_export_action.setStatusTip("导入或导出新闻分析批次")
        # Connect to the temporary wrapper in MainWindow for now
        import_export_action.triggered.connect(self.window._show_import_export_dialog)
        self._add_action('import_export', import_export_action)

        exit_action = QAction("退出", self.window)
        exit_action.setStatusTip("退出应用程序")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.window.close) # Connect to MainWindow's close
        self._add_action('exit', exit_action)

        # --- Edit Menu Actions ---
        # Renamed from 'settings' to 'app_settings'
        app_settings_action = QAction("应用程序设置...", self.window)
        app_settings_action.setStatusTip("配置应用程序常规设置")
        app_settings_action.triggered.connect(self.dialog_manager.open_settings_dialog) # Still points to the same placeholder
        self._add_action('app_settings', app_settings_action)

        # Moved from Tools menu
        llm_settings_action = QAction("LLM 设置...", self.window)
        llm_settings_action.setStatusTip("配置语言模型设置")
        llm_settings_action.triggered.connect(self.dialog_manager.open_llm_settings)
        self._add_action('llm_settings', llm_settings_action)


        # --- View Menu Actions ---
        refresh_action = QAction("更新新闻", self.window)
        refresh_action.setStatusTip("获取最新新闻")
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.app_service.refresh_all_sources)
        self._add_action('refresh', refresh_action)

        toggle_sidebar_action = QAction("切换侧边栏", self.window, checkable=True)
        toggle_sidebar_action.setStatusTip("显示或隐藏新闻分类侧边栏")
        toggle_sidebar_action.setChecked(True) # Default state, might be overridden by settings restore
        toggle_sidebar_action.triggered.connect(lambda checked: self.panel_manager.toggle_sidebar(checked))
        self._add_action('toggle_sidebar', toggle_sidebar_action)

        toggle_statusbar_action = QAction("切换状态栏", self.window, checkable=True)
        toggle_statusbar_action.setStatusTip("显示或隐藏状态栏")
        toggle_statusbar_action.setChecked(True) # Default state
        # TODO: Connect to StatusBarManager visibility toggle if implemented
        # toggle_statusbar_action.triggered.connect(lambda checked: self.status_bar_manager.set_visibility(checked))
        self._add_action('toggle_statusbar', toggle_statusbar_action)

        # --- Font Size Actions (REMOVED from View Menu) ---
        # increase_font_action = QAction("增大字体", self.window)
        # increase_font_action.setStatusTip("增大应用程序字体")
        # increase_font_action.setShortcut("Ctrl++")
        # increase_font_action.triggered.connect(self.ui_settings_manager.increase_font)
        # self._add_action('increase_font', increase_font_action)
        #
        # decrease_font_action = QAction("减小字体", self.window)
        # decrease_font_action.setStatusTip("减小应用程序字体")
        # decrease_font_action.setShortcut("Ctrl+-")
        # decrease_font_action.triggered.connect(self.ui_settings_manager.decrease_font)
        # self._add_action('decrease_font', decrease_font_action)
        #
        # reset_font_action = QAction("重置字体", self.window)
        # reset_font_action.setStatusTip("恢复默认字体大小")
        # reset_font_action.triggered.connect(self.ui_settings_manager.reset_font)
        # self._add_action('reset_font', reset_font_action)

        # --- Theme Actions (Moved to Settings Dialog, but keep group for now if needed elsewhere) ---
        theme_action_group = QActionGroup(self.window)
        theme_action_group.setExclusive(True)
        self.action_groups['theme_group'] = theme_action_group # Store the group

        allowed_themes = {"light", "dark"} # Only allow light and dark themes
        available_themes = self.theme_manager.get_available_themes()
        self.logger.debug(f"Available themes found: {available_themes}")

        for theme_name in available_themes:
            if theme_name in allowed_themes: # Only create actions for allowed themes
                display_name = "白天模式" if theme_name == "light" else "黑暗模式" if theme_name == "dark" else theme_name.capitalize()
                action = QAction(display_name, self.window, checkable=True)
                action.setStatusTip(f"切换到 {display_name}")
                action.setData(theme_name) # Store the actual theme name ('light' or 'dark')
                # Connect individual action's triggered signal (MainWindow handles theme application)
                action.triggered.connect(self.window._apply_selected_theme)
                self.logger.debug(f"Connected action '{display_name}'.triggered to self.window._apply_selected_theme")
                theme_action_group.addAction(action)
                self.logger.debug(f"Created theme action for: {theme_name} (Display: {display_name})")
            else:
                self.logger.warning(f"Skipping creation of menu action for disallowed theme: {theme_name}")


        # --- Tools Menu Actions ---
        # DELETED: browsing_history_action and manage_chat_history_action

        # ADDED: Consolidated History Management Action
        manage_all_history_action = QAction("历史记录管理...", self.window)
        manage_all_history_action.setStatusTip("管理浏览、分析和聊天记录")
        
        # --- DEBUGGING: Trace history panel action trigger ---
        def trigger_history_panel_slot():
            self.logger.info("[DEBUG] MenuManager: 'manage_all_history_action' triggered.")
            if hasattr(self.window, '_show_history_dialog') and callable(self.window._show_history_dialog):
                self.logger.info("[DEBUG] MenuManager: Calling self.window._show_history_dialog().")
                try:
                    self.window._show_history_dialog()
                except Exception as e_main_show_history:
                    self.logger.error(f"[DEBUG] MenuManager: Error during self.window._show_history_dialog() call: {e_main_show_history}", exc_info=True)
            else:
                self.logger.error("[DEBUG] MenuManager: self.window does not have a callable '_show_history_dialog' method. Falling back to direct dialog_manager call or error.")
        # --- END DEBUGGING ---
        
        manage_all_history_action.triggered.connect(trigger_history_panel_slot) # Connect to the new debug slot
        self._add_action('manage_all_history', manage_all_history_action)
        
        # 新闻分析与整合功能 (整合后的菜单项)
        news_analysis_action = QAction("新闻分析与整合...", self.window)
        news_analysis_action.setStatusTip("使用AI分析和整合多个相似新闻，提供相似度分析、重要程度和立场分析等功能")
        news_analysis_action.triggered.connect(self.dialog_manager.open_integrated_panel)
        self._add_action('news_analysis', news_analysis_action)

        # --- Automation Settings Action (New) ---
        automation_settings_action = QAction("自动化设置...", self.window)
        automation_settings_action.setStatusTip("配置自动化任务，如新闻自动刷新")
        automation_settings_action.triggered.connect(self.dialog_manager.open_automation_settings)
        self._add_action('automation_settings', automation_settings_action)

        # --- Help Menu Actions ---
        about_action = QAction("关于", self.window)
        about_action.setStatusTip("显示关于对话框")
        # Assuming dialog_manager has an 'about' method or similar
        # If not, this might need adjustment based on DialogManager implementation
        if hasattr(self.dialog_manager, 'about'):
             about_action.triggered.connect(self.dialog_manager.about)
        else:
             self.logger.warning("DialogManager does not have an 'about' method. 'About' action disabled.")
             about_action.setEnabled(False)
        self._add_action('about', about_action)

        # --- ADDED: Show Logs Action ---
        show_logs_action = QAction("显示日志", self.window)
        show_logs_action.setStatusTip("打开日志查看器或显示日志文件")
        # TODO: Connect this to an actual log viewing mechanism
        show_logs_action.triggered.connect(lambda: self.logger.info("'Show Logs' action clicked (not fully implemented)."))
        self._add_action('show_logs', show_logs_action)
        # --- END ADDED ---


    # --- Private Helper Methods for Menu Creation ---

    def _create_file_menu(self):
        """Creates the File menu and adds its actions."""
        menu = self.menu_bar.addMenu("&文件")
        self.menus['file'] = menu
        menu.addAction(self.get_action('manage_sources'))
        menu.addAction(self.get_action('import_export'))
        menu.addSeparator()
        menu.addAction(self.get_action('exit'))

    def _create_edit_menu(self):
        """Creates the Edit menu and adds its actions."""
        menu = self.menu_bar.addMenu("&编辑")
        self.menus['edit'] = menu
        menu.addAction(self.get_action('llm_settings')) # Moved from Tools
        menu.addAction(self.get_action('app_settings')) # Renamed from 'settings'
        
        # 添加提示词管理到设置菜单
        prompt_manager_action = QAction("提示词管理...", self.window)
        prompt_manager_action.setStatusTip("管理提示词模板")
        prompt_manager_action.triggered.connect(self.window.menu_prompt_manager._show_template_manager)
        self._add_action('prompt_manager', prompt_manager_action)
        menu.addAction(prompt_manager_action)

    def _create_view_menu(self):
        """Creates the View menu and adds its actions."""
        menu = self.menu_bar.addMenu("&视图")
        self.menus['view'] = menu
        menu.addAction(self.get_action('refresh'))
        menu.addSeparator()
        menu.addAction(self.get_action('toggle_sidebar'))
        menu.addAction(self.get_action('toggle_statusbar'))
        # --- REMOVED Theme and Font submenus ---
        # menu.addSeparator()
        # theme_menu = menu.addMenu("主题")
        # theme_group = self.get_action_group('theme_group')
        # if theme_group:
        #     for action in theme_group.actions():
        #         theme_menu.addAction(action)
        #     # Set initial check state based on ThemeManager
        #     current_theme = self.theme_manager.get_current_theme() # Use the correct method name
        #     for action in theme_group.actions():
        #         if action.data() == current_theme:
        #             action.setChecked(True)
        #             break
        # menu.addSeparator()
        # font_menu = menu.addMenu("字体大小")
        # font_menu.addAction(self.get_action('increase_font'))
        # font_menu.addAction(self.get_action('decrease_font'))
        # font_menu.addAction(self.get_action('reset_font'))
        # --- End REMOVED ---


    def _create_tools_menu(self):
        """Creates the Tools menu and adds its actions."""
        menu = self.menu_bar.addMenu("&工具")
        self.menus['tools'] = menu
        # menu.addAction(self.get_action('browsing_history')) # REMOVED
        menu.addAction(self.get_action('manage_all_history')) # ADDED
        menu.addAction(self.get_action('news_analysis')) # 新闻分析与整合
        # menu.addAction(self.get_action('manage_chat_history')) # REMOVED
        menu.addAction(self.get_action('automation_settings')) # Moved up for grouping, check original order if important
        menu.addSeparator()
        menu.addAction(self.get_action('show_logs'))
        # menu.addAction(self.get_action('source_status')) # Removed

    def _create_prompt_menu(self):
        """Creates the Prompt menu and adds its actions."""
        # 移除提示词菜单，因为功能已移到设置菜单下
        pass

    def _create_help_menu(self):
        """Creates the Help menu and adds its actions."""
        menu = self.menu_bar.addMenu("&帮助")
        self.menus['help'] = menu
        menu.addAction(self.get_action('about'))

    # Removed _open_source_status_dialog method