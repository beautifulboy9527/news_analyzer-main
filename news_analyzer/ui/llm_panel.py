"""
LLM分析面板

显示新闻的LLM分析结果，提供分析控制功能。
"""

import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, 
                            QPushButton, QLabel, QTextBrowser, QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from news_analyzer.llm.llm_client import LLMClient


class AnalysisThread(QThread):
    """分析线程类"""
    
    # 自定义信号：分析完成
    analysis_complete = pyqtSignal(str)
    analysis_error = pyqtSignal(str)
    
    def __init__(self, llm_client, news_item, analysis_type):
        super().__init__()
        self.llm_client = llm_client
        self.news_item = news_item
        self.analysis_type = analysis_type
    
    def run(self):
        """运行线程"""
        try:
            result = self.llm_client.analyze_news(self.news_item, self.analysis_type)
            self.analysis_complete.emit(result)
        except Exception as e:
            self.analysis_error.emit(str(e))


class LLMPanel(QWidget):
    """LLM分析面板组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.logger = logging.getLogger('news_analyzer.ui.llm_panel')
        self.llm_client = LLMClient()
        self.current_news = None
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        # 创建主布局
        layout = QVBoxLayout(self)
        
        # 标题标签
        title_label = QLabel("LLM分析")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)
        
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
        self.analyze_button.setEnabled(False)  # 初始禁用
        control_layout.addWidget(self.analyze_button)
        
        layout.addLayout(control_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 分析结果显示
        self.result_browser = QTextBrowser()
        self.result_browser.setOpenExternalLinks(True)
        layout.addWidget(self.result_browser)
        
        # 状态标签
        self.status_label = QLabel("请选择新闻项进行分析")
        layout.addWidget(self.status_label)
    
    def analyze_news(self, news_item):
        """处理新闻分析请求
        
        Args:
            news_item: 新闻数据字典
        """
        # 保存当前新闻
        self.current_news = news_item
        
        # 清空上次分析结果
        self.result_browser.setHtml("")
        
        # 启用分析按钮
        self.analyze_button.setEnabled(True)
        
        # 显示消息
        title = news_item.get('title', '无标题')[:30]
        self.status_label.setText(f"已选择: {title}...")
        
        self.logger.debug(f"准备分析新闻: {title}...")
    
    def _on_analyze_clicked(self):
        """处理分析按钮点击事件"""
        if not self.current_news:
            self.status_label.setText("错误: 未选择新闻")
            return
        
        # 获取分析类型
        analysis_type = self.analysis_type.currentText()
        
        # 显示消息和进度条
        self.status_label.setText(f"正在进行{analysis_type}分析...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 显示繁忙状态
        
        # 禁用分析按钮
        self.analyze_button.setEnabled(False)
        
        # 创建并启动分析线程
        self.analysis_thread = AnalysisThread(
            self.llm_client, 
            self.current_news, 
            analysis_type
        )
        self.analysis_thread.analysis_complete.connect(self._on_analysis_complete)
        self.analysis_thread.analysis_error.connect(self._on_analysis_error)
        self.analysis_thread.start()
        
        self.logger.info(f"开始{analysis_type}分析: {self.current_news.get('title', '')[:30]}...")
    
    def _on_analysis_complete(self, result):
        """处理分析完成事件
        
        Args:
            result: 分析结果HTML
        """
        # 隐藏进度条
        self.progress_bar.setVisible(False)
        
        # 显示结果
        self.result_browser.setHtml(result)
        
        # 更新状态
        self.status_label.setText("分析完成")
        
        # 启用分析按钮
        self.analyze_button.setEnabled(True)
        
        self.logger.info(f"完成了新闻分析: {self.current_news.get('title', '')[:30]}...")
    
    def _on_analysis_error(self, error_msg):
        """处理分析错误事件
        
        Args:
            error_msg: 错误消息
        """
        # 隐藏进度条
        self.progress_bar.setVisible(False)
        
        # 显示错误
        self.result_browser.setHtml(f"<h2>分析错误</h2><p>{error_msg}</p>")
        
        # 更新状态
        self.status_label.setText(f"错误: {error_msg}")
        
        # 启用分析按钮
        self.analyze_button.setEnabled(True)
        
        self.logger.error(f"新闻分析失败: {error_msg}")
