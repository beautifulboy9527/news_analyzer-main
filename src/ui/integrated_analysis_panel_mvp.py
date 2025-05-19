# src/ui/integrated_analysis_panel_mvp.py
"""
新闻分析整合面板 (MVP模式)

整合新闻相似度分析、重要程度和立场分析功能，
并提供新闻自动分类功能，支持按类别分组查看和分析新闻。
采用MVP(Model-View-Presenter)架构，提高代码可维护性和可测试性。
"""

import logging
from typing import List, Dict, Optional

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QLabel, QTextEdit, QPushButton,
                             QSplitter, QMessageBox, QProgressBar, QComboBox,
                             QTabWidget, QTreeWidget, QTreeWidgetItem, QMenu,
                             QHeaderView, QWidget)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QCursor

from src.models import NewsArticle
from src.llm.llm_service import LLMService
from src.storage.news_storage import NewsStorage
from src.ui.components.analysis_visualizer import AnalysisVisualizer
from src.ui.integrated_analysis_panel_prompt_manager import PromptManagerWidget

# 导入MVP架构组件
from src.ui.controllers.integrated_analysis_controller import IntegratedAnalysisController
from src.ui.components.analysis_panel_components import (
    NewsListManager, CategoryTreeManager, GroupTreeManager
)


class IntegratedAnalysisPanel(QDialog):
    """新闻分析整合面板，采用MVP架构，集成相似度分析、重要程度和立场分析，并支持自动分类"""
    
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
        
        # 创建Presenter(控制器)
        self.presenter = IntegratedAnalysisController(storage, llm_service, self)
        
        # 初始化UI组件
        self._init_ui_components()
        
        # 连接信号和槽
        self._connect_signals()
        
        # 加载新闻数据
        if self.storage and self.llm_service:
            self.presenter.load_news_data()
    
    def _init_ui_components(self):
        """初始化UI组件"""
        # 主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # --- 顶部控制区域 ---
        control_layout = self._create_control_area()
        layout.addLayout(control_layout)
        
        # --- 进度条 ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # --- 主体区域 ---
        main_splitter = QSplitter(Qt.Horizontal)
        
        # 左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 左侧分割器（分类树和新闻列表）
        left_splitter = QSplitter(Qt.Vertical)
        
        # 分类树
        category_widget = self._create_category_tree()
        left_splitter.addWidget(category_widget)
        
        # 新闻列表区域
        news_list_widget = self._create_news_list_area()
        left_splitter.addWidget(news_list_widget)
        
        # 设置左侧分割器的初始大小
        left_splitter.setSizes([200, 400])
        left_layout.addWidget(left_splitter)
        
        # 右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 右侧分析结果区域
        self._create_analysis_result_area(right_layout)
        
        # 添加左右面板到主分割器
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([400, 600])  # 设置初始大小比例
        
        layout.addWidget(main_splitter)
    
    def _create_control_area(self) -> QHBoxLayout:
        """创建顶部控制区域"""
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
            QPushButton:disabled { 
                background-color: #CCCCCC; 
                color: #666666;
            }
        """)
        self.analyze_button.setEnabled(False)  # 初始禁用
        control_layout.addWidget(self.analyze_button)
        
        return control_layout
    
    def _create_category_tree(self) -> QWidget:
        """创建分类树区域"""
        category_widget = QWidget()
        category_layout = QVBoxLayout(category_widget)
        category_layout.setContentsMargins(0, 0, 0, 0)
        
        # 添加标题和说明
        cat_header_layout = QVBoxLayout()
        cat_title_label = QLabel("新闻分类:")
        cat_title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        cat_header_layout.addWidget(cat_title_label)
        
        cat_info_label = QLabel("点击类别查看该类别下的新闻")
        cat_info_label.setStyleSheet("color: #666666; font-size: 12px;")
        cat_header_layout.addWidget(cat_info_label)
        category_layout.addLayout(cat_header_layout)
        
        # 分类树控件
        self.category_tree = QTreeWidget()
        self.category_tree.setHeaderLabel("类别")
        self.category_tree.setMinimumHeight(150)
        self.category_tree.setStyleSheet("""
            QTreeWidget { 
                border: 1px solid #C4C4C4; 
                border-radius: 4px; 
                padding: 2px;
            }
            QTreeWidget::item:selected { 
                background-color: #E3F2FD; 
                color: #000000;
            }
        """)
        category_layout.addWidget(self.category_tree)
        
        # 创建分类树管理器
        self.category_tree_manager = CategoryTreeManager(self.category_tree)
        
        return category_widget
    
    def _create_news_list_area(self) -> QWidget:
        """创建新闻列表区域"""
        news_list_widget = QWidget()
        news_list_layout = QVBoxLayout(news_list_widget)
        news_list_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建标签页控件
        self.news_tab = QTabWidget()
        self.news_tab.setStyleSheet("""
            QTabWidget::pane { 
                border: 1px solid #C4C4C4; 
                border-radius: 3px;
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
        
        # 添加标题和说明
        header_layout = QVBoxLayout()
        title_label = QLabel("新闻列表:")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(title_label)
        
        info_label = QLabel("选择多条新闻进行分析，双击查看详情")
        info_label.setStyleSheet("color: #666666; font-size: 12px;")
        header_layout.addWidget(info_label)
        normal_list_layout.addLayout(header_layout)
        
        # 新闻列表控件
        self.news_list = QListWidget()
        self.news_list.setAlternatingRowColors(True)
        self.news_list.setSelectionMode(QListWidget.ExtendedSelection)  # 允许多选
        self.news_list.setStyleSheet("""
            QListWidget { 
                border: 1px solid #C4C4C4; 
                border-radius: 4px; 
                padding: 2px;
            }
            QListWidget::item:selected { 
                background-color: #E3F2FD; 
                color: #000000;
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
        
        # 添加标题和说明
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
            QTreeWidget::item:selected { 
                background-color: #E3F2FD; 
                color: #000000;
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
        """)
        self.auto_group_button.setToolTip("根据标题相似度自动分组相关新闻")
        selection_layout.addWidget(self.auto_group_button)
        
        news_list_layout.addLayout(selection_layout)
        
        return news_list_widget
    
    def _create_analysis_result_area(self, right_layout: QVBoxLayout):
        """创建分析结果区域"""
        # 添加提示词管理组件
        self.prompt_manager_widget = PromptManagerWidget(self.llm_service.prompt_manager)
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
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 设置UI管理器到控制器
        self.presenter.set_ui_managers(
            self.news_list_manager,
            self.category_tree_manager,
            self.group_tree_manager
        )
        
        # 控制器信号连接
        self.presenter.analysis_started.connect(self._on_analysis_started)
        self.presenter.analysis_completed.connect(self._on_analysis_completed)
        self.presenter.analysis_failed.connect(self._on_analysis_failed)
        self.presenter.progress_updated.connect(self._on_progress_updated)
        
        # UI组件信号连接
        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        self.analysis_type.currentTextChanged.connect(self._on_analysis_type_changed)
        self.analyze_button.clicked.connect(self._on_analyze_clicked)
        self.category_tree.itemClicked.connect(self._on_category_selected)
        self.news_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.news_list.customContextMenuRequested.connect(self._show_context_menu)
        self.news_tab.currentChanged.connect(self._on_tab_changed)
        self.group_tree.itemSelectionChanged.connect(self._on_group_selection_changed)
        self.group_tree.customContextMenuRequested.connect(self._show_group_context_menu)
        self.select_all_button.clicked.connect(self._on_select_all_clicked)
        self.deselect_all_button.clicked.connect(self._on_deselect_all_clicked)
        self.auto_group_button.clicked.connect(self._on_auto_group_clicked)
        self.prompt_manager_widget.prompt_selected.connect(self._on_prompt_selected)
        self.prompt_manager_widget.prompt_edited.connect(self._on_prompt_edited)
    
    # ===== 事件处理方法 =====
    
    def _on_refresh_clicked(self):
        """处理刷新按钮点击事件"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10)
        self.presenter.load_news_data()
        self.progress_bar.setValue(100)
        self.progress_bar.setVisible(False)
    
    def _on_analysis_type_changed(self, analysis_type: str):
        """处理分析类型变更事件"""
        self.presenter.set_analysis_type(analysis_type)
    
    def _on_analyze_clicked(self):
        """处理分析按钮点击事件"""
        analysis_type = self.analysis_type.currentText()
        template_name = self.prompt_manager_widget.get_current_template_name()
        template_content = self.prompt_manager_widget.get_current_template_content()
        self.presenter.analyze_selected_news(analysis_type, template_name, template_content)
    
    def _on_category_selected(self, item, column):
        """处理分类选择事件"""
        category_id = item.data(0, Qt.UserRole)
        if category_id:
            self.presenter.on_category_selected(category_id)
            self.news_tab.setCurrentIndex(0)  # 切换到普通列表标签页
    
    def _on_selection_changed(self):
        """处理新闻选择变化事件"""
        indices = self.news_list_manager.get_selected_news_indices()
        self.presenter.on_news_selection_changed(indices)
        self.analyze_button.setEnabled(len(indices) > 0)
    
    def _on_group_selection_changed(self):
        """处理分组树选择变化事件"""
        indices = self.group_tree_manager.get_selected_news_indices()
        self.presenter.on_group_selection_changed(indices)
        self.analyze_button.setEnabled(len(indices) > 0)
    
    def _on_tab_changed(self, index):
        """处理标签页切换事件"""
        # 根据标签页更新选择按钮状态
        is_normal_list = (index == 0)
        self.select_all_button.setEnabled(is_normal_list)
        self.deselect_all_button.setEnabled(is_normal_list)
    
    def _show_context_menu(self, pos):
        """显示新闻列表上下文菜单"""
        if not self.news_list.selectedItems():
            return
            
        menu = QMenu(self)
        view_action = menu.addAction("查看详情")
        analyze_action = menu.addAction("分析选中新闻")
        
        action = menu.exec_(QCursor.pos())
        if action == view_action:
            self._view_selected_news_details()
        elif action == analyze_action:
            self._on_analyze_clicked()
    
    def _show_group_context_menu(self, pos):
        """显示分组树上下文菜单"""
        selected_items = self.group_tree.selectedItems()
        if not selected_items:
            return
            
        menu = QMenu(self)
        view_action = menu.addAction("查看详情")
        analyze_action = menu.addAction("分析选中新闻")
        
        action = menu.exec_(QCursor.pos())
        if action == view_action:
            self._view_selected_group_news_details()
        elif action == analyze_action:
            self._on_analyze_clicked()
    
    def _on_select_all_clicked(self):
        """处理全选按钮点击事件"""
        self.news_list_manager.select_all_news()
    
    def _on_deselect_all_clicked(self):
        """处理取消全选按钮点击事件"""
        self.news_list_manager.deselect_all_news()
    
    def _on_auto_group_clicked(self):
        """处理自动分组按钮点击事件"""
        method = self.clustering_method.currentData()
        self.presenter.auto_group_news(method)
    
    def _on_prompt_selected(self, template_name: str, template_content: str):
        """处理提示词模板选择事件"""
        self.presenter.set_prompt_template(template_name, template_content)
    
    def _on_prompt_edited(self, content: str):
        """处理提示词内容编辑事件"""
        self.presenter.set_prompt_content(content)
    
    def _view_selected_news_details(self):
        """查看选中新闻详情"""
        indices = self.news_list_manager.get_selected_news_indices()
        if indices:
            self.presenter.view_news_details(indices[0])
    
    def _view_selected_group_news_details(self):
        """查看选中分组新闻详情"""
        indices = self.group_tree_manager.get_selected_news_indices()
        if indices:
            self.presenter.view_news_details(indices[0])
    
    # ===== 控制器回调方法 =====
    
    def _on_analysis_started(self):
        """分析开始回调"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.analyze_button.setEnabled(False)
        self.result_edit.setPlaceholderText("正在分析中，请稍候...")
    
    def _on_analysis_completed(self, result: Dict):
        """分析完成回调"""
        self.progress_bar.setValue(100)
        self.progress_bar.setVisible(False)
        self.analyze_button.setEnabled(True)
        
        # 更新分析结果
        analysis_text = result.get('analysis', '')
        self.result_edit.setText(analysis_text)
        
        # 更新可视化组件
        importance = result.get('importance', 0)
        stance = result.get('stance', 0)
        self.analysis_visualizer.update_metrics(importance, stance)
        
        # 发送分析完成信号
        self.analysis_completed.emit(result)
    
    def _on_analysis_failed(self, error_msg: str):
        """分析失败回调"""
        self.progress_bar.setVisible(False)
        self.analyze_button.setEnabled(True)
        self.result_edit.setText(f"分析失败: {error_msg}")
        QMessageBox.critical(self, "分析错误", f"分析过程中出错: {error_msg}")
    
    def _on_progress_updated(self, current: int, total: int):
        """进度更新回调"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
    
    def closeEvent(self, event):
        """处理窗口关闭事件"""
        self.rejected_and_deleted.emit()
        event.accept()