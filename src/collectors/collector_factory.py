import logging
from .rss_collector import RSSCollector
from .pengpai_collector import PengpaiCollector
# Import other collectors like JSONFeedCollector if they exist and are needed
# from .json_feed_collector import JSONFeedCollector

class CollectorFactory:
    """
    工厂类，用于创建和管理不同类型的新闻收集器实例。
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # 注册已知的收集器类型及其对应的类
        self._collectors = {
            "rss": RSSCollector,
            "pengpai": PengpaiCollector,
            # "json": JSONFeedCollector, # Example: Add JSONFeedCollector if it's used
            # Add other collector types here as they are implemented
        }
        # Log available collectors at initialization for easier debugging
        self.logger.info(
            f"CollectorFactory initialized. Available collector types: {list(self._collectors.keys())}"
        )

    def get_collector(self, source_type: str):
        """
        根据源类型获取相应的收集器实例。

        Args:
            source_type (str): 新闻源的类型 (例如, 'rss', 'pengpai').

        Returns:
            An instance of the appropriate collector, or None if no collector
            is found for the given type.
        """
        collector_class = self._collectors.get(source_type.lower())
        if collector_class:
            try:
                self.logger.debug(f"Creating instance of {collector_class.__name__} for source type '{source_type}'.")
                return collector_class()  # Instantiate the collector
            except Exception as e:
                self.logger.error(
                    f"Error instantiating collector {collector_class.__name__} for type '{source_type}': {e}",
                    exc_info=True
                )
                return None
        else:
            self.logger.warning(f"No collector registered for source type: '{source_type}'.")
            return None

    def register_collector(self, source_type: str, collector_class):
        """
        动态注册一个新的收集器类型或覆盖现有的收集器。

        Args:
            source_type (str): 要注册的新闻源类型。
            collector_class (class): 与该类型对应的收集器类。
        """
        source_type_lower = source_type.lower()
        if source_type_lower in self._collectors:
            self.logger.warning(
                f"Overriding existing collector for type '{source_type_lower}' "
                f"from {self._collectors[source_type_lower].__name__} to {collector_class.__name__}."
            )
        self._collectors[source_type_lower] = collector_class
        self.logger.info(
            f"Successfully registered collector for type '{source_type_lower}': {collector_class.__name__}."
        ) 