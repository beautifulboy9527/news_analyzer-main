# src/core/news_analysis_engine.py
"""
新闻分析引擎

负责新闻分析逻辑的处理，包括相似度分析、重要程度和立场分析等，
将分析逻辑从UI层分离，提高代码可维护性和可测试性。
"""

import logging
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
import time

from src.llm.llm_service import LLMService
from src.core.news_data_processor import NewsDataProcessor

# 添加自定义异常类
class AnalysisError(Exception):
    """分析过程中的基础异常类"""
    pass

class LLMServiceError(AnalysisError):
    """LLM服务相关错误"""
    pass

class DataProcessingError(AnalysisError):
    """数据处理相关错误"""
    pass

class AnalysisProcessor:
    """处理新闻分析的核心逻辑"""
    
    def __init__(self, llm_service: LLMService):
        """初始化分析处理器
        
        Args:
            llm_service: LLM服务实例
        """
        self.logger = logging.getLogger('news_analyzer.core.analysis_processor')
        self.llm_service = llm_service
    
    def process_single_news(self, news_data: Dict, analysis_type: str) -> Dict:
        """处理单条新闻分析
        
        Args:
            news_data: 新闻数据
            analysis_type: 分析类型
            
        Returns:
            分析结果
        """
        # 基础分析
        result = self.llm_service.analyze_news(news_data, analysis_type)
        
        # 补充重要程度和立场分析
        if analysis_type != "重要程度和立场分析":
            importance_stance = self.llm_service.analyze_importance_stance(news_data)
            result.update(importance_stance)
        
        return result
    
    def process_multiple_news(self, news_items: List[Dict], analysis_type: str) -> Dict:
        """处理多条新闻分析
        
        Args:
            news_items: 新闻数据列表
            analysis_type: 分析类型
            
        Returns:
            分析结果
        """
        # 相似度分析
        result = self.llm_service.analyze_news_similarity(news_items)
        
        # 补充第一条新闻的重要程度和立场
        if news_items:
            importance_stance = self.llm_service.analyze_importance_stance(news_items[0])
            result.update(importance_stance)
        
        return result
    
    def process_custom_analysis(self, news_data: Union[Dict, List[Dict]], custom_prompt: str) -> Dict:
        """使用自定义提示词进行分析
        
        Args:
            news_data: 新闻数据（单条或多条）
            custom_prompt: 自定义提示词
            
        Returns:
            分析结果
        """
        return self.llm_service.analyze_with_custom_prompt(news_data, custom_prompt)

