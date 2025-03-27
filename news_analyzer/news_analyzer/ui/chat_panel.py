"""
聊天面板

提供与大语言模型交互的聊天界面，支持增强的流式输出和动画效果。
支持独立聊天和新闻上下文聊天模式。
"""

import logging
import math
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                            QPushButton, QScrollArea, QLabel, QTextBrowser,
                            QFrame, QSizePolicy, QCheckBox, QGraphicsOpacityEffect,
                            QApplication)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize, pyqtSlot, QObject, QPropertyAnimation, QEasingCurve, QEvent
from PyQt5.QtGui import (QColor, QPainter, QPixmap, QIcon, QKeyEvent, QPalette, 
                        QLinearGradient, QFont, QRadialGradient)

from news_analyzer.llm.llm_client import LLMClient


class StreamHandler(QObject):
    """流处理信号类 - 增强版本支持更流畅的文本动画"""
    update_signal = pyqtSignal(str, bool)
    
    def __init__(self):
        super().__init__()
        self.accumulated_text = ""
        self.last_text_length = 0
        
    def handle_stream(self, text, done):
        """处理流式文本输出"""
        # 保存完整文本用于处理完成时的最终格式化
        self.accumulated_text = text
        
        # 发出信号，立即更新UI
        self.update_signal.emit(text, done)
        
        # 记录上次处理的文本长度
        self.last_text_length = len(text)


class ChatBubble(QFrame):
    """聊天气泡组件"""
    def __init__(self, text, is_user=False, parent=None):
        super().__init__(parent)
        self.text = text
        self.is_user = is_user
        self.setMinimumWidth(200)
        self.setMaximumWidth(800)  # 增加最大宽度，改善长文本显示
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self._init_ui()
        self._setup_animation()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        if self.is_user:
            self.setStyleSheet("""
                QFrame {
                    border-radius: 15px;
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                stop:0 #E3F2FD, stop:1 #BBDEFB);
                    border: 1px solid #90CAF9;
                    margin: 2px;
                }
            """)
            text_color = "#263238"
            align = Qt.AlignRight
        else:
            self.setStyleSheet("""
                QFrame {
                    border-radius: 15px;
                    background-color: #F5F5F5;
                    border: 1px solid #E0E0E0;
                    margin: 2px;
                }
            """)
            text_color = "#37474F"
            align = Qt.AlignLeft
        
        self.text_browser = QTextBrowser()
        self.text_browser.setHtml(self.text)
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.setAlignment(align)
        
        # 设置透明背景
        palette = self.text_browser.palette()
        palette.setBrush(QPalette.Base, Qt.transparent)
        self.text_browser.setPalette(palette)
        
        # 增强文本样式以提高可读性
        self.text_browser.setStyleSheet(f"""
            QTextBrowser {{
                border: none;
                background-color: transparent;
                padding: 12px 16px;
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
                font-size: 15px;
                line-height: 1.8;
                color: {text_color};
                selection-background-color: #BBDEFB;
            }}
        """)
        
        # 关键修改: 设置最小高度但移除最大高度限制
        self.text_browser.setMinimumHeight(60)
        # 使用Qt的默认最大值，实际上是移除限制
        self.text_browser.setMaximumHeight(16777215)
        
        # 强制使用适当的尺寸策略以允许垂直扩展
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setHeightForWidth(True)
        sizePolicy.setVerticalStretch(1)
        self.setSizePolicy(sizePolicy)
        self.text_browser.setSizePolicy(sizePolicy)
        
        # 禁用所有滚动条以便气泡随内容自动扩展
        self.text_browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 启用自动换行
        self.text_browser.setWordWrapMode(True)
        
        # 设置文档边距
        self.text_browser.document().setDocumentMargin(8)
        self.text_browser.setReadOnly(True)
        
        # 文档内容变化时重新计算高度
        self.text_browser.document().contentsChanged.connect(self._adjust_height)
        
        layout.addWidget(self.text_browser)

    def _adjust_height(self):
        """直接调整文本浏览器高度以适应内容"""
        # 获取文档实际高度
        doc_height = self.text_browser.document().size().height()
        margins = self.text_browser.contentsMargins()
        total_margin = margins.top() + margins.bottom() + 24
        new_height = int(doc_height + total_margin)
        
        # 直接设置高度而不使用动画，确保立即生效
        if new_height > 60:
            self.text_browser.setMinimumHeight(new_height)
        
        # 强制立即更新布局
        self.layout().activate()
        self.updateGeometry()
    
    def _setup_animation(self):
        """设置气泡出现动画"""
        self.setGraphicsEffect(None)
        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(200)
        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)
        self.opacity_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.opacity_animation.start()
        
    def update_content(self, html_text):
        """使用HTML格式化内容更新文本浏览器"""
        # 应用增强的排版格式
        formatted_html = self._enhance_formatting(html_text)
        self.text_browser.setHtml(formatted_html)
        
        # 进行多次高度调整以确保内容完全加载后正确调整大小
        self._adjust_height()
        QTimer.singleShot(50, self._adjust_height)
        QTimer.singleShot(200, self._adjust_height)
    
    def _enhance_formatting(self, html_text):
        """增强HTML内容的排版和可读性"""
        return f"""
        <div style='font-family: "Microsoft YaHei", "Segoe UI", sans-serif; line-height: 1.8;'>
            {html_text}
        </div>
        """


