"""
JSON Feed 新闻收集器

负责从单个 JSON Feed 源获取并解析新闻数据为标准字典格式。
参考规范: https://www.jsonfeed.org/version/1.1/
"""

import logging
import json
import time
import requests
from typing import List, Dict, Optional
from src.models import NewsSource
from datetime import datetime

# 尝试从 dateutil 解析日期，如果可用
try:
    from dateutil import parser as dateutil_parser
    _HAS_DATEUTIL = True
except ImportError:
    _HAS_DATEUTIL = False
    logging.warning("dateutil not found. Date parsing will be less robust. pip install python-dateutil")

class JSONFeedCollector:
    """
    JSON Feed 新闻收集器类。

    负责从遵循 JSON Feed 规范 (https://www.jsonfeed.org/version/1.1/) 的单个新闻源
    获取并解析新闻数据。此类是无状态的，每次调用 `collect` 方法时处理单个源。

    Attributes:
        logger: 用于记录日志的 logger 实例。
        session: 用于执行 HTTP 请求的 `requests.Session` 实例。
    """

    def __init__(self):
        """
        初始化 JSONFeedCollector。

        创建一个 `requests.Session` 并设置用户代理。
        """
        """初始化 JSON Feed 收集器"""
        self.logger = logging.getLogger('news_analyzer.collectors.json_feed')
        self.session = requests.Session() # Use a session for potential connection reuse
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 NewsAnalyzer/1.0'
        })
        self.logger.info("JSONFeedCollector initialized (stateless).")

    def _parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        (内部辅助方法) 尝试将多种格式的日期时间字符串解析为 ISO 8601 格式。

        优先使用 `dateutil` 库（如果可用）进行解析，以获得更好的兼容性。
        如果 `dateutil` 不可用或解析失败，则返回原始字符串。

        Args:
            date_str (Optional[str]): 可能包含日期时间的字符串。

        Returns:
            Optional[str]: 解析并格式化为 ISO 8601 的字符串，如果输入为 None 或解析失败
                           （且无 dateutil），则返回原始字符串或 None。
        """
        """尝试解析多种格式的日期时间字符串为 ISO 8601 格式。"""
        if not date_str:
            return None
        if _HAS_DATEUTIL:
            try:
                # dateutil 通常能处理 RFC3339 和许多其他格式
                dt = dateutil_parser.isoparse(date_str)
                # 返回标准化的 ISO 格式字符串 (保留时区信息)
                return dt.isoformat()
            except (ValueError, TypeError) as e:
                self.logger.warning(f"无法使用 dateutil 解析日期 '{date_str}': {e}. 将保留原始字符串。")
                # Fallback to returning original string if parsing fails
                return date_str
        else:
            # 如果没有 dateutil，只做基本检查并返回原始字符串
            # JSON Feed 要求 RFC3339，但我们保持灵活性
            self.logger.debug(f"dateutil 不可用，返回原始日期字符串: '{date_str}'")
            return date_str # Return original string

    def collect(self, source_config: NewsSource, **kwargs) -> List[Dict]:
        """
        从指定的 JSON Feed 源获取并解析新闻条目。

        通过 HTTP GET 请求获取 Feed 数据，解析 JSON，然后逐条解析 `items` 列表
        中的新闻条目，将其转换为标准化的字典格式。

        Args:
            source_config (NewsSource): 包含要获取的 Feed URL 和其他信息的配置对象。
            **kwargs: 接受额外参数，特别是 `cancel_checker` (一个 callable)，
                      用于在耗时操作中检查是否应取消操作。

        Returns:
            List[Dict]: 包含从 Feed 中成功解析的新闻条目的字典列表。
                       每个字典代表一篇文章，包含 'title', 'link', 'content', 'summary',
                       'publish_time', 'source_name' 等键。
                       如果获取、解析 Feed 或解析单个条目时发生错误，则可能返回空列表或部分结果。
        """
        items = []
        url = source_config.url
        if not url:
            self.logger.warning(f"JSON Feed 源 '{source_config.name}' 没有提供 URL")
            return []

        self.logger.info(f"开始从 JSON Feed 源获取: {source_config.name} ({url})")
        cancel_checker = kwargs.get('cancel_checker')

        try:
            response = self.session.get(url, timeout=20) # Increased timeout
            response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)

            # Check for cancellation after request but before processing
            if cancel_checker and cancel_checker():
                self.logger.info(f"收集操作被取消 (获取后): {source_config.name}")
                return []

            # 尝试解析 JSON
            try:
                feed_data = response.json()
            except json.JSONDecodeError as e:
                self.logger.error(f"解析 JSON 失败 for {source_config.name}: {e}. Content snippet: {response.text[:500]}...")
                return []

            # 验证基本结构 (至少需要 version 和 items)
            if not isinstance(feed_data, dict) or 'version' not in feed_data or 'items' not in feed_data:
                self.logger.warning(f"无效的 JSON Feed 结构 for {source_config.name}. 缺少 'version' 或 'items' 键。")
                return []

            if not isinstance(feed_data.get('items'), list):
                 self.logger.warning(f"JSON Feed 'items' 不是列表 for {source_config.name}.")
                 return []

            # 解析条目
            for item_data in feed_data.get('items', []):
                # Check for cancellation inside loop
                if cancel_checker and cancel_checker():
                    self.logger.info(f"收集操作在解析 JSON item 时被取消: {source_config.name}")
                    return items # Return partially collected items

                if not isinstance(item_data, dict):
                    self.logger.warning(f"跳过无效的 item (非字典): {item_data} in {source_config.name}")
                    continue

                news_item = self._parse_json_item(item_data, source_config, feed_data)
                if news_item:
                    items.append(news_item)

            self.logger.info(f"从 {source_config.name} 获取并解析了 {len(items)} 条新闻")

        except requests.exceptions.Timeout:
             self.logger.error(f"获取 {source_config.name} 时超时")
        except requests.exceptions.RequestException as e:
             self.logger.error(f"获取 {source_config.name} 时发生网络错误: {e}")
        except Exception as e:
            self.logger.error(f"获取或解析 {source_config.name} 时发生未知错误: {e}", exc_info=True)

        return items

    def _parse_json_item(self, item_data: Dict, source_config: NewsSource, feed_data: Dict) -> Optional[Dict]:
        """
        (内部辅助方法) 将单个 JSON Feed item 字典解析为标准化的新闻字典格式。

        提取 'id', 'title', 'url'/'external_url', 'content_html'/'content_text',
        'summary', 'date_published' 等字段，并进行必要的处理（如日期解析、生成备用标题）。

        Args:
            item_data (Dict): 从 JSON Feed 的 'items' 列表中获取的单个条目的字典。
            source_config (NewsSource): 当前处理的新闻源的配置对象，用于获取来源名称。
            feed_data (Dict): 顶层的 JSON Feed 数据字典（可能包含 feed 级别的元数据，当前未使用）。

        Returns:
            Optional[Dict]: 包含标准化新闻信息的字典，如果条目无效或缺少关键信息
                           （如 'id'，或者根据配置是否需要 'link'），则返回 None。
                           字典包含键: 'title', 'link', 'content', 'summary', 'publish_time',
                           'source_name', 'collected_at', 'raw_data'。
        """
        try:
            # 提取 ID (必需)
            item_id = item_data.get('id')
            if not item_id:
                self.logger.warning(f"Skipping JSON Feed item due to missing 'id'. Source: {source_config.name}")
                return None

            # 提取标题 (可选，但强烈推荐)
            title = item_data.get('title', '').strip()
            if not title:
                 # 尝试从 content 生成一个简短标题
                 content_html = item_data.get('content_html', '')
                 content_text = item_data.get('content_text', '')
                 if content_html:
                     # 简单处理：取前 50 个字符，移除 HTML 标签
                     import re
                     plain_text = re.sub('<[^<]+?>', '', content_html).strip()
                     title = (plain_text[:50] + '...') if len(plain_text) > 50 else plain_text
                 elif content_text:
                     title = (content_text[:50] + '...') if len(content_text) > 50 else content_text
                 else:
                     title = f"Untitled Item ({item_id})" # Fallback title
                 self.logger.debug(f"JSON Feed item missing title, generated: '{title}' for id {item_id}. Source: {source_config.name}")


            # 提取链接 (可选，优先 'url', 其次 'external_url')
            link = item_data.get('url', '').strip()
            if not link:
                link = item_data.get('external_url', '').strip()
            # 如果还没有链接，并且 id 看起来像 URL，则使用 id (不太常见)
            if not link and isinstance(item_id, str) and item_id.startswith(('http://', 'https://')):
                 link = item_id
                 self.logger.debug(f"Using item 'id' as link for '{title[:30]}...'")

            if not link:
                 self.logger.warning(f"Skipping JSON Feed item due to missing 'url' or 'external_url' for title '{title[:50]}...'. Source: {source_config.name}")
                 # 允许没有链接的文章存在，取决于应用需求
                 # return None # 取消注释则强制要求有链接

            # --- 提取内容和摘要 ---
            content = None
            summary = item_data.get('summary', '').strip() or None # Use None if empty string

            content_html = item_data.get('content_html', '').strip()
            content_text = item_data.get('content_text', '').strip()

            if content_html:
                content = content_html # 优先 HTML 内容
            elif content_text:
                content = content_text # 其次纯文本内容

            # 如果没有显式摘要，但有纯文本内容，可以截取作为摘要
            if not summary and content_text:
                 summary = (content_text[:250] + '...') if len(content_text) > 250 else content_text

            # --- 提取发布日期 ---
            # JSON Feed 标准是 RFC3339 字符串
            pub_date_str = item_data.get('date_published')
            parsed_date_str = self._parse_date(pub_date_str) # 尝试解析并标准化

            # --- 创建新闻条目字典 ---
            news_item = {
                'title': title,
                'link': link or f"internal:{item_id}", # 提供一个内部链接如果外部链接缺失
                'content': content,
                'summary': summary,
                'publish_time': parsed_date_str or pub_date_str, # 优先使用解析后的，否则用原始的
                'source_name': source_config.name,
                'collected_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'raw_data': json.dumps(item_data) # Store raw JSON item
            }
            return news_item

        except Exception as e:
            item_id_for_log = item_data.get('id', 'N/A')
            self.logger.error(f"解析 JSON Feed 条目失败 (id: {item_id_for_log}) from {source_config.name}: {e}", exc_info=True)
            return None

# Example Usage (for testing purposes)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    collector = JSONFeedCollector()

    # Example JSON Feed URL (replace with a real one for testing)
    # Daring Fireball: https://daringfireball.net/feeds/json
    # Maybe: https://www.jsonfeed.org/feed.json (official example)
    test_url = "https://daringfireball.net/feeds/json"
    test_source = NewsSource(id=1, name="Test JSON Feed", url=test_url, category="Tech", is_enabled=True)

    print(f"Testing with URL: {test_url}")
    collected_items = collector.collect(test_source)

    if collected_items:
        print(f"\nCollected {len(collected_items)} items:")
        for i, item in enumerate(collected_items[:3]): # Print first 3 items
            print(f"\n--- Item {i+1} ---")
            print(f"  Title: {item.get('title')}")
            print(f"  Link: {item.get('link')}")
            print(f"  Publish Time: {item.get('publish_time')}")
            print(f"  Summary: {item.get('summary')[:100]}...")
            # print(f"  Content: {item.get('content')[:100]}...")
            print(f"  Collected At: {item.get('collected_at')}")
    else:
        print("\nNo items collected or an error occurred.")