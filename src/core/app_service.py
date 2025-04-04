# print("--- LOADING src/core/app_service.py ---") # Removed debug print
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
应用服务层模块 - 协调UI、收集器、存储和LLM等核心功能
"""

import logging
import inspect
from typing import List, Dict, Optional
from datetime import datetime, timedelta # 确保导入 datetime 和 timedelta
from PyQt5.QtCore import QObject, pyqtSignal, QSettings, Qt # 引入 QObject, pyqtSignal, QSettings 和 Qt
# from dependency_injector.wiring import inject, Provide # Removed for manual instantiation

# 假设的导入路径，后续需要根据实际情况调整
from src.models import NewsSource, NewsArticle # 恢复原始导入路径
from src.storage.news_storage import NewsStorage
from src.collectors.rss_collector import RSSCollector
from src.collectors.pengpai_collector import PengpaiCollector # 导入澎湃收集器
# from collectors.default_sources import initialize_sources # 不再需要导入此函数
from src.llm.llm_service import LLMService
from src.core.source_manager import SourceManager # 导入 SourceManager (Use src. prefix for consistency)
from src.config.llm_config_manager import LLMConfigManager # 修正文件名和类名
from src.collectors.categories import get_category_name # Import the function
# from src.core.containers import Container # 移除顶层导入以避免循环

# 在 NewsStorage 类外部或内部添加辅助函数

def convert_datetime_to_iso(obj):
    """递归转换数据结构中的 datetime 对象为 ISO 格式字符串"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: convert_datetime_to_iso(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime_to_iso(item) for item in obj]
    return obj


