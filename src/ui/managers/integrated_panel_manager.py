# src/ui/managers/integrated_panel_manager.py
"""
新闻分析整合面板管理器

负责创建、显示和管理新闻分析整合面板，
整合新闻相似度分析、重要程度和立场分析功能，
并提供新闻自动分类功能。
"""

import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from src.core.app_service import AppService
from src.models import NewsArticle
from src.ui.integrated_analysis_panel import IntegratedAnalysisPanel


class IntegratedPanelManager(QObject):
    """新闻分析整合面板管理器"""
    
    def __init__(self, parent, app_service: AppService):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.managers.integrated_panel_manager')
        self.app_service = app_service
        self.window = parent  # 主窗口引用
        
        # 面板实例
        self.integrated_panel: Optional[IntegratedAnalysisPanel] = None
    
    def show_integrated_panel(self, news_article: Optional[NewsArticle] = None):
        """显示新闻分析整合面板
        
        Args:
            news_article: 要分析的新闻文章，如果为None则使用当前选中的新闻
        """
        self.logger.info("显示新闻分析整合面板")
        
        # 如果面板已存在，关闭它
        if self.integrated_panel and self.integrated_panel.isVisible():
            self.integrated_panel.close()
            self.integrated_panel = None
        
        # 创建新的面板实例
        try:
            # 确保服务实例有效
            if not self.app_service.storage:
                raise ValueError("存储服务不可用，无法加载新闻数据")
            if not self.app_service.llm_service:
                raise ValueError("LLM服务不可用，无法进行AI分析")
                
            self.integrated_panel = IntegratedAnalysisPanel(
                storage=self.app_service.storage,
                llm_service=self.app_service.llm_service,
                parent=self.window
            )
            
            # 连接信号
            self.integrated_panel.rejected_and_deleted.connect(self._on_panel_closed)
            self.integrated_panel.analysis_completed.connect(self._on_analysis_completed)
            
            # 显示面板
            self.integrated_panel.show()
            
        except Exception as e:
            self.logger.error(f"创建新闻分析整合面板时出错: {e}", exc_info=True)
            QMessageBox.critical(self.window, "错误", f"无法创建新闻分析整合面板: {e}")
    
    @Slot()
    def _on_panel_closed(self):
        """处理面板关闭事件"""
        self.logger.debug("新闻分析整合面板已关闭")
        self.integrated_panel = None
    
    @Slot(dict)
    def _on_analysis_completed(self, result: dict):
        """处理分析完成事件
        
        Args:
            result: 分析结果
        """
        self.logger.info(f"收到分析完成信号，结果: {result}")
        # 可以在这里处理分析结果，例如更新主窗口的状态或显示通知