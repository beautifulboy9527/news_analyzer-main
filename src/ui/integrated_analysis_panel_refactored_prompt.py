# src/ui/integrated_analysis_panel_refactored_prompt.py
"""
新闻分析整合面板（提示词管理模块化版本）

整合新闻相似度分析、重要程度和立场分析功能，
并提供新闻自动分类功能，支持按类别分组查看和分析新闻。
使用模块化的提示词管理组件，提高代码的可维护性和复用性。
"""

import logging
import re
import os
import time
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QLabel, QTextEdit, QPushButton,
                             QSplitter, QMessageBox, QSizePolicy, QWidget,
                             QCheckBox, QGroupBox, QProgressBar, QComboBox,
                             QTabWidget, QTreeWidget, QTreeWidgetItem, QMenu,
                             QHeaderView)
from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtGui import QIcon, QFont, QAction, QCursor, QColor

from src.models import NewsArticle
from src.llm.llm_service import LLMService
from src.storage.news_storage import NewsStorage
from src.collectors.categories import STANDARD_CATEGORIES
from src.ui.components.analysis_visualizer import AnalysisVisualizer
from src.core.enhanced_news_clusterer import EnhancedNewsClusterer

# 导入模块化的提示词管理组件
from src.ui.components.prompt_manager_widget import PromptManagerWidget
from src.ui.managers.prompt_manager import PromptManagerService


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
        
        # 初始化数据
        self.all_news_items: List[Dict] = []
        self.selected_news_items: List[Dict] = []
        self.news_groups: List[List[Dict]] = []  # 存储分组后的新闻
        self.categorized_news: Dict[str, List[Dict]] = {}  # 按类别分类的新闻
        self.current_category = ""  # 当前选中的类别
        self.current_group_items = []  # 当前组内的新闻项
        self.analysis_results: Dict[str, Dict] = {}  # 存储分析结果，键为新闻组ID
        
        # 提示词管理相关
        self.current_template_name = ""  # 当前选择的提示词模板名称
        self.current_template_content = ""  # 当前选择的提示词模板内容
        
        # 初始化提示词管理服务
        self.prompt_manager_service = PromptManagerService(self.llm_service.prompt_manager)
        
        # 初始化UI
        self._init_ui()
        
        # 加载新闻数据
        if self.storage:
            self._load_news_data()
    
    # ... 其他方法保持不变 ...
    
    def _init_right_panel(self, right_panel):
        """初始化右侧面板"""
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 添加模块化的提示词管理组件
        self.prompt_manager_widget = PromptManagerWidget(self.prompt_manager_service)
        self.prompt_manager_widget.prompt_selected.connect(self._on_prompt_selected)
        self.prompt_manager_widget.prompt_edited.connect(self._on_prompt_edited)
        self.prompt_manager_widget.prompt_applied.connect(self._on_prompt_applied)
        right_layout.addWidget(self.prompt_manager_widget)
        
        # 分析结果标签和说明
        result_header_layout = QVBoxLayout()
        result_title_label = QLabel("分析结果:")
        result_title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        result_header_layout.addWidget(result_title_label)
        
        result_info_label = QLabel("AI分析结果将在此显示，包括重要程度和立场分析")
        result_info_label.setStyleSheet("color: #666666; font-size: 12px;")
        result_header_layout.addWidget(result_info_label)
        right_layout.addLayout(result_header_layout)
        
        # 添加重要程度和立场识别的可视化区域
        self.analysis_visualizer = AnalysisVisualizer()
        self.analysis_visualizer.setStyleSheet("""
            QWidget { 
                background-color: #F9F9F9; 
                border: 1px solid #E0E0E0; 
                border-radius: 6px; 
                padding: 10px;
            }
        """)
        right_layout.addWidget(self.analysis_visualizer)
        
        # 分析结果文本编辑框
        self.result_edit = QTextEdit()
        self.result_edit.setStyleSheet("""
            QTextEdit { 
                border: 1px solid #C4C4C4; 
                border-radius: 4px; 
                padding: 8px; 
                background-color: #FFFFFF;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        self.result_edit.setPlaceholderText("请在左侧选择新闻并点击'开始分析'按钮进行AI分析和整合")
        right_layout.addWidget(self.result_edit)
    
    def _on_prompt_selected(self, template_name: str, template_content: str):
        """当选择提示词模板时"""
        self.current_template_name = template_name
        self.current_template_content = template_content
        self.logger.debug(f"已选择提示词模板: {template_name}")
    
    def _on_prompt_edited(self, content: str):
        """当提示词内容被编辑时"""
        self.current_template_content = content
    
    def _on_prompt_applied(self, template_name: str, template_content: str):
        """当应用提示词模板时"""
        self.current_template_name = template_name
        self.current_template_content = template_content
        self.logger.debug(f"已应用提示词模板: {template_name}")
        
        # 可以在这里添加应用模板后的额外逻辑，例如自动开始分析
        if self.selected_news_items and self.analyze_button.isEnabled():
            # 可选：自动开始分析
            # self._analyze_selected_news()
            pass

# 使用说明：
# 1. 此文件实现了提示词管理模块化，将提示词管理功能从主面板中分离出来
# 2. 使用src.ui.components.prompt_manager_widget和src.ui.managers.prompt_manager模块
# 3. 要完全集成此功能，需要将此文件中的方法合并到integrated_analysis_panel.py中
# 4. 主要修改点：
#    - 导入新的模块化组件
#    - 初始化提示词管理服务
#    - 使用模块化的提示词管理组件替换原有实现
#    - 添加_on_prompt_applied方法处理应用模板事件