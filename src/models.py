#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据模型模块 - 定义应用程序中使用的数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import json

@dataclass
class NewsSource:
    """新闻源数据模型"""
    name: str
    type: str  # 例如 'rss', 'pengpai'
    id: Optional[int] = None # Database primary key
    url: Optional[str] = None # 对于非URL源（如澎湃），可以为None
    category: str = "未分类"
    enabled: bool = True
    is_user_added: bool = False # 标记是否为用户添加
    last_update: Optional[datetime] = None # 最后一次成功获取到新文章的时间
    error_count: int = 0
    last_error: Optional[str] = None # 作为 error_message 使用
    last_checked_time: Optional[datetime] = None # 最后一次检查源状态的时间
    status: str = "unchecked" # 源的状态: 'ok', 'error', 'unchecked'
    notes: Optional[str] = None # 添加备注字段
    custom_config: Optional[Dict[str, Any]] = field(default_factory=dict) # Changed from selector_config, more generic
    consecutive_error_count: int = 0 # 新增：连续错误计数

    def to_storage_dict(self) -> dict:
        """Converts NewsSource object to a dictionary suitable for NewsStorage, serializing custom_config."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "url": self.url,
            "category_name": self.category, # Map to category_name for NewsStorage
            "is_enabled": self.enabled,
            # is_user_added is not directly in news_sources table schema in DB
            "last_checked_time": self.last_checked_time.isoformat() if self.last_checked_time else None,
            "notes": self.notes,
            # status, last_error, error_count, consecutive_error_count are not in current news_sources DB schema
            "custom_config": json.dumps(self.custom_config) if self.custom_config else None
        }

@dataclass
class NewsArticle:
    """新闻文章数据模型"""
    # Non-default fields first
    title: str
    link: str
    source_name: str # 来源名称，例如 '澎湃新闻' 或 RSS源的名称
    id: Optional[int] = None # Database primary key

    # Default fields follow
    content: Optional[str] = None # 完整内容，可能需要单独加载
    summary: Optional[str] = None # 摘要或部分内容
    publish_time: Optional[datetime] = None
    category: str = "未分类"
    image_url: Optional[str] = None
    author: Optional[str] = None  # 新增：作者
    language: str = "unknown"     # 新增：语言，默认为 unknown
    tags: List[str] = field(default_factory=list)  # 新增：标签列表
    is_read: bool = False # 用户是否已阅读
    created_at: Optional[datetime] = None  # 新增：条目创建时间
    updated_at: Optional[datetime] = None  # 新增：条目更新时间
    raw_data: dict = field(default_factory=dict) # 存储原始解析数据，方便调试

    def to_dict(self) -> dict:
        """将 NewsArticle 对象转换为字典，用于序列化。"""
        data = {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "source_name": self.source_name,
            "content": self.content,
            "summary": self.summary,
            "publish_time": self.publish_time.isoformat() if self.publish_time else None,
            "category": self.category,
            "image_url": self.image_url,
            "author": self.author, # 新增
            "language": self.language, # 新增
            "tags": self.tags, # 新增
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None, # 新增
            "updated_at": self.updated_at.isoformat() if self.updated_at else None, # 新增
            # raw_data is already a dict, no need to include here unless specifically needed
        }
        # Optionally, include raw_data if needed for saving:
        # data['raw_data'] = self.raw_data
        return data

@dataclass
class NewsItem(NewsArticle):
    """包含状态信息的新闻条目"""
    is_new: bool = False # 标记是否为本次刷新中新增
    is_read: bool = False # 标记用户是否已阅读

@dataclass
class ChatMessage:
    """聊天消息数据模型"""
    role: str  # 'user', 'assistant', or 'system'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
