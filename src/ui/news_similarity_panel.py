# src/ui/news_similarity_panel.py
"""
新闻相似度分析与整合面板

提供基于AI的新闻相似度分析、分组和整合功能，帮助用户从多角度理解同一事件。
"""

import logging
import re
import os
from datetime import datetime
from typing import List, Dict, Optional, Set

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QLabel, QTextEdit, QPushButton,
                             QSplitter, QMessageBox, QSizePolicy, QWidget,
                             QCheckBox, QGroupBox, QProgressBar, QComboBox)
from PySide6.QtCore import Qt, Signal, QSize, Slot
from PySide6.QtGui import QIcon, QFont

from src.models import NewsArticle
from src.llm.llm_service import LLMService
from src.storage.news_storage import NewsStorage
from src.core.app_service import AppService


class NewsSimilarityPanel(QDialog):
    """新闻相似度分析与整合对话框"""
    
    # 定义信号
    rejected_and_deleted = Signal()
    
    def __init__(self, app_service: AppService, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新闻相似度分析与整合")
        self.setMinimumSize(900, 600)
        
        # 设置窗口标志，移除问号按钮，添加最大化按钮
        flags = self.windowFlags()
        flags &= ~Qt.WindowContextHelpButtonHint
        flags |= Qt.WindowMaximizeButtonHint
        self.setWindowFlags(flags)
        
        self.logger = logging.getLogger('news_analyzer.ui.news_similarity')
        
        # Store AppService and derive storage/llm from it
        self.app_service = app_service
        self.storage = self.app_service.storage
        self.llm_service = self.app_service.llm_service
        
        # 验证传入的服务实例
        if not self.storage:
            self.logger.error("AppService did not provide a valid storage service! NewsSimilarityPanel functionality limited.")
            QMessageBox.critical(self, "错误", "存储服务不可用，无法加载新闻数据。")
        else:
            self.logger.info("Connected to AppService.selected_news_changed signal.")
        
        if not self.llm_service:
            self.logger.error("AppService did not provide a valid LLM service! NewsSimilarityPanel AI functionality limited.")
            # QMessageBox.critical(self, "错误", "LLM服务不可用，无法进行AI分析。") # Maybe just warn
            # Handle error - maybe disable parts of the UI
        
        # 初始化数据
        self.all_news_items: List[Dict] = []
        self.selected_news_items: List[Dict] = []
        self.news_groups: List[List[Dict]] = []  # 存储分组后的新闻
        self._currently_selected_article: Optional[NewsArticle] = None # Store the article selected externally
        
        # 初始化UI
        self._init_ui()
        
        # 加载新闻数据
        if self.storage:
            self._load_news_data()
        
        # Connect to AppService signal for external news selection
        self.app_service.selected_news_changed.connect(self._handle_news_selection_changed)
    
    @Slot(NewsArticle) # Add the slot decorator
    def _handle_news_selection_changed(self, article: Optional[NewsArticle]):
        """Slot to handle when the selected news changes in the main application."""
        self.logger.debug(f"NewsSimilarityPanel received selected_news_changed signal. Article: {article.title if article else 'None'}")
        self._currently_selected_article = article
        # TODO: Implement logic based on the selected article
        # e.g., pre-select it in the list, trigger analysis, update UI, etc.
        # For now, just log.
        pass # Placeholder for future logic
    
    def _init_ui(self):
        """初始化UI布局和控件"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # --- 顶部控制区域 ---
        control_layout = QHBoxLayout()
        
        # 刷新按钮
        self.refresh_button = QPushButton(QIcon.fromTheme("view-refresh", QIcon("")), " 刷新新闻")
        self.refresh_button.setToolTip("重新加载新闻数据")
        self.refresh_button.clicked.connect(self._load_news_data)
        control_layout.addWidget(self.refresh_button)
        
        # 分析类型选择
        control_layout.addWidget(QLabel("分析类型:"))
        self.analysis_type = QComboBox()
        self.analysis_type.addItem("多角度整合")
        self.analysis_type.addItem("对比分析")
        self.analysis_type.addItem("事实核查")
        self.analysis_type.addItem("时间线梳理")
        self.analysis_type.addItem("信源多样性分析")
        control_layout.addWidget(self.analysis_type)
        
        control_layout.addStretch()
        
        # 分析按钮
        self.analyze_button = QPushButton(QIcon.fromTheme("system-run", QIcon("")), " 开始分析")
        self.analyze_button.setToolTip("对选中的新闻进行AI分析和整合")
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
        
        # 左侧新闻列表区域
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 新闻列表标签
        left_layout.addWidget(QLabel("可选新闻列表:"))
        
        # 新闻列表
        self.news_list = QListWidget()
        self.news_list.setAlternatingRowColors(True)
        self.news_list.setSelectionMode(QListWidget.ExtendedSelection)  # 允许多选
        self.news_list.setStyleSheet("QListWidget::item { padding: 5px; }")
        self.news_list.itemSelectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.news_list)
        
        # 选择操作按钮
        selection_layout = QHBoxLayout()
        
        self.select_all_button = QPushButton("全选")
        self.select_all_button.clicked.connect(self._select_all_news)
        selection_layout.addWidget(self.select_all_button)
        
        self.deselect_all_button = QPushButton("取消全选")
        self.deselect_all_button.clicked.connect(self._deselect_all_news)
        selection_layout.addWidget(self.deselect_all_button)
        
        self.auto_group_button = QPushButton("自动分组")
        self.auto_group_button.setToolTip("根据标题相似度自动分组相关新闻")
        self.auto_group_button.clicked.connect(self._auto_group_news)
        selection_layout.addWidget(self.auto_group_button)
        
        left_layout.addLayout(selection_layout)
        
        # 右侧分析结果区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 分析结果标签
        right_layout.addWidget(QLabel("分析结果:"))
        
        # 添加重要程度和立场识别的可视化区域
        metrics_group = QGroupBox("新闻评估指标")
        metrics_layout = QVBoxLayout(metrics_group)
        
        # 重要程度进度条
        importance_layout = QHBoxLayout()
        importance_layout.addWidget(QLabel("重要程度:"))
        self.importance_bar = QProgressBar()
        self.importance_bar.setRange(0, 5)
        self.importance_bar.setValue(0)
        self.importance_bar.setFormat("%v/5")
        self.importance_bar.setStyleSheet("QProgressBar {text-align: center;} QProgressBar::chunk {background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5cb85c, stop:1 #3c763d);}") 
        importance_layout.addWidget(self.importance_bar)
        self.importance_label = QLabel("未评估")
        importance_layout.addWidget(self.importance_label)
        metrics_layout.addLayout(importance_layout)
        
        # 立场识别进度条
        stance_layout = QHBoxLayout()
        stance_layout.addWidget(QLabel("立场倾向:"))
        self.stance_bar = QProgressBar()
        self.stance_bar.setRange(-100, 100)  # 使用-100到100表示-1到1
        self.stance_bar.setValue(0)
        self.stance_bar.setFormat("%v%")
        self.stance_bar.setStyleSheet("QProgressBar {text-align: center;} QProgressBar::chunk {background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d9534f, stop:0.5 #f0ad4e, stop:1 #5bc0de);}") 
        stance_layout.addWidget(self.stance_bar)
        self.stance_label = QLabel("中立")
        stance_layout.addWidget(self.stance_label)
        metrics_layout.addLayout(stance_layout)
        
        # 信源多样性指标
        source_diversity_layout = QHBoxLayout()
        source_diversity_layout.addWidget(QLabel("信源多样性:"))
        self.source_diversity_label = QLabel("未评估")
        source_diversity_layout.addWidget(self.source_diversity_label)
        metrics_layout.addLayout(source_diversity_layout)
        
        right_layout.addWidget(metrics_group)
        
        # 分析结果文本编辑框
        self.result_edit = QTextEdit()
        self.result_edit.setPlaceholderText("请在左侧选择新闻并点击'开始分析'按钮进行AI分析和整合")
        right_layout.addWidget(self.result_edit)
        
        # 结果操作按钮
        result_action_layout = QHBoxLayout()
        
        self.copy_button = QPushButton("复制结果")
        self.copy_button.clicked.connect(self._copy_result)
        self.copy_button.setEnabled(False)
        result_action_layout.addWidget(self.copy_button)
        
        self.save_button = QPushButton("保存结果")
        self.save_button.clicked.connect(self._save_result)
        self.save_button.setEnabled(False)
        result_action_layout.addWidget(self.save_button)
        
        self.clear_button = QPushButton("清空结果")
        self.clear_button.clicked.connect(self._clear_result)
        self.clear_button.setEnabled(False)
        result_action_layout.addWidget(self.clear_button)
        
        right_layout.addLayout(result_action_layout)
        
        # 添加左右面板到分割器
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([400, 500])  # 设置初始分割比例
        
        layout.addWidget(main_splitter, 1)  # 1表示拉伸因子
        
        # --- 底部关闭按钮 ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("关闭")
        close_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        # 禁用控件（如果服务无效）
        if not self.storage or not self.llm_service:
            self.refresh_button.setEnabled(False)
            self.analyze_button.setEnabled(False)
            self.auto_group_button.setEnabled(False)
            self.news_list.setEnabled(False)
    
    def _load_news_data(self):
        """从存储加载新闻数据"""
        if not self.storage:
            self.logger.warning("Storage 无效，无法加载新闻数据")
            return
        
        self.logger.info("开始加载新闻数据...")
        self.news_list.clear()
        self.all_news_items = []
        
        try:
            # news_data = self.storage.load_news()
            news_data = self.storage.get_all_articles() # Use the correct method
            
            if not news_data:
                self.logger.info("没有找到新闻数据")
                item = QListWidgetItem("没有新闻数据")
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)  # 不可选
                self.news_list.addItem(item)
                return
            
            self.all_news_items = news_data
            self.logger.info(f"加载了 {len(news_data)} 条新闻数据")
            
            # 填充列表
            for i, news in enumerate(news_data):
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
                
                display_text = f"{title}\n来源: {source}"
                if pub_time_str:
                    display_text += f" | 时间: {pub_time_str}"
                
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, i)  # 存储索引以便后续获取完整数据
                self.news_list.addItem(item)
            
            self.logger.info("新闻数据加载完成")
            
        except Exception as e:
            self.logger.error(f"加载新闻数据时出错: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"加载新闻数据失败: {e}")
    
    def _on_selection_changed(self):
        """处理新闻列表选择变化"""
        selected_items = self.news_list.selectedItems()
        self.selected_news_items = []
        
        for item in selected_items:
            index = item.data(Qt.UserRole)
            if isinstance(index, int) and 0 <= index < len(self.all_news_items):
                self.selected_news_items.append(self.all_news_items[index])
        
        # 更新分析按钮状态
        self.analyze_button.setEnabled(len(self.selected_news_items) > 0)
        
        self.logger.debug(f"已选择 {len(self.selected_news_items)} 条新闻")
    
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
        """自动分组相关新闻"""
        if not self.all_news_items:
            QMessageBox.information(self, "提示", "没有可分组的新闻数据")
            return
        
        # 简单实现：基于标题相似度的分组
        # 在实际应用中，应该使用更复杂的算法，如TF-IDF或嵌入向量相似度
        try:
            self.logger.info("开始自动分组新闻...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # 不确定进度
            
            # 这里使用简单的标题关键词匹配作为示例
            # 实际应用中应该使用LLM或其他算法进行更准确的分组
            groups = []
            processed = set()
            
            for i, news in enumerate(self.all_news_items):
                if i in processed:
                    continue
                
                title_i = news.get('title', '').lower()
                if not title_i:
                    continue
                
                # 创建新组
                group = [news]
                processed.add(i)
                
                # 查找相似新闻
                for j, other_news in enumerate(self.all_news_items):
                    if j in processed or i == j:
                        continue
                    
                    title_j = other_news.get('title', '').lower()
                    if not title_j:
                        continue
                    
                    # 简单相似度：共同关键词数量
                    words_i = set(title_i.split())
                    words_j = set(title_j.split())
                    common_words = words_i.intersection(words_j)
                    
                    # 如果共同关键词超过阈值，认为是相似新闻
                    if len(common_words) >= 2 and len(common_words) / len(words_i) > 0.3:
                        group.append(other_news)
                        processed.add(j)
                
                if len(group) > 1:  # 只保留有多条新闻的组
                    groups.append(group)
            
            self.news_groups = groups
            self.progress_bar.setVisible(False)
            
            # 显示分组结果
            if groups:
                result_text = "自动分组结果:\n\n"
                for i, group in enumerate(groups):
                    result_text += f"组 {i+1} ({len(group)} 条新闻):\n"
                    for news in group:
                        title = news.get('title', '无标题')
                        source = news.get('source_name', '未知来源')
                        result_text += f"- {title} (来源: {source})\n"
                    result_text += "\n"
                
                self.result_edit.setText(result_text)
                self.copy_button.setEnabled(True)
                self.save_button.setEnabled(True)
                self.clear_button.setEnabled(True)
                
                # 自动选择第一组新闻
                self.news_list.clearSelection()
                for i in range(self.news_list.count()):
                    item = self.news_list.item(i)
                    index = item.data(Qt.UserRole)
                    if any(news is self.all_news_items[index] for news in groups[0]):
                        item.setSelected(True)
                
                QMessageBox.information(self, "分组完成", f"已自动分组 {len(groups)} 组相关新闻")
            else:
                QMessageBox.information(self, "分组结果", "未找到相似度足够高的新闻组")
        
        except Exception as e:
            self.logger.error(f"自动分组新闻时出错: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"自动分组失败: {e}")
            self.progress_bar.setVisible(False)
    
    def _analyze_selected_news(self):
        """分析选中的新闻"""
        if not self.selected_news_items:
            QMessageBox.information(self, "提示", "请先选择要分析的新闻")
            return
        
        if not self.llm_service:
            QMessageBox.critical(self, "错误", "LLM服务不可用，无法进行分析")
            return
        
        try:
            self.logger.info(f"开始分析 {len(self.selected_news_items)} 条新闻...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # 不确定进度
            self.analyze_button.setEnabled(False)
            
            # 重置评估指标
            self.importance_bar.setValue(0)
            self.importance_label.setText("未评估")
            self.stance_bar.setValue(0)
            self.stance_label.setText("中立")
            self.source_diversity_label.setText("未评估")
            
            # 获取分析类型
            analysis_type = self.analysis_type.currentText()
            
            # 使用专门的多新闻分析方法
            response = self.llm_service.analyze_multiple_news(self.selected_news_items, analysis_type)
            
            # 显示结果
            if response:
                self.result_edit.setText(response)
                self.copy_button.setEnabled(True)
                self.save_button.setEnabled(True)
                self.clear_button.setEnabled(True)
                
                # 提取并更新重要程度和立场信息
                self._extract_and_update_metrics(response)
            else:
                self.result_edit.setText("分析失败，未获得有效结果")
            
            self.progress_bar.setVisible(False)
            self.analyze_button.setEnabled(True)
            self.logger.info("新闻分析完成")
            
        except Exception as e:
            self.logger.error(f"分析新闻时出错: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"分析失败: {e}")
            self.progress_bar.setVisible(False)
            self.analyze_button.setEnabled(True)
    
    def _extract_and_update_metrics(self, response_text):
        """从分析结果中提取并更新重要程度、立场和信源多样性信息"""
        try:
            # 提取重要程度
            importance_patterns = [
                r'重要程度[：:](\s*)(头条|重要|一般|次要)',
                r'重要程度评估[：:](\s*)(头条|重要|一般|次要)',
                r'重要程度分类[：:](\s*)(头条|重要|一般|次要)',
                r'事件(被|是)(评估|分类)为[：:\s]*(头条|重要|一般|次要)',
                r'(头条|重要|一般|次要)(级别|事件|新闻)'
            ]
            
            importance_value = 0
            importance_text = "未评估"
            
            for pattern in importance_patterns:
                matches = re.search(pattern, response_text)
                if matches:
                    importance_keyword = matches.group(matches.lastindex)
                    if importance_keyword == "头条":
                        importance_value = 5
                        importance_text = "头条"
                    elif importance_keyword == "重要":
                        importance_value = 3
                        importance_text = "重要"
                    elif importance_keyword == "一般":
                        importance_value = 1
                        importance_text = "一般"
                    elif importance_keyword == "次要":
                        importance_value = 0
                        importance_text = "次要"
                    break
            
            # 更新重要程度UI
            self.importance_bar.setValue(importance_value)
            self.importance_label.setText(importance_text)
            
            # 提取立场信息
            stance_patterns = [
                r'立场[：:](\s*)(亲美|亲西方|偏美|中立|偏中|亲中)',
                r'立场评估[：:](\s*)(亲美|亲西方|偏美|中立|偏中|亲中)',
                r'立场识别[：:](\s*)(亲美|亲西方|偏美|中立|偏中|亲中)',
                r'立场倾向[：:](\s*)(亲美|亲西方|偏美|中立|偏中|亲中)'
            ]
            
            stance_value = 0
            stance_text = "中立"
            
            for pattern in stance_patterns:
                matches = re.search(pattern, response_text)
                if matches:
                    stance_keyword = matches.group(matches.lastindex)
                    if stance_keyword == "亲美":
                        stance_value = -100
                        stance_text = "亲美"
                    elif stance_keyword == "亲西方":
                        stance_value = -80
                        stance_text = "亲西方"
                    elif stance_keyword == "偏美":
                        stance_value = -50
                        stance_text = "偏美"
                    elif stance_keyword == "中立":
                        stance_value = 0
                        stance_text = "中立"
                    elif stance_keyword == "偏中":
                        stance_value = 50
                        stance_text = "偏中"
                    elif stance_keyword == "亲中":
                        stance_value = 100
                        stance_text = "亲中"
                    break
            
            # 更新立场UI
            self.stance_bar.setValue(stance_value)
            self.stance_label.setText(stance_text)
            
            # 提取信源多样性信息
            diversity_patterns = [
                r'信源多样性[：:](\s*)([^\n]+)',
                r'信源多样性评估[：:](\s*)([^\n]+)',
                r'信源(分布|构成)[：:](\s*)([^\n]+)'
            ]
            
            diversity_text = "未评估"
            
            for pattern in diversity_patterns:
                matches = re.search(pattern, response_text)
                if matches:
                    diversity_text = matches.group(matches.lastindex).strip()
                    break
                    
            # 如果没有找到具体描述，尝试计算不同来源的数量
            if diversity_text == "未评估":
                sources = set()
                for news in self.selected_news_items:
                    source = news.get('source_name', news.get('source', ''))
                    if source:
                        sources.add(source)
                if sources:
                    diversity_text = f"{len(sources)}种不同来源"
            
            # 更新信源多样性UI
            self.source_diversity_label.setText(diversity_text)
            
        except Exception as e:
            self.logger.error(f"提取分析指标时出错: {e}", exc_info=True)
            # 出错时不更新UI，保持默认值
    
    def _build_analysis_prompt(self, news_items: List[Dict], analysis_type: str) -> str:
        """构建分析提示"""
        prompt = f"请对以下{len(news_items)}条关于同一事件的新闻进行{analysis_type}。\n\n"
        
        # 添加每条新闻的信息
        for i, news in enumerate(news_items):
            title = news.get('title', '无标题')
            source = news.get('source_name', '未知来源')
            content = news.get('content', news.get('summary', '无内容'))
            
            prompt += f"新闻{i+1}:\n标题: {title}\n来源: {source}\n内容: {content}\n\n"
        
        # 根据分析类型添加具体要求
        if analysis_type == "多角度整合":
            prompt += "请整合这些新闻的信息，提供一个全面、客观的报道，包含各方观点和角度。注意保留不同信源的视角差异，并指出可能存在的偏见。"
        elif analysis_type == "对比分析":
            prompt += "请对比分析这些新闻报道的异同点，特别关注不同信源在报道角度、事实选择和表述方式上的差异，并分析可能的原因。"
        elif analysis_type == "事实核查":
            prompt += "请对这些新闻中的关键事实进行核查和比对，指出一致的信息和存在分歧的部分，并尝试确定最可能准确的事实。"
        elif analysis_type == "时间线梳理":
            prompt += "请根据这些新闻报道，梳理事件的完整时间线，按时间顺序呈现事件的发展过程，并标注信息来源。"
        
        return prompt
    
    def _copy_result(self):
        """复制分析结果到剪贴板"""
        text = self.result_edit.toPlainText()
        if text:
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.clipboard().setText(text)
            self.logger.info("分析结果已复制到剪贴板")
    
    def _save_result(self):
        """保存分析结果"""
        text = self.result_edit.toPlainText()
        if not text:
            return
        
        try:
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            analysis_type = self.analysis_type.currentText()
            filename = f"news_analysis_{analysis_type}_{timestamp}.txt"
            
            # 保存到数据目录
            if self.storage:
                filepath = os.path.join(self.storage.data_dir, "analysis", filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(text)
                
                self.logger.info(f"分析结果已保存到: {filepath}")
                QMessageBox.information(self, "保存成功", f"分析结果已保存到:\n{filepath}")
            else:
                QMessageBox.critical(self, "错误", "存储服务不可用，无法保存结果")
        
        except Exception as e:
            self.logger.error(f"保存分析结果时出错: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"保存失败: {e}")
    
    def _clear_result(self):
        """清空分析结果"""
        self.result_edit.clear()
        self.copy_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.clear_button.setEnabled(False)
    
    def reject(self):
        """重写reject方法，确保正确关闭和清理"""
        self.logger.debug("NewsSimilarityPanel: reject() called")
        super().reject()
        self.deleteLater()
        self.rejected_and_deleted.emit()
    
    def closeEvent(self, event):
        """重写closeEvent方法，确保正确关闭"""
        self.logger.debug("NewsSimilarityPanel: closeEvent triggered")
        event.accept()
        self.rejected_and_deleted.emit()
        self.deleteLater()


# 用于独立测试
if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    import os
    
    logging.basicConfig(level=logging.DEBUG)
    
    # 创建模拟数据
    class MockStorage:
        def __init__(self):
            self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
            os.makedirs(os.path.join(self.data_dir, "analysis"), exist_ok=True)
            self.logger = logging.getLogger('MockStorage')
        
        def load_news(self):
            self.logger.info("MockStorage: load_news called")
            return [
                {"title": "中美元首举行会晤", "source_name": "新华社", "publish_time": datetime.now(), 
                 "content": "今日，中美两国元首在G20峰会期间举行了会晤，就双边关系和全球议题进行了深入交流。"},
                {"title": "中美领导人会谈取得积极成果", "source_name": "人民日报", "publish_time": datetime.now(),
                 "content": "中美两国领导人在G20峰会期间举行会谈，双方就经贸、气候变化等议题达成多项共识。"},
                {"title": "US-China Leaders Meet at G20", "source_name": "CNN", "publish_time": datetime.now(),
                 "content": "The leaders of US and China met today at the G20 summit, discussing trade tensions and global issues."},
                {"title": "中国宣布新能源政策", "source_name": "经济日报", "publish_time": datetime.now(),
                 "content": "中国政府今日宣布新的能源政策，计划到2030年实现碳达峰目标。"},
            ]
    
    class MockLLMService:
        def __init__(self):
            self.logger = logging.getLogger('MockLLMService')
        
        def chat(self, messages, context, stream, callback):
            self.logger.info("MockLLMService: chat called")
            # 模拟LLM响应
            return """# 多角度整合分析

## 事件概述
根据多家媒体报道，中美两国元首在G20峰会期间举行了会晤，就双边关系和全球性议题进行了深入交流。

## 各方报道角度

### 中方媒体视角
- **新华社**强调了会晤的举行事实，使用"深入交流"描述会谈内容，未具体提及成果。
- **人民日报**则明确表示会谈"取得积极成果"，并具体提到双方在"经贸、气候变化等议题达成多项共识"，报道基调更为积极。

### 美方媒体视角
- **CNN**的报道使用了更中性的描述"discussing trade tensions and global issues"，没有明确提及会谈成果。
"""