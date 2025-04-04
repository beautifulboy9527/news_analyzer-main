import logging
import json
import os
import html # 导入 html 模块
from datetime import datetime, timedelta
import re
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QListWidget,
                           QListWidgetItem, QLabel, QTextBrowser,
                           QSplitter, QHBoxLayout, QPushButton,
                           QCheckBox, QSlider, QLineEdit, QDateEdit,
                           QStackedWidget, QMessageBox, QWidget,
                           QRadioButton, QButtonGroup, QGroupBox, QFormLayout,
                           QSizePolicy, QSpacerItem, QApplication, QGridLayout,
                           QStyledItemDelegate, QStyleOptionViewItem, QStyle) # 添加 QStyledItemDelegate etc.
from PyQt5.QtCore import pyqtSignal, Qt, QDate, pyqtSlot, QTimer, QSize, QRect # 添加 QRect
from PyQt5.QtGui import (QFont, QIntValidator, QPalette, QColor, QTextDocument, QFontMetrics,
                         QPainter, QTextOption, QAbstractTextDocumentLayout) # 添加 QPainter, QTextOption, QAbstractTextDocumentLayout

from src.models import NewsArticle # Use absolute import from src
from .ui_utils import setup_news_list_widget, setup_preview_browser # 导入新的辅助函数
from src.ui.viewmodels.news_list_viewmodel import NewsListViewModel # Use absolute import
# --- 自定义 Delegate 用于绘制富文本 ---
class NewsItemDelegate(QStyledItemDelegate):
    """用于在 QListWidget 中绘制包含富文本的项"""
    RichTextRole = Qt.UserRole + 1 # 自定义角色存储富文本

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: int):
        # 绘制背景 (处理选中状态)
        self.initStyleOption(option, index) # 初始化选项，获取默认样式
        painter.save()

        # 绘制背景
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PE_PanelItemViewItem, option, painter, option.widget)

        # 获取富文本
        rich_text = index.data(self.RichTextRole)

        if rich_text:
            # 设置文本选项
            text_option = QTextOption()
            text_option.setWrapMode(QTextOption.WordWrap)
            text_option.setAlignment(Qt.AlignLeft | Qt.AlignTop) # 顶部对齐

            # 创建 QTextDocument 并设置内容
            doc = QTextDocument()
            doc.setHtml(rich_text)
            doc.setTextWidth(option.rect.width() - 10) # 减去一些边距
            doc.setDefaultFont(option.font) # 使用 item 的字体

            # 计算绘制区域 (在背景内稍微缩进)
            text_rect = option.rect.adjusted(5, 3, -5, -3) # 左右各5px, 上下各3px 边距

            # 设置 painter 状态并绘制
            painter.translate(text_rect.topLeft())
            painter.setClipRect(text_rect.translated(-text_rect.topLeft())) # 限制绘制区域
            ctx = QAbstractTextDocumentLayout.PaintContext()
            # 设置选中时的文本颜色 (如果 QSS 没有覆盖)
            if option.state & QStyle.State_Selected:
                ctx.palette.setColor(QPalette.Text, option.palette.color(QPalette.HighlightedText))
            else:
                ctx.palette.setColor(QPalette.Text, option.palette.color(QPalette.Text))

            doc.documentLayout().draw(painter, ctx)

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: int) -> QSize:
        # 计算尺寸提示
        rich_text = index.data(self.RichTextRole)
        if rich_text:
            doc = QTextDocument()
            doc.setHtml(rich_text)
            doc.setTextWidth(option.rect.width() - 10) # 与 paint 中一致
            doc.setDefaultFont(option.font)
            # 返回文档的理想高度 + 垂直边距
            return QSize(int(doc.idealWidth()), int(doc.size().height()) + 6) # 6 = 3px top + 3px bottom margin
        return super().sizeHint(option, index) # Fallback


# --- End Delegate ---


