"""
RSS新闻收集器 (Refactored - Stateless)

负责从单个RSS源获取并解析新闻数据为标准字典格式。
"""

import logging
import time
import ssl
import re
from urllib.request import urlopen, Request
from urllib.error import URLError
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from src.models import NewsSource

class RSSCollector:
    """
    RSS新闻收集器类 (Refactored - Stateless).
    从给定的 NewsSource 配置获取并解析 RSS/Atom feed。
    """

    def __init__(self):
        """初始化RSS收集器"""
        self.logger = logging.getLogger('news_analyzer.collectors.rss')
        # 创建SSL上下文以处理HTTPS请求
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        self.logger.info("RSSCollector initialized (stateless).")

    def collect(self, source_config: NewsSource, **kwargs) -> List[Dict]:
        """从单个RSS/Atom源获取新闻。

        Args:
            source_config: 新闻源配置对象 (NewsSource)。
            **kwargs: 预留参数，例如 cancel_checker。

        Returns:
            list: 包含新闻信息的原始字典列表。如果获取或解析失败则返回空列表。
        """
        items = []
        url = source_config.url
        if not url:
            self.logger.warning(f"RSS 源 '{source_config.name}' 没有提供 URL")
            return []

        self.logger.info(f"开始从 RSS/Atom 源获取: {source_config.name} ({url})")
        try:
            # 创建带User-Agent的请求以避免被屏蔽
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            req = Request(url, headers=headers)

            # 获取内容
            with urlopen(req, context=self.ssl_context, timeout=15) as response: # Increased timeout slightly
                # Check for cancellation if checker is provided
                cancel_checker = kwargs.get('cancel_checker')
                if cancel_checker and cancel_checker():
                    self.logger.info(f"收集操作被取消: {source_config.name}")
                    return [] # Return empty list if cancelled during fetch

                # Read and decode content
                try:
                    # Try UTF-8 first
                    rss_content = response.read().decode('utf-8')
                except UnicodeDecodeError:
                    self.logger.warning(f"UTF-8解码失败，尝试使用 {response.headers.get_content_charset('latin-1')} 解码: {source_config.name}")
                    # Fallback using charset from headers or latin-1
                    response.seek(0) # Reset read pointer
                    rss_content = response.read().decode(response.headers.get_content_charset('latin-1'), errors='ignore')


            # Check for cancellation again after fetch
            if cancel_checker and cancel_checker():
                self.logger.info(f"收集操作被取消: {source_config.name}")
                return []

            # 解析XML
            try:
                root = ET.fromstring(rss_content)
            except ET.ParseError as pe:
                self.logger.error(f"解析XML失败 for {source_config.name}: {pe}. Content snippet: {rss_content[:500]}...")
                # Attempt to clean problematic characters (optional, can be complex)
                # rss_content_cleaned = re.sub(r'[^\x09\x0A\x0D\x20-\x7E\x85\xA0-\uD7FF\uE000-\uFFFD]', '', rss_content)
                # try:
                #     root = ET.fromstring(rss_content_cleaned)
                #     self.logger.info(f"Successfully parsed after cleaning control characters for {source_config.name}")
                # except ET.ParseError as pe_cleaned:
                #     self.logger.error(f"Parsing still failed after cleaning for {source_config.name}: {pe_cleaned}")
                #     return [] # Return empty if parsing fails
                return [] # Return empty if parsing fails


            # 处理不同的格式
            if root.tag == 'rss':
                # 标准RSS格式
                channel = root.find('channel')
                if channel is not None:
                    for item_elem in channel.findall('item'):
                        # Check for cancellation inside loop
                        if cancel_checker and cancel_checker():
                            self.logger.info(f"收集操作在解析RSS item时被取消: {source_config.name}")
                            return items # Return partially collected items if cancelled mid-parse

                        news_item = self._parse_rss_item(item_elem, source_config)
                        if news_item:
                            items.append(news_item)

            elif root.tag.endswith('feed'): # More robust check for Atom namespace
                # Atom格式 (Handle namespace properly)
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                for entry_elem in root.findall('atom:entry', ns):
                     # Check for cancellation inside loop
                    if cancel_checker and cancel_checker():
                        self.logger.info(f"收集操作在解析Atom entry时被取消: {source_config.name}")
                        return items # Return partially collected items

                    news_item = self._parse_atom_entry(entry_elem, source_config, ns) # Pass namespace
                    if news_item:
                        items.append(news_item)
            else:
                 self.logger.warning(f"未知的 Feed 根标签 '{root.tag}' for {source_config.name}")


            self.logger.info(f"从 {source_config.name} 获取并解析了 {len(items)} 条新闻")

        except URLError as e:
             self.logger.error(f"获取 {source_config.name} 时发生 URL 错误: {e}")
             # Optionally re-raise specific network errors if needed upstream
        except ssl.SSLError as e:
             self.logger.error(f"获取 {source_config.name} 时发生 SSL 错误: {e}")
        except TimeoutError:
             self.logger.error(f"获取 {source_config.name} 时超时")
        except Exception as e:
            self.logger.error(f"获取或解析 {source_config.name} 时发生未知错误: {e}", exc_info=True)
            # Consider re-raising or returning empty list based on desired error handling

        return items


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

    # Removed _remove_duplicates method