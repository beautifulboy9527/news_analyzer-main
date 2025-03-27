"""
RSS新闻收集器

负责从RSS源获取新闻数据。
"""

import logging
import time
import ssl
import re
from urllib.request import urlopen, Request
from urllib.error import URLError
import xml.etree.ElementTree as ET


class RSSCollector:
    """RSS新闻收集器类"""
    
    def __init__(self):
        """初始化RSS收集器"""
        self.logger = logging.getLogger('news_analyzer.collectors.rss')
        self.sources = []
        self.news_cache = []
        
        # 创建SSL上下文以处理HTTPS请求
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
    
    def add_source(self, url, name=None, category="未分类", is_user_added=False):
        """添加RSS新闻源
        
        Args:
            url: RSS源URL
            name: 来源名称（可选）
            category: 分类名称（可选）
            is_user_added: 是否为用户手动添加
        """
        if not url:
            raise ValueError("URL不能为空")
        
        # 如果没有提供名称，使用URL作为默认名称
        if not name:
            name = url.split("//")[-1].split("/")[0]
        
        # 检查是否已存在相同URL的源
        for source in self.sources:
            if source['url'] == url:
                self.logger.warning(f"RSS源已存在: {url}")
                return
        
        # 添加新源
        self.sources.append({
            'url': url,
            'name': name,
            'category': category,
            'is_user_added': is_user_added
        })
        
        self.logger.info(f"添加RSS源: {name} ({url}), 分类: {category}")
    
    def fetch_from_source(self, url):
        """从特定RSS源获取新闻
        
        Args:
            url: RSS源URL
            
        Returns:
            list: 新闻条目列表
        """
        source = None
        for s in self.sources:
            if s['url'] == url:
                source = s
                break
        
        if not source:
            self.logger.warning(f"未找到RSS源: {url}")
            return []
        
        return self._fetch_rss(source)
    
    def fetch_all(self):
        """从所有RSS源获取新闻
        
        Returns:
            list: 新闻条目列表
        """
        all_news = []
        
        for source in self.sources:
            try:
                items = self._fetch_rss(source)
                all_news.extend(items)
                self.logger.info(f"从 {source['name']} 获取了 {len(items)} 条新闻")
            except Exception as e:
                self.logger.error(f"从 {source['name']} 获取新闻失败: {str(e)}")
        
        # 去重
        unique_news = self._remove_duplicates(all_news)
        
        # 更新缓存
        self.news_cache = unique_news
        
        return unique_news
    
    def get_all_news(self):
        """获取所有缓存的新闻
        
        Returns:
            list: 新闻条目列表
        """
        return self.news_cache
    
    def get_news_by_category(self, category):
        """按分类获取新闻
        
        Args:
            category: 分类名称
            
        Returns:
            list: 该分类下的新闻条目列表
        """
        if not category or category == "所有":
            return self.news_cache
        
        return [item for item in self.news_cache if item.get('category') == category]
    
    def search_news(self, query):
        """搜索新闻
        
        Args:
            query: 搜索关键词
            
        Returns:
            list: 匹配的新闻条目列表
        """
        if not query:
            return self.news_cache
        
        query_lower = query.lower()
        results = []
        
        for item in self.news_cache:
            title = item.get('title', '').lower()
            description = item.get('description', '').lower()
            
            if query_lower in title or query_lower in description:
                results.append(item)
        
        return results
    
    def get_sources(self):
        """获取所有RSS源
        
        Returns:
            list: RSS源列表
        """
        return self.sources
    
    def get_categories(self):
        """获取所有分类
        
        Returns:
            list: 分类名称列表
        """
        categories = set()
        for source in self.sources:
            categories.add(source['category'])
        return sorted(list(categories))
    
    def _fetch_rss(self, source):
        """从RSS源获取新闻
        
        Args:
            source: 新闻源信息字典
            
        Returns:
            list: 新闻条目列表
        """
        items = []
        
        try:
            # 创建带User-Agent的请求以避免被屏蔽
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            req = Request(source['url'], headers=headers)
            
            # 获取RSS内容
            with urlopen(req, context=self.ssl_context, timeout=10) as response:
                rss_content = response.read().decode('utf-8', errors='ignore')
            
            # 解析XML
            root = ET.fromstring(rss_content)
            
            # 处理不同的RSS格式
            if root.tag == 'rss':
                # 标准RSS格式
                channel = root.find('channel')
                if channel is not None:
                    for item in channel.findall('item'):
                        news_item = self._parse_rss_item(item, source)
                        if news_item:
                            items.append(news_item)
            
            elif root.tag.endswith('feed'):
                # Atom格式
                for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                    news_item = self._parse_atom_entry(entry, source)
                    if news_item:
                        items.append(news_item)
            
            self.logger.info(f"从 {source['name']} 获取了 {len(items)} 条新闻")
            
        except Exception as e:
            self.logger.error(f"获取 {source['name']} 的新闻失败: {str(e)}")
            raise
        
        return items
    
    def _parse_rss_item(self, item, source):
        """解析RSS条目
        
        Args:
            item: RSS条目XML元素
            source: 来源信息
            
        Returns:
            dict: 新闻条目字典
        """
        try:
            # 提取标题和链接（必需字段）
            title_elem = item.find('title')
            link_elem = item.find('link')
            
            if title_elem is None or link_elem is None:
                return None
            
            title = title_elem.text or ""
            link = link_elem.text or ""
            
            if not title or not link:
                return None
            
            # 提取描述和发布日期（可选字段）
            description = ""
            desc_elem = item.find('description')
            if desc_elem is not None and desc_elem.text:
                # 简单清理HTML标签
                description = re.sub(r'<[^>]+>', ' ', desc_elem.text)
                description = re.sub(r'\s+', ' ', description).strip()
            
            pub_date = ""
            date_elem = item.find('pubDate')
            if date_elem is not None and date_elem.text:
                pub_date = date_elem.text
            
            # 创建新闻条目
            return {
                'title': title,
                'link': link,
                'description': description,
                'pub_date': pub_date,
                'source_name': source['name'],
                'source_url': source['url'],
                'category': source['category'],
                'collected_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            self.logger.error(f"解析RSS条目失败: {str(e)}")
            return None
    
    def _parse_atom_entry(self, entry, source):
        """解析Atom条目
        
        Args:
            entry: Atom条目XML元素
            source: 来源信息
            
        Returns:
            dict: 新闻条目字典
        """
        try:
            # 提取标题（必需字段）
            title_elem = entry.find('{http://www.w3.org/2005/Atom}title')
            if title_elem is None:
                return None
            
            title = title_elem.text or ""
            
            # 提取链接
            link = ""
            link_elem = entry.find('{http://www.w3.org/2005/Atom}link')
            if link_elem is not None:
                link = link_elem.get('href', '')
            
            if not title or not link:
                return None
            
            # 提取内容和发布日期
            content = ""
            content_elem = entry.find('{http://www.w3.org/2005/Atom}content')
            if content_elem is not None and content_elem.text:
                # 简单清理HTML标签
                content = re.sub(r'<[^>]+>', ' ', content_elem.text)
                content = re.sub(r'\s+', ' ', content).strip()
            
            # 如果没有内容，尝试使用摘要
            if not content:
                summary_elem = entry.find('{http://www.w3.org/2005/Atom}summary')
                if summary_elem is not None and summary_elem.text:
                    content = re.sub(r'<[^>]+>', ' ', summary_elem.text)
                    content = re.sub(r'\s+', ' ', content).strip()
            
            pub_date = ""
            date_elem = entry.find('{http://www.w3.org/2005/Atom}published')
            if date_elem is not None and date_elem.text:
                pub_date = date_elem.text
            
            # 创建新闻条目
            return {
                'title': title,
                'link': link,
                'description': content,
                'pub_date': pub_date,
                'source_name': source['name'],
                'source_url': source['url'],
                'category': source['category'],
                'collected_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            self.logger.error(f"解析Atom条目失败: {str(e)}")
            return None
    
    def _remove_duplicates(self, news_items):
        """移除重复的新闻条目
        
        Args:
            news_items: 新闻条目列表
            
        Returns:
            list: 去重后的新闻条目列表
        """
        unique_items = {}
        
        for item in news_items:
            # 使用标题作为去重键
            key = item.get('title', '')
            if key and key not in unique_items:
                unique_items[key] = item
        
        return list(unique_items.values())