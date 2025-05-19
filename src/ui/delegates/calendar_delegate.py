#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Custom Delegate for QCalendarWidget View
"""

import logging
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle, QApplication, QCalendarWidget
from PySide6.QtCore import Qt, QModelIndex, QRect, QPoint, QDate
from PySide6.QtGui import QColor, QPalette, QPainter, QPen

class CalendarItemDelegate(QStyledItemDelegate):
    """Custom delegate to handle painting calendar date cells using the widget's palette."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        # No hardcoded colors needed now

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        painter.save()
        self.initStyleOption(option, index)

        text = index.data(Qt.DisplayRole)
        date = None
        calendar = None # Initialize calendar variable
        min_date = None
        max_date = None

        # Get date and calendar widget instance
        if option.widget:
            try:
                # Navigate up from the view (viewport) to the calendar
                calendar_candidate = option.widget.parent().parent()
                if isinstance(calendar_candidate, QCalendarWidget):
                    calendar = calendar_candidate
                    date = calendar.dateForCell(index.row(), index.column())
                    min_date = calendar.minimumDate()
                    max_date = calendar.maximumDate()
                else:
                     # Fallback for getting date if structure is different or UserRole+1 works
                     date_from_role = index.data(Qt.UserRole + 1)
                     if isinstance(date_from_role, QDate):
                          date = date_from_role
                     # Cannot easily get min/max date without calendar instance here

            except Exception as e:
                self.logger.warning(f"Could not get calendar/date/minmax for cell {index.row()},{index.column()}: {e}")

        is_selected = option.state & QStyle.State_Selected
        is_current_month = True
        if date and calendar:
             current_page_date = QDate(calendar.yearShown(), calendar.monthShown(), 1)
             is_current_month = (date.month() == current_page_date.month())

        is_today = (date == QDate.currentDate()) if date else False
        is_out_of_range = (date and min_date and date < min_date) or (date and max_date and date > max_date)

        # Determine if the cell should be treated as disabled/unselectable
        is_disabled_looking = is_out_of_range or not is_current_month

        # --- Background --- 
        bg_color = option.palette.color(QPalette.Base)

        # --- Background handling ---
        if is_disabled_looking:
            # Use hardcoded distinct dark background for disabled dates
            bg_color = QColor("#101010") # Very dark gray
        elif is_selected and is_current_month: # Don't highlight if disabled-looking
            bg_color = option.palette.color(QPalette.Highlight)
        elif is_today and is_current_month:
             # Use palette color for today, lighter than base
             bg_color = option.palette.color(QPalette.AlternateBase) 
             if not bg_color.isValid() or bg_color == option.palette.color(QPalette.Base):
                 # Fallback if AlternateBase isn't distinct
                 base_is_dark = option.palette.color(QPalette.Base).lightness() < 128
                 bg_color = QColor("#2C2C2C") if base_is_dark else QColor("#E0E0E0")

        painter.fillRect(option.rect, bg_color)

        # --- Text Color --- 
        text_color = option.palette.color(QPalette.WindowText)

        if is_disabled_looking:
            # Use hardcoded distinct dark text color for disabled dates
            text_color = QColor("#404040") # Dark gray text
        elif is_selected and is_current_month: # Don't highlight text if disabled-looking
            text_color = option.palette.color(QPalette.HighlightedText)
        elif is_today and is_current_month:
            # Use palette color for today's text (often Link role)
            text_color = option.palette.color(QPalette.Link)
            if not text_color.isValid(): text_color = QColor("#FFA500") # Orange fallback
        # else: use default text_color initialized above

        # --- Explicit Text Drawing --- 
        painter.setPen(QPen(text_color))
        if text:
            text_rect = option.rect
            painter.drawText(text_rect, Qt.AlignCenter, str(text))

        # --- Today's Outline --- 
        if is_today and is_current_month:
             outline_color = option.palette.color(QPalette.Link)
             if not outline_color.isValid(): outline_color = QColor("#FFA500")
             outline_pen = QPen(outline_color, 1)
             painter.setPen(outline_pen)
             painter.drawRect(option.rect.adjusted(0, 0, -1, -1))

        painter.restore()

    # sizeHint might be needed if default size is wrong
    # def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
    #     return super().sizeHint(option, index) 