class SmoothScrollArea(QScrollArea):
    """支持平滑滚动效果的滚动区域"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scroll_animation = QPropertyAnimation(self.verticalScrollBar(), b"value")
        self.scroll_animation.setDuration(300)
        self.scroll_animation.setEasingCurve(QEasingCurve.OutCubic)
    
    def smooth_scroll_to(self, value):
        """平滑滚动到指定位置"""
        if self.scroll_animation.state() == QPropertyAnimation.Running:
            self.scroll_animation.stop()
        
        self.scroll_animation.setStartValue(self.verticalScrollBar().value())
        self.scroll_animation.setEndValue(value)
        self.scroll_animation.start()


class TypingIndicator(QWidget):
    """打字指示器组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(70, 30)
        self.dots = [0, 0, 0]  # 三个点的动画状态
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_dots)
        self.timer.start(160)  # 动画速度
        
        # 使用更好看的渐变色
        self.gradient_colors = [
            QColor("#2196F3"),  # 蓝色
            QColor("#64B5F6"),  # 浅蓝色 
            QColor("#90CAF9")   # 更浅的蓝色
        ]
        
        # 添加淡入淡出效果
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(300)
    
    def update_dots(self):
        """更新点的动画状态"""
        for i in range(3):
            # 使用正弦函数创建平滑的波浪效果
            self.dots[i] = (self.dots[i] + 1) % 8
        self.update()  # 触发重绘
    
    def paintEvent(self, event):
        """绘制动画点"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for i in range(3):
            # 创建波浪效果
            y_offset = 6 * (1 + 0.5 * math.sin(self.dots[i] * math.pi / 4))
            x = 15 + i * 20
            y = 15 - y_offset
            
            # 创建渐变填充
            radial_gradient = QRadialGradient(x + 5, y + 5, 8)
            radial_gradient.setColorAt(0, self.gradient_colors[i].lighter(120))
            radial_gradient.setColorAt(1, self.gradient_colors[i])
            
            painter.setBrush(radial_gradient)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(int(x), int(y), 10, 10)
    
    def show_indicator(self):
        """平滑显示指示器"""
        self.show()
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_animation.start()
        self.timer.start()
    
    def hide_indicator(self):
        """平滑隐藏指示器"""
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.InCubic)
        self.fade_animation.start()
        
        # 等动画完成后隐藏并停止计时器
        QTimer.singleShot(300, self.timer.stop)
        QTimer.singleShot(300, self.hide)


class ChatPanel(QWidget):
    """聊天面板组件"""
    message_sent = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.chat_panel')
        self.llm_client = LLMClient()
        self.current_news = None
        self.chat_history = []
        
        # 存储可用的新闻标题
        self.available_news_titles = []
        
        # 流处理器
        self.stream_handler = StreamHandler()
        self.stream_handler.update_signal.connect(self._update_message)
        
        # 默认不使用新闻上下文
        self.use_news_context = False
        
        # 用于追踪当前AI回复
        self.current_ai_bubble = None
        
        # 用于存储打字指示器
        self.typing_indicator = None
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 顶部标题和控制栏
        header_layout = QHBoxLayout()
        title_label = QLabel("智能助手聊天")
        title_label.setStyleSheet("""
            font-weight: bold; 
            font-size: 16px; 
            color: #1976D2;
            font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            padding: 5px;
        """)
        header_layout.addWidget(title_label)
        
        self.context_checkbox = QCheckBox("使用新闻上下文")
        self.context_checkbox.setChecked(False)  # 默认不使用新闻上下文
        self.context_checkbox.toggled.connect(self._toggle_context_mode)
        self.context_checkbox.setStyleSheet("""
            QCheckBox {
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
                color: #455A64;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #90A4AE;
                background-color: white;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #2196F3;
                background-color: #2196F3;
                border-radius: 4px;
            }
        """)
        header_layout.addWidget(self.context_checkbox)
        header_layout.addStretch()
        
        self.clear_button = QPushButton("清空聊天")
        self.clear_button.setFixedSize(100, 32)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #ECEFF1;
                border: 1px solid #CFD8DC;
                border-radius: 16px;
                padding: 4px 12px;
                color: #455A64;
                font-weight: bold;
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            }
            QPushButton:hover {
                background-color: #CFD8DC;
                border: 1px solid #B0BEC5;
            }
            QPushButton:pressed {
                background-color: #B0BEC5;
            }
        """)
        self.clear_button.clicked.connect(self._clear_chat)
        header_layout.addWidget(self.clear_button)
        layout.addLayout(header_layout)
        
        # 聊天区域 - 使用自定义滚动区域支持平滑滚动
        self.chat_area = SmoothScrollArea()
        self.chat_area.setWidgetResizable(True)
        self.chat_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.chat_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #E0E0E0;
                background-color: #FAFAFA;
                border-radius: 8px;
            }
            QScrollBar:vertical {
                border: none;
                background: #F5F5F5;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #BDBDBD;
                min-height: 30px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9E9E9E;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_layout.setSpacing(12)
        self.chat_layout.setContentsMargins(15, 15, 15, 15)
        
        self.chat_area.setWidget(self.chat_container)
        layout.addWidget(self.chat_area, 1)
        
        # 创建并添加打字指示器
        self.typing_indicator = TypingIndicator()
        self.typing_indicator.hide()  # 初始时隐藏
        
        # 输入区域
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)
        
        input_frame = QFrame()
        input_frame.setFrameShape(QFrame.StyledPanel)
        input_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #BDBDBD;
                border-radius: 18px;
                background-color: white;
            }
        """)
        input_frame_layout = QHBoxLayout(input_frame)
        input_frame_layout.setContentsMargins(10, 5, 10, 5)
        
        self.message_input = QTextEdit()
        self.message_input.setFixedHeight(60)
        self.message_input.setPlaceholderText("输入消息，按Enter发送...")
        self.message_input.setStyleSheet("""
            QTextEdit {
                border: none;
                padding: 8px;
                font-size: 14px;
                font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
                background-color: transparent;
            }
        """)
        self.message_input.installEventFilter(self)
        input_frame_layout.addWidget(self.message_input)
        
        input_layout.addWidget(input_frame, 1)
        
        self.send_button = QPushButton("")
        self.send_button.setFixedSize(60, 60)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 30px;
                font-weight: bold;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: #1E88E5;
            }
            QPushButton:pressed {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        
        send_icon = QIcon.fromTheme("send")
        if not send_icon.isNull():
            self.send_button.setIcon(send_icon)
        else:
            self.send_button.setText("→")
        
        self.send_button.clicked.connect(self._on_send_clicked)
        input_layout.addWidget(self.send_button)
        
        layout.addLayout(input_layout)
        
        # 添加欢迎消息
        welcome_text = """
        <div style='font-family: "Microsoft YaHei", "Segoe UI", sans-serif; line-height: 1.8;'>
            <h3 style='color: #1976D2; margin-bottom: 12px;'>👋 欢迎使用智能助手！</h3>
            <p style='margin: 8px 0;'>我可以帮你：</p>
            <ul style='margin: 8px 0; padding-left: 20px;'>
                <li style='margin: 6px 0;'>回答一般性问题</li>
                <li style='margin: 6px 0;'>提供信息和建议</li>
                <li style='margin: 6px 0;'>分析和总结内容</li>
                <li style='margin: 6px 0;'>探讨各种话题</li>
            </ul>
            <p style='margin: 8px 0;'>如需使用新闻上下文功能，请勾选上方的"使用新闻上下文"选项并从新闻列表中选择一篇新闻。</p>
            <p style='margin: 8px 0;'>有任何问题，请直接提问！</p>
        </div>
        """
        self._add_message(welcome_text)
    
    def set_available_news_titles(self, news_items):
        """设置当前可用的所有新闻标题"""
        self.available_news_titles = []
        for news in news_items:
            title = news.get('title', '无标题')
            self.available_news_titles.append(title)
        
        self.logger.debug(f"设置了 {len(self.available_news_titles)} 条可用新闻标题")
    
    def eventFilter(self, obj, event):
        """事件过滤器 - 处理Enter键发送"""
        if obj is self.message_input and event.type() == QKeyEvent.KeyPress:
            if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
                self._on_send_clicked()
                return True
        return super().eventFilter(obj, event)
    
    def _toggle_context_mode(self, checked):
        """切换新闻上下文模式"""
        self.use_news_context = checked
        
        if checked and self.current_news:
            message = f"""
            <div style='font-family: "Microsoft YaHei", "Segoe UI", sans-serif; line-height: 1.8;'>
                <h3 style='color: #1976D2; margin-bottom: 10px;'>已切换到新闻上下文模式</h3>
                <p style='margin: 8px 0;'>当前新闻: <strong>{self.current_news.get('title', '无标题')}</strong></p>
            </div>
            """
        elif checked and not self.current_news:
            message = """
            <div style='font-family: "Microsoft YaHei", "Segoe UI", sans-serif; line-height: 1.8;'>
                <h3 style='color: #1976D2; margin-bottom: 10px;'>已切换到新闻上下文模式</h3>
                <p style='margin: 8px 0;'>提示: 请从新闻列表中选择一篇新闻</p>
            </div>
            """
        else:
            message = """
            <div style='font-family: "Microsoft YaHei", "Segoe UI", sans-serif; line-height: 1.8;'>
                <h3 style='color: #1976D2; margin-bottom: 10px;'>已切换到一般对话模式</h3>
                <p style='margin: 8px 0;'>您可以问任何问题，无需选择新闻</p>
            </div>
            """
        
        self._add_message(message)
    
    def set_current_news(self, news_item):
        """设置当前新闻"""
        if not news_item:
            return
            
        self.current_news = news_item
        
        if self.use_news_context:
            title = news_item.get('title', '未知标题')
            text = f"""
            <div style='font-family: "Microsoft YaHei", "Segoe UI", sans-serif; line-height: 1.8;'>
                <h3 style='color: #1976D2; margin-bottom: 10px;'>📰 已选择新闻</h3>
                <p style='margin: 8px 0; font-weight: bold;'>{title}</p>
                <p style='margin: 8px 0;'>你可以询问与这则新闻相关的任何问题。</p>
            </div>
            """
            self._add_message(text)
        
        self.logger.debug(f"设置当前新闻: {news_item.get('title', '')[:30]}...")
    
    def _is_asking_for_news_titles(self, message):
        """检查用户是否在询问可用新闻标题"""
        keywords = ["有什么新闻", "新闻标题", "看到什么", "左侧", "左边", "新闻列表", 
                   "有哪些", "查看新闻", "显示新闻", "列出", "看看", "新闻有哪些"]
        
        message_lower = message.lower()
        for keyword in keywords:
            if keyword in message_lower:
                return True
        return False
    
    def _create_news_title_response(self):
        """创建包含新闻标题的格式化回复"""
        if not self.available_news_titles:
            return """
            <div style='font-family: "Microsoft YaHei", "Segoe UI", sans-serif; line-height: 1.8;'>
                <h3 style='color: #1976D2; margin-bottom: 12px;'>可用新闻</h3>
                <p style='margin: 8px 0;'>目前没有可用的新闻文章。</p>
                <p style='margin: 8px 0;'>您可以通过刷新新闻或添加新闻源来获取新闻。</p>
            </div>
            """
        
        response = """
        <div style='font-family: "Microsoft YaHei", "Segoe UI", sans-serif; line-height: 1.8;'>
            <h3 style='color: #1976D2; margin-bottom: 12px;'>可用新闻文章</h3>
            <p style='margin: 8px 0;'>以下是当前可用的新闻文章：</p>
            <div style='margin: 12px 0 12px 0;'>
        """
        
        # 列出所有新闻标题
        for i, title in enumerate(self.available_news_titles, 1):
            response += f"""<p style='margin: 6px 0; padding-left: 12px; border-left: 3px solid #90CAF9;'>
                <span style='color: #1976D2; font-weight: 500;'>{i}.</span> {title}
            </p>"""
        
        response += """
            </div>
            <p style='margin: 8px 0;'>选择任意文章查看详情，或询问特定主题的问题。</p>
        </div>
        """
        
        return response
    
    def _on_send_clicked(self):
        """处理发送按钮点击事件"""
        message = self.message_input.toPlainText().strip()
        if not message:
            return
        
        # 检查是否需要新闻上下文但没有选择新闻
        if self.use_news_context and not self.current_news:
            self._add_message(f"<div>{message}</div>", is_user=True)
            self._add_message("""
            <div style='font-family: "Microsoft YaHei", "Segoe UI", sans-serif; line-height: 1.8;'>
                <h3 style='color: #F44336; margin-bottom: 10px;'>未选择新闻</h3>
                <p style='margin: 8px 0;'>请先从新闻列表中选择一篇新闻，或取消勾选"使用新闻上下文"切换到一般对话模式。</p>
            </div>
            """)
            return
        
        # 禁用UI元素
        self.send_button.setEnabled(False)
        self.message_input.setReadOnly(True)
        self.message_input.clear()
        
        # 添加用户消息
        formatted_message = f"<div style='font-family: \"Microsoft YaHei\", \"Segoe UI\", sans-serif; line-height: 1.8;'>{message}</div>"
        self._add_message(formatted_message, is_user=True)
        self.chat_history.append({"role": "user", "content": message})
        
        # 检查是否在询问新闻标题
        if self._is_asking_for_news_titles(message):
            # 直接返回新闻标题，不调用API
            response = self._create_news_title_response()
            self._add_message(response, is_user=False)
            self.chat_history.append({"role": "assistant", "content": response})
            
            # 重新启用UI
            self.send_button.setEnabled(True)
            self.message_input.setReadOnly(False)
            return
        
        # 获取AI回复
        self._get_ai_response(message)
    
    def _add_message(self, text, is_user=False):
        """添加新消息到聊天窗口"""
        # 创建聊天气泡
        bubble = ChatBubble(text, is_user)
        
        # 添加到布局中，使用Qt.AlignTop以确保气泡从顶部开始
        self.chat_layout.addWidget(bubble, 0, Qt.AlignTop)
        
        # 如果是AI消息，保存引用
        if not is_user:
            self.current_ai_bubble = bubble
        
        # 滚动到底部显示新消息
        QTimer.singleShot(100, self._scroll_to_bottom)
        
        # 更新布局以适应新气泡
        QApplication.processEvents()
        
        return bubble
    
    def _scroll_to_bottom(self):
        """平滑滚动到底部"""
        # 使用平滑滚动动画
        max_value = self.chat_area.verticalScrollBar().maximum()
        self.chat_area.smooth_scroll_to(max_value)
    
    def _get_ai_response(self, user_message):
        """获取AI回复"""
        try:
            # 准备上下文
            context = ""
            if self.use_news_context and self.current_news:
                # 单条新闻上下文处理
                title = self.current_news.get('title', '')
                source = self.current_news.get('source_name', '')
                content = self.current_news.get('description', '')
                pub_date = self.current_news.get('pub_date', '')
                link = self.current_news.get('link', '')
                
                context = f"""新闻标题: {title}
