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
# import spacy # 移除 spacy
from langdetect import detect, LangDetectException
from typing import List, Dict # 导入 List 和 Dict
from ..models import NewsSource # 相对导入 NewsSource

from ..llm.llm_client import LLMClient # 相对导入


class RSSCollector:
    """RSS新闻收集器类"""

    def __init__(self, llm_client: LLMClient): # 接收 LLMClient 实例
        """初始化RSS收集器"""
        self.logger = logging.getLogger('news_analyzer.collectors.rss')
        self.sources = []
        self.news_cache = []
        self.llm_client = llm_client # 保存 LLMClient 实例
        self.nlp = None # 移除 spacy 模型加载

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

        # --- 修改：将日志级别改为 DEBUG ---
        self.logger.debug(f"添加RSS源: {name} ({url}), 分类: {category}")

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

        return unique_news # fetch_all 也应该返回获取到的新闻


    def fetch_by_category(self, category):
        """获取指定分类的新闻并更新缓存

        Args:
            category (str): 要刷新的分类名称

        Returns:
            list: 更新后的完整新闻缓存列表
        """
        if not category or category == "所有":
            # 如果分类是"所有"，则调用 fetch_all
            return self.fetch_all()

        self.logger.info(f"开始刷新分类: {category}")
        category_news = []
        sources_in_category = [s for s in self.sources if s.get('category') == category]

        if not sources_in_category:
            self.logger.warning(f"分类 '{category}' 下没有找到任何新闻源。")
            # 仍然需要返回合并后的结果，所以先获取其他分类的新闻
            other_news = [item for item in self.news_cache if item.get('category') != category]
            self.news_cache = self._remove_duplicates(other_news) # 去重以防万一
            return self.news_cache

        for source in sources_in_category:
            try:
                items = self._fetch_rss(source)
                category_news.extend(items)
                self.logger.info(f"从 {source['name']} 获取了 {len(items)} 条新闻")
            except Exception as e:
                self.logger.error(f"从 {source['name']} 获取新闻失败: {str(e)}")

        # 获取缓存中不属于当前分类的新闻
        other_news = [item for item in self.news_cache if item.get('category') != category]

        # 合并新获取的分类新闻和其他分类的旧闻，然后去重
        combined_news = other_news + category_news
        unique_news = self._remove_duplicates(combined_news)

        # 更新缓存
        self.news_cache = unique_news
        self.logger.info(f"分类 '{category}' 刷新完成，当前缓存共 {len(self.news_cache)} 条新闻。")

        return self.news_cache

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

    # --- 重命名 _fetch_rss 为 collect 并修改签名 ---
    def collect(self, source_config: NewsSource, **kwargs) -> List[Dict]: # 添加 **kwargs
        """从单个RSS源获取新闻 (统一接口)

        Args:
            source_config: 新闻源配置对象 (NewsSource)

        Returns:
            list: 包含新闻信息的原始字典列表
        """
        items = []
        url = source_config.url
        if not url:
             self.logger.warning(f"RSS 源 '{source_config.name}' 没有提供 URL")
             return []

        self.logger.info(f"开始从 RSS 源获取: {source_config.name} ({url})")
        try:
            # 创建带User-Agent的请求以避免被屏蔽
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            req = Request(url, headers=headers) # 使用 source_config.url

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
                        # --- 修改：传递 source_config ---
                        news_item = self._parse_rss_item(item, source_config)
                        if news_item:
                            items.append(news_item)

            elif root.tag.endswith('feed'):
                # Atom格式
                for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                     # --- 修改：传递 source_config ---
                    news_item = self._parse_atom_entry(entry, source_config)
                    if news_item:
                        items.append(news_item)

            # --- 修改：使用 source_config.name ---
            self.logger.info(f"从 {source_config.name} 获取了 {len(items)} 条新闻")

        except Exception as e:
             # --- 修改：使用 source_config.name ---
            self.logger.error(f"获取 {source_config.name} 的新闻失败: {str(e)}")
            raise
        
        return items
    

    def _standardize_title(self, title):
        """尝试移除标题中常见的来源和日期时间前缀，仅保留核心标题"""
        if not title:
            return ""

        original_title = title # 保留原始标题用于比较和回退

        # 1. 尝试移除最复杂的模式: [Source] Date Time Zone Separator?
        #    (增加了对更多日期格式和可选逗号的匹配)
        pattern_complex = r'^\s*\[[^\]]+\]\s+(?:\w{3},?\s+\d{1,2}\s+\w{3,}\s+\d{4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s+[+-]\d{4}|\s+GMT)?\s*[:—-]?\s*'
        cleaned_title = re.sub(pattern_complex, '', title)

        # 2. 如果复杂模式未完全清理或未匹配，尝试移除简单的 [Source] 前缀
        #    (确保即使复杂模式部分匹配，也能清理掉残留的简单前缀)
        pattern_simple_brackets = r'^\s*\[.*?\]\s*'
        # 只有当复杂模式完全没匹配时，才在原始标题上应用简单模式
        # 否则在复杂模式清理后的结果上应用简单模式
        if cleaned_title == original_title:
            cleaned_title = re.sub(pattern_simple_brackets, '', original_title)
        else:
            # 如果复杂模式匹配了，可能仍残留简单括号，再次清理
             cleaned_title = re.sub(pattern_simple_brackets, '', cleaned_title)


        # 3. 尝试移除末尾的 " | Source Name" 模式
        cleaned_title = re.sub(r'\s*\|\s*[\w\s]+$', '', cleaned_title)

        # 4. 移除特定已知来源名称后跟分隔符的情况 (更精确)
        known_sources = ["Sky Sports", "Fox Sports", "BBC News", "Reuters", "CNN", "ESPN"] # 可扩展
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

    # --- 修改签名和内部逻辑 ---
    def _parse_rss_item(self, item, source_config: NewsSource):
        """解析RSS条目

        Args:
            item: RSS条目XML元素
            source_config: 来源配置对象 (NewsSource)

        Returns:
            dict: 新闻条目字典 或 None
        """
        try:
            # 提取标题和链接（必需字段）
            title_elem = item.find('title')
            link_elem = item.find('link')
            
            if title_elem is None or link_elem is None:
                return None

            raw_title = title_elem.text or ""
            title = self._standardize_title(raw_title) # 调用标准化方法
            link = link_elem.text or ""

            if not title or not link: # 使用清理后的 title 判断
                return None
            
            # --- 提取内容和摘要 ---
            content = None
            summary = None

            # 优先尝试 content:encoded 获取完整内容
            content_encoded_elem = item.find('{http://purl.org/rss/1.0/modules/content/}encoded')
            if content_encoded_elem is not None and content_encoded_elem.text:
                content = content_encoded_elem.text # 保留 HTML
                self.logger.debug(f"从 content:encoded 提取到内容, 长度: {len(content)}")
                # 尝试从 description 获取摘要
                desc_elem = item.find('description')
                if desc_elem is not None and desc_elem.text:
                    # 清理 HTML 作为摘要
                    summary_text = re.sub(r'<[^>]+>', ' ', desc_elem.text)
                    summary = re.sub(r'\s+', ' ', summary_text).strip()
                    self.logger.debug(f"从 description 提取到摘要, 长度: {len(summary)}")

            else:
                # 如果没有 content:encoded，则尝试将 description 作为内容或摘要
                desc_elem = item.find('description')
                if desc_elem is not None and desc_elem.text:
                    # 简单判断：如果 description 包含 HTML 标签，可能更像内容
                    if '<' in desc_elem.text and '>' in desc_elem.text:
                        content = desc_elem.text # 保留 HTML 作为内容
                        self.logger.debug(f"将包含 HTML 的 description 作为内容, 长度: {len(content)}")
                        # 尝试生成简短摘要 (如果需要，或留空)
                        summary_text = re.sub(r'<[^>]+>', ' ', desc_elem.text)
                        summary = re.sub(r'\s+', ' ', summary_text).strip()[:200] + "..." # 截断作为摘要
                    else:
                        # 纯文本 description 作为摘要
                        summary = desc_elem.text.strip()
                        self.logger.debug(f"将纯文本 description 作为摘要, 长度: {len(summary)}")
                        content = summary # 也将纯文本摘要作为内容备选

            # --- 提取发布日期 ---
            pub_date = None # 使用 None 而不是空字符串
            date_elem = item.find('pubDate')
            if date_elem is not None and date_elem.text:
                pub_date = date_elem.text.strip()

            # --- 创建新闻条目字典 ---
            news_item = {
                'title': title,
                'link': link,
                'content': content, # 使用 'content' 键
                'summary': summary, # 使用 'summary' 键
                'publish_time': pub_date,
                'source_name': source_config.name,
                'source_url': source_config.url,
                'category': source_config.category,
                'collected_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                # 'title_en': '', # 暂时注释掉翻译相关
                # 'description_en': '',
                # 'keywords_en': []
            }

            # --- 暂时注释掉翻译和关键词提取逻辑 ---
            # text_to_process = f"{title}\n{summary or content or ''}" # 使用 summary 或 content
            # lang = 'en'
            # try:
            #     if text_to_process.strip():
            #         lang = detect(text_to_process)
            # except LangDetectException:
            #     self.logger.warning(f"无法检测语言，假设为英文: {text_to_process[:50]}...")
            #     lang = 'en'
            #
            # if lang != 'en':
            #     self.logger.debug(f"检测到非英文内容 ({lang})，尝试翻译: {title[:30]}...")
            #     news_item['title_en'] = self.llm_client.translate_text(title, target_language="English")
            #     # 翻译摘要或内容
            #     text_to_translate = summary if summary else content
            #     if text_to_translate:
            #          news_item['description_en'] = self.llm_client.translate_text(text_to_translate, target_language="English")
            # else:
            #     news_item['title_en'] = title
            #     news_item['description_en'] = summary if summary else content
            #
            # news_item['keywords_en'] = []
            # --- 翻译结束 ---

            return news_item

        except Exception as e:
            self.logger.error(f"解析或处理RSS条目失败: {str(e)}", exc_info=True) # 添加 exc_info=True
            return None

    # --- 修改签名和内部逻辑 ---
    def _parse_atom_entry(self, entry, source_config: NewsSource):
        """解析Atom条目

        Args:
            entry: Atom条目XML元素
            source_config: 来源配置对象 (NewsSource)

        Returns:
            dict: 新闻条目字典 或 None
        """
        try:
            # 提取标题（必需字段）
            title_elem = entry.find('{http://www.w3.org/2005/Atom}title')
            if title_elem is None:
                return None

            raw_title = title_elem.text or ""
            title = self._standardize_title(raw_title) # 调用标准化方法

            # 提取链接
            link = ""
            link_elem = entry.find('{http://www.w3.org/2005/Atom}link')
            if link_elem is not None:
                link = link_elem.get('href', '')
            
            if not title or not link:
                return None
            
            # 提取内容和发布日期
            # --- 提取内容和摘要 ---
            content = None
            summary = None

            # 优先尝试 content 获取完整内容
            content_elem = entry.find('{http://www.w3.org/2005/Atom}content')
            if content_elem is not None and content_elem.text:
                content = content_elem.text # 保留 HTML
                self.logger.debug(f"从 Atom content 提取到内容, 长度: {len(content)}")
                # 尝试从 summary 获取摘要
                summary_elem = entry.find('{http://www.w3.org/2005/Atom}summary')
                if summary_elem is not None and summary_elem.text:
                    # 清理 HTML 作为摘要 (Atom summary 通常是纯文本或简单 HTML)
                    summary_text = re.sub(r'<[^>]+>', ' ', summary_elem.text)
                    summary = re.sub(r'\s+', ' ', summary_text).strip()
                    self.logger.debug(f"从 Atom summary 提取到摘要, 长度: {len(summary)}")

            # 如果没有 content，则尝试将 summary 作为内容或摘要
            elif entry.find('{http://www.w3.org/2005/Atom}summary') is not None and entry.find('{http://www.w3.org/2005/Atom}summary').text:
                 summary_elem = entry.find('{http://www.w3.org/2005/Atom}summary')
                 summary_text = summary_elem.text.strip()
                 # 简单判断 summary 是否像内容 (Atom summary 通常较短)
                 if '<' in summary_text and '>' in summary_text: # 如果包含 HTML
                     content = summary_text # 保留 HTML 作为内容
                     self.logger.debug(f"将包含 HTML 的 Atom summary 作为内容, 长度: {len(content)}")
                     # 尝试生成简短摘要
                     plain_summary = re.sub(r'<[^>]+>', ' ', summary_text)
                     summary = re.sub(r'\s+', ' ', plain_summary).strip()[:200] + "..."
                 else: # 纯文本 summary
                     summary = summary_text
                     content = summary # 也将纯文本摘要作为内容备选
                     self.logger.debug(f"将纯文本 Atom summary 作为摘要和内容, 长度: {len(summary)}")

            # --- 提取发布日期 ---
            pub_date = None # 使用 None
            # 优先尝试 published
            date_elem = entry.find('{http://www.w3.org/2005/Atom}published')
            # 其次尝试 updated
            if date_elem is None:
                 date_elem = entry.find('{http://www.w3.org/2005/Atom}updated')

            if date_elem is not None and date_elem.text:
                pub_date = date_elem.text.strip()

            # --- 创建新闻条目字典 ---
            news_item = {
                'title': title,
                'link': link,
                'content': content, # 使用 'content' 键
                'summary': summary, # 使用 'summary' 键
                'publish_time': pub_date,
                'source_name': source_config.name,
                'source_url': source_config.url,
                'category': source_config.category,
                'collected_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                # 'title_en': '', # 暂时注释掉翻译相关
                # 'description_en': '',
                # 'keywords_en': []
            }

            # --- 暂时注释掉翻译和关键词提取逻辑 ---
            # text_to_process = f"{title}\n{summary or content or ''}"
            # lang = 'en'
            # try:
            #     if text_to_process.strip():
            #         lang = detect(text_to_process)
            # except LangDetectException:
            #     self.logger.warning(f"无法检测语言，假设为英文: {text_to_process[:50]}...")
            #     lang = 'en'
            #
            # if lang != 'en':
            #     self.logger.debug(f"检测到非英文内容 ({lang})，尝试翻译: {title[:30]}...")
            #     news_item['title_en'] = self.llm_client.translate_text(title, target_language="English")
            #     text_to_translate = summary if summary else content
            #     if text_to_translate:
            #         news_item['description_en'] = self.llm_client.translate_text(text_to_translate, target_language="English")
            # else:
            #     news_item['title_en'] = title
            #     news_item['description_en'] = summary if summary else content
            #
            # news_item['keywords_en'] = []
            # --- 翻译结束 ---

            return news_item

        except Exception as e:
            self.logger.error(f"解析或处理Atom条目失败: {str(e)}", exc_info=True) # 添加 exc_info=True
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