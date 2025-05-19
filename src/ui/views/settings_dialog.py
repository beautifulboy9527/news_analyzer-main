# src/ui/views/settings_dialog.py
import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLabel, QComboBox, QSlider, QPushButton, QDialogButtonBox,
                             QWidget, QSpinBox, QMessageBox, QCheckBox) # Use PySide6
from PySide6.QtCore import Qt, Signal as pyqtSignal # Use PySide6, alias Signal
from typing import TYPE_CHECKING

# Adjust relative imports for moving from src/ui/ to src/ui/views/
if TYPE_CHECKING:
    from ..theme_manager import ThemeManager
    from ..ui_settings_manager import UISettingsManager
    from src.services.scheduler_service import SchedulerService # Keep absolute for different root dir

class SettingsDialog(QDialog):
    """应用程序设置对话框"""

    # Signal emitted when settings that require immediate UI update are applied
    settings_applied = pyqtSignal()

    def __init__(self, theme_manager: 'ThemeManager', ui_settings_manager: 'UISettingsManager', scheduler_service: 'SchedulerService', parent=None):
        super().__init__(parent)
        self.setWindowTitle("应用程序设置")
        self.setMinimumWidth(450) # Increased width slightly

        self.logger = logging.getLogger(__name__) # Keep standard logger name
        self.theme_manager = theme_manager
        self.ui_settings_manager = ui_settings_manager
        self.scheduler_service = scheduler_service # Store the service

        # Store initial values to check for changes before closing on Cancel/Reject
        self.initial_theme = self.theme_manager.get_current_theme()
        self.initial_font_size = self.ui_settings_manager.get_current_font_size()
        # --- Store initial scheduler settings ---
        # self.initial_scheduler_enabled, self.initial_scheduler_interval = self.scheduler_service.get_schedule_config()
        # self.logger.debug(f"Initial scheduler settings: enabled={self.initial_scheduler_enabled}, interval={self.initial_scheduler_interval}")
        # --- End store initial --- 

        self._init_ui()
        self._load_current_settings()

    def _init_ui(self):
        """初始化 UI 元素"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20) # Increased spacing

        # --- 外观设置 ---
        appearance_label = QLabel("<b>外观设置</b>")
        appearance_group = QWidget() # Use QWidget as a container
        form_layout = QFormLayout(appearance_group)
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
        self.font_size_label.setMinimumWidth(40) # Ensure space for "XX pt"
        self.font_size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        reset_font_button = QPushButton("重置")
        reset_font_button.setToolTip("恢复默认字体大小")
        reset_font_button.clicked.connect(self._reset_font_size)

        font_layout.addWidget(self.font_slider, 1) # Slider takes most space
        font_layout.addWidget(self.font_size_label)
        font_layout.addWidget(reset_font_button)

        form_layout.addRow("字体大小:", font_layout)

        main_layout.addWidget(appearance_label)
        main_layout.addWidget(appearance_group)

        # --- 自动刷新设置 --- (SECTION TO BE REMOVED)
        # refresh_label = QLabel("<b>自动刷新</b>")
        # refresh_group = QWidget()
        # refresh_form_layout = QFormLayout(refresh_group)
        # refresh_form_layout.setSpacing(10)
        # refresh_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        # 
        # self.scheduler_enabled_check = QCheckBox("启用后台自动刷新新闻源")
        # self.scheduler_enabled_check.toggled.connect(self._toggle_interval_controls_enabled)
        # refresh_form_layout.addRow(self.scheduler_enabled_check)
        # 
        # self.interval_label = QLabel("刷新间隔:")
        # self.scheduler_hours_spin = QSpinBox()
        # self.scheduler_hours_spin.setObjectName("SchedulerHoursSpin") 
        # self.scheduler_hours_spin.setRange(0, 48) 
        # self.scheduler_hours_spin.setSuffix(" 小时")
        # self.scheduler_hours_spin.setToolTip("设置自动刷新的小时数 (0-48 小时)")
        # 
        # spinbox_button_fix_style = """QSpinBox::up-button {width: 16px; height: 10px; border: 1px solid #888888; background-color: #dddddd; } QSpinBox::down-button {width: 16px; height: 10px; border: 1px solid #888888; background-color: #dddddd;}"""
        # self.scheduler_hours_spin.setStyleSheet(spinbox_button_fix_style)
        # self.logger.info("Applied direct QSS to scheduler_hours_spin for button functionality test.")
        # 
        # refresh_form_layout.addRow(self.interval_label, self.scheduler_hours_spin)
        # 
        # main_layout.addWidget(refresh_label)
        # main_layout.addWidget(refresh_group)
        # --- End 自动刷新设置 --- (SECTION TO BE REMOVED)

        main_layout.addStretch() # Push buttons to the bottom

        # --- 标准按钮 (移除 Apply) ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel) # Removed Apply
        # --- Set Chinese Text ---
        self.button_box.button(QDialogButtonBox.Ok).setText("确定")
        self.button_box.button(QDialogButtonBox.Cancel).setText("取消")
        # --- End Set Text ---
        self.button_box.accepted.connect(self.accept) # OK triggers accept
        self.button_box.rejected.connect(self.reject) # Cancel triggers reject

        main_layout.addWidget(self.button_box)

    def _load_current_settings(self):
        """加载当前设置并更新 UI 控件"""
        # self.logger.debug(f"SettingsDialog own stylesheet: {self.styleSheet()}")
        # self.logger.debug(f"SchedulerHoursSpin stylesheet: {self.scheduler_hours_spin.styleSheet()}")
        # # self.logger.debug(f"SchedulerMinutesSpin stylesheet: {self.scheduler_minutes_spin.styleSheet()}")

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

        # --- Load Scheduler Settings --- (SECTION TO BE REMOVED)
        # enabled, interval_minutes = self.scheduler_service.get_schedule_config()
        # self.scheduler_enabled_check.setChecked(enabled)
        # 
        # hours = interval_minutes // 60
        # # minutes = interval_minutes % 60 # Disabled
        # 
        # self.scheduler_hours_spin.setValue(hours)
        # # self.scheduler_minutes_spin.setValue(minutes) # Disabled
        # self._toggle_interval_controls_enabled(enabled) 
        # --- End Load Scheduler ---

        # --- TEMPORARILY DISABLE RE-POLISH STYLES --- 
        # for spin_box in [self.scheduler_hours_spin, self.scheduler_minutes_spin]:
        #     if spin_box and spin_box.style(): # Check if style object exists
        #         self.logger.debug(f"Re-polishing style for {spin_box.objectName()}")
        #         spin_box.style().unpolish(spin_box)
        #         spin_box.style().polish(spin_box)
        #         spin_box.update() # Explicitly request a repaint
        # --- END TEMPORARILY DISABLE RE-POLISH STYLES --- 

    def _update_font_label(self, value):
        """更新显示字体大小的标签"""
        self.font_size_label.setText(f"{value} pt")

    def _reset_font_size(self):
        """将字体大小滑块和标签重置为默认值"""
        default_size = self.ui_settings_manager.DEFAULT_FONT_SIZE
        self.font_slider.setValue(default_size)
        # OK button will handle saving if different from initial

    def _save_settings(self):
        """保存并应用当前选中的设置"""
        self.logger.info("保存并应用设置...")
        font_changed = False
        theme_changed = False
        scheduler_changed = False # Track scheduler changes
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

        # --- Save Scheduler Settings --- (SECTION TO BE REMOVED)
        # new_enabled = self.scheduler_enabled_check.isChecked()
        # 
        # hours = self.scheduler_hours_spin.value()
        # minutes = 0 
        # new_interval_minutes = (hours * 60) + minutes
        # 
        # if new_enabled and new_interval_minutes < 5 and hours == 0: 
        #     self.logger.warning(f"刷新间隔 ({new_interval_minutes}分钟) 低于最小允许值 (5分钟)。自动调整为5分钟。")
        #     new_interval_minutes = 5
        #     self.scheduler_hours_spin.setValue(new_interval_minutes // 60)
        # 
        # if new_enabled != self.initial_scheduler_enabled or new_interval_minutes != self.initial_scheduler_interval:
        #     self.logger.debug(f"调度器设置已更改: enabled={new_enabled}, interval={new_interval_minutes} min")
        #     try:
        #         self.scheduler_service.update_schedule(new_enabled, new_interval_minutes)
        #         scheduler_changed = True
        #         self.initial_scheduler_enabled = new_enabled
        #         self.initial_scheduler_interval = new_interval_minutes
        #         self.logger.info("调度器设置已成功更新并应用。")
        #     except Exception as e:
        #         self.logger.error(f"更新调度器设置失败: {e}", exc_info=True)
        #         QMessageBox.warning(self, "调度器错误", f"无法更新自动刷新设置: {e}")
        #         self.scheduler_enabled_check.setChecked(self.initial_scheduler_enabled)
        #         initial_hours = self.initial_scheduler_interval // 60
        #         self.scheduler_hours_spin.setValue(initial_hours)
        #         self._toggle_interval_controls_enabled(self.initial_scheduler_enabled)
        # else:
        #     self.logger.debug("调度器设置与打开时相同，跳过保存。")
        # --- End Save Scheduler ---

        # Emit signal if any setting was applied immediately
        if font_applied_now or theme_applied_now:
            self.settings_applied.emit()

        # Update initial values only if changes were successfully applied (theme handled internally)
        if font_changed:
            self.initial_font_size = new_font_size
        # Scheduler initial values updated above if change was successful
        if theme_changed and apply_success:
            self.initial_theme = new_theme

    def accept(self):
        """当用户点击 OK 时调用"""
        self._save_settings()
        super().accept()

    def reject(self):
        """当用户点击 Cancel 或关闭对话框时调用"""
        self.logger.info("设置更改已取消。恢复初始设置...")
        # Revert theme if it was changed and applied during the dialog session
        current_applied_theme = self.theme_manager.get_current_theme()
        if current_applied_theme != self.initial_theme:
            self.logger.debug(f"Reverting applied theme from '{current_applied_theme}' back to '{self.initial_theme}'")
            self.theme_manager.apply_theme(self.initial_theme)
            # Also revert the saved setting since we are canceling
            self.theme_manager.save_current_theme(self.initial_theme)
            self.settings_applied.emit() # Notify UI needs update

        # Revert font size if it was changed and applied
        current_applied_font_size = self.ui_settings_manager.get_current_font_size()
        if current_applied_font_size != self.initial_font_size:
            self.logger.debug(f"Reverting applied font size from {current_applied_font_size}pt back to {self.initial_font_size}pt")
            delta = self.initial_font_size - current_applied_font_size
            self.ui_settings_manager.adjust_font_size(delta) # This saves and applies
            self.settings_applied.emit() # Notify UI needs update

        # No need to explicitly revert scheduler settings here,
        # as `_save_settings` only updates `initial_scheduler_*` on success.
        # If the user changed scheduler settings and clicked Cancel, they weren't applied.

        super().reject()

# --- Mock Classes for Standalone Testing (Keep at the end) ---
if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QSettings

    logging.basicConfig(level=logging.DEBUG)

    class MockThemeManager:
        _current_theme = "light"
        _settings = QSettings("MockCompany", "MockApp")
        def get_available_themes(self): return ["light", "dark", "blue"]
        def get_current_theme(self): return self._settings.value("theme", "light")
        def save_current_theme(self, theme): self._settings.setValue("theme", theme)
        def apply_theme(self, theme): # Mock apply
            print(f"MOCK: Applying theme {theme}")
            self.save_current_theme(theme) # Simulate saving on apply
            return True # Assume success for mock

    class MockUISettingsManager:
        MIN_FONT_SIZE = 8
        MAX_FONT_SIZE = 20
        DEFAULT_FONT_SIZE = 13
        _current_size = 12
        font_size_changed = pyqtSignal(int)
        def __init__(self, settings):
            self._settings = settings
            self._current_size = int(self._settings.value("fontSize", self.DEFAULT_FONT_SIZE))
        def get_current_font_size(self): return self._current_size
        def adjust_font_size(self, delta):
            new_size = max(self.MIN_FONT_SIZE, min(self._current_size + delta, self.MAX_FONT_SIZE))
            if new_size != self._current_size:
                self._current_size = new_size
                self._settings.setValue("fontSize", self._current_size)
                print(f"MOCK: Font size set to {self._current_size}")
                self.font_size_changed.emit(self._current_size)
        def save_settings(self): pass # Handled in adjust_font_size

    class MockSchedulerService:
        _enabled = False
        _interval = 60
        def __init__(self, settings):
            self._settings = settings
            self._enabled = self._settings.value("scheduler/enabled", False, type=bool)
            self._interval = self._settings.value("scheduler/interval", 60, type=int)
        def get_schedule_config(self): return self._enabled, self._interval
        def update_schedule(self, enabled, interval):
            print(f"MOCK: Updating schedule to enabled={enabled}, interval={interval}")
            self._enabled = enabled
            self._interval = interval
            self._settings.setValue("scheduler/enabled", self._enabled)
            self._settings.setValue("scheduler/interval", self._interval)

    app = QApplication(sys.argv)
    settings = QSettings("MockCompany", "MockApp_SettingsTest")
    theme_mgr = MockThemeManager()
    ui_settings_mgr = MockUISettingsManager(settings)
    scheduler_svc = MockSchedulerService(settings)

    dialog = SettingsDialog(theme_mgr, ui_settings_mgr, scheduler_svc)
    result = dialog.exec()

    if result == QDialog.Accepted:
        print("Dialog accepted.")
        print(f"Final Theme: {settings.value('theme')}")
        print(f"Final Font Size: {settings.value('fontSize')}")
        # print(f"Final Scheduler Enabled: {settings.value('scheduler/enabled')}")
        # print(f"Final Scheduler Interval: {settings.value('scheduler/interval')}")
    else:
        print("Dialog cancelled.")
        # Check if settings reverted (should match initial if changed)
        print(f"Theme after cancel: {settings.value('theme')}")
        print(f"Font Size after cancel: {settings.value('fontSize')}")
        # print(f"Scheduler Enabled after cancel: {settings.value('scheduler/enabled')}")
        # print(f"Scheduler Interval after cancel: {settings.value('scheduler/interval')}")

    sys.exit() 