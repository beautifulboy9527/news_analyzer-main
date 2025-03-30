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

    def __init__(self, llm_client: LLMClient, parent=None): # 添加 llm_client 参数
        super().__init__(parent)

        self.logger = logging.getLogger('news_analyzer.ui.llm_panel')
        self.llm_client = llm_client # 使用传入的实例
        self.current_news = None

        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        # 创建主布局
        layout = QVBoxLayout(self)
        
        # 标题标签
        title_label = QLabel("LLM分析")
        # title_label.setStyleSheet("font-weight: bold; font-size: 14px;") # 移除内联样式
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
        self.result_browser.setObjectName("llmResultBrowser") # 设置 objectName
        self.result_browser.setOpenExternalLinks(True)
        layout.addWidget(self.result_browser)
        
        # 状态标签
        self.status_label = QLabel("请选择新闻项进行分析")
        layout.addWidget(self.status_label)
    
    def analyze_news(self, news_item):
        """处理新闻分析请求
        
        Args:
            news_item: 新闻数据对象 (NewsArticle)
        """
        # 保存当前新闻 (现在是 NewsArticle 对象)
        self.current_news = news_item

        # 清空上次分析结果
        self.result_browser.setHtml("")

        # 启用分析按钮
        self.analyze_button.setEnabled(True)

        # 显示消息 (使用属性访问)
        title = news_item.title if news_item and news_item.title else '无标题'
        self.status_label.setText(f"已选择: {title[:30]}...")

        self.logger.debug(f"准备分析新闻: {title[:30]}...")

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

        # 使用属性访问记录日志
        title = self.current_news.title if self.current_news and self.current_news.title else '无标题'
        self.logger.info(f"开始{analysis_type}分析: {title[:30]}...")

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

        # 使用属性访问记录日志
        title = self.current_news.title if self.current_news and self.current_news.title else '无标题'
        self.logger.info(f"完成了新闻分析: {title[:30]}...")

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
