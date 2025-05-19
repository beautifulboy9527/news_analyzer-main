# src/ui/ui_settings_manager.py
import logging
from PySide6.QtWidgets import QApplication, QWidget # Use PySide6
from PySide6.QtGui import QFont # Use PySide6
from PySide6.QtCore import QSettings, QObject, Signal as pyqtSignal # Use PySide6, alias Signal

logger = logging.getLogger('news_analyzer.ui.settings_manager')

class UISettingsManager(QObject): # 继承 QObject
    """管理全局UI外观设置，如字体大小。"""
    font_size_changed = pyqtSignal(int) # 定义信号，传递新的字体大小

    SETTINGS_FONT_SIZE_KEY = "ui/font_size"
    DEFAULT_FONT_SIZE = 11 # 默认字体大小
    MIN_FONT_SIZE = 8
    MAX_FONT_SIZE = 20

    def __init__(self):
        super().__init__() # Call QObject constructor
        self.settings = QSettings("NewsAnalyzer", "NewsAggregator")
        self.current_font_size = self._load_font_size()
        logger.info(f"UISettingsManager initialized. Current font size: {self.current_font_size}pt")

    def _load_font_size(self) -> int:
        """从 QSettings 加载字体大小，如果未设置则返回默认值。"""
        try:
            size = self.settings.value(self.SETTINGS_FONT_SIZE_KEY, self.DEFAULT_FONT_SIZE, type=int)
            # 验证加载的大小是否在合理范围内
            if self.MIN_FONT_SIZE <= size <= self.MAX_FONT_SIZE:
                 logger.debug(f"Loaded font size from settings: {size}pt")
                 return size
            else:
                 logger.warning(f"Loaded font size {size}pt is out of range [{self.MIN_FONT_SIZE}-{self.MAX_FONT_SIZE}]. Using default: {self.DEFAULT_FONT_SIZE}pt")
                 # 可以选择重置设置中的无效值
                 # self.settings.setValue(self.SETTINGS_FONT_SIZE_KEY, self.DEFAULT_FONT_SIZE)
                 return self.DEFAULT_FONT_SIZE
        except Exception as e:
            logger.error(f"Error loading font size from settings: {e}. Using default.", exc_info=True)
            return self.DEFAULT_FONT_SIZE


    def _save_font_size(self, size: int):
        """将字体大小保存到 QSettings。"""
        if self.MIN_FONT_SIZE <= size <= self.MAX_FONT_SIZE:
            self.settings.setValue(self.SETTINGS_FONT_SIZE_KEY, size)
            logger.debug(f"Saved font size to settings: {size}pt")
        else:
             logger.warning(f"Attempted to save invalid font size: {size}pt")

    def get_current_font_size(self) -> int:
        """获取当前管理的字体大小。"""
        return self.current_font_size

    def adjust_font_size(self, delta: int):
        """
        调整应用程序全局字体大小。

        Args:
            delta: 字体大小的变化量 (+1, -1, etc.)。
        """
        app = QApplication.instance()
        if not app:
            logger.error("Cannot adjust font size: QApplication instance not found.")
            return

        # 使用当前管理的字体大小计算新大小
        new_size = self.current_font_size + delta
        new_size = max(self.MIN_FONT_SIZE, min(new_size, self.MAX_FONT_SIZE)) # 限制范围

        if new_size != self.current_font_size:
            old_size = self.current_font_size
            self.current_font_size = new_size # 更新内部状态
            logger.info(f"Attempting to set global font size to: {new_size}pt")
            self._apply_font_size(new_size)
            self._save_font_size(new_size) # 保存新设置
            self.font_size_changed.emit(new_size) # 发射信号
            logger.debug(f"Emitted font_size_changed signal with size: {new_size}pt")

    def _apply_font_size(self, size: int):
        """将指定的字体大小应用到应用程序。"""
        app = QApplication.instance()
        if not app:
            logger.error("Cannot apply font size: QApplication instance not found.")
            return

        current_app_font = app.font()
        if current_app_font.pointSize() == size:
             logger.debug(f"Global font size is already {size}pt. No change needed.")
             return

        new_font = QFont(current_app_font)
        new_font.setPointSize(size)
        app.setFont(new_font) # 设置全局默认字体

        # 尝试更新所有顶级窗口及其子控件的字体
        # 这有助于确保更改立即生效，尤其是在某些样式下
        logger.debug(f"Propagating font size {size}pt to all top-level widgets.")
        for widget in QApplication.topLevelWidgets():
            try:
                widget.setFont(new_font)
                # 递归更新子控件可能过于激进且有性能影响，
                # 通常设置 QApplication 字体后，新创建的控件会继承，
                # 但现有控件可能需要手动更新或依赖样式表刷新。
                # 简单的强制刷新方法（可能影响性能）：
                # widget.style().unpolish(widget)
                # widget.style().polish(widget)
                # widget.update()
            except Exception as e:
                 logger.warning(f"Could not set font for widget {widget}: {e}")

        logger.info(f"Global font size set to: {size}pt")


    def increase_font(self):
        """增大字体。"""
        self.adjust_font_size(1)

    def decrease_font(self):
        """减小字体。"""
        self.adjust_font_size(-1)

    def reset_font(self):
        """重置字体大小为默认值。"""
        if self.current_font_size != self.DEFAULT_FONT_SIZE:
            logger.info(f"Resetting font size to default: {self.DEFAULT_FONT_SIZE}pt")
            self.current_font_size = self.DEFAULT_FONT_SIZE # 更新内部状态
            self._apply_font_size(self.DEFAULT_FONT_SIZE)
            self._save_font_size(self.DEFAULT_FONT_SIZE) # 保存设置
            self.font_size_changed.emit(self.DEFAULT_FONT_SIZE) # 发射信号
        else:
            logger.debug("Font size is already at default. No reset needed.")


    def apply_saved_font_size(self):
        """应用保存在设置中的字体大小。"""
        size_to_apply = self._load_font_size()
        self._apply_font_size(size_to_apply)
        # 确保内部状态与应用的状态一致
        self.current_font_size = size_to_apply

