#!/usr/bin/env python
# -*- coding: utf-8 -*-

\"\"\"
自定义日期范围选择器组件
\"\"\"

import logging
from datetime import date, datetime # Ensure datetime is imported
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QPushButton, QDialog,
                             QVBoxLayout, QCalendarWidget, QDialogButtonBox, QSpacerItem, QSizePolicy)
from PySide6.QtCore import Qt, Signal, Slot, QDate

class CustomCalendarDialog(QDialog):
    \"\"\"自定义日历选择对话框，用于选择单个日期\"\"\"
    dateSelected = Signal(QDate)

    def __init__(self, initial_date=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择日期")
        self.setMinimumWidth(350) # Adjust as needed
        self.logger = logging.getLogger(__name__)

        layout = QVBoxLayout(self)

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True) # Keep grid visible
        if initial_date:
            self.calendar.setSelectedDate(initial_date)
        else:
             self.calendar.setSelectedDate(QDate.currentDate())

        # --- Apply basic styling directly for now, move to QSS later ---
        # self.calendar.setStyleSheet(\"\"\"
        #     QCalendarWidget QAbstractItemView {
        #         color: #333333;
        #         selection-background-color: #FFE0B2;
        #         selection-color: #333333;
        #     }
        #     QCalendarWidget QAbstractItemView:disabled { color: #CCCCCC; }
        #     QCalendarWidget QAbstractItemView::item { color: #333333; }
        #     QCalendarWidget QAbstractItemView::item:today { color: #FFA500; font-weight: bold; }
        #     QCalendarWidget QAbstractItemView::item:selected { color: #333333; background-color: #FFE0B2; }
        # \"\"\")


        layout.addWidget(self.calendar)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # --- Manually set button text ---
        ok_button = button_box.button(QDialogButtonBox.Ok)
        if ok_button: ok_button.setText("确定")
        cancel_button = button_box.button(QDialogButtonBox.Cancel)
        if cancel_button: cancel_button.setText("取消")
        # --- End button text ---

        layout.addWidget(button_box)

        self.calendar.clicked.connect(self.handle_date_click) # Select on single click

    def handle_date_click(self, date_val):
        \"\"\"Select date immediately on click\"\"\"
        # Optionally, could call accept() here for single-click selection
        pass # Just ensure the date is selected visually

    def get_selected_date(self) -> QDate:
        \"\"\"Return the selected date\"\"\"
        return self.calendar.selectedDate()


class CustomDateRangeWidget(QWidget):
    \"\"\"自定义的日期范围显示和选择控件\"\"\"
    # Signal emitting python date objects
    dateRangeChanged = Signal(date, date)

    def __init__(self, initial_start_date=None, initial_end_date=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        # Default dates if none provided
        today = date.today()
        if initial_end_date is None:
            initial_end_date = today
        if initial_start_date is None:
            initial_start_date = initial_end_date # Default start to end

        self._start_date = initial_start_date
        self._end_date = initial_end_date

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5) # Adjust spacing

        self.start_label = QLabel("从:")
        self.start_display = QPushButton(self._start_date.strftime("%Y/%m/%d")) # Use button for click visual
        self.start_display.setFlat(True) # Make it look less like a button
        self.start_display.setStyleSheet("text-align: left; padding: 3px; border: 1px solid #E0E0E0; border-radius: 3px;") # Basic style
        self.start_display.setMinimumWidth(100)
        self.start_display.clicked.connect(self.select_start_date)

        self.end_label = QLabel("到:")
        self.end_display = QPushButton(self._end_date.strftime("%Y/%m/%d"))
        self.end_display.setFlat(True)
        self.end_display.setStyleSheet("text-align: left; padding: 3px; border: 1px solid #E0E0E0; border-radius: 3px;")
        self.end_display.setMinimumWidth(100)
        self.end_display.clicked.connect(self.select_end_date)

        layout.addWidget(self.start_label)
        layout.addWidget(self.start_display)
        # layout.addSpacerItem(QSpacerItem(10, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)) # Fixed spacer
        layout.addWidget(self.end_label)
        layout.addWidget(self.end_display)
        layout.addStretch(1) # Push components to the left

        self._update_display()

    def select_start_date(self):
        \"\"\"Open calendar dialog to select start date\"\"\"
        dialog = CustomCalendarDialog(initial_date=QDate(self._start_date), parent=self)
        if dialog.exec_() == QDialog.Accepted:
            selected_qdate = dialog.get_selected_date()
            new_start_date = selected_qdate.toPython()
            # Ensure start date is not after end date
            if new_start_date > self._end_date:
                self._end_date = new_start_date # Adjust end date if needed
            self._start_date = new_start_date
            self._update_display()
            self._emit_date_range()

    def select_end_date(self):
        \"\"\"Open calendar dialog to select end date\"\"\"
        dialog = CustomCalendarDialog(initial_date=QDate(self._end_date), parent=self)
        if dialog.exec_() == QDialog.Accepted:
            selected_qdate = dialog.get_selected_date()
            new_end_date = selected_qdate.toPython()
            # Ensure end date is not before start date
            if new_end_date < self._start_date:
                self._start_date = new_end_date # Adjust start date if needed
            self._end_date = new_end_date
            self._update_display()
            self._emit_date_range()

    def _update_display(self):
        \"\"\"Update the display labels/buttons\"\"\"
        self.start_display.setText(self._start_date.strftime("%Y/%m/%d"))
        self.end_display.setText(self._end_date.strftime("%Y/%m/%d"))

    def _emit_date_range(self):
        \"\"\"Emit the dateRangeChanged signal\"\"\"
        self.logger.debug(f"Emitting date range: {self._start_date} to {self._end_date}")
        self.dateRangeChanged.emit(self._start_date, self._end_date)

    def get_date_range(self) -> tuple[date, date]:
        \"\"\"Return the current date range\"\"\"
        return self._start_date, self._end_date 