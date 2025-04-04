# news_analyzer/ui/news_detail_dialog.py

import logging
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser,
                             QPushButton, QSizePolicy, QSpacerItem, QApplication) # Import QApplication here
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt # 移除 QTimer

from src.models import NewsArticle # 导入 NewsArticle

class NewsDetailDialog(QDialog):
    """显示新闻详情的弹出对话框"""

    DEFAULT_FONT_SIZE = 21 # 再次增大默认字体大小 (增加 5)
    MIN_FONT_SIZE = 8
    MAX_FONT_SIZE = 24

    def __init__(self, news_article: NewsArticle, parent=None): # 移除 current_theme_style 参数
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.news_detail_dialog')
        self.news_article = news_article # 保存 NewsArticle 对象
        self.logger.info(f"NewsDetailDialog received article with source_name: '{self.news_article.source_name}'") # 添加日志
        self.current_font_size = self.DEFAULT_FONT_SIZE

        # --- 从 NewsArticle 生成 HTML (使用正确的 HTML 标签) ---
        title = self.news_article.title or '无标题'
        source = self.news_article.source_name or '未知来源'
        date = self.news_article.publish_time.strftime('%Y-%m-%d %H:%M:%S') if self.news_article.publish_time else "未知日期"
        content_display = self.news_article.content
        summary_display = self.news_article.summary
        if not content_display and summary_display:
             # Use proper HTML tags
             description = f"<p><i>(仅摘要)</i></p>{summary_display}"
        elif content_display:
             description = content_display
        else:
             description = '无内容'
        link = self.news_article.link or ''
        self.logger.debug(f"Generating HTML with source: '{source}'") # 添加日志
        # Use proper HTML tags
        self.article_html = f"<h2>{title}</h2><p><strong>来源:</strong> {source} | <strong>日期:</strong> {date}</p><hr>{description}" # 直接嵌入 description HTML
        if link: self.article_html += f'<p><a href="{link}" target="_blank">阅读原文</a></p>'
        # --- HTML 生成结束 ---

        self._init_ui()
        self.logger.debug(f"Setting HTML content (length: {len(self.article_html)}):\n{self.article_html[:500]}...") # 记录前500字符

        self.content_browser.setHtml(self.article_html) # 现在 article_html 是正确的 HTML 字符串
        self._update_font_size() # 应用初始字体大小
        # 移除 QTimer 调用

        # 移除应用主题样式的代码，对话框应继承父窗口样式

        self.setWindowTitle("新闻详情")
        # 移除问号按钮，允许最大化
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint | Qt.WindowMaximizeButtonHint)
        self.setMinimumSize(700, 500) # 增大最小尺寸
        self.resize(1000, 750) # 再次增大默认尺寸

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
        self.decrease_font_button.setFixedSize(30, 30) # 增大按钮尺寸
        self.decrease_font_button.setObjectName("decreaseFontButton") # 添加 objectName
        self.decrease_font_button.setText("A-") # 在 addWidget 之前设置文本
        self.decrease_font_button.clicked.connect(self._decrease_font)
        font_control_layout.addWidget(self.decrease_font_button)
        self.logger.info(f"Decrease button text set to: {self.decrease_font_button.text()}") # 保留日志

        self.increase_font_button = QPushButton("+")
        self.increase_font_button.setToolTip("增大字体")
        self.increase_font_button.setFixedSize(30, 30) # 增大按钮尺寸
        self.increase_font_button.setObjectName("increaseFontButton") # 添加 objectName
        self.increase_font_button.setText("A+") # 在 addWidget 之前设置文本
        self.increase_font_button.clicked.connect(self._increase_font)
        font_control_layout.addWidget(self.increase_font_button)
        self.logger.info(f"Increase button text set to: {self.increase_font_button.text()}") # 保留日志

        font_control_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)) # 推到左侧

        self.copy_button = QPushButton("复制")
        self.copy_button.setToolTip("复制新闻内容到剪贴板")
        self.copy_button.clicked.connect(self._copy_content)
        font_control_layout.addWidget(self.copy_button) # 添加到字体控制行

        main_layout.addLayout(font_control_layout)

        # --- 内容显示区域 ---
        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(True) # 允许打开外部链接
        self.content_browser.setObjectName("NewsDetailContentBrowser") # 添加 objectName
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
        self.content_browser.setFont(font) # Keep setFont as a base
        # Also set stylesheet to increase specificity against global QSS
        # 设置基础样式和字体大小
        base_style = """
            p { margin-bottom: 1em; line-height: 1.6; }
            img { max-width: 100%; height: auto; display: block; margin-top: 0.5em; margin-bottom: 0.5em; border: 1px solid #ddd; }
            h2 { margin-bottom: 0.5em; }
            strong { font-weight: bold; }
            em, i { font-style: italic; }
            a { color: #007bff; text-decoration: none; }
            a:hover { text-decoration: underline; }
            hr { border: none; border-top: 1px solid #ccc; margin: 1em 0; }
        """
        self.content_browser.setStyleSheet(f"""
            QTextBrowser#NewsDetailContentBrowser {{
                font-size: {self.current_font_size}pt;
                outline: none;
                border: 1px solid #cccccc; /* Keep existing border style */
            }}
            {base_style}
        """)
        # 可能需要重新设置 HTML 以确保字体生效 (保留注释)
        # self.content_browser.setHtml(self.article_html) # 如果 setFont/setStyleSheet 不够，取消注释这行

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
            self.current_font_size += 1
            self._update_font_size()

    def _copy_content(self):
        """复制内容到剪贴板"""
        # QApplication 已在顶部导入
        clipboard = QApplication.clipboard()
        plain_text = self.content_browser.toPlainText()
        clipboard.setText(plain_text)
        self.logger.info("新闻内容已复制到剪贴板")
        # 可以考虑添加一个短暂的状态提示
        # self.statusBar().showMessage("已复制!", 2000) # 如果有状态栏的话

# 移除 _update_button_texts_and_repaint 方法