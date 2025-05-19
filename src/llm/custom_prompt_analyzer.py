# src/llm/custom_prompt_analyzer.py
"""
自定义提示词分析器

为LLMService添加使用自定义提示词进行分析的功能，
支持新闻分析整合面板中的提示词管理功能。
"""

import logging
from typing import Dict, Any, Optional

from src.llm.formatter import LLMResponseFormatter


def analyze_with_custom_prompt(self, data: Dict[str, Any], custom_prompt: str, template_name: Optional[str] = None):
    """
    使用自定义提示词进行分析
    
    Args:
        data: 分析数据，包含新闻内容等信息
        custom_prompt: 自定义提示词内容
        template_name: 模板名称，用于记录日志和格式化结果
        
    Returns:
        分析结果
    """
    if not self.provider:
        self.logger.warning(f"LLM provider not configured. Returning mock analysis for custom prompt.")
        return LLMResponseFormatter.format_analysis_result(
            f"<p style='color: red;'>LLM服务未配置，无法使用自定义提示词进行分析</p>", 
            template_name or "自定义分析"
        )
    
    self.logger.info(f"使用自定义提示词进行分析，模板: {template_name or '未指定'}")
    
    # 准备提示词
    try:
        # 使用提供的自定义提示词，并进行格式化
        formatted_prompt = custom_prompt
        
        # 尝试使用数据中的变量替换占位符
        try:
            # 确保所有必要的键都存在于数据中
            format_data = {
                'title': data.get('title', '无标题'),
                'source': data.get('source', '未知来源'),
                'pub_date': str(data.get('pub_date', '未知日期')),
                'content': data.get('content', '无内容'),
                'news_items': data.get('news_items', '')
            }
            
            # 格式化提示词
            formatted_prompt = custom_prompt.format(**format_data)
        except KeyError as e:
            self.logger.warning(f"格式化自定义提示词时出错: {e}，将使用原始提示词")
        
        # 发送请求
        headers = self.provider.get_headers()
        messages_for_payload = [{'role': 'user', 'content': formatted_prompt}]
        payload = self.provider.prepare_request_payload(
            messages=messages_for_payload,
            stream=False
        )

        result_json = self.api_client.post(
            url=self.provider.api_url,
            headers=headers,
            json_payload=payload,
            timeout=self.provider._get_config_value('timeout', 120)  # 使用更长的超时时间
        )

        content = self.provider.parse_response(result_json)

        if not content:
            self.logger.warning(f"使用自定义提示词的分析返回了空内容")
            return LLMResponseFormatter.format_analysis_result(
                "<p style='color: orange;'>分析成功，但模型未返回有效内容。</p>", 
                template_name or "自定义分析"
            )

        # 解析结果中的重要程度和立场信息
        result = LLMResponseFormatter.extract_metrics_from_content(content)
        result['analysis'] = content
        
        return result

    except Exception as e:
        self.logger.error(f"使用自定义提示词进行分析时出错: {e}", exc_info=True)
        error_html = LLMResponseFormatter.format_error_html(f"分析时发生错误: {e}")
        return {'analysis': error_html}