# src/ui/managers/classification_panel_manager.py
"""
信息分类与整理核查面板管理器

负责创建、显示和管理信息分类与整理核查面板，
协调新闻事件聚类、分类展示和LLM分析功能。
"""

import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from src.core.app_service import AppService
from src.ui.classification_panel import ClassificationPanel


class ClassificationPanelManager(QObject):
    """信息分类与整理核查面板管理器"""
    
    def __init__(self, parent, app_service: AppService):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.managers.classification_panel_manager')
        self.app_service = app_service
        self.window = parent  # 主窗口引用
        
        # 面板实例
        self.classification_panel: Optional[ClassificationPanel] = None
    
    def show_classification_panel(self):
        """显示信息分类与整理核查面板"""
        self.logger.info("显示信息分类与整理核查面板")
        
        # 如果面板已存在，关闭它
        if self.classification_panel and self.classification_panel.isVisible():
            self.classification_panel.close()
            self.classification_panel = None
        
        # 创建新的面板实例
        try:
            self.classification_panel = ClassificationPanel(
                storage=self.app_service.storage,
                llm_service=self.app_service.llm_service,
                prompt_manager=self.app_service.prompt_manager,
                parent=self.window
            )
            
            # 连接信号
            self.classification_panel.analysis_completed.connect(self._on_analysis_completed)
            self.classification_panel.status_message.connect(self._on_status_message)
            self.classification_panel.token_usage_updated.connect(self._on_token_usage_updated)
            
            # 显示面板
            self.classification_panel.show()
            
        except Exception as e:
            self.logger.error(f"创建信息分类与整理核查面板时出错: {e}", exc_info=True)
            QMessageBox.critical(self.window, "错误", f"无法创建信息分类与整理核查面板: {e}")
    
    @Slot(dict)
    def _on_analysis_completed(self, result: dict):
        """处理分析完成事件
        
        Args:
            result: 分析结果
        """
        self.logger.info(f"收到分析完成信号，结果: {result}")
        # 可以在这里处理分析结果，例如更新主窗口的状态或显示通知
    
    @Slot(str)
    def _on_status_message(self, message: str):
        """处理状态消息事件
        
        Args:
            message: 状态消息
        """
        self.logger.debug(f"收到状态消息: {message}")
        # 可以在这里更新主窗口的状态栏
        if hasattr(self.window, 'statusBar'):
            self.window.statusBar().showMessage(message, 5000)  # 显示5秒
    
    @Slot(int)
    def _on_token_usage_updated(self, tokens: int):
        """处理Token使用量更新事件
        
        Args:
            tokens: 使用的Token数量
        """
        self.logger.debug(f"收到Token使用量更新: {tokens}")
        # 可以在这里更新Token使用量统计