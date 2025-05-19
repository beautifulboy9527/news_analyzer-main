# src/ui/theme_manager.py
import os
import logging
from typing import List, Optional
from PySide6.QtWidgets import QApplication # Use PySide6 consistently
from PySide6.QtCore import QSettings, QDir, QThread, QMetaObject, Qt, QTimer # Use PySide6 consistently

# Removed duplicate import

class ThemeManager:
    """
    管理应用程序的主题（QSS样式表）。

    负责查找、加载、应用和切换主题文件。
    """
    SETTINGS_KEY = "ui/theme"
    DEFAULT_THEME = "light"
    AVAILABLE_THEMES = {"light": "亮色主题", "dark": "暗色主题"}

    def __init__(self, themes_dir: Optional[str] = None):
        """
        初始化 ThemeManager。

        Args:
            themes_dir: 包含 .qss 主题文件的目录路径。如果为 None，
                        则默认为相对于此文件位置的 '../themes' 目录。
        """
        self.logger = logging.getLogger('ui.theme_manager')
        if themes_dir is None:
            # 确定 themes 目录的路径 (相对于 theme_manager.py)
            # base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # 旧的错误逻辑
            # self.themes_dir = os.path.join(base_dir, 'themes') # 旧的错误逻辑
            current_dir = os.path.dirname(os.path.abspath(__file__)) # 获取当前文件所在目录 (src/ui/)
            self.themes_dir = os.path.join(current_dir, 'themes') # 正确的路径 (src/ui/themes)
        else:
            self.themes_dir = themes_dir

        self.logger.info(f"主题目录设置为: {self.themes_dir}")

        # 初始化settings为None，确保属性存在
        self.settings = None
        self._settings_initialized = False
        self._current_theme = None
        self._init_settings()  # 立即初始化设置

    def get_current_theme(self) -> str:
        """获取当前主题名称"""
        if not self._settings_initialized:
            self._initialize_settings()
        return self._current_theme or self.settings.value(self.SETTINGS_KEY, self.DEFAULT_THEME)

    def _initialize_settings(self):
        """初始化设置"""
        if not self._settings_initialized:
            self.settings = QSettings()
            self._current_theme = self.settings.value(self.SETTINGS_KEY, self.DEFAULT_THEME)
            self._settings_initialized = True

    def get_available_themes(self) -> dict:
        """获取可用的主题列表"""
        return self.AVAILABLE_THEMES

    def get_theme_display_name(self, theme_name: str) -> str:
        """获取主题的显示名称"""
        return self.AVAILABLE_THEMES.get(theme_name, theme_name)

    def toggle_theme(self) -> bool:
        """切换主题（在亮色和暗色之间切换）"""
        current = self.get_current_theme()
        new_theme = "dark" if current == "light" else "light"
        return self.apply_theme(new_theme)

    def apply_theme(self, theme_name: str) -> bool:
        """
        应用指定的主题。

        Args:
            theme_name: 要应用的主题名称（不带.qss扩展名）

        Returns:
            bool: 如果主题应用成功返回True，否则返回False
        """
        self.logger.info(f"尝试应用主题: {theme_name}")
        
        if not self._settings_initialized:
            self._init_settings()

        # 检查主题是否已加载
        if theme_name == self._current_theme:
            self.logger.debug(f"主题 {theme_name} 已经是当前主题，跳过重新加载")
            return True

        theme_path = os.path.join(self.themes_dir, f"{theme_name}.qss")
        if not os.path.exists(theme_path):
            self.logger.error(f"主题文件不存在: {theme_path}")
            return False

        try:
            with open(theme_path, 'r', encoding='utf-8') as f:
                style_sheet = f.read()
            
            # 应用主题前先清除现有样式
            QApplication.instance().setStyleSheet("")
            
            # 应用新主题 (TEMP DEBUG: Don't apply dark.qss content)
            # if theme_name == 'dark':
            #     self.logger.warning("TEMP DEBUG: Skipping setStyleSheet for dark theme to isolate issue.")
                 # We still need to set *something* or it might revert to default light
                 # QApplication.instance().setStyle("Fusion") # Optional: Ensure a style is set
                 # We might need to force a palette update here if Qt doesn't do it automatically
                 # pass # Or do nothing and hope Qt's default dark mode works
            # else:
                 # Apply light theme or any other theme normally
            #     QApplication.instance().setStyleSheet(style_sheet)
            # Restore normal application
            QApplication.instance().setStyleSheet(style_sheet)
            
            # 更新当前主题和设置
            self._current_theme = theme_name
            if self.settings:
                self.settings.setValue(self.SETTINGS_KEY, theme_name)
                self.settings.sync()
            
            self.logger.info(f"成功应用主题: {theme_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"应用主题时出错: {str(e)}")
            return False

    def _find_themes(self) -> List[str]:
        """查找 themes 目录下的所有 .qss 文件，返回主题名称列表。"""
        themes = []
        if not os.path.isdir(self.themes_dir):
            self.logger.warning(f"主题目录不存在或不是一个目录: {self.themes_dir}")
            return themes

        try:
            for filename in os.listdir(self.themes_dir):
                # Ensure we only process .qss files and ignore temporary files like .qss.tmp
                if filename.lower().endswith(".qss") and not filename.lower().endswith(".qss.tmp"):
                    theme_name = os.path.splitext(filename)[0] # 去掉 .qss 后缀
                    themes.append(theme_name)
            self.logger.info(f"找到可用主题: {themes}")
        except OSError as e:
            self.logger.error(f"查找主题文件时出错: {e}", exc_info=True)
        # Filter out disallowed themes here if needed, or rely on MenuManager filtering
        allowed_themes = {"light", "dark"}
        final_themes = [t for t in themes if t in allowed_themes]
        if len(final_themes) < len(themes):
             self.logger.warning(f"过滤掉不可用或不允许的主题: {set(themes) - set(final_themes)}")
        return sorted(final_themes) # 按名称排序

    def load_theme_stylesheet(self, theme_name: str) -> Optional[str]:
        """
        加载指定主题名称的 QSS 文件内容。

        Args:
            theme_name: 主题名称 (不含 .qss 后缀)。

        Returns:
            QSS 样式表内容的字符串，如果失败则返回 None。
        """
        self.logger.debug(f"ThemeManager: 尝试加载主题样式表: {theme_name}") # Added log
        if theme_name not in self.get_available_themes():
            self.logger.warning(f"尝试加载不存在或不允许的主题: {theme_name}. 可用主题: {self.get_available_themes()}") # Log available themes
            return None

        file_path = os.path.join(self.themes_dir, f"{theme_name}.qss")
        self.logger.debug(f"ThemeManager: Reading stylesheet from: {file_path}") # Log file path
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                stylesheet = f.read()
                self.logger.info(f"成功加载主题 '{theme_name}' 的样式表 (长度: {len(stylesheet)}).") # Updated log
                # 添加自定义覆盖样式
                override_styles = ''
                if theme_name == 'light':
                    override_styles = """
                    /* --- Minimal QSpinBox Test for Light Theme --- */
                    QSpinBox#SchedulerHoursSpin {
                        background-color: yellow !important; 
                        border: 2px solid orange !important; 
                        color: black !important;
                    }
                    QSpinBox#SchedulerMinutesSpin {
                        background-color: lightblue !important; 
                        border: 2px solid blue !important; 
                        color: black !important;
                    }
                    """
                elif theme_name == 'dark':
                    override_styles = """
                    /* --- Minimal QSpinBox Test for Dark Theme --- */
                    QSpinBox#SchedulerHoursSpin {
                        background-color: darkred !important; 
                        border: 2px solid red !important; 
                        color: white !important;
                    }
                    QSpinBox#SchedulerMinutesSpin {
                        background-color: darkgreen !important; 
                        border: 2px solid green !important; 
                        color: white !important;
                    }
                    """
                stylesheet += override_styles
                return stylesheet
        except FileNotFoundError:
            self.logger.error(f"主题文件未找到（虽然之前已发现）: {file_path}")
            return None
        except OSError as e:
            self.logger.error(f"读取主题文件失败: {file_path} - {e}", exc_info=True)
            return None
        except Exception as e:
             self.logger.error(f"加载主题 '{theme_name}' 时发生未知错误: {e}", exc_info=True)
             return None

    def apply_initial_theme(self):
        """
        Applies the saved theme or the default theme when the application starts.
        This should be called *after* the QApplication instance is created.
        """
        self.logger.info("ThemeManager: Entering apply_initial_theme...") # Enhanced log
        # 首先检查QApplication实例是否可用
        app_instance = QApplication.instance()
        if app_instance is None:
            self.logger.error("无法应用初始主题：QApplication实例不可用。将在实例可用时重试。")
            return False
            
        # Ensure settings are loaded correctly before getting the theme
        self.logger.debug(f"State before getting theme: _settings_initialized={self._settings_initialized}")
        if not self._settings_initialized:
            self.logger.warning("Settings not initialized when applying initial theme. Attempting to init again.")
            self._init_settings() # Attempt re-initialization
            self.logger.debug(f"State after re-init attempt: _settings_initialized={self._settings_initialized}")

        theme_to_apply = self.get_current_theme()
        self.logger.info(f"ThemeManager: Determined initial theme: {theme_to_apply}")
        if not self.apply_theme(theme_to_apply):
             self.logger.error(f"Initial theme application failed for '{theme_to_apply}'")
             # Optionally, attempt to apply the default theme as a fallback
             if theme_to_apply != self.DEFAULT_THEME:
                  self.logger.warning(f"Attempting to apply default theme '{self.DEFAULT_THEME}' as fallback.")
                  self.apply_theme(self.DEFAULT_THEME)
        return True

    def _init_settings(self):
        """初始化QSettings配置"""
        try:
            self.settings = QSettings()
            self._settings_initialized = True
            self.logger.info(f"QSettings初始化成功")
        except Exception as e:
            self.logger.error(f"初始化 QSettings 失败: {e}", exc_info=True)
            self.settings = None
            self._settings_initialized = False

    # Note: delayed_theme_application logic was removed previously or intended to be.

    def save_current_theme(self, theme_name: str):
        """保存当前选中的主题名称到设置。"""
        self.logger.info(f"ThemeManager: 尝试保存主题 '{theme_name}' 到设置 (Key: {self.SETTINGS_KEY})...") # Added log
        
        # 检查主题名称是否有效
        if theme_name not in self.get_available_themes():
            self.logger.warning(f"尝试保存无效或不可用的主题名称: {theme_name} (可用: {self.get_available_themes()})")
            return
            
        # 检查设置对象是否可用
        if not self._settings_initialized or self.settings is None:
            self.logger.error(f"无法保存主题 '{theme_name}'：QSettings 未初始化")
            # 尝试重新初始化设置
            self._init_settings()
            if not self._settings_initialized or self.settings is None:
                self.logger.error("重新初始化 QSettings 失败，无法保存主题设置")
                return
                
        try:
            self.logger.debug(f"ThemeManager: Calling settings.setValue('{self.SETTINGS_KEY}', '{theme_name}')") # Log before setValue
            self.settings.setValue(self.SETTINGS_KEY, theme_name)
            self.logger.debug(f"ThemeManager: Calling settings.sync()") # Log before sync
            self.settings.sync() # Ensure changes are written to storage
            status = self.settings.status()
            self.logger.info(f"ThemeManager: settings.sync() finished. Status: {status}") # Log after sync and status
            if status == QSettings.NoError:
                self.logger.info(f"已成功保存当前主题为: {theme_name}")
                # --- Verification Log ---
                verify_read = self.settings.value(self.SETTINGS_KEY)
                self.logger.info(f"ThemeManager: Verification read after save: Value for '{self.SETTINGS_KEY}' is '{verify_read}'")
                # --- End Verification ---
            else:
                self.logger.error(f"保存主题到 QSettings 失败！状态: {status}")
        except Exception as e:
             self.logger.error(f"保存主题 '{theme_name}' 到设置时发生异常: {e}", exc_info=True)

    def save_settings(self):
        """Ensures any pending theme setting changes are saved to persistent storage."""
        if self.settings:
            self.logger.debug("Syncing theme settings...")
            self.settings.sync()
            self.logger.info("Theme settings synced.")
        else:
            self.logger.warning("Cannot save theme settings, QSettings not initialized.")

# Test code removed, should be in a separate test file.