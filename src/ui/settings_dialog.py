# src/ui/settings_dialog.py
import logging
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLabel, QComboBox, QSlider, QPushButton, QDialogButtonBox,
                             QWidget, QSpinBox, QMessageBox) # Import QMessageBox
from PyQt5.QtCore import Qt, pyqtSignal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .theme_manager import ThemeManager
    from .ui_settings_manager import UISettingsManager

class SettingsDialog(QDialog):
    """应用程序设置对话框"""

    # Signal emitted when settings that require immediate UI update are applied
    settings_applied = pyqtSignal()

    def __init__(self, theme_manager: 'ThemeManager', ui_settings_manager: 'UISettingsManager', parent=None):
        super().__init__(parent)
        self.setWindowTitle("应用程序设置")
        self.setMinimumWidth(400)

        self.logger = logging.getLogger(__name__)
        self.theme_manager = theme_manager
        self.ui_settings_manager = ui_settings_manager

        # Store initial values to check for changes before closing on Cancel/Reject
        self.initial_theme = self.theme_manager.get_current_theme()
        self.initial_font_size = self.ui_settings_manager.get_current_font_size()

        self._init_ui()
        self._load_current_settings()

    def _init_ui(self):
        """初始化 UI 元素"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # --- 外观设置 ---
        appearance_group = QWidget() # Use QWidget as a container
        form_layout = QFormLayout(appearance_group)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow) # Allow fields to expand

        # 主题选择
        self.theme_combo = QComboBox()
        available_themes = self.theme_manager.get_available_themes()
        # Only add allowed themes (light/dark)
        allowed_themes = {"light", "dark"}
        display_map = {"light": "白天模式", "dark": "黑暗模式"}
        for theme in available_themes:
            if theme in allowed_themes:
                 self.theme_combo.addItem(display_map.get(theme, theme.capitalize()), theme) # Display name, store actual name
        # No need to connect signal for Apply button anymore
        form_layout.addRow("界面主题:", self.theme_combo)

        # 字体大小调整
        font_layout = QHBoxLayout()
        font_layout.setSpacing(10)
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(self.ui_settings_manager.MIN_FONT_SIZE, self.ui_settings_manager.MAX_FONT_SIZE)
        self.font_slider.setTickPosition(QSlider.TicksBelow)
        self.font_slider.setTickInterval(1)
        self.font_slider.valueChanged.connect(self._update_font_label)
        # No need to connect signal for Apply button anymore

        self.font_size_label = QLabel() # Label to display current size
        self.font_size_label.setMinimumWidth(30) # Ensure space for "XX pt"
        self.font_size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        reset_font_button = QPushButton("重置")
        reset_font_button.setToolTip("恢复默认字体大小")
        reset_font_button.clicked.connect(self._reset_font_size)

        font_layout.addWidget(self.font_slider, 1) # Slider takes most space
        font_layout.addWidget(self.font_size_label)
        font_layout.addWidget(reset_font_button)

        form_layout.addRow("字体大小:", font_layout)

        layout.addWidget(appearance_group)
        layout.addStretch() # Push buttons to the bottom

        # --- 标准按钮 (移除 Apply) ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel) # Removed Apply
        # --- Set Chinese Text ---
        self.button_box.button(QDialogButtonBox.Ok).setText("确定")
        self.button_box.button(QDialogButtonBox.Cancel).setText("取消")
        # --- End Set Text ---
        self.button_box.accepted.connect(self.accept) # OK triggers accept
        self.button_box.rejected.connect(self.reject) # Cancel triggers reject

        layout.addWidget(self.button_box)

    def _load_current_settings(self):
        """加载当前设置并更新 UI 控件"""
        # 主题
        current_theme = self.theme_manager.get_current_theme()
        index = self.theme_combo.findData(current_theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        else:
            self.logger.warning(f"无法在下拉框中找到当前主题: {current_theme}")

        # 字体大小
        current_size = self.ui_settings_manager.get_current_font_size()
        self.font_slider.setValue(current_size)
        self._update_font_label(current_size) # Update label initially

    def _update_font_label(self, value):
        """更新显示字体大小的标签"""
        self.font_size_label.setText(f"{value} pt")

    def _reset_font_size(self):
        """将字体大小滑块和标签重置为默认值"""
        default_size = self.ui_settings_manager.DEFAULT_FONT_SIZE
        self.font_slider.setValue(default_size)
        # OK button will handle saving if different from initial

    # Removed _mark_settings_changed method

    def _save_settings(self):
        """保存并应用当前选中的设置"""
        self.logger.info("保存并应用设置...")
        font_changed = False
        theme_changed = False
        font_applied_now = False
        theme_applied_now = False
        apply_success = False # Track theme application success

        # 保存并应用字体大小
        new_font_size = self.font_slider.value()
        # Compare with the font size when the dialog was opened
        if new_font_size != self.initial_font_size:
            self.logger.debug(f"字体大小已更改，应用新字体大小: {new_font_size}pt")
            # Calculate delta based on the *current* actual font size
            delta = new_font_size - self.ui_settings_manager.get_current_font_size()
            if delta != 0:
                self.ui_settings_manager.adjust_font_size(delta) # This saves and applies
                font_changed = True
                font_applied_now = True
        else:
            self.logger.debug("字体大小与打开时相同，跳过保存。")


        # 保存并应用主题
        new_theme_index = self.theme_combo.currentIndex()
        new_theme = self.theme_combo.itemData(new_theme_index)
        # Compare with the theme when the dialog was opened
        if new_theme != self.initial_theme:
            self.logger.debug(f"主题已更改，保存并应用新主题: {new_theme}")
            self.theme_manager.save_current_theme(new_theme) # Save setting first
            apply_success = self.theme_manager.apply_theme(new_theme) # Apply immediately
            if apply_success:
                theme_changed = True
                theme_applied_now = True
                self.logger.info(f"主题 '{new_theme}' 已成功应用。")
            else:
                self.logger.error(f"应用主题 '{new_theme}' 失败！")
                QMessageBox.warning(self, "主题错误", f"无法应用主题 '{self.theme_combo.currentText()}'。")
                # Revert combo box selection to the initial theme
                index = self.theme_combo.findData(self.initial_theme)
                if index >= 0:
                    self.theme_combo.setCurrentIndex(index)
                # Also revert the saved setting if application failed
                self.theme_manager.save_current_theme(self.initial_theme)

            # QMessageBox.information(self, "主题已更改", f"主题已设置为 {self.theme_combo.currentText()}。\n更改将在下次启动应用程序时生效。") # Removed message
        else:
             self.logger.debug("主题与打开时相同，跳过保存。")

        if font_applied_now or theme_applied_now: # Emit if font or theme was applied now
            self.settings_applied.emit()

        # Update initial values only if changes were successfully applied
        if font_changed:
            self.initial_font_size = new_font_size
        if theme_changed and apply_success:
            self.initial_theme = new_theme

        self.logger.info("设置保存/应用完成。")
        return font_changed or theme_changed # Return if any setting was actually saved/applied


    def accept(self):
        """点击确定时，保存/应用设置并关闭对话框"""
        self.logger.debug("确定按钮点击")
        self._save_settings() # Save and apply changes before closing
        super().accept()

    def reject(self):
        """点击取消或关闭时，恢复初始设置（如果字体已应用）并关闭对话框"""
        self.logger.debug("取消按钮点击")
        # Check if font size is *currently* different from the initial state when dialog opened
        font_currently_different = self.ui_settings_manager.get_current_font_size() != self.initial_font_size

        if font_currently_different:
             self.logger.info("取消设置，恢复初始字体大小...")
             # Use adjust_font_size to revert
             delta = self.initial_font_size - self.ui_settings_manager.get_current_font_size()
             self.ui_settings_manager.adjust_font_size(delta)
             self.settings_applied.emit() # Emit signal to update UI if font reverted

        # Revert theme if it was changed and applied *during this dialog session*
        theme_currently_different = self.theme_manager.get_current_theme() != self.initial_theme
        if theme_currently_different:
             self.logger.info("取消设置，恢复初始主题...")
             # Apply the initial theme back
             apply_revert_success = self.theme_manager.apply_theme(self.initial_theme)
             if apply_revert_success:
                 # Also save the reverted theme setting
                 self.theme_manager.save_current_theme(self.initial_theme)
                 self.settings_applied.emit() # Emit signal to update UI
             else:
                 self.logger.error(f"恢复初始主题 '{self.initial_theme}' 失败！")
                 QMessageBox.warning(self, "主题错误", f"无法恢复到初始主题 '{self.initial_theme}'。")


        super().reject()

# --- 用于独立测试 ---
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication

    logging.basicConfig(level=logging.DEBUG)

    # 创建模拟的 Manager 对象
    class MockThemeManager:
        _current_theme = "light"
        def get_available_themes(self): return ["light", "dark", "default"]
        def get_current_theme(self): return self._current_theme
        def save_current_theme(self, name): print(f"MockThemeManager: Saving theme {name}"); self._current_theme = name
        def apply_theme(self, name): print(f"MockThemeManager: Applying theme {name}"); return True

    class MockUISettingsManager:
        MIN_FONT_SIZE = 8
        MAX_FONT_SIZE = 20
        DEFAULT_FONT_SIZE = 13
        _current_size = 12
        def get_current_font_size(self): return self._current_size
        # Simulate adjust_font_size behavior
        def adjust_font_size(self, delta):
            new_size = max(self.MIN_FONT_SIZE, min(self.MAX_FONT_SIZE, self._current_size + delta))
            print(f"MockUISettingsManager: Adjusting font size by {delta} to {new_size}")
            self._current_size = new_size
        def increase_font(self): self.adjust_font_size(1)
        def decrease_font(self): self.adjust_font_size(-1)
        def reset_font(self): print("MockUISettingsManager: Resetting font"); self._current_size = self.DEFAULT_FONT_SIZE

    app = QApplication(sys.argv)
    mock_theme = MockThemeManager()
    mock_ui = MockUISettingsManager()
    dialog = SettingsDialog(mock_theme, mock_ui)
    dialog.show()
    sys.exit(app.exec_())