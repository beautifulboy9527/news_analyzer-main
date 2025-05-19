# src/ui/integrated_analysis_panel_simplified.py
"""
新闻分析整合面板（简化版）

整合新闻分析功能，提供清晰的用户界面和工作流程，
简化操作逻辑，提升用户体验。
移除了冗余的类别选择功能，专注于核心分析流程。
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QLabel, QTextEdit, QPushButton,
                             QSplitter, QMessageBox, QWidget, QProgressBar, 
                             QComboBox, QTabWidget, QHeaderView, QFrame, 
                             QToolTip, QMenu, QLineEdit)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QFont, QAction, QCursor

from src.models import NewsArticle
from src.llm.llm_service import LLMService
from src.storage.news_storage import NewsStorage


class IntegratedAnalysisPanel(QDialog):
    """新闻分析整合面板，提供简化的用户界面和工作流程"""
    
    # 定义信号
    rejected_and_deleted = Signal()
    analysis_completed = Signal(dict)
    
    def __init__(self, storage: NewsStorage, llm_service: LLMService, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新闻分析工具")
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
        self.current_group_items = []  # 当前组内的新闻项
        self.analysis_results: Dict[str, Dict] = {}  # 存储分析结果，键为新闻组ID
        
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
        
        # --- 顶部说明区域 ---
        self._create_header_section(layout)
        
        # --- 进度条 ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # --- 主体区域 ---
        main_splitter = QSplitter(Qt.Horizontal)
        
        # 左侧新闻选择区域
        left_panel = self._create_left_panel()
        
        # 右侧分析区域
        right_panel = self._create_right_panel()
        
        # 添加左右面板到主分割器
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([400, 600])  # 设置初始大小比例
        
        layout.addWidget(main_splitter, 1)  # 添加拉伸因子，使主体区域占据大部分空间
        
        # --- 底部按钮区域 ---
        self._create_bottom_section(layout)
    
    def _create_header_section(self, layout):
        """创建顶部说明区域"""
        header_frame = QFrame()
        header_frame.setFrameShape(QFrame.StyledPanel)
        header_frame.setStyleSheet("""
            QFrame { 
                background-color: #E3F2FD; 
                border: 1px solid #90CAF9; 
                border-radius: 4px; 
                padding: 10px;
            }
        """)
        
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        # 标题和说明
        title_label = QLabel("新闻分析工具")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1565C0;")
        header_layout.addWidget(title_label)
        
        desc_label = QLabel("本工具帮助您分析新闻内容，找出相似新闻并进行AI分析。")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #333; margin-top: 5px; font-size: 13px;")
        header_layout.addWidget(desc_label)
        
        # 使用步骤说明
        steps_label = QLabel("使用步骤：")
        steps_label.setStyleSheet("font-weight: bold; margin-top: 5px; color: #333;")
        header_layout.addWidget(steps_label)
        
        steps_text = QLabel("1. 从左侧新闻列表中选择要分析的新闻\n2. 使用搜索框筛选感兴趣的新闻\n3. 在右侧选择分析类型\n4. 点击