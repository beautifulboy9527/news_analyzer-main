# src/ui/integrated_analysis_panel_modular.py
"""
新闻分析整合面板（模块化版本）

整合新闻相似度分析、重要程度和立场分析功能，
并提供新闻自动分类功能，支持按类别分组查看和分析新闻。
采用模块化设计，提高代码可维护性。
"""

import logging
from typing import List, Dict, Optional

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
                             QMessageBox, QWidget, QProgressBar, QComboBox,
                             QTabWidget, QLabel, QPushButton)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from src.models import NewsArticle
from src.llm.llm_service import LLMService
from src.storage.news_storage import NewsStorage
from src.ui.components.analysis_visualizer import AnalysisVisualizer

# 导入模块化组件
from src.ui.components.analysis_panel_components import (
    NewsListManager, CategoryTreeManager, GroupTreeManager
)
from src.ui.integrated_analysis_panel_prompt_manager import PromptManagerWidget

# 导入面板模块
from src.ui.modules.analysis_panel_ui_builder import AnalysisPanelUIBuilder
from src.ui.modules.analysis_panel_event_handler import AnalysisPanelEventHandler
from src.ui.modules.analysis_panel_data_manager import AnalysisPanelDataManager


class IntegratedAnalysisPanel(QDialog):
    """新闻分析整合面板，集成相似度分析、重要程度和立场分析，并支持自动分类"""
    
    # 定义信号
    rejected_and_deleted = Signal()
    analysis_completed = Signal(dict)
    
    def __init__(self, storage: NewsStorage, llm_service: LLMService, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新闻分析整合面板")
        self.setMinimumSize(1000, 700)
        
        # 设置窗口标志，移除问号按钮，添加最大化按钮
        flags = self.windowFlags()
        flags &= ~Qt.WindowContextHelpButtonHint
        flags |= Qt.WindowMaximizeButtonHint
        self.setWindowFlags(flags)
        
        self.logger = logging.getLogger('news_analyzer.ui.integrated_analysis')
        
        # 验证传入的服务实例
        if not storage or not isinstance(storage, NewsStorage):
            self.logger.error("传入的 storage 无效！新闻分析功能将无法使用。")
            QMessageBox.critical(self, "错误", "存储服务不可用，无法加载新闻数据。")
            self.storage = None
        else:
            self.storage = storage
            
        if not llm_service or not isinstance(llm_service, LLMService):
            self.logger.error("传入的 llm_service 无效！AI分析功能将无法使用。")
            QMessageBox.critical(self, "错误", "LLM服务不可用，无法进行AI分析。")
            self.llm_service = None
        else:
            self.llm_service = llm_service
        
        # 初始化模块化组件
        self.data_manager = AnalysisPanelDataManager()
        self.ui_builder = None  # 将在_init_ui中初始化
        self.event_handler = None  # 将在_init_ui中初始化
        
        # 初始化UI
        self._init_ui()
        
        # 加载新闻数据
        if self.storage:
            self._load_news_data()
    
    def _init_ui(self):
        """初始化UI布局和控件"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建UI构建器
        self.ui_builder = AnalysisPanelUIBuilder(self)
        
        # 构建顶部控制区域
        control_layout = self.ui_builder.build_control_area()
        layout.addLayout(control_layout)
        
        # 添加进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 构建主体区域
        main_splitter = QSplitter(Qt.Horizontal)
        
        # 构建左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 构建左侧分类树和新闻列表
        left_splitter = self.ui_builder.build_left_panel(left_layout)
        left_layout.addWidget(left_splitter)
        
        # 构建右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 构建右侧分析结果区域
        self.ui_builder.build_right_panel(right_layout)
        
        # 添加左右面板到主分割器
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([400, 600])  # 设置初始大小比例
        
        layout.addWidget(main_splitter)
        
        # 底部按钮区域
        bottom_layout = self.ui_builder.build_bottom_area()
        layout.addLayout(bottom_layout)
        
        # 创建事件处理器并连接信号
        self.event_handler = AnalysisPanelEventHandler(
            self, self.data_manager, self.storage, self.llm_service
        )
        self.event_handler.connect_signals()
    
    def _load_news_data(self):
        """加载新闻数据"""
        self.event_handler.load_news_data()
    
    def closeEvent(self, event):
        """处理窗口关闭事件"""
        self.rejected_and_deleted.emit()
        event.accept()