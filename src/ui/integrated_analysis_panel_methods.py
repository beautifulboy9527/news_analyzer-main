# src/ui/integrated_analysis_panel_methods.py
"""
新闻分析整合面板的提示词管理方法

实现与提示词管理组件的交互方法，支持动态调整分析提示词。
"""

import logging
from typing import Dict, Optional


def _on_analysis_type_changed(self, analysis_type: str):
    """
    当分析类型改变时，自动选择对应的提示词模板
    
    Args:
        analysis_type: 新的分析类型
    """
    self.logger.debug(f"分析类型已更改为: {analysis_type}")
    
    # 使用提示词管理组件的方法设置对应的模板
    if hasattr(self, 'prompt_manager_widget'):
        success = self.prompt_manager_widget.set_template_by_analysis_type(analysis_type)
        if not success:
            self.logger.warning(f"未找到与分析类型 '{analysis_type}' 对应的提示词模板")


def _on_prompt_selected(self, template_name: str, template_content: str):
    """
    当用户选择提示词模板时触发
    
    Args:
        template_name: 模板名称
        template_content: 模板内容
    """
    self.logger.debug(f"已选择提示词模板: {template_name}")
    
    # 存储当前选择的模板信息，以便在分析时使用
    self.current_template_name = template_name
    self.current_template_content = template_content
    
    # 如果已有分析结果，可以考虑使用新模板重新分析
    if self.result_edit.toPlainText() and self.selected_news_items:
        # 这里可以添加一个询问是否要使用新模板重新分析的对话框
        pass


def _on_prompt_edited(self, edited_content: str):
    """
    当用户编辑提示词内容时触发
    
    Args:
        edited_content: 编辑后的提示词内容
    """
    self.logger.debug("提示词内容已被编辑")
    
    # 更新当前模板内容
    self.current_template_content = edited_content
    
    # 如果已有分析结果，可以考虑使用编辑后的提示词重新分析
    # 但通常不会自动触发重新分析，而是等待用户点击分析按钮