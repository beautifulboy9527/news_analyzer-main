#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主窗口模块 - 包含应用程序主界面

该模块实现了应用程序的主窗口，整合侧边栏、新闻列表和LLM面板等UI组件。
"""

import os
import logging
import threading
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QSplitter, QAction, QMenuBar, QStatusBar, 
                            QToolBar, QMessageBox, QDialog, QLabel, 
                            QLineEdit, QPushButton, QFormLayout, QTabWidget)
from PyQt5.QtCore import Qt, QSize, QSettings, QTimer
from PyQt5.QtGui import QIcon

from news_analyzer.ui.sidebar import CategorySidebar
from news_analyzer.ui.news_list import NewsListPanel
from news_analyzer.ui.search_panel import SearchPanel
from news_analyzer.ui.llm_panel import LLMPanel
from news_analyzer.ui.chat_panel import ChatPanel
from news_analyzer.ui.llm_settings import LLMSettingsDialog
from news_analyzer.collectors.rss_collector import RSSCollector
from news_analyzer.llm.llm_client import LLMClient


class AddSourceDialog(QDialog):
    """添加新闻源对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加新闻源")
        self.setMinimumWidth(400)
        
        # 创建表单布局
        layout = QFormLayout(self)
        
        # URL输入
        self.url_input = QLineEdit()
        layout.addRow("RSS URL:", self.url_input)
        
        # 名称输入
        self.name_input = QLineEdit()
        layout.addRow("名称 (可选):", self.name_input)
        
        # 分类输入
        self.category_input = QLineEdit()
        layout.addRow("分类:", self.category_input)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 取消按钮
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        # 确认按钮
        self.add_button = QPushButton("添加")
        self.add_button.setDefault(True)
        self.add_button.clicked.connect(self.accept)
        button_layout.addWidget(self.add_button)
        
        layout.addRow("", button_layout)
    
    def get_values(self):
        """获取对话框输入值"""
        return {
            'url': self.url_input.text().strip(),
            'name': self.name_input.text().strip(),
            'category': self.category_input.text().strip() or "未分类"
        }


