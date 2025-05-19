import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLabel, QLineEdit, QToolButton, QPushButton, QDialogButtonBox,
                             QWidget, QCheckBox, QMessageBox, QApplication)
from PySide6.QtCore import Qt, Signal as pyqtSignal, QEvent, QObject
from PySide6.QtGui import QIntValidator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.scheduler_service import SchedulerService

class AutomationSettingsDialog(QDialog):
    """自动化设置对话框 (使用自定义控件替代SpinBox)"""
    # Constants for ranges
    MIN_HOURS, MAX_HOURS = 0, 48
    MIN_MINUTES, MAX_MINUTES = 0, 59
    MIN_TOTAL_INTERVAL_MINUTES = 5

    def __init__(self, scheduler_service: 'SchedulerService', parent=None):
        super().__init__(parent)
        self.setWindowTitle("自动化设置")
        self.setMinimumWidth(400)
        self.logger = logging.getLogger(__name__)
        self.scheduler_service = scheduler_service
        self.initial_scheduler_enabled, self.initial_scheduler_interval = self.scheduler_service.get_schedule_config()
        self.logger.debug(f"Initial scheduler settings: enabled={self.initial_scheduler_enabled}, interval={self.initial_scheduler_interval} min")
        self._init_ui()
        self._load_current_settings()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        refresh_label = QLabel("<b>新闻自动刷新</b>")
        refresh_group = QWidget()
        refresh_form_layout = QFormLayout(refresh_group)
        refresh_form_layout.setSpacing(10)
        refresh_form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.scheduler_enabled_check = QCheckBox("启用后台自动刷新新闻源")
        self.scheduler_enabled_check.toggled.connect(self._toggle_interval_controls_enabled)
        refresh_form_layout.addRow(self.scheduler_enabled_check)

        self.interval_label = QLabel("刷新间隔:")
        
        interval_spin_container = QWidget()
        interval_spin_layout = QHBoxLayout(interval_spin_container)
        interval_spin_layout.setContentsMargins(0, 0, 0, 0)
        interval_spin_layout.setSpacing(2) # Reduced spacing for tighter look

        # --- Custom Hours Control --- 
        self.hours_decrement_button = QToolButton()
        self.hours_decrement_button.setObjectName("AutomationHoursDecrement")
        self.hours_decrement_button.setText("-")
        self.hours_decrement_button.setAutoRepeat(True) # Allow holding
        self.hours_decrement_button.setFixedSize(24, 24) # Adjust size as needed
        self.hours_decrement_button.clicked.connect(self._decrement_hours)
        
        self.hours_display = QLineEdit()
        self.hours_display.setObjectName("AutomationHoursDisplay")
        self.hours_display.setValidator(QIntValidator(self.MIN_HOURS, self.MAX_HOURS, self))
        self.hours_display.setAlignment(Qt.AlignCenter)
        self.hours_display.setFixedWidth(55) # Increased width from 40 to 55
        self.hours_display.textChanged.connect(self._validate_min_interval_from_text) # Validate on text change too
        
        self.hours_increment_button = QToolButton()
        self.hours_increment_button.setObjectName("AutomationHoursIncrement")
        self.hours_increment_button.setText("+")
        self.hours_increment_button.setAutoRepeat(True)
        self.hours_increment_button.setFixedSize(24, 24)
        self.hours_increment_button.clicked.connect(self._increment_hours)
        
        hours_label = QLabel("小时")

        # --- Custom Minutes Control --- 
        self.minutes_decrement_button = QToolButton()
        self.minutes_decrement_button.setObjectName("AutomationMinutesDecrement")
        self.minutes_decrement_button.setText("-")
        self.minutes_decrement_button.setAutoRepeat(True)
        self.minutes_decrement_button.setFixedSize(24, 24)
        self.minutes_decrement_button.clicked.connect(self._decrement_minutes)
        
        self.minutes_display = QLineEdit()
        self.minutes_display.setObjectName("AutomationMinutesDisplay")
        self.minutes_display.setValidator(QIntValidator(self.MIN_MINUTES, self.MAX_MINUTES, self))
        self.minutes_display.setAlignment(Qt.AlignCenter)
        self.minutes_display.setFixedWidth(55) # Increased width from 40 to 55
        self.minutes_display.textChanged.connect(self._validate_min_interval_from_text)
        
        self.minutes_increment_button = QToolButton()
        self.minutes_increment_button.setObjectName("AutomationMinutesIncrement")
        self.minutes_increment_button.setText("+")
        self.minutes_increment_button.setAutoRepeat(True)
        self.minutes_increment_button.setFixedSize(24, 24)
        self.minutes_increment_button.clicked.connect(self._increment_minutes)
        
        minutes_label = QLabel("分钟")
        
        # --- Add custom controls to layout --- 
        interval_spin_layout.addWidget(self.hours_decrement_button)
        interval_spin_layout.addWidget(self.hours_display)
        interval_spin_layout.addWidget(self.hours_increment_button)
        interval_spin_layout.addWidget(hours_label)
        interval_spin_layout.addSpacing(15) # Spacing between hours and minutes
        interval_spin_layout.addWidget(self.minutes_decrement_button)
        interval_spin_layout.addWidget(self.minutes_display)
        interval_spin_layout.addWidget(self.minutes_increment_button)
        interval_spin_layout.addWidget(minutes_label)
        interval_spin_layout.addStretch()
        
        refresh_form_layout.addRow(self.interval_label, interval_spin_container)

        main_layout.addWidget(refresh_label)
        main_layout.addWidget(refresh_group)
        main_layout.addStretch()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.button(QDialogButtonBox.Ok).setText("确定")
        self.button_box.button(QDialogButtonBox.Cancel).setText("取消")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    # --- Handler Methods for Custom Controls --- 
    def _increment_hours(self):
        try:
            current_val = int(self.hours_display.text() or '0')
            new_val = min(current_val + 1, self.MAX_HOURS)
            self.hours_display.setText(str(new_val))
            # textChanged signal will trigger validation
        except ValueError: pass # Ignore if text is invalid

    def _decrement_hours(self):
        try:
            current_val = int(self.hours_display.text() or '0')
            new_val = max(current_val - 1, self.MIN_HOURS)
            self.hours_display.setText(str(new_val))
        except ValueError: pass
        
    def _increment_minutes(self):
        try:
            current_val = int(self.minutes_display.text() or '0')
            new_val = min(current_val + 1, self.MAX_MINUTES)
            self.minutes_display.setText(str(new_val))
        except ValueError: pass

    def _decrement_minutes(self):
        try:
            current_val = int(self.minutes_display.text() or '0')
            new_val = max(current_val - 1, self.MIN_MINUTES)
            self.minutes_display.setText(str(new_val))
        except ValueError: pass

    def _toggle_interval_controls_enabled(self, checked):
        self.hours_decrement_button.setEnabled(checked)
        self.hours_display.setEnabled(checked)
        self.hours_increment_button.setEnabled(checked)
        self.minutes_decrement_button.setEnabled(checked)
        self.minutes_display.setEnabled(checked)
        self.minutes_increment_button.setEnabled(checked)
        self.interval_label.setEnabled(checked)
        if checked:
            self._validate_min_interval_from_text() # Validate when enabling

    # Renamed validation function to clarify it reads from text
    def _validate_min_interval_from_text(self):
        if not self.scheduler_enabled_check.isChecked():
            return
        try:
            hours = int(self.hours_display.text() or '0')
            minutes = int(self.minutes_display.text() or '0')
            total_minutes = (hours * 60) + minutes
        except ValueError:
            # Handle case where text might be temporarily invalid during typing
            # Or rely on QIntValidator to prevent non-integer input
            return 

        if hours == 0 and total_minutes < self.MIN_TOTAL_INTERVAL_MINUTES:
            if minutes < self.MIN_TOTAL_INTERVAL_MINUTES:
                # Correct the minutes display ONLY if it's currently below the minimum AND hours is 0
                # Avoid infinite loops by blocking signals during correction
                self.minutes_display.blockSignals(True)
                self.minutes_display.setText(str(self.MIN_TOTAL_INTERVAL_MINUTES))
                self.minutes_display.blockSignals(False)
        
    def _load_current_settings(self):
        enabled, interval_total_minutes = self.scheduler_service.get_schedule_config()
        self.scheduler_enabled_check.setChecked(enabled)
        hours = interval_total_minutes // 60
        minutes = interval_total_minutes % 60
        self.hours_display.setText(str(hours))
        self.minutes_display.setText(str(minutes))
        self._toggle_interval_controls_enabled(enabled)

    def _save_settings(self):
        new_enabled = self.scheduler_enabled_check.isChecked()
        try:
             hours = int(self.hours_display.text() or '0')
             minutes = int(self.minutes_display.text() or '0')
             # Ensure values are within logical range (validator should handle this, but double-check)
             hours = max(self.MIN_HOURS, min(hours, self.MAX_HOURS))
             minutes = max(self.MIN_MINUTES, min(minutes, self.MAX_MINUTES))
             self.hours_display.setText(str(hours)) # Update display if clamped
             self.minutes_display.setText(str(minutes))
        except ValueError:
             QMessageBox.warning(self, "输入错误", "刷新间隔的小时和分钟必须是有效的数字。")
             return False # Prevent closing dialog on bad input
             
        new_interval_minutes = (hours * 60) + minutes

        if new_enabled and new_interval_minutes < self.MIN_TOTAL_INTERVAL_MINUTES:
            # Validation should have already potentially corrected this, but double check before saving
            if hours == 0 and minutes < self.MIN_TOTAL_INTERVAL_MINUTES:
                 QMessageBox.warning(self, "间隔过短", f"自动刷新间隔 ({hours}小时{minutes}分钟) 低于最小允许的5分钟。\n将自动调整为0小时5分钟。")
                 new_interval_minutes = self.MIN_TOTAL_INTERVAL_MINUTES
                 hours = 0
                 minutes = self.MIN_TOTAL_INTERVAL_MINUTES
                 self.hours_display.setText(str(hours))
                 self.minutes_display.setText(str(minutes))
            elif hours > 0: 
                 # If hours > 0, the minimum interval is met, even if minutes is 0
                 pass 
            else: # Should not happen if validation worked, but catch potentially invalid state
                 QMessageBox.warning(self, "配置错误", "刷新间隔配置无效，请检查小时和分钟数。")
                 return False

        # Proceed with saving if settings changed
        if new_enabled != self.initial_scheduler_enabled or new_interval_minutes != self.initial_scheduler_interval:
            self.logger.info(f"Automation settings changed: enabled={new_enabled}, interval={new_interval_minutes} min. Updating scheduler.")
            try:
                self.scheduler_service.update_schedule(new_enabled, new_interval_minutes)
                self.initial_scheduler_enabled = new_enabled
                self.initial_scheduler_interval = new_interval_minutes
                self.logger.info("自动化调度器设置已成功更新并应用。")
                return True 
            except Exception as e:
                self.logger.error(f"更新调度器设置失败: {e}", exc_info=True)
                QMessageBox.critical(self, "调度器错误", f"无法更新自动刷新设置: {e}")
                return False 
        else:
            self.logger.debug("自动化设置未更改，跳过保存。")
            return True 

    def accept(self):
        if self._save_settings():
            super().accept()

    def reject(self):
        self.logger.debug("Automation settings dialog cancelled by user.")
        super().reject()

# Example usage (for testing this dialog standalone - not part of the main app flow)
if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication

    class MockSchedulerService:
        _enabled = True
        _interval = 75 # 1 hour 15 minutes

        def get_schedule_config(self):
            print(f"MOCK: Getting schedule: enabled={self._enabled}, interval={self._interval}")
            return self._enabled, self._interval

        def update_schedule(self, enabled, interval):
            print(f"MOCK: Updating schedule: enabled={enabled}, interval={interval}")
            self._enabled = enabled
            self._interval = interval
            print("MOCK: Schedule updated.")

    logging.basicConfig(level=logging.DEBUG)
    app = QApplication(sys.argv)
    
    mock_scheduler = MockSchedulerService()
    
    dialog = AutomationSettingsDialog(scheduler_service=mock_scheduler)
    if dialog.exec() == QDialog.Accepted:
        print("Automation Settings Accepted.")
    else:
        print("Automation Settings Cancelled.")
    
    # Check final mock values
    print(f"Final mock schedule: enabled={mock_scheduler._enabled}, interval={mock_scheduler._interval}")
    
    sys.exit() 