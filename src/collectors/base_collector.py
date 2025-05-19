from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Callable
from ..models import NewsSource # 确保NewsSource被正确导入

class BaseCollector(ABC):
    """
    采集器基类，定义了所有采集器应遵循的接口。
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.source_name = config.get("source_name", "Unknown Source")

    @abstractmethod
    def collect(self, source: NewsSource, progress_callback: Optional[Callable[[int, int], None]] = None) -> List[Dict]:
        """
        执行新闻采集。

        Args:
            source: NewsSource 对象，包含采集目标的信息 (例如 URL, 名称)。
            progress_callback: 可选的回调函数，用于报告进度 (当前处理条目, 总条目数)。

        Returns:
            一个包含新闻数据的字典列表，每个字典代表一条新闻。
            例如：[{
                "title": "新闻标题",
                "link": "新闻链接",
                "summary": "新闻摘要", (可选)
                "pub_date": "发布日期字符串", (ISO 8601格式, 可选)
                "content": "新闻正文", (可选)
                "source_name": "来源名称",
                "category": "分类"
            }]
        """
        pass

    @abstractmethod
    def check_status(self, source: NewsSource, data_dir: str, db_path: str) -> Dict[str, Any]:
        """
        检查新闻源的状态。

        Args:
            source: NewsSource 对象。
            data_dir: 数据存储目录，用于特定类型采集器（如WebDriver profile）。
            db_path: 数据库路径，用于特定类型采集器（如检查数据库条目）。

        Returns:
            一个包含状态信息的字典，例如:
            {
                "source_name": "来源名称",
                "success": True,  # 是否成功连接和获取基本信息
                "message": "状态良好 / 无法访问 / 配置错误等",
                "article_count": 10, # （可选）如果能快速获取，源中的大致文章数
                "last_updated": "YYYY-MM-DD HH:MM:SS", # （可选）源的最后更新时间
                "error_details": "..." # （可选）如果success为False，提供错误详情
            }
        """
        pass

    def close(self):
        """
        关闭采集器实例，释放资源（例如关闭WebDriver）。
        默认实现为空，子类可以覆盖此方法。
        """
        pass 