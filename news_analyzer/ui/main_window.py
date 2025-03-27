#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主窗口模块 - 包含应用程序主界面

该模块实现了应用程序的主窗口，整合侧边栏、新闻列表和LLM面板等UI组件。
"""

import os
import logging
import threading
import queue # 添加 queue
from datetime import datetime
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QSplitter, QAction, QMenuBar, QStatusBar,
                            QToolBar, QMessageBox, QDialog, QLabel,
                            QLineEdit, QPushButton, QFormLayout, QTabWidget,
                            QApplication)
from PyQt5.QtCore import Qt, QSize, QSettings, QTimer # 移除 pyqtSignal
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
    # 移除 refresh_done 信号

    def __init__(self, storage, rss_collector=None):
        super().__init__()
        # 创建队列和 Timer
        self.refresh_queue = queue.Queue()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(100) # 每 100ms 检查一次队列
        self.refresh_timer.timeout.connect(self._check_refresh_queue)

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

        # 用于存储已读新闻的ID (使用link作为ID)
        self.read_news_ids = set()
        # 初始化UI组件
        self._init_ui()

        # 加载用户设置
        self._load_settings()

        # 同步预设分类到侧边栏
        self._sync_categories()

        # 更新状态栏显示模型状态
        self._update_status_message()

        # 启动时加载并显示上次的新闻
        self._load_and_display_initial_news()

        # 移除信号连接
        # self.refresh_done.connect(self._on_refresh_complete)

        self.logger.info("主窗口已初始化")
        # 检查 refresh_action 状态
        if hasattr(self, 'refresh_action'):
            self.logger.info(f"初始化后 refresh_action enabled: {self.refresh_action.isEnabled()}")
        else:
            self.logger.error("初始化后 self.refresh_action 不存在！")


    def _load_and_display_initial_news(self):
        """加载并显示初始新闻列表"""
        try:
            self.status_label.setText("正在加载历史新闻...")
            QApplication.processEvents()
            # 加载最新的新闻文件
            initial_news = self.storage.load_news()
            if initial_news:
                # 更新收集器缓存
                self.rss_collector.news_cache = initial_news
                # 更新新闻列表UI
                self.news_list.update_news(initial_news)
                # 传递已读ID给列表面板
                self.news_list.set_read_ids(self.read_news_ids)
                # 更新聊天面板可用新闻
                self._update_chat_panel_news(initial_news) # 使用初始加载的新闻
                self.status_label.setText(f"已加载 {len(initial_news)} 条历史新闻")
                self.logger.info(f"启动时加载了 {len(initial_news)} 条历史新闻")
            else:
                self.status_label.setText("未找到历史新闻，请刷新")
        except Exception as e:
            self.logger.error(f"启动时加载新闻失败: {str(e)}")
            self.status_label.setText("加载历史新闻失败")

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

        # 先创建菜单、工具栏和状态栏 (尝试解决 AttributeError)
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_statusbar()

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
            # 初始化时传递已读ID
            self.history_panel.set_read_ids(self.read_news_ids)
            # 连接历史加载信号 (恢复)
            self.history_panel.history_loaded.connect(self.load_history_news)
            self.right_panel.addTab(self.history_panel, "历史")

        # 添加右侧面板到分割器
        splitter.addWidget(self.right_panel)

        # 设置分割器比例
        splitter.setSizes([200, 500, 500])  # 左:中:右 宽度比例

        # 连接信号和槽
        self.search_panel.search_requested.connect(self.search_news)
        self.sidebar.category_selected.connect(self.filter_by_category)
        # 新增：将分类选择信号连接到聊天面板
        self.sidebar.category_selected.connect(self.chat_panel.set_current_category)
        self.news_list.item_selected.connect(self._on_news_selected)

        # 添加新的连接 - 新闻列表更新时更新聊天面板的可用新闻标题
        self.news_list.news_updated.connect(self._update_chat_panel_news)
        # 移除查找相关报道的信号连接
        # self.news_list.related_news_requested.connect(self._handle_related_news_request)

    def _update_chat_panel_news(self, news_items):
        """更新聊天面板中的可用新闻标题"""
        # news_items 参数现在是 news_list 中实际显示的新闻
        # 但聊天面板应该能访问所有缓存的新闻
        if hasattr(self, 'chat_panel') and hasattr(self.chat_panel, 'set_available_news_titles'):
            all_cached_news = self.rss_collector.get_all_news()
            self.chat_panel.set_available_news_titles(all_cached_news)
            self.logger.debug(f"更新聊天面板可用新闻标题，共 {len(all_cached_news)} 条")


    def load_history_news(self, news_items):
        """
        处理历史新闻加载

        Args:
            news_items: 新闻条目列表
        """
        # 传递已读ID给列表面板
        self.news_list.set_read_ids(self.read_news_ids)
        # 更新新闻列表
        self.news_list.update_news(news_items)

        # 更新缓存
        self.rss_collector.news_cache = news_items
        # 更新状态栏
        self.status_label.setText(f"已加载 {len(news_items)} 条历史新闻")

        # 更新聊天面板的可用新闻
        self._update_chat_panel_news(news_items) # 使用更新后的缓存

        # 切换到新闻列表选项卡 (可能切换到分析面板更合适?)
        if hasattr(self, 'right_panel'):
             # 切换到分析面板，让用户看到分析结果
            llm_tab_index = -1
            for i in range(self.right_panel.count()):
                if self.right_panel.tabText(i) == "分析":
                    llm_tab_index = i
                    break
            if llm_tab_index != -1:
                self.right_panel.setCurrentIndex(llm_tab_index)

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
                # 标记为用户添加，以便保存时区分
                self.rss_collector.add_source(source['url'], source['name'], source['category'], is_user_added=True)

        # 加载已读新闻ID
        read_ids_list = settings.value("read_news_ids", [])
        if isinstance(read_ids_list, list): # 确保加载的是列表
            self.read_news_ids = set(read_ids_list)
            self.logger.info(f"加载了 {len(self.read_news_ids)} 个已读新闻ID")
        else:
            self.logger.warning("加载已读新闻ID失败，设置中的格式不正确")
            self.read_news_ids = set() # 如果格式错误，则重置为空集合


    def _sync_categories(self):
        """将RSS收集器中的所有分类同步到侧边栏"""
        # 获取所有分类 (包括预设和用户添加的)
        categories = set()
        for source in self.rss_collector.get_sources():
            categories.add(source['category'])

        # 清空并重新填充侧边栏
        self.sidebar.category_list.clear() # 使用 QListWidget 的 clear 方法
        self.sidebar.categories.clear() # 清空内部的 categories 集合

        self.sidebar.add_category("所有") # 确保"所有"始终在顶部
        for category in sorted(list(categories)):
             if category != "所有": # 避免重复添加
                self.sidebar.add_category(category)

        self.logger.info(f"同步了 {len(categories)} 个分类到侧边栏")

    def _save_settings(self):
        """保存应用程序设置"""
        settings = QSettings("NewsAnalyzer", "NewsAggregator")

        # 保存窗口位置和大小
        settings.setValue("geometry", self.saveGeometry())

        # 保存用户添加的RSS源
        user_sources = [s for s in self.rss_collector.get_sources() if s.get('is_user_added', False)]
        settings.setValue("user_rss_sources", user_sources)
        self.logger.info(f"保存了 {len(user_sources)} 个用户添加的RSS源")

        # 保存已读新闻ID (将集合转换为列表)
        settings.setValue("read_news_ids", list(self.read_news_ids))
        self.logger.info(f"保存了 {len(self.read_news_ids)} 个已读新闻ID")


    def _on_news_selected(self, news_item):
        """处理新闻选择事件"""
        if not news_item:
            return
        # 更新分析面板
        self.llm_panel.analyze_news(news_item)

        # 更新聊天面板
        self.chat_panel.set_current_news(news_item)

        # 自动勾选聊天面板的新闻上下文选项
        if hasattr(self, 'chat_panel') and hasattr(self.chat_panel, 'context_checkbox'):
            self.chat_panel.context_checkbox.setChecked(True)

        # --- 标记新闻为已读 ---
        news_link = news_item.get('link')
        if news_link and news_link not in self.read_news_ids:
            self.read_news_ids.add(news_link)
            self.logger.debug(f"新闻标记为已读: {news_link}")
            # 同时更新历史面板的已读状态 (如果存在)
            if hasattr(self, 'history_panel'):
                self.history_panel.set_read_ids(self.read_news_ids)
            # 触发新闻列表更新已读状态显示
            # 重新应用当前列表数据和已读状态
            current_displayed_news = self.news_list.current_news # 获取当前列表显示的数据
            self.news_list.update_news(current_displayed_news) # 重新加载数据
            self.news_list.set_read_ids(self.read_news_ids) # 确保应用最新的已读状态

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
                # 添加源并标记为用户添加
                self.rss_collector.add_source(url, name, category, is_user_added=True)
                # 更新侧边栏
                self._sync_categories() # 使用同步方法确保分类不重复
                self.status_label.setText(f"已添加新闻源: {name}")

                # 添加源后，触发一次基于当前侧边栏选择的刷新
                self.refresh_news()

                self.logger.info(f"添加了新闻源: {name} ({url}), 分类: {category}")
            except Exception as e:
                QMessageBox.critical(self, "添加失败", f"无法添加新闻源: {str(e)}")
                self.logger.error(f"添加新闻源失败: {str(e)}")

    def refresh_news(self):
        """启动后台线程刷新新闻"""
        self.logger.info("refresh_news 方法被调用") # 添加日志
        self.status_label.setText("正在获取新闻...")
        self.refresh_action.setEnabled(False) # 禁用刷新动作
        QApplication.processEvents() # 强制UI更新

        # 启动 Timer (如果尚未运行)
        if not self.refresh_timer.isActive():
            self.refresh_timer.start()

        # 创建并启动后台线程
        thread = threading.Thread(target=self._fetch_news_worker, daemon=True)
        thread.start()

    def _fetch_news_worker(self):
        """在后台线程中执行实际的新闻获取和保存"""
        try:
            selected_category = self.sidebar.get_current_category()
            fetched_news = []
            log_count = 0

            if selected_category == "所有":
                self.logger.info("后台刷新所有新闻源...")
                fetched_news = self.rss_collector.fetch_all()
                log_count = len(fetched_news)
            else:
                self.logger.info(f"后台刷新分类 '{selected_category}' 的新闻源...")
                fetched_news = self.rss_collector.fetch_by_category(selected_category)
                log_count = len(fetched_news)

            # 保存到存储 (始终保存更新后的完整缓存)
            all_news_cache = self.rss_collector.get_all_news()
            self.storage.save_news(all_news_cache)

            # 准备成功消息和数据
            news_to_display = []
            if selected_category == "所有":
                 news_to_display = all_news_cache
                 refresh_msg = f"已刷新所有源，获取 {log_count} 条新新闻，当前共 {len(news_to_display)} 条"
            else:
                 news_to_display = self.rss_collector.get_news_by_category(selected_category)
                 refresh_msg = f"已刷新分类 '{selected_category}'，获取 {log_count} 条新新闻，该分类共 {len(news_to_display)} 条"

            self.logger.info(refresh_msg)
            # 将结果放入队列
            self.refresh_queue.put((True, refresh_msg, news_to_display))
        # 添加 except 块
        except Exception as e:
            error_msg = f"获取新闻失败: {str(e)}"
            self.logger.error(f"后台刷新新闻失败: {str(e)}")
            # 将错误结果放入队列
            self.refresh_queue.put((False, error_msg, []))

    def _check_refresh_queue(self):
        """检查刷新结果队列并处理"""
        try:
            # 非阻塞获取结果
            success, message, news_to_display = self.refresh_queue.get_nowait()
            # 如果获取到结果，处理它
            self._on_refresh_complete(success, message, news_to_display)
            # 可选：如果只需要处理一次结果，可以在这里停止 timer
            # self.refresh_timer.stop()
        except queue.Empty:
            # 队列为空，什么也不做
            pass
        except Exception as e:
            # 处理可能的其他异常
            self.logger.error(f"检查刷新队列时出错: {e}", exc_info=True)
            # 确保 UI 不会卡住，恢复刷新按钮
            self.refresh_action.setEnabled(True)
            self.status_label.setText("处理刷新结果时出错")
            # 可选：停止 timer
            # self.refresh_timer.stop()

    # 这个方法现在是普通方法，不再是槽函数
    def _on_refresh_complete(self, success, message, news_to_display):
        """处理后台刷新完成的信号"""
        self.refresh_action.setEnabled(True) # 恢复刷新动作可用
        self.status_label.setText(message) # 更新状态栏

        if success:
            # 更新新闻列表UI
            self.news_list.update_news(news_to_display)
            # 传递已读ID给列表面板
            self.news_list.set_read_ids(self.read_news_ids)
            # 更新聊天面板的可用新闻 (始终使用完整的缓存)
            self._update_chat_panel_news(self.rss_collector.get_all_news())
            # 显示成功提示框
            QMessageBox.information(self, "刷新完成", message)
            # --- 更新历史面板的导出列表 ---
            if hasattr(self, 'history_panel'):
                try:
                    self.history_panel._refresh_export_combo()
                    self.logger.info("已触发历史面板导出列表刷新")
                except Exception as e:
                    self.logger.error(f"刷新历史面板导出列表时出错: {e}")
            # ------------------------------
        else:
            # 显示失败提示框
            QMessageBox.warning(self, "刷新失败", message)

    def search_news(self, search_params):
        """
        根据关键词和字段搜索新闻

        Args:
            search_params (dict): 包含 'query', 'field' 的字典
        """
        query = search_params.get("query", "")
        field = search_params.get("field", "标题和内容")
        # 移除了 days = search_params.get("days", 30)

        # 检查是否所有筛选条件都为空
        is_filtering = bool(query) # 只检查 query

        if not is_filtering:
            # 如果所有筛选条件都为空，恢复显示当前分类的新闻
            current_category = self.sidebar.get_current_category()
            self.logger.info(f"搜索条件为空，恢复显示分类: '{current_category}'")
            self.filter_by_category(current_category) # 复用分类筛选逻辑
            self.status_label.setText("搜索条件已清除")
            return

        self.status_label.setText("正在执行搜索...")
        QApplication.processEvents()

        try:
            # 从所有缓存的新闻中搜索
            all_news = self.rss_collector.get_all_news()
            results = []

            for news in all_news:
                # 1. 文本匹配
                text_match = False
                if query:
                    title = news.get('title', '').lower()
                    summary = news.get('summary', '').lower()
                    query_lower = query.lower()

                    if field == "标题和内容":
                        text_match = query_lower in title or query_lower in summary
                    elif field == "仅标题":
                        text_match = query_lower in title
                    elif field == "仅内容":
                        text_match = query_lower in summary
                else:
                    text_match = True # 如果没有查询文本，则文本条件视为匹配

                # 移除了日期匹配逻辑

                # 3. 结合条件 (只剩文本匹配)
                if text_match: # 只检查 text_match
                    results.append(news)

            # 更新新闻列表
            self.news_list.update_news(results)

            # 传递已读ID给列表面板
            self.news_list.set_read_ids(self.read_news_ids)

            # 更新聊天面板的可用新闻 (与列表保持一致)
            self._update_chat_panel_news(results)

            # 更新状态栏
            count = len(results)
            search_desc = f"'{query}'" if query else "所有新闻"
            # 移除了日期描述

            self.status_label.setText(f"搜索 {search_desc} 找到 {count} 条结果") # 更新状态文本
            self.logger.info(f"搜索参数: {search_params}, 找到 {count} 条结果")

        except Exception as e:
            self.logger.error(f"搜索新闻时出错: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "搜索错误", f"搜索新闻时发生错误: {str(e)}")
            self.status_label.setText("搜索失败")

    def filter_by_category(self, category):
        """按分类筛选新闻 (仅筛选显示，不获取新数据)

        Args:
            category: 分类名称
        """
        self.logger.info(f"筛选显示分类: '{category}'")
        news_to_display = []
        status_msg = ""

        if category == "所有":
            # 显示所有缓存的新闻
            news_to_display = self.rss_collector.get_all_news()
            status_msg = f"显示所有 {len(news_to_display)} 条缓存新闻"
        else:
            try:
                # 从缓存中获取该分类的新闻
                news_to_display = self.rss_collector.get_news_by_category(category)
                status_msg = f"显示分类 '{category}' 的 {len(news_to_display)} 条缓存新闻"
            except Exception as e:
                QMessageBox.warning(self, "筛选失败", f"筛选新闻失败: {str(e)}")
                self.status_label.setText("筛选失败")
                self.logger.error(f"筛选新闻失败: {str(e)}")
                return # 出现错误则不继续

        # 更新新闻列表UI
        self.news_list.update_news(news_to_display)

        # 传递已读ID给列表面板
        self.news_list.set_read_ids(self.read_news_ids)

        # 更新聊天面板的可用新闻 (与列表保持一致)
        self._update_chat_panel_news(news_to_display)

        # 更新状态栏
        self.status_label.setText(status_msg)
        self.logger.info(status_msg)


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


    # 移除 _handle_related_news_request 方法
    # def _handle_related_news_request(self, news_link):
    #     ...

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
