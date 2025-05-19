# src/ui/managers/analysis_panel_manager.py
"""
新闻分析面板管理器

负责创建、显示和管理新闻分析面板，
支持重要程度和立场识别的数字化与可视化展示。
"""

import logging
from typing import Optional, Dict, Any, List

from PySide6.QtCore import QObject, Signal, Slot, QSettings, Qt, QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QSplitter, QMessageBox, QWidget, QDockWidget
from PySide6.QtGui import QAction

from src.core.app_service import AppService
from src.models import NewsArticle
from src.llm.processors import analyze_text, digitize_importance, digitize_stance
from src.ui.views.analysis_visualizer import AnalysisVisualizer
# from src.ui.viewmodels.analysis_viewmodel import AnalysisViewModel # REMOVED - Seems unused
from src.core.analysis_service import AnalysisService
from src.ui.views.prompt_manager_widget import PromptManagerWidget


class NewsAnalysisPanel(QDialog):
    """新闻分析面板对话框"""
    
    # 定义信号
    analysis_completed = Signal(dict)
    rejected_and_deleted = Signal()
    
    def __init__(self, app_service: AppService, news_article: Optional[NewsArticle] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新闻分析")
        self.setMinimumSize(800, 600)
        
        self.logger = logging.getLogger('news_analyzer.ui.news_analysis_panel')
        self.app_service = app_service
        self.news_article = news_article
        
        # 分析结果
        self.analysis_result: Dict[str, Any] = {}
        
        # 初始化UI
        self._init_ui()
        
        # 如果提供了新闻文章，立即分析
        if self.news_article:
            self._analyze_news()
    
    def _init_ui(self):
        """初始化UI布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 创建分割器
        splitter = QSplitter()
        splitter.setOrientation(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # 左侧：分析结果文本区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 分析结果标题
        left_layout.addWidget(QLabel("分析结果"))
        
        # 分析结果文本区域
        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        left_layout.addWidget(self.analysis_text)
        
        splitter.addWidget(left_widget)
        
        # 右侧：可视化区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 可视化标题
        right_layout.addWidget(QLabel("可视化展示"))
        
        # 可视化组件
        self.visualizer = AnalysisVisualizer()
        right_layout.addWidget(self.visualizer)
        
        splitter.addWidget(right_widget)
        
        # 设置分割器初始比例
        splitter.setSizes([400, 400])
        
        # 底部按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 重新分析按钮
        self.reanalyze_button = QPushButton("重新分析")
        self.reanalyze_button.clicked.connect(self._analyze_news)
        button_layout.addWidget(self.reanalyze_button)
        
        # 关闭按钮
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def _update_ui_state(self, state: str, result: Optional[Dict] = None):
        """统一处理UI状态更新
        
        Args:
            state: UI状态，可选值：'analyzing', 'completed', 'error'
            result: 分析结果字典（当state为'completed'时）
        """
        if state == 'analyzing':
            # 显示分析中状态
            self.analysis_text.setText("正在分析中，请稍候...")
            self.reanalyze_button.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
        elif state == 'completed' and result:
            # 更新分析结果文本
            self.analysis_text.setText(result.get('analysis', ''))
            
            # 更新可视化组件
            self.visualizer.update_single_analysis(
                result.get('importance', 0),
                result.get('stance', 0.0)
            )
            
            # 更新UI状态
            self.reanalyze_button.setEnabled(True)
            self.progress_bar.setVisible(False)
            
            # 发送分析完成信号
            self.analysis_completed.emit(result)
            
        elif state == 'error':
            # 显示错误状态
            self.analysis_text.setText("分析失败，请重试")
            self.reanalyze_button.setEnabled(True)
            self.progress_bar.setVisible(False)
    
    def _analyze_news(self):
        """分析新闻内容"""
        if not self.news_article:
            self.logger.warning("没有提供新闻文章，无法进行分析")
            QMessageBox.warning(self, "警告", "没有提供新闻文章，无法进行分析")
            return
        
        if not self.app_service.llm_service:
            self.logger.error("LLM服务不可用，无法进行分析")
            QMessageBox.critical(self, "错误", "LLM服务不可用，无法进行分析")
            return
        
        # 更新UI为分析中状态
        self._update_ui_state('analyzing')
        
        # 准备新闻数据
        news_data = {
            'title': self.news_article.title,
            'source': self.news_article.source_name,
            'pub_date': self.news_article.publish_time,
            'content': self.news_article.content
        }
        
        # 使用LLM服务进行分析
        try:
            result = self.app_service.llm_service.analyze_news(
                news_data, 
                analysis_type="重要程度和立场分析"
            )
            self._update_ui_state('completed', result)
            
        except Exception as e:
            self.logger.error(f"分析过程中发生错误: {e}", exc_info=True)
            self._update_ui_state('error')
            QMessageBox.critical(self, "错误", f"分析失败: {str(e)}")
    
    def closeEvent(self, event):
        """处理窗口关闭事件"""
        self.rejected_and_deleted.emit()
        event.accept()


class AnalysisPanelManager(QObject):
    """新闻分析面板管理器"""
    
    def __init__(self, parent, app_service: AppService):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.managers.analysis_panel_manager')
        self.app_service = app_service
        self.main_window = parent  # Store main window reference

        # Panel instance (Dock Widget)
        self._panel: Optional[QDockWidget] = None
        self._panel_widget: Optional[NewsAnalysisPanel] = None # Store the actual panel widget

        # self.analysis_panel: Optional[NewsAnalysisPanel] = None # REMOVED - Replaced by _panel/_panel_widget
    
    def get_panel(self) -> Optional[QDockWidget]:
        """获取或创建新闻分析面板 (QDockWidget)。"""
        if self._panel is None:
            self.logger.info("Analysis panel does not exist. Creating new NewsAnalysisPanel instance...")
            try:
                from src.ui.views.news_analysis_panel import NewsAnalysisPanel # Corrected absolute import path
                self._panel_widget = NewsAnalysisPanel(self.app_service, self.main_window)
                self._panel = QDockWidget("分类与分析", self.main_window)
                self._panel.setObjectName("analysisPanelDock")
                self._panel.setWidget(self._panel_widget)
                self._panel.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
                self.main_window.addDockWidget(Qt.RightDockWidgetArea, self._panel)
                self.logger.info("NewsAnalysisPanel created and added as dock widget successfully.")
            except ImportError as e:
                self.logger.error(f"Failed to import NewsAnalysisPanel: {e}", exc_info=True)
                self._panel = None # Ensure panel remains None on import error
                # Optionally show error to user via DialogManager or status bar
                if hasattr(self.main_window, 'dialog_manager'):
                    self.main_window.dialog_manager.show_error_message(f"加载分析面板失败: {e}")
                return None
            except Exception as e:
                self.logger.error(f"Failed to create NewsAnalysisPanel or QDockWidget: {e}", exc_info=True)
                self._panel = None # Ensure panel remains None on creation error
                if hasattr(self.main_window, 'dialog_manager'):
                    self.main_window.dialog_manager.show_error_message(f"创建分析面板失败: {e}")
                return None
        else:
            self.logger.debug("Returning existing analysis panel instance.")

        return self._panel

    def show_analysis_panel(self, news_article: Optional[NewsArticle] = None):
        """显示新闻分析面板"""
        # Always create a new panel instance when showing
        self.logger.info(f"Showing new NewsAnalysisPanel for article: {news_article.title if news_article else 'None'}")
        self.analysis_panel = NewsAnalysisPanel(
            app_service=self.app_service,
            news_article=news_article,
            parent=self.window
        )
        # Connect signals if needed
        self.analysis_panel.rejected.connect(self._on_panel_closed)
        # self.analysis_panel.analysis_completed.connect(self._on_analysis_completed)
        self.analysis_panel.show()

    def _on_panel_closed(self):
        """处理面板关闭事件"""
        self.logger.debug("新闻分析面板已关闭")
        if self.analysis_panel:
            self.analysis_panel.deleteLater() # Ensure proper cleanup
        self.analysis_panel = None