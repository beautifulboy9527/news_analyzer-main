# print("--- LOADING src/core/app_service.py ---") # Removed debug print
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
应用服务层模块 - 协调UI、存储、源管理、LLM和新闻更新等核心功能 (Refactored)
"""

import logging
import inspect
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta, timezone # MODIFIED: Added timezone
from dateutil import parser as dateutil_parser # Keep dateutil import for now
from PySide6.QtCore import QObject, Signal as pyqtSignal, QSettings, Qt, Slot, Property # 统一使用 PySide6
import os
import shutil
from dependency_injector import providers # <--- 正确的导入

# 假设的导入路径，后续需要根据实际情况调整
from src.models import NewsSource, NewsArticle # 恢复原始导入路径
from src.storage.news_storage import NewsStorage
# from src.collectors.rss_collector import RSSCollector # Moved to NewsUpdateService
# from src.collectors.pengpai_collector import PengpaiCollector # Moved to NewsUpdateService
from src.llm.llm_service import LLMService
from src.core.source_manager import SourceManager # 导入 SourceManager (Use src. prefix for consistency)
from src.config.llm_config_manager import LLMConfigManager # 修正文件名和类名
from src.collectors.categories import get_category_name # Keep for category logic
from src.core.news_update_service import NewsUpdateService # Import new service
from src.core.analysis_service import AnalysisService # Import AnalysisService
from src.core.history_service import HistoryService # Import HistoryService
# from src.storage.analysis_storage_service import AnalysisStorageService # REMOVE THIS IMPORT IF NO LONGER NEEDED

# --- Helper Function (Moved to NewsUpdateService) ---
# def convert_datetime_to_iso(obj):
#     ...
# --- End Helper Function ---

class AppService(QObject): # 继承 QObject 以便使用信号槽
    """应用程序服务层 (Refactored)

    协调核心服务，并提供统一接口给UI层。
    新闻刷新逻辑已移至 NewsUpdateService。
    """

    # --- 信号定义 --- 
    # Signals related to data sources and general status
    sources_updated = pyqtSignal() # 新闻源列表发生变化
    status_message_updated = pyqtSignal(str) # 状态栏消息更新
    selected_news_changed = pyqtSignal(object) # 发射选中的 NewsArticle 或 None
    # --- News Cache Update Signal --- (Emitted AFTER refresh completes and cache is updated)
    news_cache_updated = pyqtSignal(list) # 发射【完整】的内存缓存列表
    
    # --- Signals forwarded from NewsUpdateService ---
    refresh_started = pyqtSignal() 
    refresh_progress = pyqtSignal(int, int) # Emits (current_progress_percentage, 100)
    refresh_complete = pyqtSignal(bool, str)
    # refresh_cancelled = pyqtSignal() # Covered by refresh_complete(False, "刷新已取消")
    source_fetch_failed = pyqtSignal(str, str) # Forwarded signal
    single_source_gui_update = pyqtSignal(dict) # NEW: Signal for single source UI update in SourceManagementPanel

    def __init__(self,
                 config_provider: providers.Configuration,
                 llm_config_manager: LLMConfigManager,
                 storage: NewsStorage,
                 source_manager: SourceManager,
                 llm_service: LLMService,
                 news_update_service: NewsUpdateService,
                 analysis_service: AnalysisService,
                 history_service: HistoryService): # Removed analysis_storage_service parameter
        super().__init__()
        self.logger = logging.getLogger('news_analyzer.core.app_service')
        self.logger.debug("Initializing AppService (Refactored, manual instantiation)...")

        # --- Assign Dependencies ---
        self.config = config_provider
        self.llm_config_manager = llm_config_manager
        self.storage = storage
        self.source_manager = source_manager
        self.llm_service = llm_service
        self.news_update_service = news_update_service # Assign new service
        self.analysis_service = analysis_service # Assign AnalysisService
        self.history_service = history_service # Assign HistoryService
        # self.analysis_storage_service = analysis_storage_service # REMOVED assignment
        # --- End Assign Dependencies ---

        # --- Attributes ---
        # self.news_sources: List[NewsSource] = [] # Managed by SourceManager
        self.news_cache: List[NewsArticle] = [] # --- 内存缓存 --- (Still maintained here)
        self.selected_article: Optional[NewsArticle] = None # +++ 新增属性，存储当前选中的文章 +++
        # self.collectors: Dict[str, object] = {} # Moved to NewsUpdateService

        # --- Refresh State (Managed by NewsUpdateService) ---
        # self._is_refreshing = False
        # self._cancel_refresh = False

        self.logger.info("AppService __init__ complete (dependencies assigned).")
        self._connect_service_signals() # Call new method to connect signals

    def _connect_service_signals(self):
        """Connect signals from various services to AppService handlers or forward them."""
        self.logger.info("AppService: Connecting service signals...")

        if self.news_update_service:
            self.logger.info(f"AppService: Attempting to connect NewsUpdateService signals (Instance: {self.news_update_service})...")
            try:
                self.news_update_service.refresh_started.connect(self.refresh_started)
                self.news_update_service.source_refresh_progress.connect(self._handle_source_refresh_progress)
                self.news_update_service.refresh_complete.connect(self.refresh_complete)
                self.news_update_service.news_refreshed.connect(self._handle_news_refreshed, Qt.QueuedConnection)
                self.news_update_service.error_occurred.connect(self.source_fetch_failed)
                # Connect the new signal for persisted status
                self.news_update_service.source_status_persisted_in_db.connect(self._handle_source_status_persisted)
                self.logger.info("AppService: Successfully connected all expected NewsUpdateService signals.")
            except Exception as e:
                self.logger.error(f"AppService: Error connecting NewsUpdateService signals: {e}", exc_info=True)
        else:
            self.logger.error("AppService: NewsUpdateService not provided, cannot connect signals.")

        if self.source_manager:
            self.logger.info(f"AppService: Attempting to connect SourceManager signals (Instance: {self.source_manager})...")
            try:
                self.source_manager.sources_updated.connect(self.sources_updated)
                self.logger.info("AppService: Successfully connected SourceManager.sources_updated to AppService.sources_updated.")
            except Exception as e:
                self.logger.error(f"AppService: Error connecting SourceManager signals: {e}", exc_info=True)
        else:
            self.logger.warning("AppService: SourceManager not provided, source update signals might not be forwarded.")

        # Connect signals from other services (AnalysisService, HistoryService) as needed
        # Example for HistoryService if it emits a signal that AppService needs to react to or forward:
        # if self.history_service and hasattr(self.history_service, 'some_relevant_signal'):
        # self.history_service.some_relevant_signal.connect(self._handle_history_service_signal)
        # self.logger.info("AppService: Connected HistoryService signals.")

        self.logger.info("AppService: Service signal connections configured.")

    # --- Signal Handlers / Slots ---
    @Slot(int, str, str, object)
    def _handle_source_status_persisted(self, source_id: int, status: str, error_message: Optional[str], last_checked_time: datetime):
        """Handles the signal that a source's status has been persisted to the DB.
        Updates SourceManager cache and then emits a signal for SourceManagementPanel to update a single item.
        """
        self.logger.info(f"AppService: Received source_status_persisted_in_db for source_id {source_id}. Status: '{status}', Error: '{error_message}', LastChecked: {last_checked_time}")
        updated_source_name = None
        if self.source_manager:
            try:
                self.logger.debug(f"AppService: Calling SourceManager.update_source_status_in_cache with ID: {source_id}, Status: '{status}', Error: '{error_message}', LastChecked: {last_checked_time}")
                self.source_manager.update_source_status_in_cache(source_id, status, error_message, last_checked_time)
                self.logger.debug(f"AppService: Called SourceManager to update cache for source_id {source_id}.")
                # Try to get the updated source name for the GUI update signal
                source_obj = self.source_manager.get_source_by_id(source_id) # Assuming SourceManager has get_source_by_id
                if source_obj:
                    updated_source_name = source_obj.name
                    # Construct the payload for single_source_gui_update
                    # This payload should match what SourceManagementPanel._on_single_source_check_complete expects
                    gui_update_payload = {
                        'source_name': updated_source_name,
                        'success': status == 'ok',
                        'status': status, # Pass the actual status string
                        'message': error_message if status == 'error' else (source_obj.last_error if hasattr(source_obj, 'last_error') and source_obj.last_error else ''),
                        'error_count': source_obj.consecutive_error_count if hasattr(source_obj, 'consecutive_error_count') else 0,
                        'check_time': last_checked_time.isoformat() if last_checked_time else None,
                        # Ensure all fields expected by _on_single_source_check_complete are present
                        # Original fields in _on_single_source_check_complete from result dict:
                        # source_name, success, message, error_count, check_time, (implicitly status via success)
                    }
                    self.logger.info(f"AppService: Emitting single_source_gui_update for '{updated_source_name}': {gui_update_payload}")
                    self.single_source_gui_update.emit(gui_update_payload)
                else:
                    self.logger.warning(f"AppService: Could not find source_id {source_id} in SourceManager after status update to emit single_source_gui_update.")

            except Exception as e:
                self.logger.error(f"AppService: Error in _handle_source_status_persisted for source_id {source_id}: {e}", exc_info=True)
        else:
            self.logger.warning("AppService: SourceManager not available, cannot update source status in cache or emit single_source_gui_update.")

    # --- Source Management Methods (Delegated to SourceManager) ---
    def get_sources(self) -> List[NewsSource]:
        return self.source_manager.get_sources()

    def add_source(self, source: NewsSource):
        self.source_manager.add_source(source)

    def remove_source(self, source_name: str):
        self.source_manager.remove_source(source_name)

    def update_source(self, source_name: str, updated_data: dict):
        self.source_manager.update_source(source_name, updated_data)
    # --- End Source Management ---

    # --- News Cache / Loading --- 
    def _load_initial_news(self):
        """加载初始新闻列表并更新缓存和通知UI"""
        self.logger.info("加载初始新闻...")
        try:
            initial_news_data = self.storage.get_all_articles() # Use the correct method
            if initial_news_data:
                self.logger.info(f"成功从数据库加载 {len(initial_news_data)} 条初始新闻。")
                # --- Convert dicts to articles ---
                initial_news_articles = []
                for item_dict in initial_news_data:
                    article = self._convert_dict_to_article(item_dict) # Use AppService's converter for now
                    if article:
                        initial_news_articles.append(article)
                self.logger.info(f"加载并转换了 {len(initial_news_articles)} 条初始新闻")

                # --- Assign categories based on source config ---
                source_map = {source.name: source for source in self.source_manager.get_sources()}
                for article in initial_news_articles:
                    source_config = source_map.get(article.source_name)
                    if source_config:
                        category_id = source_config.category
                        article.category = get_category_name(category_id)
                    else:
                        article.category = None
                        self.logger.warning(f"未找到来源 '{article.source_name}' 的配置，新闻 '{article.title[:20]}...' 将由后续逻辑进行分类。")
                
                # --- Load read status USING HistoryService ---
                read_count = 0
                for article in initial_news_articles:
                    try:
                        if article.link:
                            # Use HistoryService here!
                            article.is_read = self.history_service.is_read(article.link)
                            if article.is_read: read_count += 1
                        else: article.is_read = False
                    except Exception as read_e:
                        self.logger.warning(f"检查已读状态失败 for '{article.title[:20]}...': {read_e}")
                        article.is_read = False
                self.logger.info(f"已加载已读状态，其中 {read_count} 条标记为已读。")
                # --- Update Cache and Emit Signal ---
                self.news_cache = initial_news_articles # Update internal cache
                self.logger.debug(f"内存缓存已更新 (初始加载)，包含 {len(self.news_cache)} 条新闻")
                self.logger.info(f"_load_initial_news: Emitting news_cache_updated with {len(self.news_cache)} articles.")
                self.news_cache_updated.emit(self.news_cache) # Emit the full cache
                self.status_message_updated.emit(f"已加载 {len(self.news_cache)} 条历史新闻")
            else:
                self.logger.info("未找到历史新闻")
                self.news_cache = [] # 确保缓存为空
                self.logger.info(f"_load_initial_news: Emitting news_cache_updated with {len(self.news_cache)} articles (empty cache).")
                self.news_cache_updated.emit(self.news_cache) # Emit empty cache
                self.status_message_updated.emit("未找到历史新闻，请刷新")
        except AttributeError as ae:
            if "'Provide' object has no attribute" in str(ae):
                 self.logger.error(f"加载初始新闻失败: 依赖项尚未解析! Error: {ae}", exc_info=True)
            else:
                 self.logger.error(f"加载初始新闻时发生属性错误: {ae}", exc_info=True)
            self.status_message_updated.emit("加载历史新闻失败 (依赖错误)")
        except Exception as e:
            self.logger.error(f"加载初始新闻失败: {e}", exc_info=True)
            self.status_message_updated.emit("加载历史新闻失败")

    def _handle_news_refreshed(self, source_name: str, news_items: List[Dict[str, Any]]):
        """处理从 NewsUpdateService.news_refreshed 信号传来的单个源的新闻条目。"""
        self.logger.info(f"--- AppService: _handle_news_refreshed 被调用！来源: '{source_name}', 条目数: {len(news_items)} ---") # +++ 新增日志 +++
        if not news_items:
            self.logger.info(f"来源 '{source_name}' 没有返回新的新闻条目，不处理。")
            self._emit_news_cache_updated_signal(source_name, 0) # 即使没有新文章也通知，以便UI可以结束加载状态
            return

        self.logger.info(f"AppService: 从 '{source_name}' 接收到 {len(news_items)} 条新闻条目。准备处理...")

        # +++ ADDED: Get source map for category lookup +++
        source_map = {source.name: source for source in self.source_manager.get_sources()}
        # +++ END ADDED +++

        # 1. 转换原始字典为 NewsArticle 对象 (不含数据库 ID)
        articles_without_ids = []
        for item_dict in news_items:
            try:
                # Ensure publish_time is correctly parsed to datetime if it's a string
                # MODIFICATION START: Prioritize 'publish_time' (datetime object), then 'pub_date' (string)
                publish_time_dt: Optional[datetime] = None
                article_title_for_log = item_dict.get('title', 'N/A')[:50]
                article_link_for_log = item_dict.get('link', 'N/A')

                datetime_from_collector = item_dict.get('publish_time') # Expected to be a datetime object or None
                date_str_from_collector = item_dict.get('pub_date')     # Expected to be a date string or None

                self.logger.info(f"AppService [{source_name}]: Processing item '{article_title_for_log}...'. Link: {article_link_for_log}. Collector provided 'publish_time' (datetime): {datetime_from_collector} (type: {type(datetime_from_collector)}), 'pub_date' (str): {date_str_from_collector} (type: {type(date_str_from_collector)})")

                if isinstance(datetime_from_collector, datetime):
                    publish_time_dt = datetime_from_collector
                    self.logger.info(f"AppService [{source_name}]: Using 'publish_time' (datetime object): {publish_time_dt} (tzinfo: {publish_time_dt.tzinfo}) for article '{article_title_for_log}...'")
                    if publish_time_dt.tzinfo is None: # Ensure it's timezone-aware
                        publish_time_dt = publish_time_dt.replace(tzinfo=timezone.utc)
                        self.logger.info(f"AppService [{source_name}]: Localized naive datetime object from 'publish_time' to UTC: {publish_time_dt} for '{article_title_for_log}...'")
                
                elif isinstance(date_str_from_collector, str) and date_str_from_collector.strip():
                    self.logger.info(f"AppService [{source_name}]: 'publish_time' was not a datetime. Attempting to parse 'pub_date' string '{date_str_from_collector}' for article '{article_title_for_log}...'")
                    try:
                        # Use dateutil_parser for robust parsing of various string formats
                        publish_time_dt = dateutil_parser.parse(date_str_from_collector, fuzzy=True) # fuzzy might help with slight variations
                        self.logger.info(f"AppService [{source_name}]: Successfully parsed 'pub_date' string '{date_str_from_collector}' to datetime: {publish_time_dt} (type: {type(publish_time_dt)}) for '{article_title_for_log}...'")

                        if publish_time_dt and publish_time_dt.tzinfo is None:
                            publish_time_dt = publish_time_dt.replace(tzinfo=timezone.utc) # Assume UTC if naive
                            self.logger.info(f"AppService [{source_name}]: Localized naive datetime from 'pub_date' string to UTC: {publish_time_dt} for '{article_title_for_log}...'")

                    except (ValueError, TypeError, OverflowError) as e_date_str_parse:
                        self.logger.warning(f"AppService [{source_name}]: Parsing 'pub_date' string '{date_str_from_collector}' FAILED for article '{article_title_for_log}...'. Error: {e_date_str_parse}. Setting publish_time_dt to None.")
                        publish_time_dt = None
                    except Exception as e_date_str_unknown:
                        self.logger.error(f"AppService [{source_name}]: Unknown error while parsing 'pub_date' string '{date_str_from_collector}' for article '{article_title_for_log}...'. Error: {e_date_str_unknown}", exc_info=True)
                        publish_time_dt = None
                else:
                    self.logger.warning(f"AppService [{source_name}]: Neither 'publish_time' (datetime) nor 'pub_date' (str) provided or valid for article '{article_title_for_log}...'. publish_time_dt remains None.")
                # MODIFICATION END

                # 在创建 NewsArticle 对象前记录最终的 publish_time_dt
                self.logger.info(f"AppService [{source_name}]: For article '{article_title_for_log}...', final publish_time_dt to be used for NewsArticle: {publish_time_dt} (type: {type(publish_time_dt)})")
                
                article = NewsArticle(
                    title=item_dict.get('title', ''),
                    link=item_dict.get('link', ''),
                    summary=item_dict.get('summary'),
                    content=item_dict.get('content'),
                    source_name=item_dict.get('source_name', source_name), # Fallback to the overall source name
                    category=item_dict.get('category', '未分类'), # MODIFIED: Use determined category
                    publish_time=publish_time_dt,
                    raw_data=item_dict # MODIFIED: Store the whole item_dict
                )
                if not article.link: # Skip articles with no link
                    self.logger.warning(f"Skipping article with no link: {article.title}")
                    continue
                articles_without_ids.append(article)
            except Exception as e_create:
                self.logger.error(f"创建 NewsArticle 对象失败 for item: {item_dict.get('title', 'N/A')}. Error: {e_create}", exc_info=True)
                continue
        
        if not articles_without_ids:
            self.logger.info(f"来源 '{source_name}' 的所有条目转换后为空或无效，不继续处理。")
            self._emit_news_cache_updated_signal(source_name, 0)
            return

        # Convert NewsArticle objects to dictionaries for storage
        articles_to_store_as_dicts = []
        for article_obj in articles_without_ids:
            articles_to_store_as_dicts.append({
                'title': article_obj.title,
                'link': article_obj.link,
                'source_name': article_obj.source_name,
                'category': article_obj.category,
                'content': article_obj.content,
                'summary': article_obj.summary,
                'publish_time': article_obj.publish_time, # NewsStorage will handle datetime object
                'raw_data': article_obj.raw_data # This should be the original item_dict
            })

        # 2. 批量将这些文章写入数据库 (upsert)
        try:
            self.storage.upsert_articles_batch(articles_to_store_as_dicts) # MODIFIED: Pass list of dicts
            self.logger.info(f"AppService: 为来源 '{source_name}' 批量更新/插入了 {len(articles_to_store_as_dicts)} 条文章到数据库。")
        except Exception as e_db_upsert:
            self.logger.error(f"AppService: 数据库批量更新/插入文章失败 for '{source_name}': {e_db_upsert}", exc_info=True)
            self._emit_news_cache_updated_signal(source_name, 0, error_message=str(e_db_upsert))
            return

        # 3. 从数据库根据链接重新获取这些文章，确保它们现在拥有数据库ID
        #    并过滤掉那些可能因为某种原因未成功插入或更新的文章
        links_of_processed_articles = [art.link for art in articles_without_ids if art.link]
        articles_with_ids: List[NewsArticle] = []
        if links_of_processed_articles:
            try:
                # NEW: Fetch as dicts then convert
                articles_as_dicts_from_db = self.storage.get_articles_by_links(links_of_processed_articles)
                self.logger.info(f"AppService: 从数据库为来源 '{source_name}' 重新获取了 {len(articles_as_dicts_from_db)} 条文章 (字典格式)。")

                converted_articles_with_ids: List[NewsArticle] = []
                for db_dict in articles_as_dicts_from_db:
                    article_obj = self._convert_dict_to_article(db_dict) # Use existing helper
                    if article_obj:
                        converted_articles_with_ids.append(article_obj)
                    else:
                        self.logger.warning(f"AppService: 未能将从数据库获取的字典转换为 NewsArticle 对象: {db_dict.get('link', 'N/A')}")
                articles_with_ids = converted_articles_with_ids
                self.logger.info(f"AppService: 成功将 {len(articles_with_ids)} 条数据库字典转换为 NewsArticle 对象。")

                if len(articles_with_ids) != len(articles_without_ids): # This comparison might be less relevant now, more about successful conversion
                    self.logger.warning(f"AppService: 数量不匹配！尝试 upsert {len(articles_without_ids)} 条，但重新获取到 {len(articles_with_ids)} 条带ID的文章 for '{source_name}'.")
                    # Log missing links if any for debugging
                    if len(articles_with_ids) < len(articles_without_ids):
                        fetched_links = {art.link for art in articles_with_ids}
                        missing_links = [link for link in links_of_processed_articles if link not in fetched_links]
                        self.logger.warning(f"AppService: 未能从数据库取回以下链接的文章: {missing_links}")

            except Exception as e_db_fetch:
                self.logger.error(f"AppService: 从数据库根据链接批量获取文章失败 for '{source_name}': {e_db_fetch}", exc_info=True)
                # Proceed with empty list or potentially just the ones without IDs?
                # For now, we will proceed and the cache update will reflect this issue.
                articles_with_ids = [] # Fallback to empty to prevent further errors down the line if critical
        
        # 4. 更新内部缓存，并仅保留真正唯一的、带有ID的文章
        unique_new_articles_with_ids_count = 0
        if articles_with_ids:
            current_cache_size = len(self.news_cache)
            # --- MODIFICATION START: Improved cache update logic ---
            # Create a map of existing article links to their index in the cache for efficient lookup
            cache_link_to_index_map = {cached_article.link: i for i, cached_article in enumerate(self.news_cache)}

            for article_with_id in articles_with_ids:
                if not article_with_id.link: # Should not happen if filtered earlier, but as a safeguard
                    self.logger.warning(f"AppService: Article with ID {article_with_id.id} has no link, cannot process for cache update.")
                    continue

                if article_with_id.link in cache_link_to_index_map:
                    # Article already exists in cache, replace it with the potentially updated version
                    existing_article_index = cache_link_to_index_map[article_with_id.link]
                    self.news_cache[existing_article_index] = article_with_id
                    # self.logger.debug(f"AppService: Updated existing article in cache: {article_with_id.link}")
                    # Not counted as "new" for the purpose of the signal count, but it is an update.
                else:
                    # New article, add to cache
                    self.news_cache.append(article_with_id)
                    cache_link_to_index_map[article_with_id.link] = len(self.news_cache) - 1 # Update map for newly added item
                    unique_new_articles_with_ids_count += 1
            # --- MODIFICATION END ---
            
            self.logger.info(f"AppService: 为 '{source_name}' 将 {unique_new_articles_with_ids_count} 条唯一新文章（带ID）合并到缓存。缓存大小从 {current_cache_size} 变为 {len(self.news_cache)}.")
        else:
            self.logger.warning(f"AppService: 没有从数据库获取到带有ID的文章 for '{source_name}'，缓存未更新新条目。")

        # 5. 发射信号，通知UI新闻列表已更新
        #    传递的是成功从数据库获取并加入缓存的文章数量
        self._emit_news_cache_updated_signal(source_name, unique_new_articles_with_ids_count)
        self.logger.info(f"AppService: 已为来源 '{source_name}' 发射 news_cache_updated 信号，新增文章数: {unique_new_articles_with_ids_count}")

    def _emit_news_cache_updated_signal(self, source_name: str, count: int, error_message: Optional[str] = None):
        """Helper method to emit news_cache_updated signal and log relevant info."""
        if error_message:
            self.logger.error(f"Error during news processing for source '{source_name}': {error_message}. Emitting empty update.")
            # In case of error, we might still want to emit the current cache, 
            # or an empty list depending on desired behavior for partial updates.
            # For now, let's assume we emit the current (potentially partially updated) cache.
            # Or, if count is 0 due to error, it correctly reflects no *new* articles from this source.
        else:
            self.logger.info(f"Emitting news_cache_updated for source '{source_name}'. New/updated articles from this source: {count}. Total cache size: {len(self.news_cache)}")
        
        # The news_cache_updated signal is defined to emit the ENTIRE cache list.
        self.news_cache_updated.emit(list(self.news_cache)) # Ensure a copy is emitted

    # --- News Refresh Methods (Delegated to NewsUpdateService) ---
    def refresh_all_sources(self):
        """触发所有启用的新闻源进行刷新 (委托给 NewsUpdateService)。"""
        self.logger.debug("AppService: refresh_all_sources() called. Delegating to NewsUpdateService...")
        self.news_update_service.refresh_all_sources()

    def cancel_refresh(self):
        """请求取消当前正在进行的刷新操作 (委托给 NewsUpdateService)。"""
        self.logger.debug("AppService: Delegating cancel_refresh to NewsUpdateService.")
        self.news_update_service.cancel_refresh()
        
    def is_refreshing(self) -> bool:
        """检查当前是否正在刷新 (委托给 NewsUpdateService)。"""
        return self.news_update_service.is_refreshing()
    # --- End News Refresh Delegation ---

    # --- Helper Methods (Keep ones needed by non-refresh/non-analysis logic) ---
    def _convert_dict_to_article(self, item_dict: Dict[str, Any]) -> Optional[NewsArticle]:
        """将字典转换为 NewsArticle 对象，并进行数据清洗和验证。"""
        if not item_dict or not isinstance(item_dict, dict):
            self.logger.warning("_convert_dict_to_article: 输入的 item_dict 为空或非字典类型，跳过转换。")
            return None

        article_id = item_dict.get('id')
        link = item_dict.get('link')
        title = item_dict.get('title', '无标题').strip()
        source_name = item_dict.get('source_name', '未知来源')
        
        raw_publish_time_from_dict = item_dict.get('publish_time')
        self.logger.info(f"_convert_dict_to_article (来源: {source_name}, 标题: {title[:30]}...): 从字典获取的原始 'publish_time' 字段: '{raw_publish_time_from_dict}' (类型: {type(raw_publish_time_from_dict)})")

        parsed_datetime = self._parse_datetime(raw_publish_time_from_dict) # 传递原始值给 _parse_datetime

        content = item_dict.get('content', '')
        if not isinstance(content, str):
            self.logger.warning(f"Content for '{title}' is not a string ({type(content)}), setting to empty.")
            content = ''
        
        summary = item_dict.get('summary', '')
        if not isinstance(summary, str): # 确保摘要是字符串
            self.logger.warning(f"Summary for '{title}' is not a string ({type(summary)}), setting to empty.")
            summary = ''

        if not link: # 链接是必需的
            self.logger.warning(f"创建 NewsArticle 失败: 链接为空。字典: {item_dict}")
            return None
        
        # 其他字段
        image_url = item_dict.get('image_url')
        author = item_dict.get('author')
        language = item_dict.get('language', 'unknown') # 从字典获取或默认为 unknown
        category = item_dict.get('category', '未分类') # 从字典获取或默认为 未分类
        tags_str = item_dict.get('tags') # 假设 tags 在字典中是字符串
        tags = [tag.strip() for tag in tags_str.split(',')] if isinstance(tags_str, str) else []
        
        # 确保 created_at 和 updated_at 是 datetime 对象
        created_at_str = item_dict.get('created_at')
        created_at = self._parse_datetime(created_at_str) if created_at_str else datetime.now(timezone.utc)

        updated_at_str = item_dict.get('updated_at')
        updated_at = self._parse_datetime(updated_at_str) if updated_at_str else datetime.now(timezone.utc)

        try:
            article = NewsArticle(
                id=article_id, # id 可能为 None (例如新文章)
                link=link,
                title=title,
                content=content,
                source_name=source_name,
                publish_time=parsed_datetime, # 使用 _parse_datetime 的结果
                image_url=image_url,
                author=author,
                summary=summary,
                language=language, # 设置 language
                category=category, # 设置 category
                tags=tags,         # 设置 tags
                created_at=created_at,
                updated_at=updated_at
            )
            self.logger.info(f"AppService [_convert_dict_to_article]: Successfully converted dict to NewsArticle: '{article.title[:50]}...', final publish_time: {article.publish_time}")
            return article
        except Exception as e:
            self.logger.error(f"在 _convert_dict_to_article 中创建 NewsArticle 对象失败: {e}. 字典: {item_dict}", exc_info=True)
            return None

    def _parse_datetime(self, date_input: Optional[Any]) -> Optional[datetime]: # MODIFIED: Changed param name from date_string to date_input and type to Any
        # MODIFIED: Handle cases where date_input is already a datetime object
        if isinstance(date_input, datetime):
            self.logger.debug(f"_parse_datetime: 输入已经是 datetime 对象: {date_input} (时区: {date_input.tzinfo})。准备进行时区标准化。")
            dt_aware = date_input
            # 标准化为 UTC 时间
            if dt_aware.tzinfo is None or dt_aware.tzinfo.utcoffset(dt_aware) is None:
                # 如果是 naive datetime，假定它是本地时间，然后转换为 UTC
                # 或者，如果业务逻辑规定所有无时区信息的时间默认为 UTC，则直接附加 UTC
                try:
                    local_tz = datetime.now().astimezone().tzinfo
                    dt_aware_localized = dt_aware.replace(tzinfo=local_tz)
                    self.logger.debug(f"_parse_datetime (datetime input): naive datetime {dt_aware} 被赋予本地时区 {local_tz} -> {dt_aware_localized}")
                except Exception as e_tz_local:
                    self.logger.warning(f"_parse_datetime (datetime input): 为 naive datetime {dt_aware} 附加本地时区失败 ({e_tz_local})，将直接赋予 UTC。")
                    dt_aware_localized = dt_aware.replace(tzinfo=timezone.utc) # 假设 naive datetime 是 UTC
                dt_utc = dt_aware_localized.astimezone(timezone.utc)
            else:
                dt_utc = dt_aware.astimezone(timezone.utc) # 已经是 aware, 统一转 UTC
            
            self.logger.info(f"_parse_datetime: datetime 输入 '{date_input}' 成功标准化为 UTC: {dt_utc}")
            return dt_utc

        # Original logic for string inputs
        if not date_input or not isinstance(date_input, str) or date_input.lower() == 'none':
            self.logger.info(f"_parse_datetime: 输入日期值为空、非字符串/datetime 或为 'none'。Value: '{date_input}' (Type: {type(date_input)}). 返回 None。")
            return None

        # Rename date_input to date_string for the rest of the string parsing logic for clarity
        date_string = date_input 
        self.logger.debug(f"_parse_datetime: 开始解析日期字符串: '{date_string}' (类型: {type(date_string)})")
        try:
            # 尝试使用 dateutil.parser 进行智能解析 (优先)
            dt = dateutil_parser.parse(date_string)
            self.logger.debug(f"_parse_datetime: dateutil_parser.parse 成功，原始解析结果 dt: {dt} (时区: {dt.tzinfo})")

            # 标准化为 UTC 时间
            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                # 如果是 naive datetime，假定它是本地时间，然后转换为 UTC
                # 或者，如果业务逻辑规定所有无时区信息的时间默认为 UTC，则直接附加 UTC
                # 为了安全起见，如果它是 naive，我们记录并可能需要根据来源调整策略
                # 这里我们先尝试赋予本地时区然后转UTC，如果不行，则直接赋UTC
                try:
                    local_tz = datetime.now().astimezone().tzinfo
                    dt_aware = dt.replace(tzinfo=local_tz)
                    self.logger.debug(f"_parse_datetime: naive datetime {dt} 被赋予本地时区 {local_tz} -> {dt_aware}")
                except Exception as e_tz_local:
                    self.logger.warning(f"_parse_datetime: 为 naive datetime {dt} 附加本地时区失败 ({e_tz_local})，将直接赋予 UTC。")
                    dt_aware = dt.replace(tzinfo=timezone.utc) # 假设 naive datetime 是 UTC
            else:
                dt_aware = dt # 已经是 aware

            dt_utc = dt_aware.astimezone(timezone.utc)
            self.logger.info(f"_parse_datetime: 日期字符串 '{date_string}' 成功解析并转换为 UTC: {dt_utc}")
            return dt_utc

        except (ValueError, TypeError) as e_dateutil:
            self.logger.warning(f"_parse_datetime: dateutil.parser 解析 '{date_string}' 失败: {e_dateutil}。尝试备用格式。")
            # 备用格式尝试 (可以根据需要添加更多)
            common_formats = [
                "%Y-%m-%dT%H:%M:%S.%fZ",  # 包含毫秒和Z
                "%Y-%m-%dT%H:%M:%SZ",     # 不含毫秒和Z
                "%Y-%m-%d %H:%M:%S",      # 常见格式
                "%a, %d %b %Y %H:%M:%S %z", # RFC 822
                "%a, %d %b %Y %H:%M:%S %Z", # RFC 822 with named timezone
            ]
            for fmt in common_formats:
                try:
                    dt = datetime.strptime(date_string, fmt)
                    self.logger.debug(f"_parse_datetime: strptime 使用格式 '{fmt}' 成功解析了 '{date_string}' 得到: {dt} (时区: {dt.tzinfo})")
                     # 标准化为 UTC 时间 (同上)
                    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                        try:
                            local_tz = datetime.now().astimezone().tzinfo
                            dt_aware = dt.replace(tzinfo=local_tz)
                            self.logger.debug(f"_parse_datetime (strptime path): naive datetime {dt} 被赋予本地时区 {local_tz} -> {dt_aware}")
                        except Exception:
                            dt_aware = dt.replace(tzinfo=timezone.utc)
                            self.logger.debug(f"_parse_datetime (strptime path): 为 naive datetime {dt} 附加本地时区失败，已直接赋予 UTC -> {dt_aware}")
                    else:
                        dt_aware = dt
                    dt_utc = dt_aware.astimezone(timezone.utc)
                    self.logger.info(f"_parse_datetime: 日期字符串 '{date_string}' (使用 strptime fmt '{fmt}') 成功解析并转换为 UTC: {dt_utc}")
                    return dt_utc
                except ValueError:
                    continue # 尝试下一个格式
            self.logger.error(f"_parse_datetime: 所有尝试均无法解析日期字符串: '{date_string}'")
            return None

    # --- LLM Analysis Data Management (via AnalysisService) ---
    def get_llm_analysis_by_id(self, analysis_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a specific LLM analysis result by its ID."""
        if not self.analysis_service:
            self.logger.warning("AppService: AnalysisService not available to get LLM analysis by ID.")
            return None
        return self.analysis_service.get_llm_analysis_by_id(analysis_id)

    def get_llm_analyses_for_article(self, article_id: int) -> List[Dict[str, Any]]:
        """Retrieves all LLM analysis results for a specific article ID."""
        if not self.analysis_service:
            self.logger.warning("AppService: AnalysisService not available to get LLM analyses for article.")
            return []
        return self.analysis_service.get_llm_analyses_for_article(article_id)

    def get_all_llm_analyses(self, limit: Optional[int] = None, offset: Optional[int] = 0) -> List[Dict[str, Any]]:
        """Retrieves all LLM analysis results, with optional pagination."""
        if not self.analysis_service:
            self.logger.warning("AppService: AnalysisService not available to get all LLM analyses.")
            return []
        return self.analysis_service.get_all_llm_analyses(limit=limit, offset=offset)

    def delete_llm_analysis(self, analysis_id: int) -> bool:
        """Deletes a specific LLM analysis result by its ID."""
        if not self.analysis_service:
            self.logger.warning("AppService: AnalysisService not available to delete LLM analysis.")
            return False
        return self.analysis_service.delete_llm_analysis(analysis_id)

    def delete_all_llm_analyses(self) -> bool:
        """Deletes all LLM analysis results."""
        if not self.analysis_service:
            self.logger.warning("AppService: AnalysisService not available to delete all LLM analyses.")
            return False
        return self.analysis_service.delete_all_llm_analyses()

    # --- End LLM Analysis Data Management ---

    def get_all_articles(self) -> List[NewsArticle]: # This method wasn't in the outline but seems to be used by storage.
        """返回当前新闻缓存中的所有文章。"""
        self.logger.info(f"get_all_articles: Returning {len(self.news_cache)} cached articles.")
        return self.news_cache

    # +++ ADDED METHOD: set_selected_news +++
    def set_selected_news(self, article: Optional[NewsArticle]):
        """
        设置当前选中的新闻文章，并发出信号。
        如果 article 为 None，表示取消选择。
        """
        current_title = self.selected_article.title if self.selected_article else "None"
        new_title = article.title if article else "None"
        self.logger.info(f"AppService.set_selected_news: Changing from '{current_title[:50]}...' to '{new_title[:50]}...'")
        
        # Simple attribute to hold the selected article.
        # Consider if deepcopy is needed if modifications are made elsewhere.
        self.selected_article: Optional[NewsArticle] = article 
        self.selected_news_changed.emit(self.selected_article)
        self.logger.debug(f"AppService.set_selected_news: Emitted selected_news_changed with {'article' if article else 'None'}.")
    # +++ END ADDED METHOD +++

    # --- Signal Handlers from NewsUpdateService ---
    @Slot(str, int, int, int)
    def _handle_source_refresh_progress(self, source_name: str, progress_percent: int, total_sources: int, processed_sources: int):
        # +++ 日志：记录接收到的参数和即将发射的信号 +++
        self.logger.info(f"AppService._handle_source_refresh_progress: 收到源 '{source_name}' 进度 {progress_percent}%. 已处理 {processed_sources}/{total_sources} 个源。准备发射 AppService.refresh_progress({processed_sources}, {total_sources}).")
        # AppService的refresh_progress信号期望 (current_value, total_value)
        # NewsUpdateService的source_refresh_progress信号提供 (source_name, progress_percent, total_sources, processed_sources)
        # 我们需要将 "已处理的源数量" 和 "总源数量" 传递给UI的进度条
        self.refresh_progress.emit(processed_sources, total_sources)
        self.logger.debug(f"AppService._handle_source_refresh_progress: AppService.refresh_progress({processed_sources}, {total_sources}) 信号已发射。")

    def shutdown(self):
        """
        在应用程序关闭前执行清理操作。
        """
        self.logger.info("AppService.shutdown() 开始执行清理...")
        try:
            if self.news_update_service and hasattr(self.news_update_service, 'shutdown'):
                self.logger.info("正在关闭 NewsUpdateService...")
                self.news_update_service.shutdown()
            elif self.news_update_service and hasattr(self.news_update_service, 'stop_all_operations'): # Fallback
                self.logger.info("正在停止 NewsUpdateService 操作...")
                self.news_update_service.stop_all_operations()


            if self.storage and hasattr(self.storage, 'close'):
                self.logger.info("正在关闭 NewsStorage...")
                self.storage.close()

            if self.llm_service and hasattr(self.llm_service, 'shutdown'):
                self.logger.info("正在关闭 LLMService...")
                self.llm_service.shutdown()
            
            # 其他服务如有需要也可以在这里添加关闭逻辑
            # if self.source_manager and hasattr(self.source_manager, 'close'):
            #     self.logger.info("正在关闭 SourceManager...")
            #     self.source_manager.close()
            # if self.analysis_service and hasattr(self.analysis_service, 'shutdown'):
            #     self.logger.info("正在关闭 AnalysisService...")
            #     self.analysis_service.shutdown()
            # if self.history_service and hasattr(self.history_service, 'close'):
            #     self.logger.info("正在关闭 HistoryService...")
            #     self.history_service.close()

            self.logger.info("AppService 清理完成。")
        except Exception as e:
            self.logger.error(f"AppService shutdown 过程中发生错误: {e}", exc_info=True)
