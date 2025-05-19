# src/core/news_clusterer.py
"""
新闻聚类器模块

负责将不同信源的相似新闻聚类为单一事件项，
支持按分类组织事件。
"""

import logging
import re
from typing import List, Dict, Tuple, Set, Optional
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import DBSCAN
import numpy as np

from src.collectors.categories import STANDARD_CATEGORIES


class NewsClusterer:
    """新闻聚类器，将不同信源的相似新闻聚类为单一事件项"""
    
    def __init__(self):
        """初始化新闻聚类器"""
        self.logger = logging.getLogger('news_analyzer.core.news_clusterer')
        
        # 聚类参数
        self.eps = 0.5  # DBSCAN的邻域半径参数
        self.min_samples = 2  # DBSCAN的最小样本数参数
        self.similarity_threshold = 0.4  # 相似度阈值
        
        # 分类关键词
        self.category_keywords = {
            "politics": ["政治", "政府", "总统", "主席", "国家", "党", "选举", "外交", "政策", "人大", "政协", "法律", "法规", "立法", "司法", "行政"],
            "military": ["军事", "军队", "武器", "导弹", "战争", "战斗", "军演", "国防", "航母", "坦克", "战机", "士兵", "将军", "作战", "军备", "军工"],
            "international": ["国际", "全球", "世界", "外国", "海外", "联合国", "欧盟", "美国", "俄罗斯", "中国", "日本", "韩国", "印度", "英国", "法国", "德国", "外交", "国际关系"],
            "technology": ["科技", "技术", "互联网", "软件", "硬件", "AI", "人工智能", "5G", "数字", "创新", "编程", "算法", "大数据", "云计术", "区块链", "芯片", "半导体"],
            "business": ["商业", "经济", "金融", "股市", "投资", "企业", "公司", "市场", "贸易", "产业", "创业", "融资", "上市", "IPO", "并购", "利润", "营收", "GDP", "通胀", "通货膨胀"],
            "science": ["科学", "研究", "发现", "实验", "宇宙", "物理", "化学", "生物", "医学", "天文", "地理", "环境", "气候", "基因", "DNA", "细胞", "分子", "原子"],
            "sports": ["体育", "足球", "篮球", "比赛", "奥运", "冠军", "运动员", "联赛", "赛事", "网球", "排球", "乒乓球", "羽毛球", "游泳", "田径", "马拉松", "世界杯", "欧冠", "NBA", "CBA"],
            "entertainment": ["娱乐", "明星", "电影", "音乐", "演出", "综艺", "电视", "艺人", "演员", "导演", "歌手", "演唱会", "电视剧", "综艺节目", "选秀", "颁奖", "奖项", "票房"],
            "health": ["健康", "医疗", "疾病", "药物", "治疗", "医院", "医生", "患者", "保健", "养生", "疫苗", "病毒", "细菌", "感染", "预防", "康复", "营养", "饮食", "锻炼"],
            "culture": ["文化", "艺术", "历史", "传统", "教育", "学校", "学生", "老师", "课程", "学习", "文学", "诗歌", "小说", "绘画", "雕塑", "音乐", "舞蹈", "戏剧", "博物馆", "展览"]
        }
    
    def cluster(self, news_list: List[Dict]) -> List[Dict]:
        """将新闻列表聚类为事件组
        
        Args:
            news_list: 新闻列表，每个新闻为一个字典
            
        Returns:
            事件组列表，每个事件组为一个字典
        """
        if not news_list:
            self.logger.warning("输入的新闻列表为空，无法进行聚类")
            return []
        
        self.logger.info(f"开始对 {len(news_list)} 条新闻进行聚类")
        
        # 提取文本特征
        texts = [f"{n.get('title', '')} {n.get('content', '')}" for n in news_list]
        
        # 使用TF-IDF向量化文本
        try:
            vectorizer = TfidfVectorizer(max_features=5000, stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(texts)
            
            # 使用DBSCAN进行聚类
            clustering = DBSCAN(eps=self.eps, min_samples=self.min_samples, metric='cosine').fit(tfidf_matrix)
            
            # 整理聚类结果
            events = {}
            for i, label in enumerate(clustering.labels_):
                if label == -1:  # 噪声点（未分配到任何簇）
                    continue
                    
                if label not in events:
                    # 创建新的事件组
                    first_news = news_list[i]
                    events[label] = {
                        "event_id": f"event_{label}",
                        "title": first_news.get('title', '无标题'),
                        "summary": self._generate_summary(first_news),
                        "keywords": self._extract_keywords(first_news),
                        "category": self._categorize_news(first_news),
                        "reports": [],
                        "sources": set(),
                        "publish_time": first_news.get('publish_time', datetime.now())
                    }
                
                # 添加新闻到事件组
                news = news_list[i]
                source = news.get('source_name', '未知来源')
                
                # 如果该来源已存在，检查是否为更新的报道
                if source in events[label]["sources"]:
                    # 检查是否有更新的时间戳
                    existing_reports = [r for r in events[label]["reports"] if r.get('source_name') == source]
                    if existing_reports:
                        existing_time = existing_reports[0].get('publish_time')
                        current_time = news.get('publish_time')
                        
                        # 如果当前新闻更新，替换旧的
                        if current_time and existing_time and current_time > existing_time:
                            events[label]["reports"] = [r for r in events[label]["reports"] if r.get('source_name') != source]
                            events[label]["reports"].append(news)
                    else:
                        events[label]["reports"].append(news)
                else:
                    events[label]["reports"].append(news)
                    events[label]["sources"].add(source)
                    
                    # 更新事件的发布时间为最早的报道时间
                    news_time = news.get('publish_time')
                    if news_time and isinstance(news_time, datetime):
                        if news_time < events[label]["publish_time"]:
                            events[label]["publish_time"] = news_time
            
            # 将sources从集合转换为列表，以便JSON序列化
            for event in events.values():
                event["sources"] = list(event["sources"])
            
            # 按报道数量排序
            sorted_events = sorted(events.values(), key=lambda x: len(x["reports"]), reverse=True)
            
            self.logger.info(f"聚类完成，共生成 {len(sorted_events)} 个事件组")
            return sorted_events
            
        except Exception as e:
            self.logger.error(f"聚类过程中出错: {e}", exc_info=True)
            return []
    
    def _generate_summary(self, news: Dict) -> str:
        """为新闻生成摘要
        
        Args:
            news: 新闻字典
            
        Returns:
            摘要文本
        """
        # 简单实现：使用新闻内容的前200个字符作为摘要
        content = news.get('content', '')
        if not content:
            return news.get('title', '无摘要')
            
        # 提取前200个字符，确保不截断句子
        if len(content) <= 200:
            return content
            
        # 尝试在200个字符附近找到句号或问号
        for i in range(200, min(300, len(content))):
            if content[i] in ['。', '？', '！', '.', '?', '!']:
                return content[:i+1]
                
        return content[:200] + '...'
    
    def _extract_keywords(self, news: Dict) -> List[str]:
        """从新闻中提取关键词
        
        Args:
            news: 新闻字典
            
        Returns:
            关键词列表
        """
        # 简单实现：提取标题中的名词和动词作为关键词
        title = news.get('title', '')
        if not title:
            return []
            
        # 移除标点符号
        title = re.sub(r'[^\w\s]', '', title)
        
        # 分词并过滤停用词
        words = title.split()
        stop_words = {'的', '了', '在', '是', '和', '与', '或', '有', '被', '将', '把', '从', '到', '对', '为'}
        keywords = [w for w in words if w not in stop_words and len(w) > 1]
        
        # 限制关键词数量
        return keywords[:5]
    
    def _categorize_news(self, news: Dict) -> str:
        """对新闻进行分类
        
        Args:
            news: 新闻字典
            
        Returns:
            分类ID
        """
        title = news.get('title', '') or ''
        content = news.get('content', '') or ''
        text = (title + " " + content).lower()
        
        # 匹配关键词
        matched_categories = []
        for category_id, keywords in self.category_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text:
                    matched_categories.append((category_id, keyword))
                    break
        
        # 如果有匹配的类别
        if matched_categories:
            # 优先考虑标题中出现的关键词
            title_matches = []
            for cat_id, keyword in matched_categories:
                if keyword.lower() in title.lower():
                    title_matches.append(cat_id)
            
            if title_matches:
                # 使用标题中的第一个匹配类别
                return title_matches[0]
            else:
                # 使用内容中的第一个匹配类别
                return matched_categories[0][0]
        
        # 如果没有匹配到任何类别，返回未分类
        return "uncategorized"
    
    def get_category_name(self, category_id: str) -> str:
        """获取分类名称
        
        Args:
            category_id: 分类ID
            
        Returns:
            分类名称
        """
        if category_id == "uncategorized":
            return "未分类"
        elif category_id == "military" and category_id not in STANDARD_CATEGORIES:
            return "军事新闻"
        else:
            return STANDARD_CATEGORIES.get(category_id, {}).get("name", "未分类")
    
    def set_clustering_params(self, eps: Optional[float] = None, min_samples: Optional[int] = None, 
                             similarity_threshold: Optional[float] = None) -> None:
        """设置聚类参数
        
        Args:
            eps: DBSCAN的邻域半径参数
            min_samples: DBSCAN的最小样本数参数
            similarity_threshold: 相似度阈值
        """
        if eps is not None:
            self.eps = eps
        if min_samples is not None:
            self.min_samples = min_samples
        if similarity_threshold is not None:
            self.similarity_threshold = similarity_threshold
        
        self.logger.info(f"聚类参数已更新: eps={self.eps}, min_samples={self.min_samples}, "
                       f"similarity_threshold={self.similarity_threshold}")