class MainWindow(QMainWindow):
    """应用程序主窗口类"""
    
    def __init__(self, storage, rss_collector=None):
        super().__init__()
        
        self.logger = logging.getLogger('news_analyzer.ui.main_window')
        self.storage = storage
        
        # 使用传入的RSS收集器或创建新的
        self.rss_collector = rss_collector or RSSCollector()
        
        # 设置窗口属性
        self.setWindowTitle("新闻聚合与分析系统")
        self.setMinimumSize(1200, 800)
        
        # 加载语言模型设置到环境变量
        self._load_llm_settings()
        
        # 创建共享的LLM客户端实例
        self.llm_client = LLMClient()
        
        # 初始化UI组件
        self._init_ui()
        
        # 加载用户设置
        self._load_settings()
        
        # 同步预设分类到侧边栏
        self._sync_categories()
        
        # 更新状态栏显示模型状态
        self._update_status_message()
        
        self.logger.info("主窗口已初始化")
    
    def _load_llm_settings(self):
        """从设置读取LLM配置并设置环境变量"""
        settings = QSettings("NewsAnalyzer", "NewsAggregator")
        
        # 读取API设置
        api_key = settings.value("llm/api_key", "")
        api_url = settings.value("llm/api_url", "")
        model_name = settings.value("llm/model_name", "")
        
        # 设置环境变量
        if api_key:
            os.environ["LLM_API_KEY"] = api_key
        if api_url:
            os.environ["LLM_API_URL"] = api_url
        if model_name:
            os.environ["LLM_MODEL"] = model_name
    
    def _update_status_message(self):
        """更新状态栏显示模型信息"""
        if hasattr(self, 'llm_client') and self.llm_client.api_key:
            self.status_label.setText(f"语言模型已就绪: {self.llm_client.model}")
        else:
            self.status_label.setText("语言模型未配置，请设置API密钥")
    
    def _init_ui(self):
        """初始化UI组件"""
        # 创建中央窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建搜索面板
        self.search_panel = SearchPanel()
        main_layout.addWidget(self.search_panel)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)  # 分割器占据主要空间
        
        # 创建左侧分类侧边栏
        self.sidebar = CategorySidebar()
        splitter.addWidget(self.sidebar)
        
        # 创建中间新闻列表面板
        self.news_list = NewsListPanel()
        splitter.addWidget(self.news_list)
        
        # 导入历史面板
        try:
            from news_analyzer.ui.history_panel import HistoryPanel
            has_history_panel = True
        except ImportError:
            has_history_panel = False
            self.logger.warning("未找到历史面板模块，将不加载此功能")
        
        # 右侧标签页面板
        self.right_panel = QTabWidget()
        self.right_panel.setTabPosition(QTabWidget.North)
        self.right_panel.setStyleSheet("""
            QTabWidget::pane { 
                border: 1px solid #cccccc; 
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #f8f8f8;
                border: 1px solid #cccccc;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 6px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover {
                background-color: #f0f0f0;
            }
        """)
        
        # 创建聊天面板 - 使用共享LLM客户端
        self.chat_panel = ChatPanel()
        self.chat_panel.llm_client = self.llm_client
        
        # 创建LLM分析面板 - 使用共享LLM客户端
        self.llm_panel = LLMPanel()
        self.llm_panel.llm_client = self.llm_client
        
        # 添加标签页，默认显示聊天标签
        self.right_panel.addTab(self.chat_panel, "聊天")
        self.right_panel.addTab(self.llm_panel, "分析")
        
        # 如果历史面板可用，添加历史标签页
        if has_history_panel:
            self.history_panel = HistoryPanel(self.storage)
            # 连接历史加载信号
            self.history_panel.history_loaded.connect(self.load_history_news)
            self.right_panel.addTab(self.history_panel, "历史")
        
        # 添加右侧面板到分割器
        splitter.addWidget(self.right_panel)
        
        # 设置分割器比例
        splitter.setSizes([200, 500, 500])  # 左:中:右 宽度比例
        
        # 连接信号和槽
        self.search_panel.search_requested.connect(self.search_news)
        self.sidebar.category_selected.connect(self.filter_by_category)
        self.news_list.item_selected.connect(self._on_news_selected)
        
        # 添加新的连接 - 新闻列表更新时更新聊天面板的可用新闻标题
        self.news_list.news_updated.connect(self._update_chat_panel_news)
        
        # 创建菜单、工具栏和状态栏
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_statusbar()
    
    def _update_chat_panel_news(self, news_items):
        """更新聊天面板中的可用新闻标题"""
        if hasattr(self, 'chat_panel') and hasattr(self.chat_panel, 'set_available_news_titles'):
            self.chat_panel.set_available_news_titles(news_items)
    
    def load_history_news(self, news_items):
        """
        处理历史新闻加载
        
        Args:
            news_items: 新闻条目列表
        """
        # 更新新闻列表
        self.news_list.update_news(news_items)
        
        # 更新缓存
        self.rss_collector.news_cache = news_items
        
        # 更新状态栏
        self.status_label.setText(f"已加载 {len(news_items)} 条历史新闻")
        
        # 更新聊天面板的可用新闻
        self.chat_panel.set_available_news_titles(news_items)
        
        # 切换到新闻列表选项卡
        if hasattr(self, 'right_panel'):
            self.right_panel.setCurrentIndex(1)  # 切换到分析面板
        
        self.logger.info(f"从历史记录加载了 {len(news_items)} 条新闻")
    
    def _create_actions(self):
        """创建菜单和工具栏动作"""
        # 添加新闻源
        self.add_source_action = QAction("添加新闻源", self)
        self.add_source_action.setStatusTip("添加新的RSS新闻源")
        self.add_source_action.triggered.connect(self.add_news_source)
        
        # 刷新新闻
        self.refresh_action = QAction("刷新新闻", self)
        self.refresh_action.setStatusTip("获取最新新闻")
        self.refresh_action.triggered.connect(self.refresh_news)
        
        # 设置
        self.settings_action = QAction("设置", self)
        self.settings_action.setStatusTip("修改应用程序设置")
        self.settings_action.triggered.connect(self.show_settings)
        
        # 语言模型设置
        self.llm_settings_action = QAction("语言模型设置", self)
        self.llm_settings_action.setStatusTip("配置语言模型API设置")
        self.llm_settings_action.triggered.connect(self._show_llm_settings)
        
        # 退出
        self.exit_action = QAction("退出", self)
        self.exit_action.setStatusTip("退出应用程序")
        self.exit_action.triggered.connect(self.close)
        
        # 关于
        self.about_action = QAction("关于", self)
        self.about_action.setStatusTip("显示关于信息")
        self.about_action.triggered.connect(self.show_about)
    
    def _create_menus(self):
        """创建菜单栏"""
        # 文件菜单
        file_menu = self.menuBar().addMenu("文件")
        file_menu.addAction(self.add_source_action)
        file_menu.addAction(self.refresh_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)
        
        # 工具菜单
        tools_menu = self.menuBar().addMenu("工具")
        tools_menu.addAction(self.settings_action)
        tools_menu.addAction(self.llm_settings_action)
        
        # 帮助菜单
        help_menu = self.menuBar().addMenu("帮助")
        help_menu.addAction(self.about_action)
    
    def _create_toolbars(self):
        """创建工具栏"""
        main_toolbar = self.addToolBar("主工具栏")
        main_toolbar.setMovable(False)
        main_toolbar.setIconSize(QSize(24, 24))
        
        main_toolbar.addAction(self.add_source_action)
        main_toolbar.addAction(self.refresh_action)
        main_toolbar.addSeparator()
        main_toolbar.addAction(self.llm_settings_action)
    
    def _create_statusbar(self):
        """创建状态栏"""
        self.status_label = QLabel("就绪")
        self.statusBar().addPermanentWidget(self.status_label)
    
    def _load_settings(self):
        """加载应用程序设置"""
        settings = QSettings("NewsAnalyzer", "NewsAggregator")
        
        # 加载窗口位置和大小
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        # 加载用户添加的RSS源
        sources = settings.value("user_rss_sources", [])
        if sources:
            for source in sources:
                self.rss_collector.add_source(source['url'], source['name'], source['category'])
    
    def _sync_categories(self):
        """将RSS收集器中的所有分类同步到侧边栏"""
        # 获取所有分类
        categories = set()
        for source in self.rss_collector.get_sources():
            categories.add(source['category'])
        
        # 添加到侧边栏
        for category in sorted(categories):
            self.sidebar.add_category(category)
            
        self.logger.info(f"同步了 {len(categories)} 个分类到侧边栏")
    
    def _save_settings(self):
        """保存应用程序设置"""
        settings = QSettings("NewsAnalyzer", "NewsAggregator")
        
        # 保存窗口位置和大小
        settings.setValue("geometry", self.saveGeometry())
        
        # 保存用户添加的RSS源
        # 注意：预设源不需要保存，因为会在启动时自动加载
        user_sources = []
        default_urls = {s['url'] for s in self.rss_collector.get_sources() 
                        if not s.get('is_user_added', False)}
        
        for source in self.rss_collector.get_sources():
            if source['url'] not in default_urls or source.get('is_user_added', False):
                source['is_user_added'] = True
                user_sources.append(source)
        
        settings.setValue("user_rss_sources", user_sources)
    
    def _on_news_selected(self, news_item):
        """处理新闻选择事件"""
        # 更新分析面板
        self.llm_panel.analyze_news(news_item)
        
        # 更新聊天面板
        self.chat_panel.set_current_news(news_item)
        
        # 自动勾选聊天面板的新闻上下文选项
        if hasattr(self, 'chat_panel') and hasattr(self.chat_panel, 'context_checkbox'):
            self.chat_panel.context_checkbox.setChecked(True)
    
    def add_news_source(self):
        """添加新闻源"""
        dialog = AddSourceDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            values = dialog.get_values()
            
            if not values['url']:
                QMessageBox.warning(self, "输入错误", "请输入有效的RSS URL")
                return
            
            url = values['url']
            name = values['name'] or url.split("//")[-1].split("/")[0]
            category = values['category']
            
            try:
                self.rss_collector.add_source(url, name, category, is_user_added=True)
                self.sidebar.add_category(category)
                self.status_label.setText(f"已添加新闻源: {name}")
                
                # 立即获取此源的新闻
                self.refresh_news(url)
                
                self.logger.info(f"添加了新闻源: {name} ({url}), 分类: {category}")
            except Exception as e:
                QMessageBox.critical(self, "添加失败", f"无法添加新闻源: {str(e)}")
                self.logger.error(f"添加新闻源失败: {str(e)}")
    
    def refresh_news(self, source_url=None):
        """刷新新闻
        
        Args:
            source_url: 可选，特定源的URL
        """
        self.status_label.setText("正在获取新闻...")
        
        try:
            if source_url:
                # 刷新特定源
                news_items = self.rss_collector.fetch_from_source(source_url)
                count = len(news_items)
                self.status_label.setText(f"已获取 {count} 条新闻")
            else:
                # 刷新所有源
                news_items = self.rss_collector.fetch_all()
                count = len(news_items)
                self.status_label.setText(f"已获取 {count} 条新闻")
            
            # 更新新闻列表
            self.news_list.update_news(news_items)
            
            # 更新聊天面板的可用新闻
            self.chat_panel.set_available_news_titles(news_items)
            
            # 保存到存储
            self.storage.save_news(news_items)
            
            self.logger.info(f"已刷新新闻，获取了 {count} 条")
        except Exception as e:
            QMessageBox.warning(self, "刷新失败", f"获取新闻失败: {str(e)}")
            self.status_label.setText("刷新失败")
            self.logger.error(f"刷新新闻失败: {str(e)}")
    
    def search_news(self, query):
        """搜索新闻
        
        Args:
            query: 搜索关键词
        """
        if not query:
            # 如果搜索词为空，显示所有新闻
            news_items = self.rss_collector.get_all_news()
            self.news_list.update_news(news_items)
            self.chat_panel.set_available_news_titles(news_items)
            self.status_label.setText("显示所有新闻")
            return
        
        self.status_label.setText(f"搜索: {query}")
        
        try:
            # 执行搜索
            results = self.rss_collector.search_news(query)
            
            # 更新新闻列表
            self.news_list.update_news(results)
            
            # 更新聊天面板的可用新闻
            self.chat_panel.set_available_news_titles(results)
            
            count = len(results)
            self.status_label.setText(f"搜索 '{query}' 找到 {count} 条结果")
            self.logger.info(f"搜索 '{query}' 找到 {count} 条结果")
        except Exception as e:
            QMessageBox.warning(self, "搜索失败", f"搜索新闻失败: {str(e)}")
            self.status_label.setText("搜索失败")
            self.logger.error(f"搜索新闻失败: {str(e)}")
    
    def filter_by_category(self, category):
        """按分类筛选新闻
        
        Args:
            category: 分类名称
        """
        if category == "所有":
            # 显示所有新闻
            news_items = self.rss_collector.get_all_news()
            self.news_list.update_news(news_items)
            self.chat_panel.set_available_news_titles(news_items)
            self.status_label.setText("显示所有新闻")
            return
        
        self.status_label.setText(f"分类: {category}")
        
        try:
            # 获取该分类的新闻
            results = self.rss_collector.get_news_by_category(category)
            
            # 更新新闻列表
            self.news_list.update_news(results)
            
            # 更新聊天面板的可用新闻
            self.chat_panel.set_available_news_titles(results)
            
            count = len(results)
            self.status_label.setText(f"分类 '{category}' 包含 {count} 条新闻")
            self.logger.info(f"筛选分类 '{category}' 找到 {count} 条新闻")
        except Exception as e:
            QMessageBox.warning(self, "筛选失败", f"筛选新闻失败: {str(e)}")
            self.status_label.setText("筛选失败")
            self.logger.error(f"筛选新闻失败: {str(e)}")
    
    def show_settings(self):
        """显示设置对话框"""
        # 在这里实现设置对话框
        QMessageBox.information(self, "设置", "设置功能开发中...")
    
    def _show_llm_settings(self):
        """显示语言模型设置对话框"""
        dialog = LLMSettingsDialog(self)
        if dialog.exec_():
            dialog.save_settings()
            
            # 重新加载设置到环境变量
            self._load_llm_settings()
            
            # 创建新的LLM客户端
            self.llm_client = LLMClient()
            
            # 更新各面板的LLM客户端引用
            self.llm_panel.llm_client = self.llm_client
            self.chat_panel.llm_client = self.llm_client
            
            # 更新状态栏
            self._update_status_message()
            
            self.logger.info("语言模型设置已更新")
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于", 
                          "新闻聚合与分析系统 v1.0\n\n"
                          "一个集成了LLM功能的新闻聚合工具，\n"
                          "支持搜索、分类、智能分析和聊天交互。")
    
    def closeEvent(self, event):
        """窗口关闭事件处理"""
        # 保存设置
        self._save_settings()
        
        # 确认退出
        reply = QMessageBox.question(self, '确认退出', 
                                     "确定要退出程序吗?", 
                                     QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.logger.info("应用程序关闭")
            event.accept()
        else:
            event.ignore()