# --- 示例用法 (用于独立测试此模块) ---
if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG)

    # 创建一个虚拟的 QApplication 用于测试
    app = QApplication(sys.argv)

    # 创建一个简单的窗口用于测试字体变化
    test_window = QWidget()
    test_window.setWindowTitle("Font Test Window")
    test_window.setGeometry(100, 100, 300, 200)
    from PyQt5.QtWidgets import QLabel, QVBoxLayout
    layout = QVBoxLayout(test_window)
    label = QLabel("这是测试文本 This is test text.", test_window)
    layout.addWidget(label)
    test_window.show()


    manager = UISettingsManager()
    print(f"Initial loaded font size: {manager.get_current_font_size()}pt")
    print(f"Initial App font size: {QApplication.instance().font().pointSize()}pt")

    # 应用保存的字体（通常在程序启动时调用）
    print("\nApplying saved font size...")
    manager.apply_saved_font_size()
    print(f"App font size after apply_saved_font_size: {QApplication.instance().font().pointSize()}pt")
    print(f"Label font size: {label.font().pointSize()}pt") # 标签字体可能不会立即更新，除非强制刷新

    # 增大字体
    print("\nIncreasing font size...")
    manager.increase_font()
    print(f"Current manager font size: {manager.get_current_font_size()}pt")
    print(f"App font size after increase: {QApplication.instance().font().pointSize()}pt")
    # 强制更新标签字体以查看效果
    label.setFont(QApplication.instance().font())
    print(f"Label font size after increase: {label.font().pointSize()}pt")


    # 减小字体
    print("\nDecreasing font size...")
    manager.decrease_font()
    print(f"Current manager font size: {manager.get_current_font_size()}pt")
    print(f"App font size after decrease: {QApplication.instance().font().pointSize()}pt")
    label.setFont(QApplication.instance().font())
    print(f"Label font size after decrease: {label.font().pointSize()}pt")

    # 重置字体
    print("\nResetting font size...")
    manager.reset_font()
    print(f"Current manager font size: {manager.get_current_font_size()}pt")
    print(f"App font size after reset: {QApplication.instance().font().pointSize()}pt")
    label.setFont(QApplication.instance().font())
    print(f"Label font size after reset: {label.font().pointSize()}pt")


    # 再次加载（验证保存）
    print("\nRe-initializing manager to check saved settings...")
    manager2 = UISettingsManager()
    print(f"Font size loaded by new manager: {manager2.get_current_font_size()}pt")

    # 清理设置（可选）
    # settings = QSettings("NewsAnalyzer", "NewsAggregator")
    # settings.remove(UISettingsManager.SETTINGS_FONT_SIZE_KEY)
    # print("\nTest settings cleared.")

    sys.exit(app.exec_()) # 启动事件循环以显示窗口