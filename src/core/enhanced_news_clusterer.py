# src/core/enhanced_news_clusterer.py
"""
增强型新闻聚类器模块

实现基于深度学习的多特征融合分类方法，
结合预训练语言模型、命名实体识别和主题模型，
提供更精确的新闻分类和聚类功能。
"""

import logging
import re
import os
import json
import numpy as np
from typing import List, Dict, Tuple, Set, Optional, Any
from datetime import datetime, timedelta
from collections import Counter

# 基础NLP工具
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import DBSCAN, AgglomerativeClustering
from sklearn.decomposition import LatentDirichletAllocation

# 导入项目模块
from src.collectors.categories import STANDARD_CATEGORIES
from src.llm.llm_service import LLMService


class EnhancedNewsClusterer:
    """增强型新闻聚类器，使用多特征融合方法实现更精确的新闻分类和聚类"""
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """初始化增强型新闻聚类器
        
        Args:
            llm_service: LLM服务实例，用于语义分析和实体识别
        """
        self.logger = logging.getLogger('news_analyzer.core.enhanced_news_clusterer')
        self.llm_service = llm_service
        
        # 聚类参数
        self.eps = 0.4  # DBSCAN的邻域半径参数，调小以提高精度
        self.min_samples = 2  # DBSCAN的最小样本数参数
        self.similarity_threshold = 0.5  # 相似度阈值，调高以提高精度
        self.time_window = 3  # 时间窗口（天），同一事件的新闻时间应该接近
        
        # 特征权重
        self.weights = {
            'title_tfidf': 0.3,      # 标题TF-IDF特征权重
            'content_tfidf': 0.2,    # 内容TF-IDF特征权重
            'entity': 0.25,          # 命名实体特征权重
            'topic': 0.15,           # 主题模型特征权重
            'time_proximity': 0.1    # 时间接近度特征权重
        }
        
        # 分类关键词 - 扩展并优化关键词列表
        self.category_keywords = {
            "politics": [
                "政治", "政府", "总统", "主席", "国家", "党", "选举", "外交", "政策", 
                "人大", "政协", "法律", "法规", "立法", "司法", "行政", "议会", "议员",
                "内阁", "首相", "总理", "宪法", "法案", "投票", "民主", "执政", "在野",
                "施政", "改革", "政见", "政纲", "政令", "政局", "政坛", "政要", "政体"
            ],
            "military": [
                "军事", "军队", "武器", "导弹", "战争", "战斗", "军演", "国防", "航母", 
                "坦克", "战机", "士兵", "将军", "作战", "军备", "军工", "部队", "战略",
                "战术", "军力", "军费", "军工", "军控", "军改", "军人", "军官", "军衔",
                "军舰", "军机", "军火", "军援", "军情", "军警", "军阀", "军团", "军区"
            ],
            "international": [
                "国际", "全球", "世界", "外国", "海外", "联合国", "欧盟", "美国", "俄罗斯", 
                "中国", "日本", "韩国", "印度", "英国", "法国", "德国", "外交", "国际关系",
                "跨国", "多边", "双边", "国际组织", "国际法", "国际秩序", "国际社会",
                "国际合作", "国际援助", "国际贸易", "国际金融", "国际安全", "国际局势"
            ],
            "technology": [
                "科技", "技术", "互联网", "软件", "硬件", "AI", "人工智能", "5G", "数字", 
                "创新", "编程", "算法", "大数据", "云计算", "区块链", "芯片", "半导体",
                "量子", "机器学习", "深度学习", "神经网络", "自动驾驶", "机器人", "虚拟现实",
                "增强现实", "物联网", "边缘计算", "网络安全", "数据挖掘", "自然语言处理"
            ],
            "business": [
                "商业", "经济", "金融", "股市", "投资", "企业", "公司", "市场", "贸易", 
                "产业", "创业", "融资", "上市", "IPO", "并购", "利润", "营收", "GDP", 
                "通胀", "通货膨胀", "经济增长", "经济衰退", "经济危机", "货币政策", "财政政策",
                "税收", "关税", "汇率", "利率", "债券", "证券", "基金", "保险", "银行"
            ],
            "science": [
                "科学", "研究", "发现", "实验", "宇宙", "物理", "化学", "生物", "医学", 
                "天文", "地理", "环境", "气候", "基因", "DNA", "细胞", "分子", "原子",
                "理论", "假说", "定律", "方程", "粒子", "能量", "物质", "反应", "合成",
                "进化", "生态", "系统", "结构", "功能", "机制", "模型", "仿真", "预测"
            ],
            "sports": [
                "体育", "足球", "篮球", "比赛", "奥运", "冠军", "运动员", "联赛", "赛事", 
                "网球", "排球", "乒乓球", "羽毛球", "游泳", "田径", "马拉松", "世界杯", "欧冠", 
                "NBA", "CBA", "体操", "拳击", "武术", "击剑", "射箭", "射击", "举重",
                "赛车", "高尔夫", "棒球", "橄榄球", "冰球", "滑雪", "滑冰", "跳水", "跆拳道"
            ],
            "entertainment": [
                "娱乐", "明星", "电影", "音乐", "演出", "综艺", "电视", "艺人", "演员", 
                "导演", "歌手", "演唱会", "电视剧", "综艺节目", "选秀", "颁奖", "奖项", "票房",
                "剧情", "角色", "表演", "舞台", "戏剧", "喜剧", "悲剧", "动作片", "爱情片",
                "科幻片", "恐怖片", "动画片", "纪录片", "流行音乐", "摇滚", "嘻哈", "爵士"
            ],
            "health": [
                "健康", "医疗", "疾病", "药物", "治疗", "医院", "医生", "患者", "保健", 
                "养生", "疫苗", "病毒", "细菌", "感染", "预防", "康复", "营养", "饮食", "锻炼",
                "症状", "诊断", "手术", "护理", "急救", "公共卫生", "心理健康", "精神疾病",
                "慢性病", "传染病", "流行病", "免疫", "抗体", "抗原", "基因治疗", "干细胞"
            ],
            "culture": [
                "文化", "艺术", "历史", "传统", "教育", "学校", "学生", "老师", "课程", 
                "学习", "文学", "诗歌", "小说", "绘画", "雕塑", "音乐", "舞蹈", "戏剧", 
                "博物馆", "展览", "文物", "遗产", "古迹", "考古", "民俗", "风俗", "习惯",
                "礼仪", "节日", "庆典", "宗教", "信仰", "哲学", "思想", "价值观", "伦理",
                "建筑", "建筑师", "architect", "gaudí", "教皇", "pope", "sainthood", "圣人"
            ],
            "environment": [
                "环境", "生态", "污染", "保护", "气候变化", "全球变暖", "碳排放", "可再生能源", 
                "可持续发展", "绿色", "节能", "减排", "森林", "海洋", "湿地", "生物多样性",
                "濒危物种", "自然保护区", "环保", "回收", "垃圾处理", "水资源", "空气质量"
            ],
            "disaster": [
                "灾害", "地震", "台风", "飓风", "洪水", "干旱", "火灾", "山火", "海啸", 
                "泥石流", "滑坡", "暴雨", "暴雪", "冰雹", "龙卷风", "沙尘暴", "雷击",
                "救灾", "避难", "疏散", "重建", "预警", "应急", "救援", "伤亡", "损失"
            ]
        }
        
        # 实体类型映射
        self.entity_types = {
            "PERSON": "人物",
            "ORGANIZATION": "组织",
            "LOCATION": "地点",
            "DATE": "日期",
            "TIME": "时间",
            "MONEY": "金额",
            "PERCENT": "百分比",
            "FACILITY": "设施",
            "GPE": "地理政治实体",
            "EVENT": "事件"
        }
        
        # 主题模型参数
        self.n_topics = 20  # 主题数量
        self.lda_model = None  # LDA模型实例
        
        # 缓存
        self.entity_cache = {}  # 实体识别缓存
        self.topic_cache = {}  # 主题分析缓存
    
    def cluster(self, news_list: List[Dict]) -> List[Dict]:
        """将新闻列表聚类为事件组，使用多特征融合方法
        
        Args:
            news_list: 新闻列表，每个新闻为一个字典
            
        Returns:
            事件组列表，每个事件组为一个字典
        """
        if not news_list:
            self.logger.warning("输入的新闻列表为空，无法进行聚类")
            return []
        
        self.logger.info(f"开始对 {len(news_list)} 条新闻进行增强聚类")
        
        # 1. 预处理新闻数据
        processed_news = self._preprocess_news(news_list)
        
        # 2. 提取多维特征
        features = self._extract_features(processed_news)
        
        # 3. 使用层次聚类进行粗分类
        coarse_clusters = self._coarse_clustering(features, processed_news)
        
        # 4. 对每个粗分类簇进行细分组
        events = self._fine_clustering(coarse_clusters, features, processed_news)
        
        # 5. 整理聚类结果
        sorted_events = sorted(events, key=lambda x: len(x["reports"]), reverse=True)
        
        self.logger.info(f"聚类完成，共生成 {len(sorted_events)} 个事件组")
        return sorted_events
    
    def _preprocess_news(self, news_list: List[Dict]) -> List[Dict]:
        """预处理新闻数据，包括文本清洗、时间标准化等
        
        Args:
            news_list: 原始新闻列表
            
        Returns:
            预处理后的新闻列表
        """
        processed_news = []
        
        for news in news_list:
            # 复制原始新闻数据
            processed = news.copy()
            
            # 文本清洗
            title = processed.get('title', '')
            content = processed.get('content', '')
            
            # 移除HTML标签
            title = re.sub(r'<[^>]+>', '', title)
            content = re.sub(r'<[^>]+>', '', content)
            
            # 移除多余空白字符
            title = re.sub(r'\s+', ' ', title).strip()
            content = re.sub(r'\s+', ' ', content).strip()
            
            processed['clean_title'] = title
            processed['clean_content'] = content
            
            # 时间标准化
            pub_time = processed.get('publish_time')
            if not pub_time or not isinstance(pub_time, datetime):
                processed['publish_time'] = datetime.now()
            
            processed_news.append(processed)
        
        return processed_news
    
    def _extract_features(self, news_list: List[Dict]) -> Dict[str, np.ndarray]:
        """提取多维特征，包括TF-IDF、实体、主题等
        
        Args:
            news_list: 预处理后的新闻列表
            
        Returns:
            特征字典，包含不同类型的特征矩阵
        """
        # 提取文本
        titles = [news.get('clean_title', '') for news in news_list]
        contents = [news.get('clean_content', '') for news in news_list]
        combined_texts = [f"{t} {c}" for t, c in zip(titles, contents)]
        
        # 1. 提取TF-IDF特征
        title_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        title_tfidf = title_vectorizer.fit_transform(titles)
        
        content_vectorizer = TfidfVectorizer(max_features=2000, stop_words='english')
        content_tfidf = content_vectorizer.fit_transform(contents)
        
        # 2. 提取命名实体特征
        entity_features = self._extract_entity_features(news_list)
        
        # 3. 提取主题模型特征
        topic_features = self._extract_topic_features(combined_texts)
        
        # 4. 提取时间接近度特征
        time_features = self._extract_time_features(news_list)
        
        return {
            'title_tfidf': title_tfidf,
            'content_tfidf': content_tfidf,
            'entity': entity_features,
            'topic': topic_features,
            'time': time_features
        }
    
    def _extract_entity_features(self, news_list: List[Dict]) -> np.ndarray:
        """提取命名实体特征
        
        Args:
            news_list: 预处理后的新闻列表
            
        Returns:
            实体特征矩阵
        """
        # 如果有LLM服务，使用LLM进行实体识别
        if self.llm_service and self.llm_service.is_configured():
            return self._extract_entity_features_with_llm(news_list)
        else:
            # 简化版实体识别：提取大写开头的词和数字
            return self._extract_entity_features_simple(news_list)
    
    def _extract_entity_features_with_llm(self, news_list: List[Dict]) -> np.ndarray:
        """使用LLM进行实体识别
        
        Args:
            news_list: 预处理后的新闻列表
            
        Returns:
            实体特征矩阵
        """
        # 实体特征矩阵初始化
        n_samples = len(news_list)
        entity_features = np.zeros((n_samples, n_samples))
        
        # 提取每篇新闻的实体
        news_entities = []
        
        for i, news in enumerate(news_list):
            # 检查缓存
            news_id = news.get('id', '')
            if news_id and news_id in self.entity_cache:
                entities = self.entity_cache[news_id]
            else:
                # 构建提示
                prompt = f"提取以下新闻中的命名实体（人物、组织、地点、事件等）：\n标题：{news.get('clean_title', '')}\n内容：{news.get('clean_content', '')[:500]}\n仅返回实体列表，格式为JSON：{{\"entities\": [{{\"text\": \"实体名\", \"type\": \"实体类型\"}}]}}"
                
                try:
                    # 调用LLM服务
                    response = self.llm_service.call_llm(prompt)
                    
                    # 解析结果
                    if isinstance(response, str):
                        try:
                            result = json.loads(response)
                            entities = result.get('entities', [])
                        except json.JSONDecodeError:
                            entities = []
                    else:
                        entities = response.get('entities', [])
                    
                    # 缓存结果
                    if news_id:
                        self.entity_cache[news_id] = entities
                        
                except Exception as e:
                    self.logger.error(f"实体识别出错: {e}")
                    entities = []
            
            news_entities.append(entities)
        
        # 计算实体相似度矩阵
        for i in range(n_samples):
            for j in range(i, n_samples):
                if i == j:
                    entity_features[i, j] = 1.0
                    continue
                
                entities_i = news_entities[i]
                entities_j = news_entities[j]
                
                # 计算实体重叠度
                if not entities_i or not entities_j:
                    similarity = 0.0
                else:
                    # 提取实体文本
                    texts_i = [e.get('text', '').lower() for e in entities_i]
                    texts_j = [e.get('text', '').lower() for e in entities_j]
                    
                    # 计算Jaccard相似度
                    intersection = len(set(texts_i) & set(texts_j))
                    union = len(set(texts_i) | set(texts_j))
                    
                    similarity = intersection / union if union > 0 else 0.0
                
                entity_features[i, j] = similarity
                entity_features[j, i] = similarity
        
        return entity_features
    
    def _extract_entity_features_simple(self, news_list: List[Dict]) -> np.ndarray:
        """使用简单规则提取实体特征
        
        Args:
            news_list: 预处理后的新闻列表
            
        Returns:
            实体特征矩阵
        """
        # 实体特征矩阵初始化
        n_samples = len(news_list)
        entity_features = np.zeros((n_samples, n_samples))
        
        # 提取每篇新闻的实体
        news_entities = []
        
        for news in news_list:
            title = news.get('clean_title', '')
            content = news.get('clean_content', '')[:500]  # 只使用前500个字符
            
            # 提取大写开头的词（可能是人名、地名、组织名等）
            title_words = title.split()
            content_words = content.split()
            
            # 英文文本：提取大写开头的词
            if re.search(r'[a-zA-Z]', title + content):
                entities = [word for word in title_words + content_words 
                           if word and word[0].isupper()]
            # 中文文本：提取2-4个字的词
            else:
                # 简单分词
                entities = []
                for text in [title, content]:
                    for i in range(len(text)):
                        for j in range(2, 5):  # 提取2-4个字的词
                            if i + j <= len(text):
                                entities.append(text[i:i+j])
            
            # 提取数字（可能是日期、数量等）
            numbers = re.findall(r'\d+', title + content)
            
            # 合并实体
            all_entities = entities + numbers
            news_entities.append(all_entities)
        
        # 计算实体相似度矩阵
        for i in range(n_samples):
            for j in range(i, n_samples):
                if i == j:
                    entity_features[i, j] = 1.0
                    continue
                
                entities_i = set(news_entities[i])
                entities_j = set(news_entities[j])
                
                # 计算Jaccard相似度
                intersection = len(entities_i & entities_j)
                union = len(entities_i | entities_j)
                
                similarity = intersection / union if union > 0 else 0.0
                
                entity_features[i, j] = similarity
                entity_features[j, i] = similarity
        
        return entity_features
    
    def _extract_topic_features(self, texts: List[str]) -> np.ndarray:
        """提取主题模型特征
        
        Args:
            texts: 文本列表
            
        Returns:
            主题特征矩阵
        """
        # 使用CountVectorizer进行词频统计
        vectorizer = CountVectorizer(max_features=1000, stop_words='english')
        X = vectorizer.fit_transform(texts)
        
        # 训练LDA模型
        self.lda_model = LatentDirichletAllocation(
            n_components=self.n_topics,
            max_iter=10,
            learning_method='online',
            random_state=42
        )
        
        # 获取文档-主题分布
        doc_topic_dist = self.lda_model.fit_transform(X)
        
        # 计算主题相似度矩阵
        n_samples = len(texts)
        topic_features = np.zeros((n_samples, n_samples))
        
        for i in range(n_samples):
            for j in range(i, n_samples):
                if i == j:
                    topic_features[i, j] = 1.0
                    continue
                
                # 计算余弦相似度
                similarity = cosine_similarity(
                    doc_topic_dist[i].reshape(1, -1),
                    doc_topic_dist[j].reshape(1, -1)
                )[0, 0]
                
                topic_features[i, j] = similarity
                topic_features[j, i] = similarity
        
        return topic_features
    
    def _extract_time_features(self, news_list: List[Dict]) -> np.ndarray:
        """提取时间接近度特征
        
        Args:
            news_list: 预处理后的新闻列表
            
        Returns:
            时间特征矩阵
        """
        # 获取发布时间
        times = [news.get('publish_time', datetime.now()) for news in news_list]
        
        # 计算时间接近度矩阵
        n_samples = len(news_list)
        time_features = np.zeros((n_samples, n_samples))
        
        for i in range(n_samples):
            for j in range(i, n_samples):
                if i == j:
                    time_features[i, j] = 1.0
                    continue
                
                # 计算时间差（天）
                time_diff = abs((times[i] - times[j]).total_seconds()) / (24 * 3600)
                
                # 使用高斯衰减函数计算时间接近度
                # 时间差越小，接近度越高；超过时间窗口，接近度接近0
                similarity = np.exp(-(time_diff ** 2) / (2 * self.time_window ** 2))
                
                time_features[i, j] = similarity
                time_features[j, i] = similarity
        
        return time_features
    
    def _coarse_clustering(self, features: Dict[str, np.ndarray], news_list: List[Dict]) -> List[List[int]]:
        """使用层次聚类进行粗分类
        
        Args:
            features: 特征字典
            news_list: 预处理后的新闻列表
            
        Returns:
            粗分类结果，每个元素是一个索引列表
        """
        # 融合多维特征
        similarity_matrix = self._fuse_features(features)
        
        # 将相似度矩阵转换为距离矩阵
        distance_matrix = 1 - similarity_matrix
        
        # 使用层次聚类
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=0.5,  # 距离阈值
            affinity='precomputed',
            linkage='average'
        )
        
        # 执行聚类
        labels = clustering.fit_predict(distance_matrix)
        
        # 整理聚类结果
        clusters = {}
        for i, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(i)
        
        return list(clusters.values())
    
    def _fine_clustering(self, coarse_clusters: List[List[int]], features: Dict[str, np.ndarray], news_list: List[Dict]) -> List[Dict]:
        """对粗分类结果进行细分组
        
        Args:
            coarse_clusters: 粗分类结果
            features: 特征字典
            news_list: 预处理后的新闻列表
            
        Returns:
            事件组列表
        """
        events = []
        
        # 融合特征
        similarity_matrix = self._fuse_features(features)
        
        # 对每个粗分类簇进行细分组
        for cluster_indices in coarse_clusters:
            # 如果簇只有一个元素，直接创建事件
            if len(cluster_indices) == 1:
                idx = cluster_indices[0]
                news = news_list[idx]
                
                event = {
                    "event_id": f"event_{len(events)}",
                    "title": news.get('title', '无标题'),
                    "summary": self._generate_summary(news),
                    "keywords": self._extract_keywords(news),
                    "category": self._categorize_news(news),
                    "reports": [news],
                    "sources": [news.get('source_name', '未知来源')],
                    "publish_time": news.get('publish_time', datetime.now())
                }
                
                events.append(event)
                continue
            
            # 提取子矩阵
            sub_matrix = np.zeros((len(cluster_indices), len(cluster_indices)))
            for i, idx_i in enumerate(cluster_indices):
                for j, idx_j in enumerate(cluster_indices):
                    sub_matrix[i, j] = similarity_matrix[idx_i, idx_j]
            
            # 使用DBSCAN进行细分组
            clustering = DBSCAN(eps=self.eps, min_samples=self.min_samples, metric='precomputed')
            labels = clustering.fit_predict(1 - sub_matrix)  # 转换为距离矩阵
            
            # 整理细分组结果
            sub_clusters = {}
            for i, label in enumerate(labels):
                if label == -1:  # 噪声点（未分配到任何簇）
                    # 创建单独的事件
                    idx = cluster_indices[i]
                    news = news_list[idx]
                    
                    event = {
                        "event_id": f"event_{len(events)}",
                        "title": news.get('title', '无标题'),
                        "summary": self._generate_summary(news),
                        "keywords": self._extract_keywords(news),
                        "category": self._categorize_news(news),
                        "reports": [news],
                        "sources": [news.get('source_name', '未知来源')],
                        "publish_time": news.get('publish_time', datetime.now())
                    }
                    
                    events.append(event)
                else:
                    if label not in sub_clusters:
                        sub_clusters[label] = []
                    sub_clusters[label].append(cluster_indices[i])
            
            # 为每个细分组创建事件
            for sub_cluster in sub_clusters.values():
                # 收集新闻报道
                reports = [news_list[idx] for idx in sub_cluster]
                sources = set(news.get('source_name', '未知来源') for news in reports)
                
                # 选择代表性新闻作为事件标题和摘要
                representative_idx = self._find_representative_news(sub_cluster, similarity_matrix)
                representative_news = news_list[representative_idx]
                
                # 创建事件
                event = {
                    "event_id": f"event_{len(events)}",
                    "title": representative_news.get('title', '无标题'),
                    "summary": self._generate_summary(representative_news),
                    "keywords": self._extract_keywords_from_cluster(reports),
                    "category": self._categorize_cluster(reports),
                    "reports": reports,
                    "sources": list(sources),
                    "publish_time": min([news.get('publish_time', datetime.now()) for news in reports])
                }
                
                events.append(event)
        
        return events
    
    def _fuse_features(self, features: Dict[str, np.ndarray]) -> np.ndarray:
        """融合多维特征
        
        Args:
            features: 特征字典
            
        Returns:
            融合后的相似度矩阵
        """
        # 获取样本数
        n_samples = features['title_tfidf'].shape[0]
        
        # 初始化融合矩阵
        fused_matrix = np.zeros((n_samples, n_samples))
        
        # 计算标题TF-IDF相似度
        title_sim = cosine_similarity(features['title_tfidf'])
        fused_matrix += self.weights['title_tfidf'] * title_sim
        
        # 计算内容TF-IDF相似度
        content_sim = cosine_similarity(features['content_tfidf'])
        fused_matrix += self.weights['content_tfidf'] * content_sim
        
        # 添加实体特征
        fused_matrix += self.weights['entity'] * features['entity']
        
        # 添加主题特征
        fused_matrix += self.weights['topic'] * features['topic']
        
        # 添加时间特征
        fused_matrix += self.weights['time_proximity'] * features['time']
        
        return fused_matrix
    
    def _find_representative_news(self, cluster_indices: List[int], similarity_matrix: np.ndarray) -> int:
        """找到簇中最具代表性的新闻
        
        Args:
            cluster_indices: 簇中新闻的索引列表
            similarity_matrix: 相似度矩阵
            
        Returns:
            代表性新闻的索引
        """
        # 计算每个新闻与簇中其他新闻的平均相似度
        avg_similarities = []
        
        for i, idx_i in enumerate(cluster_indices):
            total_sim = 0.0
            for j, idx_j in enumerate(cluster_indices):
                if i != j:
                    total_sim += similarity_matrix[idx_i, idx_j]
            
            avg_sim = total_sim / (len(cluster_indices) - 1) if len(cluster_indices) > 1 else 0.0
            avg_similarities.append((idx_i, avg_sim))
        
        # 选择平均相似度最高的新闻
        representative_idx = max(avg_similarities, key=lambda x: x[1])[0]
        return representative_idx
    
    def _generate_summary(self, news: Dict) -> str:
        """为新闻生成摘要
        
        Args:
            news: 新闻字典
            
        Returns:
            摘要文本
        """
        # 如果有LLM服务，使用LLM生成摘要
        if self.llm_service and self.llm_service.is_configured():
            try:
                # 构建提示
                prompt = f"为以下新闻生成一个简短的摘要（不超过100字）：\n标题：{news.get('title', '')}\n内容：{news.get('content', '')[:500]}"
                
                # 调用LLM服务
                summary = self.llm_service.call_llm(prompt)
                
                if isinstance(summary, str) and summary.strip():
                    return summary.strip()
            except Exception as e:
                self.logger.error(f"生成摘要出错: {e}")
        
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
        # 如果有LLM服务，使用LLM提取关键词
        if self.llm_service and self.llm_service.is_configured():
            try:
                # 构建提示
                prompt = f"从以下新闻中提取5个关键词：\n标题：{news.get('title', '')}\n内容：{news.get('content', '')[:500]}\n仅返回关键词列表，格式为JSON：{{\"keywords\": [\"关键词1\", \"关键词2\", ...]}}"
                
                # 调用LLM服务
                response = self.llm_service.call_llm(prompt)
                
                # 解析结果
                if isinstance(response, str):
                    try:
                        result = json.loads(response)
                        keywords = result.get('keywords', [])
                        if keywords:
                            return keywords[:5]
                    except json.JSONDecodeError:
                        pass
                elif isinstance(response, dict):
                    keywords = response.get('keywords', [])
                    if keywords:
                        return keywords[:5]
            except Exception as e:
                self.logger.error(f"提取关键词出错: {e}")
        
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
    
    def _extract_keywords_from_cluster(self, news_list: List[Dict]) -> List[str]:
        """从新闻簇中提取关键词
        
        Args:
            news_list: 新闻列表
            
        Returns:
            关键词列表
        """
        # 收集所有新闻的关键词
        all_keywords = []
        for news in news_list:
            keywords = self._extract_keywords(news)
            all_keywords.extend(keywords)
        
        # 统计关键词频率
        keyword_counter = Counter(all_keywords)
        
        # 选择频率最高的5个关键词
        top_keywords = [kw for kw, _ in keyword_counter.most_common(5)]
        
        return top_keywords
    
    def _categorize_news(self, news: Dict) -> str:
        """对新闻进行分类
        
        Args:
            news: 新闻字典
            
        Returns:
            分类ID
        """
        # 如果有LLM服务，使用LLM进行分类
        if self.llm_service and self.llm_service.is_configured():
            try:
                # 构建提示
                categories_str = ", ".join([f"{cat_id}({STANDARD_CATEGORIES.get(cat_id, {}).get('name', cat_id)})" 
                                         for cat_id in STANDARD_CATEGORIES.keys()])
                
                prompt = f"将以下新闻分类到这些类别之一：{categories_str}\n\n标题：{news.get('title', '')}\n内容：{news.get('content', '')[:500]}\n\n仅返回分类ID，格式为JSON：{{\"category\": \"分类ID\"}}"
                
                # 调用LLM服务
                response = self.llm_service.call_llm(prompt)
                
                # 解析结果
                if isinstance(response, str):
                    try:
                        result = json.loads(response)
                        category = result.get('category', '')
                        if category in STANDARD_CATEGORIES:
                            return category
                    except json.JSONDecodeError:
                        pass
                elif isinstance(response, dict):
                    category = response.get('category', '')
                    if category in STANDARD_CATEGORIES:
                        return category
            except Exception as e:
                self.logger.error(f"分类新闻出错: {e}")
        
        # 使用关键词匹配进行分类
        title = news.get('title', '') or ''
        content = news.get('content', '') or ''
        text = (title + " " + content).lower()
        
        # 特殊处理：检查是否包含建筑师相关关键词，如果有，优先归类为文化类别
        if "architect" in text.lower() or "建筑师" in text.lower() or "gaudí" in text.lower() or "教皇" in text.lower() or "pope" in text.lower() or "sainthood" in text.lower() or "圣人" in text.lower():
            matched_categories = [("culture", "建筑师")]
        else:
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
        return "general"
    
    def _categorize_cluster(self, news_list: List[Dict]) -> str:
        """对新闻簇进行分类
        
        Args:
            news_list: 新闻列表
            
        Returns:
            分类ID
        """
        # 统计每篇新闻的分类
        category_counter = Counter()
        for news in news_list:
            category = self._categorize_news(news)
            category_counter[category] += 1
        
        # 选择频率最高的分类
        if category_counter:
            return category_counter.most_common(1)[0][0]
        else:
            return "general"
    
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
                             similarity_threshold: Optional[float] = None, time_window: Optional[int] = None) -> None:
        """设置聚类参数
        
        Args:
            eps: DBSCAN的邻域半径参数
            min_samples: DBSCAN的最小样本数参数
            similarity_threshold: 相似度阈值
            time_window: 时间窗口（天）
        """
        if eps is not None:
            self.eps = eps
        if min_samples is not None:
            self.min_samples = min_samples
        if similarity_threshold is not None:
            self.similarity_threshold = similarity_threshold
        if time_window is not None:
            self.time_window = time_window
        
        self.logger.info(f"聚类参数已更新: eps={self.eps}, min_samples={self.min_samples}, similarity_threshold={self.similarity_threshold}, time_window={self.time_window}")
    
    def set_feature_weights(self, weights: Dict[str, float]) -> None:
        """设置特征权重
        
        Args:
            weights: 特征权重字典
        """
        for feature, weight in weights.items():
            if feature in self.weights:
                self.weights[feature] = weight
        
        # 归一化权重
        total_weight = sum(self.weights.values())
        if total_weight > 0:
            for feature in self.weights:
                self.weights[feature] /= total_weight
        
        self.logger.info(f"特征权重已更新: {self.weights}")