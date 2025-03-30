"""
新闻列表面板

显示新闻列表，并处理新闻项选择事件。
"""

import logging
import json
import os
from datetime import datetime, timedelta
import re
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QListWidget,
                           QListWidgetItem, QLabel, QTextBrowser,
                           QSplitter, QHBoxLayout, QPushButton,
                           QCheckBox, QSlider, QLineEdit, QDateEdit,
                           QStackedWidget, QMessageBox, QWidget,
                           QRadioButton, QButtonGroup, QGroupBox, QFormLayout,
                           QSizePolicy, QSpacerItem) # 正确添加导入并保持格式
from PyQt5.QtCore import pyqtSignal, Qt, QDate
from PyQt5.QtGui import QFont, QIntValidator, QPalette, QColor

from ..models import NewsArticle


class NewsListPanel(QWidget):
    """新闻列表面板组件"""

    item_selected = pyqtSignal(object)
    news_updated = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.news_list')
        self.current_news = []
        self.original_news = []
        self.read_news_ids = set()
        self._init_ui()

    HISTORY_FILE = os.path.join('data', 'browsing_history.json')
    MAX_HISTORY_ITEMS = 50

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10) # 增加主布局间距
        title_label = QLabel("新闻列表")
        # title_label.setStyleSheet("font-weight: bold; font-size: 14px;") # 移除内联样式
        layout.addWidget(title_label)

        # 主水平布局，包含筛选和排序
        filter_sort_group = QGroupBox("") # 移除标题文本
        filter_sort_group.setObjectName("dateFilterGroup") # 设置 objectName
        # 移除内联样式
        # filter_sort_group.setStyleSheet("""...""") # Removed comment
        # --- GroupBox 样式 (移除 ::title 部分) ---
        filter_sort_group.setStyleSheet("""
            QGroupBox {
                border: none; /* 移除主边框 */
                border-top: 1px solid #ededed; /* 只保留顶部细线 */
                margin-top: 8px; /* 与上方控件的间距 */
                padding-top: 8px; /* 顶部内边距 */
                background-color: transparent;
            }
            /* QGroupBox::title { ... } */ /* 移除 title 样式 */
        """)
        filter_sort_layout = QHBoxLayout(filter_sort_group) # 改为 QHBoxLayout
        filter_sort_layout.setContentsMargins(8, 15, 8, 8) # 调整边距, top 要大于 margin-top
        filter_sort_layout.setSpacing(5) # 减小筛选排序内部间距

        # --- 模式选择 ---
        # mode_layout = QHBoxLayout() # Removed
        # mode_layout.setSpacing(15) # Removed
        self.date_filter_mode = QButtonGroup(self)
        self.days_mode_radio = QRadioButton("最近天数")
        filter_title_label = QLabel("筛选与排序")
        filter_title_label.setStyleSheet("font-weight: normal; color: #888; margin-bottom: 5px; margin-left: 2px;") # 取消加粗，颜色更浅，增加左边距
        filter_sort_layout.addWidget(filter_title_label) # 添加自定义标题
        self.range_mode_radio = QRadioButton("指定日期范围")
        self.date_filter_mode.addButton(self.days_mode_radio, 0) # ID 0 for days mode
        self.date_filter_mode.addButton(self.range_mode_radio, 1) # ID 1 for range mode
        self.days_mode_radio.setChecked(True)
        self.date_filter_mode.buttonClicked[int].connect(self._on_date_filter_mode_changed) # Connect with ID
        filter_sort_layout.addWidget(self.days_mode_radio) # Directly add to main layout
        filter_sort_layout.addWidget(self.range_mode_radio) # Directly add to main layout
        # mode_layout.addStretch() # Removed
        # filter_sort_layout.addLayout(mode_layout) # Removed

        # --- QStackedWidget for filter controls ---
        self.filter_stack = QStackedWidget()
        self.filter_stack.setMinimumWidth(180) # 进一步减小最小宽度
        size_policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred) # 水平策略改为 Preferred
        self.filter_stack.setSizePolicy(size_policy) # 应用尺寸策略
        filter_sort_layout.addWidget(self.filter_stack) # Add stack directly to main layout

        # --- Page 0: 最近天数筛选 ---
        days_filter_widget = QWidget()
        days_filter_layout = QHBoxLayout(days_filter_widget) # 改为 QHBoxLayout
        days_filter_layout.setContentsMargins(0, 5, 0, 5)
        days_filter_layout.setSpacing(5) # 调整水平间距

        # 滑块行 (直接添加到新布局)
        # slider_row = QHBoxLayout() # Removed
        self.date_slider = QSlider(Qt.Horizontal)
        self.date_slider.setMinimum(1)
        self.date_slider.setMaximum(365)
        self.date_slider.setValue(7)
        self.date_slider.setTickInterval(30)
        self.date_slider.setTickPosition(QSlider.TicksBelow)
        self.date_slider.setMinimumWidth(100) # 给滑块一个最小宽度
        # 移除内联样式
        # self.date_slider.setStyleSheet("""...""")
        self.date_slider.valueChanged.connect(self._on_date_range_changed)
        # slider_row.addWidget(self.date_slider) # Removed
        # days_filter_layout.addLayout(slider_row) # Removed
        days_filter_layout.addWidget(self.date_slider, 1) # 添加滑块，允许伸缩

        # 天数显示和输入行 (直接添加到新布局)
        # days_display_row = QHBoxLayout() # Removed
        # days_display_row.setSpacing(5) # Removed
        # days_display_row.addStretch() # Removed

        self.date_range_label = QLabel("7天")
        # self.date_range_label.setFixedWidth(45) # 移除固定宽度
        self.date_range_label.setMinimumWidth(40) # 设置最小宽度
        self.date_range_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter) # 右对齐
        # days_display_row.addWidget(self.date_range_label) # Removed
        days_filter_layout.addWidget(self.date_range_label) # 直接添加标签

        self.days_input = QLineEdit()
        # self.days_input.setFixedWidth(40) # 移除固定宽度
        self.days_input.setMinimumWidth(35) # 设置最小宽度
        self.days_input.setAlignment(Qt.AlignCenter)
        self.days_input.setValidator(QIntValidator(1, 365))
        self.days_input.setText(str(self.date_slider.value()))
        self.days_input.setToolTip("输入天数 (1-365) 后按 Enter 确认")
        # 移除内联样式
        # self.days_input.setStyleSheet("""...""")
        self.days_input.editingFinished.connect(self._on_days_input_changed)
        # days_display_row.addWidget(self.days_input) # Removed
        days_filter_layout.addWidget(self.days_input) # 直接添加输入框

        days_label = QLabel("天")
        # days_label.setStyleSheet("color: #555; margin-left: 2px;") # 移除内联样式
        # days_display_row.addWidget(days_label) # Removed
        days_filter_layout.addWidget(days_label) # 直接添加 "天" 标签

        # 移除内联样式
        # self.date_range_label.setStyleSheet("color: #333; font-weight: bold;") # 加粗显示

        # days_filter_layout.addLayout(days_display_row) # Removed
        self.filter_stack.addWidget(days_filter_widget) # Add page 0


        # --- Page 1: 指定日期范围筛选 ---
        range_filter_widget = QWidget()
        range_filter_layout = QHBoxLayout(range_filter_widget) # 改为 QHBoxLayout
        range_filter_layout.setContentsMargins(5, 5, 5, 5) # 增加左右边距
        range_filter_layout.setSpacing(2) # 设置一个较小的基础间距
        # range_filter_layout.setLabelAlignment(Qt.AlignLeft) # Removed for QHBoxLayout

        # 移除 QDateEdit 的内联样式定义
        # date_edit_style = """..."""

        start_label = QLabel("从:") # 创建 "从:" 标签
        start_label.setStyleSheet("margin-right: 3px;") # 添加右边距
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        # 1. 修改默认开始日期为 3 天前
        self.start_date_edit.setDate(QDate.currentDate().addDays(-3))
        # 2. 添加最大日期限制
        self.start_date_edit.setMaximumDate(QDate.currentDate())
        # self.start_date_edit.setStyleSheet(date_edit_style) # 移除应用
        self.start_date_edit.dateChanged.connect(self._on_specific_date_changed)

        end_label = QLabel("到:") # 创建 "到:" 标签
        end_label.setStyleSheet("margin-right: 3px;") # 添加右边距
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        # 2. 添加最大日期限制
        self.end_date_edit.setMaximumDate(QDate.currentDate())
        # self.end_date_edit.setStyleSheet(date_edit_style) # 移除应用
        self.end_date_edit.dateChanged.connect(self._on_specific_date_changed)

        # --- 为 QDateEdit 的日历弹窗和下拉按钮应用样式 ---
        calendar_style = """
            QDateEdit { /* 针对 QDateEdit 本身 */
                border: 1px solid #c0c0c0; /* 统一边框 */
                border-radius: 3px;
                padding: 1px 3px; /* 内边距 */
                /* margin-left: 5px; */ /* 移除左边距 */
            }
            QDateEdit::down-button { /* 下拉按钮 */
                subcontrol-origin: padding;
                subcontrol-position: center right; /* 居中对齐 */
                width: 16px; /* 宽度调整 */
                border: none; /* 无边框 */
                /* 让按钮背景比输入框稍微不同，以示区别 */
                background-color: #fdfdfd; /* 比默认白色稍暗一点 */
                border-top-right-radius: 2px; /* 保持圆角一致 */
                border-bottom-right-radius: 2px;
            }
            QDateEdit::down-arrow { /* 使用更细小的 V 形 SVG */
                image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="8" height="5" viewBox="0 0 8 5"><polyline points="1,1 4,4 7,1" style="fill:none;stroke:%23777777;stroke-width:1"/></svg>'); /* 更细的灰色 V 形 */
                width: 8px; /* 减小图标宽度 */
                height: 5px; /* 减小图标高度 */
                margin-right: 3px; /* 调整右边距 */
            }
            /* 移除旧的箭头绘制规则注释 */
            QDateEdit::down-button:hover {
                background-color: #f0f0f0; /* 悬停时给按钮一个浅背景 */
            }
            QCalendarWidget QAbstractItemView:enabled { /* 日历视图 */
                color: #333; /* 浅色模式文字颜色 */
                background-color: #f0f0f0; /* 浅色背景 */
                selection-background-color: #a0a0a0; /* 选中背景 (类似深色模式但更浅) */
                selection-color: #ffffff; /* 选中文字颜色 */
                border: 1px solid #d0d0d0; /* 添加边框 */
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar { /* 日历导航栏 */
                background-color: #e0e0e0; /* 导航栏背景 */
                border: 1px solid #c0c0c0;
            }
            QCalendarWidget QToolButton { /* 日历工具按钮 */
                color: #333;
                background-color: transparent;
                border: none;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #d0d0d0;
            }
            QCalendarWidget QToolButton:pressed {
                background-color: #b0b0b0;
            }
        """
        self.start_date_edit.setStyleSheet(calendar_style)
        self.end_date_edit.setStyleSheet(calendar_style)

        # 移除 "应用范围" 按钮 (之前是 QFormLayout 的 addRow)
        layout.addSpacing(10) # 增加标题和筛选组之间的间距
        # 使用 addStretch 控制间距
        range_filter_layout.addStretch(1) # 左侧伸缩
        range_filter_layout.addWidget(start_label) # 添加 "从:" 标签
        range_filter_layout.addWidget(self.start_date_edit) # 添加开始日期控件
        range_filter_layout.addStretch(1) # 中间伸缩
        range_filter_layout.addWidget(end_label) # 添加 "到:" 标签
        range_filter_layout.addWidget(self.end_date_edit) # 添加结束日期控件
        range_filter_layout.addStretch(1) # 右侧伸缩
        self.filter_stack.addWidget(range_filter_widget) # Add page 1
        # --- 排序部分 ---
        # sort_layout = QHBoxLayout() # Removed
        # sort_layout.setSpacing(10) # Removed
        self.sort_button = QPushButton("排序")
        # self.sort_button.setFixedWidth(70) # 移除固定宽度
        self.sort_button.setMinimumWidth(60) # 设置最小宽度
        # 移除内联样式
        self.sort_button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed) # 允许水平收缩
        # self.sort_button.setStyleSheet("""...""")
        self.sort_button.clicked.connect(self._sort_by_date)
        # sort_layout.addWidget(self.sort_button) # Removed

        self.sort_order = QCheckBox("降序")
        self.sort_order.setChecked(True)
        self.sort_order.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed) # 允许水平收缩
        # 移除内联样式
        # self.sort_order.setStyleSheet("""...""")
        # sort_layout.addWidget(self.sort_order) # Removed
        # sort_layout.addStretch() # Removed
        # filter_sort_layout.addLayout(sort_layout) # Removed
        filter_sort_layout.addWidget(self.sort_button) # Directly add to main layout
        filter_sort_layout.addSpacing(2) # 进一步减小排序按钮和复选框之间的间距
        filter_sort_layout.addWidget(self.sort_order) # Directly add to main layout
        filter_sort_layout.addStretch(1) # 调整伸缩因子

        # filter_sort_layout.addStretch() # Remove stretch from here
        layout.addWidget(filter_sort_group) # Add the groupbox to the main layout

        # --- 新闻列表和预览 ---
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter, stretch=1) # Allow splitter to take remaining space
        self.news_list = QListWidget()
        self.news_list.setObjectName("newsListWidget") # 设置 objectName
        self.news_list.setAlternatingRowColors(False) # 禁用交替行颜色
        self.news_list.itemClicked.connect(self._on_item_clicked) # 恢复单击信号连接，用于更新预览
        self.news_list.itemDoubleClicked.connect(self._on_item_double_clicked) # 连接双击信号，用于弹出详情
        # --- 移除焦点虚线框 ---
        self.news_list.setStyleSheet("QListWidget { outline: none; } QListWidget::item:selected { border: none; }")

        # --- 通过 Palette 设置深色背景 ---
        palette = self.news_list.palette()
        # 使用更符合优雅黑的颜色
        palette.setColor(QPalette.Base, QColor("#1a1a1a")) # 列表背景
        palette.setColor(QPalette.Text, QColor("#e8e8e8")) # 列表文字
        palette.setColor(QPalette.Highlight, QColor("#2c2c2c")) # 选中背景
        palette.setColor(QPalette.HighlightedText, QColor("#f5f5f5")) # 选中文字
        # palette.setColor(QPalette.AlternateBase, QColor("#1e1e1e")) # 交替行颜色
        self.news_list.setPalette(palette)
        self.news_list.viewport().setAutoFillBackground(True) # 确保 viewport 使用 Palette 填充
        # --- Palette 设置结束 ---

        splitter.addWidget(self.news_list)
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        splitter.addWidget(self.preview)
        splitter.setSizes([400, 200])
        self.status_label = QLabel("加载新闻...")
        layout.addWidget(self.status_label)

        # 初始显示 QStackedWidget 的第一页 (最近天数)
        self.filter_stack.setCurrentIndex(0)

    def _on_date_range_changed(self, value):
        """处理日期范围滑块变化"""
        # 确保当前是 "最近天数" 模式
        if self.date_filter_mode.checkedId() != 0:
            return
        display_days_text = f"{value}天" if value < 365 else "一年内"
        self.date_range_label.setText(display_days_text)
        if hasattr(self, 'days_input'):
             self.days_input.blockSignals(True)
             self.days_input.setText(str(value))
             self.days_input.blockSignals(False)
        self._apply_date_filter() # 应用筛选
        status_text = f"显示最近 {display_days_text} {len(self.current_news)} 条新闻"
        self.status_label.setText(status_text)

    def _on_days_input_changed(self):
        """处理天数输入框编辑完成事件"""
        try:
            days = int(self.days_input.text())
            clamped_days = max(1, min(days, 365))
            if days != clamped_days:
                self.days_input.setText(str(clamped_days))
                days = clamped_days

            self.date_slider.blockSignals(True)
            self.date_slider.setValue(days)
            self.date_slider.blockSignals(False)

            # 确保当前是 "最近天数" 模式
            if self.date_filter_mode.checkedId() != 0:
                return

            display_days_text = f"{days}天" if days < 365 else "一年内"
            self.date_range_label.setText(display_days_text)
            self._apply_date_filter() # 应用筛选
            status_text = f"显示最近 {display_days_text} {len(self.current_news)} 条新闻"
            self.status_label.setText(status_text)
            self.logger.debug(f"通过输入框设置日期范围为: {days} 天 ({display_days_text})")

        except ValueError:
            current_slider_value = self.date_slider.value()
            self.days_input.setText(str(current_slider_value))
        except Exception as e:
            self.logger.error(f"处理天数输入时出错: {e}", exc_info=True)

    # 移除 _update_controls_for_days_mode 和 _update_controls_for_range_mode 方法
    # 因为 QStackedWidget 会自动处理控件显隐，不再需要手动启用/禁用

    def set_read_ids(self, read_ids):
        """设置已读新闻ID集合"""
        self.read_news_ids = read_ids
        # 更新列表显示以反映已读状态
        if hasattr(self, 'current_news'):
            self._populate_list_widget(self.current_news)

    def update_news(self, news_items):
        """更新新闻列表显示 (已修复)"""
        self.logger.debug(f"update_news 收到 {len(news_items)} 条新闻 (已按分类筛选)")
        self.original_news = news_items # Store the category-filtered list as the base for date filtering

        # Apply the *currently selected* date filter mode
        current_mode_id = self.date_filter_mode.checkedId()
        self.logger.debug(f"当前日期筛选模式 ID: {current_mode_id}")

        if current_mode_id == 0: # 最近天数模式
            self.logger.debug("应用 '最近天数' 日期筛选")
            self._apply_date_filter() # This filters self.original_news and updates self.current_news/list
        elif current_mode_id == 1: # 指定日期范围模式
            self.logger.debug("应用 '指定日期范围' 日期筛选")
            # Call the handler which reads dates and applies the filter
            self._on_specific_date_changed() # This filters self.original_news and updates self.current_news/list
        else:
            # Fallback or default case if needed, maybe just populate directly?
            self.logger.warning(f"未知的日期筛选模式 ID: {current_mode_id}, 直接填充列表")
            self.current_news = self.original_news # Use the category-filtered list directly
            self._populate_list_widget(self.current_news)
            self.status_label.setText(f"显示 {len(self.current_news)} 条新闻 (无日期筛选)")

        # The status label is updated within _apply_date_filter and _on_specific_date_changed/_apply_specific_date_range
        # So no need to update it again here unless it's the fallback case.

        # Do NOT reset the UI controls here. The user might have selected a specific date range.
        # self.filter_stack.setCurrentIndex(0)
        # self.days_mode_radio.setChecked(True)

        # Emit signal that news has been updated (potentially useful for other components)
        self.news_updated.emit(self.current_news)
        self.logger.debug(f"update_news 完成, 最终显示 {len(self.current_news)} 条新闻")


    def _populate_list_widget(self, news_list: list):
        """用给定的新闻列表填充 QListWidget"""
        self.news_list.clear()
        self.logger.debug(f"_populate_list_widget: 准备填充 {len(news_list)} 条新闻到列表")
        for news in news_list:
            if not isinstance(news, NewsArticle): continue
            item = QListWidgetItem()
            title = news.title or '无标题'
            source = news.source_name or '未知来源'
            publish_time = news.publish_time
            display_date = publish_time.strftime('%Y-%m-%d %H:%M:%S') if publish_time else "未知日期"
            display_text = f"{title}\n[{source}] {display_date}"
            item.setText(display_text)
            font = QFont()
            news_link = news.link
            is_read = news_link and news_link in self.read_news_ids
            font.setBold(not is_read)
            if is_read: item.setForeground(Qt.gray)
            item.setFont(font)
            item.setData(Qt.UserRole, news)
            self.news_list.addItem(item)
        self.logger.debug(f"QListWidget 添加项目完成: {len(news_list)} 条")

    def _apply_date_filter(self):
        """应用日期范围筛选 (基于滑块/天数输入)"""
        if not hasattr(self, 'original_news') or not self.original_news:
            self._populate_list_widget([])
            self.current_news = [] # Explicitly set current_news to empty
            self.status_label.setText("无新闻可供筛选")
            return
        days = self.date_slider.value()
        now = datetime.now()
        # self.logger.debug(f"_apply_specific_date_range: 日期筛选后剩余 {len(filtered_news)} 条新闻") # This log seems misplaced, commenting out
        cutoff_date = now - timedelta(days=days)
        show_all_dates = days >= 365
        filtered_news = [] # Initialize before try block
        try:
            filtered_news = [
                news for news in self.original_news
                if (news.publish_time and news.publish_time >= cutoff_date) or show_all_dates or not news.publish_time
            ]
        except Exception as e:
            self.logger.error(f"Error during date filtering list comprehension in _apply_date_filter: {e}", exc_info=True)
            # filtered_news remains []

        self.current_news = filtered_news
        self.logger.debug(f"_apply_date_filter: 日期筛选后剩余 {len(filtered_news)} 条新闻") # Log after assignment
        self._populate_list_widget(filtered_news)

    def _apply_specific_date_range(self, start_datetime: datetime, end_datetime: datetime):
        """应用指定的开始和结束日期时间进行筛选"""
        if not hasattr(self, 'original_news') or not self.original_news:
            self._populate_list_widget([])
            self.status_label.setText("无新闻可供筛选")
            self.current_news = [] # Ensure current_news is cleared here too
            return
        filtered_news = [] # Initialize before try block
        try:
            filtered_news = [
                news for news in self.original_news
                if news.publish_time and start_datetime <= news.publish_time <= end_datetime
            ]
        except Exception as e:
            self.logger.error(f"Error during date filtering list comprehension in _apply_specific_date_range: {e}", exc_info=True)
            # filtered_news remains []

        self.current_news = filtered_news
        self._populate_list_widget(filtered_news)
        start_date_str = start_datetime.strftime('%Y-%m-%d')
        end_date_str = end_datetime.strftime('%Y-%m-%d')
        self.status_label.setText(f"显示日期范围 {start_date_str} 到 {end_date_str} 的 {len(filtered_news)} 条新闻")

    def _on_date_filter_mode_changed(self, mode_id):
        """处理日期筛选模式切换事件 (基于 QButtonGroup ID)"""
        self.filter_stack.setCurrentIndex(mode_id)
        self.logger.debug(f"日期筛选模式切换到: {'最近天数' if mode_id == 0 else '指定日期范围'}")
        if mode_id == 0: # 最近天数模式
            self._apply_date_filter() # 应用滑块/输入框的当前值
        elif mode_id == 1: # 指定日期范围模式
            self._on_specific_date_changed() # 应用日期选择器的当前值

    # 移除 _on_apply_date_range 方法，因为按钮已移除，日期更改实时生效

    def _on_specific_date_changed(self):
        """处理指定日期范围 QDateEdit 变化事件，实时应用筛选"""
        # 仅在 "指定日期范围" 模式激活时执行
        if self.date_filter_mode.checkedId() != 1:
            return

        start_date = self.start_date_edit.date().toPyDate()
        end_date = self.end_date_edit.date().toPyDate()

        # 确保结束日期不早于开始日期
        if start_date > end_date:
            # 暂时静默调整结束日期为开始日期
            self.end_date_edit.blockSignals(True)
            self.end_date_edit.setDate(self.start_date_edit.date())
            self.end_date_edit.blockSignals(False)
            end_date = start_date # 更新 end_date 变量
            self.logger.warning("结束日期早于开始日期，已自动调整结束日期。")
            # 或者可以取消注释下面的代码以显示警告框
            # QMessageBox.warning(self, "日期错误", "开始日期不能晚于结束日期。")
            # return

        end_datetime = datetime.combine(end_date, datetime.max.time())
        start_datetime = datetime.combine(start_date, datetime.min.time())

        self.logger.debug(f"指定日期范围变更，应用筛选: {start_date.isoformat()} 到 {end_date.isoformat()}")
        self._apply_specific_date_range(start_datetime, end_datetime)

    def _sort_by_date(self):
        """按日期排序新闻列表"""
        if not self.current_news: return
        sorted_news = self.current_news.copy()
        try:
            reverse_order = self.sort_order.isChecked()
            def get_date(news_item):
                return news_item.publish_time if news_item.publish_time else datetime.min
            sorted_news.sort(key=get_date, reverse=reverse_order)
            self.current_news = sorted_news
            self._populate_list_widget(self.current_news)
            order_text = "降序" if reverse_order else "升序"
            self.status_label.setText(f"已按日期{order_text}排列 {len(sorted_news)} 条新闻")
        except Exception as e:
            self.status_label.setText(f"排序失败: {str(e)}")
            self.logger.error(f"新闻排序失败: {str(e)}")

    def _on_item_clicked(self, item):
        """处理列表项单击事件 - 只更新预览"""
        news_article: NewsArticle = item.data(Qt.UserRole)
        if not news_article or not isinstance(news_article, NewsArticle):
            self.logger.warning("单击事件：列表项数据不是有效的 NewsArticle 对象")
            return
        self._update_preview(news_article)
        # 单击不再触发 item_selected 信号或记录历史

    def _on_item_double_clicked(self, item):
        """处理列表项双击事件 - 触发主窗口行为"""
        news_article: NewsArticle = item.data(Qt.UserRole)
        if not news_article or not isinstance(news_article, NewsArticle):
            self.logger.warning("双击事件：列表项数据不是有效的 NewsArticle 对象")
            return
        # self._update_preview(news_article) # 双击时预览区已更新，无需重复
        self.item_selected.emit(news_article) # 发送信号给主窗口
        self._record_browsing_history(news_article) # 记录历史

    def _update_preview(self, news_article: NewsArticle):
        """更新新闻预览"""
        title = news_article.title or '无标题'
        source = news_article.source_name or '未知来源'
        date = news_article.publish_time.strftime('%Y-%m-%d %H:%M:%S') if news_article.publish_time else "未知日期"
        content_display = news_article.content
        summary_display = news_article.summary
        if not content_display and summary_display:
             description = f"<p><i>(仅摘要)</i></p>{summary_display}"
        elif content_display:
             description = content_display
        else:
             description = '无内容'
        link = news_article.link or ''
        html = f"""
        <h2>{title}</h2>
        <p><strong>来源:</strong> {source} | <strong>日期:</strong> {date}</p>
        <hr>
        <p>{description}</p>
        """
        if link: html += f'<p><a href="{link}" target="_blank">阅读原文</a></p>'
        self.preview.setHtml(html)

    def _record_browsing_history(self, news_article: NewsArticle):
        """记录浏览历史"""
        title = news_article.title or '无标题'
        self.logger.debug(f"记录浏览历史: {title[:30]}...")
        try:
            history = []
            os.makedirs(os.path.dirname(self.HISTORY_FILE), exist_ok=True)
            if os.path.exists(self.HISTORY_FILE):
                try:
                    with open(self.HISTORY_FILE, 'r', encoding='utf-8') as f: history = json.load(f)
                    if not isinstance(history, list): history = []
                except (json.JSONDecodeError, IOError) as e:
                    self.logger.error(f"读取浏览历史文件失败: {e}"); history = []
            pub_date_str = news_article.publish_time.isoformat() if news_article.publish_time else None
            entry = {
                'title': title, 'link': news_article.link, 'source_name': news_article.source_name,
                'pub_date': pub_date_str, 'description': news_article.summary or news_article.content,
                'viewed_at': datetime.now().isoformat()
            }
            link_to_check = entry.get('link')
            if link_to_check:
                history = [item for item in history if item.get('link') != link_to_check]
            history.insert(0, entry)
            history = history[:self.MAX_HISTORY_ITEMS]
            with open(self.HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存浏览历史失败: {e}")
