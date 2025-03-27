"""
新闻数据存储

负责保存和加载新闻数据。
"""

import os
import json
import logging
import shutil
from datetime import datetime


class NewsStorage:
    """新闻数据存储类"""
    
    def __init__(self, data_dir="data"):
        """初始化存储器
        
        Args:
            data_dir: 数据存储目录
        """
        self.logger = logging.getLogger('news_analyzer.storage')
        
        # 优先使用绝对路径，兼容运行位置
        self.app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(self.app_root, data_dir)
        
        # 如果上述路径不存在，尝试使用绝对路径
        if not os.path.exists(self.data_dir):
            self.data_dir = os.path.abspath(data_dir)
            
        # 如果仍然不存在，尝试使用 C:\Users\Administrator\Desktop\news_analyzer\data
        if not os.path.exists(self.data_dir):
            self.data_dir = r"C:\Users\Administrator\Desktop\news_analyzer\data"
        
        # 确保目录存在
        self._ensure_dir(self.data_dir)
        self._ensure_dir(os.path.join(self.data_dir, "news"))
        self._ensure_dir(os.path.join(self.data_dir, "analysis"))
        
        self.logger.info(f"数据存储目录: {self.data_dir}")
    
    def _ensure_dir(self, directory):
        """确保目录存在
        
        Args:
            directory: 目录路径
        """
        if not os.path.exists(directory):
            os.makedirs(directory)
            self.logger.info(f"创建目录: {directory}")
    
    def save_news(self, news_items, filename=None):
        """保存新闻数据
        
        Args:
            news_items: 新闻条目列表
            filename: 文件名（可选，默认使用时间戳）
            
        Returns:
            str: 保存的文件路径
        """
        if not news_items:
            self.logger.warning("没有新闻数据可保存")
            return None
        
        # 如果没有指定文件名，使用时间戳
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"news_{timestamp}.json"
        
        filepath = os.path.join(self.data_dir, "news", filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(news_items, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"保存了 {len(news_items)} 条新闻到 {filepath}")
            return filepath
        
        except Exception as e:
            self.logger.error(f"保存新闻数据失败: {str(e)}")
            return None
    
    def load_news(self, filename=None):
        """加载新闻数据
        
        Args:
            filename: 文件名（可选，默认加载最新的文件）
            
        Returns:
            list: 新闻条目列表
        """
        # 如果没有指定文件名，加载最新的文件
        if not filename:
            files = self.list_news_files()
            if not files:
                self.logger.warning("没有找到新闻数据文件")
                return []
            
            filename = files[-1]  # 最新的文件
        
        filepath = os.path.join(self.data_dir, "news", filename)
        
        try:
            if not os.path.exists(filepath):
                self.logger.warning(f"文件不存在: {filepath}")
                return []
            
            with open(filepath, 'r', encoding='utf-8') as f:
                news_items = json.load(f)
            
            self.logger.info(f"从 {filepath} 加载了 {len(news_items)} 条新闻")
            return news_items
        
        except Exception as e:
            self.logger.error(f"加载新闻数据失败: {str(e)}")
            return []
    
    def list_news_files(self):
        """列出所有新闻文件
        
        Returns:
            list: 文件名列表，按日期排序
        """
        news_dir = os.path.join(self.data_dir, "news")
        if not os.path.exists(news_dir):
            self.logger.warning(f"新闻目录不存在: {news_dir}")
            return []
        
        try:
            files = [f for f in os.listdir(news_dir) if f.endswith('.json')]
            return sorted(files)
        except Exception as e:
            self.logger.error(f"列出新闻文件失败: {str(e)}")
            return []