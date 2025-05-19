# src/core/news_data_processor.py
"""
新闻数据处理器

负责新闻数据的加载、分类、分组和预处理，
将数据处理逻辑从UI层分离，提高代码可维护性和可测试性。
"""

import logging
import time
from datetime import datetime
from typing import List, Dict, Set, Tuple, Optional, Any

from src.storage.news_storage import NewsStorage
from src.collectors.categories import STANDARD_CATEGORIES
from src.core.enhanced_news_clusterer import EnhancedNewsClusterer


class NewsDataProcessor:
    """
    新闻数据处理器，负责新闻数据的加载、分类、分组和预处理
    """
    
    def __init__(self, storage: NewsStorage):
        """
        初始化新闻数据处理器
        
        Args:
            storage: 新闻存储服务实例
        """
        self.logger = logging.getLogger('news_analyzer.core.news_data_processor')
        self.storage = storage
        
        # 初始化数据容器
        self.all_news_items: List[Dict] = []
        self.categorized_news: Dict[str, List[Dict]] = {}
        self.news_groups: List[List[Dict]] = []
        
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
        
    def load_news_data(self) -> List[Dict]:
        """
        从存储加载新闻数据
        
        Returns:
            新闻数据列表
        """
        if not self.storage:
            self.logger.warning("Storage 无效，无法加载新闻数据")
            return []
        
        self.logger.info("开始加载新闻数据...")
        self.all_news_items = []
        self.categorized_news = {}
        
        try:
            # 加载最新的新闻批次
            news_data = self.storage.load_news()
            
            if not news_data:
                self.logger.info("没有找到新闻数据")
                return []
            
            self.all_news_items = news_data
            self.logger.info(f"加载了 {len(news_data)} 条新闻数据")
            
            # 自动分类新闻
            self._categorize_news()
            
            return self.all_news_items
            
        except Exception as e:
            self.logger.error(f"加载新闻数据时出错: {e}", exc_info=True)
            return []
    
    def _categorize_news(self):
        """
        自动将新闻分类到不同类别
        """
        self.logger.info("开始自动分类新闻...")
        
        # 初始化分类字典
        for category_id, category_info in STANDARD_CATEGORIES.items():
            self.categorized_news[category_id] = []
        
        # 添加一个未分类类别
        self.categorized_news["uncategorized"] = []
        
        # 添加军事类别（在STANDARD_CATEGORIES中可能没有）
        if "military" not in self.categorized_news:
            self.categorized_news["military"] = []
        
        for news in self.all_news_items:
            title = news.get('title', '') or ''
            content = news.get('content', '') or ''
            text = (title + " " + content).lower()
            
            # 初始化分类结果
            categorized = False
            matched_categories = []
            
            # 遍历所有类别的关键词，收集所有匹配的类别
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
                    self.categorized_news[title_matches[0]].append(news)
                    categorized = True
                else:
                    # 使用内容中的第一个匹配类别
                    self.categorized_news[matched_categories[0][0]].append(news)
                    categorized = True
            
            # 如果没有匹配到任何类别，放入未分类
            if not categorized:
                self.categorized_news["uncategorized"].append(news)
        
        # 记录各类别的新闻数量
        for category_id, news_list in self.categorized_news.items():
            category_name = STANDARD_CATEGORIES.get(category_id, {}).get("name", "未分类")
            if category_id == "uncategorized":
                category_name = "未分类"
            elif category_id == "military" and category_id not in STANDARD_CATEGORIES:
                category_name = "军事新闻"
            self.logger.info(f"类别 '{category_name}' 包含 {len(news_list)} 条新闻")
    
    def get_news_by_category(self, category_id: str) -> List[Dict]:
        """
        获取指定类别的新闻
        
        Args:
            category_id: 类别ID，如果为'all'则返回所有新闻
            
        Returns:
            新闻列表
        """
        if category_id == "all":
            return self.all_news_items
        elif category_id in self.categorized_news:
            return self.categorized_news[category_id]
        else:
            return []
    
    def get_category_name(self, category_id: str) -> str:
        """
        获取类别名称
        
        Args:
            category_id: 类别ID
            
        Returns:
            类别名称
        """
        if category_id == "all":
            return "所有新闻"
        elif category_id == "uncategorized":
            return "未分类"
        elif category_id == "military" and category_id not in STANDARD_CATEGORIES:
            return "军事新闻"
        else:
            return STANDARD_CATEGORIES.get(category_id, {}).get("name", "未分类")
    
    def get_news_categories(self, news_items: List[Dict]) -> List[str]:
        """
        获取新闻所属的分类列表
        
        Args:
            news_items: 新闻列表
            
        Returns:
            分类名称列表
        """
        categories = []
        for news in news_items:
            # 查找新闻所属分类
            for cat_id, cat_news in self.categorized_news.items():
                if news in cat_news:
                    categories.append(self.get_category_name(cat_id))
                    break
        return categories
    
    def auto_group_news(self, news_items: List[Dict], method: str = "title_similarity") -> List[List[Dict]]:
        """
        自动分组相关新闻
        
        Args:
            news_items: 要分组的新闻列表
            method: 分组方法，'title_similarity'或'multi_feature'
            
        Returns:
            分组后的新闻列表，每个元素是一个新闻组
        """
        if not news_items:
            self.logger.warning("没有可分组的新闻数据")
            return []
        
        self.logger.info(f"开始自动分组新闻，使用方法: {method}...")
        
        # 如果选择多特征融合方法，使用增强型新闻聚类器
        if method == "multi_feature":
            return self._auto_group_news_enhanced(news_items)
        
        # 使用标题相似度方法（原始方法）
        return self._auto_group_news_by_title(news_items)
    
    def _auto_group_news_enhanced(self, news_items: List[Dict]) -> List[Dict]:
        """
        使用增强型新闻聚类器进行多特征融合分组
        
        Args:
            news_items: 要分组的新闻列表
            
        Returns:
            事件组列表，每个事件组为一个字典
        """
        try:
            # 创建增强型新闻聚类器实例
            clusterer = EnhancedNewsClusterer()
            
            # 准备数据
            news_data = []
            for news in news_items:
                news_data.append({
                    'id': news.get('id'),
                    'title': news.get('title', ''),
                    'content': news.get('content', ''),
                    'source': news.get('source_name', ''),
                    'publish_time': news.get('publish_time', '')
                })
            
            # 执行聚类 (Corrected method name)
            events = clusterer.cluster(news_data)
            
            # 直接返回 EnhancedClusterer 的结果
            self.news_groups = events # Store the events
            return events
            
        except Exception as e:
            self.logger.error(f"使用增强型新闻聚类器分组时出错: {e}", exc_info=True)
            return []
    
    def _auto_group_news_by_title(self, news_items: List[Dict]) -> List[List[Dict]]:
        """
        使用标题相似度方法分组新闻
        
        Args:
            news_items: 要分组的新闻列表
            
        Returns:
            分组后的新闻列表
        """
        try:
            # 使用标题关键词匹配、主题识别和来源区分进行分组
            groups = []
            processed = set()
            
            # 优化：预处理所有标题，避免重复处理
            preprocessed_titles = []
            # 主题关键词字典 - 用于识别新闻主题
            topic_keywords = {
                "ai": ["ai", "artificial intelligence", "chatgpt", "openai", "llm", "large language model", "gpt", "机器学习", "人工智能"],
                "tech": ["technology", "tech", "software", "hardware", "app", "application", "digital", "computer", "internet", "web", "online", "科技", "技术"],
                "social": ["social", "society", "community", "people", "public", "social media", "facebook", "twitter", "instagram", "tiktok", "社交", "社会"],
                "politics": ["politics", "government", "election", "president", "policy", "political", "vote", "democracy", "republican", "democrat", "政治", "政府"],
                "business": ["business", "economy", "market", "stock", "company", "corporation", "finance", "investment", "商业", "经济", "市场", "金融"],
                "health": ["health", "medical", "medicine", "disease", "virus", "doctor", "hospital", "patient", "healthcare", "健康", "医疗", "疾病"],
                "environment": ["environment", "climate", "weather", "pollution", "green", "sustainable", "ecology", "wildlife", "nature", "环境", "气候", "生态", "野生动物"],
                "sports": ["sports", "game", "match", "team", "player", "championship", "tournament", "competition", "体育", "比赛", "选手", "冠军"],
                "entertainment": ["entertainment", "movie", "film", "music", "celebrity", "star", "actor", "actress", "singer", "娱乐", "电影", "音乐", "明星"],
                "science": ["science", "research", "study", "discovery", "experiment", "scientist", "laboratory", "科学", "研究", "发现", "实验"]
            }
            
            for news in news_items:
                title = news.get('title', '').lower()
                words = set(title.split()) if title else set()
                
                # 识别新闻主题
                topics = set()
                for topic, keywords in topic_keywords.items():
                    for keyword in keywords:
                        if keyword in title:
                            topics.add(topic)
                            break
                
                preprocessed_titles.append((title, words, topics))
            
            import time
            start_time = time.time()
            max_processing_time = 60  # 最大处理时间（秒）
            
            for i, news in enumerate(news_items):
                # 检查是否超时
                if time.time() - start_time > max_processing_time:
                    self.logger.warning(f"自动分组处理时间超过{max_processing_time}秒，提前结束处理")
                    break
                    
                if i in processed:
                    continue
                
                title_i, words_i, topics_i = preprocessed_titles[i]
                if not title_i:
                    continue
                
                # 创建新组，记录新闻来源
                group = [news]
                sources = {news.get('source_name', '未知来源')}
                processed.add(i)
                
                # 查找相似新闻，但来源不同的新闻
                for j, other_news in enumerate(news_items):
                    if j in processed or i == j:
                        continue
                    
                    # 检查来源是否已存在于当前组
                    other_source = other_news.get('source_name', '未知来源')
                    if other_source in sources:
                        continue  # 跳过相同来源的新闻
                    
                    title_j, words_j, topics_j = preprocessed_titles[j]
                    if not title_j:
                        continue
                    
                    # 1. 主题匹配检查 - 如果两篇新闻的主题完全不同且都有明确主题，则跳过
                    if topics_i and topics_j and not topics_i.intersection(topics_j):
                        continue
                    
                    # 2. 关键词匹配
                    common_words = words_i.intersection(words_j)
                    keyword_similarity = len(common_words) / max(len(words_i), 1) if words_i else 0
                    
                    # 提取实体名词（大写开头的词，可能是人名、地名、组织名等）
                    entities_i = {word for word in title_i.split() if word and word[0].isupper()}
                    entities_j = {word for word in title_j.split() if word and word[0].isupper()}
                    entity_match = bool(entities_i.intersection(entities_j)) if entities_i and entities_j else False
                    
                    # 提取数字（可能是日期、数量等重要信息）
                    import re
                    numbers_i = set(re.findall(r'\d+', title_i))
                    numbers_j = set(re.findall(r'\d+', title_j))
                    # 如果两篇新闻都包含数字，但没有共同数字，可能是不同事件
                    if numbers_i and numbers_j and not numbers_i.intersection(numbers_j):
                        # 数字不匹配，降低相似度可能性
                        # 但如果有强实体匹配，仍然继续检查
                        if not entity_match or len(entities_i.intersection(entities_j)) < 2:
                            continue
                    
                    # 只有关键词匹配度较高或有共同实体的才进行更复杂的相似度计算
                    if keyword_similarity > 0.3 or len(common_words) >= 3 or (entity_match and len(entities_i.intersection(entities_j)) >= 2):
                        # 3. 字符串相似度 - 使用更高效的算法
                        # 简化版：使用共同字符比例而不是LCS
                        chars_i = set(title_i)
                        chars_j = set(title_j)
                        common_chars = len(chars_i.intersection(chars_j))
                        string_similarity = common_chars / max(len(chars_i) + len(chars_j) - common_chars, 1)
                        
                        # 4. 语义相似度评估 - 基于关键词和实体
                        semantic_similarity = 0.0
                        
                        # 检查是否包含相同的关键实体（如公司名、人名等）
                        if entity_match:
                            # 根据匹配实体数量调整权重
                            matched_entities = len(entities_i.intersection(entities_j))
                            if matched_entities >= 3:
                                semantic_similarity += 0.4
                            elif matched_entities >= 2:
                                semantic_similarity += 0.3
                            else:
                                semantic_similarity += 0.2
                        
                        # 检查关键词的语义相关性
                        if len(common_words) >= 4:
                            semantic_similarity += 0.3
                        elif len(common_words) >= 3:
                            semantic_similarity += 0.2
                        elif len(common_words) >= 2:
                            semantic_similarity += 0.1
                        
                        # 5. 综合相似度评分 - 加入语义相似度权重
                        similarity_score = 0.35 * keyword_similarity + 0.25 * string_similarity + 0.4 * semantic_similarity
                        
                        # 6. 更严格的相似度阈值判断
                        # 如果相似度超过阈值，认为是相似新闻
                        if similarity_score > 0.6 or (entity_match and keyword_similarity > 0.4) or (len(common_words) >= 5):
                            group.append(other_news)
                            sources.add(other_source)
                            processed.add(j)
                
                if len(group) > 1:  # 只保留有多条新闻的组
                    groups.append(group)
            
            # 记录处理时间
            processing_time = time.time() - start_time
            self.logger.info(f"自动分组处理完成，耗时 {processing_time:.2f} 秒，处理了 {len(processed)}/{len(news_items)} 条新闻")
            
            self.news_groups = groups
            return groups
            
        except Exception as e:
            self.logger.error(f"使用标题相似度方法分组时出错: {e}", exc_info=True)
            return []
    
    def prepare_news_for_analysis(self, news_items: List[Dict]) -> List[Dict]:
        """
        准备用于分析的新闻数据
        
        Args:
            news_items: 原始新闻列表
            
        Returns:
            处理后的新闻数据列表
        """
        news_data = []
        for news in news_items:
            news_data.append({
                'title': news.get('title', ''),
                'content': news.get('content', ''),
                'source': news.get('source_name', ''),
                'publish_time': news.get('publish_time', '')
            })
        return news_data
    
    def save_analysis_result(self, result: str, analysis_type: str, selected_news: List[Dict]):
        """
        保存分析结果到历史记录
        
        Args:
            result: 分析结果文本
            analysis_type: 分析类型
            selected_news: 被分析的新闻列表
        """
        try:
            # 获取分析的新闻标题和来源
            news_titles = []
            news_sources = []
            for news in selected_news:
                title = news.get('title', '无标题')
                source = news.get('source_name', '未知来源')
                if title not in news_titles:
                    news_titles.append(title)
                if source not in news_sources:
                    news_sources.append(source)
            
            # 创建分析记录
            analysis_record = {
                'timestamp': datetime.now().isoformat(),
                'type': analysis_type,
                'result': result,
                'news_count': len(selected_news),
                'news_titles': news_titles,
                'news_sources': news_sources,
                'categories': list(set(self.get_news_categories(selected_news)))
            }
            
            # 如果是分组分析，添加分组信息
            if self.news_groups:
                group_info = []
                for group in self.news_groups:
                    if any(news in selected_news for news in group):
                        first_news = group[0]
                        sources = set(news.get('source_name', '未知来源') for news in group)
                        group_info.append({
                            'title': first_news.get('title', '无标题'),
                            'sources': list(sources),
                            'count': len(group)
                        })
                if group_info:
                    analysis_record['groups'] = group_info
            
            # 调用存储服务保存记录
            if self.storage:
                self.storage.save_analysis_result(analysis_record)
                self.logger.info(f"已保存分析结果到历史记录: {analysis_type}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"保存分析结果到历史记录时出错: {e}", exc_info=True)
            return False