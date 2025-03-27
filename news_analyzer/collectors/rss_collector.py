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

            raw_title = title_elem.text or ""
            title = self._standardize_title(raw_title) # 调用标准化方法
            link = link_elem.text or ""

            if not title or not link: # 使用清理后的 title 判断
                return None
            
            # 提取描述/内容和发布日期（可选字段）
            description = ""
            # 优先尝试 content:encoded (常见于提供全文的RSS)
            # 注意：需要添加命名空间处理，但 ElementTree 对命名空间的支持有限，这里简化处理
            content_encoded_elem = item.find('{http://purl.org/rss/1.0/modules/content/}encoded')
            if content_encoded_elem is not None and content_encoded_elem.text:
                description = content_encoded_elem.text # 保留 HTML 供预览显示
            else:
                # 其次尝试 description
                desc_elem = item.find('description')
                if desc_elem is not None and desc_elem.text:
                    # 简单清理HTML标签 (如果不是 content:encoded)
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
                'collected_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'title_en': '', # 新增字段
                'description_en': '', # 新增字段
                'keywords_en': [] # 新增字段
            }

            # --- 开始翻译和关键词提取 ---
            text_to_process = f"{title}\n{description}"
            lang = 'en' # 默认英文
            try:
                if text_to_process.strip():
                    lang = detect(text_to_process)
            except LangDetectException:
                self.logger.warning(f"无法检测语言，假设为英文: {text_to_process[:50]}...")
                lang = 'en'

            if lang != 'en':
                self.logger.debug(f"检测到非英文内容 ({lang})，尝试翻译: {title[:30]}...")
                news_item['title_en'] = self.llm_client.translate_text(title, target_language="English")
                news_item['description_en'] = self.llm_client.translate_text(description, target_language="English")
            else:
                news_item['title_en'] = title
                news_item['description_en'] = description

            # 移除关键词提取逻辑
            # if self.nlp:
            #     ...
            news_item['keywords_en'] = [] # 保留字段但设置为空列表
            # --- 结束翻译和关键词提取 ---

            return news_item

        except Exception as e:
            self.logger.error(f"解析或处理RSS条目失败: {str(e)}")
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
            # 提取内容和发布日期
            content = ""
            # 优先尝试 content
            content_elem = entry.find('{http://www.w3.org/2005/Atom}content')
            if content_elem is not None and content_elem.text:
                content = content_elem.text # 保留 HTML
            # 其次尝试 summary
            elif entry.find('{http://www.w3.org/2005/Atom}summary') is not None and entry.find('{http://www.w3.org/2005/Atom}summary').text:
                 summary_elem = entry.find('{http://www.w3.org/2005/Atom}summary')
                 content = summary_elem.text # 保留 HTML

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
                'collected_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'title_en': '', # 新增字段
                'description_en': '', # 新增字段 (使用 content 作为 description)
                'keywords_en': [] # 新增字段
            }

            # --- 开始翻译和关键词提取 ---
            text_to_process = f"{title}\n{content}" # 使用 content 作为 description
            lang = 'en' # 默认英文
            try:
                if text_to_process.strip():
                    lang = detect(text_to_process)
            except LangDetectException:
                self.logger.warning(f"无法检测语言，假设为英文: {text_to_process[:50]}...")
                lang = 'en'

            if lang != 'en':
                self.logger.debug(f"检测到非英文内容 ({lang})，尝试翻译: {title[:30]}...")
                news_item['title_en'] = self.llm_client.translate_text(title, target_language="English")
                news_item['description_en'] = self.llm_client.translate_text(content, target_language="English")
            else:
                news_item['title_en'] = title
                news_item['description_en'] = content

            # 移除关键词提取逻辑
            # if self.nlp:
            #     ...
            news_item['keywords_en'] = [] # 保留字段但设置为空列表
            # --- 结束翻译和关键词提取 ---

            return news_item

        except Exception as e:
            self.logger.error(f"解析或处理Atom条目失败: {str(e)}")
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