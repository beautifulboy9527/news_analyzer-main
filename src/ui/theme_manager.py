# src/ui/theme_manager.py
import os
import logging
from typing import List, Optional
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QSettings, QDir

class ThemeManager:
    """
    管理应用程序的主题（QSS样式表）。

    负责查找、加载、应用和切换主题文件。
    """
    SETTINGS_KEY = "ui/theme"
    DEFAULT_THEME = "dark" # 将默认主题更改为 dark

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
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.themes_dir = os.path.join(base_dir, 'themes')
        else:
            self.themes_dir = themes_dir

        self.logger.info(f"主题目录设置为: {self.themes_dir}")

        # --- Use INI format for QSettings ---
        # Ensure organization and application names are set for INI path consistency
        QApplication.setOrganizationName("YourCompany") # Or your actual company name
        QApplication.setApplicationName("NewsAnalyzer") # Or your actual app name
        self.settings = QSettings(QSettings.IniFormat, QSettings.UserScope,
                                  QApplication.organizationName(), QApplication.applicationName())
        # --- End Use INI format ---

        self.logger.info(f"QSettings format: {self.settings.format()}")
        self.logger.info(f"QSettings scope: {self.settings.scope()}")
        self.logger.info(f"QSettings organization: {self.settings.organizationName()}")
        self.logger.info(f"QSettings application: {self.settings.applicationName()}")
        self.logger.info(f"QSettings backend status on init: {self.settings.status()}")
        self.logger.info(f"QSettings file path on init: {self.settings.fileName()}")

        self.available_themes = self._find_themes()


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


    def get_available_themes(self) -> List[str]:
        """获取可用主题名称的列表。"""
        # Ensure themes are found, maybe re-scan if needed, though usually done at init
        if not self.available_themes:
             self.logger.warning("get_available_themes called but no themes were found initially. Re-scanning.")
             self.available_themes = self._find_themes()
        return self.available_themes

    def load_theme_stylesheet(self, theme_name: str) -> Optional[str]:
        """
        加载指定主题名称的 QSS 文件内容。

        Args:
            theme_name: 主题名称 (不含 .qss 后缀)。

        Returns:
            QSS 样式表内容的字符串，如果失败则返回 None。
        """
        self.logger.debug(f"ThemeManager: 尝试加载主题样式表: {theme_name}") # Added log
        if theme_name not in self.available_themes:
            self.logger.warning(f"尝试加载不存在或不允许的主题: {theme_name}. 可用主题: {self.available_themes}") # Log available themes
            return None

        file_path = os.path.join(self.themes_dir, f"{theme_name}.qss")
        self.logger.debug(f"ThemeManager: Reading stylesheet from: {file_path}") # Log file path
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                stylesheet = f.read()
                self.logger.info(f"成功加载主题 '{theme_name}' 的样式表 (长度: {len(stylesheet)}).") # Updated log
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


    def apply_theme(self, theme_name: str) -> bool:
        """
        加载并应用指定的主题到整个应用程序。

        Args:
            theme_name: 要应用的主题名称。

        Returns:
            True 如果主题成功应用，否则 False。
        """
        self.logger.info(f"ThemeManager: 尝试应用主题: {theme_name}") # Added log
        stylesheet = self.load_theme_stylesheet(theme_name)
        if stylesheet is not None:
            try:
                app = QApplication.instance()
                if app:
                    self.logger.debug(f"ThemeManager: 获取到 QApplication 实例，准备调用 setStyleSheet 应用主题 '{theme_name}'...") # Added log
                    app.setStyleSheet(stylesheet)
                    # Check if stylesheet was actually applied (basic check)
                    if app.styleSheet(): # Check if stylesheet is not empty after setting
                         self.logger.debug(f"ThemeManager: setStyleSheet 调用完成，样式表已设置。") # Updated log
                    else:
                         self.logger.warning(f"ThemeManager: setStyleSheet 调用后，样式表为空！主题 '{theme_name}' 可能未正确应用。")

                    # Don't save here, save should happen explicitly in settings dialog or on exit
                    # self.save_current_theme(theme_name) # 应用成功后保存
                    self.logger.info(f"已应用主题: {theme_name}")
                    return True
                else:
                    self.logger.error("无法获取 QApplication 实例来应用样式表。")
                    return False
            except Exception as e:
                self.logger.error(f"应用样式表时出错: {e}", exc_info=True)
                return False
        else:
            self.logger.error(f"无法应用主题 '{theme_name}'，因为加载样式表失败。")
            return False

    def get_current_theme(self) -> str:
        """获取当前保存的主题名称。"""
        self.logger.debug(f"ThemeManager: 尝试从设置获取主题 (Key: {self.SETTINGS_KEY})...") # Added log
        # --- Log value before validation ---
        raw_saved_theme = self.settings.value(self.SETTINGS_KEY, defaultValue=None)
        self.logger.debug(f"ThemeManager: Raw value read from settings for key '{self.SETTINGS_KEY}': {raw_saved_theme} (Type: {type(raw_saved_theme)})")
        # --- End log ---
        if raw_saved_theme is None:
            self.logger.info(f"未在设置中找到主题 (Key: {self.SETTINGS_KEY})，将使用默认主题: {self.DEFAULT_THEME}")
            return self.DEFAULT_THEME
        else:
            saved_theme_str = str(raw_saved_theme) # Ensure it's a string
            self.logger.info(f"从设置中获取到已保存主题: {saved_theme_str} (Key: {self.SETTINGS_KEY})")
            # Validate if the saved theme is still available
            if saved_theme_str not in self.available_themes:
                 self.logger.warning(f"已保存的主题 '{saved_theme_str}' 不再可用 (可用: {self.available_themes})，将使用默认主题: {self.DEFAULT_THEME}")
                 return self.DEFAULT_THEME
            return saved_theme_str


    def save_current_theme(self, theme_name: str):
        """保存当前选中的主题名称到设置。"""
        self.logger.info(f"ThemeManager: 尝试保存主题 '{theme_name}' 到设置 (Key: {self.SETTINGS_KEY})...") # Added log
        if theme_name in self.available_themes:
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
        else:
            self.logger.warning(f"尝试保存无效或不可用的主题名称: {theme_name} (可用: {self.available_themes})")

    def apply_saved_theme(self) -> bool:
        """应用上次保存的主题，如果未保存则应用默认主题。"""
        theme_to_apply = self.get_current_theme() # get_current_theme now handles validation and default fallback
        self.logger.info(f"ThemeManager: 尝试应用保存的/默认的主题: {theme_to_apply}") # Updated log
        return self.apply_theme(theme_to_apply)