新闻来源: {source}
发布日期: {pub_date}
原文链接: {link}

新闻内容: 
{content}
"""
            
            # 创建一个初始的AI消息气泡，显示"思考中..."
            initial_content = """
            <div style='font-family: "Microsoft YaHei", "Segoe UI", sans-serif; line-height: 1.8;'>
                <p style='font-style: italic; color: #757575;'>思考中...</p>
            </div>
            """
            self.current_ai_bubble = self._add_message(initial_content, is_user=False)
            
            # 显示打字指示器
            indicator_container = QWidget()
            indicator_layout = QHBoxLayout(indicator_container)
            indicator_layout.setAlignment(Qt.AlignLeft)
            indicator_layout.setContentsMargins(15, 0, 0, 0)
            
            indicator_layout.addWidget(self.typing_indicator)
            self.chat_layout.addWidget(indicator_container)
            self.typing_indicator.show_indicator()
            
            self._scroll_to_bottom()
            
            # 发起流式请求
            self.llm_client.chat(
                messages=self.chat_history, 
                context=context,
                stream=True,
                callback=self.stream_handler.handle_stream
            )
            
        except Exception as e:
            self.typing_indicator.hide_indicator()
            error_msg = f"""
            <div style='font-family: "Microsoft YaHei", "Segoe UI", sans-serif; line-height: 1.8;'>
                <h3 style='color: #F44336; margin-bottom: 10px;'>请求失败</h3>
                <p style='margin: 8px 0;'><b>错误:</b> {str(e)}</p>
                <p style='margin: 8px 0;'>请检查语言模型设置或网络连接后重试。</p>
            </div>
            """
            if self.current_ai_bubble:
                self.current_ai_bubble.update_content(error_msg)
            else:
                self._add_message(error_msg)
                
            self.send_button.setEnabled(True)
            self.message_input.setReadOnly(False)
            self.logger.error(f"获取AI回复失败: {str(e)}")
    
    def _format_ai_response(self, text):
        """增强AI回复的排版格式化"""
        from html import escape
        
        if not text:
            return text
            
        # 如果文本中没有HTML标签，则对其进行转义并转换换行符
        if '<' not in text and '>' not in text:
            text = escape(text)
            text = text.replace('\n', '<br>')
        
        # 格式化各种HTML元素以提升排版质量
        # 1. 标题格式化
        if '<h3>' in text:
            text = text.replace('<h3>', '<h3 style="font-size: 18px; margin-top: 12px; margin-bottom: 12px; color: #1976D2; font-weight: 600;">')
        
        # 2. 段落格式化  
        if '<p>' in text:
            text = text.replace('<p>', '<p style="margin-top: 10px; margin-bottom: 10px; line-height: 1.8;">')
        
        # 3. 列表格式化
        if '<ul>' in text:
            text = text.replace('<ul>', '<ul style="margin-top: 10px; margin-bottom: 14px; padding-left: 25px;">')
            
        if '<li>' in text:
            text = text.replace('<li>', '<li style="margin-bottom: 8px; padding-left: 5px;">')
        
        # 4. 代码块格式化
        if '<code>' in text:
            text = text.replace('<code>', '<code style="font-family: Consolas, Monaco, monospace; background-color: #F5F5F5; padding: 2px 4px; border-radius: 3px; border: 1px solid #E0E0E0;">')
            
        # 强调元素格式化
        if '<strong>' in text:
            text = text.replace('<strong>', '<strong style="font-weight: 600; color: #1565C0;">')
            
        # 引用格式化
        if '<blockquote>' in text:
            text = text.replace('<blockquote>', '<blockquote style="border-left: 4px solid #BBDEFB; padding: 8px 12px; margin: 10px 0; background-color: #F5F5F5;">')
        
        # 包装在一个统一样式的容器中
        return f"""
        <div style='font-family: "Microsoft YaHei", "Segoe UI", sans-serif; 
               line-height: 1.8; 
               font-size: 15px;'>
            {text}
        </div>
        """
    
    @pyqtSlot(str, bool)
    def _update_message(self, text, done):
        """更新消息内容，支持流式输出"""
        if not self.current_ai_bubble:
            return
            
        # 格式化文本
        formatted_text = self._format_ai_response(text)
        
        # 更新气泡内容
        self.current_ai_bubble.update_content(formatted_text)
        
        # 确保滚动保持在底部
        if len(text) > 100:  # 仅在内容较长时执行滚动，减少性能消耗
            self._scroll_to_bottom()
        
        # 如果消息完成，更新聊天历史并重新启用UI
        if done:
            # 隐藏打字指示器
            self.typing_indicator.hide_indicator()
            
            # 更新聊天历史
            self.chat_history.append({"role": "assistant", "content": text})
            
            # 重新启用UI
            self.send_button.setEnabled(True)
            self.message_input.setReadOnly(False)
            
            # 清空当前气泡引用
            self.current_ai_bubble = None
            
            # 最终滚动以确保完整消息可见
            QTimer.singleShot(150, self._scroll_to_bottom)
    
    def _clear_chat(self):
        """清空聊天历史"""
        # 清空聊天布局中的所有内容
        while self.chat_layout.count() > 0:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 清空聊天历史记录
        self.chat_history = []
        self.current_ai_bubble = None
        
        # 添加欢迎消息
        welcome_text = """
        <div style='font-family: "Microsoft YaHei", "Segoe UI", sans-serif; line-height: 1.8;'>
            <h3 style='color: #1976D2; margin-bottom: 10px;'>聊天已重置！</h3>
            <p style='margin: 8px 0;'>如有问题，请继续提问。</p>
        </div>
        """
        self._add_message(welcome_text)