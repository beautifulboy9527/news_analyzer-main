# src/ui/integrated_analysis_panel_refactored.py
"""
新闻分析整合面板（重构版）

整合新闻相似度分析、重要程度和立场分析功能，
并提供新闻自动分类功能，支持按类别分组查看和分析新闻。
采用MVC架构，提高代码可维护性和可测试性。
"""

import logging
import os
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
from PySide6.QtWidgets import QApplication

from src.models import NewsArticle
from src.llm.llm_service import LLMService
from src.storage.news_storage import NewsStorage
from src.ui.components.analysis_visualizer import AnalysisVisualizer
from src.ui.integrated_analysis_panel_prompt_manager import PromptManagerWidget

# 导入重构后的模块
from src.core.news_data_processor import NewsDataProcessor
from src.core.news_analysis_engine import NewsAnalysisEngine
from src.ui.components.analysis_panel_components import NewsListManager, CategoryTreeManager, GroupTreeManager
from src.ui.controllers.integrated_analysis_controller import IntegratedAnalysisController


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
        
        # 创建控制器和组件
        self.controller = IntegratedAnalysisController(storage, llm_service, self)
        
        # 初始化UI
        self._init_ui()
        
        # 连接控制器信号
        self._connect_controller_signals()
        
        # 加载新闻数据
        if self.storage and self.llm_service:
            self.controller.load_news_data()
    
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
        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        control_layout.addWidget(self.refresh_button)
        
        # 分析类型选择
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
        self.analyze_button.clicked.connect(self._on_analyze_clicked)
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
        self.category_tree.itemClicked.connect(self._on_category_clicked)
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
        self.news_list.itemSelectionChanged.connect(self._on_news_selection_changed)
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
        self.select_all_button.clicked.connect(self._on_select_all_clicked)
        selection_layout.addWidget(self.select_all_button)
        
        self.deselect_all_button = QPushButton(QIcon.fromTheme("edit-clear", QIcon("")), "取消全选")
        self.deselect_all_button.setStyleSheet(button_style)
        self.deselect_all_button.clicked.connect(self._on_deselect_all_clicked)
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
        self.auto_group_button.clicked.connect(self._on_auto_group_clicked)
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
        
        # 添加提示词管理组件
        self.prompt_manager_widget = PromptManagerWidget(self.llm_service.prompt_manager)
        self.prompt_manager_widget.prompt_selected.connect(self._on_prompt_selected)
        self.prompt_manager_widget.prompt_edited.connect(self._on_prompt_edited)
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
        self.copy_button.clicked.connect(self._on_copy_clicked)
        self.copy_button.setEnabled(False)
        result_action_layout.addWidget(self.copy_button)
        
        self.save_button = QPushButton(QIcon.fromTheme("document-save", QIcon("")), "保存结果")
        self.save_button.setStyleSheet(button_style)
        self.save_button.clicked.connect(self._on_save_clicked)
        self.save_button.setEnabled(False)
        result_action_layout.addWidget(self.save_button)
        
        self.clear_button = QPushButton(QIcon.fromTheme("edit-clear", QIcon("")), "清空结果")
        self.clear_button.setStyleSheet(button_style)
        self.clear_button.clicked.connect(self._on_clear_clicked)
        self.clear_button.setEnabled(False)
        result_action_layout.addWidget(self.clear_button)
        
        right_layout.addLayout(result_action_layout)
        
        # 添加左右面板到分割器
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([400, 600])  # 设置初始分割比例
        
        layout.addWidget(main_splitter, 1)  # 1表示拉伸因子
        
        # --- 底部关闭按钮 ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("关闭")
        close_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        close_button.setStyleSheet("""
            QPushButton { 
                background-color: #F0F0F0; 
                border: 1px solid #C0C0C0; 
                border-radius: 4px; 
                padding: 8px 16px; 
                font-weight: bold;
            }
            QPushButton:hover { 
                background-color: #E0E0E0;
            }
            QPushButton:pressed { 
                background-color: #D0D0D0;
            }
        """)
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        # 禁用控件（如果服务无效）
        if not self.storage or not self.llm_service:
            self.refresh_button.setEnabled(False)
            self.analyze_button.setEnabled(False)
            self.auto_group_button.setEnabled(False)
            self.news_list.setEnabled(False)
            self.category_tree.setEnabled(False)
        
        # 创建UI组件管理器
        self.news_list_manager = NewsListManager(self.news_list)
        self.category_tree_manager = CategoryTreeManager(self.category_tree)
        self.group_tree_manager = GroupTreeManager(self.group_tree)
        
        # 设置控制器的UI管理器
        self.controller.set_ui_managers(
            self.news_list_manager,
            self.category_tree_manager,
            self.group_tree_manager
        )
    
    def _connect_controller_signals(self):
        """连接控制器信号"""
        self.controller.analysis_started.connect(self._on_analysis_started)
        self.controller.analysis_completed.connect(self._on_analysis_completed)
        self.controller.analysis_failed.connect(self._on_analysis_failed)
        
        # 设置树形控件的样式表，为选中项添加边框效果
        self.group_tree.setStyleSheet("""
            QTreeWidget::item { 
                padding: 2px;
            }
            QTreeWidget::item:selected { 
                border: 2px solid #2196F3; 
                border-radius: 4px; 
                background-color: transparent; /* 让背景色由代码控制 */
            }
        """)
        
    def _on_group_selection_changed(self):
        """处理分组树选择变化，自动选中组内所有新闻并提供视觉反馈"""
        selected_items = self.group_tree.selectedItems()
        selected_indices = []
        
        # 记录需要选中的子项
        children_to_select = []
        
        for item in selected_items:
            # 检查是否是组节点
            if item.parent() is None:
                # 是组节点，添加该组所有新闻并选中所有子项
                group_index = item.data(0, Qt.UserRole)
                if isinstance(group_index, int) and 0 <= group_index < len(self.controller.news_groups):
                    # 记录该组下的所有子项，稍后统一选中
                    for i in range(item.childCount()):
                        child = item.child(i)
                        if not child.isSelected():
                            children_to_select.append(child)
                    
                    # 添加该组所有新闻到选中列表
                    for news in self.controller.news_groups[group_index]:
                        # 找到新闻在all_news_items中的索引
                        for j, n in enumerate(self.controller.all_news_items):
                            if n is news and j not in selected_indices:
                                selected_indices.append(j)
                                break
                    
                    # 设置组项的背景色，提供即时视觉反馈
                    item.setBackground(0, QColor("#BBDEFB"))  # 使用更明显的蓝色背景
                    item.setBackground(1, QColor("#BBDEFB"))
                    font = item.font(0)
                    font.setBold(True)
                    item.setFont(0, font)
                    item.setFont(1, font)  # 确保两列都加粗
                    # 添加图标指示选中状态
                    item.setIcon(0, QIcon.fromTheme("folder-open", QIcon("")))
            else:
                # 是新闻节点，添加该新闻
                news_index = item.data(0, Qt.UserRole)
                if isinstance(news_index, int) and 0 <= news_index < len(self.controller.all_news_items) and news_index not in selected_indices:
                    selected_indices.append(news_index)
                    
                    # 设置新闻项的背景色，提供即时视觉反馈
                    item.setBackground(0, QColor("#E3F2FD"))
                    font = item.font(0)
                    font.setBold(True)
                    item.setFont(0, font)
                    # 添加图标指示选中状态
                    item.setIcon(0, QIcon.fromTheme("emblem-checked", QIcon("")))
        
        # 统一选中所有子项，避免触发多次选择变化事件
        if children_to_select:
            # 暂时断开信号连接，避免递归调用
            self.group_tree.itemSelectionChanged.disconnect(self._on_group_selection_changed)
            for child in children_to_select:
                child.setSelected(True)
                # 立即为子项设置视觉反馈
                child.setBackground(0, QColor("#E3F2FD"))
                font = child.font(0)
                font.setBold(True)
                child.setFont(0, font)
                child.setIcon(0, QIcon.fromTheme("emblem-checked", QIcon("")))
            # 重新连接信号
            self.group_tree.itemSelectionChanged.connect(self._on_group_selection_changed)
        
        # 更新控制器中的选中索引
        self.controller.selected_indices = selected_indices
        self.controller.selected_news_items = []
        
        # 更新分析按钮状态
        self.analyze_button.setEnabled(len(selected_indices) > 0)
        
        self.logger.debug(f"已选择 {len(selected_indices)} 条新闻")
        
        # 高亮显示选中的组和新闻项
        self._highlight_selected_group_items()
    
    def _highlight_selected_group_items(self):
        """高亮显示选中的组和新闻项，提供明显的视觉反馈"""
        # 暂时断开信号连接，避免递归调用
        try:
            self.group_tree.itemSelectionChanged.disconnect(self._on_group_selection_changed)
        except Exception:
            pass
            
        try:
            # 设置选中项的背景色
            for i in range(self.group_tree.topLevelItemCount()):
                group_item = self.group_tree.topLevelItem(i)
                
                # 检查组是否被选中
                is_group_selected = group_item.isSelected()
                
                # 设置组项的背景色和边框
                if is_group_selected:
                    # 使用更明显的蓝色背景
                    group_item.setBackground(0, QColor("#BBDEFB"))  # 更深的蓝色背景
                    group_item.setBackground(1, QColor("#BBDEFB"))
                    # 设置字体加粗
                    font = group_item.font(0)
                    font.setBold(True)
                    group_item.setFont(0, font)
                    group_item.setFont(1, font)
                    # 添加图标指示选中状态
                    group_item.setIcon(0, QIcon.fromTheme("folder-open", QIcon("")))
                else:
                    group_item.setBackground(0, QColor("transparent"))
                    group_item.setBackground(1, QColor("transparent"))
                    # 恢复字体
                    font = group_item.font(0)
                    font.setBold(True)  # 组标题保持加粗
                    group_item.setFont(0, font)
                    # 恢复默认图标
                    group_item.setIcon(0, QIcon.fromTheme("folder", QIcon("")))
                    
                # 处理组内的新闻项
                child_selected_count = 0
                for j in range(group_item.childCount()):
                    news_item = group_item.child(j)
                    if news_item.isSelected():
                        # 使用更明显的蓝色背景
                        news_item.setBackground(0, QColor("#E3F2FD"))
                        # 设置字体加粗
                        font = news_item.font(0)
                        font.setBold(True)
                        news_item.setFont(0, font)
                        # 添加图标指示选中状态
                        news_item.setIcon(0, QIcon.fromTheme("emblem-checked", QIcon("")))
                        child_selected_count += 1
                    else:
                        news_item.setBackground(0, QColor("transparent"))
                        # 恢复字体
                        font = news_item.font(0)
                        font.setBold(False)
                        news_item.setFont(0, font)
                        # 恢复默认图标
                        news_item.setIcon(0, QIcon.fromTheme("text-x-generic", QIcon("")))
                
                # 如果组内所有新闻都被选中，确保组也被选中
                if child_selected_count == group_item.childCount() and group_item.childCount() > 0 and not is_group_selected:
                    group_item.setSelected(True)
                    # 立即应用视觉效果
                    group_item.setBackground(0, QColor("#BBDEFB"))
                    group_item.setBackground(1, QColor("#BBDEFB"))
                    font = group_item.font(0)
                    font.setBold(True)
                    group_item.setFont(0, font)
                    group_item.setFont(1, font)
                    group_item.setIcon(0, QIcon.fromTheme("folder-open", QIcon("")))
                # 如果组内有部分新闻被选中，显示部分选中状态
                elif child_selected_count > 0 and child_selected_count < group_item.childCount() and not is_group_selected:
                    # 使用浅色背景表示部分选中
                    group_item.setBackground(0, QColor("#E1F5FE"))  # 更浅的蓝色背景
                    group_item.setBackground(1, QColor("#E1F5FE"))
                    # 设置字体为斜体加粗，表示部分选中
                    font = group_item.font(0)
                    font.setBold(True)
                    font.setItalic(True)
                    group_item.setFont(0, font)
                    group_item.setFont(1, font)
                    # 使用特殊图标表示部分选中
                    group_item.setIcon(0, QIcon.fromTheme("folder-visiting", QIcon.fromTheme("folder", QIcon("")))) 
                    
            # 确保选择状态的一致性
            self._ensure_selection_consistency()
        finally:
            # 重新连接信号
            self.group_tree.itemSelectionChanged.connect(self._on_group_selection_changed)
    
    def _ensure_selection_consistency(self):
        """确保组选择状态与子项选择状态的一致性"""
        # 检查每个组，根据子项选中状态更新组的选中状态和视觉效果
        for i in range(self.group_tree.topLevelItemCount()):
            group_item = self.group_tree.topLevelItem(i)
            
            # 统计选中的子项数量
            selected_count = 0
            total_count = group_item.childCount()
            
            for j in range(total_count):
                if group_item.child(j).isSelected():
                    selected_count += 1
            
            # 根据选中比例设置不同的视觉效果
            if total_count > 0:
                if selected_count == total_count and not group_item.isSelected():
                    # 所有子项都被选中，确保组也被选中
                    group_item.setSelected(True)
                    # 应用完全选中的视觉效果
                    group_item.setBackground(0, QColor("#BBDEFB"))
                    group_item.setBackground(1, QColor("#BBDEFB"))
                    font = group_item.font(0)
                    font.setBold(True)
                    font.setItalic(False)
                    group_item.setFont(0, font)
                    group_item.setFont(1, font)
                    group_item.setIcon(0, QIcon.fromTheme("folder-open", QIcon("")))
                elif selected_count > 0 and selected_count < total_count:
                    # 部分子项被选中，应用部分选中的视觉效果
                    if not group_item.isSelected():
                        group_item.setBackground(0, QColor("#E1F5FE"))  # 更浅的蓝色背景
                        group_item.setBackground(1, QColor("#E1F5FE"))
                        font = group_item.font(0)
                        font.setBold(True)
                        font.setItalic(True)  # 斜体表示部分选中
                        group_item.setFont(0, font)
                        group_item.setFont(1, font)
                        group_item.setIcon(0, QIcon.fromTheme("folder-visiting", QIcon.fromTheme("folder", QIcon("")))) 
                elif selected_count == 0 and group_item.isSelected():
                    # 如果没有子项被选中但组被选中，保持组的选中状态
                    # 这种情况可能是用户直接点击了组
                    pass
                

    
    def _on_refresh_clicked(self):
        """处理刷新按钮点击事件"""
        self.controller.load_news_data()
    
    def _on_analysis_type_changed(self, analysis_type: str):
        """处理分析类型变化事件"""
        # 使用提示词管理组件的方法设置对应的模板
        if hasattr(self, 'prompt_manager_widget'):
            # 根据分析类型选择对应的模板
            template_map = {
                "新闻相似度分析": "similarity_analysis",
                "增强型多特征分析": "enhanced_analysis",
                "重要程度和立场分析": "importance_stance_analysis",
                "深度分析": "deep_analysis",
                "关键观点": "key_points",
                "事实核查": "fact_check",
                "摘要": "summary"
            }
            template_key = template_map.get(analysis_type)
            if template_key:
                self.prompt_manager_widget.select_template(template_key)
    
    def _on_analysis_started(self):
        """处理分析开始事件"""
        # 禁用分析按钮和其他相关控件
        self.analyze_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.auto_group_button.setEnabled(False)
        
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 设置为循环模式
        
        # 清空之前的结果
        self.result_edit.clear()
        self.result_edit.setPlaceholderText("正在进行分析，请稍候...")
        
        # 禁用结果操作按钮
        self.copy_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.clear_button.setEnabled(False)
    
    def _on_analysis_completed(self, results: dict):
        """处理分析完成事件"""
        try:
            # 隐藏进度条
            self.progress_bar.setVisible(False)
            
            # 重新启用按钮
            self.analyze_button.setEnabled(True)
            self.refresh_button.setEnabled(True)
            self.auto_group_button.setEnabled(True)
            
            # 更新分析结果显示
            if results:
                # 提取分析结果
                analysis_text = results.get('formatted_text', results.get('analysis', ''))
                importance_scores = results.get('importance_scores', {})
                stance_scores = results.get('stance_scores', {})
                
                # 更新文本结果
                if analysis_text:
                    self.result_edit.setPlainText(analysis_text)
                    # 启用结果操作按钮
                    self.copy_button.setEnabled(True)
                    self.save_button.setEnabled(True)
                    self.clear_button.setEnabled(True)
                
                # 更新可视化组件
                if importance_scores or stance_scores:
                    self.analysis_visualizer.update_visualization(
                        importance_scores=importance_scores,
                        stance_scores=stance_scores
                    )
            else:
                self.result_edit.setPlainText("分析完成，但未返回结果。")
                
        except Exception as e:
            self.logger.error(f"处理分析结果时出错: {str(e)}")
            QMessageBox.warning(self, "错误", f"处理分析结果时出错: {str(e)}")
    
    def _on_analysis_failed(self, error_msg: str):
        """处理分析失败事件"""
        # 隐藏进度条
        self.progress_bar.setVisible(False)
        
        # 重新启用按钮
        self.analyze_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.auto_group_button.setEnabled(True)
        
        # 显示错误信息
        self.result_edit.setPlainText(f"分析失败: {error_msg}")
        QMessageBox.critical(self, "分析失败", f"新闻分析失败: {error_msg}")
        
        self.logger.error(f"新闻分析失败: {error_msg}")
    
    def _on_copy_clicked(self):
        """处理复制结果按钮点击事件"""
        text = self.result_edit.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            QMessageBox.information(self, "成功", "分析结果已复制到剪贴板")
    
    def _on_save_clicked(self):
        """处理保存结果按钮点击事件"""
        try:
            # 获取当前时间作为文件名
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"news_analysis_{current_time}.txt"
            
            # 获取分析结果文本
            text = self.result_edit.toPlainText()
            
            # 保存到文件
            save_path = os.path.join(os.path.expanduser("~"), "Documents", filename)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            QMessageBox.information(self, "成功", f"分析结果已保存到: {save_path}")
            
        except Exception as e:
            self.logger.error(f"保存分析结果时出错: {str(e)}")
            QMessageBox.warning(self, "错误", f"保存分析结果时出错: {str(e)}")
    
    def _on_clear_clicked(self):
        """处理清空结果按钮点击事件"""
        self.result_edit.clear()
        self.analysis_visualizer.clear()
        self.copy_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.clear_button.setEnabled(False)

    def _on_analyze_clicked(self):
        """处理分析按钮点击事件"""
        try:
            # 获取当前选择的分析类型
            analysis_type = self.analysis_type.currentText()
            
            # 调用控制器进行分析
            self.controller.analyze_selected_news(analysis_type)
            
        except Exception as e:
            self.logger.error(f"启动分析时出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"启动分析时出错: {str(e)}")