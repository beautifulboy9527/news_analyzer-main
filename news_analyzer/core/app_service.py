#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
应用服务层模块 - 协调UI、收集器、存储和LLM等核心功能
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta # 确保导入 datetime 和 timedelta
from PyQt5.QtCore import QObject, pyqtSignal, QSettings # 引入 QObject, pyqtSignal 和 QSettings

# 假设的导入路径，后续需要根据实际情况调整
from news_analyzer.models import NewsSource, NewsArticle
from news_analyzer.storage.news_storage import NewsStorage
from news_analyzer.collectors.rss_collector import RSSCollector
from news_analyzer.collectors.pengpai_collector import PengpaiCollector # 导入澎湃收集器
from news_analyzer.collectors.default_sources import initialize_sources # 导入预设源初始化函数
from news_analyzer.llm.llm_client import LLMClient
# 可能还需要导入配置管理模块

class AppService(QObject): # 继承 QObject 以便使用信号槽
    """应用程序服务层"""

    # 定义信号，用于通知UI更新
    sources_updated = pyqtSignal() # 新闻源列表发生变化
    news_refreshed = pyqtSignal(list) # 新闻刷新完成，传递新闻列表
    status_message_updated = pyqtSignal(str) # 状态栏消息更新
    refresh_started = pyqtSignal() # NEW: 刷新开始信号
    # 添加刷新进度信号
    refresh_progress = pyqtSignal(int, int)  # (当前进度, 总数)
    refresh_complete = pyqtSignal(list)
    refresh_cancelled = pyqtSignal()

    def __init__(self, storage: NewsStorage, llm_client: LLMClient):
        super().__init__()
        self.logger = logging.getLogger('news_analyzer.core.app_service')
        self.storage = storage
        self.llm_client = llm_client

        # 初始化收集器实例
        self.collectors: Dict[str, object] = {
            'rss': RSSCollector(self.llm_client), # 传递 llm_client
            'pengpai': PengpaiCollector() # 添加澎湃收集器实例
        }
        self.news_sources: List[NewsSource] = [] # 内存中的新闻源配置列表
        self.news_cache: List[NewsArticle] = [] # --- 新增：内存缓存 ---

        # 刷新状态
        self._is_refreshing = False
        self._cancel_refresh = False

        self._load_sources_config() # 启动时加载配置
        self._load_initial_news() # 启动时加载初始新闻

    def _load_sources_config(self):
        """从 QSettings 加载新闻源列表"""
        self.logger.info("加载新闻源配置...")
        self.news_sources = [] # 清空当前列表
        settings = QSettings("NewsAnalyzer", "NewsAggregator")

        # 加载用户添加的RSS源
        user_rss_sources_data = settings.value("user_rss_sources", [])
        user_source_urls = set()
        user_source_names = set()
        if isinstance(user_rss_sources_data, list):
            for data in user_rss_sources_data:
                if isinstance(data, dict) and 'url' in data:
                    source = NewsSource(
                        name=data.get('name', data['url'].split("//")[-1].split("/")[0]),
                        type='rss',
                        url=data['url'],
                        category=data.get('category', '未分类'),
                        enabled=data.get('enabled', True),
                        is_user_added=True,
                        notes=data.get('notes') # 加载备注
                    )
                    self.news_sources.append(source)
                    user_source_urls.add(source.url)
                    user_source_names.add(source.name)
            self.logger.info(f"加载了 {len([s for s in self.news_sources if s.is_user_added])} 个用户添加的 RSS 源")

        # --- 调用 initialize_sources 来添加预设 RSS 源到收集器 ---
        rss_collector_instance = self.collectors.get('rss')
        if rss_collector_instance:
            try:
                # 让 initialize_sources 直接操作收集器实例
                preset_count = initialize_sources(rss_collector_instance)
                self.logger.info(f"通过 initialize_sources 添加了 {preset_count} 个预设 RSS 源到收集器")

                # --- 从收集器获取所有 RSS 源信息，并更新 AppService 的列表 ---
                all_rss_sources_from_collector = rss_collector_instance.get_sources() # 假设 get_sources 返回字典列表
                preset_added_count_in_service = 0
                for src_data in all_rss_sources_from_collector:
                    # 只添加那些不是用户添加的（避免重复添加已从设置加载的用户源）
                    if not src_data.get('is_user_added', False):
                         # 检查是否已存在同名或同 URL 的用户源 (双重检查)
                         if src_data['url'] not in user_source_urls and src_data['name'] not in user_source_names:
                            preset_source = NewsSource(
                                name=src_data['name'],
                                type='rss',
                                url=src_data['url'],
                                category=src_data.get('category', '未分类'),
                                enabled=True, # 预设默认启用
                                is_user_added=False
                            )
                            self.news_sources.append(preset_source)
                            preset_added_count_in_service += 1
                self.logger.info(f"将 {preset_added_count_in_service} 个预设 RSS 源同步到 AppService 列表")

            except Exception as e:
                self.logger.error(f"调用 initialize_sources 或处理预设源时出错: {e}", exc_info=True)
        else:
            self.logger.error("无法找到 RSS 收集器实例来初始化预设源")


        # --- 加载澎湃新闻源配置 ---
        pengpai_enabled = settings.value("source/pengpai_enabled", True, type=bool)
        # 假设我们总是有一个代表澎湃的 NewsSource 对象
        # --- 修改：为澎湃指定分类 ---
        pengpai_source = NewsSource(name="澎湃新闻", type="pengpai", enabled=pengpai_enabled, category="综合新闻")
        self.news_sources.append(pengpai_source) # 添加到列表

        self.logger.info(f"加载了 {len(self.news_sources)} 个新闻源配置")
        self.sources_updated.emit() # 发出信号通知UI更新


    def _load_initial_news(self):
        """加载初始新闻列表并通知UI"""
        self.logger.info("加载初始新闻...")
        try:
            initial_news_data = self.storage.load_news() # 加载字典列表
            if initial_news_data:
                # --- 调用统一的转换方法 ---
                initial_news_articles = []
                for item_dict in initial_news_data:
                    article = self._convert_dict_to_article(item_dict)
                    if article:
                        initial_news_articles.append(article)

                self.logger.info(f"加载并转换了 {len(initial_news_articles)} 条初始新闻")

                # --- 根据来源名称为加载的新闻设置分类 --- 
                source_map = {source.name: source for source in self.news_sources}
                for article in initial_news_articles:
                    source_config = source_map.get(article.source_name)
                    if source_config:
                        article.category = source_config.category
                        self.logger.debug(f"为 '{article.title[:20]}...' (来源: {article.source_name}) 设置分类为: {article.category}")
                    else:
                        article.category = "未分类" # 默认分类
                        self.logger.warning(f"未找到来源 '{article.source_name}' 的配置，为新闻 '{article.title[:20]}...' 设置为默认分类 '未分类'")
                # --- 分类设置结束 ---
                # --- 更新内存缓存 ---
                self.news_cache = initial_news_articles
                self.logger.debug(f"内存缓存已更新，包含 {len(self.news_cache)} 条新闻")
                # --- 更新结束 ---
                self.news_refreshed.emit(self.news_cache) # 发射缓存中的数据
                self.status_message_updated.emit(f"已加载 {len(self.news_cache)} 条历史新闻")
            else:
                self.logger.info("未找到历史新闻")
                self.news_cache = [] # 确保缓存为空
                self.status_message_updated.emit("未找到历史新闻，请刷新")
        except Exception as e:
            self.logger.error(f"加载初始新闻失败: {e}", exc_info=True)
            self.status_message_updated.emit("加载历史新闻失败")

    def _save_sources_config(self):
        """将新闻源配置保存到 QSettings"""
        self.logger.info("保存新闻源配置...")
        settings = QSettings("NewsAnalyzer", "NewsAggregator")

        # 保存用户添加的 RSS 源
        user_rss_sources_data = []
        for source in self.news_sources:
            if source.type == 'rss' and source.is_user_added:
                user_rss_sources_data.append({
                    'name': source.name,
                    'url': source.url,
                    'category': source.category,
                    'enabled': source.enabled,
                    'is_user_added': True,
                    'notes': source.notes # 保存备注
                })
        settings.setValue("user_rss_sources", user_rss_sources_data)
        self.logger.info(f"保存了 {len(user_rss_sources_data)} 个用户添加的 RSS 源")

        # 保存澎湃新闻源的启用状态
        pengpai_source = next((s for s in self.news_sources if s.type == 'pengpai'), None)
        if pengpai_source:
            settings.setValue("source/pengpai_enabled", pengpai_source.enabled)
            self.logger.info(f"保存澎湃新闻启用状态: {pengpai_source.enabled}")

        self.logger.info("新闻源配置已保存")


    def get_sources(self) -> List[NewsSource]:
        """获取所有新闻源配置"""
        return self.news_sources

    def add_source(self, source: NewsSource):
        """添加新的新闻源"""
        self.logger.info(f"尝试添加新闻源: {source.name} ({source.type})")
        # 检查重复 (基于 URL 或 Name)
        if any(s.url == source.url for s in self.news_sources if s.url):
             raise ValueError(f"已存在相同 URL 的源: {source.url}")
        if any(s.name == source.name for s in self.news_sources):
             raise ValueError(f"已存在相同名称的源: {source.name}")

        self.news_sources.append(source)
        # 不需要更新收集器内部状态
        self._save_sources_config()
        self.sources_updated.emit()

    def remove_source(self, source_name: str):
        """移除指定名称的新闻源"""
        self.logger.info(f"尝试移除新闻源: {source_name}")
        source_to_remove = next((s for s in self.news_sources if s.name == source_name), None)

        if source_to_remove:
            # --- 移除阻止删除预设源的检查 ---
            # if not source_to_remove.is_user_added and source_to_remove.type == 'rss':
            #      self.logger.warning(f"不允许移除预设 RSS 源: {source_name}")
            #      raise ValueError("不能移除预设 RSS 源")
            # if source_to_remove.type == 'pengpai':
            #      self.logger.warning(f"不允许移除澎湃新闻源: {source_name}")
            #      raise ValueError("不能移除澎湃新闻源，请禁用")
            # --- 检查移除结束 ---

            self.news_sources.remove(source_to_remove)
            self._save_sources_config()
            self.sources_updated.emit()
            self.logger.info(f"新闻源 '{source_name}' 已移除")
        else:
            self.logger.warning(f"未找到要移除的新闻源: {source_name}")


    def update_source(self, source_name: str, updated_data: dict):
        """更新指定新闻源的信息 (例如启用/禁用, 分类)"""
        self.logger.info(f"AppService: 尝试更新新闻源 '{source_name}' 使用数据: {updated_data}")
        source = next((s for s in self.news_sources if s.name == source_name), None)
        if source:
            updated = False
            for key, value in updated_data.items():
                if hasattr(source, key) and getattr(source, key) != value:
                    # 特殊处理分类，确保不为空
                    if key == 'category' and not value.strip():
                        value = "未分类"
                    setattr(source, key, value)
                    self.logger.info(f"AppService: 更新了 '{source_name}' 的属性 '{key}' 为 '{value}'")
                    updated = True

            if updated:
                self._save_sources_config()
                self.sources_updated.emit()
                self.logger.info(f"AppService: 新闻源 '{source_name}' 已更新并发出信号")
            else:
                self.logger.info(f"AppService: 新闻源 '{source_name}' 无需更新 (数据未改变)")
        else:
            self.logger.warning(f"AppService: 未找到要更新的新闻源: {source_name}")


    def refresh_all_sources(self):
        """触发所有启用的新闻源进行刷新(异步)"""
        if self._is_refreshing:
            self.logger.warning("刷新操作正在进行中，忽略重复请求")
            return

        self._is_refreshing = True
        self._cancel_refresh = False
        self.logger.info("开始刷新所有启用的新闻源...")
        self.status_message_updated.emit("正在刷新新闻...")
        self.refresh_started.emit() # 发射刷新开始信号

        # 获取需要刷新的源列表
        sources_to_refresh = [s for s in self.news_sources if s.enabled]
        if not sources_to_refresh:
            self.logger.info("没有启用的新闻源需要刷新")
            self._is_refreshing = False
            self.refresh_complete.emit([])
            return

        # 启动异步刷新
        self._async_refresh(sources_to_refresh)

    def _async_refresh(self, sources_to_refresh):
        """异步执行刷新"""
        import threading
        thread = threading.Thread(
            target=self._do_refresh,
            args=(sources_to_refresh,),
            daemon=True
        )
        thread.start()

    def cancel_refresh(self):
        """外部调用的方法，用于请求取消当前的刷新操作"""
        if self._is_refreshing:
            self.logger.info("收到外部取消刷新请求")
            self._cancel_refresh = True
        else:
            self.logger.warning("收到取消请求，但当前没有刷新操作在进行")

    def _do_refresh(self, sources_to_refresh):
        """实际执行刷新操作，确保在 finally 中发射完成或取消信号"""
        all_news_articles = []
        errors = []
        total = len(sources_to_refresh)
        self.logger.info(f"_do_refresh: 开始处理 {total} 个源")
        # --- 优先处理澎湃新闻 --- 
        sources_to_refresh.sort(key=lambda s: s.type != 'pengpai') # pengpai 类型会排在前面
        self.logger.info(f'刷新顺序调整后: {[s.name for s in sources_to_refresh]}')
        final_articles = []
        was_cancelled = False # 局部变量跟踪取消状态

        try: # 主要处理逻辑
            for i, source_config in enumerate(sources_to_refresh):
                if self._cancel_refresh:
                    self.logger.info("刷新操作在循环中被取消")
                    was_cancelled = True # 设置取消标志
                    break # 跳出循环，进入 finally 处理

                self.logger.info(f"_do_refresh: 准备发射进度信号 ({i+1}/{total})")
                self.refresh_progress.emit(i+1, total)

                if source_config.enabled:
                    collector_type = source_config.type
                    if collector_type in self.collectors:
                        collector = self.collectors[collector_type]
                        try:
                            self.logger.info(f"正在刷新来源: {source_config.name} ({collector_type})")
                            # 传递一个检查取消状态的回调函数
                            cancel_checker = lambda: self._cancel_refresh
                            raw_news_items = collector.collect(source_config, cancel_checker=cancel_checker)
                            converted_news = []
                            for item_dict in raw_news_items:
                                article = self._convert_dict_to_article(item_dict)
                                if article:
                                    article.source_name = source_config.name
                                    article.category = source_config.category
                                    converted_news.append(article)
                            all_news_articles.extend(converted_news)
                            source_config.last_update = datetime.now()
                            source_config.error_count = 0
                            source_config.last_error = None
                        except Exception as e:
                            self.logger.error(f"刷新来源 {source_config.name} 失败: {e}", exc_info=True)
                            errors.append(f"{source_config.name}: {e}")
                            source_config.error_count += 1
                            source_config.last_error = str(e)
                    else:
                        self.logger.warning(f"未找到类型为 '{collector_type}' 的收集器来处理来源: {source_config.name}")

            # --- 循环结束后的处理 (仅在未取消时执行) ---
            if not was_cancelled:
                if all_news_articles:
                    unique_articles = {article.link: article for article in all_news_articles if article.link}
                    final_articles = list(unique_articles.values())
                    self.logger.info(f"去重后剩余 {len(final_articles)} 条新闻")

                    news_data_to_save = self._convert_articles_to_dicts(final_articles)
                    try:
                        self.storage.save_news(news_data_to_save)
                        self.logger.info(f"已将 {len(news_data_to_save)} 条新闻数据保存到存储")
                    except Exception as save_e:
                        self.logger.error(f"保存新闻数据失败: {save_e}", exc_info=True)
                        errors.append(f"保存失败: {save_e}")

                    self.news_cache = final_articles # 更新缓存
                    self.logger.info(f"内存缓存已更新，包含 {len(self.news_cache)} 条新闻")
                    self.status_message_updated.emit(f"刷新完成，获取 {len(self.news_cache)} 条新闻")
                    # 不在这里发射 refresh_complete
                else:
                    self.logger.warning("刷新完成，未获取到任何新新闻")
                    self.news_cache = [] # 清空缓存
                    self.status_message_updated.emit("刷新完成，未获取到新新闻")
                    # 不在这里发射 refresh_complete

                if errors:
                    self.status_message_updated.emit(f"刷新完成，部分来源出错: {'; '.join(errors)}")

                self.sources_updated.emit() # 更新源状态

        except Exception as outer_e: # 捕获主要逻辑中的意外错误
            self.logger.error(f"_do_refresh 过程中发生意外错误: {outer_e}", exc_info=True)
            try:
                self.status_message_updated.emit(f"刷新过程中发生错误: {outer_e}")
            except Exception as status_e:
                self.logger.error(f"发射错误状态消息失败: {status_e}")
            # 不在这里发射 refresh_complete

        finally: # 确保状态重置和信号发射
            self.logger.debug("_do_refresh finally block executing")
            try:
                if was_cancelled or self._cancel_refresh: # 再次检查以防万一
                    self.logger.info("在 finally 中检测到取消状态，发射 refresh_cancelled")
                    self.refresh_cancelled.emit()
                else:
                    self.logger.info("在 finally 中发射 refresh_complete")
                    # 确保 final_articles 是 list 类型
                    articles_to_emit = final_articles if isinstance(final_articles, list) else []
                    self.refresh_complete.emit(articles_to_emit)
            except Exception as signal_e:
                self.logger.error(f"在 finally 中发射信号失败: {signal_e}")
            finally:
                # 确保 _is_refreshing 总是被重置
                self._is_refreshing = False
                self.logger.info("_do_refresh 完成，_is_refreshing 设置为 False")

    # --- 新增：统一的字典到对象转换方法 ---
    def _convert_dict_to_article(self, item_dict: Dict) -> Optional[NewsArticle]:
        """将单个字典转换为 NewsArticle 对象，处理日期解析"""
        try:
            # 处理日期字段 - 支持 'publish_time' 和 'pub_date' 两种键名
            publish_time = item_dict.get('publish_time') or item_dict.get('pub_date')

            article = NewsArticle(
                title=item_dict.get('title', '无标题'),
                link=item_dict.get('link', ''),
                source_name=item_dict.get('source_name', '未知来源'),
                content=item_dict.get('content'),
                summary=item_dict.get('summary') or item_dict.get('description'),
                publish_time=self._parse_datetime(publish_time),
                # category=item_dict.get('category', '未分类'), # 移除，由调用者根据来源设置
                raw_data=item_dict # 保留原始数据
            )
            if article.link:
                return article
            else:
                 self.logger.warning(f"转换字典时缺少链接，已跳过: {item_dict.get('title')}")
                 return None
        except Exception as convert_e:
             self.logger.error(f"转换字典到 NewsArticle 失败: {convert_e} - 数据: {item_dict}", exc_info=True) # 添加 exc_info
             return None
    # --- 新增结束 ---

    def _convert_to_news_articles(self, raw_items: List[Dict], source_config: NewsSource) -> List[NewsArticle]:
        """将收集器返回的原始数据转换为NewsArticle对象列表"""
        # 这个方法现在可以简化或移除，因为转换逻辑已移至 _convert_dict_to_article
        # 并且 refresh_all_sources 内部直接调用 _convert_dict_to_article
        articles = []
        for item in raw_items:
             article = self._convert_dict_to_article(item)
             if article:
                 # 确保来源和分类正确
                 article.source_name = source_config.name
                 article.category = source_config.category
                 articles.append(article)
        return articles


    def _parse_datetime(self, date_string: Optional[str]) -> Optional[datetime]:
        """使用 dateutil 尝试解析多种格式的日期时间字符串"""
        if date_string is None:
            self.logger.debug("传入的日期字符串为 None，返回 None")
            return None
        if not date_string.strip():
             self.logger.debug("传入的日期字符串为空或仅包含空格，返回 None")
             return None
        self.logger.debug(f"尝试解析日期字符串: '{date_string}'")
        try:
            from dateutil import parser
            dt = parser.parse(date_string, fuzzy=False)
            result_dt = dt.replace(tzinfo=None)
            self.logger.debug(f"解析成功: {result_dt}")
            return result_dt
        except (ValueError, OverflowError, TypeError, parser.ParserError) as e:
            self.logger.warning(f"使用 dateutil 解析日期时间字符串失败: '{date_string}' - 错误: {e}")
            return None
        except ImportError:
            self.logger.error("解析日期失败：缺少 python-dateutil 库。请运行 'pip install python-dateutil'")
            return None

    def get_llm_client(self) -> LLMClient:
        """获取LLM客户端实例"""
        return self.llm_client

    def get_news_by_category(self, category: str) -> List[NewsArticle]:
        """根据分类从内存缓存中获取新闻"""
        self.logger.debug(f"从缓存根据分类 '{category}' 获取新闻")
        if category == "所有":
            self.logger.debug(f"返回所有 {len(self.news_cache)} 条缓存新闻")
            return self.news_cache
        else:
            filtered_articles = [news for news in self.news_cache if news.category == category]
            self.logger.debug(f"分类 '{category}' 从缓存筛选出 {len(filtered_articles)} 条新闻")
            return filtered_articles

    def search_news(self, query: str, field: str = "标题和内容", days: Optional[int] = None) -> List[NewsArticle]:
        """根据关键词、字段和时间范围从内存缓存中搜索新闻"""
        self.logger.debug(f"搜索请求: query='{query}', field='{field}', days={days}")

        # 准备搜索结果列表
        results = []

        # 如果查询为空，则只应用时间筛选（如果提供了）
        if not query:
            if days is None: # 如果查询为空且没有时间筛选，返回全部缓存
                 self.logger.debug("查询为空且无时间筛选，返回所有缓存新闻")
                 return self.news_cache
            else: # 如果查询为空但有时间筛选
                 self.logger.debug(f"查询为空，仅应用时间筛选 (最近 {days} 天)")
                 # 计算截止日期
                 now = datetime.now()
                 cutoff_date = now - timedelta(days=days)
                 for news in self.news_cache:
                     if news.publish_time and news.publish_time >= cutoff_date:
                         results.append(news)
                 self.logger.debug(f"时间筛选后找到 {len(results)} 条新闻")
                 return results

        # 如果查询不为空
        query_lower = query.lower()
        now = datetime.now()
        cutoff_date = now - timedelta(days=days) if days is not None else None

        for news in self.news_cache:
            # 1. 检查时间范围 (如果提供了 days)
            if cutoff_date and (not news.publish_time or news.publish_time < cutoff_date):
                continue # 不在时间范围内，跳过

            # 2. 检查关键词匹配
            title_match = news.title and query_lower in news.title.lower()
            content_match = (news.summary and query_lower in news.summary.lower()) or \
                            (news.content and query_lower in news.content.lower())

            match = False
            if field == "标题和内容":
                match = title_match or content_match
            elif field == "仅标题":
                match = title_match
            elif field == "仅内容":
                match = content_match

            if match:
                results.append(news)

        self.logger.debug(f"搜索完成: query='{query}', field='{field}', days={days} - 找到 {len(results)} 条新闻")
        return results

    def _convert_articles_to_dicts(self, articles: List[NewsArticle]) -> List[Dict]:
        """将 NewsArticle 对象列表转换为字典列表以便存储"""
        dict_list = []
        for article in articles:
            pub_date_str = article.publish_time.isoformat() if article.publish_time else None
            dict_list.append({
                'title': article.title,
                'link': article.link,
                'source_name': article.source_name,
                'content': article.content,
                'summary': article.summary,
                'publish_time': pub_date_str,
                'category': article.category,
            })
        return dict_list

    def get_all_cached_news(self) -> List[NewsArticle]:
        """获取当前内存缓存中的所有新闻"""
        self.logger.debug(f"返回所有 {len(self.news_cache)} 条缓存新闻")
        # --- 直接返回内存缓存 ---
        return self.news_cache

    def close_resources(self):
        """关闭应用服务使用的资源，例如 WebDriver"""
        self.logger.info("正在关闭 AppService 资源...")
        for collector_name, collector_instance in self.collectors.items():
            if hasattr(collector_instance, 'close') and callable(getattr(collector_instance, 'close')):
                try:
                    self.logger.info(f"正在关闭收集器: {collector_name}")
                    collector_instance.close()
                except Exception as e:
                    self.logger.error(f"关闭收集器 {collector_name} 时出错: {e}")
        self.logger.info("AppService 资源关闭完成")
