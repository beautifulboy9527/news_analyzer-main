# src/ui/managers/menu_prompt_manager.py
"""
提示词管理菜单集成

将提示词管理功能集成到主窗口菜单栏中，
提供全局访问提示词模板的能力。
"""

import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QMenu, QMessageBox
from PySide6.QtGui import QIcon, QAction

from src.llm.prompt_manager import PromptManager
from src.ui.managers.prompt_manager import PromptManagerService
from src.ui.managers.prompt_template_manager import PromptTemplateManager


class MenuPromptManager(QObject):
    """
    提示词管理菜单管理器，负责在主窗口菜单栏中集成提示词管理功能
    """
    
    def __init__(self, parent, prompt_manager: PromptManager):
        """
        初始化提示词管理菜单管理器
        
        Args:
            parent: 父对象（通常是主窗口）
            prompt_manager: 提示词管理器实例
        """
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.managers.menu_prompt_manager')
        self.window = parent  # 主窗口引用
        
        # 初始化提示词管理服务
        self.prompt_manager_service = PromptManagerService(prompt_manager)
    
    def _show_template_manager(self):
        """
        显示模板管理对话框
        """
        self.prompt_manager_service.show_template_manager_dialog(self.window)
    
    def get_prompt_manager_service(self) -> PromptManagerService:
        """
        获取提示词管理服务实例
        
        Returns:
            提示词管理服务实例
        """
        return self.prompt_manager_service