class AppService(QObject): # 继承 QObject 以便使用信号槽
    """应用程序服务层"""

    # 定义信号，用于通知UI更新
    sources_updated = pyqtSignal() # 新闻源列表发生变化
    news_refreshed = pyqtSignal(list) # 新闻刷新完成，传递新闻列表
    status_message_updated = pyqtSignal(str) # 状态栏消息更新
    refresh_started = pyqtSignal() # NEW: 刷新开始信号
    # 添加刷新进度信号
    refresh_progress = pyqtSignal(int, int)  # (当前进度, 总数)
    refresh_complete = pyqtSignal(bool, str) # 修改信号定义以包含成功状态和消息
    refresh_cancelled = pyqtSignal() # 保留，如果其他地方需要专门处理取消事件

    selected_news_changed = pyqtSignal(object) # 发射选中的 NewsArticle 或 None

    # Removed @inject decorator
    def __init__(self,
                 # Parameters now required for manual instantiation
                 llm_config_manager: LLMConfigManager,
                 storage: NewsStorage,
                 source_manager: SourceManager,
                 llm_service: LLMService):
        super().__init__()
        self.logger = logging.getLogger('news_analyzer.core.app_service')
        self.logger.debug("Initializing AppService (manual instantiation)...") # Updated log message

        # --- 将传入的依赖赋值给实例属性 ---
        self.llm_config_manager = llm_config_manager
        self.storage = storage
        self.source_manager = source_manager
        self.llm_service = llm_service
        # --- 赋值结束 ---

        # Initialize attributes that don't depend on injected services yet
        self.news_sources: List[NewsSource] = [] # 内存中的新闻源配置列表
        self.news_cache: List[NewsArticle] = [] # --- 新增：内存缓存 ---
        self.collectors: Dict[str, object] = {} # Initialize as empty dict

        # 刷新状态
        self._is_refreshing = False
        self._cancel_refresh = False

        self.logger.info("AppService __init__ complete (dependencies assigned).")


    def _initialize_dependencies(self):
        """Initialize components that depend on assigned service instances. Should be called after __init__."""
        self.logger.debug("Initializing AppService dependencies (_initialize_dependencies)...")

        # Check if dependencies were assigned correctly in __init__
        if not all([hasattr(self, attr) and getattr(self, attr) is not None for attr in ['storage', 'source_manager', 'llm_service', 'llm_config_manager']]):
             self.logger.error("Dependencies not assigned correctly before calling _initialize_dependencies!")
             # Handle error appropriately, maybe raise?
             return # Or raise specific error

        # Initialize collectors
        self.collectors = {
            'rss': RSSCollector(), # Removed llm_service dependency
            'pengpai': PengpaiCollector()
        }
        self.logger.debug(f"Collectors initialized: {list(self.collectors.keys())}")

        # --- 连接澎湃采集器的选择器失效信号 ---
        pengpai_collector = self.collectors.get('pengpai')
        if isinstance(pengpai_collector, PengpaiCollector):
            try:
                # 使用 Qt.QueuedConnection 确保信号在主线程处理（如果 AppService 在不同线程）
                pengpai_collector.selector_failed.connect(self._handle_pengpai_selector_failure, Qt.QueuedConnection)
                self.logger.info("已连接 PengpaiCollector 的 selector_failed 信号。")
            except Exception as e:
                self.logger.error(f"连接 PengpaiCollector 信号失败: {e}", exc_info=True)
        else:
            self.logger.warning("未找到 PengpaiCollector 实例或类型不匹配，无法连接信号。")
        # --- 信号连接结束 ---

        # Connect signals from dependencies
        try:
            if hasattr(self.source_manager, 'sources_updated') and callable(getattr(self.source_manager.sources_updated, 'connect', None)):
                 self.source_manager.sources_updated.connect(self.sources_updated.emit)
                 self.logger.debug("Connected source_manager.sources_updated signal.")
            else:
                 self.logger.warning("source_manager does not have sources_updated signal or connect method.")
        except Exception as e:
            self.logger.error(f"Error connecting source_manager signal: {e}", exc_info=True)

        # Load initial news (depends on storage and source_manager)
        self._load_initial_news()
        self.logger.debug("AppService dependencies initialized.")

    # --- 移除 AppService 中直接处理源配置的方法 ---
    # 源管理逻辑已移至 SourceManager

    # +++ 保留调用 SourceManager 的接口方法 +++
    def get_sources(self) -> List[NewsSource]:
        """获取所有新闻源配置 (通过 SourceManager)。

        Returns:
            List[NewsSource]: 当前所有新闻源配置对象的列表副本。
        """
        return self.source_manager.get_sources()

    def add_source(self, source: NewsSource):
        """添加新的新闻源 (通过 SourceManager)。

        Args:
            source (NewsSource): 要添加的新闻源对象。

        Raises:
            ValueError: 如果添加的源名称或 URL 与现有源冲突。
        """
        # AppService 可能需要处理添加前的验证或添加后的额外逻辑
        self.source_manager.add_source(source)
        # SourceManager 会发射 sources_updated 信号，AppService 已连接

    def remove_source(self, source_name: str):
        """移除指定名称的新闻源 (通过 SourceManager)。

        Args:
            source_name (str): 要移除的新闻源的名称。

        Raises:
            ValueError: 如果尝试删除内置的澎湃新闻源。
        """
        self.source_manager.remove_source(source_name)
        # SourceManager 会发射 sources_updated 信号

    def update_source(self, source_name: str, updated_data: dict):
        """更新指定新闻源的信息 (通过 SourceManager)。

        Args:
            source_name (str): 要更新的新闻源的当前名称。
            updated_data (dict): 包含要更新的属性和新值的字典。
                                 支持的键包括 'name', 'url', 'category', 'enabled', 'notes'。

        Raises:
            ValueError: 如果更新导致名称或 URL 冲突，或者提供了无效的值（如空名称/URL）。
        """
        self.source_manager.update_source(source_name, updated_data)
        # SourceManager 会发射 sources_updated 信号
    # +++ 添加结束 +++


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
                # 从 SourceManager 获取最新的源信息
                source_map = {source.name: source for source in self.source_manager.get_sources()}
                for article in initial_news_articles:
                    source_config = source_map.get(article.source_name)
                    if source_config:
                        # Convert category ID to display name
                        category_id = source_config.category
                        article.category = get_category_name(category_id)
                        self.logger.debug(f"为 '{article.title[:20]}...' (来源: {article.source_name}) 设置分类为: {article.category} (ID: {category_id})")
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
        except AttributeError as ae:
             # Catch specific error if storage is still Provide
            if "'Provide' object has no attribute" in str(ae):
                 self.logger.error(f"加载初始新闻失败: 依赖项 'storage' 尚未解析! Error: {ae}", exc_info=True)
            else:
                 self.logger.error(f"加载初始新闻时发生属性错误: {ae}", exc_info=True)
            self.status_message_updated.emit("加载历史新闻失败 (依赖错误)")
        except Exception as e:
            self.logger.error(f"加载初始新闻失败: {e}", exc_info=True)
            self.status_message_updated.emit("加载历史新闻失败")


    def refresh_all_sources(self):
        """触发所有启用的新闻源进行刷新。

        此方法会启动一个后台线程来执行实际的刷新操作，以避免阻塞 UI。
        刷新过程中会发射 `refresh_started`, `refresh_progress`, `news_refreshed`,
        `refresh_complete` 或 `refresh_cancelled` 信号。
        如果已有刷新操作正在进行，则忽略本次请求。
        """
        if self._is_refreshing:
            self.logger.warning("刷新操作正在进行中，忽略重复请求")
            return

        self._is_refreshing = True
        self._cancel_refresh = False
        self.logger.info("开始刷新所有启用的新闻源...")
        self.status_message_updated.emit("正在刷新新闻...")
        self.refresh_started.emit() # 发射刷新开始信号

        # 从 SourceManager 获取需要刷新的源列表
        sources_to_refresh = [s for s in self.get_sources() if s.enabled] # 使用 get_sources() 方法
        if not sources_to_refresh:
            self.logger.info("没有启用的新闻源需要刷新")
            self._is_refreshing = False
            self.refresh_complete.emit(True, "没有启用的新闻源") # Emit completion signal even if nothing to refresh
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
        """请求取消当前正在进行的刷新操作。

        设置一个标志位，后台刷新线程会在检查点检查此标志并停止刷新。
        如果取消成功，将发射 `refresh_cancelled` 信号。
        """
        if self._is_refreshing:
            self.logger.info("收到外部取消刷新请求")
            self._cancel_refresh = True
        else:
            self.logger.warning("收到取消请求，但当前没有刷新操作在进行")

    def _do_refresh(self, sources_to_refresh_input): # Rename input arg slightly for clarity
        # print("--- ENTERING _do_refresh ---") # Removed debug print
        """实际执行刷新操作，确保在 finally 中发射完成或取消信号"""
        all_raw_news_items = [] # Store raw dicts first
        errors = []

        # --- 添加日志：检查 AppService 内部认为的所有源 ---
        all_sources_in_appservice = self.get_sources()
        self.logger.info(f"AppService: _do_refresh - All sources from self.get_sources(): {[(s.name, s.enabled) for s in all_sources_in_appservice]}")
        # --- 现在根据这些源构建实际要刷新的列表 ---
        sources_to_refresh = [s for s in all_sources_in_appservice if s.enabled]
        total = len(sources_to_refresh)
        self.logger.info(f"_do_refresh: 开始处理 {total} 个启用的源")
        # --- 打印将要刷新的源列表 (基于过滤后的) ---
        self.logger.info(f"AppService: _do_refresh - sources_to_refresh (enabled only) contains: {[s.name for s in sources_to_refresh]}")
        # --- 优先处理澎湃新闻 ---
        sources_to_refresh.sort(key=lambda s: s.type != 'pengpai') # pengpai 类型会排在前面
        self.logger.info(f'刷新顺序调整后: {[s.name for s in sources_to_refresh]}')
        final_articles = []
        was_cancelled = False # 局部变量跟踪取消状态

        # --- 获取当前缓存中新闻的链接集合 ---
        existing_links = {article.link for article in self.news_cache if article.link}
        self.logger.debug(f"刷新前缓存中存在 {len(existing_links)} 个唯一链接。")
        # --- 获取结束 ---

        try: # 主要处理逻辑
            # 移除这里的 'from datetime import datetime as dt_class'
            for i, source_config in enumerate(sources_to_refresh):
                if self._cancel_refresh:
                    self.logger.info("刷新操作在循环中被取消")
                    was_cancelled = True # 设置取消标志
                    break # 跳出循环，进入 finally 处理

                self.logger.info(f"_do_refresh: 准备发射进度信号 ({i+1}/{total})")
                self.refresh_progress.emit(i+1, total)

                # --- 添加日志：检查当前源的启用状态 ---
                self.logger.info(f"AppService: _do_refresh - Checking source: '{source_config.name}', Enabled: {source_config.enabled}")
                if source_config.enabled:
                    collector_type = source_config.type
                    if collector_type in self.collectors:
                        collector = self.collectors[collector_type]
                        try:
                            self.logger.info(f"DEBUG - AppService: 准备调用收集器 '{collector_type}' (类型: {type(collector)}) 处理来源: {source_config.name}") # DEBUG LOG
                            self.logger.info(f"正在刷新来源: {source_config.name} ({collector_type})")
                            # 传递一个检查取消状态的回调函数
                            cancel_checker = lambda: self._cancel_refresh
                            # --- 添加更明确的调用前日志 ---
                            self.logger.info(f"AppService: 即将调用 collector.collect() for source '{source_config.name}' (Type: {collector_type})")
                            # Collect raw dictionaries
                            raw_news_items = collector.collect(source_config, cancel_checker=cancel_checker)
                            # Add source_name to each item BEFORE extending the main list
                            for item in raw_news_items:
                                item['source_name'] = source_config.name
                            all_raw_news_items.extend(raw_news_items) # Add items with source_name
                            self.logger.info(f"DEBUG - AppService: 收集器 '{collector_type}' 返回了 {len(raw_news_items)} 条原始新闻条目 for source '{source_config.name}'") # DEBUG LOG

                            # 尝试更新时间戳
                            try:
                                source_config.last_update = datetime.now() # 恢复使用顶层 datetime
                                source_config.error_count = 0
                                source_config.last_error = None
                            except AttributeError as e_dt:
                                # 记录错误，但不重新引发
                                self.logger.critical(f"捕获到 AttributeError: {e_dt}", exc_info=True)
                                errors.append(f"{source_config.name}: {e_dt}")
                                source_config.error_count += 1
                                source_config.last_error = str(e_dt)
                                source_config.last_update = None # 明确设为 None

                        except Exception as e: # 捕获 collect 或其他步骤的错误
                            self.logger.error(f"刷新来源 {source_config.name} 失败: {e}", exc_info=True)
                            errors.append(f"{source_config.name}: {e}")
                            source_config.error_count += 1
                            source_config.last_error = str(e)
                    else:
                        self.logger.warning(f"未找到类型为 '{collector_type}' 的收集器来处理来源: {source_config.name}")

            # --- 循环结束后的处理 (仅在未取消时执行) ---
            if not was_cancelled:
                if all_raw_news_items:
                    self.logger.info(f"_do_refresh: 刷新共收集到 {len(all_raw_news_items)} 条原始新闻条目") # <-- 现有日志
                    # --- 添加日志: 打印部分原始数据 ---
                    if all_raw_news_items:
                         self.logger.debug(f"  原始数据示例 (前2条): {all_raw_news_items[:2]}")
                    # --- 日志结束 ---

                    # --- Convert and Deduplicate ---
                    self.logger.debug("开始将原始数据转换为 NewsArticle 对象...") # <-- 新增日志
                    converted_articles = []
                    # --- 添加日志：确认进入转换循环 ---
                    self.logger.info(f"AppService: 准备进入转换和分类循环，处理 {len(all_raw_news_items)} 条原始数据...")
                    # ---
                    for item_dict in all_raw_news_items:
                        article = self._convert_dict_to_article(item_dict)
                        if article:
                            # Assign category based on source config AFTER conversion
                            source_map = {s.name: s for s in self.get_sources()} # 优化：可以在循环外创建一次
                            source_cfg = source_map.get(article.source_name)
                            # --- 修改日志级别为 INFO ---
                            self.logger.info(f"处理文章 '{article.title[:20]}...' (来源: {article.source_name})")
                            if source_cfg:
                                self.logger.info(f"  找到来源配置: {source_cfg.name}, 分类ID: {source_cfg.category}")
                                assigned_category_name = get_category_name(source_cfg.category)
                                article.category = assigned_category_name # Assign category NAME using the ID from config
                                self.logger.info(f"  分配的分类名称: {assigned_category_name}")
                            else:
                                self.logger.warning(f"  未找到来源 '{article.source_name}' 的配置，将分类设为 '未分类'")
                                article.category = "未分类" # Default if source not found
                            # --- 日志级别修改结束 ---
                            converted_articles.append(article)
                    self.logger.info(f"转换完成，共获得 {len(converted_articles)} 个 NewsArticle 对象 (去重前)") # <-- 修改日志级别

                    # Deduplicate based on link AFTER conversion and category assignment
                    unique_articles_map = {article.link: article for article in converted_articles if article.link}
                    final_articles = list(unique_articles_map.values())
                    self.logger.info(f"去重后剩余 {len(final_articles)} 条新闻") # <-- 修改日志级别为 INFO

                    # --- 设置 is_new 标记 ---
                    new_count = 0
                    for article in final_articles:
                        if article.link not in existing_links:
                            article.is_new = True
                            new_count += 1
                    self.logger.info(f"标记了 {new_count} 条新闻为 '新'")
                    # --- is_new 标记设置结束 ---
                    # --- 加载已读状态 ---
                    self.logger.info(f"开始为 {len(final_articles)} 条新闻加载已读状态...")
                    read_count = 0
                    for article in final_articles:
                        try:
                            # 确保 article.link 存在且不为空
                            if article.link:
                                is_read = self.storage.is_item_read(article.link)
                                self.logger.debug(f"Checking read status for {article.link}: {is_read}")
                                article.is_read = is_read
                                if is_read:
                                    read_count += 1
                            else:
                                article.is_read = False # 没有链接的文章视为未读
                                self.logger.warning(f"文章 '{article.title[:20]}...' 缺少链接，无法检查已读状态。")
                        except Exception as read_e:
                            self.logger.warning(f"检查文章 '{article.title[:20]}...' (链接: {article.link}) 的已读状态时出错: {read_e}")
                            article.is_read = False # 出错时默认为未读
                    self.logger.info(f"已加载已读状态，其中 {read_count} 条标记为已读。")
                    # --- 已读状态加载结束 ---


                    # --- End Convert and Deduplicate ---

                    # --- Convert articles back to dicts for saving ---
                    news_data_to_save = []
                    for article in final_articles:
                         # Assuming NewsArticle has a method or can be easily converted
                         # This might need adjustment based on NewsArticle structure
                         article_dict = article.to_dict() if hasattr(article, 'to_dict') else vars(article).copy()
                         # Ensure datetime is converted for saving
                         article_dict = convert_datetime_to_iso(article_dict)
                         news_data_to_save.append(article_dict)
                    # --- End conversion for saving ---

                    try:
                        self.storage.save_news(news_data_to_save)
                        self.logger.info(f"已将 {len(news_data_to_save)} 条新闻数据保存到存储")
                    except Exception as save_e:
                        self.logger.error(f"保存新闻数据失败: {save_e}", exc_info=True)
                        errors.append(f"保存失败: {save_e}")

                    self.news_cache = final_articles # 更新缓存
                    self.logger.info(f"内存缓存已更新，包含 {len(self.news_cache)} 条新闻")
                else:
                    self.logger.warning("刷新完成，未获取到任何新新闻")
                    # Don't clear cache if no new news, keep old news


        except Exception as outer_e: # 捕获主要逻辑中的意外错误
            self.logger.error(f"_do_refresh 过程中发生意外错误: {outer_e}", exc_info=True)
            try:
                self.status_message_updated.emit(f"刷新过程中发生错误: {outer_e}")
            except Exception as status_e:
                self.logger.error(f"发射错误状态消息失败: {status_e}")

        finally: # 确保状态重置和信号发射
            self.logger.debug("_do_refresh finally block executing")
            final_success = False # Default to failure
            final_message = "刷新过程中发生未知错误" # Default message
            try:
                if was_cancelled or self._cancel_refresh: # 再次检查以防万一
                    self.logger.info("在 finally 中检测到取消状态，发射 refresh_cancelled 和 refresh_complete(False)")
                    self.refresh_cancelled.emit()
                    final_success = False
                    final_message = "刷新已取消"
                    # 发射 refresh_complete 信号，表明刷新结束（但未成功）
                    self.refresh_complete.emit(final_success, final_message)
                else:
                    # 根据错误和获取的文章确定最终状态和消息
                    if errors:
                        final_success = False
                        final_message = f"刷新完成但部分来源出错: {'; '.join(errors)}"
                        self.status_message_updated.emit(final_message) # 更新状态栏
                    elif final_articles:
                        final_success = True
                        final_message = f"刷新完成，获取 {len(final_articles)} 条新闻"
                        self.status_message_updated.emit(final_message) # 更新状态栏
                    else:
                        final_success = True # 技术上成功，只是没有新内容
                        final_message = "刷新完成，未获取到新新闻"
                        self.status_message_updated.emit(final_message) # 更新状态栏

                    self.logger.info(f"在 finally 中发射 refresh_complete({final_success}, '{final_message[:50]}...')") # 截断消息以防过长
                    # 确保 final_articles 是 list 类型
                    articles_to_emit = final_articles if isinstance(final_articles, list) else []
                    # --- 添加日志：发射前确认数据 ---
                    self.logger.info(f"AppService: 准备发射 news_refreshed 信号，共 {len(articles_to_emit)} 条新闻。示例: {articles_to_emit[0].title if articles_to_emit else '无'}")
                    # --- 日志结束 ---
                    self.logger.info(f"_do_refresh: 发射 news_refreshed 信号，包含 {len(articles_to_emit)} 条新闻") # 保留原有日志
                    self.news_refreshed.emit(articles_to_emit) # 发射带有数据的 news_refreshed 信号
                    self.refresh_complete.emit(final_success, final_message) # 发射带状态的 refresh_complete 信号
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
                 article.category = source_config.category # This line seems redundant now
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

    def get_llm_client(self) -> LLMService:
        """获取LLM客户端实例"""
        # This method might be deprecated if llm_service is directly accessed
        self.logger.warning("get_llm_client() is deprecated, access self.llm_service directly.")
        return self.llm_service

    def get_news_by_category(self, category_display_name: str) -> List[NewsArticle]: # 参数改为显示名称
        """根据分类显示名称从内存缓存中获取新闻。

        Args:
            category_display_name (str): 要筛选的分类的显示名称 (例如 "科技", "财经", 或 "所有")。

        Returns:
            List[NewsArticle]: 属于该分类的新闻文章列表。
                             如果 `category_display_name` 为 "所有"，则返回所有缓存的新闻。
                             如果找不到对应的分类，返回空列表。
        """
        self.logger.debug(f"从缓存根据分类显示名称 '{category_display_name}' 获取新闻")
        if category_display_name == "所有":
            self.logger.debug(f"返回所有 {len(self.news_cache)} 条缓存新闻")
            return self.news_cache
        else:
            # --- 根据显示名称查找分类 ID ---
            # Category assignment now happens after conversion in _do_refresh
            # We filter based on the assigned category string directly
            filtered_articles = [news for news in self.news_cache if news.category == category_display_name]
            self.logger.debug(f"分类 '{category_display_name}' 从缓存筛选出 {len(filtered_articles)} 条新闻")
            return filtered_articles


    def search_news(self, query: str, field: str = "标题和内容", days: Optional[int] = None) -> List[NewsArticle]:
        """根据关键词、字段和时间范围从内存缓存中搜索新闻。

        Args:
            query (str): 搜索关键词。如果为空字符串，则仅应用时间筛选。
            field (str, optional): 要搜索的字段 ("标题和内容", "仅标题", "仅内容")。
                                 默认为 "标题和内容"。
            days (Optional[int], optional): 搜索最近 N 天的新闻。如果为 None，则不限制时间范围。
                                          默认为 None。

        Returns:
            List[NewsArticle]: 匹配搜索条件的新闻文章列表。
        """
        self.logger.info(f"开始在缓存中搜索: query='{query}', field='{field}', days={days}")
        if not query and days is None:
            self.logger.info("搜索查询为空且未指定天数，返回所有缓存新闻")
            return self.news_cache # 如果查询为空且没有时间限制，返回所有

        results = self.news_cache # 从缓存开始

        # 1. 时间筛选
        if days is not None:
            cutoff_date = datetime.now() - timedelta(days=days)
            results = [news for news in results if news.publish_time and news.publish_time >= cutoff_date]
            self.logger.debug(f"时间筛选后剩余 {len(results)} 条新闻 (最近 {days} 天)")

        # 2. 关键词筛选
        if query:
            query_lower = query.lower()
            filtered_results = []
            for news in results:
                match = False
                if field == "仅标题" or field == "标题和内容":
                    if news.title and query_lower in news.title.lower():
                        match = True
                if not match and (field == "仅内容" or field == "标题和内容"):
                    # 优先搜索 summary，然后是 content
                    if news.summary and query_lower in news.summary.lower():
                        match = True
                    elif news.content and query_lower in news.content.lower():
                        match = True
                if match:
                    filtered_results.append(news)
            results = filtered_results
            self.logger.debug(f"关键词 '{query}' 在字段 '{field}' 筛选后剩余 {len(results)} 条新闻")

        self.logger.info(f"搜索完成，找到 {len(results)} 条匹配新闻")
        return results

    # --- 新增：浏览历史和已读状态管理 ---
    def record_browsing_history(self, news_article: NewsArticle):
        """记录浏览历史"""
        if not news_article:
            return
        self.logger.info(f"AppService: 准备记录浏览历史: {news_article.title[:30]}...")
        try:
            entry = {
                "link": news_article.link,
                "title": news_article.title,
                "source_name": news_article.source_name,
                "browsed_at": datetime.now().isoformat() # 使用 ISO 格式字符串
            }
            self.storage.save_history_entry(entry)
            self.logger.info(f"AppService: 成功调用 save_history_entry 记录: {news_article.title[:30]}")
            # 标记为已读
            self.mark_as_read(news_article.link)
        except Exception as e:
            self.logger.error(f"记录浏览历史失败: {e}", exc_info=True)

    def close_resources(self):
        """关闭所有需要清理的资源，例如 WebDriver"""

    # --- 新增：处理澎湃选择器失效的槽函数 ---
    def _handle_pengpai_selector_failure(self, source_name: str):
        """处理澎湃新闻选择器失效的信号"""
        error_message = f"澎湃新闻源 '{source_name}' 采集失败，可能是网站结构已更改。请前往‘源管理’检查并更新 CSS 选择器。"
        self.logger.error(error_message) # 记录错误日志
        # 确保在主线程发射信号给 UI
        self.status_message_updated.emit(error_message) # 发送状态栏提示
    # --- 槽函数结束 ---
    # --- 注意：以下代码块之前因缩进错误被包含在 _handle_pengpai_selector_failure 中 ---
    # --- 正确的关闭逻辑应在 shutdown 方法中 ---

    # (此处留空，因为关闭逻辑已存在于 shutdown 方法中)

    # --- 新增：选中新闻管理 ---
    def set_selected_news(self, news_article: Optional[NewsArticle]):
        """设置当前选中的新闻文章，并发出信号"""
        self.logger.debug(f"AppService: 设置选中新闻: {news_article.title if news_article else 'None'}")
        # 这里可以添加逻辑，例如如果文章内容不完整，尝试获取完整内容
        # if news_article and not news_article.content:
        #     news_article = self.get_detailed_article(news_article)
        self.selected_news_changed.emit(news_article)

    # --- 新增：已读状态接口 ---
    def is_read(self, link: str) -> bool:
        """检查链接是否已读"""
        if not link: return False
        return self.storage.is_item_read(link)

    def mark_as_read(self, link: str):
        """标记指定链接的新闻为已读，并添加到浏览历史"""
        self.logger.debug(f"AppService: Received request to mark link as read and add to history: {link}")
        if not link:
             self.logger.warning("AppService: 尝试标记空链接为已读或添加到历史")
             return

        # 检查 storage 是否同时具有 add_read_item 和 add_history_entry 方法
        has_read_method = hasattr(self.storage, 'add_read_item')
        has_history_method = hasattr(self.storage, 'add_history_entry')

        if has_read_method and has_history_method:
            # 尝试从内存缓存中查找对应的 NewsArticle 对象
            article_to_add = next((article for article in self.news_cache if article.link == link), None)

            if article_to_add:
                try:
                    # 1. 标记为已读 (影响列表项视觉状态)
                    self.storage.add_read_item(link)
                    self.logger.info(f"AppService: Called storage.add_read_item for link: {link}")

                    # 2. 添加到浏览历史 (填充历史记录面板)
                    self.storage.add_history_entry(article_to_add)
                    # 注意: add_history_entry 应该在其内部处理自己的日志记录
                    self.logger.info(f"AppService: Called storage.add_history_entry for article: {article_to_add.title[:30]}...")

                    # 3. 更新内存缓存中的状态 (推荐)
                    article_to_add.is_read = True
                    self.logger.debug(f"Updated is_read status in cache for link: {link}")

                    # 4. (可选) 发射信号通知UI状态变化
                    # self.read_status_changed.emit(link, True)

                except Exception as e:
                    self.logger.error(f"处理标记已读/添加历史时出错 (link: {link}): {e}", exc_info=True)
            else:
                # 未在缓存中找到文章，仅标记为已读
                self.logger.warning(f"Mark as read: Could not find article with link {link} in cache to add to history. Only marking as read.")
                try:
                    self.storage.add_read_item(link)
                    self.logger.info(f"AppService: Called storage.add_read_item for link (not found in cache): {link}")
                    # 在这种情况下，我们无法添加历史记录，因为没有文章对象
                except Exception as e:
                    self.logger.error(f"调用 storage.add_read_item 时出错 (link not in cache): {e}", exc_info=True)
        elif has_read_method:
             # 只有 add_read_item 方法，执行旧逻辑（仅标记已读）
             self.logger.warning(f"NewsStorage has add_read_item but not add_history_entry. Only marking link {link} as read.")
             try:
                 self.storage.add_read_item(link)
                 self.logger.info(f"AppService: Called storage.add_read_item for link: {link}")
                 # Optionally update cache status here too if desired
                 article_in_cache = next((article for article in self.news_cache if article.link == link), None)
                 if article_in_cache:
                     article_in_cache.is_read = True
                     self.logger.debug(f"Updated is_read status in cache for link: {link}")
             except Exception as e:
                 self.logger.error(f"调用 storage.add_read_item 时出错 (only read method available): {e}", exc_info=True)
        else:
            # Storage 对象缺少必要的方法
            missing_methods = []
            if not has_read_method:
                missing_methods.append('add_read_item')
            if not has_history_method: # This condition might be redundant if we reached here, but good for clarity
                missing_methods.append('add_history_entry')
            self.logger.warning(f"NewsStorage 对象缺少方法: {', '.join(missing_methods)}！标记已读/添加历史操作未执行。")

    def shutdown(self):
        """执行关闭前的清理工作"""
        self.logger.info("AppService shutdown requested.")
        self.close_resources()

    def get_detailed_article(self, article: NewsArticle) -> NewsArticle:
        """
        尝试获取指定文章的详细内容（主要是 HTML 格式）。

        Args:
            article (NewsArticle): 需要获取详情的文章对象（可能内容不完整）。

        Returns:
            NewsArticle: 更新了 content 字段的文章对象。如果获取失败或不支持，
                         则返回原始文章对象（content 可能不变或包含错误信息）。
        """
        self.logger.info(f"请求获取文章详情: '{article.title[:30]}...' (来源: {article.source_name})")
        if not article or not article.link:
            self.logger.warning("传入的文章对象无效或缺少链接，无法获取详情。")
            return article # 返回原始文章

        # 查找对应的 NewsSource 配置以获取 collector 类型
        # source_config = self.source_manager.find_source_by_name(article.source_name) # 错误的方法调用
        source_config = next((s for s in self.source_manager.get_sources() if s.name == article.source_name), None) # 正确的查找方式
        collector_type = None # 初始化 collector_type

        if source_config:
            collector_type = source_config.type
            self.logger.debug(f"文章来源 '{article.source_name}' 配置找到，类型确定为: {collector_type}")
        elif article.source_name == "未知来源" and article.link and article.link.startswith("https://m.thepaper.cn"):
             self.logger.warning(f"来源为 '未知来源' 但链接指向澎湃，强制设置类型为 'pengpai' 并更新来源名称。")
             collector_type = 'pengpai'
             article.source_name = "澎湃新闻" # 更新文章对象的来源名称，确保传递给对话框
        else:
             self.logger.warning(f"通过名称 '{article.source_name}' 未找到配置，且不符合澎湃链接规则，无法获取详情。")
             return article # 返回原始文章

        # --- 根据确定的 collector_type 执行操作 ---
        if collector_type == 'pengpai':
            collector = self.collectors.get('pengpai')
            if collector and hasattr(collector, '_fetch_detail'):
                self.logger.info(f"找到 PengpaiCollector，准备调用 _fetch_detail 获取详情: {article.link}")
                try:
                    # 注意：_fetch_detail 是内部方法，理论上应该提供公共接口
                    # 但为了快速验证，我们暂时直接调用它
                    # 并且，这个调用是同步的，可能会阻塞 UI，后续需要优化
                    # 获取 selector_config，如果 source_config 或其 selector_config 为 None，则传递空字典
                    selector_config_to_pass = source_config.selector_config if source_config else {}
                    detail_data = collector._fetch_detail(article.link, selector_config_to_pass or {}, article.source_name)
                    fetched_content = detail_data.get('content')

                    if fetched_content and "失败" not in fetched_content and "无效" not in fetched_content:
                        self.logger.info(f"成功获取到澎湃新闻详情内容，长度: {len(fetched_content)}")
                        article.content = fetched_content # 更新文章内容
                        # 可以考虑也更新其他字段，如 pub_date, author
                        # article.publish_time = self._parse_datetime(detail_data.get('pub_date')) or article.publish_time
                        # article.author = detail_data.get('author') or article.author
                    elif fetched_content: # 内容包含错误信息
                         self.logger.error(f"获取澎湃新闻详情失败（Collector 返回错误信息）: {fetched_content}")
                         # 可以选择将错误信息放入 content，或者保留原始内容
                         # article.content = f"获取详情失败: {fetched_content}"
                    else:
                         self.logger.warning(f"调用 PengpaiCollector._fetch_detail 未返回有效内容。")

                except Exception as e:
                    self.logger.error(f"调用 PengpaiCollector._fetch_detail 时发生异常: {e}", exc_info=True)
                    # 可以选择将错误信息放入 content
                    # article.content = f"获取详情时发生错误: {e}"
            else:
                self.logger.warning("未找到 PengpaiCollector 或其 _fetch_detail 方法。")

        elif collector_type == 'rss':
            # RSS 源通常在 collect 时已获取完整内容，无需额外获取详情
            self.logger.info(f"文章来源为 RSS ({article.source_name})，通常无需额外获取详情。")
            # 可以选择在这里检查 content 是否为空，如果为空尝试用 requests 简单获取一下？
            # 但目前假设 RSS 源内容是完整的
            pass
        else:
            self.logger.warning(f"未知的 Collector 类型 '{collector_type}'，无法获取详情。")

        return article # 返回（可能已更新的）文章对象

    # --- 新增：辅助方法，将 NewsArticle 列表转换为字典列表 ---
    def _convert_articles_to_dicts(self, articles: List[NewsArticle]) -> List[Dict]:
        """将 NewsArticle 对象列表转换为适合保存的字典列表"""
        dict_list = []
        for article in articles:
            article_dict = article.to_dict() if hasattr(article, 'to_dict') else vars(article).copy()
            # 确保 datetime 转换为字符串
            article_dict = convert_datetime_to_iso(article_dict)
            dict_list.append(article_dict)
        return dict_list
    # --- 新增结束 ---
