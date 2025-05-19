# src/ui/modules/analysis_panel_data_manager.py
"""
分析面板数据管理器

负责新闻分析整合面板的数据管理，
包括新闻数据的加载、分类、分组和分析结果管理。
"""

import logging
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime

from src.models import NewsArticle
from src.storage.news_storage import NewsStorage
from src.llm.llm_service import LLMService
from src.core.enhanced_news_clusterer import EnhancedNewsClusterer


class AnalysisPanelDataManager:
    """
    分析面板数据管理器，负责数据的加载、分类、分组和分析结果管理
    """
    
    def __init__(self):
        """
        初始化数据管理器
        """
        self.logger = logging.getLogger('news_analyzer.ui.modules.analysis_panel_data_manager')
        
        # 数据容器
        self.all_news_items: List[Dict] = []  # 所有新闻项
        self.selected_news_items: List[Dict] = []  # 选中的新闻项
        self.news_groups: List[List[Dict]] = []  # 分组后的新闻
        self.categorized_news: Dict[str, List[Dict]] = {}  # 按类别分类的新闻
        self.current_category = ""  # 当前选中的类别
        self.current_group_items = []  # 当前组内的新闻项
        self.analysis_results: Dict[str, Dict] = {}  # 存储分析结果，键为新闻组ID
        
        # 提示词管理相关
        self.current_template_name = ""  # 当前选择的提示词模板名称
        self.current_template_content = ""  # 当前选择的提示词模板内容
    
    def load_news_data(self, storage: NewsStorage) -> List[Dict]:
        """
        从存储服务加载新闻数据
        
        Args:
            storage: 新闻存储服务
            
        Returns:
            加载的新闻数据列表
        """
        try:
            # 清空现有数据
            self.all_news_items = []
            self.selected_news_items = []
            self.news_groups = []
            self.categorized_news = {}
            self.current_category = ""
            self.current_group_items = []
            
            # 从存储服务加载数据
            news_articles = storage.get_all_news()
            
            # 转换为字典格式
            for article in news_articles:
                if isinstance(article, NewsArticle):
                    news_dict = article.to_dict()
                    self.all_news_items.append(news_dict)
                else:
                    self.all_news_items.append(article)
            
            # 按类别分类新闻
            self._categorize_news()
            
            # 设置当前类别为全部
            self.current_category = "all"
            self.current_group_items = self.all_news_items
            
            return self.all_news_items
            
        except Exception as e:
            self.logger.error(f"加载新闻数据时出错: {e}", exc_info=True)
            raise
    
    def _categorize_news(self):
        """
        将新闻按类别分类
        """
        # 初始化分类字典
        self.categorized_news = {
            "politics": [],  # 政治新闻
            "economy": [],  # 经济新闻
            "technology": [],  # 科技新闻
            "sports": [],  # 体育新闻
            "entertainment": [],  # 娱乐新闻
            "military": [],  # 军事新闻
            "society": [],  # 社会新闻
            "international": [],  # 国际新闻
            "health": [],  # 健康医疗
            "education": [],  # 教育新闻
            "environment": [],  # 环境新闻
            "culture": [],  # 文化新闻
            "uncategorized": []  # 未分类
        }
        
        # 遍历所有新闻，按类别分组
        for news in self.all_news_items:
            category = news.get('category', '')
            if not category:
                self.categorized_news["uncategorized"].append(news)
                continue
                
            # 尝试将类别ID转换为小写并去除空格
            category_id = category.lower().strip() if isinstance(category, str) else ''
            
            # 检查类别ID是否在预定义类别中
            if category_id in self.categorized_news:
                self.categorized_news[category_id].append(news)
            else:
                # 尝试从类别名称中提取类别ID
                category_name = news.get('category_name', '')
                if category_name:
                    category_name_lower = category_name.lower()
                    
                    # 根据类别名称匹配预定义类别
                    if '政治' in category_name or 'politic' in category_name_lower:
                        self.categorized_news["politics"].append(news)
                    elif '经济' in category_name or 'econom' in category_name_lower:
                        self.categorized_news["economy"].append(news)
                    elif '科技' in category_name or 'tech' in category_name_lower:
                        self.categorized_news["technology"].append(news)
                    elif '体育' in category_name or 'sport' in category_name_lower:
                        self.categorized_news["sports"].append(news)
                    elif '娱乐' in category_name or 'entertain' in category_name_lower:
                        self.categorized_news["entertainment"].append(news)
                    elif '军事' in category_name or 'military' in category_name_lower:
                        self.categorized_news["military"].append(news)
                    elif '社会' in category_name or 'society' in category_name_lower:
                        self.categorized_news["society"].append(news)
                    elif '国际' in category_name or 'international' in category_name_lower:
                        self.categorized_news["international"].append(news)
                    elif '健康' in category_name or '医疗' in category_name or 'health' in category_name_lower:
                        self.categorized_news["health"].append(news)
                    elif '教育' in category_name or 'education' in category_name_lower:
                        self.categorized_news["education"].append(news)
                    elif '环境' in category_name or 'environment' in category_name_lower:
                        self.categorized_news["environment"].append(news)
                    elif '文化' in category_name or 'culture' in category_name_lower:
                        self.categorized_news["culture"].append(news)
                    else:
                        self.categorized_news["uncategorized"].append(news)
                else:
                    self.categorized_news["uncategorized"].append(news)
    
    def get_news_by_category(self, category_id: str) -> List[Dict]:
        """
        获取指定类别的新闻
        
        Args:
            category_id: 类别ID
            
        Returns:
            该类别下的新闻列表
        """
        if category_id == "all":
            return self.all_news_items
        
        return self.categorized_news.get(category_id, [])
    
    def set_selected_news(self, indices: List[int]):
        """
        设置选中的新闻
        
        Args:
            indices: 选中的新闻索引列表
        """
        self.selected_news_items = []
        
        for index in indices:
            if 0 <= index < len(self.current_group_items):
                self.selected_news_items.append(self.current_group_items[index])
    
    def auto_group_news(self, method: str = "title_similarity") -> List[List[Dict]]:
        """
        自动分组新闻
        
        Args:
            method: 分组方法，'title_similarity'或'multi_feature'
            
        Returns:
            分组后的新闻列表
        """
        if not self.current_group_items:
            return []
        
        try:
            # 创建新闻聚类器
            clusterer = EnhancedNewsClusterer()
            
            # 根据方法选择分组算法
            if method == "multi_feature":
                self.news_groups = clusterer.cluster_by_multi_features(self.current_group_items)
            else:  # 默认使用标题相似度
                self.news_groups = clusterer.cluster_by_title_similarity(self.current_group_items)
            
            return self.news_groups
            
        except Exception as e:
            self.logger.error(f"自动分组新闻时出错: {e}", exc_info=True)
            raise
    
    def analyze_news(self, llm_service: LLMService, analysis_type: str) -> Dict:
        """
        分析选中的新闻
        
        Args:
            llm_service: LLM服务
            analysis_type: 分析类型
            
        Returns:
            分析结果
        """
        if not self.selected_news_items:
            return {"error": "未选择任何新闻"}
        
        try:
            # 根据分析类型选择提示词模板
            template_name = self._get_template_by_analysis_type(analysis_type)
            
            # 如果已经选择了自定义模板，则使用自定义模板
            if self.current_template_name and self.current_template_content:
                template_content = self.current_template_content
            else:
                # 否则使用默认模板
                template_content = llm_service.prompt_manager.get_template_content(template_name)
            
            # 准备新闻数据
            news_data = []
            for news in self.selected_news_items:
                news_data.append({
                    "title": news.get('title', '无标题'),
                    "source": news.get('source_name', '未知来源'),
                    "pub_date": news.get('publish_time', ''),
                    "content": news.get('content', '无内容'),
                    "url": news.get('url', '')
                })
            
            # 调用LLM服务进行分析
            result = llm_service.analyze_news_with_template(
                news_data, template_content, analysis_type
            )
            
            # 存储分析结果
            group_id = f"group_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self.analysis_results)}"
            self.analysis_results[group_id] = {
                "news_items": self.selected_news_items,
                "analysis_type": analysis_type,
                "result": result
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"分析新闻时出错: {e}", exc_info=True)
            raise
    
    def _get_template_by_analysis_type(self, analysis_type: str) -> str:
        """
        根据分析类型获取对应的提示词模板名称
        
        Args:
            analysis_type: 分析类型
            
        Returns:
            模板名称
        """
        template_map = {
            "新闻相似度分析": "news_similarity",
            "增强型多特征分析": "news_similarity_enhanced",
            "重要程度和立场分析": "importance_stance",
            "深度分析": "deep_analysis",
            "关键观点": "key_points",
            "事实核查": "fact_check",
            "摘要": "summary"
        }
        
        return template_map.get(analysis_type, "news_analysis")
    
    def set_template(self, template_name: str, template_content: str):
        """
        设置当前使用的提示词模板
        
        Args:
            template_name: 模板名称
            template_content: 模板内容
        """
        self.current_template_name = template_name
        self.current_template_content = template_content