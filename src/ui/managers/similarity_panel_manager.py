# src/ui/managers/similarity_panel_manager.py
"""
新闻相似度分析面板管理器

负责创建、显示和管理新闻相似度分析面板。
"""

import logging
from typing import Optional

from PySide6.QtCore import QObject

from src.core.app_service import AppService
from src.ui.news_similarity_panel import NewsSimilarityPanel


class SimilarityPanelManager(QObject):
    """新闻相似度分析面板管理器"""
    
    def __init__(self, parent, app_service: AppService):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.managers.similarity_panel_manager')
        self.app_service = app_service
        self.window = parent  # 主窗口引用
        
        # 面板实例
        self.similarity_panel: Optional[NewsSimilarityPanel] = None
    
    def get_panel(self) -> NewsSimilarityPanel:
        """获取或创建新闻相似度分析面板实例。"""
        if self.similarity_panel is None:
            self.logger.info("Creating NewsSimilarityPanel instance via get_panel().")
            # 创建新的面板实例
            self.similarity_panel = NewsSimilarityPanel(
                app_service=self.app_service,
                parent=self.window
            )
            # 连接信号
            self.similarity_panel.rejected_and_deleted.connect(self._on_panel_closed)
        return self.similarity_panel

    def show_similarity_panel(self):
        """显示新闻相似度分析面板"""
        panel = self.get_panel() # Use get_panel to ensure it exists
        self.logger.info("显示新闻相似度分析面板")
        
        # 如果面板已存在，激活它
        if panel.isVisible():
            panel.raise_()
            panel.activateWindow()
            return
        
        # 显示面板
        panel.show()
    
    def _on_panel_closed(self):
        """处理面板关闭事件"""
        self.logger.debug("新闻相似度分析面板已关闭")
        self.similarity_panel = None