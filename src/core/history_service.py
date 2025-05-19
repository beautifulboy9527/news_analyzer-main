#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
用户活动服务模块 - 负责管理新闻的已读状态和浏览历史
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from PySide6.QtCore import QObject, Signal as pyqtSignal
from dataclasses import dataclass

from ..storage.news_storage import NewsStorage
from src.models import NewsArticle

@dataclass
class HistoryEntry:
    id: str  # Represents str(browsing_history_table_pk from DB)
    article_id: str # Represents str(articles_table_pk from DB) - FK
    article_title: str
    article_link: str
    viewed_at: datetime

class HistoryService(QObject):
    """
    管理新闻文章的已读状态和用户浏览历史记录。
    """
    browsing_history_updated = pyqtSignal()
    history_updated = pyqtSignal()

    def __init__(self, storage: NewsStorage, parent: Optional[QObject] = None):
        """
        初始化历史服务。

        Args:
            storage: 新闻存储服务实例。
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        if storage is None:
            self.logger.warning("NewsStorage instance is None. HistoryService will run in degraded mode.")
        self.storage = storage
        self.logger.debug("HistoryService initialized.")
        # Load read items on initialization (if needed, maybe handled elsewhere)
        # self._read_items_links = set(self.storage.get_read_items_links())

    def mark_as_read(self, link: str):
        """
        将指定链接的文章标记为已读。

        Args:
            link: 文章的唯一链接。
        """
        if not link or not self.storage:
            return
        try:
            self.storage.add_read_item(link)
            self.logger.debug(f"Marked item as read: {link}")
        except Exception as e:
            self.logger.error(f"Error marking item as read ({link}): {e}", exc_info=True)

    def mark_as_unread(self, link: str):
        """
        将指定链接的文章标记为未读。

        Args:
            link: 文章的唯一链接。
        """
        if not link or not self.storage:
            return
        try:
            self.storage.mark_item_as_unread(link)
            self.logger.debug(f"Marked item as unread: {link}")
        except Exception as e:
            self.logger.error(f"Error marking item as unread ({link}): {e}", exc_info=True)

    def is_read(self, link: str) -> bool:
        """
        检查指定链接的文章是否已读。

        Args:
            link: 文章的唯一链接。

        Returns:
            如果文章已读则返回 True，否则返回 False。
        """
        if not link or not self.storage:
            return False
        try:
            return self.storage.is_item_read(link)
        except Exception as e:
            self.logger.error(f"Error checking read status for item ({link}): {e}", exc_info=True)
            return False

    def add_history_item(self, news_article: NewsArticle):
        """添加浏览历史记录。

        Args:
            news_article: 要添加历史记录的 NewsArticle 对象 (包含 ID)。
        """
        if not news_article or news_article.id is None:
            self.logger.warning(f"无法添加历史记录: news_article 对象无效或缺少 ID。 Link: {news_article.link if news_article else 'N/A'}")
            return

        try:
            article_id = news_article.id # Directly use the ID from the object
            timestamp = datetime.now()

            self.logger.debug(f"尝试添加浏览历史: Article ID: {article_id}, Link: {news_article.link}, Timestamp: {timestamp}")

            # 检查是否已存在相同的历史记录（避免短时间内重复添加）
            # 可以根据需要调整检查逻辑，例如只检查最近几分钟的记录
            existing_record = self.storage.get_latest_history_by_article_id(article_id)
            if existing_record and (timestamp - existing_record['view_time']).total_seconds() < 60: # 60秒内不重复添加
                self.logger.debug(f"最近已记录过 Article ID: {article_id} 的浏览历史，跳过重复添加。")
                return

            # 插入新的历史记录
            self.storage.add_browsing_history(article_id, timestamp)
            self.logger.info(f"成功添加浏览历史记录: Article ID: {article_id}, Link: {news_article.link}")

            # 发射信号通知历史记录已更新
            self.history_updated.emit()
            self.logger.debug("history_updated signal emitted from HistoryService.")

        except Exception as e:
            self.logger.error(f"记录浏览历史时出错 {news_article.link}: {e}", exc_info=True)
            # Optionally re-raise or handle the error further

    def get_browsing_history(self, days_limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieves browsing history, optionally limited by days."""
        try:
            history_data = self.storage.get_browsing_history(days_limit=days_limit)
            self.logger.info(f"Retrieved {len(history_data)} history entries (days_limit: {days_limit} days)." )
            return history_data
        except Exception as e:
            self.logger.error(f"Failed to retrieve browsing history: {e}", exc_info=True)
            return []

    def clear_browsing_history(self):
        """Clears all browsing history."""
        try:
            self.storage.clear_browsing_history()
            self.logger.info("Cleared all browsing history.")
            self.history_updated.emit() # Emit signal after clearing
        except Exception as e:
            self.logger.error(f"Failed to clear browsing history: {e}", exc_info=True)

    # --- Read Status Management --- (Potentially belongs here or in a separate ReadStatusService)
    def mark_item_as_read(self, article_link: str):
        """Marks an article as read in storage."""
        if not article_link:
            self.logger.warning("Attempted to mark as read with empty link.")
            return
        try:
            article_id = self.storage.get_article_id_by_link(article_link)
            if article_id:
                self.storage.mark_article_as_read(article_id, True)
                self.logger.debug(f"Marked article as read in storage: ID={article_id}, Link={article_link}")
                # Optionally emit a signal if needed: self.read_status_changed.emit(article_link, True)
            else:
                self.logger.warning(f"Cannot mark as read: Article not found in DB for link {article_link}")
        except Exception as e:
            self.logger.error(f"Failed to mark article as read for link {article_link}: {e}", exc_info=True)

    def is_item_read(self, article_link: str) -> bool:
        """Checks if an article is marked as read in storage."""
        if not article_link:
            return False
        try:
            article_id = self.storage.get_article_id_by_link(article_link)
            if article_id:
                return self.storage.is_article_read(article_id)
            else:
                return False # Article not found, so not read
        except Exception as e:
            self.logger.error(f"Failed to check read status for link {article_link}: {e}", exc_info=True)
            return False

    def remove_history_item(self, history_item_id: str) -> None:
        """
        根据历史记录条目的数据库ID删除指定的历史记录。
        Replaces old delete_history_entry (which used link).
        history_item_id is the string representation of the history record's database primary key.
        """
        if not history_item_id or not self.storage:
            self.logger.warning("Cannot remove history item: invalid ID or no storage.")
            return
        
        self.logger.debug(f"Attempting to remove history item with ID: {history_item_id}")
        try:
            db_id = int(history_item_id)
            self.storage.delete_browsing_history_item(history_id=db_id)
            self.logger.info(f"History item with ID '{history_item_id}' removed.")
            self.browsing_history_updated.emit()
        except ValueError:
            self.logger.error(f"Invalid history_item_id format: '{history_item_id}'. Must be an integer string.")
        except Exception as e:
            self.logger.error(f"Error deleting history item (ID: {history_item_id}): {e}", exc_info=True)

    def clear_all_history_items(self) -> None:
        """
        清空所有浏览历史记录。
        Replaces old clear_browse_history.
        """
        if not self.storage:
            self.logger.warning("Cannot clear history: no storage service.")
            return

        self.logger.debug("Attempting to clear all history items.")
        try:
            self.storage.clear_all_browsing_history()
            self.logger.info("All browsing history items have been cleared.")
            self.browsing_history_updated.emit()
        except Exception as e:
            self.logger.error(f"Error clearing all browsing history: {e}", exc_info=True)

    def add_analysis_entry(self, entry_data: Dict):
        pass # Placeholder to fix indentation error. Original logic might be missing.

        # ... new code ... # This comment might indicate incomplete code or future plans 
        # END OF FILE HERE 