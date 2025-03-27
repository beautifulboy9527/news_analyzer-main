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
                           QCheckBox, QSlider)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont


class NewsListPanel(QWidget):
    """新闻列表面板组件"""
    
    # 自定义信号：选择新闻项
    item_selected = pyqtSignal(dict)

    # 新增信号：新闻列表已更新
    news_updated = pyqtSignal(list)

    # 移除 related_news_requested 信号
    # related_news_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.logger = logging.getLogger('news_analyzer.ui.news_list')
        self.current_news = []
        
        self.read_news_ids = set() # 用于存储已读新闻的ID
        self._init_ui()
    
    HISTORY_FILE = os.path.join('data', 'browsing_history.json')
    MAX_HISTORY_ITEMS = 50

    def _init_ui(self):
        """初始化UI"""
        # 创建主布局
        layout = QVBoxLayout(self)
        
        # 标题标签
        title_label = QLabel("新闻列表")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)
        
        # 控制面板
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(0, 5, 0, 5)

        # 创建日期范围控制组
        date_control_layout = QHBoxLayout()
        date_control_layout.setContentsMargins(0, 0, 0, 0)
        date_control_layout.setSpacing(5)
        
        # 添加日期范围滑块
        self.date_slider = QSlider(Qt.Horizontal)
        self.date_slider.setMinimum(1)
        self.date_slider.setMaximum(30)
        self.date_slider.setValue(1)
        self.date_slider.setTickInterval(1)
        self.date_slider.setTickPosition(QSlider.TicksBelow)
        self.date_slider.setFixedWidth(150)
        self.date_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #CFD8DC;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                height: 16px;
                margin: -5px 0;
                background: #607D8B;
                border-radius: 8px;
            }
        """)
        self.date_slider.valueChanged.connect(self._on_date_range_changed)
        
        # 添加日期范围显示
        self.date_range_label = QLabel("1天")
        self.date_range_label.setFixedWidth(40)
        self.date_range_label.setAlignment(Qt.AlignCenter)
        
        date_control_layout.addWidget(self.date_slider)
        date_control_layout.addWidget(self.date_range_label)
        control_layout.addLayout(date_control_layout)
        
        # 添加排序按钮
        self.sort_button = QPushButton("按日期排序")
        self.sort_button.setFixedWidth(120)
        self.sort_button.setStyleSheet("""
            QPushButton {
                background-color: #ECEFF1;
                border: 1px solid #CFD8DC;
                border-radius: 4px;
                padding: 4px 8px;
                color: #455A64;
            }
            QPushButton:hover {
                background-color: #CFD8DC;
            }
        """)
        self.sort_button.clicked.connect(self._sort_by_date)
        control_layout.addWidget(self.sort_button)

        # 添加一个复选框，决定升序还是降序
        self.sort_order = QCheckBox("降序排列")
        self.sort_order.setChecked(True)  # 默认降序（最新的在前面）
        control_layout.addWidget(self.sort_order)

        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)
        
        # 新闻列表
        self.news_list = QListWidget()
        self.news_list.setAlternatingRowColors(True)
        self.news_list.itemClicked.connect(self._on_item_clicked)
        # 移除上下文菜单相关代码
        # self.news_list.setContextMenuPolicy(Qt.CustomContextMenu)
        # self.news_list.customContextMenuRequested.connect(self._show_context_menu)
        splitter.addWidget(self.news_list)

        # 新闻预览
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        splitter.addWidget(self.preview)
        
        # 设置分割器比例
        splitter.setSizes([400, 200])  # 列表:预览 高度比例
        
        # 状态标签
        self.status_label = QLabel("加载新闻...")
        layout.addWidget(self.status_label)
    

    def set_read_ids(self, read_ids):
        """设置已读新闻ID集合
        
        Args:
            read_ids (set): 包含已读新闻链接的集合
        """
        self.read_news_ids = read_ids
        # 可以在这里触发一次列表刷新来立即应用样式，
        # 但更优的做法是在 update_news/_apply_date_filter 中直接应用
        # self._apply_date_filter() # 取消注释以立即刷新，但可能导致重复刷新

    def update_news(self, news_items):
        """更新新闻列表
        
        Args:
            news_items: 新闻条目列表
        """
        # 清空当前列表
        self.news_list.clear()
        
        # 保存原始新闻数据
        self.original_news = news_items
        
        # 应用当前时间范围筛选
        self._apply_date_filter()

    def _apply_date_filter(self):
        """应用日期范围筛选"""
        if not hasattr(self, 'original_news') or not self.original_news:
            return
            
        # 获取当前天数范围
        days = self.date_slider.value() if hasattr(self, 'date_slider') else 1
        
        # 计算截止日期
        now = datetime.now()
        cutoff_date = now - timedelta(days=days)
        
        # 筛选新闻
        filtered_news = []
        for news in self.original_news:
            pub_date = self._parse_date(news.get('pub_date', ''))
            if pub_date >= cutoff_date:
                filtered_news.append(news)
        
        # 保存当前显示的新闻数据
        self.current_news = filtered_news
        
        # 添加新闻项到列表
        for news in filtered_news:
            # 创建并添加新闻项
            item = QListWidgetItem()
            title = news.get('title', '无标题')
            source = news.get('source_name', '未知来源')
            raw_date_str = news.get('pub_date', '')
            # --- 新增：标准化日期显示 ---
            parsed_date = self._parse_date(raw_date_str)
            if parsed_date != datetime.min:
                # 如果解析成功，格式化为统一格式
                display_date = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
            else:
                # 如果解析失败，显示原始字符串
                display_date = raw_date_str
            # --- 新增结束 ---
            display_text = f"{title}\n[{source}] {display_date}" # 使用格式化后的日期
            item.setText(display_text)
            # 设置字体加粗
            font = QFont()
            # --- 应用已读状态 ---
            news_link = news.get('link')
            is_read = news_link and news_link in self.read_news_ids
            
            if is_read:
                font.setBold(False) # 已读新闻取消加粗
                item.setForeground(Qt.gray) # 设置为灰色
            else:
                font.setBold(True) # 未读新闻保持加粗
            # --- 已读状态应用结束 ---
            item.setFont(font)
            item.setData(Qt.UserRole, news)  # 存储完整新闻数据
            self.news_list.addItem(item)
        
        # 更新状态
        self.status_label.setText(f"显示最近{days}天内 {len(filtered_news)} 条新闻")
        self.date_range_label.setText(f"{days}天")

    def _on_date_range_changed(self, value):
        """处理日期范围滑块变化"""
        self._apply_date_filter()

    def update_date_range(self, days):
        """更新显示的日期范围
        Args:
            days (int): 要显示的天数范围，365表示全部
        """
        if not hasattr(self, 'date_range_label'):
            return
            
        if days == 365:
            self.date_range_label.setText("日期范围: 全部")
        else:
            self.date_range_label.setText(f"日期范围: 最近{days}天")
            item = NewsItem(news)
            self.news_list.addItem(item)
        
        # 更新状态标签
    def update_date_range(self, days):
        """更新显示的日期范围
        Args:
            days (int): 要显示的天数范围，365表示全部
        """
        if not hasattr(self, 'date_range_label'):
            return
            
        if days == 365:
            self.date_range_label.setText("日期范围: 全部")
        else:
            self.date_range_label.setText(f"日期范围: 最近{days}天")
        count = len(news_items)
        self.status_label.setText(f"共 {count} 条新闻")
        
        # 清空预览
        self.preview.setHtml("")
        
        # 发送更新信号
        self.news_updated.emit(news_items)
        
        self.logger.debug(f"更新了新闻列表，共 {count} 条")

    def _parse_date(self, date_str):
        """
        解析多种格式的日期字符串为datetime对象，确保所有返回的对象都是不带时区信息的
        
        Args:
            date_str: 日期字符串
            
        Returns:
            datetime: 解析后的datetime对象（不带时区信息），如果解析失败返回datetime.min
        """
        if not date_str:
            return datetime.min
        
        # 常见的日期格式列表
        date_formats = [
            # RFC 822 格式 (常见于RSS Feed)
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S",
            # ISO 格式
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            # 常见日期格式
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%d %b %Y %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d"
        ]
        
        # 尝试每一种格式
        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # 移除时区信息，确保返回不带时区的datetime
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                return dt
            except ValueError:
                continue
        
        # 如果标准格式都失败，尝试使用正则表达式提取日期
        try:
            # 查找类似 YYYY-MM-DD 或 YYYY/MM/DD 的模式
            date_match = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', date_str)
            if date_match:
                year, month, day = map(int, date_match.groups())
                return datetime(year, month, day)
            
            # 尝试提取英文月份格式，如 "25 Dec 2023"
            month_names = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            
            month_pattern = r'(\d{1,2})\s+([a-zA-Z]{3})\s+(\d{4})'
            date_match = re.search(month_pattern, date_str, re.IGNORECASE)
            if date_match:
                day, month_str, year = date_match.groups()
                month = month_names.get(month_str.lower()[:3], 1)
                return datetime(int(year), month, int(day))
        except:
            pass
        
        # 所有方法都失败，返回最小日期
        return datetime.min
    
    def _sort_by_date(self):
        """按日期排序新闻列表，使用增强的日期解析算法"""
        if not self.current_news:
            return
            
        # 复制一份新闻列表，避免直接修改原始数据
        sorted_news = self.current_news.copy()
        
        # 按发布日期排序
        try:
            # 检查是否需要降序（最新的在前面）
            reverse_order = self.sort_order.isChecked()
            
            # 定义排序键函数，解析日期
            def get_date(news_item):
                date_str = news_item.get('pub_date', '')
                return self._parse_date(date_str)
            
            # 使用增强的日期解析进行排序
            sorted_news.sort(key=get_date, reverse=reverse_order)
            
            # 更新显示
            self.update_news(sorted_news)
            
            # 更新状态
            order_text = "降序" if reverse_order else "升序"
            self.status_label.setText(f"已按日期{order_text}排列 {len(sorted_news)} 条新闻")
            self.logger.debug(f"新闻列表已按日期{order_text}排序")
        
        except Exception as e:
            self.status_label.setText(f"排序失败: {str(e)}")
            self.logger.error(f"新闻排序失败: {str(e)}")
    
    def _on_item_clicked(self, item):
        """处理列表项点击事件
        
        Args:
            item: 被点击的列表项
        """
        # 获取新闻数据
        news_data = item.data(Qt.UserRole)
        if not news_data:
            return
            
        # 更新预览
        self._update_preview(news_data)
        
        # 发送信号
        self.item_selected.emit(news_data)
        
        self.logger.debug(f"选择了新闻: {news_data.get('title', '')[:30]}...")
        # 记录浏览历史
        self._record_browsing_history(news_data)

    
    def _update_preview(self, news_data):
        """更新新闻预览
        
        Args:
            news_data: 新闻数据字典
        """
        title = news_data.get('title', '无标题')
        source = news_data.get('source_name', '未知来源')
        date = news_data.get('pub_date', '未知日期')
        description = news_data.get('description', '无内容')
        link = news_data.get('link', '')
        
        # 创建HTML内容
        html = f"""
        <h2>{title}</h2>
        <p><strong>来源:</strong> {source} | <strong>日期:</strong> {date}</p>
        <hr>
        <p>{description}</p>
        """
    # 移除 _show_context_menu 方法
    # def _show_context_menu(self, pos):
    #     ...
        
        if link:
            html += f'<p><a href="{link}" target="_blank">阅读原文</a></p>'
        
        # 设置HTML内容
        self.preview.setHtml(html)

    def _record_browsing_history(self, news_data):
        """记录浏览历史"""
        self.logger.debug(f"记录浏览历史: {news_data.get('title', '')[:30]}...")
        try:
            history = []
            # 确保目录存在
            os.makedirs(os.path.dirname(self.HISTORY_FILE), exist_ok=True)

            # 读取现有历史
            if os.path.exists(self.HISTORY_FILE):
                try:
                    with open(self.HISTORY_FILE, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                    if not isinstance(history, list): # 基本的类型检查
                        self.logger.warning(f"浏览历史文件格式不正确，已重置: {self.HISTORY_FILE}")
                        history = []
                except (json.JSONDecodeError, IOError) as e:
                    self.logger.error(f"读取浏览历史文件失败: {e}")
                    history = [] # 出错时重置

            # 准备新条目
            entry = {
                'title': news_data.get('title'),
                'link': news_data.get('link'),
                'source_name': news_data.get('source_name'),
                'pub_date': news_data.get('pub_date'), # 也记录原始发布日期
                'description': news_data.get('description'), # 记录描述以供预览
                'viewed_at': datetime.now().isoformat() # 使用 ISO 格式记录查看时间
            }

            # 检查是否已存在（基于链接），如果存在则移到最前
            link_to_check = entry.get('link')
            if link_to_check: # 仅当链接存在时才检查重复
                existing_indices = [i for i, item in enumerate(history) if item.get('link') == link_to_check]
                for i in sorted(existing_indices, reverse=True):
                    del history[i]

            # 添加到开头并限制长度
            history.insert(0, entry)
            history = history[:self.MAX_HISTORY_ITEMS]

            # 保存历史
            with open(self.HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

        except Exception as e:
            self.logger.error(f"保存浏览历史失败: {e}")

