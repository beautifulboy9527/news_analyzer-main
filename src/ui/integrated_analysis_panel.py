# src/ui/integrated_analysis_panel.py
"""
新闻分析整合面板

整合新闻相似度分析、重要程度和立场分析功能，
并提供新闻自动分类功能，支持按类别分组查看和分析新闻。
"""

import logging
import re
import os
import time
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
import markdown # +++ NEW IMPORT +++

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QLabel, QTextEdit, QPushButton,
                             QSplitter, QMessageBox, QSizePolicy, QWidget,
                             QCheckBox, QGroupBox, QProgressBar, QComboBox,
                             QTabWidget, QTreeWidget, QTreeWidgetItem, QMenu,
                             QHeaderView, QApplication)
from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtGui import QIcon, QFont, QAction, QCursor, QColor

from src.models import NewsArticle
from src.llm.llm_service import LLMService
from src.storage.news_storage import NewsStorage
from src.collectors.categories import STANDARD_CATEGORIES, get_category_name as get_display_category_name_from_collector # IMPORT HELPER
# from src.ui.components.analysis_visualizer import AnalysisVisualizer # Remove old import
from src.ui.views.advanced_analysis_visualizer import AdvancedAnalysisVisualizer # CORRECTED PATH
from src.core.enhanced_news_clusterer import EnhancedNewsClusterer
# Removed PromptManagerWidget import