# --- 用于独立测试 ThemeManager ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    # 假设在项目根目录下运行此脚本进行测试
    # 需要调整 themes_dir 的路径
    test_themes_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'src', 'themes')
    print(f"测试时使用的 themes_dir: {test_themes_dir}")

    # 创建一个虚拟的 QApplication 用于测试
    app = QApplication([])
    # Set org/app name for QSettings INI format test
    QApplication.setOrganizationName("TestCompany")
    QApplication.setApplicationName("TestApp")


    manager = ThemeManager(themes_dir=test_themes_dir)

    print("可用主题:", manager.get_available_themes())

    # 尝试应用默认主题 (现在是 dark)
    print("\n应用默认主题...")
    if manager.apply_theme(manager.DEFAULT_THEME):
        print("默认主题应用成功。")
        print("当前样式表:\n", app.styleSheet()[:200] + "...") # 打印部分样式
    else:
        print("默认主题应用失败。")

    # 模拟保存和加载
    manager.save_current_theme("light") # Save light theme
    print("\n当前保存的主题:", manager.get_current_theme()) # Should print light

    print("\n尝试应用保存的主题...")
    if manager.apply_saved_theme(): # Should apply light
         print("保存的主题应用成功。")
         print("当前样式表:\n", app.styleSheet()[:200] + "...") # 打印部分样式
    else:
         print("保存的主题应用失败。")

    # 清理设置（可选）
    settings = QSettings(QSettings.IniFormat, QSettings.UserScope, "TestCompany", "TestApp")
    settings.remove(ThemeManager.SETTINGS_KEY)
    print("\n测试设置已清理。")
    print("现在获取当前主题应为默认:", manager.get_current_theme()) # Should now be dark again