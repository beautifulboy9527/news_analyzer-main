# src/ui/classification_panel.py
"""
信息分类与整理核查面板

实现新闻事件的自动聚类，将不同信源的相似报道整理为单一事件项，按分类展示。
支持用户查看事件详情、媒体原文，并通过LLM进行深入分析（重要性、立场、事实与观点）。
提供自定义Prompt功能，历史记录管理，数据导入导出。
"""

import logging
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple, Any

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QLabel, QTextEdit, QPushButton,
                             QSplitter, QMessageBox, QSizePolicy, QTabWidget,
                             QTreeWidget, QTreeWidgetItem, QMenu, QHeaderView,
                             QComboBox, QProgressBar, QDialog, QFileDialog,
                             QGroupBox, QCheckBox, QLineEdit)
from PySide6.QtCore import Qt, Signal, QSize, QPoint, Slot
from PySide6.QtGui import QIcon, QFont, QAction, QCursor, QColor

from src.models import NewsArticle
from src.llm.llm_service import LLMService
from src.llm.prompt_manager import PromptManager
from src.storage.news_storage import NewsStorage
from src.core.news_clusterer import NewsClusterer
from src.core.event_analyzer import EventAnalyzer
from src.collectors.categories import STANDARD_CATEGORIES
from src.ui.components.analysis_visualizer import AnalysisVisualizer


