#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
News Detail ViewModel - MVVM模式中的ViewModel层，用于新闻详情对话框。
"""

from PyQt5.QtCore import QObject, pyqtSignal, pyqtProperty, QUrl # Changed PyQt6 to PyQt5
from dependency_injector.wiring import inject, Provide
from datetime import datetime
from typing import Optional

from src.models import NewsArticle # NewsItem is deprecated, use NewsArticle
from src.core.app_service import AppService
# from src.containers import Container # <-- 移动导入语句以解决循环导入
from src.utils.date_utils import format_datetime_friendly

class NewsDetailViewModel(QObject):
    """
    新闻详情对话框的ViewModel。
    负责处理新闻数据的加载、格式化和状态管理。
    """
    # --- Signals ---
    title_changed = pyqtSignal(str)
    content_changed = pyqtSignal(str)
    source_name_changed = pyqtSignal(str)
    publish_time_str_changed = pyqtSignal(str)
    link_changed = pyqtSignal(QUrl)
    metadata_changed = pyqtSignal(str) # 用于显示来源和时间的组合信息

    def __init__(self, news_item: NewsArticle, parent: Optional[QObject] = None):
        """
        初始化ViewModel。

        Args:
            news_item (NewsArticle): 要显示的新闻条目。
            parent (Optional[QObject]): 父对象。
        """
        super().__init__(parent)
        self._news_item = news_item
        self._app_service: AppService = Provide['.app_service'] # 依赖注入 (使用字符串 Provide)

        # 初始化内部状态
        self._title = ""
        self._content = ""
        self._source_name = ""
        self._publish_time_str = ""
        self._link = QUrl()
        self._metadata = ""

        self._update_properties()

    def _update_properties(self):
        """根据当前的 _news_item 更新所有属性并发出信号。"""
        if not self._news_item:
            return

        new_title = self._news_item.title or "无标题"
        if new_title != self._title:
            self._title = new_title
            self.title_changed.emit(self._title)

        # 优先使用 content，如果为空则使用 summary
        new_content = self._news_item.content or self._news_item.summary or "无内容"
        # TODO: 未来可能需要异步加载完整内容
        if new_content != self._content:
            self._content = new_content
            self.content_changed.emit(self._content)

        new_source_name = self._news_item.source_name or "未知来源"
        if new_source_name != self._source_name:
            self._source_name = new_source_name
            self.source_name_changed.emit(self._source_name)

        new_publish_time_str = format_datetime_friendly(self._news_item.publish_time) if self._news_item.publish_time else "未知时间"
        if new_publish_time_str != self._publish_time_str:
            self._publish_time_str = new_publish_time_str
            self.publish_time_str_changed.emit(self._publish_time_str)

        new_link = QUrl(self._news_item.link) if self._news_item.link else QUrl()
        if new_link != self._link:
            self._link = new_link
            self.link_changed.emit(self._link)

        new_metadata = f"来源: {self.source_name} | 发布时间: {self.publish_time_str}"
        if new_metadata != self._metadata:
            self._metadata = new_metadata
            self.metadata_changed.emit(self._metadata)


    # --- Properties ---
    @pyqtProperty(str, notify=title_changed)
    def title(self) -> str:
        return self._title

    @pyqtProperty(str, notify=content_changed)
    def content(self) -> str:
        # 注意：这里返回的是处理过的HTML或文本内容
        return self._content

    @pyqtProperty(str, notify=source_name_changed)
    def source_name(self) -> str:
        return self._source_name

    @pyqtProperty(str, notify=publish_time_str_changed)
    def publish_time_str(self) -> str:
        return self._publish_time_str

    @pyqtProperty(QUrl, notify=link_changed)
    def link(self) -> QUrl:
        return self._link

    @pyqtProperty(str, notify=metadata_changed)
    def metadata(self) -> str:
        return self._metadata

    # --- Slots (for future use, e.g., loading full content) ---
    # @pyqtSlot()
    # def load_full_content(self):
    #     # 示例：如果需要异步加载完整内容
    #     # self._app_service.fetch_full_content(self._news_item.link) ...
    #     # 然后更新 self._content 并发出 content_changed 信号
    #     pass

    def set_news_item(self, news_item: NewsArticle):
        """更新ViewModel使用的新闻条目。"""
        if news_item != self._news_item:
            self._news_item = news_item
            self._update_properties()