# src/ui/modules/analysis_panel_ui_builder.py
"""
分析面板UI构建器

负责构建新闻分析整合面板的各个UI部分，
将UI构建逻辑从主面板类中分离，提高代码可维护性。
"""

import logging
from typing import Dict, List, Optional

from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QLabel, QTextEdit, QPushButton,
                             QSplitter, QMessageBox, QSizePolicy, QWidget,
                             QCheckBox, QGroupBox, QProgressBar, QComboBox,
                             QTabWidget, QTreeWidget, QTreeWidgetItem, QMenu,
                             QHeaderView)
from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtGui import QIcon, QFont, QAction, QCursor, QColor

from src.ui.components.analysis_panel_components import (
    NewsListManager, CategoryTreeManager, GroupTreeManager
)
from src.ui.components.analysis_visualizer import AnalysisVisualizer
from src.ui.integrated_analysis_panel_prompt_manager import PromptManagerWidget


class AnalysisPanelUIBuilder:
    """
    分析面板UI构建器，负责构建新闻分析整合面板的各个UI部分
    """
    
    def __init__(self, panel):
        """
        初始化UI构建器
        
        Args:
            panel: 父面板实例
        """
        self.panel = panel
        self.logger = logging.getLogger('news_analyzer.ui.modules.analysis_panel_ui_builder')
        
        # UI组件管理器
        self.news_list_manager = None
        self.category_tree_manager = None
        self.group_tree_manager = None
        
        # UI组件引用
        self.refresh_button = None
        self.analysis_type = None
        self.clustering_method = None
        self.analyze_button = None
        self.category_tree = None
        self.news_list = None
        self.news_tab = None
        self.group_tree = None
        self.select_all_button = None
        self.deselect_all_button = None
        self.auto_group_button = None
        self.prompt_manager_widget = None
        self.analysis_visualizer = None
        self.result_edit = None
        self.export_button = None
        self.close_button = None
    
    def build_control_area(self) -> QHBoxLayout:
        """
        构建顶部控制区域
        
        Returns:
            控制区域布局
        """
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
        self.analyze_button.setEnabled(False)  # 初始禁用
        control_layout.addWidget(self.analyze_button)
        
        return control_layout
    
    def build_left_panel(self, left_layout: QVBoxLayout) -> QSplitter:
        """
        构建左侧面板（分类树和新闻列表）
        
        Args:
            left_layout: 左侧面板布局
            
        Returns:
            左侧分割器
        """
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
        category_layout.addWidget(self.category_tree)
        
        # 创建分类树管理器
        self.category_tree_manager = CategoryTreeManager(self.category_tree)
        
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
        self.news_list.setContextMenuPolicy(Qt.CustomContextMenu)
        normal_list_layout.addWidget(self.news_list)
        
        # 创建新闻列表管理器
        self.news_list_manager = NewsListManager(self.news_list)
        
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
        """)
        self.group_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        # 设置列宽
        self.group_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.group_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        grouped_list_layout.addWidget(self.group_tree)
        
        # 创建分组树管理器
        self.group_tree_manager = GroupTreeManager(self.group_tree)
        
        # 添加标签页
        self.news_tab.addTab(normal_list_widget, "普通列表")
        self.news_tab.addTab(grouped_list_widget, "分组视图")
        
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
        selection_layout.addWidget(self.select_all_button)
        
        self.deselect_all_button = QPushButton(QIcon.fromTheme("edit-clear", QIcon("")), "取消全选")
        self.deselect_all_button.setStyleSheet(button_style)
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
        selection_layout.addWidget(self.auto_group_button)
        
        news_list_layout.addLayout(selection_layout)
        
        left_splitter.addWidget(news_list_widget)
        
        # 设置左侧分割器的初始大小
        left_splitter.setSizes([200, 400])
        
        return left_splitter
    
    def build_right_panel(self, right_layout: QVBoxLayout):
        """
        构建右侧面板（提示词管理和分析结果）
        
        Args:
            right_layout: 右侧面板布局
        """
        # 添加提示词管理组件
        self.prompt_manager_widget = PromptManagerWidget(self.panel.llm_service.prompt_manager)
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
    
    def build_bottom_area(self) -> QHBoxLayout:
        """
        构建底部按钮区域
        
        Returns:
            底部区域布局
        """
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 10, 0, 0)
        
        # 导出按钮
        self.export_button = QPushButton(QIcon.fromTheme("document-save", QIcon("")), "导出分析结果")
        self.export_button.setStyleSheet("""
            QPushButton { 
                background-color: #2196F3; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                padding: 8px 16px; 
                font-weight: bold;
            }
            QPushButton:hover { 
                background-color: #0b7dda;
            }
            QPushButton:pressed { 
                background-color: #0a69b7;
            }
            QPushButton:disabled { 
                background-color: #CCCCCC; 
                color: #666666;
            }
        """)
        self.export_button.setEnabled(False)  # 初始禁用
        bottom_layout.addWidget(self.export_button)
        
        bottom_layout.addStretch()
        
        # 关闭按钮
        self.close_button = QPushButton(QIcon.fromTheme("window-close", QIcon("")), "关闭")
        self.close_button.setStyleSheet("""
            QPushButton { 
                background-color: #F0F0F0; 
                border: 1px solid #C0C0C0; 
                border-radius: 4px; 
                padding: 8px 16px; 
            }
            QPushButton:hover { 
                background-color: #E0E0E0;
            }
            QPushButton:pressed { 
                background-color: #D0D0D0;
            }
        """)
        bottom_layout.addWidget(self.close_button)
        
        return bottom_layout
    
    def get_ui_components(self) -> Dict:
        """
        获取所有UI组件的引用
        
        Returns:
            UI组件字典
        """
        return {
            "refresh_button": self.refresh_button,
            "analysis_type": self.analysis_type,
            "clustering_method": self.clustering_method,
            "analyze_button": self.analyze_button,
            "category_tree": self.category_tree,
            "news_list": self.news_list,
            "news_tab": self.news_tab,
            "group_tree": self.group_tree,
            "select_all_button": self.select_all_button,
            "deselect_all_button": self.deselect_all_button,
            "auto_group_button": self.auto_group_button,
            "prompt_manager_widget": self.prompt_manager_widget,
            "analysis_visualizer": self.analysis_visualizer,
            "result_edit": self.result_edit,
            "export_button": self.export_button,
            "close_button": self.close_button
        }
    
    def get_managers(self) -> Dict:
        """
        获取所有UI组件管理器的引用
        
        Returns:
            UI组件管理器字典
        """
        return {
            "news_list_manager": self.news_list_manager,
            "category_tree_manager": self.category_tree_manager,
            "group_tree_manager": self.group_tree_manager
        }