class ClassificationPanel(QWidget):
    """信息分类与整理核查面板，实现新闻事件聚类、分类展示和LLM分析"""
    
    # 定义信号
    analysis_completed = Signal(dict)
    status_message = Signal(str)
    token_usage_updated = Signal(int)
    
    def __init__(self, storage: NewsStorage, llm_service: LLMService, prompt_manager: PromptManager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.classification_panel')
        
        # 验证传入的服务实例
        if not storage or not isinstance(storage, NewsStorage):
            self.logger.error("传入的 storage 无效！新闻分析功能将无法使用。")
            QMessageBox.critical(self, "错误", "存储服务不可用，无法加载新闻数据。")
            self.storage = None
        else:
            self.storage = storage
            
        if not llm_service or not isinstance(llm_service, LLMService):
            self.logger.error("传入的 llm_service 无效！AI分析功能将无法使用。")
            QMessageBox.warning(self, "警告", "LLM服务不可用，无法进行AI分析。")
            self.llm_service = None
        else:
            self.llm_service = llm_service
            
        if not prompt_manager or not isinstance(prompt_manager, PromptManager):
            self.logger.error("传入的 prompt_manager 无效！自定义Prompt功能将无法使用。")
            QMessageBox.warning(self, "警告", "Prompt管理器不可用，无法使用自定义Prompt。")
            self.prompt_manager = None
        else:
            self.prompt_manager = prompt_manager
        
        # 初始化聚类器和分析器
        self.clusterer = NewsClusterer()
        self.event_analyzer = EventAnalyzer(llm_service=self.llm_service, prompt_manager=self.prompt_manager)
        
        # 初始化数据
        self.all_news_items: List[Dict] = []
        self.events: List[Dict] = []  # 聚类后的事件列表
        self.categorized_events: Dict[str, List[Dict]] = {}  # 按类别分类的事件
        self.current_category = ""  # 当前选中的类别
        self.current_event = None  # 当前选中的事件
        self.analysis_results: Dict[str, Dict] = {}  # 存储分析结果，键为事件ID
        self.history_records: List[Dict] = []  # 历史记录
        self.custom_prompts: Dict[str, str] = {}  # 自定义Prompt，键为名称
        
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
        
        # --- 顶部工具栏 ---
        toolbar_layout = QHBoxLayout()
        
        # 刷新按钮
        self.refresh_button = QPushButton(QIcon.fromTheme("view-refresh", QIcon("")), " 刷新")
        self.refresh_button.setToolTip("重新加载新闻数据并聚类")
        self.refresh_button.clicked.connect(self._load_news_data)
        toolbar_layout.addWidget(self.refresh_button)
        
        # 设置按钮
        self.settings_button = QPushButton(QIcon.fromTheme("preferences-system", QIcon("")), " 设置")
        self.settings_button.setToolTip("打开Prompt管理窗口")
        self.settings_button.clicked.connect(self._show_prompt_manager)
        toolbar_layout.addWidget(self.settings_button)
        
        # 导出按钮
        self.export_button = QPushButton(QIcon.fromTheme("document-save", QIcon("")), " 导出")
        self.export_button.setToolTip("导出分析结果")
        self.export_button.clicked.connect(self._export_results)
        toolbar_layout.addWidget(self.export_button)
        
        # 搜索框
        toolbar_layout.addWidget(QLabel("搜索:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入关键词过滤事件")
        self.search_input.textChanged.connect(self._filter_events)
        toolbar_layout.addWidget(self.search_input)
        
        layout.addLayout(toolbar_layout)
        
        # --- 进度条 ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # --- 主体区域 ---
        main_splitter = QSplitter(Qt.Horizontal)
        
        # --- 左侧导航栏 ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 分类筛选
        left_layout.addWidget(QLabel("分类筛选:"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("全部分类", "all")
        for cat_id, cat_info in STANDARD_CATEGORIES.items():
            self.category_combo.addItem(cat_info["name"], cat_id)
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        left_layout.addWidget(self.category_combo)
        
        # 立场标签云
        self.stance_group = QGroupBox("立场标签")
        stance_layout = QVBoxLayout(self.stance_group)
        self.stance_checkboxes = {}
        # 这里的标签将由LLM动态生成，先添加一些示例
        sample_stances = ["亲欧盟", "中立", "亲美", "亲中", "亲俄"]
        for stance in sample_stances:
            checkbox = QCheckBox(stance)
            checkbox.stateChanged.connect(self._filter_by_stance)
            stance_layout.addWidget(checkbox)
            self.stance_checkboxes[stance] = checkbox
        left_layout.addWidget(self.stance_group)
        
        # Prompt管理
        prompt_group = QGroupBox("Prompt管理")
        prompt_layout = QVBoxLayout(prompt_group)
        
        # Prompt选择下拉框
        prompt_layout.addWidget(QLabel("选择Prompt模板:"))
        self.prompt_combo = QComboBox()
        self.prompt_combo.addItem("默认分析", "default")
        # 这里将从PromptManager加载模板
        prompt_layout.addWidget(self.prompt_combo)
        
        # 编辑Prompt按钮
        self.edit_prompt_button = QPushButton("编辑Prompt")
        self.edit_prompt_button.clicked.connect(self._edit_prompt)
        prompt_layout.addWidget(self.edit_prompt_button)
        
        left_layout.addWidget(prompt_group)
        
        # 历史记录按钮
        self.history_button = QPushButton("查看历史记录")
        self.history_button.clicked.connect(self._show_history)
        left_layout.addWidget(self.history_button)
        
        left_layout.addStretch()
        
        # --- 中心内容区 ---
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        
        # 事件列表标题
        center_layout.addWidget(QLabel("事件列表:"))
        
        # 事件列表
        self.event_list = QTreeWidget()
        self.event_list.setHeaderLabels(["事件标题", "媒体数量", "时间", "分类"])
        self.event_list.setAlternatingRowColors(True)
        self.event_list.setSelectionMode(QTreeWidget.SingleSelection)
        self.event_list.itemSelectionChanged.connect(self._on_event_selected)
        self.event_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.event_list.customContextMenuRequested.connect(self._show_event_context_menu)
        # 设置列宽
        self.event_list.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.event_list.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.event_list.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.event_list.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        center_layout.addWidget(self.event_list)
        
        # --- 右侧功能面板 ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建标签页
        self.detail_tabs = QTabWidget()
        
        # 事件详情标签页
        event_detail_widget = QWidget()
        event_detail_layout = QVBoxLayout(event_detail_widget)
        
        # 事件摘要
        event_detail_layout.addWidget(QLabel("事件摘要:"))
        self.event_summary = QTextEdit()
        self.event_summary.setReadOnly(True)
        self.event_summary.setMaximumHeight(100)
        event_detail_layout.addWidget(self.event_summary)
        
        # 关键词
        event_detail_layout.addWidget(QLabel("关键词:"))
        self.event_keywords = QTextEdit()
        self.event_keywords.setReadOnly(True)
        self.event_keywords.setMaximumHeight(50)
        event_detail_layout.addWidget(self.event_keywords)
        
        self.detail_tabs.addTab(event_detail_widget, "事件详情")
        
        # 媒体报道标签页
        media_widget = QWidget()
        media_layout = QVBoxLayout(media_widget)
        
        # 媒体报道列表
        self.media_list = QTreeWidget()
        self.media_list.setHeaderLabels(["媒体来源", "标题"])
        self.media_list.setAlternatingRowColors(True)
        self.media_list.itemClicked.connect(self._on_media_selected)
        # 设置列宽
        self.media_list.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.media_list.header().setSectionResizeMode(1, QHeaderView.Stretch)
        media_layout.addWidget(self.media_list)
        
        # 报道内容
        media_layout.addWidget(QLabel("报道内容:"))
        self.media_content = QTextEdit()
        self.media_content.setReadOnly(True)
        media_layout.addWidget(self.media_content)
        
        self.detail_tabs.addTab(media_widget, "媒体报道")
        
        # 分析结果标签页
        analysis_widget = QTabWidget()
        
        # 重要性分析
        importance_widget = QWidget()
        importance_layout = QVBoxLayout(importance_widget)
        
        # 重要性可视化
        self.importance_visualizer = AnalysisVisualizer()
        importance_layout.addWidget(self.importance_visualizer)
        
        # 重要性详情
        importance_layout.addWidget(QLabel("重要性分析详情:"))
        self.importance_detail = QTextEdit()
        self.importance_detail.setReadOnly(True)
        importance_layout.addWidget(self.importance_detail)
        
        analysis_widget.addTab(importance_widget, "重要性")
        
        # 立场分析
        stance_widget = QWidget()
        stance_layout = QVBoxLayout(stance_widget)
        
        # 立场标签列表
        stance_layout.addWidget(QLabel("立场标签:"))
        self.stance_list = QListWidget()
        stance_layout.addWidget(self.stance_list)
        
        # 立场详情
        stance_layout.addWidget(QLabel("立场分析详情:"))
        self.stance_detail = QTextEdit()
        self.stance_detail.setReadOnly(True)
        stance_layout.addWidget(self.stance_detail)
        
        analysis_widget.addTab(stance_widget, "立场")
        
        # 事实与观点分析
        facts_opinions_widget = QWidget()
        facts_opinions_layout = QVBoxLayout(facts_opinions_widget)
        
        # 事实列表
        facts_opinions_layout.addWidget(QLabel("事实:"))
        self.facts_list = QListWidget()
        facts_opinions_layout.addWidget(self.facts_list)
        
        # 观点列表
        facts_opinions_layout.addWidget(QLabel("观点:"))
        self.opinions_list = QListWidget()
        facts_opinions_layout.addWidget(self.opinions_list)
        
        analysis_widget.addTab(facts_opinions_widget, "事实与观点")
        
        self.detail_tabs.addTab(analysis_widget, "分析结果")
        
        # 自定义分析标签页
        custom_widget = QWidget()
        custom_layout = QVBoxLayout(custom_widget)
        
        # 自定义Prompt输入
        custom_layout.addWidget(QLabel("自定义Prompt:"))
        self.custom_prompt = QTextEdit()
        self.custom_prompt.setPlaceholderText("输入自定义Prompt进行个性化分析...")
        custom_layout.addWidget(self.custom_prompt)
        
        # 分析按钮
        self.custom_analyze_button = QPushButton("开始分析")
        self.custom_analyze_button.clicked.connect(self._analyze_with_custom_prompt)
        custom_layout.addWidget(self.custom_analyze_button)
        
        # 分析结果
        custom_layout.addWidget(QLabel("分析结果:"))
        self.custom_result = QTextEdit()
        self.custom_result.setReadOnly(True)
        custom_layout.addWidget(self.custom_result)
        
        self.detail_tabs.addTab(custom_widget, "自定义分析")
        
        right_layout.addWidget(self.detail_tabs)
        
        # 分析按钮
        self.analyze_button = QPushButton("分析事件")
        self.analyze_button.clicked.connect(self._analyze_current_event)
        self.analyze_button.setEnabled(False)  # 初始禁用
        right_layout.addWidget(self.analyze_button)
        
        # 添加面板到分割器
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(center_panel)
        main_splitter.addWidget(right_panel)
        
        # 设置分割器初始比例
        main_splitter.setSizes([200, 400, 300])
        
        layout.addWidget(main_splitter)
        
        # --- 底部状态栏 ---
        status_layout = QHBoxLayout()
        
        # 状态信息
        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        # Token消耗
        self.token_label = QLabel("Token消耗: 0")
        status_layout.addWidget(self.token_label)
        
        layout.addLayout(status_layout)
    
    def _load_news_data(self):
        """加载新闻数据并进行聚类"""
        if not self.storage:
            self.logger.error("存储服务不可用，无法加载新闻数据")
            self.status_label.setText("错误: 存储服务不可用")
            return
        
        try:
            self.status_label.setText("正在加载新闻数据...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(10)
            
            # 从存储加载新闻
            news_items = self.storage.get_all_news()
            self.all_news_items = [item.to_dict() for item in news_items]
            
            self.progress_bar.setValue(30)
            self.status_label.setText(f"已加载 {len(self.all_news_items)} 条新闻，正在聚类...")
            
            # 进行聚类
            self.events = self.clusterer.cluster(self.all_news_items)
            
            self.progress_bar.setValue(70)
            self.status_label.setText("正在按类别组织事件...")
            
            # 按类别组织事件
            self._categorize_events()
            
            self.progress_bar.setValue(90)
            
            # 更新UI
            self._update_event_list()
            self._update_stance_tags()
            
            self.progress_bar.setValue(100)
            self.status_label.setText(f"已完成，共 {len(self.events)} 个事件")
            self.progress_bar.setVisible(False)
            
        except Exception as e:
            self.logger.error(f"加载新闻数据时出错: {e}", exc_info=True)
            self.status_label.setText(f"错误: {str(e)}")
            self.progress_bar.setVisible(False)
    
    def _categorize_events(self):
        """按类别组织事件"""
        self.categorized_events = {}
        
        # 初始化类别
        self.categorized_events["all"] = self.events
        
        # 按类别分组
        for event in self.events:
            category = event.get("category", "uncategorized")
            if category not in self.categorized_events:
                self.categorized_events[category] = []
            self.categorized_events[category].append(event)
    
    def _update_event_list(self):
        """更新事件列表"""
        self.event_list.clear()
        
        # 获取当前类别的事件
        category = self.category_combo.currentData()
        events = self.categorized_events.get(category, [])
        
        # 添加事件到列表
        for event in events:
            item = QTreeWidgetItem()
            item.setText(0, event.get("title", "无标题"))
            item.setText(1, str(len(event.get("reports", []))))
            
            # 格式化时间
            pub_time = event.get("publish_time")
            if pub_time:
                if isinstance(pub_time, str):
                    try:
                        pub_time = datetime.fromisoformat(pub_time)
                    except ValueError:
                        pub_time = None
                
                if isinstance(pub_time, datetime):
                    item.setText(2, pub_time.strftime("%Y-%m-%d %H:%M"))
                else:
                    item.setText(2, "未知时间")
            else:
                item.setText(2, "未知时间")
            
            # 获取分类名称
            category_id = event.get("category", "uncategorized")
            category_name = self.clusterer.get_category_name(category_id)
            item.setText(3, category_name)
            
            # 存储事件ID
            item.setData(0, Qt.UserRole, event.get("event_id"))
            
            self.event_list.addTopLevelItem(item)
        
        # 调整列宽
        for i in range(4):
            self.event_list.resizeColumnToContents(i)
    
    def _update_stance_tags(self):
        """更新立场标签"""
        # 收集所有分析结果中的立场标签
        all_stances = set()
        for result in self.analysis_results.values():
            stance_result = result.get("stance", {})
            stances = stance_result.get("stances", [])
            all_stances.update(stances)
        
        # 更新立场标签复选框
        stance_layout = self.stance_group.layout()
        
        # 清除现有复选框
        while stance_layout.count():
            item = stance_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加新的复选框
        self.stance_checkboxes = {}
        for stance in sorted(all_stances):
            checkbox = QCheckBox(stance)
            checkbox.stateChanged.connect(self._filter_by_stance)
            stance_layout.addWidget(checkbox)
            self.stance_checkboxes[stance] = checkbox
        
        # 如果没有标签，添加提示
        if not all_stances:
            stance_layout.addWidget(QLabel("暂无立场标签，请先分析事件"))
    
    def _on_category_changed(self, index):
        """处理类别选择变化"""
        self.current_category = self.category_combo.currentData()
        self._update_event_list()
    
    def _on_event_selected(self):
        """处理事件选择变化"""
        selected_items = self.event_list.selectedItems()
        if not selected_items:
            self.current_event = None
            self.analyze_button.setEnabled(False)
            return
        
        # 获取选中的事件
        item = selected_items[0]
        event_id = item.data(0, Qt.UserRole)
        
        # 查找事件
        for event in self.events:
            if event.get("event_id") == event_id:
                self.current_event = event
                break
        
        if self.current_event:
            self.analyze_button.setEnabled(True)
            self._update_event_details()
            self._update_media_list()
            self._update_analysis_results()
        else:
            self.analyze_button.setEnabled(False)
    
    def _on_media_selected(self, item, column):
        """处理媒体报道选择变化"""
        if not item:
            return
        
        # 获取报道索引
        report_index = item.data(0, Qt.UserRole)
        if self.current_event and "reports" in self.current_event:
            reports = self.current_event["reports"]
            if 0 <= report_index < len(reports):
                report = reports[report_index]
                self.media_content.setText(report.get("content", "无内容"))
    
    def _update_event_details(self):
        """更新事件详情"""
        if not self.current_event:
            self.event_summary.clear()
            self.event_keywords.clear()
            return
        
        # 更新摘要
        summary = self.current_event.get("summary", "无摘要")
        self.event_summary.setText(summary)
        
        # 更新关键词
        keywords = self.current_event.get("keywords", [])
        self.event_keywords.setText(", ".join(keywords))
    
    def _update_media_list(self):
        """更新媒体报道列表"""
        self.media_list.clear()
        self.media_content.clear()
        
        if not self.current_event:
            return
        
        reports = self.current_event.get("reports", [])
        for i, report in enumerate(reports):
            item = QTreeWidgetItem()
            item.setText(0, report.get("source_name", "未知来源"))
            item.setText(1, report.get("title", "无标题"))
            
            # 存储报道索引
            item.setData(0, Qt.UserRole, i)
            
            self.media_list.addTopLevelItem(item)
        
        # 调整列宽
        for i in range(2):
            self.media_list.resizeColumnToContents(i)
    
    def _update_analysis_results(self):
        """更新分析结果"""
        # 清空分析结果
        self.importance_detail.clear()
        self.stance_list.clear()
        self.stance_detail.clear()
        self.facts_list.clear()
        self.opinions_list.clear()
        
        if not self.current_event:
            return
        
        event_id = self.current_event.get("event_id")
        if event_id not in self.analysis_results:
            return
        
        result = self.analysis_results[event_id]
        
        # 更新重要性分析
        importance_result = result.get("importance", {})
        importance_score = importance_result.get("importance", 0)
        self.importance_visualizer.update_importance(importance_score)
        self.importance_detail.setText(str(importance_result))
        
        # 更新立场分析
        stance_result = result.get("stance", {})
        stances = stance_result.get("stances", [])
        for stance in stances:
            self.stance_list.addItem(stance)
        self.stance_detail.setText(str(stance_result))
        
        # 更新事实与观点分析
        facts_opinions_result = result.get("facts_opinions", {})
        facts = facts_opinions_result.get("facts", [])
        opinions = facts_opinions_result.get("opinions", [])
        
        for fact in facts:
            self.facts_list.addItem(fact)
        
        for opinion in opinions:
            self.opinions_list.addItem(opinion)
    
    def _analyze_current_event(self):
        """分析当前选中的事件"""
        if not self.current_event or not self.llm_service or not self.prompt_manager:
            return
        
        try:
            self.status_label.setText("正在分析事件...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(10)
            self.analyze_button.setEnabled(False)
            
            # 获取事件ID
            event_id = self.current_event.get("event_id")
            
            # 进行分析
            self.progress_bar.setValue(30)
            result = self.event_analyzer.analyze(self.current_event)
            
            # 保存分析结果
            self.analysis_results[event_id] = result
            
            # 更新UI
            self.progress_bar.setValue(70)
            self._update_analysis_results()
            self._update_stance_tags()
            
            # 添加到历史记录
            self._add_to_history(event_id, None, result)
            
            self.progress_bar.setValue(100)
            self.status_label.setText("分析完成")
            self.progress_bar.setVisible(False)
            self.analyze_button.setEnabled(True)
            
            # 发送分析完成信号
            self.analysis_completed.emit(result)
            
        except Exception as e:
            self.logger.error(f"分析事件时出错: {e}", exc_info=True)
            self.status_label.setText(f"错误: {str(e)}")
            self.progress_bar.setVisible(False)
            self.analyze_button.setEnabled(True)
    
    def _analyze_with_custom_prompt(self):
        """使用自定义Prompt进行分析"""
        if not self.current_event or not self.llm_service:
            return
        
        # 获取自定义Prompt
        custom_prompt = self.custom_prompt.toPlainText().strip()
        if not custom_prompt:
            QMessageBox.warning(self, "警告", "请输入自定义Prompt")
            return
        
        try:
            self.status_label.setText("正在使用自定义Prompt分析...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(10)
            self.custom_analyze_button.setEnabled(False)
            
            # 获取事件ID
            event_id = self.current_event.get("event_id")
            
            # 进行分析
            self.progress_bar.setValue(30)
            result = self.event_analyzer.analyze(self.current_event, custom_prompt)
            
            # 更新UI
            self.progress_bar.setValue(70)
            self.custom_result.setText(str(result.get("custom", {})))
            
            # 添加到历史记录
            self._add_to_history(event_id, custom_prompt, result)
            
            self.progress_bar.setValue(100)
            self.status_label.setText("自定义分析完成")
            self.progress_bar.setVisible(False)
            self.custom_analyze_button.setEnabled(True)
            
        except Exception as e:
            self.logger.error(f"使用自定义Prompt分析时出错: {e}", exc_info=True)
            self.status_label.setText(f"错误: {str(e)}")
            self.progress_bar.setVisible(False)
            self.custom_analyze_button.setEnabled(True)
    
    def _filter_events(self):
        """根据搜索关键词过滤事件"""
        keyword = self.search_input.text().strip().lower()
        
        # 如果关键词为空，显示所有事件
        if not keyword:
            self._update_event_list()
            return
        
        # 获取当前类别的事件
        category = self.category_combo.currentData()
        events = self.categorized_events.get(category, [])
        
        # 过滤事件
        filtered_events = []
        for event in events:
            title = event.get("title", "").lower()
            summary = event.get("summary", "").lower()
            keywords = [k.lower() for k in event.get("keywords", [])]
            
            if (keyword in title or keyword in summary or 
                any(keyword in k for k in keywords)):
                filtered_events.append(event)
        
        # 更新事件列表
        self.event_list.clear()
        for event in filtered_events:
            item = QTreeWidgetItem()
            item.setText(0, event.get("title", "无标题"))
            item.setText(1, str(len(event.get("reports", []))))
            
            # 格式化时间
            pub_time = event.get("publish_time")
            if pub_time and isinstance(pub_time, datetime):
                item.setText(2, pub_time.strftime("%Y-%m-%d %H:%M"))
            else:
                item.setText(2, "未知时间")
            
            # 获取分类名称
            category_id = event.get("category", "uncategorized")
            category_name = self.clusterer.get_category_name(category_id)
            item.setText(3, category_name)
            
            # 存储事件ID
            item.setData(0, Qt.UserRole, event.get("event_id"))
            
            self.event_list.addTopLevelItem(item)
    
    def _filter_by_stance(self):
        """根据立场标签过滤事件"""
        # 获取选中的立场标签
        selected_stances = []
        for stance, checkbox in self.stance_checkboxes.items():
            if checkbox.isChecked():
                selected_stances.append(stance)
        
        # 如果没有选中的标签，显示所有事件
        if not selected_stances:
            self._update_event_list()
            return
        
        # 获取当前类别的事件
        category = self.category_combo.currentData()
        events = self.categorized_events.get(category, [])
        
        # 过滤事件
        filtered_events = []
        for event in events:
            event_id = event.get("event_id")
            if event_id in self.analysis_results:
                result = self.analysis_results[event_id]
                stance_result = result.get("stance", {})
                stances = stance_result.get("stances", [])
                
                if any(stance in stances for stance in selected_stances):
                    filtered_events.append(event)
        
        # 更新事件列表
        self.event_list.clear()
        for event in filtered_events:
            item = QTreeWidgetItem()
            item.setText(0, event.get("title", "无标题"))
            item.setText(1, str(len(event.get("reports", []))))
            
            # 格式化时间
            pub_time = event.get("publish_time")
            if pub_time and isinstance(pub_time, datetime):
                item.setText(2, pub_time.strftime("%Y-%m-%d %H:%M"))
            else:
                item.setText(2, "未知时间")
            
            # 获取分类名称
            category_id = event.get("category", "uncategorized")
            category_name = self.clusterer.get_category_name(category_id)
            item.setText(3, category_name)
            
            # 存储事件ID
            item.setData(0, Qt.UserRole, event.get("event_id"))
            
            self.event_list.addTopLevelItem(item)
    
    def _delete_custom_prompt(self, prompt_list):
        """删除自定义Prompt"""
        selected_items = prompt_list.selectedItems()
        if not selected_items:
            return
        
        # 获取选中的Prompt
        prompt_name = selected_items[0].text()
        if not prompt_name.startswith("custom_"):
            QMessageBox.warning(self, "警告", "只能删除自定义Prompt")
            return
        
        # 解析名称
        name = prompt_name.split(" - ")[0][7:]  # 去掉"custom_"前缀
        
        # 确认删除
        reply = QMessageBox.question(self, "确认删除", f"确定要删除Prompt \"{name}\"吗？",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        
        # 从列表中删除
        self.custom_prompts.pop(name, None)
        prompt_list.takeItem(prompt_list.row(selected_items[0]))