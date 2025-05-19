# src/processors/event_analyzer.py
"""
事件分析器模块

负责对新闻事件进行LLM分析，包括重要性评估、立场分析和事实与观点分离。
支持自定义Prompt进行个性化分析。
"""

import logging
import json
from typing import Dict, List, Any, Optional, Union

from src.llm.llm_service import LLMService
from src.llm.prompt_manager import PromptManager


class EventAnalyzer:
    """事件分析器，使用LLM对新闻事件进行分析"""
    
    def __init__(self, llm_service: LLMService = None, prompt_manager: PromptManager = None):
        """初始化事件分析器
        
        Args:
            llm_service: LLM服务实例
            prompt_manager: Prompt管理器实例
        """
        self.logger = logging.getLogger('news_analyzer.processors.event_analyzer')
        self.llm_service = llm_service
        self.prompt_manager = prompt_manager
    
    def analyze(self, event: Dict, custom_prompt: Optional[str] = None) -> Dict[str, Any]:
        """分析事件
        
        Args:
            event: 事件数据字典
            custom_prompt: 自定义Prompt，如果为None则使用默认Prompt
            
        Returns:
            分析结果字典
        """
        if not self.llm_service or not self.prompt_manager:
            self.logger.error("LLM服务或Prompt管理器未初始化，无法进行分析")
            return {"error": "分析服务未初始化"}
        
        try:
            results = {}
            
            if custom_prompt:
                # 使用自定义Prompt进行分析
                self.logger.info("使用自定义Prompt进行分析")
                results["custom"] = self._analyze_with_custom_prompt(event, custom_prompt)
            else:
                # 使用默认Prompt进行标准分析
                self.logger.info("使用默认Prompt进行标准分析")
                
                # 重要性分析
                results["importance"] = self._analyze_importance(event)
                
                # 立场分析
                results["stance"] = self._analyze_stance(event)
                
                # 事实与观点分析
                results["facts_opinions"] = self._analyze_facts_opinions(event)
            
            return results
            
        except Exception as e:
            self.logger.error(f"分析事件时出错: {e}", exc_info=True)
            return {"error": f"分析失败: {str(e)}"}
    
    def _analyze_importance(self, event: Dict) -> Dict[str, Any]:
        """分析事件重要性
        
        Args:
            event: 事件数据字典
            
        Returns:
            重要性分析结果
        """
        try:
            # 获取重要性分析的Prompt
            prompt = self.prompt_manager.load_template("importance")
            if not prompt:
                self.logger.warning("未找到重要性分析的Prompt模板，使用默认Prompt")
                prompt = "评估以下事件的重要性（头条:5,重要:3,一般:1）。输出JSON：{'importance': score}。输入：{summary}"
            
            # 准备输入数据
            input_data = {"summary": event.get("title", "") + "\n" + event.get("summary", "")}
            
            # 调用LLM服务
            response = self.llm_service.call_llm(prompt, input_data)
            
            # 解析响应
            if isinstance(response, str):
                try:
                    response = json.loads(response)
                except json.JSONDecodeError:
                    # 如果响应不是有效的JSON，尝试提取数字
                    import re
                    match = re.search(r'\d+', response)
                    if match:
                        return {"importance": int(match.group())}
                    else:
                        return {"importance": 0, "raw_response": response}
            
            return response if isinstance(response, dict) else {"importance": 0, "raw_response": response}
            
        except Exception as e:
            self.logger.error(f"分析重要性时出错: {e}", exc_info=True)
            return {"importance": 0, "error": str(e)}
    
    def _analyze_stance(self, event: Dict) -> Dict[str, Any]:
        """分析事件立场
        
        Args:
            event: 事件数据字典
            
        Returns:
            立场分析结果
        """
        try:
            # 获取立场分析的Prompt
            prompt = self.prompt_manager.load_template("stance")
            if not prompt:
                self.logger.warning("未找到立场分析的Prompt模板，使用默认Prompt")
                prompt = "分析以下事件报道的立场（如亲欧盟、中立）。输出JSON：{'stances': []}。输入：{reports}"
            
            # 准备输入数据
            reports_text = ""
            for i, report in enumerate(event.get("reports", [])):
                source = report.get("source_name", "未知来源")
                title = report.get("title", "无标题")
                content_preview = report.get("content", "")[:200] + "..." if len(report.get("content", "")) > 200 else report.get("content", "")
                reports_text += f"报道{i+1}（{source}）：{title}\n{content_preview}\n\n"
            
            input_data = {"reports": reports_text}
            
            # 调用LLM服务
            response = self.llm_service.call_llm(prompt, input_data)
            
            # 解析响应
            if isinstance(response, str):
                try:
                    response = json.loads(response)
                except json.JSONDecodeError:
                    return {"stances": [], "raw_response": response}
            
            return response if isinstance(response, dict) else {"stances": [], "raw_response": response}
            
        except Exception as e:
            self.logger.error(f"分析立场时出错: {e}", exc_info=True)
            return {"stances": [], "error": str(e)}
    
    def _analyze_facts_opinions(self, event: Dict) -> Dict[str, Any]:
        """分析事件中的事实与观点
        
        Args:
            event: 事件数据字典
            
        Returns:
            事实与观点分析结果
        """
        try:
            # 获取事实与观点分析的Prompt
            prompt = self.prompt_manager.load_template("fact_opinion")
            if not prompt:
                self.logger.warning("未找到事实与观点分析的Prompt模板，使用默认Prompt")
                prompt = "分离以下事件报道中的事实和观点。输出JSON：{'facts': [], 'opinions': []}。输入：{reports}"
            
            # 准备输入数据
            reports_text = ""
            for i, report in enumerate(event.get("reports", [])):
                source = report.get("source_name", "未知来源")
                content = report.get("content", "")
                reports_text += f"报道{i+1}（{source}）：{content}\n\n"
            
            input_data = {"reports": reports_text}
            
            # 调用LLM服务
            response = self.llm_service.call_llm(prompt, input_data)
            
            # 解析响应
            if isinstance(response, str):
                try:
                    response = json.loads(response)
                except json.JSONDecodeError:
                    return {"facts": [], "opinions": [], "raw_response": response}
            
            return response if isinstance(response, dict) else {"facts": [], "opinions": [], "raw_response": response}
            
        except Exception as e:
            self.logger.error(f"分析事实与观点时出错: {e}", exc_info=True)
            return {"facts": [], "opinions": [], "error": str(e)}
    
    def _analyze_with_custom_prompt(self, event: Dict, custom_prompt: str) -> Dict[str, Any]:
        """使用自定义Prompt进行分析
        
        Args:
            event: 事件数据字典
            custom_prompt: 自定义Prompt
            
        Returns:
            分析结果
        """
        try:
            # 准备输入数据
            input_data = {
                "title": event.get("title", ""),
                "summary": event.get("summary", ""),
                "keywords": event.get("keywords", []),
                "category": event.get("category", ""),
                "reports": event.get("reports", []),
                "sources": event.get("sources", [])
            }
            
            # 调用LLM服务
            response = self.llm_service.call_llm(custom_prompt, input_data)
            
            # 解析响应
            if isinstance(response, str):
                try:
                    response = json.loads(response)
                    return response
                except json.JSONDecodeError:
                    return {"result": response}
            
            return response if isinstance(response, dict) else {"result": response}
            
        except Exception as e:
            self.logger.error(f"使用自定义Prompt分析时出错: {e}", exc_info=True)
            return {"error": str(e)}