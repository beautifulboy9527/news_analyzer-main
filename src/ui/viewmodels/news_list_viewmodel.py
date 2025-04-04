import logging
from typing import List, Optional, Dict, Any # 确保导入 List, Optional
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, Qt, QTimer # 导入 QTimer
from datetime import datetime, timedelta # 导入 datetime, timedelta

# 导入模型和核心服务
from src.models import NewsArticle
from src.core.app_service import AppService # 确保 AppService 被导入

class NewsListViewModel(QObject):
    """
    新闻列表的 ViewModel。

    管理新闻数据的获取、过滤和状态，并通知视图更新。
    """

    # --- 信号 ---
    # 当需要显示的新闻列表更新时发射
    news_list_changed = pyqtSignal()
    # 当选中的新闻项发生变化时发射
    selected_news_changed = pyqtSignal()
    # 当已读状态需要更新时发射 (可以传递 link 或整个 article)
    read_status_changed = pyqtSignal(str, bool) # 发射新闻链接和状态

    def __init__(self, app_service: AppService, parent: Optional[QObject] = None):
        """
        初始化 NewsListViewModel。

        Args:
            app_service (AppService): 应用程序核心服务实例。
            parent (Optional[QObject]): 父对象，用于 Qt 对象树管理。
        """
        super().__init__(parent)
        # --- Use root logger directly ---
        self.logger = logging.getLogger() # Get root logger
        self.logger.info(f"NewsListViewModel now using root logger. Effective level: {logging.getLevelName(self.logger.getEffectiveLevel())}")
        # --- End use root logger ---
        self._app_service = app_service
        self._all_news: List[NewsArticle] = [] # Store all loaded articles
        self._filtered_news: List[NewsArticle] = [] # Store currently filtered/sorted articles
        self._current_category: str = "所有"
        self._current_search_term: str = ""
        self._current_search_fields: List[str] = ["title", "content"]
        self._sort_order = Qt.DescendingOrder # 默认降序
        self._sort_column = 'publish_time' # 默认按发布时间

        self._current_days_filter: Optional[int] = None # 默认不过滤天数
        self._start_date_filter: Optional[datetime] = None # 新增：开始日期过滤器
        self._end_date_filter: Optional[datetime] = None   # 新增：结束日期过滤器
        self._connect_signals()
        # self._load_initial_data() # 不要立即加载
        QTimer.singleShot(0, self._load_initial_data) # 使用 QTimer 延迟加载
        self.logger.info("NewsListViewModel initialized.")

    def _connect_signals(self):
        """连接必要的信号"""
        # 连接 AppService 的 news_refreshed 信号到新的处理槽
        self._app_service.news_refreshed.connect(self._handle_app_news_refreshed)
        # 移除 AppService.read_status_changed 连接
        # self._app_service.read_status_changed.connect(self._handle_read_status_changed)
        self.logger.debug("ViewModel signals connected to AppService.")


    def _load_initial_data(self):
        """加载初始数据并应用默认过滤器和排序"""
        self.logger.debug("Loading initial data from AppService cache...")
        self._all_news = self._app_service.news_cache[:] # 直接访问 news_cache 属性 (并创建副本)
        self.logger.info(f"ViewModel: Initial data loaded/reloaded. All news count: {len(self._all_news)}") # <-- 修改日志级别
        self._apply_filters_and_sort() # 应用过滤器和排序
        self.logger.info("ViewModel: Emitting news_list_changed signal after loading/reloading data.") # <-- 新增日志
        self.news_list_changed.emit() # 通知 View 更新

    # --- 属性 ---
    @property
    def newsList(self) -> List[NewsArticle]:
        """获取当前过滤和排序后的新闻列表"""
        return self._filtered_news

    # --- 公共方法/槽 ---
    @pyqtSlot(str)
    def filter_by_category(self, category: str):
        """按分类过滤新闻"""
        self.logger.debug(f"Filtering news by category: {category}")
        self._current_category = category
        self._apply_filters_and_sort()
        self.news_list_changed.emit()

    @pyqtSlot(str, str) # 第二个参数现在是字符串
    def search_news(self, term: str, field_description: str): # 修正类型提示和行尾冒号
        """搜索新闻"""
        self.logger.debug(f"Received search request: term='{term}', field_description='{field_description}'")
        self._current_search_term = term.lower()

        # 将描述性字符串映射到实际的字段列表 (修正缩进)
        if field_description == "标题和内容":
            self._current_search_fields = ["title", "content"]
        elif field_description == "仅标题":
            self._current_search_fields = ["title"]
        elif field_description == "仅内容":
            self._current_search_fields = ["content"]
        else:
            self.logger.warning(f"Unknown field description '{field_description}', defaulting to title and content.")
            self._current_search_fields = ["title", "content"] # 默认或错误处理

        self.logger.debug(f"Searching news with term '{self._current_search_term}' in mapped fields {self._current_search_fields}") # 修正缩进
        self._apply_filters_and_sort()
        self.news_list_changed.emit()

    @pyqtSlot(int)

    @pyqtSlot()
    def clear_search(self):
        """清除搜索条件并更新列表"""
        self.logger.debug("Clearing search term and updating list.")
        if self._current_search_term: # 只有在确实有搜索词时才更新
            self._current_search_term = ""
            self._apply_filters_and_sort()
            self.news_list_changed.emit()

    def filter_by_days(self, days: int):
        """按最近天数过滤新闻"""
        self.logger.debug(f"Filtering news by last {days} days.")
        # 如果 days 是一个特殊值（例如 365 代表一年或更大值代表全部），则设为 None
        if days >= 365: # 假设 365 或更大表示“所有时间”
            self._current_days_filter = None
            self.logger.debug("Days filter set to None (all time).")
        else:
            self._current_days_filter = days
            self.logger.debug(f"Days filter set to {days}.")
        self._apply_filters_and_sort()
        self.news_list_changed.emit()


    @pyqtSlot(datetime, datetime)
    def filter_by_date_range(self, start_date: datetime, end_date: datetime):
        """按指定的开始和结束日期过滤新闻"""
        self.logger.debug(f"Filtering news by date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        # 清除按天数过滤的设置，因为日期范围优先
        self._current_days_filter = None
        # 存储日期范围以供 _apply_filters_and_sort 使用
        self._start_date_filter = start_date
        self._end_date_filter = end_date
        self._apply_filters_and_sort()
        self.news_list_changed.emit()

    @pyqtSlot(str, Qt.SortOrder)
    def sort_news(self, column: str, order: Qt.SortOrder):
        """对新闻列表进行排序"""
        self.logger.debug(f"Sorting news by column '{column}' in order {order}")
        self._sort_column = column
        self._sort_order = order
        self._apply_filters_and_sort()
        self.news_list_changed.emit()

    @pyqtSlot(NewsArticle)
    def select_news(self, article: Optional[NewsArticle]):
        """处理新闻项的选择"""
        self.logger.info(f"NewsListViewModel.select_news called with article: {article.title[:30] if article else 'None'}...")
        if article:
            self.logger.debug(f"News selection changed in ViewModel: {article.title[:30]}")
            # 通知 AppService 选中了新闻
            self._app_service.set_selected_news(article)
            # 标记为已读
            if not self.is_read(article.link): # 调用 is_read 方法判断
                self.mark_as_read(article.link) # 使用 link 作为唯一标识符
        else:
            self._app_service.set_selected_news(None) # 清除选中

        self.selected_news_changed.emit() # 通知 View 选中项变化（如果需要）

    @pyqtSlot(str)
    def mark_as_read(self, link: str):
        """标记指定链接的新闻为已读，并更新内部状态"""
        self.logger.debug(f"Marking news as read: {link}")
        # 1. 调用 AppService 持久化并更新其内部状态
        self._app_service.mark_as_read(link)

        # 2. 更新 ViewModel 内部缓存的状态以立即反映
        item_found_in_all = False
        for item in self._all_news:
            if item.link == link:
                item.is_read = True
                item_found_in_all = True
                self.logger.debug(f"Updated is_read=True for item in _all_news: {link}")
                break # 假设 link 是唯一的

        item_found_in_filtered = False
        for item in self._filtered_news:
            if item.link == link:
                item.is_read = True
                item_found_in_filtered = True
                self.logger.debug(f"Updated is_read=True for item in _filtered_news: {link}")
                break # 假设 link 是唯一的

        if not item_found_in_all and not item_found_in_filtered:
             self.logger.warning(f"Tried to mark item as read, but link not found in ViewModel caches: {link}")

        # 3. 发射信号通知 View 更新特定项的状态
        self.read_status_changed.emit(link, True)


    # +++ 添加 is_read 方法 +++
    def is_read(self, link: str) -> bool:
        """检查新闻是否已读 (通过 AppService)"""
        return self._app_service.is_read(link)

    # --- 私有方法 ---
    def _apply_filters_and_sort(self):
        """应用当前的过滤器和排序规则"""
        self.logger.debug(f"Applying filters. Current category: {self._current_category}")
        # 从 AppService 获取最新的完整缓存
        self._all_news = self._app_service.news_cache[:]
        filtered = self._all_news

        # 1. 按分类过滤
        if self._current_category != "所有":
            self.logger.debug(f"Filtering by category '{self._current_category}'. News count before: {len(filtered)}")
            filtered = [news for news in filtered if news.category == self._current_category]
            self.logger.debug(f"News count after category filtering: {len(filtered)}")
            if not filtered:
                self.logger.warning(f"Category filter '{self._current_category}' resulted in an empty list.")

        # 2. 按搜索词过滤
        if self._current_search_term:
            term = self._current_search_term
            fields = self._current_search_fields
            self.logger.debug(f"Applying search filter: term='{term}', fields={fields}. News count before: {len(filtered)}")
            original_count_search = len(filtered)
            new_filtered_search = []
            for news in filtered: # 修正 for 循环语法
                found = False
                for field in fields:
                    if hasattr(news, field):
                        value = getattr(news, field)
                        if value is not None:
                            try:
                                value_lower = str(value).lower() # 确保字符串转换和转小写
                                self.logger.debug(f"  Checking article '{news.link[:30]}...' field '{field}': term='{term}' in value='{value_lower[:100]}...'?") # 记录比较细节
                                if term in value_lower:
                                    self.logger.debug(f"    Found term '{term}' in field '{field}' for article '{news.link[:30]}...'")
                                    found = True
                                    break # 在一个字段找到即可
                            except Exception as e:
                                self.logger.warning(f"  Error processing field '{field}' for article '{news.link[:30]}...': {e}")
                if found:
                    new_filtered_search.append(news)
            filtered = new_filtered_search
            self.logger.debug(f"News count after search filtering: {len(filtered)} (was {original_count_search})")

        # 3. 按日期范围过滤 (新增)
        if self._current_days_filter is not None:
            self.logger.debug(f"Applying days filter: last {self._current_days_filter} days.")
            now = datetime.now()
            cutoff_date = now - timedelta(days=self._current_days_filter)
            original_count = len(filtered)
            filtered = [
                news for news in filtered
                if news.publish_time is not None and isinstance(news.publish_time, datetime) and news.publish_time >= cutoff_date
            ]
            self.logger.debug(f"Filtered by date: {original_count} -> {len(filtered)}")


        # 3b. 按指定日期范围过滤 (如果设置了)
        elif self._start_date_filter and self._end_date_filter:
            self.logger.debug(f"Applying date range filter: {self._start_date_filter.strftime('%Y-%m-%d')} to {self._end_date_filter.strftime('%Y-%m-%d')}")
            start_dt = self._start_date_filter
            end_dt = datetime.combine(self._end_date_filter, datetime.max.time())
            original_count = len(filtered)
            new_filtered = []
            for news in filtered:
                self.logger.debug(f"Filtering news item: Link={news.link}, Publish Time={news.publish_time} (Type: {type(news.publish_time)}), Start Date={start_dt} (Type: {type(start_dt)}), End Date={end_dt} (Type: {type(end_dt)})")
                if news.publish_time is not None and isinstance(news.publish_time, datetime):
                    if start_dt <= news.publish_time.date() and news.publish_time <= end_dt:
                        new_filtered.append(news)
            filtered = new_filtered
            self.logger.debug(f"Filtered by specific date range: {original_count} -> {len(filtered)}")

        self.logger.debug(f"Filters applied. Filtered news count: {len(filtered)}")

        # 4. 排序
        reverse_order = (self._sort_order == Qt.DescendingOrder)
        try:
            def sort_key(article: NewsArticle):
                value = getattr(article, self._sort_column, None)
                if self._sort_column == 'publish_time' and value is None:
                    return datetime.min
                elif value is None:
                    return ""
                if self._sort_column == 'publish_time' and not isinstance(value, datetime):
                    try:
                        return datetime.fromisoformat(str(value))
                    except (ValueError, TypeError):
                        self.logger.warning(f"Could not parse date string '{value}' for sorting, using min date.")
                        return datetime.min
                return value

            filtered.sort(key=sort_key, reverse=reverse_order)
            self.logger.debug(f"Sorted news by '{self._sort_column}' {'descending' if reverse_order else 'ascending'}.")
        except TypeError as e:
            self.logger.error(f"Sorting failed for column '{self._sort_column}'. Inconsistent data types might exist. Error: {e}", exc_info=True)
        except Exception as e:
            self.logger.error(f"Unexpected error during sorting: {e}", exc_info=True)

        self._filtered_news = filtered

    # --- 信号处理槽 ---
    @pyqtSlot(str, bool)
    def _handle_read_status_changed(self, link: str, is_read: bool):
        """处理来自 AppService 的已读状态变化信号 (此连接已移除)"""
        self.logger.debug(f"Received read status changed signal for link: {link}")
        # self.read_status_changed.emit(link, is_read) # 不再需要转发

    @pyqtSlot(list) # 添加槽装饰器
    def _handle_app_news_refreshed(self, news_articles: list):
        """处理来自 AppService 的新闻刷新信号"""
        self.logger.info("ViewModel: Received news_refreshed signal from AppService.") # <-- 修改日志级别
        self.logger.debug(f"  Received {len(news_articles)} articles from signal.") # <-- 新增日志
        self._load_initial_data()