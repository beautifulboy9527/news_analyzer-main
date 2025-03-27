"""
新闻列表面板

显示新闻列表，并处理新闻项选择事件。
"""

import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QListWidget, 
                            QListWidgetItem, QLabel, QTextBrowser, 
                            QSplitter, QHBoxLayout)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont


class NewsItem(QListWidgetItem):
    """自定义新闻列表项类"""
    
    def __init__(self, news_data):
        """初始化新闻列表项
        
        Args:
            news_data: 新闻数据字典
        """
        super().__init__()
        self.news_data = news_data
        
        # 设置显示文本
        title = news_data.get('title', '无标题')
        source = news_data.get('source_name', '未知来源')
        date = news_data.get('pub_date', '')
        
        display_text = f"{title}\n[{source}] {date}"
        self.setText(display_text)
        
        # 设置字体
        font = QFont()
        font.setBold(True)
        self.setFont(font)


class NewsListPanel(QWidget):
    """新闻列表面板组件"""
    
    # 自定义信号：选择新闻项
    item_selected = pyqtSignal(dict)
    
    # 新增信号：新闻列表已更新
    news_updated = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.logger = logging.getLogger('news_analyzer.ui.news_list')
        self.current_news = []
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        # 创建主布局
        layout = QVBoxLayout(self)
        
        # 标题标签
        title_label = QLabel("新闻列表")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)
        
        # 新闻列表
        self.news_list = QListWidget()
        self.news_list.setAlternatingRowColors(True)
        self.news_list.itemClicked.connect(self._on_item_clicked)
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
    
    def update_news(self, news_items):
        """更新新闻列表
        
        Args:
            news_items: 新闻条目列表
        """
        # 清空当前列表
        self.news_list.clear()
        
        # 保存新闻数据
        self.current_news = news_items
        
        # 添加新闻项到列表
        for news in news_items:
            item = NewsItem(news)
            self.news_list.addItem(item)
        
        # 更新状态标签
        count = len(news_items)
        self.status_label.setText(f"共 {count} 条新闻")
        
        # 清空预览
        self.preview.setHtml("")
        
        # 发送更新信号
        self.news_updated.emit(news_items)
        
        self.logger.debug(f"更新了新闻列表，共 {count} 条")
    
    def _on_item_clicked(self, item):
        """处理列表项点击事件
        
        Args:
            item: 被点击的列表项
        """
        # 获取新闻数据
        news_data = item.news_data
        
        # 更新预览
        self._update_preview(news_data)
        
        # 发送信号
        self.item_selected.emit(news_data)
        
        self.logger.debug(f"选择了新闻: {news_data.get('title', '')[:30]}...")
    
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
        
        if link:
            html += f'<p><a href="{link}" target="_blank">阅读原文</a></p>'
        
        # 设置HTML内容
        self.preview.setHtml(html)