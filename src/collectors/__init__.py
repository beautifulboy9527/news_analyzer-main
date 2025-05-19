"""
新闻收集器包

包含从各种来源收集新闻的模块。
"""

# 从相应的模块导入类，以便可以直接从包中导入
from .rss_collector import RSSCollector
from .pengpai_collector import PengpaiCollector
from .collector_factory import CollectorFactory

# 可以选择性地定义 __all__ 来明确导出哪些名称
__all__ = ['RSSCollector', 'PengpaiCollector', 'CollectorFactory']
