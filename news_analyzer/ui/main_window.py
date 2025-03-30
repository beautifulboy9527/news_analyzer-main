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
from datetime import datetime, timedelta # 确保导入 timedelta
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QAction, QMenuBar, QStatusBar,
                             QToolBar, QMessageBox, QDialog, QLabel,
                             QLineEdit, QPushButton, QFormLayout, QTabWidget,
                             QApplication, QProgressBar)
from PyQt5.QtCore import Qt, QSize, QSettings, QTimer, pyqtSlot # 导入 pyqtSlot
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor # 导入 QPalette, QColor

from news_analyzer.ui.sidebar import CategorySidebar
from news_analyzer.ui.news_list import NewsListPanel
from news_analyzer.ui.search_panel import SearchPanel
from news_analyzer.ui.llm_panel import LLMPanel
from news_analyzer.ui.chat_panel import ChatPanel
from news_analyzer.ui.llm_settings import LLMSettingsDialog
# from news_analyzer.collectors.rss_collector import RSSCollector # 不再直接使用
from news_analyzer.llm.llm_client import LLMClient
from news_analyzer.ui.source_management_panel import SourceManagementPanel # 移动导入到这里
from news_analyzer.ui.import_export_dialog import ImportExportDialog # NEW Import
from news_analyzer.ui.news_detail_dialog import NewsDetailDialog # 导入新闻详情对话框