class NewsAnalysisEngine:
    """
    新闻分析引擎，负责处理新闻分析相关的逻辑
    """
    
    def __init__(self, llm_service: LLMService, data_processor: NewsDataProcessor):
        """
        初始化新闻分析引擎
        
        Args:
            llm_service: LLM服务实例
            data_processor: 新闻数据处理器实例
        """
        self.logger = logging.getLogger('news_analyzer.core.news_analysis_engine')
        self.llm_service = llm_service
        self.data_processor = data_processor
        
        # 分析结果缓存
        self.analysis_results: Dict[str, Dict] = {}
        
        # 初始化分析处理器
        self.processor = AnalysisProcessor(llm_service)
        
        # 重试配置
        self.max_retries = 3
        self.retry_delay = 1  # 秒
    
    def analyze_news(self, news_items: List[Dict], analysis_type: str, custom_prompt: Optional[str] = None) -> Dict:
        """
        分析新闻
        
        Args:
            news_items: 要分析的新闻列表
            analysis_type: 分析类型
            custom_prompt: 自定义提示词
            
        Returns:
            分析结果字典，包含以下字段：
            - analysis: 分析文本
            - formatted_text: 格式化后的分析文本（包含元数据）
            - importance_scores: 重要程度评分（如果有）
            - stance_scores: 立场评分（如果有）
            - error: 错误信息（如果有）
            
        Raises:
            LLMServiceError: LLM服务相关错误
            DataProcessingError: 数据处理相关错误
        """
        if not news_items:
            raise DataProcessingError("没有提供新闻数据")
            
        if not self.llm_service:
            raise LLMServiceError("LLM服务未初始化")
        
        try:
            self.logger.info(f"开始分析 {len(news_items)} 条新闻...")
            
            # 数据预处理
            processed_data = self._preprocess_news_data(news_items)
            
            # 带重试的分析
            for attempt in range(self.max_retries):
                try:
                    # 使用分析处理器进行分析
                    if custom_prompt:
                        result = self.processor.process_custom_analysis(processed_data, custom_prompt)
                    elif len(processed_data) > 1:
                        result = self.processor.process_multiple_news(processed_data, analysis_type)
                    else:
                        result = self.processor.process_single_news(processed_data[0], analysis_type)
                    
                    # 后处理分析结果
                    final_result = self._postprocess_result(result)
                    
                    # 缓存结果
                    cache_key = f"{analysis_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    self.analysis_results[cache_key] = final_result
                    
                    # 添加元数据
                    final_result['analysis_type'] = analysis_type
                    final_result['news_count'] = len(news_items)
                    final_result['timestamp'] = datetime.now().isoformat()
                    
                    # 构建格式化文本
                    formatted_text = f"分析类型: {analysis_type}\n"
                    formatted_text += f"新闻数量: {len(news_items)}\n"
                    
                    # 添加新闻标题列表
                    formatted_text += "\n分析的新闻:\n"
                    for i, news in enumerate(news_items, 1):
                        title = news.get('title', '无标题')
                        source = news.get('source_name', news.get('source', '未知来源'))
                        formatted_text += f"{i}. {title} ({source})\n"
                    
                    formatted_text += "\n分析结果:\n"
                    formatted_text += final_result.get('analysis', '')
                    
                    # 更新结果字典
                    final_result['formatted_text'] = formatted_text
                    
                    # 保存分析结果到历史记录
                    self.data_processor.save_analysis_result(
                        result=final_result.get('analysis', ''),
                        analysis_type=analysis_type,
                        selected_news=news_items
                    )
                    
                    return final_result
                    
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        self.logger.warning(f"分析失败，尝试重试 ({attempt + 1}/{self.max_retries}): {str(e)}")
                        time.sleep(self.retry_delay)
                    else:
                        raise LLMServiceError(f"分析失败，已达到最大重试次数: {str(e)}")
            
        except Exception as e:
            self.logger.error(f"分析新闻时出错: {e}", exc_info=True)
            return {"error": f"分析新闻失败: {e}"}
    
    def _preprocess_news_data(self, news_items: List[Dict]) -> List[Dict]:
        """预处理新闻数据
        
        Args:
            news_items: 原始新闻数据列表
            
        Returns:
            处理后的新闻数据列表
        """
        processed_items = []
        for item in news_items:
            try:
                processed_item = {
                    'title': item.get('title', '').strip(),
                    'content': item.get('content', '').strip(),
                    'source': item.get('source_name', '未知来源'),
                    'pub_date': str(item.get('publish_time', '')),
                    'url': item.get('url', '')
                }
                processed_items.append(processed_item)
            except Exception as e:
                self.logger.warning(f"处理新闻项时出错，已跳过: {str(e)}")
                continue
        
        if not processed_items:
            raise DataProcessingError("所有新闻数据处理失败")
        
        return processed_items
    
    def _postprocess_result(self, result: Dict) -> Dict:
        """后处理分析结果
        
        Args:
            result: 原始分析结果
            
        Returns:
            处理后的分析结果
        """
        if not isinstance(result, dict):
            raise DataProcessingError("分析结果格式错误")
        
        # 确保结果包含必要字段
        processed_result = {
            'analysis': result.get('analysis', ''),
            'importance': result.get('importance', 0),
            'stance': result.get('stance', 0.0)
        }
        
        # 添加时间戳
        processed_result['timestamp'] = datetime.now().isoformat()
        
        return processed_result
    
    def get_analysis_result(self, group_id: str) -> Optional[Dict]:
        """
        获取指定组的分析结果
        
        Args:
            group_id: 组ID
            
        Returns:
            分析结果字典，如果不存在则返回None
        """
        return self.analysis_results.get(group_id)
    
    def get_all_analysis_results(self) -> Dict[str, Dict]:
        """
        获取所有分析结果
        
        Returns:
            所有分析结果字典
        """
        return self.analysis_results
    
    def clear_analysis_results(self):
        """
        清空分析结果缓存
        """
        self.analysis_results.clear()