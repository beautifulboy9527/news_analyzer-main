"""
RSS新闻收集器 (Refactored - Stateless)

负责从单个RSS源获取并解析新闻数据为标准字典格式。
"""

import logging
import time
import ssl
import re
import socket
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Tuple, Any, Callable
from src.models import NewsSource
import feedparser
from datetime import datetime, timezone, timedelta
import requests
from dateutil import parser as dateutil_parser

from .base_collector import BaseCollector

# +++ Define tzinfos mapping +++
DEFAULT_TZINFOS = {
    "EST": timezone(timedelta(hours=-5)),
    "EDT": timezone(timedelta(hours=-4)),
    "CST": timezone(timedelta(hours=-6)),
    "CDT": timezone(timedelta(hours=-5)),
    "MST": timezone(timedelta(hours=-7)),
    "MDT": timezone(timedelta(hours=-6)),
    "PST": timezone(timedelta(hours=-8)),
    "PDT": timezone(timedelta(hours=-7)),
    "BST": timezone(timedelta(hours=1)),  # British Summer Time
    "GMT": timezone.utc,
    "CET": timezone(timedelta(hours=1)),
    "CEST": timezone(timedelta(hours=2)),
    # Add other common abbreviations as needed
}
# +++ End tzinfos mapping +++

class RSSCollector(BaseCollector):
    """
    RSS新闻收集器类 (Refactored - Stateless).
    从给定的 NewsSource 配置获取并解析 RSS/Atom feed。
    """
    # 定义 User-Agent
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 NewsAnalyzer/1.0'

    def __init__(self, config: Optional[Dict] = None):
        """初始化RSS收集器"""
        super().__init__(config if config else {})
        self.logger = logging.getLogger('news_analyzer.collectors.rss')
        # SSL context 可以在需要时按需创建，或者如果 feedparser 内部处理良好则可能不需要
        # self.ssl_context = ssl.create_default_context()
        # self.ssl_context.check_hostname = False
        # self.ssl_context.verify_mode = ssl.CERT_NONE
        self.logger.info("RSSCollector initialized.")

    def check_status(self, source: NewsSource, data_dir: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Checks the status of a single RSS source by trying to fetch its feed.

        Args:
            source: The NewsSource object for the RSS feed.
            data_dir: Optional data directory. (Corresponds to BaseCollector's data_dir)
            db_path: Optional database path. (Corresponds to BaseCollector's db_path)

        Returns:
            A dictionary containing:
            - 'source_name': Name of the source.
            - 'status': 'ok' or 'error'.
            - 'error': Error message if status is 'error', else None.
            - 'last_checked_time': datetime object of when the check was performed.
        """
        self.logger.info(f"检查 RSS 源状态: {source.name} ({source.url})")
        check_time = datetime.now()
        result = {
            'source_name': source.name,
            'status': 'error',
            'error': None,
            'last_checked_time': check_time
        }

        if not source.url:
            result['error'] = "源 URL 未配置"
            self.logger.warning(f"RSS 源 '{source.name}' 状态检查失败: {result['error']}")
            return result

        try:
            feed_data = feedparser.parse(source.url, agent=self.USER_AGENT)

            # Safely access 'status'
            status_code = feed_data.get('status')
            is_bozo = feed_data.get('bozo', 1) # Default to bozo=1 (True) if not present
            bozo_exception = feed_data.get('bozo_exception', 'Unknown parsing error')

            if status_code == 200 and not is_bozo:
                result['status'] = 'ok'
                self.logger.info(f"RSS 源 '{source.name}' 状态检查成功 (Status: {status_code}, Bozo: {is_bozo})")
            elif status_code is not None and status_code != 200:
                result['error'] = f"HTTP 状态码: {status_code}"
                self.logger.warning(f"RSS 源 '{source.name}' 状态检查失败: {result['error']}")
            elif is_bozo: # If status_code might be None but it's a bozo feed
                result['error'] = f"Feed 解析问题 (Bozo): {bozo_exception}"
                self.logger.warning(f"RSS 源 '{source.name}' 状态检查失败: {result['error']}")
            else: # Should not happen if status_code is None and not bozo, but as a fallback
                result['error'] = "无法确定Feed状态 (无状态码且非Bozo)"
                self.logger.warning(f"RSS 源 '{source.name}' 状态检查失败: {result['error']}")

        except Exception as e:
            error_msg = f"检查时发生网络或解析错误: {e}"
            result['error'] = error_msg
            self.logger.error(f"RSS 源 '{source.name}' 状态检查失败: {error_msg}", exc_info=True)
        return result

    def collect(self, source: NewsSource, 
                progress_callback: Optional[Callable[[int, int], None]] = None,
                cancel_checker: Optional[Callable[[], bool]] = None) -> List[Dict[str, Any]]:
        """
        从 RSS 源收集新闻条目。

        Args:
            source: 新闻源配置对象。
            progress_callback: 一个可选的回调函数，用于报告进度。
            cancel_checker: 一个可选的函数，调用它如果返回 True 则表示应取消操作。

        Returns:
            一个包含新闻条目字典的列表。
        """
        self.logger.info("RSSCOLLECTOR_COLLECT_METHOD_ENTERED") # MODIFIED: error -> info
        self.logger.info(f"开始收集 RSS 源: {source.name} ({source.url})")
        news_items = []
        source_url = source.url
        source_name = source.name

        if not source_url:
            self.logger.warning(f"RSS 源 '{source_name}' 没有配置 URL，跳过收集。")
            return []

        try:
            self.logger.debug(f"RSSCOLLECTOR_BEFORE_FEEDPARSER_PARSE: URL={source_url}") # MODIFIED: error -> debug
            feed_data = feedparser.parse(source_url, agent=self.USER_AGENT)
            
            # --- MODIFIED: Robust access to feed_data attributes ---
            feed_status = feed_data.get('status') # Use .get() for safer access
            feed_bozo = feed_data.get('bozo', 1) # Default to bozo=1 (True) if not present
            num_entries = len(feed_data.entries) if hasattr(feed_data, 'entries') and feed_data.entries is not None else 0

            self.logger.info(f"RSSCOLLECTOR_AFTER_FEEDPARSER_PARSE: Status={feed_status if feed_status is not None else 'N/A'}, Bozo={feed_bozo}, Entries={num_entries}") # MODIFIED: error -> info

            # Check if feed_data itself is None or empty, or if crucial attributes are missing after network error
            if not feed_data or not hasattr(feed_data, 'entries'):
                self.logger.error(f"RSS 源 '{source_name}' ({source_url}) feed_data 为空或缺少 'entries' 属性，可能由于网络请求失败。跳过处理。")
                if progress_callback: progress_callback(0,0)
                self.logger.info(f"RSSCOLLECTOR_COLLECT_METHOD_EXITING_DUE_TO_EMPTY_FEED_DATA") # MODIFIED: error -> info
                return []

            self.logger.info(f"RSS 源 '{source_name}' ({source_url}) 原始 feed 状态: status={feed_status if feed_status is not None else '未知'}, bozo={feed_bozo}, len(entries)={num_entries}")
            if hasattr(feed_data, 'headers'):
                 self.logger.debug(f"RSS 源 '{source_name}' 返回的 Headers: {feed_data.headers}")

            if feed_bozo: # feed_data.bozo is 1 if problem, 0 if not.
                bozo_exception = feed_data.get("bozo_exception", "未知解析问题")
                self.logger.warning(f"Feedparser 在解析 {source_url} 时遇到问题 (bozo=1)。异常: {bozo_exception}")

            # Handle cases where status might be None due to severe parsing/network errors
            if feed_status is None:
                self.logger.error(f"请求 RSS 源 '{source_name}' ({source_url}) 时未能获取 HTTP 状态码。可能存在严重网络或解析问题。")
                # Bozo exception might give more clues here.
                # Depending on strictness, we might return [] here.
                # For now, proceed if entries exist, but this is risky.
                if not num_entries: # If no status AND no entries, definitely bail.
                    self.logger.error(f"RSS 源 '{source_name}' ({source_url}) 无状态码且无条目，终止处理。")
                    if progress_callback: progress_callback(0,0)
                    self.logger.info(f"RSSCOLLECTOR_COLLECT_METHOD_EXITING_DUE_TO_NO_STATUS_AND_NO_ENTRIES") # MODIFIED: error -> info
                    return []
            elif feed_status not in [200, 301, 302, 304, 307, 308]: # 304 Not Modified 也是可接受的
                 self.logger.warning(f"请求 RSS 源 '{source_name}' ({source_url}) 时收到非成功状态码: {feed_status}")
                 # If status is an error (e.g. 4xx, 5xx), and we have no entries, likely a failure.
                 if not num_entries and (400 <= feed_status < 600):
                     self.logger.error(f"RSS 源 '{source_name}' ({source_url}) 返回错误状态码 {feed_status} 且无条目，终止处理。")
                     if progress_callback: progress_callback(0,0)
                     self.logger.info(f"RSSCOLLECTOR_COLLECT_METHOD_EXITING_DUE_TO_ERROR_STATUS_AND_NO_ENTRIES") # MODIFIED: error -> info
                     return []
            
            if num_entries == 0: # Use the safe num_entries
                self.logger.info(f"RSS源 '{source_name}' ({source_url}) 没有找到任何新闻条目。")
                # 调用一次 progress_callback 表示0/0完成
                if progress_callback:
                    progress_callback(0, 0)
                return []
            
            total_entries = num_entries # Use the safe num_entries
            self.logger.info(f"RSS源 '{source_name}' ({source_url}) 找到 {total_entries} 个条目。开始处理...")

            processed_links = set()
            for i, entry in enumerate(feed_data.entries):
                if cancel_checker and cancel_checker():
                    self.logger.info(f"RSS 收集 '{source_name}' 在处理条目 {i+1}/{total_entries} 时被取消。")
                    break 

                link = entry.get('link')
                title = entry.get('title', '无标题')

                if not link: # 如果链接为空，记录并跳过
                    self.logger.warning(f"RSS源 '{source_name}' 的条目 '{title[:50]}...' (索引 {i}) 缺少链接，已跳过。")
                    if progress_callback:
                        progress_callback(i + 1, total_entries)
                    continue
                
                if link in processed_links: # 避免在同一次收集中处理完全相同的链接
                    self.logger.debug(f"RSS源 '{source_name}' 的条目 '{title[:50]}...' (链接: {link}) 是重复链接，在本次采集中已跳过。")
                    if progress_callback:
                        progress_callback(i + 1, total_entries)
                    continue

                # 日期处理
                raw_pub_date = None
                publish_time_dt = None

                # 1. 尝试 feedparser 预解析的日期字段 (time.struct_time)
                parsed_date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']
                for field_name in parsed_date_fields:
                    if hasattr(entry, field_name) and entry[field_name]:
                        try:
                            # time.struct_time to datetime
                            # feedparser times are typically in UTC if timezone info is present in feed,
                            # or local time if not. mktime assumes local time if no tz info.
                            # For consistency, we should convert to aware datetime, preferably UTC.
                            # datetime.fromtimestamp(time.mktime(entry[field_name])) creates a naive local time.
                            # We need to make it timezone-aware, or ideally get it as UTC from feedparser directly if possible.
                            # feedparser usually returns UTC if the feed specifies it.
                            # Let's assume feedparser gives a struct_time that, when converted,
                            # should be treated as if it's UTC, or convert explicitly if it's naive.
                            # A safer approach is to use the raw string with dateutil_parser if available,
                            # as dateutil_parser handles timezones better.
                            # However, if _parsed is available, it means feedparser succeeded.

                            # Re-check raw string corresponding to the _parsed field for better timezone handling by dateutil
                            raw_field_name = field_name.replace('_parsed', '')
                            raw_pub_date_candidate = entry.get(raw_field_name)
                            if raw_pub_date_candidate:
                                self.logger.debug(f"RSS源 '{source_name}', 条目 '{title[:30]}...': 优先使用原始字符串 '{raw_pub_date_candidate}' (来自 '{raw_field_name}') 进行解析，因为找到了 '{field_name}'.")
                                raw_pub_date = raw_pub_date_candidate
                                break # Found a raw string associated with a parsed field, use this
                            else:
                                # Fallback to using the struct_time if raw string isn't available
                                dt_naive = datetime.fromtimestamp(time.mktime(entry[field_name]))
                                # Heuristic: If original feed had timezone, feedparser often converts to UTC for _parsed.
                                # If not, it might be naive. For safety, assume UTC if using _parsed directly.
                                publish_time_dt = dt_naive.replace(tzinfo=timezone.utc)
                                # MODIFIED: Changed from INFO to DEBUG as this is a fallback/direct conversion from struct_time
                                self.logger.debug(f"RSS源 '{source_name}', 条目 '{title[:30]}...': 从 '{field_name}' (time_struct) 解析得到日期: {publish_time_dt}")
                                raw_pub_date = publish_time_dt.isoformat() # Store ISO format if directly from struct_time
                                break
                        except Exception as e_parsed_date:
                            self.logger.warning(f"RSS源 '{source_name}', 条目 '{title[:30]}...': 从 '{field_name}' 解析日期失败: {e_parsed_date}")
                
                # 2. 如果上面没有通过 _parsed 字段的对应原始字符串找到 raw_pub_date, 再尝试标准原始字符串字段
                if not raw_pub_date:
                    standard_raw_fields = ["published", "updated", "created"]
                    for field_name in standard_raw_fields:
                        candidate = entry.get(field_name)
                        if candidate:
                            raw_pub_date = candidate
                            self.logger.debug(f"RSS源 '{source_name}', 条目 '{title[:30]}...': 使用标准字段 '{field_name}' 的原始日期字符串: '{raw_pub_date}'")
                            break
                
                # 3. 如果仍未找到，尝试其他常见非标准原始字符串字段
                if not raw_pub_date:
                    additional_raw_fields = ["pubDate", "dc:date", "date", "dcterms:created", "dcterms:modified"] # dc:date might be entry.get('dc_date') by feedparser
                    for field_name in additional_raw_fields:
                        candidate = entry.get(field_name)
                        # For "dc:date", feedparser might store it as "dc_date" or access via entry.get('terms', {}).get('created')
                        # This simplified check might not catch all namespaced tags perfectly without knowing feedparser's exact aliasing.
                        if not candidate and ":" in field_name: # Try replacing colon for common feedparser flattening
                             candidate = entry.get(field_name.replace(":", "_"))

                        if candidate:
                            raw_pub_date = candidate
                            self.logger.info(f"RSS源 '{source_name}', 条目 '{title[:30]}...': 使用非标准字段 '{field_name}' 的原始日期字符串: '{raw_pub_date}'")
                            break

                if not raw_pub_date:
                    self.logger.warning(f"RSS源 '{source_name}', 条目 '{title[:30]}...': 未找到任何可识别的日期字段. Entry keys: {list(entry.keys())}")
                    self.logger.debug(f"Full entry data for missing date: {entry}")
                else:
                    self.logger.debug(f"RSS源 '{source_name}', 条目 '{title[:30]}...': 最终选用的原始日期字符串进行解析: '{raw_pub_date}'")
                
                # 4. 解析最终选定的 raw_pub_date (如果之前没有从 _parsed 直接获得 publish_time_dt)
                if raw_pub_date and not publish_time_dt: # publish_time_dt is None if we came from raw strings
                    try:
                        publish_time_dt = dateutil_parser.parse(raw_pub_date, tzinfos=DEFAULT_TZINFOS)
                        # Ensure it's offset-aware, prefer UTC
                        if publish_time_dt.tzinfo is None or publish_time_dt.tzinfo.utcoffset(publish_time_dt) is None:
                            self.logger.debug(f"RSS源 '{source_name}', 条目 '{title[:30]}...': 解析后日期 {publish_time_dt} 是 naive, 附加 UTC 时区。")
                            publish_time_dt = publish_time_dt.replace(tzinfo=timezone.utc)
                        else:
                            publish_time_dt = publish_time_dt.astimezone(timezone.utc) # Convert to UTC
                        self.logger.debug(f"RSS源 '{source_name}', 条目 '{title[:30]}...': 解析后日期 (UTC): {publish_time_dt}")
                    except Exception as e_date:
                        self.logger.warning(f"RSS源 '{source_name}', 条目 '{title[:30]}...': 解析日期字符串 '{raw_pub_date}' 失败: {e_date}")
                        publish_time_dt = None # Ensure it's None if parsing fails
                
                pub_date_to_store = publish_time_dt # 直接存储 datetime 对象或 None

                summary = self._extract_summary(entry) # 保留原有的 summary 提取
                image_url = self._extract_image(entry) # 保留原有的 image 提取

                news_item = {
                    'source_name': source_name, # 使用从 source 对象获取的名称
                    'category': source.category if hasattr(source, 'category') and source.category else '未分类',
                    'title': title,
                    'link': link,
                    'summary': summary,
                    'content': entry.get('content', [{}])[0].get('value') if entry.get('content') else summary, # 尝试获取更完整的 content
                    'publish_time': pub_date_to_store, # 存储 datetime 对象或 None
                    'image_url': image_url,
                    'raw_data': { # 保持收集原始数据
                        'title': entry.get('title'),
                        'link': entry.get('link'),
                        'summary_detail': entry.get('summary_detail'), # feedparser 的 summary_detail
                        'summary': entry.get('summary'),
                        'published': entry.get('published'),
                        'updated': entry.get('updated'),
                        'created': entry.get('created'),
                        'author_detail': entry.get('author_detail'),
                        'tags': entry.get('tags'),
                        'content': entry.get('content'),
                        'enclosures': entry.get('enclosures'),
                        'media_content': entry.get('media_content'),
                        'media_thumbnail': entry.get('media_thumbnail'),
                    }
                }
                news_items.append(news_item)
                processed_links.add(link)

                if progress_callback:
                    progress_callback(i + 1, total_entries)
            
            # 如果循环因为取消而提前结束，确保最后一次进度被调用（如果需要精确到100%）
            if cancel_checker and cancel_checker() and progress_callback:
                 progress_callback(total_entries, total_entries) # 标记为完成（或已处理的总数）

        except Exception as e:
            self.logger.error(f"收集 RSS 源 '{source_name}' ({source_url}) 时发生主错误: {e}", exc_info=True)
            # Ensure progress_callback is called to signal completion/failure
            # Calculate total_entries safely in case feed_data was problematic
            _total_entries_for_cb = 0
            if 'feed_data' in locals() and hasattr(feed_data, 'entries') and feed_data.entries is not None:
                _total_entries_for_cb = len(feed_data.entries)
            
            if progress_callback:
                progress_callback(_total_entries_for_cb, _total_entries_for_cb) # Signal processed all (even if 0 or error caused premature exit)

            self.logger.error(f"RSSCOLLECTOR_COLLECT_METHOD_EXITING_DUE_TO_EXCEPTION: {e}")
            return [] 

        self.logger.info(f"完成收集 RSS 源: {source_name}, 获取了 {len(news_items)} 条有效新闻。")
        self.logger.info(f"RSSCOLLECTOR_COLLECT_METHOD_EXITING_{'NORMALLY' if not news_items and not source.url else ('WITH_ITEMS' if news_items else 'EARLY_EXIT')}" + (f" with {len(news_items)} items" if news_items else "")) # MODIFIED: error -> info
        return news_items

    def _standardize_title(self, title: Optional[str]) -> str:
        """尝试移除标题中常见的来源和日期时间前缀，仅保留核心标题"""
        if not title:
            return ""

        original_title = title # 保留原始标题用于比较和回退

        # 1. 尝试移除最复杂的模式: [Source] Date Time Zone Separator?
        #    (增加了对更多日期格式和可选逗号的匹配)
        pattern_complex = r'^\s*\[[^\]]+\]\s+(?:\w{3},?\s+\d{1,2}\s+\w{3,}\s+\d{4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s+[+-]\d{4}|\s+GMT)?\s*[:—-]?\s*'
        cleaned_title = re.sub(pattern_complex, '', title)

        # 2. 如果复杂模式未完全清理或未匹配，尝试移除简单的 [Source] 前缀
        pattern_simple_brackets = r'^\s*\[.*?\]\s*'
        if cleaned_title == original_title: # Only apply if complex pattern didn't match at all
            cleaned_title = re.sub(pattern_simple_brackets, '', original_title)
        else: # If complex pattern matched, clean potential remaining simple brackets
             cleaned_title = re.sub(pattern_simple_brackets, '', cleaned_title)


        # 3. 尝试移除末尾的 " | Source Name" 模式
        cleaned_title = re.sub(r'\s*\|\s*[\w\s.&]+$', '', cleaned_title) # Allow more chars in source name

        # 4. 移除特定已知来源名称后跟分隔符的情况 (更精确)
        known_sources = ["Sky Sports", "Fox Sports", "BBC News", "Reuters", "CNN", "ESPN", "The Hill", "TechCrunch", "Variety", "The Verge"] # 可扩展
        for src in known_sources:
             # 匹配 "Source Name : " 或 "Source Name - " 等
             pattern_specific = rf'^\s*{re.escape(src)}\s*[:—-]\s*'
             cleaned_title = re.sub(pattern_specific, '', cleaned_title, flags=re.IGNORECASE)


        # 5. 最后去除首尾空格
        final_title = cleaned_title.strip()

        # 6. 如果清理后变为空字符串，返回原始标题（去除首尾空格）
        if not final_title:
            return original_title.strip()

        return final_title

    def _parse_rss_item(self, item_elem: ET.Element, source_config: NewsSource) -> Optional[Dict]:
        """解析单个RSS条目为标准字典格式。

        Args:
            item_elem: RSS条目的XML元素。
            source_config: 来源配置对象 (NewsSource)。

        Returns:
            dict: 包含新闻信息的字典，如果缺少必要信息则返回 None。
        """
        try:
            # 提取标题和链接（必需字段）
            title_elem = item_elem.find('title')
            link_elem = item_elem.find('link')

            # Handle potential empty elements or missing text
            raw_title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""

            # Fallback for link in guid if link element is missing/empty
            if not link:
                guid_elem = item_elem.find('guid')
                if guid_elem is not None and guid_elem.text and guid_elem.get('isPermaLink', 'true') == 'true':
                     link = guid_elem.text.strip()
                     self.logger.debug(f"Using guid as link for '{raw_title[:30]}...'")

            if not raw_title or not link:
                self.logger.warning(f"Skipping RSS item due to missing title or link. Source: {source_config.name}")
                return None

            title = self._standardize_title(raw_title)
            if not title: # If standardization results in empty title, use original
                title = raw_title
                self.logger.warning(f"Title standardization resulted in empty string for '{raw_title}', using original. Source: {source_config.name}")


            # --- 提取内容和摘要 ---
            content = None
            summary = None

            # Namespace dictionary for content:encoded
            content_ns = {'content': 'http://purl.org/rss/1.0/modules/content/'}
            content_encoded_elem = item_elem.find('content:encoded', content_ns)

            desc_elem = item_elem.find('description')
            description_text = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else None

            if content_encoded_elem is not None and content_encoded_elem.text:
                content = content_encoded_elem.text.strip()
                # Use description as summary if available and different from content
                if description_text and description_text != content:
                    summary_text = re.sub(r'<[^>]+>', ' ', description_text) # Clean HTML
                    summary = re.sub(r'\s+', ' ', summary_text).strip()
            elif description_text:
                # If no content:encoded, use description
                # Decide if description is content or summary based on HTML presence
                if '<' in description_text and '>' in description_text:
                    content = description_text # Keep HTML
                    summary_text = re.sub(r'<[^>]+>', ' ', description_text)
                    summary = re.sub(r'\s+', ' ', summary_text).strip()[:250] + "..." # Truncate cleaned text for summary
                else:
                    summary = description_text # Pure text is summary
                    content = description_text # Also use as content if no other content found

            # --- 提取发布日期 ---
            pub_date_str = None
            date_elem = item_elem.find('pubDate')
            if date_elem is not None and date_elem.text:
                pub_date_str = date_elem.text.strip()

            # --- 创建新闻条目字典 ---
            news_item = {
                'title': title,
                'link': link,
                'content': content,
                'summary': summary,
                'publish_time': pub_date_str, # Keep as string, AppService will parse
                'source_name': source_config.name, # Use name from config
                # 'source_url': source_config.url, # Optional: Add if needed later
                # 'category': source_config.category, # Let AppService handle category assignment
                'collected_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'raw_data': ET.tostring(item_elem, encoding='unicode') # Optional: Store raw XML snippet
            }
            return news_item

        except Exception as e:
            raw_title_for_log = item_elem.findtext('title', 'N/A')
            self.logger.error(f"解析 RSS 条目失败 for '{raw_title_for_log[:50]}...' from {source_config.name}: {e}", exc_info=True)
            return None

    def _parse_atom_entry(self, entry_elem: ET.Element, source_config: NewsSource, ns: Dict) -> Optional[Dict]:
        """解析单个Atom条目为标准字典格式。

        Args:
            entry_elem: Atom条目的XML元素。
            source_config: 来源配置对象 (NewsSource)。
            ns: XML命名空间字典。

        Returns:
            dict: 包含新闻信息的字典，如果缺少必要信息则返回 None。
        """
        try:
            # 提取标题（必需字段）
            title_elem = entry_elem.find('atom:title', ns)
            if title_elem is None or not title_elem.text:
                 self.logger.warning(f"Skipping Atom entry due to missing title. Source: {source_config.name}")
                 return None
            raw_title = title_elem.text.strip()
            title = self._standardize_title(raw_title)
            if not title:
                title = raw_title # Fallback to original if standardization fails
                self.logger.warning(f"Title standardization resulted in empty string for '{raw_title}', using original. Source: {source_config.name}")


            # 提取链接 (Prefer alternate link if available)
            link = ""
            for link_elem in entry_elem.findall('atom:link', ns):
                rel = link_elem.get('rel')
                href = link_elem.get('href')
                if href:
                    if rel == 'alternate' or not link: # Prioritize alternate or take first href
                        link = href.strip()
                    if rel == 'alternate': # Found the best link type
                        break
            if not link:
                 self.logger.warning(f"Skipping Atom entry due to missing link for title '{title[:50]}...'. Source: {source_config.name}")
                 return None

            # --- 提取内容和摘要 ---
            content = None
            summary = None

            content_elem = entry_elem.find('atom:content', ns)
            summary_elem = entry_elem.find('atom:summary', ns)

            content_text = content_elem.text.strip() if content_elem is not None and content_elem.text else None
            summary_text = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else None

            if content_text:
                content = content_text # Assume Atom content is primary, keep HTML if present
                if summary_text and summary_text != content_text:
                    # Clean summary if it exists and is different
                    cleaned_summary_text = re.sub(r'<[^>]+>', ' ', summary_text)
                    summary = re.sub(r'\s+', ' ', cleaned_summary_text).strip()
            elif summary_text:
                 # If no content, use summary
                 if '<' in summary_text and '>' in summary_text: # Treat HTML summary as content
                     content = summary_text
                     cleaned_summary_text = re.sub(r'<[^>]+>', ' ', summary_text)
                     summary = re.sub(r'\s+', ' ', cleaned_summary_text).strip()[:250] + "..."
                 else: # Plain text summary is just summary
                     summary = summary_text
                     content = summary_text # Also use as content

            # --- 提取发布日期 (Try 'published' first, then 'updated') ---
            pub_date_str = None
            published_elem = entry_elem.find('atom:published', ns)
            updated_elem = entry_elem.find('atom:updated', ns)

            if published_elem is not None and published_elem.text:
                pub_date_str = published_elem.text.strip()
            elif updated_elem is not None and updated_elem.text:
                pub_date_str = updated_elem.text.strip()
                self.logger.debug(f"Using 'updated' date as publish time for '{title[:30]}...'")


            # --- 创建新闻条目字典 ---
            news_item = {
                'title': title,
                'link': link,
                'content': content,
                'summary': summary,
                'publish_time': pub_date_str, # Keep as string
                'source_name': source_config.name,
                # 'source_url': source_config.url,
                # 'category': source_config.category, # Let AppService handle
                'collected_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'raw_data': ET.tostring(entry_elem, encoding='unicode')
            }
            return news_item

        except Exception as e:
            raw_title_for_log = entry_elem.findtext('{http://www.w3.org/2005/Atom}title', 'N/A')
            self.logger.error(f"解析 Atom 条目失败 for '{raw_title_for_log[:50]}...' from {source_config.name}: {e}", exc_info=True)
            return None

    def _parse_pub_date(self, entry) -> Optional[str]:
        """
        Parses the publication date from an RSS/Atom entry.
        Tries 'published_parsed', 'updated_parsed', 'created_parsed'.
        Returns an ISO 8601 formatted string or None.
        """
        # This method is largely superseded by the logic in collect() using parse_datetime_utils.
        # However, feedparser does provide pre-parsed time_structs which can be robust.
        date_fields_parsed = ['published_parsed', 'updated_parsed', 'created_parsed']
        date_fields_raw = ['published', 'updated', 'created']
        
        parsed_time_struct = None
        raw_date_str_for_log = "N/A"

        for field in date_fields_parsed:
            if hasattr(entry, field) and entry[field]:
                parsed_time_struct = entry[field]
                raw_date_str_for_log = entry.get(field.replace('_parsed',''), "N/A") # Get corresponding raw string for logging
                self.logger.debug(f"使用 feedparser 的 '{field}' ({raw_date_str_for_log}) 得到 time_struct: {parsed_time_struct}")
                break
        
        if parsed_time_struct:
            try:
                # Convert time_struct to datetime object (UTC)
                dt_object = datetime.fromtimestamp(time.mktime(parsed_time_struct), timezone.utc)
                return dt_object.isoformat() # Return as ISO string
            except Exception as e:
                self.logger.warning(f"从 time_struct {parsed_time_struct} (来自字段 {field if parsed_time_struct else 'N/A'}) 转换到 datetime 失败: {e}")

        # Fallback to raw strings if no parsed versions are available or usable
        self.logger.debug(f"未能从 feedparser 的 _parsed 字段获取有效日期，尝试解析原始日期字符串。")
        for field_raw in date_fields_raw:
            raw_date_str = entry.get(field_raw)
            if raw_date_str:
                try:
                    # Use the robust dateutil parser for raw strings
                    from dateutil import parser as dateutil_parser # Local import
                    # Provide tzinfos for ambiguous timezone abbreviations
                    dt_object = dateutil_parser.parse(raw_date_str, tzinfos=DEFAULT_TZINFOS)
                    # Ensure datetime is timezone-aware (assume UTC if naive, or convert)
                    if dt_object.tzinfo is None or dt_object.tzinfo.utcoffset(dt_object) is None:
                        self.logger.debug(f"原始日期字符串 '{raw_date_str}' 解析为 naive datetime {dt_object}，假设为 UTC。")
                        dt_object = dt_object.replace(tzinfo=timezone.utc)
                    else: # Convert to UTC for consistency
                        dt_object = dt_object.astimezone(timezone.utc)
                    self.logger.debug(f"从原始字符串 '{raw_date_str}' (字段: {field_raw}) 解析并转换为UTC datetime: {dt_object}")
                    return dt_object.isoformat()
                except Exception as e:
                    self.logger.warning(f"使用 dateutil 解析原始日期字符串 '{raw_date_str}' (字段: {field_raw}) 失败: {e}")
        
        self.logger.warning(f"未能从条目中提取有效的发布日期: {entry.get('title', entry.get('link', 'Unknown Entry'))}")
        return None

    def _extract_summary(self, entry) -> Optional[str]:
        # Prioritize content if available, otherwise use summary
        # Often 'content' provides more detail than 'summary' in RSS
        if entry.get('content') and isinstance(entry.content, list) and len(entry.content) > 0:
            # Content can be a list of content objects
            # We'll take the first one and try to get its value
            content_obj = entry.content[0]
            if hasattr(content_obj, 'value'):
                summary = content_obj.value
                if summary: return summary.strip()

        # Fallback to summary or summary_detail
        summary = entry.get('summary', None)
        if summary:
            return summary.strip()
        
        summary_detail = entry.get('summary_detail', None)
        if summary_detail and hasattr(summary_detail, 'value'):
            summary = summary_detail.value
            if summary: return summary.strip()
            
        return None

    def _extract_image(self, entry) -> Optional[str]:
        # Check for media:thumbnail
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail and isinstance(entry.media_thumbnail, list):
            if entry.media_thumbnail[0].get('url'):
                return entry.media_thumbnail[0]['url']

        # Check for media:content with medium='image'
        if hasattr(entry, 'media_content') and entry.media_content and isinstance(entry.media_content, list):
            for media_item in entry.media_content:
                if media_item.get('medium') == 'image' and media_item.get('url'):
                    return media_item['url']
        
        # Check enclosures (common for images in RSS)
        if hasattr(entry, 'enclosures') and entry.enclosures and isinstance(entry.enclosures, list):
            for enclosure in entry.enclosures:
                if enclosure.get('type', '').startswith('image/') and enclosure.get('href'):
                    return enclosure['href']
        
        # Some feeds put image in description/summary/content as <img> tag
        # This would require HTML parsing, which can be complex and slow here.
        # For now, we rely on structured media fields.
        # A simple regex could be a light-touch alternative if needed:
        # summary_html = self._extract_summary(entry) or ''
        # content_html_list = entry.get('content', [])
        # full_text_html = summary_html
        # if content_html_list and isinstance(content_html_list[0], dict) and 'value' in content_html_list[0]:
        #     full_text_html += " " + content_html_list[0]['value']
        
        # img_match = re.search(r'<img[^>]+src="([^">]+)"', full_text_html, re.IGNORECASE)
        # if img_match:
        #     return img_match.group(1)
            
        return None
    
    # Placeholder for close, as BaseCollector defines it
    def close(self):
        self.logger.debug("RSSCollector.close() called. No specific resources to release for stateless RSS collector.")
        pass

    def _parse_datetime_flexible(self, date_string: str, source_name_for_log: str, title_for_log: str) -> Optional[datetime]:
        # This method is largely superseded by the logic in collect() using parse_datetime_utils.
        # However, feedparser does provide pre-parsed time_structs which can be robust.
        date_fields_parsed = ['published_parsed', 'updated_parsed', 'created_parsed']
        date_fields_raw = ['published', 'updated', 'created']
        
        parsed_time_struct = None
        raw_date_str_for_log = "N/A"

        for field in date_fields_parsed:
            if hasattr(entry, field) and entry[field]:
                parsed_time_struct = entry[field]
                raw_date_str_for_log = entry.get(field.replace('_parsed',''), "N/A") # Get corresponding raw string for logging
                self.logger.debug(f"使用 feedparser 的 '{field}' ({raw_date_str_for_log}) 得到 time_struct: {parsed_time_struct}")
                break
        
        if parsed_time_struct:
            try:
                # Convert time_struct to datetime object (UTC)
                dt_object = datetime.fromtimestamp(time.mktime(parsed_time_struct), timezone.utc)
                return dt_object
            except Exception as e:
                self.logger.warning(f"从 time_struct {parsed_time_struct} (来自字段 {field if parsed_time_struct else 'N/A'}) 转换到 datetime 失败: {e}")

        # Fallback to raw strings if no parsed versions are available or usable
        self.logger.debug(f"未能从 feedparser 的 _parsed 字段获取有效日期，尝试解析原始日期字符串。")
        for field_raw in date_fields_raw:
            raw_date_str = entry.get(field_raw)
            if raw_date_str:
                try:
                    # Use the robust dateutil parser for raw strings
                    from dateutil import parser as dateutil_parser # Local import
                    # Provide tzinfos for ambiguous timezone abbreviations
                    dt_object = dateutil_parser.parse(raw_date_str, tzinfos=DEFAULT_TZINFOS)
                    # Ensure datetime is timezone-aware (assume UTC if naive, or convert)
                    if dt_object.tzinfo is None or dt_object.tzinfo.utcoffset(dt_object) is None:
                        self.logger.debug(f"原始日期字符串 '{raw_date_str}' 解析为 naive datetime {dt_object}，假设为 UTC。")
                        dt_object = dt_object.replace(tzinfo=timezone.utc)
                    else: # Convert to UTC for consistency
                        dt_object = dt_object.astimezone(timezone.utc)
                    self.logger.debug(f"从原始字符串 '{raw_date_str}' (字段: {field_raw}) 解析并转换为UTC datetime: {dt_object}")
                    return dt_object
                except Exception as e:
                    self.logger.warning(f"使用 dateutil 解析原始日期字符串 '{raw_date_str}' (字段: {field_raw}) 失败: {e}")
        
        self.logger.warning(f"未能从条目中提取有效的发布日期: {entry.get('title', entry.get('link', 'Unknown Entry'))}")
        return None

# Potentially other helper methods like _standardize_title, _parse_rss_item, _parse_atom_entry
# can be kept if they are still useful or refactored.
# For now, focusing on the main collect method.