# from news_analyzer.ui.refresh_dialog import RefreshProgressDialog # 不再需要导入刷新对话框
# 导入 AppService 和 Models 以便类型提示
from news_analyzer.core.app_service import AppService
from news_analyzer.models import NewsSource, NewsArticle


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

    # --- Theme Styles (Moved inside the class) ---
    LIGHT_THEME = """
        /* 浅色主题 - V9 - 结构同步深色主题 */
        QWidget {
            background-color: #f8f9fa; /* 浅灰背景 */
            color: #212529; /* 深色文字 */
            font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        }
        QMainWindow, QDialog {
            background-color: #ffffff; /* 白色窗口/弹窗背景 */
        }
        QDialog { border: 1px solid #dee2e6; border-radius: 6px; } /* 浅灰边框 */
        QMenuBar { background-color: #ffffff; border-bottom: 1px solid #dee2e6; padding: 5px 0; }
        QMenuBar::item { padding: 8px 15px; border-radius: 4px; color: #212529; }
        QMenuBar::item:selected { background-color: #e9ecef; color: #000000; } /* 选中背景/文字 */
        QMenu { background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 6px; padding: 5px; }
        QMenu::item { padding: 8px 30px 8px 20px; min-width: 120px; color: #212529; }
        QMenu::item:selected { background-color: #e9ecef; color: #000000; }
        QPushButton {
            background-color: #ffffff; border: 1px solid #ced4da; padding: 8px 16px; /* 按钮边框稍深 */
            border-radius: 6px; color: #212529; min-height: 32px;
        }
        QPushButton:hover { background-color: #f1f3f5; border-color: #adb5bd; }
        QPushButton:pressed { background-color: #e9ecef; }

        /* --- 通用输入控件 --- */
        QLineEdit, QTextEdit, QComboBox {
            background-color: #ffffff; border: 1px solid #ced4da; color: #212529;
            border-radius: 6px; padding: 8px; min-height: 32px;
            selection-background-color: #a5d8ff; selection-color: #000000; /* 浅蓝选中 */
        }
        /* --- QListWidget 和 QTextBrowser 基础样式 --- */
        QListWidget, QTextBrowser {
             border: 1px solid #dee2e6; /* 统一边框 */
             background-color: #ffffff; /* 确保白色背景 */
             color: #212529; /* 确保文字颜色 */
        }
        /* 强制Viewport背景 */
        QAbstractItemView::viewport {
            background-color: #ffffff; /* 确保Viewport是白色 */
            border: none;
        }
        QTextBrowser {
             padding: 8px;
        }

        /* --- 使用 ID 选择器强制样式 --- */
        #sidebarList, #newsListWidget { /* 侧边栏和新闻列表 */
            background-color: #ffffff;
            border: 1px solid #dee2e6;
            color: #212529;
        }
        #sidebarList::item, #newsListWidget::item {
            padding: 12px 12px;
            color: #495057; /* 列表项文字 */
            border-radius: 4px;
            background-color: transparent;
            border: none;
        }
        #sidebarList::item:selected, #newsListWidget::item:selected {
            background-color: #d0ebff; /* 浅蓝选中背景 */
            color: #1971c2; /* 选中文字 */
        }
        #sidebarList::item:hover:!selected, #newsListWidget::item:hover:!selected {
             background-color: #e9ecef; /* 悬停背景 */
             color: #000000;
        }

        #chatArea, #llmResultBrowser { /* 聊天区和分析结果区 */
            background-color: #ffffff;
            border: 1px solid #dee2e6;
            color: #212529;
        }
        #chatArea > QWidget > QWidget { /* 聊天区视口 */
             background-color: #ffffff;
             border: none;
        }
        #llmResultBrowser { /* 分析结果区特定样式 */
             padding: 8px;
             background-color: #f8f9fa; /* 稍灰背景 */
             border: 1px solid #e9ecef;
             color: #212529;
        }

        #chatInput { /* 聊天输入框 */
             background-color: #ffffff;
             border: 1px solid #ced4da;
             color: #212529;
             selection-background-color: #a5d8ff;
             selection-color: #000000;
        }

        #dateFilterGroup { /* 日期筛选区域 - 提高可视性 */
            background-color: #f1f3f5; /* 稍深背景 */
            border: 1px solid #dee2e6; /* 边框 */
            color: #212529; /* 文字 */
            margin-top: 8px;
            padding: 8px;
        }
        #dateFilterGroup QGroupBox::title {
             color: #212529; margin-top: -8px; padding: 0 5px; left: 10px;
        }
        #dateFilterGroup QRadioButton,
        #dateFilterGroup QLineEdit,
        #dateFilterGroup QDateEdit,
        #dateFilterGroup QLabel,
        #dateFilterGroup QCheckBox {
            color: #212529;
        }
        #dateFilterGroup QLineEdit,
        #dateFilterGroup QDateEdit {
            background-color: #ffffff; /* 白色背景 */
            border: 1px solid #ced4da;
            color: #212529;
        }
        /* 确保其他 QGroupBox 也应用浅色 */
        QGroupBox {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            color: #212529;
            margin-top: 12px;
            padding: 12px;
        }
        QGroupBox::title {
             color: #212529; margin-top: -6px; padding: 0 8px; left: 12px;
        }

        /* --- 滚动条样式 (浅色) --- */
        QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }
        QScrollBar::handle:vertical { background: #adb5bd; min-height: 25px; border-radius: 3px; border: none; opacity: 0.6; } /* 浅灰滑块 */
        QScrollBar::handle:vertical:hover { background: #868e96; opacity: 1.0; } /* 悬停加深 */
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { border: none; background: none; height: 0px; }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        QScrollBar:horizontal { border: none; background: transparent; height: 6px; margin: 0px; }
        QScrollBar::handle:horizontal { background: #adb5bd; min-width: 25px; border-radius: 3px; border: none; opacity: 0.6; }
        QScrollBar::handle:horizontal:hover { background: #868e96; opacity: 1.0; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { border: none; background: none; width: 0px; }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }

        /* --- 特定控件微调 (浅色) --- */
        #update_news_button { /* 突出更新按钮 */
             background-color: #20c997; /* 浅绿色背景 */
             color: #ffffff; /* 白色文字 */
             font-weight: bold;
             border: 1px solid #1aab8a; /* 深一点的绿色边框 */
        }
        #update_news_button:hover { background-color: #1baa85; border-color: #178f71; }
        /* 确保 Tab 样式 */
        QTabBar::tab { background-color: #f8f9fa; border: 1px solid #dee2e6; border-bottom: none; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px; color: #495057; }
        QTabBar::tab:selected { background-color: #ffffff; border-bottom: 1px solid #ffffff; color: #212529; }
        QTabBar::tab:hover:!selected { background-color: #e9ecef; color: #000000; }
        QTabWidget::pane { border: 1px solid #dee2e6; border-top: none; border-radius: 0 0 6px 6px; background-color: #ffffff; }
        QSplitter::handle { background-color: #dee2e6; width: 1px; margin: 0 8px; }
        QStatusBar { background-color: #ffffff; border-top: 1px solid #dee2e6; color: #495057; } /* 状态栏文字 */

    """

    DARK_THEME = """
        /* 优雅黑主题 - V9 - Palette生效 + 文字可视性最终调整 */
        QWidget {
            background-color: #111111;
            color: #f0f0f0; /* 最终提高基础文字亮度 */
            font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        }
        QMainWindow, QDialog {
            background-color: #181818;
        }
        QDialog { border: 1px solid #252525; border-radius: 6px; } /* 边框稍亮 */
        QMenuBar { background-color: #181818; border-bottom: 1px solid #252525; padding: 5px 0; }
        QMenuBar::item { padding: 8px 15px; border-radius: 4px; color: #f0f0f0; } /* 菜单文字 */
        QMenuBar::item:selected { background-color: #2a2a2a; color: #ffffff; }
        QMenu { background-color: #181818; border: 1px solid #252525; border-radius: 6px; padding: 5px; }
        QMenu::item { padding: 8px 30px 8px 20px; min-width: 120px; color: #f0f0f0; } /* 菜单项文字 */
        QMenu::item:selected { background-color: #2a2a2a; color: #ffffff; }
        QPushButton {
            background-color: #282828; border: 1px solid #353535; padding: 8px 16px; /* 按钮背景/边框稍亮 */
            border-radius: 6px; color: #f0f0f0; min-height: 32px; /* 按钮文字 */
        }
        QPushButton:hover { background-color: #303030; border-color: #404040; color: #ffffff; }
        QPushButton:pressed { background-color: #222222; }

        /* --- 通用输入控件 --- */
        QLineEdit, QTextEdit, QComboBox {
            background-color: #1e1e1e; border: 1px solid #303030; color: #f0f0f0; /* 输入文字 */
            border-radius: 6px; padding: 8px; min-height: 32px;
            selection-background-color: #3a3a3a; selection-color: #ffffff;
        }
        /* --- QListWidget 和 QTextBrowser 由 Palette 控制，这里只设置基础边框 --- */
        QListWidget, QTextBrowser {
             border: 1px solid #282828; /* 统一边框 */
        }
        /* 强制Viewport背景 (重要!) */
        QAbstractItemView::viewport {
            background-color: #1a1a1a; /* 确保Viewport是深色 */
            border: none;
        }
        QTextBrowser {
             padding: 8px; /* 保留内边距 */
             background-color: #1e1e1e; /* 确保背景 */
             color: #f0f0f0; /* 确保文字颜色 */
        }

        /* --- 使用 ID 选择器强制样式 (主要用于特定背景/边框/文字色) --- */
        /* #sidebarList, #newsListWidget 由 Palette 控制 Base 和 Text */
        #sidebarList::item, #newsListWidget::item { /* 列表项样式 */
            padding: 12px 12px;
            /* color 由 Palette 控制 */
            border-radius: 4px;
            background-color: transparent; /* 确保透明 */
            border: none;
        }
        /* #sidebarList::item:selected, #newsListWidget::item:selected 由 Palette 控制 Highlight/HighlightedText */
        #sidebarList::item:hover:!selected, #newsListWidget::item:hover:!selected {
             background-color: #252525; /* 悬停背景 */
             /* color 由 Palette 控制 */
        }

        #chatArea, #llmResultBrowser { /* 聊天区和分析结果区 */
            background-color: #1a1a1a;
            border: 1px solid #282828;
            color: #f0f0f0;
        }
        #chatArea > QWidget > QWidget { /* 聊天区视口 */
             background-color: #1a1a1a;
             border: none;
        }
        #llmResultBrowser { /* 分析结果区特定样式 */
             padding: 8px;
             background-color: #1e1e1e; /* 使用稍亮的背景 */
             border: 1px solid #303030;
             color: #f0f0f0;
        }

        #chatInput { /* 聊天输入框 */
             background-color: #1e1e1e;
             border: 1px solid #303030;
             color: #f0f0f0;
             selection-background-color: #3a3a3a;
             selection-color: #ffffff;
        }

        #dateFilterGroup { /* 日期筛选区域 - 提高可视性 */
            background-color: #222222; /* 更亮的背景 */
            border: 1px solid #3a3a3a; /* 更亮的边框 */
            color: #f5f5f5; /* 内部文字最亮 */
            margin-top: 8px;
            padding: 8px;
        }
        #dateFilterGroup QGroupBox::title {
             color: #f5f5f5; margin-top: -8px; padding: 0 5px; left: 10px;
        }
        #dateFilterGroup QRadioButton,
        #dateFilterGroup QLineEdit,
        #dateFilterGroup QDateEdit,
        #dateFilterGroup QLabel,
        #dateFilterGroup QCheckBox {
            color: #f5f5f5; /* 确保文字可视性 */
        }
        #dateFilterGroup QLineEdit,
        #dateFilterGroup QDateEdit {
            background-color: #2a2a2a; /* 更亮背景 */
            border: 1px solid #424242;
            color: #f5f5f5;
        }
        /* 确保其他 QGroupBox 也应用深色 */
        QGroupBox {
            background-color: #1a1a1a;
            border: 1px solid #252525;
            color: #e8e8e8; /* GroupBox 内文字 */
            margin-top: 12px;
            padding: 12px;
        }
        QGroupBox::title {
             color: #e8e8e8; margin-top: -6px; padding: 0 8px; left: 12px;
        }

        /* --- 滚动条样式 (优雅黑) --- */
        QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }
        QScrollBar::handle:vertical { background: #383838; min-height: 25px; border-radius: 3px; border: none; opacity: 0.5; }
        QScrollBar::handle:vertical:hover { background: #505050; opacity: 1.0; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { border: none; background: none; height: 0px; }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        QScrollBar:horizontal { border: none; background: transparent; height: 6px; margin: 0px; }
        QScrollBar::handle:horizontal { background: #383838; min-width: 25px; border-radius: 3px; border: none; opacity: 0.5; }
        QScrollBar::handle:horizontal:hover { background: #505050; opacity: 1.0; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { border: none; background: none; width: 0px; }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }

        /* --- 特定控件微调 (优雅黑) --- */
        #update_news_button { /* 突出更新按钮 */
             background-color: #353535; color: #f5f5f5; font-weight: bold; border: 1px solid #505050; /* 更突出 */
        }
        #update_news_button:hover { background-color: #404040; border-color: #606060; }
        /* 确保 Tab 样式 */
        QTabBar::tab { background-color: #181818; border: 1px solid #252525; border-bottom: none; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px; color: #909090; }
        QTabBar::tab:selected { background-color: #1e1e1e; border-bottom: 1px solid #1e1e1e; color: #f0f0f0; } /* 提高选中Tab文字亮度 */
        QTabBar::tab:hover:!selected { background-color: #222222; color: #b0b0b0; }
        QTabWidget::pane { border: 1px solid #252525; border-top: none; border-radius: 0 0 6px 6px; background-color: #1a1a1a; }
        QSplitter::handle { background-color: #252525; width: 1px; margin: 0 8px; } /* 分割线稍亮 */
        QStatusBar { background-color: #181818; border-top: 1px solid #252525; color: #808080; } /* 状态栏文字稍亮 */

    """

    def __init__(self, app_service: AppService): # 添加类型提示
        super().__init__()
        # 移除旧的 refresh_queue 和 refresh_timer
        # self.refresh_queue = queue.Queue()
        # self.refresh_timer = QTimer(self)
        # self.refresh_timer.setInterval(100)
        # self.refresh_timer.timeout.connect(self._check_refresh_queue)

        self.logger = logging.getLogger('news_analyzer.ui.main_window')
        self.app_service = app_service # 保存 AppService 实例

        # 设置窗口属性
        self.setWindowTitle("讯析 v1.0.0") # 修改窗口标题并加入版本号
        self.setMinimumSize(1200, 800)

        # --- 直接在 MainWindow 创建和管理 LLMClient ---
        self.llm_client = LLMClient()
        self.logger.info("在 MainWindow 中创建了 LLMClient 实例")
        # --- 创建结束 ---

        # 用于存储已读新闻的ID (使用link作为ID) - 注意：这个状态最终应该移至 AppService
        self.read_news_ids = set() # 暂时保留，用于UI状态
        # TODO: 从 AppService 加载已读状态
        # self.read_news_ids = self.app_service.load_read_ids()

        # 初始化UI组件
        self._init_ui()

        # --- 设置默认全局字体大小 ---
        default_font = QFont()
        default_font.setPointSize(11) # 设置默认大小为 11pt
        QApplication.instance().setFont(default_font)
        self.logger.info("设置默认全局字体大小为 11pt")


        # 加载用户设置 (主要是窗口几何信息)
        self._load_settings()

        # 更新状态栏显示模型状态 (需要确保 llm_client 已正确初始化)
        self._update_status_message()

        # --- 连接 AppService 信号 ---
        self.app_service.sources_updated.connect(self._on_sources_updated) # 更新侧边栏分类和新闻源管理面板
        self.app_service.refresh_started.connect(self._on_refresh_started) # 连接刷新开始信号
        # refresh_complete 和 refresh_cancelled 已经连接到 _hide_refresh_progress_bar，我们可以在那里恢复按钮状态
        # 或者创建一个单独的 _on_refresh_finished 槽函数连接这两个信号
        self.app_service.refresh_complete.connect(self._on_refresh_finished) # 连接刷新完成信号
        self.app_service.refresh_cancelled.connect(self._on_refresh_finished) # 连接刷新取消信号
        self.app_service.news_refreshed.connect(self._on_news_refreshed) # 更新新闻列表
        self.app_service.status_message_updated.connect(self._update_status_bar) # 更新状态栏文本

        # --- 连接刷新信号到状态栏进度条处理函数 ---
        self.app_service.refresh_progress.connect(self._update_refresh_progress_bar)
        self.app_service.refresh_complete.connect(self._hide_refresh_progress_bar)
        self.app_service.refresh_cancelled.connect(self._hide_refresh_progress_bar) # 取消也隐藏进度条

        self.logger.info("主窗口已初始化")


        # --- 初始加载完成后，默认显示'所有'分类 ---
        self.filter_by_category("所有")

    # --- 以下方法不再需要，由 AppService 处理或通过信号触发 ---
    # def _load_and_display_initial_news(self): ...
    # def _load_llm_settings(self): ...
    # def _sync_categories(self): ...

    def _update_status_message(self):
        """更新状态栏显示模型信息"""
        if hasattr(self, 'llm_client') and self.llm_client and self.llm_client.api_key:
            self.status_label.setText(f"语言模型已就绪: {self.llm_client.model}")
        else:
            self.status_label.setText("语言模型未配置或未就绪")

    def _init_ui(self):
        """初始化UI组件"""
        # 创建中央窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- 尝试创建 HistoryPanel 实例 (移到 _create_actions 之前) ---
        self.history_panel = None # 初始化为 None
        try:
            from news_analyzer.ui.history_panel import HistoryPanel
            # TODO: 调整 HistoryPanel 的初始化以适应 AppService
            self.history_panel = HistoryPanel(self.app_service.storage) # 假设它需要 storage
            self.history_panel.set_read_ids(self.read_news_ids)
            # self.history_panel.history_loaded.connect(self.load_history_news) # REMOVED - No longer needed as it's a dialog
            self.logger.info(f"HistoryPanel instance created successfully: {self.history_panel}")
        except ImportError as imp_err:
            self.logger.error(f"导入 HistoryPanel 失败: {imp_err}", exc_info=True)
            self.history_panel = None # 确保导入失败时实例为 None
        except AttributeError as attr_err:
             # 捕获可能由于 app_service.storage 或 storage.data_dir 不存在导致的错误
             self.logger.error(f"创建 HistoryPanel 时缺少属性: {attr_err}", exc_info=True)
             # 添加更详细的日志
             if not hasattr(self, 'app_service'):
                 self.logger.error("AttributeError 时 app_service 不存在")
             elif not hasattr(self.app_service, 'storage'):
                 self.logger.error(f"AttributeError 时 app_service ({self.app_service}) 缺少 storage 属性")
             elif not hasattr(self.app_service.storage, 'data_dir'):
                  self.logger.error(f"AttributeError 时 storage ({self.app_service.storage}) 缺少 data_dir 属性")
             self.history_panel = None # 确保属性错误时实例为 None
        except Exception as e:
             self.logger.error(f"创建 HistoryPanel 实例时发生未知错误: {type(e).__name__} - {e}", exc_info=True)
             self.history_panel = None # 确保其他错误时实例为 None
        # --- HistoryPanel 创建结束 ---


        # 先创建菜单、工具栏和状态栏
        self._create_actions()
        self._create_menus()
        # self._create_toolbars() # Removed toolbar creation
        self._create_statusbar()

        # 创建搜索面板 (恢复直接添加到主布局)
        self.search_panel = SearchPanel()
        main_layout.addWidget(self.search_panel)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        # --- 创建左侧面板容器 (包含按钮和侧边栏) ---
        # 先创建侧边栏
        self.sidebar = CategorySidebar()

        # 再创建容器和布局
        self.left_panel_container = QWidget() # 存储为成员变量，方便切换可见性
        left_layout = QVBoxLayout(self.left_panel_container)
        left_layout.setContentsMargins(0, 5, 5, 0) # 调整边距
        left_layout.setSpacing(5) # 调整间距

        # 创建并添加更新新闻按钮
        self.update_news_button = QPushButton("更新新闻")
        self.update_news_button.setToolTip("获取最新新闻 (F5)")
        self.update_news_button.setObjectName("update_news_button")
        self.update_news_button.clicked.connect(self.app_service.refresh_all_sources)
        left_layout.addWidget(self.update_news_button)

        # 添加已创建的侧边栏
        left_layout.addWidget(self.sidebar, 1) # 让侧边栏占据剩余空间

        # 将左侧容器添加到分割器
        self.left_panel_container.setMinimumWidth(180) # 设置左侧面板最小宽度
        splitter.addWidget(self.left_panel_container)
        # --- 左侧面板容器结束 ---

        # 创建中间新闻列表面板
        self.news_list = NewsListPanel()
        splitter.addWidget(self.news_list)
        self.news_list.setMinimumWidth(300) # 设置中间面板最小宽度

        # 右侧标签页面板
        self.right_panel = QTabWidget()
        self.right_panel.setTabPosition(QTabWidget.North)
        # 移除内联样式，由全局主题控制
        # self.right_panel.setStyleSheet("""...""")

        # 创建聊天面板，并传入共享的 llm_client
        self.chat_panel = ChatPanel(llm_client=self.llm_client)
        # self.chat_panel.llm_client = self.llm_client # 不再需要单独设置

        # 创建LLM分析面板，并传入共享的 llm_client
        self.llm_panel = LLMPanel(llm_client=self.llm_client)
        # self.llm_panel.llm_client = self.llm_client # 不再需要单独设置

        # 添加核心标签页
        self.right_panel.addTab(self.chat_panel, "聊天")
        self.right_panel.addTab(self.llm_panel, "分析")

        # 创建 HistoryPanel 的代码块已移动到 _create_actions 调用之前

        # 不再将 SourceManagementPanel 添加为标签页

        # 添加右侧面板到分割器
        splitter.addWidget(self.right_panel)
        self.right_panel.setMinimumWidth(350) # 设置右侧面板最小宽度

        # 调整分割器比例：减小中间面板，增大右侧面板
        splitter.setSizes([200, 450, 550]) # 示例调整，可根据需要微调

        # 连接信号和槽
        self.search_panel.search_requested.connect(self.search_news)
        self.sidebar.category_selected.connect(self.filter_by_category)
        self.sidebar.category_selected.connect(self.chat_panel.set_current_category)
        self.news_list.item_selected.connect(self._on_news_selected)
        self.news_list.news_updated.connect(self._update_chat_panel_news)


    def _update_chat_panel_news(self, news_items):
        """更新聊天面板中的可用新闻标题"""
        if hasattr(self, 'chat_panel') and hasattr(self.chat_panel, 'set_available_news_titles'):
            all_cached_news = self.app_service.get_all_cached_news()
            self.chat_panel.set_available_news_titles(all_cached_news)
            self.logger.debug(f"更新聊天面板可用新闻标题，共 {len(all_cached_news)} 条")

    # def load_history_news(self, news_items_dicts: list): # REMOVED - No longer needed
    #     """处理历史新闻加载 (由 HistoryPanel 发出信号触发)""" # REMOVED
    #     self.logger.info(f"从历史记录加载 {len(news_items_dicts)} 条新闻字典") # REMOVED
    #
    #     # --- 将字典列表转换为 NewsArticle 对象列表 --- # REMOVED
    #     news_articles = [] # REMOVED
    #     if hasattr(self, 'app_service') and hasattr(self.app_service, '_convert_dict_to_article'): # REMOVED
    #         for item_dict in news_items_dicts: # REMOVED
    #             article = self.app_service._convert_dict_to_article(item_dict) # REMOVED
    #             if article: # REMOVED
    #                 news_articles.append(article) # REMOVED
    #         self.logger.info(f"成功将 {len(news_articles)} 条历史记录转换为 NewsArticle 对象") # REMOVED
    #     else: # REMOVED
    #         self.logger.error("无法访问 AppService 或其转换方法，无法转换历史记录") # REMOVED
    #         news_articles = [] # 避免后续出错 # REMOVED
    #     # --- 转换结束 --- # REMOVED
    #
    #     self.news_list.set_read_ids(self.read_news_ids) # REMOVED
    #     self.news_list.update_news(news_articles) # 传递转换后的对象列表 # REMOVED
    #     self.status_label.setText(f"已加载 {len(news_articles)} 条历史新闻") # REMOVED
    #     self._update_chat_panel_news(news_articles) # 传递转换后的对象列表 # REMOVED

    # --- UI 创建方法 ---
    def _create_actions(self):
        """创建菜单和工具栏动作"""
        # --- 文件菜单动作 ---
        self.exit_action = QAction("退出", self)
        self.exit_action.setStatusTip("退出应用程序")
        self.exit_action.setShortcut("Ctrl+Q") # 添加快捷键
        self.exit_action.triggered.connect(self.close)

        # --- 视图菜单动作 ---
        self.refresh_action = QAction("更新新闻", self) # 重命名为 "更新新闻"
        self.refresh_action.setStatusTip("获取最新新闻")
        self.refresh_action.setShortcut("F5") # 添加快捷键
        self.refresh_action.triggered.connect(self.app_service.refresh_all_sources)

        self.toggle_sidebar_action = QAction("切换侧边栏", self, checkable=True) # 可勾选
        self.toggle_sidebar_action.setStatusTip("显示或隐藏新闻分类侧边栏")
        self.toggle_sidebar_action.setChecked(True) # 默认显示
        self.toggle_sidebar_action.triggered.connect(self._toggle_sidebar)

        self.toggle_statusbar_action = QAction("切换状态栏", self, checkable=True) # 可勾选
        self.toggle_statusbar_action.setStatusTip("显示或隐藏状态栏")
        self.toggle_statusbar_action.setChecked(True) # 默认显示
        self.toggle_statusbar_action.triggered.connect(self._toggle_statusbar)

        self.toggle_theme_action = QAction("夜间模式", self, checkable=True) # NEW Theme Toggle
        self.toggle_theme_action.setStatusTip("切换日间/夜间模式")
        self.toggle_theme_action.setChecked(False) # 默认日间模式
        self.toggle_theme_action.triggered.connect(self._toggle_theme) # Connect to new slot

        # --- 字体大小控制动作 ---
        self.increase_font_action = QAction("增大字体", self)
        self.increase_font_action.setStatusTip("增大应用程序字体")
        self.increase_font_action.setShortcut("Ctrl++")
        self.increase_font_action.triggered.connect(self._increase_app_font)

        self.decrease_font_action = QAction("减小字体", self)
        self.decrease_font_action.setStatusTip("减小应用程序字体")
        self.decrease_font_action.setShortcut("Ctrl+-")
        self.decrease_font_action.triggered.connect(self._decrease_app_font)


        # --- 数据菜单动作 ---
        self.manage_sources_action = QAction("管理新闻源", self)
        self.manage_sources_action.setStatusTip("添加、编辑或删除新闻源")
        self.manage_sources_action.triggered.connect(self._show_source_management_dialog)

        # self.manage_json_action = QAction("管理新闻 JSON", self) # REMOVED Placeholder
        # self.manage_json_action.setStatusTip("管理已保存的新闻 JSON 文件") # REMOVED
        # self.manage_json_action.triggered.connect(self._manage_news_json) # REMOVED

        self.view_browse_history_action = QAction("查看浏览历史", self) # NEW
        self.view_browse_history_action.setStatusTip("打开历史记录管理窗口") # Update tooltip
        # Connect to the new dialog showing method
        self.view_browse_history_action.triggered.connect(self._show_history_dialog)
        # Disable if history_panel failed to load (keep this check)
        if not self.history_panel:
            self.view_browse_history_action.setEnabled(False)

        # self.clear_browse_history_action = QAction("清除浏览记录", self) # REMOVED Action Definition
        # ... (removed lines)

        # self.import_batch_action = QAction("导入新闻批次", self) # REMOVED
        # self.import_batch_action.setStatusTip("从 JSON 文件导入新闻批次") # REMOVED
        # if self.history_panel: # REMOVED
        #     self.import_batch_action.triggered.connect(self.history_panel._import_news_file) # REMOVED
        # else: # REMOVED
        #     self.import_batch_action.setEnabled(False) # REMOVED
        #
        # self.export_batch_action = QAction("导出新闻批次", self) # REMOVED
        # self.export_batch_action.setStatusTip("将历史新闻批次导出为 JSON 文件") # REMOVED
        # if self.history_panel: # REMOVED
        #     self.export_batch_action.triggered.connect(self.history_panel._export_selected_file) # REMOVED
        # else: # REMOVED
        #     self.export_batch_action.setEnabled(False) # REMOVED

        self.import_export_action = QAction("导入/导出批次", self) # NEW Merged Action
        self.import_export_action.setStatusTip("打开导入/导出新闻批次对话框") # NEW
        self.import_export_action.triggered.connect(self._show_import_export_dialog) # NEW Connect to new slot

        self.manage_chat_history_action = QAction("管理对话历史", self) # 保留
        self.manage_chat_history_action.setStatusTip("管理 LLM 对话历史记录") # 保留
        self.manage_chat_history_action.triggered.connect(self._manage_chat_history) # 保留

        # self.import_export_history_action = QAction("导入/导出历史", self) # REMOVED Placeholder
        # self.import_export_history_action.setStatusTip("导入或导出浏览/分析历史") # REMOVED
        # self.import_export_history_action.triggered.connect(self._import_export_history) # REMOVED

        # --- 设置菜单动作 ---
        self.llm_settings_action = QAction("语言模型设置", self)
        self.llm_settings_action.setStatusTip("配置语言模型API密钥和模型")
        self.llm_settings_action.triggered.connect(self._show_llm_settings)

        # --- 帮助菜单动作 ---
        self.view_logs_action = QAction("查看日志", self)
        self.view_logs_action.setStatusTip("打开应用程序日志文件")
        self.view_logs_action.triggered.connect(self._show_logs) # 连接到新槽

        self.about_action = QAction("关于", self)
        self.about_action.setStatusTip("显示关于应用程序的信息")
        self.about_action.triggered.connect(self.show_about)


    def _toggle_theme(self):
        """切换日间/夜间模式"""
        app = QApplication.instance()
        if self.toggle_theme_action.isChecked():
            # 切换到夜间模式
            app.setStyleSheet(self.DARK_THEME)
            self.current_theme = 'dark'
            self.toggle_theme_action.setText("日间模式") # 更新菜单文本
            self.logger.info("切换到夜间模式")
        else:
            # 切换到日间模式
            app.setStyleSheet(self.LIGHT_THEME)
            self.current_theme = 'light'
            self.toggle_theme_action.setText("夜间模式") # 更新菜单文本
            self.logger.info("切换到日间模式")
        # TODO: 保存当前主题设置
        self._save_theme_setting() # 调用保存设置



    def _toggle_theme(self):
        """切换日间/夜间模式"""
        app = QApplication.instance()
        if self.toggle_theme_action.isChecked():
            # 切换到夜间模式
            app.setStyleSheet(self.DARK_THEME)
            self.current_theme = 'dark'
            self.toggle_theme_action.setText("日间模式") # 更新菜单文本
            self.logger.info("切换到夜间模式")
        else:
            # 切换到日间模式
            app.setStyleSheet(self.LIGHT_THEME)
            self.current_theme = 'light'
            self.toggle_theme_action.setText("夜间模式") # 更新菜单文本
            self.logger.info("切换到日间模式")
        # TODO: 保存当前主题设置
        self._save_theme_setting() # 调用保存设置



    # 移除 _go_to_source_management 方法
    # def _go_to_source_management(self): ...

    def _create_menus(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")
        file_menu.addAction(self.exit_action) # 只保留退出

        # 视图菜单
        view_menu = menubar.addMenu("视图")
        # view_menu.addAction(self.refresh_action) # REMOVED from menu
        # view_menu.addSeparator() # 移除分隔符
        view_menu.addAction(self.toggle_sidebar_action) # 恢复切换侧边栏选项
        # view_menu.addAction(self.toggle_statusbar_action) # 保持移除切换状态栏选项
        view_menu.addSeparator() # 在侧边栏和主题之间添加分隔符
        view_menu.addAction(self.toggle_theme_action) # 切换主题选项
        view_menu.addSeparator() # 添加分隔符
        view_menu.addAction(self.increase_font_action) # 添加增大字体选项
        view_menu.addAction(self.decrease_font_action) # 添加减小字体选项

        # 数据菜单 (整合历史功能)
        data_menu = menubar.addMenu("数据")
        data_menu.addAction(self.manage_sources_action)
        data_menu.addSeparator()
        data_menu.addAction(self.view_browse_history_action) # NEW
        # data_menu.addAction(self.clear_browse_history_action) # REMOVED - Moved to dialog
        data_menu.addSeparator()
        data_menu.addAction(self.import_export_action) # NEW Merged Action
        # data_menu.addAction(self.export_batch_action) # REMOVED
        data_menu.addSeparator()
        data_menu.addAction(self.manage_chat_history_action) # 保留

        # 设置菜单
        settings_menu = menubar.addMenu("设置")
        settings_menu.addAction(self.llm_settings_action) # 只保留 LLM 设置

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        help_menu.addAction(self.view_logs_action)
        help_menu.addSeparator()
        help_menu.addAction(self.about_action)
# Removed _create_toolbars method as it's no longer needed
# def _create_toolbars(self): ...
    # def _create_toolbars(self): ...

    def _create_statusbar(self):
        """创建状态栏"""
        self.status_label = QLabel("就绪")
        self.statusBar().addWidget(self.status_label, 1) # 让标签占据主要空间

        # 添加进度条，初始隐藏
        self.refresh_progress_bar = QProgressBar()
        self.refresh_progress_bar.setMaximumSize(200, 15) # 设置一个合适的大小
        self.refresh_progress_bar.setVisible(False) # 初始隐藏
        self.statusBar().addPermanentWidget(self.refresh_progress_bar)

    def _load_settings(self):
        """加载应用程序设置 (UI相关)"""
        settings = QSettings("NewsAnalyzer", "NewsAggregator")

        # 加载窗口几何信息
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
            self.logger.info("加载窗口几何设置")
        else:
            self.logger.info("未找到窗口几何设置")

        # 加载主题设置
        self.current_theme = settings.value("theme", "light") # 默认为 light
        self.logger.info(f"加载主题设置: {self.current_theme}")
        app = QApplication.instance()
        if self.current_theme == 'dark':
            app.setStyleSheet(self.DARK_THEME)
            self.toggle_theme_action.setChecked(True)
            self.toggle_theme_action.setText("日间模式")
        else:
            # 默认应用浅色主题 (或者不设置，依赖默认样式)
            app.setStyleSheet(self.LIGHT_THEME)
            self.toggle_theme_action.setChecked(False)
            self.toggle_theme_action.setText("夜间模式")

        # TODO: 从 AppService 加载已读 ID

    def _save_settings(self):
        """保存应用程序设置 (仅UI相关)"""
        settings = QSettings("NewsAnalyzer", "NewsAggregator")
        # 保存窗口几何信息
        settings.setValue("geometry", self.saveGeometry())
        self.logger.info("保存窗口几何设置")
        # 保存主题设置
        if hasattr(self, 'current_theme'):
             settings.setValue("theme", self.current_theme)
             self.logger.info(f"保存主题设置: {self.current_theme}")
        else:
             # 如果 current_theme 属性不存在，则保存默认值或记录警告
             settings.setValue("theme", "light") # 保存默认值

    def _save_theme_setting(self):
        """保存当前主题设置"""
        settings = QSettings("NewsAnalyzer", "NewsAggregator")
        if hasattr(self, 'current_theme'):
            settings.setValue("theme", self.current_theme)
            self.logger.debug(f"实时保存主题设置: {self.current_theme}")
        else:
            settings.setValue("theme", "light") # 保存默认值
            self.logger.warning("尝试实时保存主题但未找到 current_theme 属性，保存默认 'light'")

        # REMOVED duplicate and incorrectly indented line 675

        # TODO: 通知 AppService 保存已读 ID

    @pyqtSlot(object) # 明确槽接收 object 类型
    def _on_news_selected(self, news_article: NewsArticle): # 参数改为 news_article
        """处理新闻选择事件 - 弹出详情对话框"""
        if not news_article or not isinstance(news_article, NewsArticle):
            self.logger.warning("_on_news_selected 接收到的不是有效的 NewsArticle 对象")
            return

        # --- 准备新闻详情 HTML ---
        title = news_article.title or '无标题'
        source = news_article.source_name or '未知来源'
        date = news_article.publish_time.strftime('%Y-%m-%d %H:%M:%S') if news_article.publish_time else "未知日期"
        content_display = news_article.content
        summary_display = news_article.summary
        if not content_display and summary_display:
             description = f"<p><i>(仅摘要)</i></p>{summary_display}"
        elif content_display:
             description = content_display
        else:
             description = '无内容'
        link = news_article.link or ''
        detail_html = f"""
            <h2>{title}</h2>
            <p><strong>来源:</strong> {source} | <strong>日期:</strong> {date}</p>
            <hr>
            <p>{description}</p>
        """
        if link: detail_html += f'<p><a href="{link}" target="_blank">阅读原文</a></p>'

        # --- 获取当前主题样式 ---
        current_style = ""
        if hasattr(self, 'current_theme'):
            current_style = self.DARK_THEME if self.current_theme == 'dark' else self.LIGHT_THEME

        # --- 创建并显示对话框 ---
        dialog = NewsDetailDialog(detail_html, current_style, self)
        dialog.exec_() # 以模态方式显示

        # --- 原有的 LLM 和聊天面板更新逻辑可以保留 ---
        self.llm_panel.analyze_news(news_article)
        self.chat_panel.set_current_news(news_article)
        if hasattr(self, 'chat_panel') and hasattr(self.chat_panel, 'context_checkbox'):
            self.chat_panel.context_checkbox.setChecked(True)

        # --- 标记新闻为已读 (逻辑不变) ---
        # TODO: 将已读状态的管理移至 AppService
        news_link = news_article.link
        if news_link and news_link not in self.read_news_ids:
            self.read_news_ids.add(news_link)
            self.logger.debug(f"新闻标记为已读: {news_link}")
            # self.app_service.mark_as_read(news_link)
            self.news_list.set_read_ids(self.read_news_ids)
            # 检查 history_panel 是否存在再调用其方法
            if self.history_panel:
                self.history_panel.set_read_ids(self.read_news_ids)
            # self.news_list.update_item_read_status(news_link)

    # add_news_source 方法不再需要，由 SourceManagementPanel 处理
    # def add_news_source(self): ...

    # --- 移除旧的刷新相关方法 ---
    # def refresh_news(self): ...
    # def _fetch_news_worker(self): ...
    # def _check_refresh_queue(self): ...
    # def _on_refresh_complete(self, success, message, news_to_display): ...

    def search_news(self, search_params):
        """处理搜索请求"""
        query = search_params.get("query", "")
        field = search_params.get("field", "标题和内容")

        is_filtering = bool(query)
        if not is_filtering:
            current_category = self.sidebar.get_current_category()
            self.logger.info(f"搜索条件为空，恢复显示分类: '{current_category}'")
            self.filter_by_category(current_category)
            self.status_label.setText("搜索条件已清除")
            return

        self.status_label.setText("正在执行搜索...")
        QApplication.processEvents()
        try:
            if hasattr(self, 'app_service') and hasattr(self, 'news_list') and hasattr(self.news_list, 'date_slider'):
                # 从 news_list 获取当前时间范围
                current_days = self.news_list.date_slider.value()
                # 调用 app_service 的搜索方法，传递 query, field 和 days
                results = self.app_service.search_news(query=query, field=field, days=current_days)
                self.news_list.update_news(results) # update_news 内部会调用 _apply_date_filter，无需重复筛选
                self.news_list.set_read_ids(self.read_news_ids)
                self._update_chat_panel_news(results)
                count = len(results)
                search_desc = f"'{query}'" if query else "所有新闻"
                self.status_label.setText(f"搜索 {search_desc} 找到 {count} 条结果")
                self.logger.info(f"搜索参数: {search_params}, 找到 {count} 条结果")
            else:
                self.logger.error("AppService 未初始化，无法执行搜索")
                QMessageBox.critical(self, "错误", "应用程序服务未初始化")
                self.status_label.setText("服务未初始化")
        except Exception as e:
            self.logger.error(f"搜索新闻时出错: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "搜索错误", f"搜索新闻时发生错误: {str(e)}")
            self.status_label.setText("搜索失败")

    def filter_by_category(self, category):
        """按分类筛选新闻 (通过 AppService 获取数据)"""
        self.logger.info(f"筛选显示分类: '{category}'")
        self.logger.info(f"filter_by_category: 接收到分类 '{category}'")
        news_to_display = []
        status_msg = ""
        try:
            if hasattr(self, 'app_service'):
                news_articles = self.app_service.get_news_by_category(category)
                news_to_display = news_articles
                self.logger.info(f"filter_by_category: AppService 返回 {len(news_articles)} 条 '{category}' 类新闻")
                status_msg = f"显示分类 '{category}' 的 {len(news_to_display)} 条新闻"
                if category == "所有":
                     status_msg = f"显示所有 {len(news_to_display)} 条新闻"

                self.news_list.update_news(news_to_display)
                self.news_list.set_read_ids(self.read_news_ids)
                all_news = self.app_service.get_all_cached_news()
                self._update_chat_panel_news(all_news)

                self.status_label.setText(status_msg)
                self.logger.info(status_msg)
            else:
                 self.logger.error("AppService 未初始化，无法按分类筛选")
                 QMessageBox.critical(self, "错误", "应用程序服务未初始化")
                 self.status_label.setText("服务未初始化")
                 return
        except Exception as e:
            QMessageBox.warning(self, "筛选失败", f"筛选新闻失败: {str(e)}")
            self.status_label.setText("筛选失败")
            self.logger.error(f"筛选新闻失败: {str(e)}")
            return

    # --- 新增的槽函数 ---
    def _toggle_sidebar(self):
        """切换左侧面板容器 (包含按钮和侧边栏) 的可见性"""
        if hasattr(self, 'left_panel_container'): # 检查容器是否存在
            self.left_panel_container.setVisible(self.toggle_sidebar_action.isChecked()) # 切换容器可见性
            # 可能需要调整分割器的大小
            # self.splitter.setSizes(...) # 如果需要恢复比例
        else:
             QMessageBox.warning(self, "错误", "左侧面板容器未找到")

    def _toggle_statusbar(self):
        """切换状态栏的可见性"""
        self.statusBar().setVisible(self.toggle_statusbar_action.isChecked())

    def _show_logs(self):
        """打开日志文件（占位符）"""
        # TODO: 实现打开日志文件的逻辑
        # 例如，找到日志文件路径并使用 os.startfile (Windows) 或 QDesktopServices.openUrl (跨平台)
        log_file_path = os.path.join("logs", "news_analyzer.log") # 假设路径
        if os.path.exists(log_file_path):
             try:
                 # 尝试使用跨平台方式打开
                 from PyQt5.QtGui import QDesktopServices
                 from PyQt5.QtCore import QUrl
                 QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(log_file_path)))
                 self.logger.info(f"尝试打开日志文件: {log_file_path}")
             except Exception as e:
                 self.logger.error(f"无法使用 QDesktopServices 打开日志文件: {e}")
                 QMessageBox.warning(self, "打开日志失败", f"无法自动打开日志文件。\n请手动查看: {os.path.abspath(log_file_path)}")
        else:
             QMessageBox.warning(self, "日志文件未找到", f"日志文件不存在于预期路径: {log_file_path}")

    # --- 新增的占位符槽函数 (用于数据菜单) ---
    # def _view_browse_history(self): # REMOVED Placeholder
    #     """查看浏览历史 (占位符)""" # REMOVED
    #     # TODO: 实现打开或显示浏览历史的逻辑 # REMOVED
    #     QMessageBox.information(self, "功能开发中", "查看浏览历史的功能正在开发中...") # REMOVED
    #
    # def _clear_browse_history(self): # REMOVED Placeholder
    #     """清除浏览记录 (占位符)""" # REMOVED
    #     # TODO: 实现清除浏览历史的逻辑 (需要确认) # REMOVED
    #     reply = QMessageBox.question(self, '确认清除', # REMOVED
    #                                  "确定要清除所有浏览历史记录吗？此操作不可恢复。", # REMOVED
    #                                  QMessageBox.Yes | QMessageBox.No, QMessageBox.No) # REMOVED
    #     if reply == QMessageBox.Yes: # REMOVED
    #         # 在这里调用 AppService 或 Storage 的方法来清除历史 # REMOVED
    #         QMessageBox.information(self, "功能开发中", "清除浏览历史的功能正在开发中...") # REMOVED
    #         self.logger.info("用户请求清除浏览历史 (功能待实现)") # REMOVED
    #
    # def _import_batch(self): # REMOVED Placeholder
    #     """导入新闻批次 (占位符)""" # REMOVED
    #     # TODO: 实现调用文件对话框并处理导入逻辑 # REMOVED
    #     QMessageBox.information(self, "功能开发中", "从 JSON 文件导入新闻批次的功能正在开发中...") # REMOVED
    #
    # def _export_batch(self): # REMOVED Placeholder
    #     """导出新闻批次 (占位符)""" # REMOVED
    #     # TODO: 实现选择批次并导出为 JSON 的逻辑 # REMOVED
    #     QMessageBox.information(self, "功能开发中", "导出历史新闻批次为 JSON 文件的功能正在开发中...") # REMOVED

    def _manage_chat_history(self): # 保留的占位符
        """管理对话历史 (占位符)"""
        QMessageBox.information(self, "功能开发中", "管理 LLM 对话历史的功能正在开发中...")

    # --- 现有槽函数 ---
    def show_settings(self):
        """显示设置对话框 (占位符)"""
        QMessageBox.information(self, "应用程序设置", "应用程序设置功能开发中...") # 更新标题

    def _show_llm_settings(self):
        """显示语言模型设置对话框，并连接信号"""
        dialog = LLMSettingsDialog(self)
        # 连接信号到更新槽函数
        dialog.settings_changed.connect(self._update_llm_client)
        dialog.exec_() # 显示对话框
        # 对话框关闭后，如果设置有更改，信号会触发 _update_llm_client
        # 不再需要在 dialog.exec_() 之后手动更新

    def _update_llm_client(self):
        """重新创建 LLMClient 实例并更新子面板"""
        self.logger.info("检测到 LLM 设置更改，正在更新 LLMClient...")
        self.llm_client = LLMClient() # 重新创建实例以加载新配置
        if hasattr(self, 'llm_panel'):
            self.llm_panel.llm_client = self.llm_client
            self.logger.info("已更新 LLMPanel 的 LLMClient 实例")
        if hasattr(self, 'chat_panel'):
            self.chat_panel.llm_client = self.llm_client
            self.logger.info("已更新 ChatPanel 的 LLMClient 实例")
        self._update_status_message() # 更新状态栏显示

    # --- 修正 show_about 方法 ---
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于",
                          "新闻聚合与分析系统 v1.1 (Refactored)\n\n"
                          "一个集成了LLM功能的新闻聚合工具，\n"
                          "支持RSS和澎湃新闻源，提供搜索、分类、\n"
                          "智能分析和聊天交互功能。")

    # --- 新增方法：显示新闻源管理对话框 ---
    def _show_source_management_dialog(self):
        """显示新闻源管理对话框"""
        if not hasattr(self, 'app_service'):
            QMessageBox.critical(self, "错误", "应用程序服务未初始化")
            return

        # 注意：SourceManagementPanel 需要修改为 QDialog
        try:
            # 假设 SourceManagementPanel 已被正确导入
            dialog = SourceManagementPanel(self.app_service, self) # 传入 app_service 和 parent
            dialog.exec_() # 以模态方式显示对话框
            # 对话框关闭后，AppService 发出的 sources_updated 信号会自动更新侧边栏
        except Exception as e:
             self.logger.error(f"显示新闻源管理对话框时出错: {e}", exc_info=True)
             QMessageBox.critical(self, "错误", f"无法打开新闻源管理：{e}")

    def _show_history_dialog(self):
        """显示历史记录管理对话框"""
        if self.history_panel:
            # 如果 history_panel 实例存在，则显示它
            # 可以考虑每次都刷新列表内容
            if hasattr(self.history_panel, '_refresh_history_list'):
                 self.history_panel._refresh_history_list()
            if hasattr(self.history_panel, '_refresh_export_combo'):
                 self.history_panel._refresh_export_combo()
            self.history_panel.exec_() # 以模态方式显示
        else:
            # 如果 history_panel 未能创建，显示错误消息
            QMessageBox.warning(self, "错误", "无法加载历史记录管理功能。")
            self.logger.error("尝试显示历史记录对话框，但 history_panel 实例不存在")

    def _show_import_export_dialog(self):
        """显示导入/导出批次对话框"""
        try:
            # from .import_export_dialog import ImportExportDialog # 导入语句已移到文件顶部
            # 确保 app_service 和 storage 存在
            if hasattr(self, 'app_service') and hasattr(self.app_service, 'storage'):
                 dialog = ImportExportDialog(self.app_service.storage, self)
                 dialog.exec_()
            else:
                 QMessageBox.critical(self, "错误", "应用程序服务或存储未初始化，无法打开导入/导出功能。")
                 self.logger.error("无法打开导入/导出对话框：app_service 或 storage 不可用")
        except ImportError as e:
             QMessageBox.critical(self, "错误", f"无法加载导入/导出模块: {e}")
             self.logger.error(f"导入 ImportExportDialog 失败: {e}", exc_info=True)
        except Exception as e:
             QMessageBox.critical(self, "错误", f"打开导入/导出对话框时出错: {e}")
             self.logger.error(f"打开导入/导出对话框时出错: {e}", exc_info=True)

    # --- 移除旧的 _show_refresh_dialog 方法 ---
    # def _show_refresh_dialog(self): ...

    # --- Slots for AppService signals ---

    @pyqtSlot() # 明确槽接收无参数信号
    def _on_sources_updated(self): # Corrected indentation
        """处理新闻源更新信号"""
        self.logger.info("接收到新闻源更新信号")
        # 1. 更新侧边栏分类

    # --- 刷新状态处理槽函数 ---
    @pyqtSlot()
    def _on_refresh_started(self):
        """处理刷新开始事件"""
        if hasattr(self, 'update_news_button'):
            self.update_news_button.setEnabled(False)
            self.update_news_button.setText("正在更新...")
            # 添加视觉效果：改变背景色 (需要根据主题调整颜色)
            original_style = self.update_news_button.styleSheet() # 保存原始样式
            self.update_news_button.setProperty("original_style", original_style) # 存储原始样式
            # 根据当前主题选择不同的刷新中颜色
            refreshing_style = ""
            if hasattr(self, 'current_theme') and self.current_theme == 'dark':
                refreshing_style = "background-color: #555; color: #ccc; border: 1px solid #777;" # 深色模式下的刷新中样式
            else:
                refreshing_style = "background-color: #ffc107; color: #333; border: 1px solid #ffa000;" # 浅色模式下的刷新中样式 (黄色)
            self.update_news_button.setStyleSheet(original_style + refreshing_style) # 合并样式
            self.logger.info("刷新开始，更新按钮状态和样式")

    @pyqtSlot()
    def _on_refresh_finished(self):
        """处理刷新完成或取消事件"""
        if hasattr(self, 'update_news_button'):
            self.update_news_button.setEnabled(True)
            self.update_news_button.setText("更新新闻")
            # 恢复原始样式
            original_style = self.update_news_button.property("original_style")
            if original_style is not None:
                self.update_news_button.setStyleSheet(original_style)
            else:
                 self.update_news_button.setStyleSheet("") # 兜底恢复默认
            self.logger.info("刷新结束，恢复更新按钮状态和样式")
        # 注意：隐藏进度条的逻辑已在 _hide_refresh_progress_bar 中处理

        categories = set()
        sources = self.app_service.get_sources()
        for source in sources:
            categories.add(source.category)

        self.sidebar.category_list.clear()
        self.sidebar.categories.clear()
        self.sidebar.add_category("所有")
        for category in sorted(list(categories)):
            if category != "所有":
                self.sidebar.add_category(category)
        self.logger.info(f"侧边栏分类已更新，共 {len(categories)} 个分类")

        # 2. 更新新闻源管理面板 (它会自己获取数据)
        # 注意：如果对话框是模态的，它关闭后此信号才可能触发UI更新，
        # 如果希望对话框内部实时更新，需要在对话框内部连接此信号。
        # if hasattr(self, 'source_management_dialog_instance') and self.source_management_dialog_instance.isVisible():
        #     self.source_management_dialog_instance.update_sources()
        #     self.logger.info("已触发新闻源管理对话框更新")
        # 暂时只更新侧边栏

    @pyqtSlot(list) # 明确槽接收 list 参数
    def _on_news_refreshed(self, news_articles: list): # 参数应为 list[NewsArticle]
        """处理新闻刷新完成信号"""
        self.logger.info(f"接收到新闻刷新完成信号，共 {len(news_articles)} 条新闻")
        self.logger.info(f"_on_news_refreshed: 准备调用 news_list.update_news 更新 {len(news_articles)} 条新闻")
        self.news_list.update_news(news_articles) # 更新列表数据
        self.news_list.set_read_ids(self.read_news_ids)
        self._update_chat_panel_news(news_articles)

    @pyqtSlot(str) # 明确槽接收 str 参数
    def _update_status_bar(self, message: str):
        """更新状态栏文本"""
        if hasattr(self, 'status_label'):
            self.status_label.setText(message)
            self.logger.debug(f"状态栏更新: {message}")

    # --- 移除旧的刷新处理槽函数 ---

    # --- 字体大小控制槽函数 ---
    def _adjust_app_font_size(self, delta):
        """调整应用程序全局字体大小"""
        app = QApplication.instance()
        current_font = app.font()
        current_size = current_font.pointSize()
        new_size = current_size + delta

        # 设置字体大小限制 (例如 8pt 到 20pt)
        min_font_size = 8
        max_font_size = 20
        new_size = max(min_font_size, min(new_size, max_font_size))

        if new_size != current_size:
            new_font = QFont(current_font)
            new_font.setPointSize(new_size)
            app.setFont(new_font)
            self.logger.info(f"全局字体大小调整为: {new_size}pt")
            # 更新所有窗口和控件以应用新字体
            # 这可能需要更复杂的逻辑来强制刷新所有UI元素
            # 一个简单的方法是重新应用样式表，但这可能影响性能
            # app.setStyleSheet(app.styleSheet()) # 强制刷新样式
            # 或者，可以尝试更新主窗口字体，但这不一定能传递到所有子控件
            # self.setFont(new_font)
            # 更好的方法可能是遍历所有顶级窗口并更新它们的字体
            for widget in QApplication.topLevelWidgets():
                widget.setFont(new_font)
                # 可能还需要更新子控件
                for child_widget in widget.findChildren(QWidget):
                     try:
                         # 尝试更新字体，忽略不支持的控件
                         child_widget.setFont(new_font)
                     except AttributeError:
                         pass # 有些控件可能没有 setFont

    def _increase_app_font(self):
        """增大全局字体"""
        self._adjust_app_font_size(1)

    def _decrease_app_font(self):
        """减小全局字体"""
        self._adjust_app_font_size(-1)

    # def _update_refresh_progress(self, current, total): ...
    # def _on_refresh_complete(self, news_articles): ...
    # def _on_refresh_cancelled(self): ...

    @pyqtSlot(int, int)
    def _update_refresh_progress_bar(self, current, total):
        """更新状态栏进度条"""
        if total > 0:
            self.refresh_progress_bar.setMaximum(total)
            self.refresh_progress_bar.setValue(current)
            if not self.refresh_progress_bar.isVisible():
                self.refresh_progress_bar.setVisible(True)
                self.status_label.setText("正在刷新...") # 同时更新状态文本
        else:
            self._hide_refresh_progress_bar()

    @pyqtSlot()
    def _hide_refresh_progress_bar(self):
        """隐藏状态栏进度条并重置状态文本"""
        self.refresh_progress_bar.setVisible(False)
        # 可以在这里根据刷新结果更新状态文本，或者依赖 AppService 发送的 status_message_updated 信号
        # self.status_label.setText("刷新完成" or "刷新取消")

    # def _cancel_refresh(self): ...


    def closeEvent(self, event):
        """窗口关闭事件处理"""
        self._save_settings()
        # TODO: 通知 AppService 保存其状态
        # self.app_service.save_all_state()

        reply = QMessageBox.question(self, '确认退出',
                                     "确定要退出程序吗?",
                                     QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.logger.info("应用程序关闭")
            event.accept()
        else:
            event.ignore()

    # --- 可能不再需要的旧方法 ---
    # def _check_refresh_queue(self): ...
