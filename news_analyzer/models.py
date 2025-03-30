#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据模型模块 - 定义应用程序中使用的数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class NewsSource:
    """新闻源数据模型"""
    name: str
    type: str  # 例如 'rss', 'pengpai'
    url: Optional[str] = None # 对于非URL源（如澎湃），可以为None
    category: str = "未分类"
    enabled: bool = True
    is_user_added: bool = False # 标记是否为用户添加
    last_update: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    notes: Optional[str] = None # 添加备注字段

@dataclass
class NewsArticle:
    """新闻文章数据模型"""
    # Non-default fields first
    title: str
    link: str
    source_name: str # 来源名称，例如 '澎湃新闻' 或 RSS源的名称

    # Default fields follow
    content: Optional[str] = None # 完整内容，可能需要单独加载
    summary: Optional[str] = None # 摘要或部分内容
    publish_time: Optional[datetime] = None
    category: str = "未分类"
    # 可以添加其他字段，如作者、标签等
    raw_data: dict = field(default_factory=dict) # 存储原始解析数据，方便调试