class IntegratedAnalysisPanel(QDialog):
    """新闻分析整合面板，集成相似度分析、重要程度和立场分析，并支持自动分类"""
    
    # 定义信号
    rejected_and_deleted = Signal()
    analysis_completed = Signal(dict)
    
    def __init__(self, storage: NewsStorage, llm_service: LLMService, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新闻分析整合面板")
        self.setMinimumSize(1000, 700)
        
        # 设置窗口标志，确保最小化、最大化和关闭按钮可用
        flags = self.windowFlags()
        flags &= ~Qt.WindowContextHelpButtonHint  # 移除帮助按钮 (？)
        flags |= Qt.WindowMinMaxButtonsHint     # 添加最小化和最大化按钮
        flags |= Qt.WindowCloseButtonHint       # 添加关闭按钮 (X)
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
        
        # 初始化UI
        self._init_ui()
        
        # 连接信号到槽
        # Ensure this connection is robustly made and logged.
        try:
            self.analysis_completed.disconnect(self._on_analysis_completed) # Attempt to disconnect first to avoid duplicates if any
            self.logger.info("Attempted to disconnect existing analysis_completed to _on_analysis_completed.")
        except RuntimeError: # disconnect throws RuntimeError if not connected
            self.logger.info("No existing analysis_completed to _on_analysis_completed connection to disconnect.")
            pass # No problem if it wasn't connected

        self.analysis_completed.connect(self._on_analysis_completed)
        self.logger.critical("--- PANEL INIT SUCCESS: analysis_completed SIGNAL CONNECTED to self._on_analysis_completed ---") # VERY CLEAR LOG
        
        # 加载新闻数据
        if self.storage:
            self._load_news_data()
    
    def _init_ui(self):
        """初始化UI布局和控件"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # --- 顶部控制区域 ---
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)
        
        # 刷新按钮
        self.refresh_button = QPushButton(QIcon.fromTheme("view-refresh", QIcon("")), " 刷新新闻")
        self.refresh_button.setToolTip("重新加载新闻数据")
        self.refresh_button.setStyleSheet("""
            QPushButton { 
                background-color: #F0F0F0; 
                border: 1px solid #C0C0C0; 
                border-radius: 4px; 
                padding: 6px 12px; 
                font-weight: bold;
            }
            QPushButton:hover { 
                background-color: #E0E0E0;
            }
            QPushButton:pressed { 
                background-color: #D0D0D0;
            }
        """)
        self.refresh_button.clicked.connect(self._load_news_data)
        control_layout.addWidget(self.refresh_button)
        
        # 分析类型选择 - 整合为一个选项
        type_label = QLabel("分析类型:")
        type_label.setStyleSheet("font-weight: bold;")
        control_layout.addWidget(type_label)
        
        self.analysis_type = QComboBox()
        self.analysis_type.addItem("新闻相似度分析")
        self.analysis_type.addItem("增强型多特征分析")
        self.analysis_type.addItem("重要程度和立场分析")
        self.analysis_type.addItem("深度分析")
        self.analysis_type.addItem("关键观点")
        self.analysis_type.addItem("事实核查")
        self.analysis_type.addItem("摘要")
        self.analysis_type.currentTextChanged.connect(self._on_analysis_type_changed)
        self.analysis_type.setStyleSheet("""
            QComboBox { 
                border: 1px solid #C0C0C0; 
                border-radius: 4px; 
                padding: 5px; 
                min-width: 150px;
            }
            QComboBox::drop-down { 
                subcontrol-origin: padding; 
                subcontrol-position: top right; 
                width: 20px; 
                border-left: 1px solid #C0C0C0;
            }
        """)
        control_layout.addWidget(self.analysis_type)
        
        # 分类方法选择
        method_label = QLabel("分类方法:")
        method_label.setStyleSheet("font-weight: bold;")
        control_layout.addWidget(method_label)
        
        self.clustering_method = QComboBox()
        self.clustering_method.addItem("标题相似度", "title_similarity")
        self.clustering_method.addItem("多特征融合", "multi_feature")
        self.clustering_method.setStyleSheet("""
            QComboBox { 
                border: 1px solid #C0C0C0; 
                border-radius: 4px; 
                padding: 5px; 
                min-width: 150px;
            }
            QComboBox::drop-down { 
                subcontrol-origin: padding; 
                subcontrol-position: top right; 
                width: 20px; 
                border-left: 1px solid #C0C0C0;
            }
        """)
        self.clustering_method.setToolTip("选择新闻分类方法：标题相似度(基础)或多特征融合(更精确)")
        control_layout.addWidget(self.clustering_method)
        
        control_layout.addStretch()
        
        # 分析按钮
        self.analyze_button = QPushButton(QIcon.fromTheme("system-run", QIcon("")), " 开始分析")
        self.analyze_button.setToolTip("对选中的新闻进行AI分析和整合")
        self.analyze_button.setStyleSheet("""
            QPushButton { 
                background-color: #4CAF50; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                padding: 8px 16px; 
                font-weight: bold;
            }
            QPushButton:hover { 
                background-color: #45a049;
            }
            QPushButton:pressed { 
                background-color: #3d8b40;
            }
            QPushButton:disabled { 
                background-color: #CCCCCC; 
                color: #666666;
            }
        """)
        self.analyze_button.clicked.connect(self._analyze_selected_news)
        self.analyze_button.setEnabled(False)  # 初始禁用
        control_layout.addWidget(self.analyze_button)
        
        layout.addLayout(control_layout)
        
        # --- 进度条 ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # --- 主体区域 ---
        main_splitter = QSplitter(Qt.Horizontal)
        
        # 左侧分类树和新闻列表区域
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建左侧分割器（分类树和新闻列表）
        left_splitter = QSplitter(Qt.Vertical)
        
        # 分类树
        category_widget = QWidget()
        category_layout = QVBoxLayout(category_widget)
        category_layout.setContentsMargins(0, 0, 0, 0)
        
        # 添加更明显的标题和说明
        cat_header_layout = QVBoxLayout()
        cat_title_label = QLabel("新闻分类:")
        cat_title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        cat_header_layout.addWidget(cat_title_label)
        
        cat_info_label = QLabel("点击类别查看该类别下的新闻")
        cat_info_label.setStyleSheet("color: #666666; font-size: 12px;")
        cat_header_layout.addWidget(cat_info_label)
        category_layout.addLayout(cat_header_layout)
        
        self.category_tree = QTreeWidget()
        self.category_tree.setHeaderLabel("类别")
        self.category_tree.setMinimumHeight(150)
        self.category_tree.setStyleSheet("""
            QTreeWidget { 
                border: 1px solid #C4C4C4; 
                border-radius: 4px; 
                padding: 2px;
            }
            QTreeWidget::item { 
                padding: 6px 2px; 
            }
            QTreeWidget::item:selected { 
                background-color: #E3F2FD; 
                color: #000000;
            }
            QTreeWidget::item:hover { 
                background-color: #F5F5F5;
            }
        """)
        self.category_tree.itemClicked.connect(self._on_category_selected)
        category_layout.addWidget(self.category_tree)
        
        left_splitter.addWidget(category_widget)
        
        # 新闻列表区域
        news_list_widget = QWidget()
        news_list_layout = QVBoxLayout(news_list_widget)
        news_list_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建标签页控件，用于切换普通新闻列表和分组新闻列表
        self.news_tab = QTabWidget()
        self.news_tab.setStyleSheet("""
            QTabWidget::pane { 
                border: 1px solid #C4C4C4; 
                border-radius: 3px;
            }
            QTabBar::tab { 
                padding: 8px 12px; 
                margin-right: 2px; 
                border: 1px solid #C4C4C4;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected { 
                background-color: #f0f0f0; 
                font-weight: bold;
            }
        """)
        news_list_layout.addWidget(self.news_tab)
        
        # 普通新闻列表页
        normal_list_widget = QWidget()
        normal_list_layout = QVBoxLayout(normal_list_widget)
        normal_list_layout.setContentsMargins(8, 8, 8, 8)
        
        # 添加更明显的标题和说明
        header_layout = QVBoxLayout()
        title_label = QLabel("新闻列表:")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(title_label)
        
        info_label = QLabel("选择多条新闻进行分析，双击查看详情")
        info_label.setStyleSheet("color: #666666; font-size: 12px;")
        header_layout.addWidget(info_label)
        normal_list_layout.addLayout(header_layout)
        
        self.news_list = QListWidget()
        self.news_list.setAlternatingRowColors(True)
        self.news_list.setSelectionMode(QListWidget.ExtendedSelection)  # 允许多选
        self.news_list.setStyleSheet("""
            QListWidget { 
                border: 1px solid #C4C4C4; 
                border-radius: 4px; 
                padding: 2px;
            }
            QListWidget::item { 
                padding: 8px; 
                border-bottom: 1px solid #E0E0E0;
            }
            QListWidget::item:selected { 
                background-color: #E3F2FD; 
                color: #000000;
            }
            QListWidget::item:hover { 
                background-color: #F5F5F5;
            }
        """)
        self.news_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.news_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.news_list.customContextMenuRequested.connect(self._show_context_menu)
        normal_list_layout.addWidget(self.news_list)
        
        # 分组新闻列表页
        grouped_list_widget = QWidget()
        grouped_list_layout = QVBoxLayout(grouped_list_widget)
        grouped_list_layout.setContentsMargins(8, 8, 8, 8)
        
        # 添加更明显的标题和说明
        group_header_layout = QVBoxLayout()
        group_title_label = QLabel("新闻分组:")
        group_title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        group_header_layout.addWidget(group_title_label)
        
        group_info_label = QLabel("相似新闻已自动分组，双击组内新闻查看详情")
        group_info_label.setStyleSheet("color: #666666; font-size: 12px;")
        group_header_layout.addWidget(group_info_label)
        grouped_list_layout.addLayout(group_header_layout)
        
        # 分组树视图
        self.group_tree = QTreeWidget()
        self.group_tree.setHeaderLabels(["分组新闻", "来源数"])
        self.group_tree.setAlternatingRowColors(True)
        self.group_tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.group_tree.setStyleSheet("""
            QTreeWidget { 
                border: 1px solid #C4C4C4; 
                border-radius: 4px; 
                padding: 2px;
            }
            QTreeWidget::item { 
                padding: 6px 2px; 
                border-bottom: 1px solid #E0E0E0;
            }
            QTreeWidget::item:selected { 
                background-color: #E3F2FD; 
                color: #000000;
            }
            QTreeWidget::item:hover { 
                background-color: #F5F5F5;
            }
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {
                border-image: none;
                image: url(:/images/branch-closed.png);
            }
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {
                border-image: none;
                image: url(:/images/branch-open.png);
            }
        """)
        self.group_tree.itemSelectionChanged.connect(self._on_group_selection_changed)
        self.group_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.group_tree.customContextMenuRequested.connect(self._show_group_context_menu)
        self.group_tree.itemDoubleClicked.connect(self._on_group_item_double_clicked)
        # 设置列宽
        self.group_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.group_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        grouped_list_layout.addWidget(self.group_tree)
        
        # 添加标签页
        self.news_tab.addTab(normal_list_widget, "普通列表")
        self.news_tab.addTab(grouped_list_widget, "分组视图")
        self.news_tab.currentChanged.connect(self._on_tab_changed)
        
        # 选择操作按钮
        selection_layout = QHBoxLayout()
        selection_layout.setSpacing(10)
        
        button_style = """
            QPushButton { 
                background-color: #F0F0F0; 
                border: 1px solid #C0C0C0; 
                border-radius: 4px; 
                padding: 6px 12px;
            }
            QPushButton:hover { 
                background-color: #E0E0E0;
            }
            QPushButton:pressed { 
                background-color: #D0D0D0;
            }
        """
        
        self.select_all_button = QPushButton(QIcon.fromTheme("edit-select-all", QIcon("")), "全选")
        self.select_all_button.setStyleSheet(button_style)
        self.select_all_button.clicked.connect(self._select_all_news)
        selection_layout.addWidget(self.select_all_button)
        
        self.deselect_all_button = QPushButton(QIcon.fromTheme("edit-clear", QIcon("")), "取消全选")
        self.deselect_all_button.setStyleSheet(button_style)
        self.deselect_all_button.clicked.connect(self._deselect_all_news)
        selection_layout.addWidget(self.deselect_all_button)
        
        self.auto_group_button = QPushButton(QIcon.fromTheme("object-group", QIcon("")), "自动分组")
        self.auto_group_button.setStyleSheet("""
            QPushButton { 
                background-color: #2196F3; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                padding: 6px 12px; 
                font-weight: bold;
            }
            QPushButton:hover { 
                background-color: #0b7dda;
            }
            QPushButton:pressed { 
                background-color: #0a69b7;
            }
        """)
        self.auto_group_button.setToolTip("根据标题相似度自动分组相关新闻")
        self.auto_group_button.clicked.connect(self._auto_group_news)
        selection_layout.addWidget(self.auto_group_button)
        
        news_list_layout.addLayout(selection_layout)
        
        left_splitter.addWidget(news_list_widget)
        
        # 设置左侧分割器的初始大小
        left_splitter.setSizes([200, 400])
        
        left_layout.addWidget(left_splitter)
        
        # 右侧分析结果区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 提示词管理组件已移除
        
        # 分析结果标签和说明
        result_header_layout = QVBoxLayout()
        result_title_label = QLabel("分析结果:")
        result_title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        result_header_layout.addWidget(result_title_label)
        
        result_info_label = QLabel("AI分析结果将在此显示，包括重要程度和立场分析")
        result_info_label.setStyleSheet("color: #666666; font-size: 12px;")
        result_header_layout.addWidget(result_info_label)
        right_layout.addLayout(result_header_layout)
        
        # 添加重要程度和立场识别的可视化区域 (Now using Advanced Visualizer)
        self.analysis_visualizer = AdvancedAnalysisVisualizer()
        # Remove stylesheet application as AdvancedAnalysisVisualizer handles its own styling
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
        
        # 结果操作按钮
        result_action_layout = QHBoxLayout()
        result_action_layout.setSpacing(10)
        
        button_style = """
            QPushButton { 
                background-color: #F0F0F0; 
                border: 1px solid #C0C0C0; 
                border-radius: 4px; 
                padding: 6px 12px;
            }
            QPushButton:hover { 
                background-color: #E0E0E0;
            }
            QPushButton:pressed { 
                background-color: #D0D0D0;
            }
            QPushButton:disabled { 
                background-color: #F8F8F8; 
                color: #AAAAAA; 
                border: 1px solid #DDDDDD;
            }
        """
        
        self.copy_button = QPushButton(QIcon.fromTheme("edit-copy", QIcon("")), "复制结果")
        self.copy_button.setStyleSheet(button_style)
        self.copy_button.clicked.connect(self._copy_result)
        self.copy_button.setEnabled(False)
        result_action_layout.addWidget(self.copy_button)
        
        self.save_button = QPushButton(QIcon.fromTheme("document-save", QIcon("")), "保存结果")
        self.save_button.setStyleSheet(button_style)
        self.save_button.clicked.connect(self._save_result)
        self.save_button.setEnabled(False)
        result_action_layout.addWidget(self.save_button)
        
        self.clear_button = QPushButton(QIcon.fromTheme("edit-clear", QIcon("")), "清空结果")
        self.clear_button.setStyleSheet(button_style)
        self.clear_button.clicked.connect(self._clear_result)
        self.clear_button.setEnabled(False)
        result_action_layout.addWidget(self.clear_button)
        
        right_layout.addLayout(result_action_layout)
        
        # 添加左右面板到分割器
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        # 调整分割比例，增加右侧分析结果区域的大小
        main_splitter.setSizes([350, 650])
        # 设置拉伸因子，让右侧区域优先拉伸
        main_splitter.setStretchFactor(0, 1) # 左侧拉伸因子
        main_splitter.setStretchFactor(1, 2) # 右侧拉伸因子 (更大)
        
        layout.addWidget(main_splitter, 1)  # 1表示拉伸因子
        
        # --- 底部关闭按钮 (移除) ---
        # button_layout = QHBoxLayout()
        # button_layout.addStretch()
        # 
        # close_button = QPushButton("关闭")
        # close_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # close_button.setStyleSheet("""
        #     QPushButton { 
        #         background-color: #F0F0F0; 
        #         border: 1px solid #C0C0C0; 
        #         border-radius: 4px; 
        #         padding: 8px 16px; 
        #         font-weight: bold;
        #     }
        #     QPushButton:hover { 
        #         background-color: #E0E0E0;
        #     }
        #     QPushButton:pressed { 
        #         background-color: #D0D0D0;
        #     }
        # """)
        # close_button.clicked.connect(self.reject)
        # button_layout.addWidget(close_button)
        # 
        # layout.addLayout(button_layout)
        
        # 禁用控件（如果服务无效）
        if not self.storage or not self.llm_service:
            self.refresh_button.setEnabled(False)
            self.analyze_button.setEnabled(False)
            self.auto_group_button.setEnabled(False)
            self.news_list.setEnabled(False)
            self.category_tree.setEnabled(False)

    # --- Event Handlers ---

    def _on_analysis_type_changed(self, analysis_type: str):
        """
        当分析类型改变时触发。

        Args:
            analysis_type: 新的分析类型
        """
        self.logger.debug(f"分析类型已更改为: {analysis_type}")
        # 目前此方法仅记录更改，未来可以扩展以根据类型调整UI或行为
        pass
    
    def _load_news_data(self):
        """从存储加载新闻数据并进行自动分类"""
        if not self.storage:
            self.logger.warning("Storage 无效，无法加载新闻数据")
            return
        
        self.logger.info("开始加载新闻数据...")
        self.news_list.clear()
        self.category_tree.clear()
        self.all_news_items = []
        self.categorized_news = {}
        
        try:
            news_data = self.storage.get_all_articles() # 假设这里返回 List[Dict]
            
            if not news_data:
                self.logger.info("没有找到新闻数据")
                # ... (处理无数据情况) ...
                return
            
            self.all_news_items = news_data
            self.logger.info(f"加载了 {len(news_data)} 条新闻数据")
            
            # 自动分类新闻
            self.logger.info("调用 _categorize_news 进行新闻分类...")
            self._categorize_news()
            self.logger.info("_categorize_news 调用完成。")

            # --- DEBUG: 清空未分类新闻列表 --- 
            if "uncategorized" in self.categorized_news:
                self.logger.info(f"清空前，'未分类'列表包含 {len(self.categorized_news['uncategorized'])} 条新闻。")
                self.categorized_news["uncategorized"] = []
                self.logger.info("调试：已清空'未分类'列表。")
            else:
                self.logger.info("调试：'未分类'键不在 categorized_news 中，无需清空。")
            # --- DEBUG END ---
            
            # 填充分类树
            self.logger.info("调用 _populate_category_tree 更新UI分类列表...")
            self._populate_category_tree()
            self.logger.info("_populate_category_tree 调用完成。")
            
            # 默认显示所有新闻
            self._populate_news_list(self.all_news_items)
            
            self.logger.info("新闻数据加载和分类完成")
            
        except Exception as e:
            self.logger.error(f"加载新闻数据时出错: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"加载新闻数据失败: {e}")
    
    def _categorize_news(self):
        """自动将新闻分类到不同类别"""
        self.logger.info("开始自动分类新闻...")
        
        # 初始化分类字典
        for category_id, category_info in STANDARD_CATEGORIES.items():
            self.categorized_news[category_id] = []
        
        # 添加一个未分类类别
        self.categorized_news["uncategorized"] = []
        
        # 添加军事类别（在STANDARD_CATEGORIES中可能没有）
        if "military" not in self.categorized_news:
            self.categorized_news["military"] = []
        
        # 扩展的关键词匹配分类方法
        # 在实际应用中，应该使用更复杂的算法，如机器学习分类器
        category_keywords = {
            "politics": ["政治", "政府", "总统", "主席", "国家", "党", "选举", "外交", "政策", "人大", "政协", "法律", "法规", "立法", "司法", "行政"],
            "military": ["军事", "军队", "武器", "导弹", "战争", "战斗", "军演", "国防", "航母", "坦克", "战机", "士兵", "将军", "作战", "军备", "军工"],
            "technology": ["科技", "技术", "互联网", "IT", "AI", "人工智能", "APP", "软件", "硬件", "算法", "数据", "编程", "代码", "芯片", "半导体", "创新科技", "数码", "智能"],
            "science": ["科学", "研究", "发现", "实验", "物理", "化学", "生物", "天文", "地理", "医学研究", "科研", "探索", "知识", "自然科学", "生命科学"],
            "business": ["经济", "商业", "财经", "金融", "市场", "股票", "公司", "产业", "贸易", "投资", "银行", "企业家", "商业模式", "股市", "数字货币", "加密货币"],
            "entertainment": ["娱乐", "明星", "电影", "电视", "音乐", "综艺", "游戏", "动漫", "戏剧", "艺术", "演出", "八卦", "流行文化", "偶像"],
            "sports": ["体育", "足球", "篮球", "奥运", "比赛", "运动", "赛事", "健身", "电竞", "冠军", "运动员", "世界杯", "NBA", "CBA"],
            "health": ["健康", "医疗", "养生", "疾病", "医院", "医生", "药品", "保健", "疫情", "公共卫生", "身心健康", "健身", "医学"],
            "education": ["教育", "学校", "大学", "学习", "考试", "课程", "教学", "培训", "学术", "留学", "教育改革", "在线教育"],
            "world": ["国际", "世界", "全球", "外交", "地缘政治", "国际关系", "海外", "联合国", "峰会", "国际新闻"], # Note: Used to be 'international', changed to 'world' to match common usage if applicable, or ensure consistency with STANDARD_CATEGORIES
            "society": ["社会", "民生", "热点", "事件", "社区", "生活", "文化", "公益", "环境", "可持续发展", "社会问题", "舆情"],
            "automobile": ["汽车", "新车", "电动车", "自动驾驶", "车展", "交通工具", "新能源汽车", "智能汽车", "购车", "评测"],
            "real_estate": ["房产", "楼市", "房价", "房地产", "购房", "租房", "物业", "地产政策", "城市规划", "家居"],
            "travel": ["旅游", "出行", "景点", "度假", "酒店", "航空", "旅行", "攻略", "户外", "背包客", "自驾游"],
            "fashion": ["时尚", "潮流", "美妆", "奢侈品", "服装", "设计", "模特", "时尚周", "穿搭", "生活方式"],
            # 'general' (综合) 通常不通过关键词主动分类，而是作为其他分类匹配不上的一个默认选项，或者由新闻源直接提供
        }

        # 确保uncategorized类别存在
        if "uncategorized" not in self.categorized_news:
            self.categorized_news["uncategorized"] = []
            self.logger.info("Added 'uncategorized' to self.categorized_news as it was missing.")

        self.logger.info(f"Initial self.categorized_news keys: {list(self.categorized_news.keys())}")

        for article in self._all_news_articles:
            assigned_category = False
            
            # 方案A: 优先使用新闻条目自带的 category_id
            if article.category and article.category in STANDARD_CATEGORIES:
                self.categorized_news[article.category].append(article)
                self.logger.debug(f"News '{article.title[:20]}...' categorized as '{article.category}' from article.category field.")
                assigned_category = True
            elif article.category and article.category == "uncategorized": # If explicitly marked as uncategorized
                 # Handled by keyword matching or fallback later if still unassigned
                 pass


            if not assigned_category:
                # 如果没有自带分类或自带分类无效，则尝试关键词匹配
                title_content = (article.title + " " + article.content).lower() if article.content else article.title.lower()
                
                for category, keywords in category_keywords.items():
                    if any(keyword in title_content for keyword in keywords):
                        if category in self.categorized_news:
                            self.categorized_news[category].append(article)
                            self.logger.debug(f"News '{article.title[:20]}...' categorized as '{category}' by keyword matching.")
                            assigned_category = True
                            break 
                        else:
                            self.logger.warning(f"Keyword match for category '{category}' but this key is not in self.categorized_news. News: {article.title[:20]}")
            
            if not assigned_category:
                # 如果新闻自带分类是 "uncategorized" 或者关键词无法匹配，则放入 "uncategorized"
                if "uncategorized" in self.categorized_news:
                    self.categorized_news["uncategorized"].append(article)
                    self.logger.debug(f"News '{article.title[:20]}...' placed in 'uncategorized'. Original article.category: '{article.category}'")
                else:
                    self.logger.error(f"'uncategorized' key missing from self.categorized_news. Cannot categorize: {article.title[:20]}")


        self.logger.info("新闻自动分类完成。")
        for category_id, news_list in self.categorized_news.items():
            self.logger.info(f"分类 '{get_display_category_name_from_collector(category_id)}' (ID: {category_id}) 中有 {len(news_list)} 条新闻。")

        # 确保在分类后调用，以反映最新的分类结果
        self._update_category_counts()
        # Manually trigger tree population after categorization
        # self._populate_category_tree() # Let main_window or specific actions call this

    def _populate_category_tree(self):
        """填充分类树控件，确保分类按指定顺序显示在'所有新闻'下，'未分类'始终在底部。"""
        self.logger.info("--- ENTERING _populate_category_tree (Restored Stable Version) ---")
        self.category_tree.clear()
        self.category_tree.setSortingEnabled(False) 
        # self.category_tree.setHeaderHidden(True) # 通常分类列表不需要显示表头

        # 1. 创建 "所有新闻" 顶级节点
        all_news_node = QTreeWidgetItem(self.category_tree, ["所有新闻"])
        all_news_node.setData(0, Qt.UserRole, "all_news")
        all_news_node.setIcon(0, QIcon.fromTheme("folder-open", QIcon(":/icons/folder_open.svg")))
        font = all_news_node.font(0)
        font.setBold(True)
        all_news_node.setFont(0, font)
        self.logger.info(f"Added top-level node: {all_news_node.text(0)} (ID: {all_news_node.data(0, Qt.UserRole)})")

        # 2. 定义期望的分类顺序 (内部ID)
        # 期望顺序: 综合, 科技, 科学, 政治, 娱乐, 国际, 商业, 健康, 体育
        category_order = [
            "general", "technology", "science", "politics", "entertainment",
            "international", "business", "health", "sports" 
        ]
        self.logger.info(f"Desired category order: {category_order}")

        # 3. 添加标准分类到 "所有新闻" 节点下
        added_categories_count = 0
        for category_id in category_order:
            if category_id in STANDARD_CATEGORIES:
                display_name = get_display_category_name_from_collector(category_id, "未知分类")
                
                # Create child item and explicitly set parent in constructor
                child_node = QTreeWidgetItem(all_news_node, [display_name]) 
                child_node.setData(0, Qt.UserRole, category_id)
                child_node.setIcon(0, QIcon.fromTheme("document-multiple", QIcon(":/icons/article.svg"))) # Standard icon for categories
                
                self.logger.info(f"  Added child: {display_name} (ID: {category_id}) to parent '{all_news_node.text(0)}'.")
                added_categories_count += 1
            else:
                self.logger.warning(f"Category ID '{category_id}' from order list not found in STANDARD_CATEGORIES.")
        
        self.logger.info(f"Added {added_categories_count} standard categories under '{all_news_node.text(0)}'. Child count: {all_news_node.childCount()}")

        # 4. 添加 "未分类" 到 "所有新闻" 节点下 (始终在最后)
        uncategorized_name = get_display_category_name_from_collector("uncategorized", "未分类")
        uncategorized_node = QTreeWidgetItem(all_news_node, [uncategorized_name])
        uncategorized_node.setData(0, Qt.UserRole, "uncategorized")
        uncategorized_node.setIcon(0, QIcon.fromTheme("folder-question", QIcon(":/icons/folder_question_outline.svg")))
        self.logger.info(f"  Added child: {uncategorized_name} (ID: uncategorized) to parent '{all_news_node.text(0)}'.")
        self.logger.info(f"Final child count of '{all_news_node.text(0)}': {all_news_node.childCount()}")

        all_news_node.setExpanded(True) # Expand "所有新闻" by default
        self.logger.info(f"Expanded '{all_news_node.text(0)}'.")
        # self.category_tree.setCurrentItem(all_news_node) # Optionally select "All News" by default
        self.logger.info("--- EXITING _populate_category_tree (Restored Stable Version) ---")
    
    def _populate_news_list(self, news_items):
        """填充新闻列表控件"""
        self.news_list.clear()
        
        if not news_items:
            item = QListWidgetItem("该类别下没有新闻")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)  # 不可选
            self.news_list.addItem(item)
            return
        
        for i, news in enumerate(news_items):
            title = news.get('title', '无标题')
            source = news.get('source_name', '未知来源')
            
            # 尝试解析发布时间
            pub_time_str = ''
            pub_time = news.get('publish_time', '')
            if pub_time:
                if isinstance(pub_time, str):
                    try:
                        pub_time_dt = datetime.fromisoformat(pub_time)
                        pub_time_str = pub_time_dt.strftime('%Y-%m-%d %H:%M')
                    except (ValueError, TypeError):
                        pub_time_str = pub_time
                elif isinstance(pub_time, datetime):
                    pub_time_str = pub_time.strftime('%Y-%m-%d %H:%M')
            
            # 获取新闻分类（如果有）
            category_str = ''
            for cat_id, cat_news in self.categorized_news.items():
                if news in cat_news:
                    if cat_id == "uncategorized":
                        category_str = "未分类"
                    elif cat_id == "military" and cat_id not in STANDARD_CATEGORIES:
                        category_str = "军事新闻"
                    else:
                        category_str = STANDARD_CATEGORIES.get(cat_id, {}).get("name", "未分类")
                    break
            
            # 构建显示文本，使用更清晰的格式
            display_text = f"{title}"
            meta_info = []
            
            if source:
                meta_info.append(f"来源: {source}")
            if pub_time_str:
                meta_info.append(f"时间: {pub_time_str}")
            if category_str:
                meta_info.append(f"分类: {category_str}")
                
            if meta_info:
                display_text += f"\n{' | '.join(meta_info)}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, i)  # 存储索引以便后续获取完整数据
            
            # 为所有新闻项统一设置样式
            # 使用统一的浅色背景，确保视觉一致性
            item.setBackground(QColor(245, 245, 250))  # 统一的浅色背景
            
            # 设置统一的字体样式
            font = item.font()
            font.setPointSize(9)  # 统一字体大小
            item.setFont(font)
            
            # 设置统一的图标
            item.setIcon(QIcon.fromTheme("text-x-generic", QIcon("")))
                
            self.news_list.addItem(item)
    
    def _on_category_selected(self, item):
        """处理分类树节点选择事件"""
        category_id = item.data(0, Qt.UserRole)
        self.current_category = category_id
        
        if category_id == "all":
            # 显示所有新闻
            self._populate_news_list(self.all_news_items)
            self.current_group_items = self.all_news_items
        else:
            # 显示特定类别的新闻
            self._populate_news_list(self.categorized_news[category_id])
            self.current_group_items = self.categorized_news[category_id]
    
    def _on_selection_changed(self):
        """处理新闻列表选择变化"""
        selected_items = self.news_list.selectedItems()
        indices = []
        
        for item in selected_items:
            index = item.data(Qt.UserRole)
            if isinstance(index, int) and 0 <= index < len(self.all_news_items):
                indices.append(index)
        
        # 更新分析按钮状态
        self.analyze_button.setEnabled(len(indices) > 0)
        
        # 只存储索引，避免重复加载新闻数据
        self.selected_indices = indices
        # 清空已选择的新闻项列表，避免重复加载
        self.selected_news_items = []
        self.logger.debug(f"已选择 {len(indices)} 条新闻")
        
        # 不在这里加载新闻项，只在需要时（如点击分析按钮时）才加载
        # 这样可以避免每次选择变化都重复加载数据
    
    def _select_all_news(self):
        """选择所有新闻"""
        for i in range(self.news_list.count()):
            item = self.news_list.item(i)
            if item.flags() & Qt.ItemIsSelectable:  # 确保项目可选
                item.setSelected(True)
    
    def _deselect_all_news(self):
        """取消选择所有新闻"""
        self.news_list.clearSelection()
    
    def _auto_group_news(self):
        """自动分组相关新闻，将不同新闻源的相同新闻作为一个项目展示"""
        if not self.current_group_items:
            QMessageBox.information(self, "提示", "当前类别下没有可分组的新闻数据")
            return
        
        # 获取选择的分类方法
        clustering_method = self.clustering_method.currentData()
        
        # 显示进度条
        self.logger.info(f"开始自动分组新闻，使用方法: {clustering_method}...")
        self.progress_bar.setVisible(True)
        total_items = len(self.current_group_items)
        self.progress_bar.setRange(0, total_items)
        self.progress_bar.setValue(0)
        
        try:
            # 如果选择多特征融合方法，使用增强型新闻聚类器
            if clustering_method == "multi_feature":
                self._auto_group_news_enhanced()
                return
            
            # 使用标题相似度方法（原始方法）
            # 使用标题关键词匹配、主题识别和来源区分进行分组
            groups = []
            processed = set()
            
            # 优化：预处理所有标题，避免重复处理
            preprocessed_titles = []
            # 主题关键词字典 - 用于识别新闻主题
            topic_keywords = {
                "ai": ["ai", "artificial intelligence", "chatgpt", "openai", "llm", "large language model", "gpt", "机器学习", "人工智能"],
                "tech": ["technology", "tech", "software", "hardware", "app", "application", "digital", "computer", "internet", "web", "online", "科技", "技术"],
                "social": ["social", "society", "community", "people", "public", "social media", "facebook", "twitter", "instagram", "tiktok", "社交", "社会"],
                "politics": ["politics", "government", "election", "president", "policy", "political", "vote", "democracy", "republican", "democrat", "政治", "政府"],
                "business": ["business", "economy", "market", "stock", "company", "corporation", "finance", "investment", "商业", "经济", "市场", "金融"],
                "health": ["health", "medical", "medicine", "disease", "virus", "doctor", "hospital", "patient", "healthcare", "健康", "医疗", "疾病"],
                "environment": ["environment", "climate", "weather", "pollution", "green", "sustainable", "ecology", "wildlife", "nature", "环境", "气候", "生态", "野生动物"],
                "sports": ["sports", "game", "match", "team", "player", "championship", "tournament", "competition", "体育", "比赛", "选手", "冠军"],
                "entertainment": ["entertainment", "movie", "film", "music", "celebrity", "star", "actor", "actress", "singer", "娱乐", "电影", "音乐", "明星"],
                "science": ["science", "research", "study", "discovery", "experiment", "scientist", "laboratory", "科学", "研究", "发现", "实验"]
            }
            
            for news in self.current_group_items:
                title = news.get('title', '').lower()
                words = set(title.split()) if title else set()
                
                # 识别新闻主题
                topics = set()
                for topic, keywords in topic_keywords.items():
                    for keyword in keywords:
                        if keyword in title:
                            topics.add(topic)
                            break
                
                preprocessed_titles.append((title, words, topics))
            
            # 设置批处理大小，每处理一批更新一次进度条
            batch_size = max(1, total_items // 100)  # 确保至少为1
            processed_count = 0
            
            import time
            start_time = time.time()
            max_processing_time = 60  # 最大处理时间（秒）
            
            for i, news in enumerate(self.current_group_items):
                # 检查是否超时
                if time.time() - start_time > max_processing_time:
                    self.logger.warning(f"自动分组处理时间超过{max_processing_time}秒，提前结束处理")
                    break
                    
                # 更新进度条
                processed_count += 1
                if processed_count % batch_size == 0 or processed_count == total_items:
                    self.progress_bar.setValue(processed_count)
                    # 处理Qt事件，确保UI响应
                    from PySide6.QtCore import QCoreApplication
                    QCoreApplication.processEvents()
                
                if i in processed:
                    continue
                
                title_i, words_i, topics_i = preprocessed_titles[i]
                if not title_i:
                    continue
                
                # 创建新组，记录新闻来源
                group = [news]
                sources = {news.get('source_name', '未知来源')}
                processed.add(i)
                
                # 查找相似新闻，但来源不同的新闻
                for j, other_news in enumerate(self.current_group_items):
                    # 定期处理Qt事件，确保UI响应
                    if j % 100 == 0:
                        from PySide6.QtCore import QCoreApplication
                        QCoreApplication.processEvents()
                        
                    if j in processed or i == j:
                        continue
                    
                    # 检查来源是否已存在于当前组
                    other_source = other_news.get('source_name', '未知来源')
                    if other_source in sources:
                        continue  # 跳过相同来源的新闻
                    
                    title_j, words_j, topics_j = preprocessed_titles[j]
                    if not title_j:
                        continue
                    
                    # 1. 主题匹配检查 - 如果两篇新闻的主题完全不同且都有明确主题，则跳过
                    if topics_i and topics_j and not topics_i.intersection(topics_j):
                        continue
                    
                    # 2. 关键词匹配
                    common_words = words_i.intersection(words_j)
                    keyword_similarity = len(common_words) / max(len(words_i), 1) if words_i else 0
                    
                    # 提取实体名词（大写开头的词，可能是人名、地名、组织名等）
                    entities_i = {word for word in title_i.split() if word and word[0].isupper()}
                    entities_j = {word for word in title_j.split() if word and word[0].isupper()}
                    entity_match = bool(entities_i.intersection(entities_j)) if entities_i and entities_j else False
                    
                    # 提取数字（可能是日期、数量等重要信息）
                    import re
                    numbers_i = set(re.findall(r'\d+', title_i))
                    numbers_j = set(re.findall(r'\d+', title_j))
                    # 如果两篇新闻都包含数字，但没有共同数字，可能是不同事件
                    if numbers_i and numbers_j and not numbers_i.intersection(numbers_j):
                        # 数字不匹配，降低相似度可能性
                        # 但如果有强实体匹配，仍然继续检查
                        if not entity_match or len(entities_i.intersection(entities_j)) < 2:
                            continue
                    
                    # 只有关键词匹配度较高或有共同实体的才进行更复杂的相似度计算
                    if keyword_similarity > 0.3 or len(common_words) >= 3 or (entity_match and len(entities_i.intersection(entities_j)) >= 2):
                        # 3. 字符串相似度 - 使用更高效的算法
                        # 简化版：使用共同字符比例而不是LCS
                        chars_i = set(title_i)
                        chars_j = set(title_j)
                        common_chars = len(chars_i.intersection(chars_j))
                        string_similarity = common_chars / max(len(chars_i) + len(chars_j) - common_chars, 1)
                        
                        # 4. 语义相似度评估 - 基于关键词和实体
                        semantic_similarity = 0.0
                        
                        # 检查是否包含相同的关键实体（如公司名、人名等）
                        if entity_match:
                            # 根据匹配实体数量调整权重
                            matched_entities = len(entities_i.intersection(entities_j))
                            if matched_entities >= 3:
                                semantic_similarity += 0.4
                            elif matched_entities >= 2:
                                semantic_similarity += 0.3
                            else:
                                semantic_similarity += 0.2
                        
                        # 检查关键词的语义相关性
                        if len(common_words) >= 4:
                            semantic_similarity += 0.3
                        elif len(common_words) >= 3:
                            semantic_similarity += 0.2
                        elif len(common_words) >= 2:
                            semantic_similarity += 0.1
                        
                        # 5. 综合相似度评分 - 加入语义相似度权重
                        similarity_score = 0.35 * keyword_similarity + 0.25 * string_similarity + 0.4 * semantic_similarity
                        
                        # 6. 更严格的相似度阈值判断
                        # 如果相似度超过阈值，认为是相似新闻
                        if similarity_score > 0.6 or (entity_match and keyword_similarity > 0.4) or (len(common_words) >= 5):
                            group.append(other_news)
                            sources.add(other_source)
                            processed.add(j)
                
                if len(group) > 1:  # 只保留有多条新闻的组
                    groups.append(group)
                    
            # 记录处理时间
            processing_time = time.time() - start_time
            self.logger.info(f"自动分组处理完成，耗时 {processing_time:.2f} 秒，处理了 {processed_count}/{total_items} 条新闻")
            
            self.news_groups = groups
            self.progress_bar.setVisible(False)
            
            # 显示分组结果到分组树视图
            self._populate_group_tree(groups)
            
            # 切换到分组视图标签页
            self.news_tab.setCurrentIndex(1)
            
            if groups:
                # 生成简要分析结果文本
                result_text = f"已自动分组 {len(groups)} 组相关新闻。\n\n"
                result_text += "请在左侧\"分组视图\"标签页中查看详细分组结果，\n"
                result_text += "选择感兴趣的新闻组后点击\"开始分析\"按钮进行深度分析。"
                
                self.result_edit.setText(result_text)
                self.copy_button.setEnabled(True)
                self.save_button.setEnabled(True)
                self.clear_button.setEnabled(True)
                
                QMessageBox.information(self, "分组完成", f"已自动分组 {len(groups)} 组相关新闻，请在分组视图中查看。")
            else:
                QMessageBox.information(self, "分组结果", "未找到相似度足够高的新闻组。")
                self.result_edit.setText("自动分组结果: 未找到相似度足够高的新闻组。")
                self.copy_button.setEnabled(True)
                self.save_button.setEnabled(True)
                self.clear_button.setEnabled(True)
            
        except Exception as e:
            self.logger.error(f"自动分组新闻时出错: {e}", exc_info=True)
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "错误", f"自动分组新闻失败: {e}")
    
    def _populate_group_tree(self, groups):
        """填充分组树视图，优化显示不同新闻源的相同新闻"""
        self.group_tree.clear()
        
        # 保存当前滚动位置
        scrollbar_position = self.group_tree.verticalScrollBar().value()
        
        if not groups:
            item = QTreeWidgetItem(self.group_tree)
            item.setText(0, "未找到相似度足够高的新闻组")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)  # 不可选
            return
        
        # 添加分组到树视图
        for i, group in enumerate(groups):
            # 获取组内第一条新闻的标题作为组标题
            first_news = group[0]
            group_title = first_news.get('title', '无标题')
            
            # 提取组内所有新闻来源
            sources = set(news.get('source_name', '未知来源') for news in group)
            sources_str = ", ".join(sources)
            
            # 创建组节点，优化显示格式
            group_item = QTreeWidgetItem(self.group_tree)
            # 优化组标题显示
            group_item.setText(0, f"{group_title}")
            group_item.setText(1, f"{len(group)}")
            group_item.setData(0, Qt.UserRole, i)  # 存储组索引
            group_item.setToolTip(0, f"来源: {sources_str}\n包含{len(group)}条相关新闻")
            
            # 设置字体加粗
            font = group_item.font(0)
            font.setBold(True)
            group_item.setFont(0, font)
            
            # 添加组内新闻，按来源分类
            for news in group:
                news_item = QTreeWidgetItem(group_item)
                title = news.get('title', '无标题')
                source = news.get('source_name', '未知来源')
                pub_time = ''
                
                # 尝试格式化发布时间
                if news.get('publish_time'):
                    try:
                        if isinstance(news['publish_time'], str):
                            pub_time = datetime.fromisoformat(news['publish_time']).strftime('%m-%d %H:%M')
                        elif isinstance(news['publish_time'], datetime):
                            pub_time = news['publish_time'].strftime('%m-%d %H:%M')
                    except (ValueError, TypeError):
                        pass
                
                # 优化新闻项显示格式
                display_text = f"{source}" + (f" ({pub_time})" if pub_time else "")
                news_item.setText(0, display_text)
                
                # 设置工具提示显示完整标题和内容预览
                content = news.get('content') # Get content, might be None
                if content is None:
                    content = "" # Ensure content is a string
                content_preview = content[:100] + '...' if len(content) > 100 else content
                news_item.setToolTip(0, f"标题: {title}\n\n{content_preview}")
                
                # 存储新闻在all_news_items中的索引
                for j, n in enumerate(self.all_news_items):
                    if n is news:
                        news_item.setData(0, Qt.UserRole, j)
                        break
        
        # 展开所有组
        self.group_tree.expandAll()
        
        # 自动选择第一组
        if self.group_tree.topLevelItemCount() > 0:
            self.group_tree.setCurrentItem(self.group_tree.topLevelItem(0))
    
    def _on_group_selection_changed(self):
        """处理分组树选择变化"""
        selected_items = self.group_tree.selectedItems()
        selected_indices = []
        
        for item in selected_items:
            # 检查是否是组节点
            if item.parent() is None:
                # 是组节点，添加该组所有新闻
                group_index = item.data(0, Qt.UserRole)
                if isinstance(group_index, int) and 0 <= group_index < len(self.news_groups):
                    for news in self.news_groups[group_index]:
                        # 找到新闻在all_news_items中的索引
                        for j, n in enumerate(self.all_news_items):
                            if n is news and j not in selected_indices:
                                selected_indices.append(j)
                                break
            else:
                # 是新闻节点，添加该新闻
                news_index = item.data(0, Qt.UserRole)
                if isinstance(news_index, int) and 0 <= news_index < len(self.all_news_items) and news_index not in selected_indices:
                    selected_indices.append(news_index)
        
        # 只存储索引，避免重复加载新闻数据
        self.selected_indices = selected_indices
        # 清空已选择的新闻项列表，避免重复加载
        self.selected_news_items = []
        
        # 不在这里加载新闻项，只在需要时（如点击分析按钮时）才加载
        # 这样可以避免每次选择变化都重复加载数据
        
        # 更新分析按钮状态
        self.analyze_button.setEnabled(len(selected_indices) > 0)
        
        self.logger.debug(f"已选择 {len(selected_indices)} 条新闻")
        
        # 高亮显示选中的组和新闻项
        self._highlight_selected_group_items()
    
    def _show_group_context_menu(self, position):
        """显示分组树的上下文菜单"""
        menu = QMenu()
        
        current_item = self.group_tree.itemAt(position)
        if not current_item:
            return
            
        # 根据选中项类型显示不同菜单
        if current_item.parent():  # 新闻项
            view_action = QAction("查看详情", self)
            view_action.triggered.connect(lambda: self._on_group_item_double_clicked(current_item))
            menu.addAction(view_action)
            
            analyze_action = QAction("分析此新闻", self)
            analyze_action.triggered.connect(lambda: self._analyze_single_group_news(current_item))
            menu.addAction(analyze_action)
        else:  # 组项
            select_action = QAction("选择该组所有新闻", self)
            select_action.triggered.connect(self._select_current_group)
            menu.addAction(select_action)
            
            analyze_action = QAction("分析该组新闻", self)
            analyze_action.triggered.connect(lambda: self._analyze_selected_news())
            menu.addAction(analyze_action)
        
        menu.exec_(QCursor.pos())
        
    def _on_group_item_double_clicked(self, item):
        """处理分组树项目双击事件，显示新闻详情
        
        Args:
            item: 树项目
        """
        # 如果是新闻项（有父节点），显示详情
        if item.parent():
            news_index = item.data(0, Qt.UserRole)
            if isinstance(news_index, int) and 0 <= news_index < len(self.all_news_items):
                news = self.all_news_items[news_index]
                
                # 创建详情对话框
                from src.ui.news_detail_dialog import NewsDetailDialog
                from src.models import NewsArticle
                
                # 转换为NewsArticle对象
                # 处理publish_time字段，确保类型正确
                publish_time = news.get('publish_time')
                if publish_time and not isinstance(publish_time, datetime):
                    # 如果是字符串，保持原样，NewsDetailDialog会处理
                    publish_time = publish_time
                elif not publish_time:
                    publish_time = datetime.now()
                
                article = NewsArticle(
                    title=news.get('title', '无标题'),
                    content=news.get('content', ''),
                    summary=news.get('summary', ''),
                    link=news.get('link', ''),
                    source_name=news.get('source_name', '未知来源'),
                    publish_time=publish_time
                )
                
                dialog = NewsDetailDialog(article, self)
                dialog.show()
        # 如果是组项（没有父节点），展开/折叠
        else:
            if item.isExpanded():
                item.setExpanded(False)
            else:
                item.setExpanded(True)
                
    def _analyze_single_group_news(self, item):
        """分析分组树中的单条新闻
        
        Args:
            item: 树项目
        """
        if not item.parent():
            return
            
        # 清除当前选择
        self.group_tree.clearSelection()
        
        # 选中指定项
        item.setSelected(True)
        
        # 执行分析
        self._analyze_selected_news()
    
    def _select_current_group(self):
        """选择当前组的所有新闻"""
        current_item = self.group_tree.currentItem()
        if not current_item:
            return
            
        # 如果选中的是新闻项，获取其父组项
        if current_item.parent():
            current_item = current_item.parent()
            
        # 选择该组所有子项
        for i in range(current_item.childCount()):
            child = current_item.child(i)
            child.setSelected(True)
    
    def _on_tab_changed(self, index):
        """处理标签页切换事件"""
        # 当切换到分组视图时，如果有分组结果但树为空，则填充树
        if index == 1 and self.news_groups and self.group_tree.topLevelItemCount() == 0:
            self._populate_group_tree(self.news_groups)

    # _on_analysis_type_changed, _on_prompt_selected, _on_prompt_edited methods removed as prompt management is removed.

    def _set_ui_enabled(self, enabled: bool):
        """启用或禁用UI元素，防止用户在分析过程中进行操作
        
        Args:
            enabled: 是否启用UI元素
        """
        # 禁用/启用按钮和列表
        self.analyze_button.setEnabled(enabled and (hasattr(self, 'selected_indices') and len(self.selected_indices) > 0))
        self.refresh_button.setEnabled(enabled)
        self.auto_group_button.setEnabled(enabled)
        self.select_all_button.setEnabled(enabled)
        self.deselect_all_button.setEnabled(enabled)
        self.news_list.setEnabled(enabled)
        self.group_tree.setEnabled(enabled)
        self.category_tree.setEnabled(enabled)
        self.news_tab.setEnabled(enabled)
        self.analysis_type.setEnabled(enabled)
        self.clustering_method.setEnabled(enabled)
        
        # 提示词管理组件已移除
            
        # 更新鼠标光标
        if not enabled:
            from PySide6.QtWidgets import QApplication
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            from PySide6.QtWidgets import QApplication
            QApplication.restoreOverrideCursor()
    
    def _highlight_selected_group_items(self):
        """高亮显示选中的组和新闻项"""
        # 设置选中项的背景色
        for i in range(self.group_tree.topLevelItemCount()):
            group_item = self.group_tree.topLevelItem(i)
            
            # 检查组是否被选中
            is_group_selected = group_item.isSelected()
            
            # 设置组项的背景色
            if is_group_selected:
                group_item.setBackground(0, QColor("#E3F2FD"))
            else:
                group_item.setBackground(0, QColor("transparent"))
                
            # 处理组内的新闻项
            for j in range(group_item.childCount()):
                news_item = group_item.child(j)
                if news_item.isSelected():
                    news_item.setBackground(0, QColor("#E3F2FD"))
                else:
                    news_item.setBackground(0, QColor("transparent"))
    
    def _analyze_selected_news(self):
        """分析选中的新闻，整合相似度分析、重要程度和立场分析功能"""
        # 使用索引获取选中的新闻，避免重复加载
        if not hasattr(self, 'selected_indices') or not self.selected_indices:
            QMessageBox.information(self, "提示", "请先选择要分析的新闻")
            return
            
        if not self.llm_service:
            QMessageBox.critical(self, "错误", "LLM服务不可用，无法进行AI分析")
            return
            
        # 禁用UI元素，显示进度条
        self._set_ui_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        try:
            # 禁用UI元素，防止用户在分析过程中进行操作
            self._set_ui_enabled(False)
            
            # 从索引获取选中的新闻
            selected_news_items = [self.all_news_items[idx] for idx in self.selected_indices if 0 <= idx < len(self.all_news_items)]
            
            # 保存到实例变量，以便其他方法可以访问
            self.selected_news_items = selected_news_items
            
            self.logger.info(f"开始分析 {len(selected_news_items)} 条新闻...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setRange(0, 100)  # 设置确定进度
            self.progress_bar.setValue(10)  # 初始进度
            
            # 更新状态栏或结果区域，显示正在分析的提示
            self.result_edit.setPlainText("正在分析中，请稍候...")
            
            # 准备新闻数据
            news_data = []
            for news in selected_news_items:
                news_data.append({
                    'title': news.get('title', ''),
                    'content': news.get('content', ''),
                    'source': news.get('source_name', ''),
                    'publish_time': news.get('publish_time', '')
                })
            
            # 获取当前分析类型
            analysis_type_str = self.analysis_type.currentText() # Renamed to avoid conflict
            self.logger.debug(f"--- ANALYZE_SELECTED_NEWS: Starting analysis of type: {analysis_type_str} ---")

            # 更新进度条
            self.progress_bar.setValue(30)
            from PySide6.QtCore import QCoreApplication
            QCoreApplication.processEvents()  # 处理事件，确保UI更新
            
            # 显示分析中的状态
            self.result_edit.setPlainText("正在分析中，请稍候...\n正在处理新闻数据并生成分析结果...")
            
            # 使用默认方法进行分析 (提示词模板选择已移除)
            # 更新进度条
            self.progress_bar.setValue(50)
            QCoreApplication.processEvents()  # 处理事件，确保UI更新
            
            # 根据 analysis_type 下拉菜单确定分析类型
            if analysis_type_str == "新闻相似度分析":
                result = self.llm_service.analyze_news_similarity(news_data)
            elif analysis_type_str == "增强型多特征分析":
                # Placeholder for enhanced analysis call
                # TODO: Implement enhanced multi-feature analysis call in LLMService
                result = self.llm_service.analyze_news_similarity(news_data) # Replace with actual call
                self.logger.warning("增强型多特征分析尚未完全实现，暂时使用相似度分析")
            elif analysis_type_str == "重要程度和立场分析":
                if news_data:
                    first_news = news_data[0]
                    result = self.llm_service.analyze_importance_stance({
                        'title': first_news['title'],
                        'content': first_news['content']
                    })
                else:
                    result = {}
            elif analysis_type_str == "深度分析":
                if news_data:
                    first_news = news_data[0]
                    self.logger.debug(f"--- ANALYZE_SELECTED_NEWS: Calling LLMService.analyze_deep_analysis with title: {first_news['title'][:50]}... ---")
                    result = self.llm_service.analyze_deep_analysis({
                        'title': first_news['title'],
                        'content': first_news['content']
                    })
                else:
                    result = {}
            elif analysis_type_str == "关键观点":
                if news_data:
                    first_news = news_data[0]
                    result = self.llm_service.analyze_key_points({
                        'title': first_news['title'],
                        'content': first_news['content']
                    })
                else:
                    result = {}
            elif analysis_type_str == "事实核查":
                if news_data:
                    first_news = news_data[0]
                    result = self.llm_service.analyze_fact_check({
                        'title': first_news['title'],
                        'content': first_news['content']
                    })
                else:
                    result = {}
            elif analysis_type_str == "摘要":
                if news_data:
                    first_news = news_data[0]
                    result = self.llm_service.analyze_summary({
                        'title': first_news['title'],
                        'content': first_news['content']
                    })
                else:
                    result = {}
            else:
                self.logger.warning(f"未知的分析类型: {analysis_type_str}, 默认执行相似度分析")
                result = self.llm_service.analyze_news_similarity(news_data)
            
            self.logger.debug(f"--- ANALYZE_SELECTED_NEWS: Result from LLMService: {result} ---")

            analysis_data_to_emit = {}
            if isinstance(result, dict):
                self.logger.info("LLMService returned a dictionary.")
                analysis_data_to_emit = result
                # Ensure analysis_type is present in the emitted data if it was in the result
                if 'analysis_type' not in analysis_data_to_emit and hasattr(result, 'get') and result.get('analysis_type'):
                    analysis_data_to_emit['analysis_type'] = result.get('analysis_type')
                elif 'analysis_type' not in analysis_data_to_emit:
                    analysis_data_to_emit['analysis_type'] = analysis_type_str # from the method

            elif isinstance(result, str) and result.strip():
                self.logger.info(f"LLMService returned a non-empty string. Treating as valid analysis content (HTML/Markdown). Length: {len(result)}")
                # If LLMService returned a string (e.g., pre-formatted HTML or Markdown)
                analysis_data_to_emit = {
                    # 'content' key might be preferred by _on_analysis_completed for direct Markdown/HTML strings
                    "content": result, 
                    "analysis": result, # Also populate 'analysis' for robustness, though 'content' is primary for strings
                    "analysis_type": analysis_type_str, # Use the current analysis type from the dropdown
                    "error": None, # Explicitly set no error
                    # Add default empty values for other fields _on_analysis_completed might expect if result was a dict
                    "importance": 0,
                    "stance": 0.0,
                    "stance_dimensions": {}
                }
            else:
                self.logger.error(f"LLMService returned an empty or unexpected result (type: {type(result)}). Result: {str(result)[:500]}...")
                analysis_data_to_emit = {
                    "error": f"LLM服务返回了空或非预期的结果格式 (类型: {type(result)}).",
                    "analysis_type": analysis_type_str,
                    "analysis": "分析未返回有效内容。",
                    "content": "分析未返回有效内容。",
                    "importance": 0,
                    "stance": 0.0,
                    "stance_dimensions": {}
                }

            # Ensure analysis_type is always present in the emitted dictionary
            if 'analysis_type' not in analysis_data_to_emit:
                analysis_data_to_emit['analysis_type'] = analysis_type_str
            elif not analysis_data_to_emit.get('analysis_type'): # If it's None or empty from result dict
                 analysis_data_to_emit['analysis_type'] = analysis_type_str

            self.logger.debug(f"--- ANALYZE_SELECTED_NEWS: Emitting analysis_data_to_emit: {str(analysis_data_to_emit)[:500]}...")

            # 更新进度条到100%并隐藏 (Moved earlier to ensure it always runs before emit)
            self.progress_bar.setValue(100)
            QCoreApplication.processEvents()  # 确保UI更新
            self.progress_bar.setVisible(False)
            
            # 恢复UI状态 (Moved earlier)
            self._set_ui_enabled(True)
            self.logger.info("分析完成，已恢复UI状态")
            QApplication.restoreOverrideCursor()  # 确保鼠标光标恢复正常

            # Emit the processed dictionary
            self.analysis_completed.emit(analysis_data_to_emit)

        except Exception as e:
            self.logger.error(f"分析新闻时出错: {e}", exc_info=True)
            self.progress_bar.setVisible(False)
            # 恢复UI状态
            self._set_ui_enabled(True)
            QMessageBox.critical(self, "错误", f"分析新闻失败: {e}")
    
    def _on_analysis_completed(self, result: dict):
        """处理从 LLMService 返回的分析结果并更新UI"""
        self.logger.info(f"--- MINIMAL_ON_ANALYSIS_ENTERED --- Raw result (first 500): {str(result)[:500]}")

        try:
            self.progress_bar.setVisible(False)
            self._set_ui_enabled(True)
            QApplication.restoreOverrideCursor()
            self.logger.info("--- MINIMAL_ON_ANALYSIS --- UI state reset (progress bar, enabled, cursor).")

            content_to_display = None
            is_html = False

            if isinstance(result, dict):
                error = result.get("error")
                primary_content = result.get("content")
                secondary_content = result.get("analysis") # Usually the same as content if string

                self.logger.info(f"--- MINIMAL_ON_ANALYSIS --- Error: {error}, Type of primary_content: {type(primary_content)}")

                if error is None:
                    if isinstance(primary_content, str) and primary_content.strip():
                        self.logger.info(f"--- MINIMAL_ON_ANALYSIS --- Using primary_content (string, len: {len(primary_content)}). Assuming HTML.")
                        content_to_display = primary_content
                        is_html = True
                    elif isinstance(secondary_content, str) and secondary_content.strip(): # Fallback to analysis key
                        self.logger.info(f"--- MINIMAL_ON_ANALYSIS --- Using secondary_content (string, len: {len(secondary_content)}). Assuming HTML.")
                        content_to_display = secondary_content
                        is_html = True
                    elif isinstance(primary_content, dict): # If content is a dict, try to format it simply
                        self.logger.info(f"--- MINIMAL_ON_ANALYSIS --- Primary content is dict. Formatting simply.")
                        content_to_display = "<p>" + "<br>".join([f"<b>{k}:</b> {v}" for k,v in primary_content.items()]) + "</p>"
                        is_html = True 
                    else:
                        content_to_display = "分析完成，但未收到预期的可显示内容格式。"
                        self.logger.warning(f"--- MINIMAL_ON_ANALYSIS --- No valid string/dict content found when error is None.")
                else: # Error is not None
                    self.logger.warning(f"--- MINIMAL_ON_ANALYSIS --- Error reported: {error}")
                    # Check if error is the specific one where content might still be in 'analysis'
                    if error == "LLM service processing error or no content." and isinstance(secondary_content, str) and secondary_content.strip():
                        self.logger.info(f"--- MINIMAL_ON_ANALYSIS --- Specific error, but using secondary_content as HTML.")
                        content_to_display = secondary_content
                        is_html = True
                    else:
                        content_to_display = f"分析失败：{error}"
                        if isinstance(primary_content, str) and primary_content.strip():
                            content_to_display += f"<br><br>部分内容：{primary_content[:200]}..."
                            is_html = True # Error message can be HTML too
                        elif isinstance(primary_content, dict):
                            content_to_display += f"<br><br>部分内容：{str(primary_content)[:200]}..."
                            is_html = True
            else:
                content_to_display = "收到的分析结果格式无效 (非字典)。"
                self.logger.error(f"--- MINIMAL_ON_ANALYSIS --- Result is not a dict: {type(result)}")
            
            if content_to_display:
                if is_html:
                    self.logger.info(f"--- MINIMAL_ON_ANALYSIS --- Attempting self.result_edit.setHtml(), len: {len(content_to_display)}.")
                    self.result_edit.setHtml(content_to_display)
                    self.logger.info(f"--- MINIMAL_ON_ANALYSIS --- AFTER SET HTML. Content (first 500): {self.result_edit.toHtml()[:500]}")
                else:
                    self.logger.info(f"--- MINIMAL_ON_ANALYSIS --- Attempting self.result_edit.setPlainText(), len: {len(content_to_display)}.")
                    self.result_edit.setPlainText(content_to_display)
                    self.logger.info(f"--- MINIMAL_ON_ANALYSIS --- AFTER SET PLAIN TEXT. Content (first 500): {self.result_edit.toPlainText()[:500]}")
                QApplication.processEvents() # Try to force UI update
            else:
                self.logger.warning("--- MINIMAL_ON_ANALYSIS --- No content was prepared for display.")
                self.result_edit.setPlainText("分析完成，但没有内容可显示。")
                QApplication.processEvents()

            # Update button states
            has_text_in_result_edit = bool(self.result_edit.toPlainText().strip())
            self.copy_button.setEnabled(has_text_in_result_edit)
            self.save_button.setEnabled(has_text_in_result_edit)
            self.clear_button.setEnabled(True)
            self.logger.info("--- MINIMAL_ON_ANALYSIS --- Buttons updated.")

        except Exception as e_minimal:
            self.logger.critical(f"--- MINIMAL_ON_ANALYSIS --- CRITICAL EXCEPTION in simplified handler: {e_minimal}", exc_info=True)
            try:
                self.result_edit.setPlainText(f"处理分析结果时发生严重内部错误: {e_minimal}")
            except:
                pass # Avoid error in error handling
        
        self.logger.info(f"--- MINIMAL_ON_ANALYSIS_EXITED ---")

    def _save_analysis_to_history(self, result_text: str, analysis_type: str):
        """保存分析结果到历史记录
        
        Args:
            result_text: 分析结果文本
            analysis_type: 分析类型
        """
        try:
            # 获取分析的新闻标题和来源
            news_titles = []
            news_sources = []
            for news in self.selected_news_items:
                title = news.get('title', '无标题')
                source = news.get('source_name', '未知来源')
                if title not in news_titles:
                    news_titles.append(title)
                if source not in news_sources:
                    news_sources.append(source)
            
            # 创建分析记录
            analysis_record = {
                'timestamp': datetime.now().isoformat(),
                'type': analysis_type,
                'result': result_text, # Use the passed text
                'news_count': len(self.selected_news_items),
                'news_titles': news_titles,
                'news_sources': news_sources,
                'categories': list(set(self._get_news_categories(self.selected_news_items)))
            }
            
            # 如果是分组分析，添加分组信息
            if self.news_tab.currentIndex() == 1:  # 分组视图
                selected_items = self.group_tree.selectedItems()
                group_info = []
                for item in selected_items:
                    if item.parent() is None:  # 是组节点
                        group_index = item.data(0, Qt.UserRole)
                        if isinstance(group_index, int) and 0 <= group_index < len(self.news_groups):
                            group = self.news_groups[group_index]
                            sources = set(news.get('source_name', '未知来源') for news in group)
                            group_info.append({
                                'title': item.text(0),
                                'sources': list(sources),
                                'count': len(group)
                            })
                if group_info:
                    analysis_record['groups'] = group_info
            
            # 调用存储服务保存记录
            if self.storage:
                try:
                    self.storage.save_analysis_result(analysis_record)
                    self.logger.info(f"已保存分析结果到历史记录: {analysis_type}")
                    QMessageBox.information(self, "保存成功", "分析结果已保存到历史记录")
                except AttributeError as ae:
                    self.logger.error(f"保存分析结果到历史记录时出错: {ae}", exc_info=True)
                    QMessageBox.warning(self, "保存失败", "存储服务不支持保存分析结果功能，请更新应用版本")
                except Exception as e:
                    self.logger.error(f"保存分析结果到历史记录时出错: {e}", exc_info=True)
                    QMessageBox.warning(self, "保存失败", f"保存分析结果到历史记录失败: {e}")
            
        except Exception as e:
            self.logger.error(f"保存分析结果到历史记录时出错: {e}", exc_info=True)
            QMessageBox.warning(self, "保存失败", f"保存分析结果到历史记录失败: {e}")
    
    def _get_news_categories(self, news_items):
        """获取新闻所属的分类列表
        
        Args:
            news_items: 新闻列表
            
        Returns:
            分类名称列表
        """
        categories = []
        for news in news_items:
            # 查找新闻所属分类
            for cat_id, cat_news in self.categorized_news.items():
                if news in cat_news:
                    if cat_id == "uncategorized":
                        categories.append("未分类")
                    elif cat_id == "military" and cat_id not in STANDARD_CATEGORIES:
                        categories.append("军事新闻")
                    else:
                        categories.append(STANDARD_CATEGORIES.get(cat_id, {}).get("name", "未分类"))
                    break
        return categories
    
    def _copy_result(self):
        """复制分析结果到剪贴板"""
        text = self.result_edit.toPlainText()
        if text:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(text)
            self.logger.info("已复制分析结果到剪贴板")
    
    def _save_result(self):
        """保存分析结果到文件并添加到历史记录"""
        text_to_save = self.result_edit.toPlainText() # Get plain text for saving
        html_to_save = self.result_edit.toHtml() # Could also save HTML if preferred for some formats

        if not text_to_save and not html_to_save: # Check if there's anything to save
            QMessageBox.information(self, "提示", "没有分析结果可保存。")
            return
        
        # Ask user for preferred format if HTML is substantial and different from plain text
        preferred_format = '.txt'
        content_to_file = text_to_save

        if len(html_to_save) > len(text_to_save) + 100: # Heuristic: if HTML is much richer
            reply = QMessageBox.question(self, "选择保存格式", 
                                       "检测到结果包含富文本格式。您希望如何保存？",
                                       "保存为纯文本 (.txt)", "保存为HTML (.html)", "取消")
            if reply == 0: # Plain text
                preferred_format = '.txt'
                content_to_file = text_to_save
            elif reply == 1: # HTML
                preferred_format = '.html'
                content_to_file = html_to_save
            else: # Cancel
                return

        try:
            # 获取保存路径
            from PySide6.QtWidgets import QFileDialog
            default_filename = f"新闻分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}{preferred_format}"
            
            file_filter = "纯文本文件 (*.txt);;HTML 文件 (*.html);;所有文件 (*)"
            if preferred_format == '.html':
                file_filter = "HTML 文件 (*.html);;纯文本文件 (*.txt);;所有文件 (*)"

            file_path, selected_filter = QFileDialog.getSaveFileName(
                self, "保存分析结果", default_filename, file_filter
            )
            
            if not file_path:
                return  # 用户取消

            # Adjust content if user chose a different filter than default
            if ".txt" in selected_filter and preferred_format == ".html":
                content_to_file = text_to_save
                if not file_path.endswith(".txt"): file_path += ".txt"
            elif ".html" in selected_filter and preferred_format == ".txt":
                content_to_file = html_to_save
                if not file_path.endswith(".html"): file_path += ".html"
            elif not file_path.endswith(preferred_format): # Ensure correct extension if filter not specific
                if ".txt" in selected_filter: file_path += ".txt"
                elif ".html" in selected_filter: file_path += ".html"
                else: file_path += preferred_format


            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content_to_file)
            
            # 获取当前分析类型
            analysis_type = self.analysis_type.currentText()
            
            # 同时保存到历史记录 (save the plain text version or a summary to history)
            # For history, usually plain text is better.
            self._save_analysis_to_history(text_to_save, analysis_type) # Pass plain text to history
            
            # 保存分析结果到类属性中，以便在界面关闭后仍能保留
            if not hasattr(self, 'saved_analysis_results'):
                self.saved_analysis_results = {}
            
            # 使用时间戳作为键
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.saved_analysis_results[timestamp] = {
                'text': text_to_save, # Save plain text version here
                'type': analysis_type,
                'file_path': file_path,
                # 'history_path': history_file_path # _save_analysis_to_history doesn't return path
            }
            
            self.logger.info(f"已保存分析结果到文件: {file_path}")
            QMessageBox.information(self, "保存成功", f"分析结果已保存到: {file_path}\n同时已添加到历史记录")
            
        except Exception as e:
            self.logger.error(f"保存分析结果到文件时出错: {e}", exc_info=True)
            QMessageBox.critical(self, "保存失败", f"无法保存文件: {str(e)}")
    
    def _clear_result(self):
        """清空分析结果"""
        self.result_edit.clear()
        self.copy_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        
        # 重置可视化组件 (Advanced visualizer reset handles multiple dimensions)
        self.analysis_visualizer.reset()
    
    def _show_context_menu(self, position: QPoint):
        """显示右键菜单
        
        Args:
            position: 鼠标位置
        """
        item = self.news_list.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self)
        
        # 查看详情
        view_action = QAction("查看详情", self)
        view_action.triggered.connect(lambda: self._view_news_detail(item))
        menu.addAction(view_action)
        
        # 分析此新闻
        analyze_action = QAction("分析此新闻", self)
        analyze_action.triggered.connect(lambda: self._analyze_single_news(item))
        menu.addAction(analyze_action)
        
        # 添加分类相关菜单项
        menu.addSeparator()
        category_menu = QMenu("设置分类", menu)
        
        # 添加标准分类
        for category_id, category_info in STANDARD_CATEGORIES.items():
            action = QAction(category_info.get("name", category_id), self)
            action.triggered.connect(lambda checked, cid=category_id: self._set_news_category(cid))
            category_menu.addAction(action)
        
        # 添加军事分类
        if "military" not in STANDARD_CATEGORIES:
            military_action = QAction("军事新闻", self)
            military_action.triggered.connect(lambda: self._set_news_category("military"))
            category_menu.addAction(military_action)
        
        # 添加未分类选项
        uncategorized_action = QAction("未分类", self)
        uncategorized_action.triggered.connect(lambda: self._set_news_category("uncategorized"))
        category_menu.addAction(uncategorized_action)
        
        menu.addMenu(category_menu)
        
        # 显示菜单
        menu.exec_(self.news_list.viewport().mapToGlobal(position))
    
    def _set_news_category(self, category_id):
        """手动设置选中新闻的分类"""
        selected_items = self.news_list.selectedItems()
        if not selected_items:
            return
            
        # 获取选中的新闻
        selected_news = []
        for item in selected_items:
            index = item.data(Qt.UserRole)
            if isinstance(index, int) and 0 <= index < len(self.all_news_items):
                selected_news.append(self.all_news_items[index])
        
        if not selected_news:
            return
            
        # 从原分类中移除
        for cat_id, news_list in self.categorized_news.items():
            for news in selected_news:
                if news in news_list:
                    news_list.remove(news)
        
        # 添加到新分类
        for news in selected_news:
            self.categorized_news[category_id].append(news)
        
        # 更新分类树
        self._populate_category_tree()
        
        # 更新新闻列表显示
        self._populate_news_list(self.current_group_items)
        
        # 重新选中这些新闻
        for i in range(self.news_list.count()):
            item = self.news_list.item(i)
            index = item.data(Qt.UserRole)
            if isinstance(index, int) and 0 <= index < len(self.all_news_items):
                if self.all_news_items[index] in selected_news:
                    item.setSelected(True)
        
        # 显示提示
        category_name = "未分类"
        if category_id == "military":
            category_name = "军事新闻"
        elif category_id in STANDARD_CATEGORIES:
            category_name = STANDARD_CATEGORIES[category_id]["name"]
            
        QMessageBox.information(self, "分类已更新", f"已将选中的 {len(selected_news)} 条新闻设置为 {category_name} 类别")
    
    def _view_news_detail(self, item: QListWidgetItem):
        """查看新闻详情
        
        Args:
            item: 列表项
        """
        index = item.data(Qt.UserRole)
        if isinstance(index, int) and 0 <= index < len(self.all_news_items):
            news = self.all_news_items[index]
            
            # 创建详情对话框
            from src.ui.news_detail_dialog import NewsDetailDialog
            from src.models import NewsArticle
            
            # 转换为NewsArticle对象
            article = NewsArticle(
                title=news.get('title', '无标题'),
                content=news.get('content', ''),
                summary=news.get('summary', ''),
                link=news.get('link', ''),
                source_name=news.get('source_name', '未知来源'),
                publish_time=news.get('publish_time', datetime.now())
            )
            
            dialog = NewsDetailDialog(article, self)
            dialog.show()
    
    def _analyze_single_news(self, item: QListWidgetItem):
        """分析单条新闻
        
        Args:
            item: 列表项
        """
        # 清除当前选择
        self.news_list.clearSelection()
        
        # 选中指定项
        item.setSelected(True)
        
        # 执行分析
        self._analyze_selected_news()
    
    def closeEvent(self, event):
        """处理窗口关闭事件"""
        self.rejected_and_deleted.emit()
        event.accept()