class NewsListPanel(QWidget):
    """新闻列表面板组件"""

    item_selected = pyqtSignal(object)
    news_updated = pyqtSignal(object)
    item_double_clicked_signal = pyqtSignal(object) # 新增双击信号

    def __init__(self, view_model: NewsListViewModel, parent=None): # 修改为接收 ViewModel
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.news_list')
        if not isinstance(view_model, NewsListViewModel):
            raise TypeError("NewsListPanel requires a NewsListViewModel instance.")
        self.view_model = view_model # 存储 ViewModel 实例

        # 移除旧的状态变量，状态由 ViewModel 管理
        # self.current_news = [] # 由 ViewModel 管理
        # self.original_news = [] # 由 ViewModel 管理

        # self.read_news_ids = set() # 不再需要，状态由 ViewModel 管理
        self._init_ui()

    # 移除历史记录文件相关常量和方法，这些将由 AppService 和 Storage 处理

    def _init_ui(self):
        """初始化UI"""
        # --- 设置 Delegate ---
        self.delegate = NewsItemDelegate(self) # 创建 Delegate 实例

        # --- 连接 ViewModel 信号 ---
        self.view_model.news_list_changed.connect(self._on_news_list_changed)
        self.view_model.read_status_changed.connect(self._update_item_read_status) # 连接已读状态变化信号

        layout = QVBoxLayout(self)
        layout.setSpacing(10) # 增加主布局间距
        title_label = QLabel("新闻列表")
        layout.addWidget(title_label)

        # 主布局，包含筛选和排序，使用 QGridLayout
        filter_sort_group = QGroupBox("") # 移除标题文本
        filter_sort_group.setObjectName("dateFilterGroup") # 设置 objectName
        # filter_sort_group.setStyleSheet("""
        #     QGroupBox {
        #         border: none; /* 移除主边框 */
        #         border-top: 1px solid #ededed; /* 只保留顶部细线 */
        #         margin-top: 8px; /* 与上方控件的间距 */
        #         padding-top: 8px; /* 顶部内边距 */
        #         background-color: transparent;
        #    } 
        # """)
 # 样式移至 QSS
        filter_sort_layout = QGridLayout(filter_sort_group) # *** 改为 QGridLayout ***
        filter_sort_layout.setContentsMargins(8, 15, 8, 8) # 调整边距, top 要大于 margin-top
        filter_sort_layout.setSpacing(5) # 减小筛选排序内部间距

        # --- 模式选择 ---
        self.date_filter_mode = QButtonGroup(self)
        self.days_mode_radio = QRadioButton("最近天数")
        filter_title_label = QLabel("筛选与排序")
        # filter_title_label.setStyleSheet("font-weight: normal; color: #888; margin-bottom: 5px; margin-left: 2px;") # 样式移至 QSS 或移除
        filter_sort_layout.addWidget(filter_title_label, 0, 0) # *** (0, 0) ***
        self.range_mode_radio = QRadioButton("指定日期范围")
        self.date_filter_mode.addButton(self.days_mode_radio, 0) # ID 0 for days mode
        self.date_filter_mode.addButton(self.range_mode_radio, 1) # ID 1 for range mode
        self.days_mode_radio.setChecked(True)
        self.date_filter_mode.buttonClicked[int].connect(self._on_date_filter_mode_changed) # Connect with ID
        filter_sort_layout.addWidget(self.days_mode_radio, 0, 1) # *** (0, 1) ***
        filter_sort_layout.addWidget(self.range_mode_radio, 0, 2) # *** (0, 2) ***

        # --- QStackedWidget for filter controls ---
        self.filter_stack = QStackedWidget()
        self.filter_stack.setMinimumWidth(180) # 进一步减小最小宽度
        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred) # *** 水平策略改为 Expanding ***
        self.filter_stack.setSizePolicy(size_policy) # 应用尺寸策略
        filter_sort_layout.addWidget(self.filter_stack, 1, 0, 1, 5) # *** (1, 0) 跨 1 行 5 列 ***

        # --- Page 0: 最近天数筛选 ---
        days_filter_widget = QWidget()
        days_filter_layout = QHBoxLayout(days_filter_widget) # 改为 QHBoxLayout
        days_filter_layout.setContentsMargins(0, 5, 0, 5)
        days_filter_layout.setSpacing(5) # 调整水平间距

        self.date_slider = QSlider(Qt.Horizontal)
        self.date_slider.setMinimum(1)
        self.date_slider.setMaximum(365)
        self.date_slider.setValue(7)
        self.date_slider.setTickInterval(30)
        self.date_slider.setTickPosition(QSlider.TicksBelow)
        self.date_slider.setMinimumWidth(100) # 给滑块一个最小宽度
        self.date_slider.valueChanged.connect(self._on_date_range_changed)
        days_filter_layout.addWidget(self.date_slider, 1) # 添加滑块，允许伸缩

        self.date_range_label = QLabel("7天")
        self.date_range_label.setMinimumWidth(40) # 设置最小宽度
        self.date_range_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter) # 右对齐
        days_filter_layout.addWidget(self.date_range_label) # 直接添加标签

        self.days_input = QLineEdit()
        self.days_input.setMinimumWidth(35) # 设置最小宽度
        self.days_input.setMaximumWidth(50) # 设置最大宽度
        self.days_input.setAlignment(Qt.AlignCenter)
        self.days_input.setValidator(QIntValidator(1, 365))
        self.days_input.setText(str(self.date_slider.value()))
        self.days_input.setToolTip("输入天数 (1-365) 后按 Enter 确认")
        self.days_input.editingFinished.connect(self._on_days_input_changed)
        days_filter_layout.addStretch(0) # 添加少量伸缩，将输入框和标签推向右侧
        days_filter_layout.addWidget(self.days_input) # 直接添加输入框

        days_label = QLabel("天")
        days_filter_layout.addWidget(days_label) # 直接添加 "天" 标签

        self.filter_stack.addWidget(days_filter_widget) # Add page 0


        # --- Page 1: 指定日期范围筛选 ---
        range_filter_widget = QWidget()
        range_filter_layout = QHBoxLayout(range_filter_widget) # 改为 QHBoxLayout
        range_filter_layout.setContentsMargins(5, 5, 5, 5) # 增加左右边距
        range_filter_layout.setSpacing(2) # 设置一个较小的基础间距

        start_label = QLabel("从:") # 创建 "从:" 标签
        # start_label.setStyleSheet("margin-right: 3px;") # 样式移至 QSS
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addDays(-3))
        self.start_date_edit.setMaximumDate(QDate.currentDate())
        self.start_date_edit.dateChanged.connect(self._on_specific_date_changed)

        end_label = QLabel("到:") # 创建 "到:" 标签
        # end_label.setStyleSheet("margin-right: 3px;") # 样式移至 QSS
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setMaximumDate(QDate.currentDate())
        self.end_date_edit.dateChanged.connect(self._on_specific_date_changed)

        calendar_style = """
            /* QDateEdit { */ /* 针对 QDateEdit 本身 */
            /*     border: 1px solid #c0c0c0; */ /* 统一边框 */
            /*     border-radius: 3px;
 */
            /*     padding: 1px 3px; */ /* 内边距 */
            /* } */
             /*QDateEdit::down-button { */ /* 下拉按钮 */
            /*     subcontrol-origin: padding;
 */
            /*     subcontrol-position: center right; */ /* 居中对齐 */
            /*     width: 16px; */ /* 宽度调整 */
            /*     border: none; */ /* 无边框 */
            /*     background-color: #fdfdfd; */ /* 比默认白色稍暗一点 */
            /*     border-top-right-radius: 2px; */ /* 保持圆角一致 */
            /*     border-bottom-right-radius: 2px;
 */
            /* } */
             /*QDateEdit::down-arrow { */ /* 使用更细小的 V 形 SVG */
             /*    image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="8" height="5" viewBox="0 0 8 5"><polyline points="1,1 4,4 7,1" style="fill:none;stroke:%23777777;stroke-width:1"/></svg>'); */ /* 更细的灰色 V 形 */
             /*    width: 8px; */ /* 减小图标宽度 */
            /*     height: 5px; */ /* 减小图标高度 */
            /*     margin-right: 3px; */ /* 调整右边距 */
            /* } */
            /* QDateEdit::down-button:hover {
 */
             /*    background-color: #f0f0f0; */ /* 悬停时给按钮一个浅背景 */
            /* } */
             /*QCalendarWidget QAbstractItemView:enabled { */ /* 日历视图 */
            /*     color: #333; */ /* 浅色模式文字颜色 */
            /*     background-color: #f0f0f0; */ /* 浅色背景 */
            /*     selection-background-color: #a0a0a0; */ /* 选中背景 (类似深色模式但更浅) */
             /*    selection-color: #ffffff; */ /* 选中文字颜色 */
            /*     border: 1px solid #d0d0d0; */ /* 添加边框 */
            /* } */
             /*QCalendarWidget QWidget#qt_calendar_navigationbar { */ /* 日历导航栏 */
            /*     background-color: #e0e0e0; */ /* 导航栏背景 */
            /*     border: 1px solid #c0c0c0;
 */
            /* } */
             /*QCalendarWidget QToolButton { */ /* 日历工具按钮 */
             /*    color: #333;
 */
             /*    background-color: transparent;
 */
            /*     border: none;
 */
            /* } */
             /*QCalendarWidget QToolButton:hover {
 */
             /*    background-color: #d0d0d0;
 */
            /* } */
            /* QCalendarWidget QToolButton:pressed {
 */
             /*    background-color: #b0b0b0;
 */
            /* } */
        """
        # self.start_date_edit.setStyleSheet(calendar_style)
 # 样式移至 QSS
         #self.end_date_edit.setStyleSheet(calendar_style)
 # 样式移至 QSS

        range_filter_layout.addStretch(1) # 左侧伸缩
        range_filter_layout.addWidget(start_label) # 添加 "从:" 标签
        range_filter_layout.addWidget(self.start_date_edit) # 添加开始日期控件
        range_filter_layout.addStretch(1) # 中间伸缩
        range_filter_layout.addWidget(end_label) # 添加 "到:" 标签
        range_filter_layout.addWidget(self.end_date_edit) # 添加结束日期控件
        range_filter_layout.addStretch(1) # 右侧伸缩
        self.filter_stack.addWidget(range_filter_widget) # Add page 1

        # --- 排序部分 ---
        self.sort_button = QPushButton("排序")
        self.sort_button.setMinimumWidth(60) # 设置最小宽度
        self.sort_button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed) # 允许水平收缩
        self.sort_button.clicked.connect(self._sort_by_date)

        self.sort_order = QCheckBox("降序")
        self.sort_order.setChecked(True)
        self.sort_order.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed) # 允许水平收缩

        filter_sort_layout.addWidget(self.sort_button, 0, 3) # *** (0, 3) ***
        filter_sort_layout.addWidget(self.sort_order, 0, 4) # *** (0, 4) ***

        # *** 设置列伸缩 ***
        filter_sort_layout.setColumnStretch(0, 0) # 第 0 列不伸缩 (标题)
        filter_sort_layout.setColumnStretch(1, 0) # 第 1 列不伸缩 (Radio)
        filter_sort_layout.setColumnStretch(2, 1) # 第 2 列伸缩 (Radio + filter_stack)
        filter_sort_layout.setColumnStretch(3, 0) # 第 3 列不伸缩 (排序按钮)
        filter_sort_layout.setColumnStretch(4, 0) # 第 4 列不伸缩 (排序复选框)

        layout.addWidget(filter_sort_group) # Add the groupbox to the main layout

        # --- 新闻列表和预览 ---
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter, stretch=1) # Allow splitter to take remaining space

        # 使用辅助函数配置新闻列表
        self.news_list = QListWidget()
        self.news_list.setItemDelegate(self.delegate) # 设置自定义 Delegate
        self.news_list.setObjectName("newsListWidget") # 确保 objectName 设置正确
        setup_news_list_widget(self.news_list) # 调用辅助函数
        self.news_list.itemClicked.connect(self._on_item_clicked) # 恢复单击信号连接，用于更新预览
        self.news_list.itemDoubleClicked.connect(self._on_item_double_clicked) # 连接双击信号，用于弹出详情
        splitter.addWidget(self.news_list)

        # 使用辅助函数配置预览浏览器
        self.preview = QTextBrowser()
        setup_preview_browser(self.preview) # 调用辅助函数
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
        # 调用 ViewModel 进行筛选
        self.view_model.filter_by_days(value)
        # 状态标签的更新现在由 _on_news_list_changed 处理

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
            # 调用 ViewModel 进行筛选
            self.view_model.filter_by_days(days)
            self.logger.debug(f"通过输入框设置日期范围为: {days} 天 ({display_days_text})")
            # 状态标签的更新现在由 _on_news_list_changed 处理

        except ValueError:
            current_slider_value = self.date_slider.value()
            self.days_input.setText(str(current_slider_value))
        except Exception as e:
            self.logger.error(f"处理天数输入时出错: {e}", exc_info=True)

    # 移除 set_read_ids 方法，状态由 ViewModel 管理
    # def set_read_ids(self, read_ids): ...

    @pyqtSlot()
    def _on_news_list_changed(self):
        """处理 ViewModel 的 news_list_changed 信号，更新列表显示"""
        self.logger.info("NewsListPanel: Received news_list_changed signal from ViewModel. Updating UI.") # <-- 新增日志
        news_to_display = self.view_model.newsList
        self.logger.info(f"ViewModel data changed, updating list with {len(news_to_display)} items.")
        self._populate_list_widget(news_to_display)

        # 更新状态标签
        status_text = f"显示 {len(news_to_display)} 条新闻"
        if hasattr(self, 'status_label'): # Check if status_label exists
            self.status_label.setText(status_text)

        # Emit signal that news has been updated (potentially useful for other components)
        self.news_updated.emit(news_to_display) # 发射更新后的列表
        self.logger.debug(f"_on_news_list_changed 完成, 列表已更新")


    def _populate_list_widget(self, news_list: list):
        """用给定的新闻列表填充 QListWidget"""
        self.news_list.clear()
        self.logger.info(f"_populate_list_widget: 列表已清空，准备填充 {len(news_list)} 条新闻") # Changed to INFO
        self.logger.debug(f"_populate_list_widget: 准备填充 {len(news_list)} 条新闻到列表")
        items_added_count = 0 # Counter for added items
        self.news_list.blockSignals(True) # Block signals during population
        for news in news_list:
            if not isinstance(news, NewsArticle): continue

            # --- 获取状态和数据 ---
            is_new = getattr(news, 'is_new', False)
            is_read = getattr(news, 'is_read', False)
            title = news.title or '无标题'
            source = news.source_name or '未知来源'
            publish_time = news.publish_time
            display_date = publish_time.strftime('%Y-%m-%d %H:%M') if publish_time else "未知日期"

            # --- 构建富文本内容 ---
            # 对标题和来源日期进行 HTML 转义，防止特殊字符干扰富文本解析
            escaped_title = html.escape(title)
            escaped_source_date = html.escape(f"[{source}] {display_date}")

            # 使用 HTML/富文本格式创建两行文本
            # 第一行：标题 (正常大小，如果未读且是新的，可以考虑加粗或其他标记)
            # 第二行：来源和日期 (稍小字体，灰色)
            # star_prefix = "<b>* </b>" if is_new and not is_read else "" # Example: Bold star
            star_prefix = "* " if is_new and not is_read else ""
            # 使用 <p> 标签来强制换行，并为第二行设置样式
            # 注意：Delegate 会处理绘制，这里只需要准备好富文本字符串
            rich_text = f"""
            <p style="margin:0; padding:0;">{html.escape(star_prefix)}{escaped_title}</p>
            <p style="margin:0; padding:0; font-size:9pt; color:#888888;">{escaped_source_date}</p>
            """

            # --- 创建 QListWidgetItem ---
            item = QListWidgetItem()
            # 不再需要设置文本或 Widget，Delegate 会处理绘制
            # item.setText(f"{title} - [{source}]") # 可以设置一个纯文本供 Delegate 回退或工具提示

            # --- 存储数据 ---
            item.setData(Qt.UserRole, news) # 存储 NewsArticle 对象
            item.setData(NewsItemDelegate.RichTextRole, rich_text) # 存储富文本供 Delegate 使用

            # --- 添加 Item 到列表 ---
            self.news_list.addItem(item)

            # --- 移除设置已读样式的代码，Delegate 会处理 ---
            items_added_count += 1
        self.news_list.blockSignals(False) # Unblock signals
        self.logger.info(f"_populate_list_widget: 循环结束，尝试添加了 {items_added_count} 个项目")
        self.logger.info(f"_populate_list_widget: QListWidget 实际包含 {self.news_list.count()} 个项目")
        self.logger.debug(f"QListWidget 添加项目完成: {len(news_list)} 条")

    # 移除 _apply_date_filter 方法
    # def _apply_date_filter(self): ...

    # 移除 _apply_specific_date_range 方法
    # def _apply_specific_date_range(self, start_datetime: datetime, end_datetime: datetime): ...

    def _on_date_filter_mode_changed(self, mode_id):
        """处理日期筛选模式切换事件 (基于 QButtonGroup ID)"""
        self.filter_stack.setCurrentIndex(mode_id)
        self.logger.debug(f"日期筛选模式切换到: {'最近天数' if mode_id == 0 else '指定日期范围'}")
        if mode_id == 0: # 最近天数模式
            # 应用滑块/输入框的当前值
            self.view_model.filter_by_days(self.date_slider.value())
        elif mode_id == 1: # 指定日期范围模式
            # 应用日期选择器的当前值
            self._on_specific_date_changed() # 调用此方法以获取日期并调用 ViewModel

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

        # 调用 ViewModel 进行筛选
        self.logger.debug(f"指定日期范围变更，调用 ViewModel 筛选: {start_date.isoformat()} 到 {end_date.isoformat()}")
        self.view_model.filter_by_date_range(start_date, end_date)
        # 状态标签的更新现在由 _on_news_list_changed 处理

    def _sort_by_date(self):
        """按日期排序新闻列表"""
        # 需要排序的数据来自 ViewModel
        news_to_sort = list(self.view_model.newsList) # 获取当前显示的列表副本
        if not news_to_sort: return
        # sorted_news = self.current_news.copy() # Removed
        try:
            reverse_order = self.sort_order.isChecked()
            def get_date(news_item):
                # Handle potential None publish_time for sorting
                return news_item.publish_time if news_item.publish_time else datetime.min
            news_to_sort.sort(key=get_date, reverse=reverse_order)
            # self.current_news = sorted_news # Removed
            # 直接更新列表显示，不修改 ViewModel 的内部顺序（除非 ViewModel 提供排序方法）
            self._populate_list_widget(news_to_sort)
            order_text = "降序" if reverse_order else "升序"
            self.status_label.setText(f"已按日期{order_text}排列 {len(news_to_sort)} 条新闻")
        except Exception as e:
            self.status_label.setText(f"排序失败: {str(e)}")
            self.logger.error(f"新闻排序失败: {str(e)}")

    def _on_item_clicked(self, item):
        """处理列表项单击事件 - 更新预览并通知 ViewModel"""
        news_article: NewsArticle = item.data(Qt.UserRole)
        if not news_article or not isinstance(news_article, NewsArticle):
            self.logger.warning("单击事件：列表项数据不是有效的 NewsArticle 对象")
            return
        # 添加日志：确认即将发射信号
        title = news_article.title if news_article.title else "N/A"
        self.logger.info(f"NewsListPanel._on_item_clicked: Emitting item_selected for: {title[:30]}...")
        self.item_selected.emit(news_article) # 发射信号给 MainWindow
        self._update_preview(news_article)
        # 显式设置当前项为选中状态
        self.news_list.setCurrentItem(item) # <--- 添加这行
        # 通知 ViewModel 选中项已更改
        self.view_model.select_news(news_article)


    def _on_item_double_clicked(self, item):
        """处理列表项双击事件 - 更新选中并触发主窗口行为"""
        news_article: NewsArticle = item.data(Qt.UserRole)
        if not news_article or not isinstance(news_article, NewsArticle):
            self.logger.warning("双击事件：列表项数据不是有效的 NewsArticle 对象")
            return
        # --- 标记为已读 ---
        link = news_article.link
        if link:
            self.logger.debug(f"双击项，调用 mark_as_read: {link}")
            self.view_model.mark_as_read(link) # 在显示详情前标记为已读

        # 通知 ViewModel 选中项已更改 (双击也算选中)
        self.view_model.select_news(news_article)
        # 添加日志：确认即将发射信号
        title = news_article.title if news_article.title else "N/A"
        self.logger.info(f"NewsListPanel._on_item_double_clicked: Emitting item_double_clicked_signal for: {title[:30]}...")
        # 发射双击专用信号以弹出对话框
        self.item_double_clicked_signal.emit(news_article)

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

    @pyqtSlot(str, bool) # 修改槽签名以接收 is_read
    def _update_item_read_status(self, news_link: str, is_read: bool):
        """更新列表中特定新闻项的已读状态和显示"""
        """处理 ViewModel 的 read_status_changed 信号，请求更新单个列表项"""
        self.logger.debug(f"尝试更新链接 {news_link} 的已读状态为 {is_read}，请求重绘")
        found = False
        for index in range(self.news_list.count()): # Use 'index' for clarity
            item = self.news_list.item(index)
            if not item: continue

            news_data: NewsArticle = item.data(Qt.UserRole)
            if news_data and news_data.link == news_link:
                self.logger.debug(f"找到匹配项于索引 {index}，请求更新。")
                found = True
                # 更新富文本数据以反映星号变化
                is_new = getattr(news_data, 'is_new', False)
                title = news_data.title or '无标题'
                source = news_data.source_name or '未知来源'
                publish_time = news_data.publish_time
                display_date = publish_time.strftime('%Y-%m-%d %H:%M') if publish_time else "未知日期"
                escaped_title = html.escape(title)
                escaped_source_date = html.escape(f"[{source}] {display_date}")
                star_prefix = "* " if is_new and not is_read else "" # is_read 是函数参数
                rich_text = f"""
                <p style="margin:0; padding:0;">{html.escape(star_prefix)}{escaped_title}</p>
                <p style="margin:0; padding:0; font-size:9pt; color:#888888;">{escaped_source_date}</p>
                """
                item.setData(NewsItemDelegate.RichTextRole, rich_text) # 更新存储的富文本

                # 请求 QListWidget 重绘该项
                # 获取该项的 QModelIndex
                model_index = self.news_list.indexFromItem(item)
                if model_index.isValid():
                    self.news_list.update(model_index) # 请求更新特定索引
                    self.logger.debug(f"已请求更新索引 {model_index.row()}")
                else:
                     self.logger.warning(f"无法获取索引 {index} 的有效 QModelIndex 进行更新")
                break # 找到后退出循环
        if not found: # 使用 if not found 保持一致性
            self.logger.warning(f"未在列表中找到链接为 {news_link} 的新闻项进行状态更新")

    # _record_browsing_history 方法已移除，逻辑移至 AppService