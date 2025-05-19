# news_analyzer/ui/news_detail_dialog.py

import logging
from datetime import datetime  # 添加datetime导入
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser,
                             QPushButton, QSizePolicy, QSpacerItem, QApplication,
                             QToolButton, QStyle, QLabel, QTextEdit, 
                             QCheckBox, QScrollArea, QWidget, QDialogButtonBox)
from PySide6.QtGui import QFont, QDesktopServices # Use PySide6
from PySide6.QtCore import Qt, Signal as pyqtSignal # Use PySide6
import os

from src.models import NewsArticle # 导入 NewsArticle
# from .news_detail_viewmodel import NewsDetailViewModel # Old incorrect path
from .viewmodels.news_detail_viewmodel import NewsDetailViewModel # Corrected relative import path

class NewsDetailDialog(QDialog):
    """显示新闻详情的弹出对话框"""

    DEFAULT_FONT_SIZE = 18 # Increase default size slightly
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
        # 处理publish_time可能是各种类型的情况
        if isinstance(self.news_article.publish_time, datetime):
            date = self.news_article.publish_time.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(self.news_article.publish_time, str):
            # 尝试将字符串转换为datetime对象以统一格式
            try:
                date_obj = datetime.fromisoformat(self.news_article.publish_time.replace('Z', '+00:00'))
                date = date_obj.strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                # 如果无法解析，直接使用原始字符串
                date = self.news_article.publish_time
        elif self.news_article.publish_time is None:
            date = "未知日期"
        else:
            # 处理其他类型，尝试转换为字符串
            try:
                date = str(self.news_article.publish_time)
            except:
                date = "未知日期"
        content_display = self.news_article.content
        summary_display = self.news_article.summary
        if summary_display: # New logic: Prioritize summary
            description = summary_display
        elif content_display: # If no summary, but content exists
            description = content_display
        else: # If neither summary nor content exists
            description = '无内容'
        link = self.news_article.link or ''
        self.logger.debug(f"Generating HTML with source: '{source}'") # 添加日志

        # Construct content first with CSS resets
        inner_html = f'''
        <h2 style="margin:0; padding:0;">{title}</h2>
        <p style="margin:0; padding:0;"><strong>来源:</strong> {source} | <strong>日期:</strong> {date}</p>
        <hr style="margin-top: 5px; margin-bottom: 5px;">
        <div style="margin:0; padding:0;">{description}</div>
        '''
        if link: inner_html += f'<p style="margin:0; padding:0; margin-top: 10px;"><a href="{link}" target="_blank">阅读原文</a></p>'

        # Wrap everything in a div with zero margin/padding and basic text style
        # self.article_html = f'<div style="margin:0; padding:0;">{inner_html}</div>'
        # Apply basic styling to the outer div to ensure text flows correctly
        # self.article_html = f'<div style="margin:0; padding:5px; line-height: 1.4;">{inner_html}</div>' # Added padding and line-height
        # Revert to zero padding on outer div, remove line-height
        # self.article_html = f'<div style="margin:0; padding:0;">{inner_html}</div>'

        # Use full HTML structure with CSS resets
        self.article_html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style type="text/css">
  body, div, h2, p, hr {{ margin: 0; padding: 0; border: none; font-size: {self.current_font_size}pt; }}
  body {{ background-color: transparent; }}
  hr {{ border-top: 1px solid #cccccc; margin-top: 5px; margin-bottom: 5px; }}
  a {{ color: #0066cc; }}
</style>
</head>
<body>
{inner_html}
</body>
</html>'''

        # --- HTML 生成结束 ---

        self._init_ui()
        self.logger.debug(f"Final HTML content before setHtml:\n{self.article_html}") # Log the final HTML
        # self.logger.debug(f"Setting HTML content (length: {len(self.article_html)}):\n{self.article_html[:500]}...") # 记录前500字符

        self.content_browser.setHtml(self.article_html) # 现在 article_html 是正确的 HTML 字符串
        self._update_font_size() # 应用初始字体大小
        # 移除 QTimer 调用

        # 移除应用主题样式的代码，对话框应继承父窗口样式

        self.setWindowTitle("新闻详情")
        # Simplify window flags to ensure standard behavior
        self.setWindowFlags(
            Qt.Dialog |
            Qt.WindowTitleHint |
            Qt.WindowSystemMenuHint |
            Qt.WindowMinimizeButtonHint | # Explicitly add minimize button hint
            Qt.WindowMaximizeButtonHint | # Explicitly add maximize button hint
            Qt.WindowCloseButtonHint
        )
        self.setMinimumSize(700, 500) # 增大最小尺寸
        self.resize(1000, 750) # 再次增大默认尺寸

    def showEvent(self, event):
        """Override showEvent to log geometry after the dialog is shown."""
        super().showEvent(event)
        # Use QTimer.singleShot to ensure layout is processed before logging
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._log_details_after_show)

    def _log_details_after_show(self):
        """Logs geometry and stylesheet after dialog is shown."""
        if hasattr(self, 'content_browser'):
            self.logger.debug(f"Detail Dialog content_browser geometry: {self.content_browser.geometry()}")
            self.logger.debug(f"Detail Dialog content_browser effective stylesheet:\n{self.content_browser.styleSheet()}")
        else:
            self.logger.warning("_log_details_after_show: content_browser not found.")

    def _init_ui(self):
        """初始化UI组件"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2) # Reduce margins significantly
        main_layout.setSpacing(4) # Reduce spacing

        # --- 字体控制按钮 ---
        font_control_layout = QHBoxLayout()
        font_control_layout.setSizeConstraint(QHBoxLayout.SetMaximumSize) # Prevent vertical stretch
        font_control_layout.setSpacing(5)

        self.decrease_font_button = QToolButton()
        self.decrease_font_button.setToolTip("减小字体")
        # self.decrease_font_button.setText("-")
        self.decrease_font_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)) # Use standard icon
        self.decrease_font_button.setObjectName("decreaseFontButton") # 添加 objectName
        self.decrease_font_button.clicked.connect(self._decrease_font)
        font_control_layout.addWidget(self.decrease_font_button)

        self.increase_font_button = QToolButton()
        self.increase_font_button.setToolTip("增大字体")
        # self.increase_font_button.setText("+")
        self.increase_font_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp)) # Use standard icon
        self.increase_font_button.setObjectName("increaseFontButton") # 添加 objectName
        self.increase_font_button.clicked.connect(self._increase_font)
        font_control_layout.addWidget(self.increase_font_button)

        font_control_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)) # 推到左侧

        self.copy_button = QPushButton("复制")
        self.copy_button.setToolTip("复制新闻内容到剪贴板")
        self.copy_button.clicked.connect(self._copy_content)
        font_control_layout.addWidget(self.copy_button) # 添加到字体控制行
        main_layout.addLayout(font_control_layout, 0) # Add top layout with stretch factor 0

        # --- 内容显示区域 ---
        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(True) # 允许打开外部链接
        self.content_browser.setObjectName("NewsDetailContentBrowser") # 添加 objectName
        # Try Ignored policy vertically
        self.content_browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        # Try setting document margin to 0 to reduce internal padding
        self.content_browser.document().setDocumentMargin(0)
        # Also explicitly set padding to 0 via stylesheet
        self.content_browser.setStyleSheet("QTextBrowser#NewsDetailContentBrowser { padding: 0px; border: 1px solid #cccccc; }")
        main_layout.addWidget(self.content_browser, 1) # Add browser with stretch factor 1 (takes most space)

        # --- 关闭按钮 ---
        button_layout = QHBoxLayout()
        button_layout.setSizeConstraint(QHBoxLayout.SetMaximumSize) # Prevent vertical stretch
        button_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)) # 推到右侧
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        main_layout.addLayout(button_layout, 0) # Add bottom layout with stretch factor 0

    def _update_font_size(self):
        """更新文本浏览器的字体大小"""
        # font = self.content_browser.font()
        # font.setPointSize(self.current_font_size)
        # self.content_browser.setFont(font) # Keep setFont as a base (Commented out: Rely on HTML CSS)
        # Also set stylesheet to increase specificity against global QSS
        # 设置基础样式和字体大小
        # base_style = "" # Corrected: Empty string
        # self.content_browser.setStyleSheet(f"""
        #     QTextBrowser#NewsDetailContentBrowser {{
        #         font-size: {self.current_font_size}pt;
        #         outline: none;
        #         border: 1px solid #cccccc; /* 整合边框样式 */
        #     }}
        #     /* {base_style} */ /* Temporarily removed */
        # """)

        # Regenerate HTML with the new font size in its style block
        self._regenerate_and_set_html()

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

    def _regenerate_and_set_html(self):
        """Regenerate HTML with the new font size in its style block"""
        # 处理publish_time可能是各种类型的情况
        if isinstance(self.news_article.publish_time, datetime):
            date = self.news_article.publish_time.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(self.news_article.publish_time, str):
            # 尝试将字符串转换为datetime对象以统一格式
            try:
                date_obj = datetime.fromisoformat(self.news_article.publish_time.replace('Z', '+00:00'))
                date = date_obj.strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                # 如果无法解析，直接使用原始字符串
                date = self.news_article.publish_time
        elif self.news_article.publish_time is None:
            date = "未知日期"
        else:
            # 处理其他类型，尝试转换为字符串
            try:
                date = str(self.news_article.publish_time)
            except:
                date = "未知日期"
        content_display = self.news_article.content
        summary_display = self.news_article.summary
        if summary_display: # New logic: Prioritize summary
            description = summary_display
        elif content_display: # If no summary, but content exists
            description = content_display
        else: # If neither summary nor content exists
            description = '无内容'
        link = self.news_article.link or ''
        self.logger.debug(f"Generating HTML with source: '{self.news_article.source_name}'") # 添加日志

        # Construct content first with CSS resets
        inner_html = f'''
        <h2 style="margin:0; padding:0;">{self.news_article.title or '无标题'}</h2>
        <p style="margin:0; padding:0;"><strong>来源:</strong> {self.news_article.source_name or '未知来源'} | <strong>日期:</strong> {date}</p>
        <hr style="margin-top: 5px; margin-bottom: 5px;">
        <div style="margin:0; padding:0;">{description}</div>
        '''
        if link: inner_html += f'<p style="margin:0; padding:0; margin-top: 10px;"><a href="{link}" target="_blank">阅读原文</a></p>'

        # Wrap everything in a div with zero margin/padding and basic text style
        # self.article_html = f'<div style="margin:0; padding:0;">{inner_html}</div>'
        # Apply basic styling to the outer div to ensure text flows correctly
        # self.article_html = f'<div style="margin:0; padding:5px; line-height: 1.4;">{inner_html}</div>' # Added padding and line-height
        # Revert to zero padding on outer div, remove line-height
        # self.article_html = f'<div style="margin:0; padding:0;">{inner_html}</div>'

        # Use full HTML structure with CSS resets
        self.article_html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style type="text/css">
  body, div, h2, p, hr {{ margin: 0; padding: 0; border: none; font-size: {self.current_font_size}pt; }}
  body {{ background-color: transparent; }}
  hr {{ border-top: 1px solid #cccccc; margin-top: 5px; margin-bottom: 5px; }}
  a {{ color: #0066cc; }}
</style>
</head>
<body>
{inner_html}
</body>
</html>'''

        # --- HTML 生成结束 ---

        self.content_browser.setHtml(self.article_html) # 现在 article_html 是正确的 HTML 字符串
        # 可能需要重新设置 HTML 以确保字体生效 (保留注释)
        # self.content_browser.setHtml(self.article_html) # Remove forced re-render from here

# 移除 _update_button_texts_and_repaint 方法