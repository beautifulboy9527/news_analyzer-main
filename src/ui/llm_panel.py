"""
LLM分析面板

显示新闻的LLM分析结果，提供分析控制功能。
"""

import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
                            QPushButton, QLabel, QTextBrowser, QProgressBar, QSizePolicy) # Use PySide6
from PySide6.QtCore import Qt, Slot as pyqtSlot # Use PySide6, alias Slot
from src.models import NewsArticle # Use absolute import from src
from src.ui.viewmodels.llm_panel_viewmodel import LLMPanelViewModel # Import the ViewModel
from typing import Dict, Any
from src.llm.formatter import LLMResponseFormatter

class LLMPanel(QWidget):
    """LLM分析面板组件"""

    def __init__(self, view_model: LLMPanelViewModel, parent=None): # Inject ViewModel
        super().__init__(parent)
        self.setObjectName("LLMPanel") # Add objectName for QSS targeting

        self.logger = logging.getLogger('news_analyzer.ui.llm_panel')
        self._view_model = view_model # Store the ViewModel instance
        # self.current_news is now managed by the ViewModel

        self._init_ui()
        self._connect_view_model()
    
    def _init_ui(self):
        """初始化UI"""
        # 创建主布局
        layout = QVBoxLayout(self)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding) # Set size policy
        
        # 标题标签
        # title_label = QLabel("LLM分析") # Removed title label
        # # title_label.setStyleSheet("font-weight: bold; font-size: 14px;") # 移除内联样式
        # layout.addWidget(title_label) # Removed title label

        # 控制面板
        control_layout = QHBoxLayout()
        
        # 分析类型选择
        self.analysis_type = QComboBox()
        self.analysis_type.addItem("摘要")
        self.analysis_type.addItem("深度分析")
        self.analysis_type.addItem("关键观点")
        self.analysis_type.addItem("事实核查")
        control_layout.addWidget(QLabel("分析类型:"))
        control_layout.addWidget(self.analysis_type)
        
        # 分析按钮
        self.analyze_button = QPushButton("分析")
        self.analyze_button.clicked.connect(self._on_analyze_clicked)
        self.analyze_button.setEnabled(False)  # Initial state managed by ViewModel connection
        control_layout.addWidget(self.analyze_button)
        
        layout.addLayout(control_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 分析结果显示
        self.result_browser = QTextBrowser()
        self.result_browser.setObjectName("LLMResultBrowser") # 统一大小写以匹配 QSS
        self.result_browser.setOpenExternalLinks(True)
        layout.addWidget(self.result_browser, 1) # Add stretch factor
        
        # 状态标签
        self.status_label = QLabel("请选择新闻项进行分析")
        layout.addWidget(self.status_label)
    
    def _connect_view_model(self):
        """连接ViewModel的信号到UI槽函数"""
        self._view_model.analysis_started.connect(self._on_analysis_started)
        self._view_model.analysis_finished.connect(self._on_analysis_complete)
        self._view_model.analysis_error.connect(self._on_analysis_error)
        self._view_model.busy_changed.connect(self._on_busy_changed)
        self._view_model.current_article_changed.connect(self._on_current_article_changed)

    def _on_analyze_clicked(self):
        """处理分析按钮点击事件"""
        analysis_type = self.analysis_type.currentText()
        self.logger.info(f"请求分析: {analysis_type}")
        self._view_model.perform_analysis(analysis_type)

    @pyqtSlot()
    def _on_analysis_started(self):
        """处理分析开始事件"""
        self.status_label.setText("正在进行分析...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        self.analyze_button.setEnabled(False)
        self.logger.info("分析开始")

    @pyqtSlot(object) # Keep object for flexibility, but handle str primarily
    def _on_analysis_complete(self, result) -> None:
        """处理分析完成事件
        
        Args:
            result: 分析结果 (现在是格式化好的 HTML 字符串)
        """
        self.logger.info(f"--- LLMPanel._on_analysis_complete: Received result (type: {type(result)}). First 500 chars: {str(result)[:500]} ---")
        try:
            # 隐藏进度条
            self.progress_bar.hide()
            
            # --- FIX: Handle string result directly --- Modified
            # 检查结果是否为有效字符串
            if not result or not isinstance(result, str):
                self.logger.error(f"_on_analysis_complete received invalid result type: {type(result)}. Expected str.")
                self.result_browser.setHtml(
                    '<div style="color: #e74c3c; padding: 20px;">分析结果无效 (内部错误: 类型不匹配)，请重试</div>'
                )
                return
                
            # 直接使用结果作为 HTML
            analysis_html = result 
            # --- End FIX ---
            
            # 更新结果显示
            self.result_browser.setHtml(analysis_html)
            
            # 更新状态标签
            self.status_label.setText("分析完成")
            self.status_label.setStyleSheet("color: #27ae60;")
            
            # 记录日志
            self.logger.info("分析结果已更新到UI")
            
        except Exception as e:
            error_msg = f"显示分析结果时发生错误: {str(e)}"
            self.logger.error(error_msg)
            self.result_browser.setHtml(
                f'<div style="color: #e74c3c; padding: 20px;">{error_msg}</div>'
            )
            self.status_label.setText("分析结果显示失败")
            self.status_label.setStyleSheet("color: #e74c3c;")

    @pyqtSlot(str)
    def _on_analysis_error(self, error_msg: str):
        """处理分析错误事件
        
        Args:
            error_msg: 错误消息
        """
        # 隐藏进度条
        self.progress_bar.setVisible(False)
        
        # 显示错误
        self.result_browser.setHtml(
            f'<div style="color: #e74c3c; padding: 20px;">'
            f'<h3>分析失败</h3>'
            f'<p>{error_msg}</p>'
            f'</div>'
        )
        
        # 更新状态
        self.status_label.setText("分析失败")
        self.status_label.setStyleSheet("color: #e74c3c;")
        
        # 记录错误
        self.logger.error(f"分析失败: {error_msg}")

    @pyqtSlot(bool)
    def _on_busy_changed(self, is_busy: bool):
        """更新UI状态
        
        Args:
            is_busy: 是否处于忙碌状态
        """
        self.progress_bar.setVisible(is_busy)
        if not is_busy:
            self.progress_bar.setRange(0, 1)  # 重置进度条
        # 仅在非忙碌且有文章选中时启用按钮
        self.analyze_button.setEnabled(not is_busy and self._view_model._current_article is not None)
        self.logger.debug(f"忙碌状态改变: {is_busy}, 按钮状态: {self.analyze_button.isEnabled()}")

    @pyqtSlot(object) # Slot to handle the new signal from ViewModel
    def _on_current_article_changed(self, article: NewsArticle | None):
        """Updates the UI when the selected article changes in the ViewModel."""
        self.logger.debug(f"LLMPanel received current_article_changed signal. Article: {'Set' if article else 'None'}")
        # Clear previous results
        self.result_browser.setHtml("")

        # Update status label
        if article:
            title = article.title if article.title else '无标题'
            display_text = f"已选择: {title[:30]}..."
            self.status_label.setText(display_text)
            self.logger.debug(f"Status label set to: '{display_text}'")
        else:
            self.status_label.setText("请选择新闻项进行分析")
            self.logger.debug("Status label set to: '请选择新闻项进行分析'")

        # Button enablement is handled by _on_busy_changed, which checks self._view_model._current_article
        # No need to explicitly set button state here unless _on_busy_changed logic changes.
        # Re-emitting busy_changed from ViewModel ensures _on_busy_changed runs after article change.
        self.update() # Request repaint

