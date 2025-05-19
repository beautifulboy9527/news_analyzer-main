# src/llm/processors.py
"""
信息处理模块

提供将LLM输出的文本分析结果转换为数字化表示的功能，
支持重要程度和立场识别的数字化与可视化展示。
"""

import re
import logging
from typing import Dict, Any, Tuple, Optional, List, Union

class TextProcessor:
    """文本处理器，将LLM输出的文本分析结果转换为数字化表示"""
    
    def __init__(self):
        """初始化文本处理器"""
        self.logger = logging.getLogger('news_analyzer.llm.processors')
        
        # 默认重要程度映射规则
        self.importance_mapping = {
            "头条": 5,
            "重要": 3,
            "一般": 1,
            "次要": 0
        }
        
        # 默认立场映射规则
        self.stance_mapping = {
            "亲美": -1,
            "亲西方": -0.8,
            "偏美": -0.5,
            "中立": 0,
            "偏中": 0.5,
            "亲中": 1
        }
        
        # 多维立场分析支持
        self.stance_dimensions = {
            "政治立场": {
                "左翼": -1,
                "中间": 0,
                "右翼": 1
            },
            "经济立场": {
                "国家干预": -1,
                "混合": 0,
                "自由市场": 1
            }
        }
    
    def digitize_importance(self, text: str) -> int:
        """将重要程度文本转为数字
        
        Args:
            text: 包含重要程度描述的文本
            
        Returns:
            重要程度的数字表示（0-5）
        """
        # 转换为小写并移除标点符号，以提高匹配率
        normalized_text = text.lower().strip()
        
        # 尝试直接匹配关键词
        for keyword, score in self.importance_mapping.items():
            if keyword.lower() in normalized_text:
                self.logger.debug(f"匹配到重要程度关键词: {keyword}, 分数: {score}")
                return score
        
        # 如果没有直接匹配，尝试使用正则表达式进行模糊匹配
        if re.search(r'(非常|极其|特别)(重要|关键)', normalized_text):
            return 5
        elif re.search(r'重要|关键', normalized_text):
            return 3
        elif re.search(r'一般|普通', normalized_text):
            return 1
        elif re.search(r'(不|不太|不很)(重要|关键)', normalized_text):
            return 0
            
        # 默认返回中等重要程度
        self.logger.warning(f"无法从文本中提取重要程度: {text}, 返回默认值1")
        return 1
    
    def digitize_stance(self, text: str, dimension: str = None) -> float:
        """将立场文本转为数字
        
        Args:
            text: 包含立场描述的文本
            dimension: 立场维度，如'政治立场'、'经济立场'等，默认为None（使用通用立场映射）
            
        Returns:
            立场的数字表示（-1到1）
        """
        # 转换为小写并移除标点符号，以提高匹配率
        normalized_text = text.lower().strip()
        
        # 如果指定了维度，使用该维度的映射
        if dimension and dimension in self.stance_dimensions:
            mapping = self.stance_dimensions[dimension]
        else:
            mapping = self.stance_mapping
        
        # 尝试直接匹配关键词
        for keyword, score in mapping.items():
            if keyword.lower() in normalized_text:
                self.logger.debug(f"匹配到立场关键词: {keyword}, 分数: {score}")
                return score
        
        # 如果没有直接匹配，尝试使用正则表达式进行模糊匹配
        if dimension is None:  # 仅对通用立场进行模糊匹配
            if re.search(r'(强烈|明显)(支持|倾向)(美|西方)', normalized_text):
                return -1.0
            elif re.search(r'(支持|倾向)(美|西方)', normalized_text):
                return -0.5
            elif re.search(r'中立|平衡|客观', normalized_text):
                return 0.0
            elif re.search(r'(支持|倾向)中', normalized_text):
                return 0.5
            elif re.search(r'(强烈|明显)(支持|倾向)中', normalized_text):
                return 1.0
                
        # 默认返回中立立场
        self.logger.warning(f"无法从文本中提取立场: {text}, 返回默认值0")
        return 0.0
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """分析文本，提取重要程度和立场
        
        Args:
            text: 需要分析的文本
            
        Returns:
            包含分析结果的字典
        """
        # 初始化结果字典
        result = {
            'importance': 0,
            'stance': 0.0,
            'dimensions': {}
        }
        
        # 提取重要程度
        importance_patterns = [
            r'重要(程度|性)[：:](.*?)(?=\n|$)',
            r'(头条|重要|一般|次要)(新闻|报道)',
            r'新闻(重要性|价值)[：:](.*?)(?=\n|$)'
        ]
        
        for pattern in importance_patterns:
            matches = re.search(pattern, text)
            if matches:
                importance_text = matches.group(0)
                result['importance'] = self.digitize_importance(importance_text)
                break
        
        # 提取立场
        stance_patterns = [
            r'(政治|媒体)?立场[：:](.*?)(?=\n|$)',
            r'(倾向|偏向)[：:](.*?)(?=\n|$)',
            r'(亲美|亲中|中立|偏美|偏中)'
        ]
        
        for pattern in stance_patterns:
            matches = re.search(pattern, text)
            if matches:
                stance_text = matches.group(0)
                result['stance'] = self.digitize_stance(stance_text)
                break
        
        # 尝试提取多维度立场分析
        for dimension in self.stance_dimensions.keys():
            dimension_pattern = f"{dimension}[：:](.*?)(?=\n|$)"
            matches = re.search(dimension_pattern, text)
            if matches:
                dimension_text = matches.group(0)
                result['dimensions'][dimension] = self.digitize_stance(dimension_text, dimension)
        
        return result
    
    def customize_importance_mapping(self, mapping: Dict[str, int]) -> None:
        """自定义重要程度映射规则
        
        Args:
            mapping: 自定义的重要程度映射字典
        """
        if not isinstance(mapping, dict):
            self.logger.error("自定义重要程度映射必须是字典类型")
            return
            
        self.importance_mapping.update(mapping)
        self.logger.info(f"已更新重要程度映射: {self.importance_mapping}")
    
    def customize_stance_mapping(self, mapping: Dict[str, float], dimension: str = None) -> None:
        """自定义立场映射规则
        
        Args:
            mapping: 自定义的立场映射字典
            dimension: 立场维度，如果为None则更新通用立场映射
        """
        if not isinstance(mapping, dict):
            self.logger.error("自定义立场映射必须是字典类型")
            return
            
        if dimension and dimension in self.stance_dimensions:
            self.stance_dimensions[dimension].update(mapping)
            self.logger.info(f"已更新{dimension}立场映射: {self.stance_dimensions[dimension]}")
        elif dimension:
            # 添加新的维度
            self.stance_dimensions[dimension] = mapping
            self.logger.info(f"已添加新的立场维度: {dimension}")
        else:
            # 更新通用立场映射
            self.stance_mapping.update(mapping)
            self.logger.info(f"已更新通用立场映射: {self.stance_mapping}")


# 单例模式，方便全局访问
text_processor = TextProcessor()


# 便捷函数，直接调用单例实例的方法
def digitize_importance(text: str) -> int:
    """将重要程度文本转为数字"""
    return text_processor.digitize_importance(text)


def digitize_stance(text: str, dimension: str = None) -> float:
    """将立场文本转为数字"""
    return text_processor.digitize_stance(text, dimension)


def analyze_text(text: str) -> Dict[str, Any]:
    """分析文本，提取重要程度和立场"""
    return text_processor.analyze_text(text)


# 测试代码
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # 测试文本
    test_text = """
    这是一篇重要性：头条的新闻报道。
    政治立场：偏向中国。
    经济立场：支持自由市场。
    """
    
    # 分析文本
    result = analyze_text(test_text)
    print(f"分析结果: {result}")
    
    # 测试单独的函数
    print(f"重要程度: {digitize_importance('这是一篇重要的新闻')}")
    print(f"立场: {digitize_stance('这篇报道明显偏向中国')}")