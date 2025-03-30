# news_analyzer/ui/news_detail_dialog.py

import logging
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser,
                             QPushButton, QSizePolicy, QSpacerItem)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

class NewsDetailDialog(QDialog):
    """显示新闻详情的弹出对话框"""

    DEFAULT_FONT_SIZE = 12 # 默认字体大小
    MIN_FONT_SIZE = 8
    MAX_FONT_SIZE = 24

    def __init__(self, article_html, current_theme_style="", parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.news_detail_dialog')
        self.article_html = article_html
        self.current_font_size = self.DEFAULT_FONT_SIZE

        self._init_ui()
        self.content_browser.setHtml(self.article_html)
        self._update_font_size() # 应用初始字体大小

        # 应用主题样式
        if current_theme_style:
            self.setStyleSheet(current_theme_style)
            # 可能需要强制刷新样式
            self.style().unpolish(self)
            self.style().polish(self)

        self.setWindowTitle("新闻详情")
        # 移除问号按钮 (上下文帮助按钮)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumSize(600, 400) # 设置最小尺寸
        self.resize(800, 600) # 设置默认尺寸

    def _init_ui(self):
        """初始化UI组件"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # --- 字体控制按钮 ---
        font_control_layout = QHBoxLayout()
        font_control_layout.setSpacing(5)

        self.decrease_font_button = QPushButton("-")
        self.decrease_font_button.setToolTip("减小字体")
        self.decrease_font_button.setFixedSize(25, 25)
        self.decrease_font_button.clicked.connect(self._decrease_font)
        font_control_layout.addWidget(self.decrease_font_button)

        self.increase_font_button = QPushButton("+")
        self.increase_font_button.setToolTip("增大字体")
        self.increase_font_button.setFixedSize(25, 25)
        self.increase_font_button.clicked.connect(self._increase_font)
        font_control_layout.addWidget(self.increase_font_button)

        font_control_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)) # 推到左侧

        self.copy_button = QPushButton("复制")
        self.copy_button.setToolTip("复制新闻内容到剪贴板")
        self.copy_button.clicked.connect(self._copy_content)
        font_control_layout.addWidget(self.copy_button) # 添加到字体控制行

        main_layout.addLayout(font_control_layout)

        # --- 内容显示区域 ---
        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(True) # 允许打开外部链接
        # 移除焦点框
        self.content_browser.setStyleSheet("QTextBrowser { outline: none; border: 1px solid #cccccc; }") # 添加边框以便区分
        main_layout.addWidget(self.content_browser, 1) # 占据主要空间

        # --- 关闭按钮 ---
        button_layout = QHBoxLayout()
        button_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)) # 推到右侧
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        main_layout.addLayout(button_layout)


    def _update_font_size(self):
        """更新文本浏览器的字体大小"""
        font = self.content_browser.font()
        font.setPointSize(self.current_font_size)
        self.content_browser.setFont(font)
        # 可能需要重新设置 HTML 以确保字体生效
        # self.content_browser.setHtml(self.article_html) # 如果 setFont 不够，取消注释这行

        # 更新按钮状态
        self.decrease_font_button.setEnabled(self.current_font_size > self.MIN_FONT_SIZE)
        self.increase_font_button.setEnabled(self.current_font_size < self.MAX_FONT_SIZE)
        self.logger.debug(f"字体大小更新为: {self.current_font_size}pt")


    def _decrease_font(self):
        """减小字体大小"""
        if self.current_font_size > self.MIN_FONT_SIZE:
            self.current_font_size -= 1
            self._update_font_size()

    def _increase_font(self):
        """增大字体大小"""
        if self.current_font_size < self.MAX_FONT_SIZE:
            self.current_font_size += 1 # 修正缩进
            self._update_font_size() # 修正缩进

    def _copy_content(self):
        """复制内容到剪贴板"""
        # 需要导入 QApplication
        from PyQt5.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        plain_text = self.content_browser.toPlainText()
        clipboard.setText(plain_text)
        self.logger.info("新闻内容已复制到剪贴板")
        # 可以考虑添加一个短暂的状态提示
        # self.statusBar().showMessage("已复制!", 2000) # 如果有状态栏的话