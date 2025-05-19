"""
LLM 响应格式化工具
"""
from typing import Dict, Any
import re
import markdown2
import logging

class LLMResponseFormatter:
    """
    提供将 LLM 响应或错误格式化为 HTML 的静态方法。
    """
    
    logger = logging.getLogger('news_analyzer.llm.formatter')

    @staticmethod
    def format_analysis_result(content: str, analysis_type: str) -> str:
        """格式化分析结果为HTML
        
        Args:
            content: 原始分析内容
            analysis_type: 分析类型
            
        Returns:
            格式化后的HTML字符串
        """
        try:
            # 处理内容格式化
            formatted_content = LLMResponseFormatter._format_content(content)
            
            # 根据分析类型选择不同的格式化模板
            template = LLMResponseFormatter._get_template_by_type(analysis_type)
            
            # 应用模板
            html = template.replace("{content}", formatted_content)
            # 移除可能出现的重复标题（同一个<h2>标签连续出现两次）
            try:
                html = re.sub(
                    r'(?P<h><h2\b[^>]*>.*?</h2>)\s*(?P=h)',
                    r'\1',
                    html,
                    flags=re.DOTALL
                )
            except Exception:
                pass
            return html
        except Exception as e:
            LLMResponseFormatter.logger.error(f"格式化分析结果时出错: {e}", exc_info=True)
            return LLMResponseFormatter.format_error_html(f"格式化结果时出错: {str(e)}")

    @staticmethod
    def _format_content(content: str) -> str:
        """格式化内容文本为HTML
        
        Args:
            content: 原始内容文本
            
        Returns:
            格式化后的HTML
        """
        if not content:
            return ""
            
        try:
            # 去除开头可能的Markdown标题行
            content = re.sub(r'^(?:\s*#+[^\n]*\n)+', '', content)
            # 移除可能存在的标题前缀（包括全角或半角括号内的字数说明）
            content = re.sub(
                r'^(?:新闻摘要|深度分析|关键观点|事实核查)(?:\s*[（(]\d+字以内[)）])?\s*[:：]?\s*',
                '',
                content.strip()
            )
            
            # 使用markdown2进行基础转换
            extras = {
                'code-friendly': True,
                'break-on-newline': True,
                'tables': True,
                'header-ids': True,
                'fenced-code-blocks': True
            }
            content = markdown2.markdown(content, extras=extras)
            
            # 移除可能存在的HTML标题标签，防止重复显示
            content = re.sub(
                r'<h[1-6][^>]*>(?:新闻摘要|深度分析|关键观点|事实核查)(?:\s*[（(]\d+字以内[)）])?\s*<\/h[1-6]>',
                '', content)
            
            # 自定义后处理
            # 1. 处理连续的换行，确保段落间距一致
            content = re.sub(r'<\/p>\s*<p>', '</p><p>', content)
            
            # 2. 优化列表样式
            content = content.replace('<ul>', '<ul style="margin: 10px 0; padding-left: 20px;">')
            content = content.replace('<ol>', '<ol style="margin: 10px 0; padding-left: 20px;">')
            
            # 3. 优化代码块样式
            content = content.replace('<code>', '<code style="background-color: #f8f9fa; padding: 2px 4px; border-radius: 4px; font-family: Consolas, monospace;">')
            
            # 4. 确保内容被正确包装
            if not content.startswith('<p>') and not content.startswith('<h'):
                content = '<p>' + content
            if not content.endswith('</p>') and not content.endswith('</ol>') and not content.endswith('</ul>'):
                content += '</p>'
            
            # 包装在带样式的div中
            content = f'''
                <div class="analysis-content" style="
                    font-family: 'Microsoft YaHei', sans-serif;
                    line-height: 1.6;
                    padding: 0px;
                ">
                    {content}
                    <style>
                        .analysis-content p {{ margin: 10px 0; }}
                        .analysis-content h1, .analysis-content h2, .analysis-content h3 {{ 
                            color: #34495e;
                            margin: 18px 0 8px;
                            font-size: 1.15em;
                            font-weight: 600;
                        }}
                        .analysis-content ul, .analysis-content ol {{
                            margin: 10px 0;
                            padding-left: 20px;
                        }}
                        .analysis-content li {{
                            margin: 5px 0;
                        }}
                        .analysis-content code {{
                            background-color: rgba(0,0,0,0.04);
                            padding: 2px 4px;
                            border-radius: 4px;
                            font-family: Consolas, monospace;
                            font-size: 0.9em;
                        }}
                        .analysis-content pre {{
                            background-color: rgba(0,0,0,0.04);
                            padding: 10px;
                            border-radius: 6px;
                            overflow-x: auto;
                        }}
                        .analysis-content strong {{
                            font-weight: 600;
                        }}
                        .analysis-content em {{
                            color: #7f8c8d;
                            font-style: italic;
                        }}
                        .analysis-content blockquote {{
                            border-left: 3px solid #a5b1b6;
                            margin: 10px 0;
                            padding: 6px 12px;
                            background-color: rgba(0,0,0,0.03);
                            color: #6a737d;
                        }}
                        .analysis-content table {{
                            border-collapse: collapse;
                            width: 100%;
                            margin: 10px 0;
                        }}
                        .analysis-content th, .analysis-content td {{
                            border: 1px solid #dfe2e5;
                            padding: 6px;
                            text-align: left;
                        }}
                        .analysis-content th {{
                            background-color: rgba(0,0,0,0.04);
                            font-weight: 600;
                        }}
                    </style>
                </div>
            '''
            
            return content
        except Exception as e:
            LLMResponseFormatter.logger.error(f"格式化内容时出错: {e}", exc_info=True)
            return f'<p style="color: #e74c3c;">格式化内容时出错: {str(e)}</p>'

    @staticmethod
    def _get_template_by_type(analysis_type: str) -> str:
        """根据分析类型获取对应的HTML模板
        
        Args:
            analysis_type: 分析类型
            
        Returns:
            HTML模板字符串
        """
        # 获取分析类型的显示名称
        display_names = {
            "摘要": "新闻摘要 (200字以内)",
            "深度分析": "深度分析结果",
            "关键观点": "关键观点分析",
            "事实核查": "事实核查结果",
            "重要程度和立场分析": "重要程度和立场分析",
            "新闻相似度分析": "新闻相似度分析"
        }
        display_name = display_names.get(analysis_type, analysis_type)
        
        # 定义不同类型的边框颜色
        border_colors = {
            "摘要": "#9b59b6",
            "深度分析": "#2ecc71",
            "关键观点": "#f1c40f",
            "事实核查": "#1abc9c",
            "重要程度和立场分析": "#3498db",
            "新闻相似度分析": "#e74c3c"
        }
        border_color = border_colors.get(analysis_type, "#95a5a6")
        
        # 统一的模板
        template = f'''
            <div class="analysis-result" style="margin-bottom: 20px;">
                <h2 style="
                    color: #2c3e50;
                    border-bottom: 2px solid {border_color};
                    padding-bottom: 10px;
                    margin-bottom: 20px;
                    font-family: 'Microsoft YaHei', sans-serif;
                    font-size: 1.3em;
                ">
                    {display_name}
                </h2>
                {{content}}
        </div>
        '''
        
        return template

    @staticmethod
    def format_error_html(error_message: str) -> str:
        """格式化错误消息为HTML
        
        Args:
            error_message: 错误消息
            
        Returns:
            格式化后的HTML字符串
        """
        return f'''
            <div style="
                font-family: 'Microsoft YaHei', sans-serif;
                color: #e74c3c;
                background-color: #fdf3f2;
                padding: 20px;
                border-radius: 8px;
                border-left: 4px solid #e74c3c;
                margin: 10px 0;
            ">
                <h3 style="margin-top: 0; color: #c0392b;">分析过程中出现错误</h3>
                <p style="margin-bottom: 0;">{error_message}</p>
         </div>
        '''

    @staticmethod
    def mock_analysis(news_item: Dict[str, Any], analysis_type: str) -> str:
        """生成模拟分析结果的HTML
        
        Args:
            news_item: 新闻数据字典
            analysis_type: 分析类型
            
        Returns:
            模拟分析结果HTML
        """
        title = news_item.get('title', '无标题')
        return f'''
            <div style="
                font-family: 'Microsoft YaHei', sans-serif;
                background-color: #fff3cd;
                color: #856404;
                padding: 20px;
                border-radius: 8px;
                border-left: 4px solid #ffeeba;
                margin: 10px 0;
            ">
                <h3 style="margin-top: 0; color: #533f03;">{analysis_type}结果 (模拟)</h3>
                <div>
                <p>这是对"{title}"的{analysis_type}。</p>
                    <p style="color: #721c24;">由于 LLM 未配置，这是一个模拟结果。</p>
                    <div style="
                        background-color: #ffffff;
                        padding: 15px;
                        border-radius: 4px;
                        margin-top: 10px;
                    ">
                        请完成以下设置以获取真实分析：
                        <ul style="margin: 10px 0; padding-left: 20px;">
                            <li>检查环境变量配置</li>
                            <li>在设置中选择有效的LLM配置</li>
                        </ul>
                    </div>
                </div>
        </div>
        '''

    @staticmethod
    def extract_metrics_from_content(content: str) -> Dict[str, Any]:
        """从分析内容中提取指标
        
        Args:
            content: 分析内容
            
        Returns:
            包含提取指标的字典
        """
        result = {
            'importance': None,
            'stance': None
        }
        
        try:
            # 提取重要程度
            importance_pattern = r'重要[程度性][:：]\s*(\d+(?:\.\d+)?)'
            importance_match = re.search(importance_pattern, content)
            if importance_match:
                try:
                    result['importance'] = float(importance_match.group(1))
                except ValueError:
                    pass
                    
            # 提取立场
            stance_pattern = r'立场[:：]\s*([-+]?\d+(?:\.\d+)?)'
            stance_match = re.search(stance_pattern, content)
            if stance_match:
                try:
                    result['stance'] = float(stance_match.group(1))
                except ValueError:
                    pass
        except Exception as e:
            LLMResponseFormatter.logger.error(f"提取指标时出错: {e}", exc_info=True)
            
        return result