"""
LLM 响应格式化工具
"""
from typing import Dict, Any

class LLMResponseFormatter:
    """
    提供将 LLM 响应或错误格式化为 HTML 的静态方法。
    """

    @staticmethod
    def format_analysis_result(content: str, analysis_type: str) -> str:
        """格式化分析结果为HTML"""
        # 使用更安全的 HTML 转义可能更好，但暂时保持原样
        # import html
        # escaped_content = html.escape(content)
        formatted_content = content.replace('\n\n', '</p><p>').replace('\n- ', '</p><li>').replace('\n', '<br>')
        html = f'''
        <div style="font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; padding: 15px; line-height: 1.5;">
            <h2 style="color: #1976D2; border-bottom: 1px solid #E0E0E0; padding-bottom: 8px;">{analysis_type}结果</h2>
            <div style="padding: 10px 0;">
                {formatted_content}
            </div>
        </div>
        '''
        return html

    @staticmethod
    def format_error_html(error_message: str) -> str:
         """格式化错误信息为HTML"""
         # import html
         # escaped_message = html.escape(error_message)
         return f"""
         <div style="color: #d32f2f; font-weight: bold; padding: 10px;">
             处理失败: {error_message}
         </div>
         <div style="padding: 0 10px 10px 10px;">
             请检查环境变量设置、网络连接或 LLM 服务状态。
         </div>
         """

    @staticmethod
    def mock_analysis(news_item: Dict[str, Any], analysis_type: str) -> str:
        """生成模拟分析结果的HTML（当未配置时）"""
        # news_item 预期是字典
        title = news_item.get('title', '无标题')
        return f'''
        <div style="font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; padding: 15px; line-height: 1.5;">
            <h2 style="color: #1976D2; border-bottom: 1px solid #E0E0E0; padding-bottom: 8px;">{analysis_type}结果</h2>
            <div style="padding: 10px 0;">
                <p>这是对"{title}"的{analysis_type}。</p>
                <p style="color: #F44336;">由于 LLM 未配置，这是一个模拟结果。请检查环境变量或在设置中选择有效的配置以获取真实分析。</p>
            </div>
        </div>
        '''