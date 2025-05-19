"""聊天面板

提供与大语言模型交互的聊天界面。
支持独立聊天和新闻上下文聊天模式。 (非流式，但有等待提示)
"""

import logging
from typing import List, Optional # 导入 List 和 Optional

import re # 添加 re 模块导入
import math
# import threading # 不再需要
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
                             QScrollArea, QLabel, QTextBrowser, QFrame, QSizePolicy,
                             QCheckBox, QApplication, QSpacerItem, QStyle) # Use PySide6
from PySide6.QtCore import Qt, Signal as pyqtSignal, QTimer, QSize, Slot as pyqtSlot, QEvent # Use PySide6, alias Signal/Slot
from PySide6.QtGui import QIcon, QKeyEvent, QFontMetrics, QTextOption # Use PySide6, combined QtGui imports
# LLMService is now accessed via ViewModel
# from src.llm.llm_service import LLMService
from src.models import NewsArticle, ChatMessage # Use absolute import from src
from ..ui_utils import create_standard_button, create_title_label # <-- RELATIVE IMPORT to parent dir ui_utils
from ..viewmodels.chat_panel_viewmodel import ChatPanelViewModel # <-- RELATIVE IMPORT to parent dir viewmodels

class ChatPanel(QWidget):
    """聊天面板组件"""
    message_sent = pyqtSignal(str) # Keep if external components need to know about user messages

    def __init__(self, view_model: ChatPanelViewModel, parent=None): # 参数改回 ViewModel
        super().__init__(parent)
        self.setObjectName("ChatPanel") # Add objectName for QSS targeting
        self.logger = logging.getLogger('news_analyzer.ui.chat_panel')
        self._view_model = view_model # 使用 ViewModel
        self.typing_indicator = None # Will hold the indicator label (QLabel)
        self.current_assistant_bubble: Optional[QTextBrowser] = None # Stores the current assistant bubble for streaming updates
        self._init_ui()
        self._connect_view_model()

    def _init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding) # Set size policy
        layout.setSpacing(10)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        # title_label = create_title_label("智能助手聊天") # Removed title
        # header_layout.addWidget(title_label) # Removed title

        self.context_checkbox = QCheckBox("使用新闻上下文")
        self.context_checkbox.setChecked(False)
        self.context_checkbox.setObjectName("contextCheckbox") # Add objectName
        self.context_checkbox.toggled.connect(self._view_model.set_use_news_context)
        header_layout.addWidget(self.context_checkbox)
        header_layout.addStretch()

        self.clear_button = create_standard_button(
            text="清空聊天",
            tooltip="清空当前聊天记录",
            fixed_size=QSize(100, 32)
        )
        self.clear_button.setObjectName("clearChatButton") # Add objectName
        self.clear_button.clicked.connect(self._clear_chat)
        header_layout.addWidget(self.clear_button)
        layout.addLayout(header_layout)

        self.selected_news_label = QLabel("未选择新闻")
        self.selected_news_label.setObjectName("selectedNewsLabel") # QSS target
        # Style handled by QSS
        layout.addWidget(self.selected_news_label)

        self.chat_area = QScrollArea() # Use standard QScrollArea
        self.chat_area.setObjectName("chatArea") # QSS target
        # --- Restore widgetResizable=True ---
        self.chat_area.setWidgetResizable(True)
        self.chat_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.chat_area.verticalScrollBar().rangeChanged.connect(self._scroll_to_bottom_on_range_change)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container) # This layout holds bubbles and indicator
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_layout.setSpacing(12)
        self.chat_layout.setContentsMargins(15, 15, 15, 15)

        self.chat_area.setWidget(self.chat_container)
        layout.addWidget(self.chat_area, 1) # Give chat area more stretch factor

        # Typing Indicator is added/removed dynamically
        self.logger.info("<<< Entering _add_message >>>") # Log entry

        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)

        input_frame = QFrame()
        input_frame.setObjectName("chatInputFrame") # QSS target
        # Style handled by QSS
        input_frame_layout = QHBoxLayout(input_frame)
        # Adjust margins for better vertical centering appearance
        input_frame_layout.setContentsMargins(10, 5, 10, 5) # Restore original margins

        self.message_input = QTextEdit()
        self.message_input.setObjectName("chatInput") # QSS target
        # Remove fixed height, allow vertical expansion based on content
        # self.message_input.setFixedHeight(input_height)
        self.message_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred) # Allow vertical expansion
        self.message_input.document().contentsChanged.connect(self._adjust_input_height) # Reconnect height adjustment
        self.message_input.setPlaceholderText("输入消息，按Enter发送...")
        self.message_input.installEventFilter(self)
        input_frame_layout.addWidget(self.message_input)

        input_layout.addWidget(input_frame, 1)

        # Calculate initial button height based on font metrics
        fm = QFontMetrics(self.message_input.font())
        initial_input_height = fm.height() + 10 # Approx 1 line + internal padding/margins
        # Make button height slightly larger than single line input height for better look
        initial_button_height = initial_input_height + 10
        self.button_size = QSize(initial_button_height, initial_button_height) # Store initial size

        self.stop_button = create_standard_button(
            text="", # Use icon instead of text
            tooltip="停止当前的 AI 响应",
            fixed_size=self.button_size, # Use calculated initial size
            object_name="chatStopButton" # QSS target
        )
        # Set standard stop icon
        self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_button.setIconSize(QSize(self.button_size.width() // 2, self.button_size.height() // 2)) # Adjust icon size
        self.stop_button.hide()
        self.stop_button.clicked.connect(self._view_model.stop_chat) # Connect to ViewModel's stop method
        input_layout.addWidget(self.stop_button)

        self.send_button = create_standard_button(
            text="", # Icon set below or by QSS
            icon_path=None,
            tooltip="发送消息 (Enter)",
            fixed_size=self.button_size, # Use calculated initial size
            object_name="chatSendButton" # QSS target
        )
        # --- Set Icon Programmatically as Fallback ---
        self.send_button.setText("➤") # Use a unicode arrow
        self.send_button.setStyleSheet(f"font-size: {int(self.button_size.height() * 0.5)}px; padding-bottom: 4px;") # Adjust font size based on height
        self.send_button.clicked.connect(self._on_send_clicked)
        input_layout.addWidget(self.send_button)
        layout.addLayout(input_layout)
        QTimer.singleShot(0, self._adjust_input_height) # Call initial adjustment after event loop


        # Initial welcome message handled by _handle_history_update

    def set_available_news_items(self, news_articles: List[NewsArticle]):
        """(DEPRECATED) ViewModel manages context."""
        self.logger.warning("set_available_news_items called, but ViewModel manages context.")
        pass

    def eventFilter(self, obj, event):
        """事件过滤器 - 处理Enter键发送"""
        if obj is self.message_input and event.type() == QKeyEvent.KeyPress:
            if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
                self._on_send_clicked()
                return True
        return super().eventFilter(obj, event)

    def _toggle_context_mode(self, checked):
        """(DEPRECATED) UI state driven by ViewModel signals."""
        self.logger.debug(f"Checkbox toggled (state: {checked}), ViewModel handles logic.")
        # UI updates handled by _handle_context_mode_change_ui and _update_selected_news_label
        if self._view_model:
            self._view_model.set_use_news_context(checked)
        else:
            self.logger.warning("Context checkbox toggled but ViewModel is None.")

    # Removed deprecated set_current_news and set_current_category methods

    def _is_asking_for_news_titles(self, message):
        """(Helper) Checks if user message asks for news titles."""
        # This logic might be better placed in the ViewModel if it triggers specific actions
        keywords = ["有什么新闻", "新闻标题", "看到什么", "左侧", "左边", "新闻列表",
                   "有哪些", "查看新闻", "显示新闻", "列出", "看看", "新闻有哪些", "news titles", "list news"]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in keywords)

    def _create_news_title_response(self):
        """(Helper) Creates HTML response listing available news titles."""
        # This logic might be better placed in the ViewModel
        available_news = self._view_model.newsList # Assuming ViewModel has newsList property
        if not available_news:
            return "<p>当前没有可用的新闻。</p>"

        response_html = "<p>当前可用的新闻标题：</p><ul>"
        for news_item in available_news[:15]: # Limit displayed titles
            title = news_item.title if news_item.title else "无标题"
            safe_title = title.replace('&', '&amp;').replace('<', '<').replace('>', '>')
            response_html += f"<li>{safe_title}</li>"
        response_html += "</ul>"
        if len(available_news) > 15:
             response_html += "<p><i>(仅显示前 15 条)</i></p>"
        return response_html

    def _is_asking_about_category(self, message):
        """(Helper) Checks if user message asks about the current category."""
        # This logic might be better placed in the ViewModel
        keywords = ["什么分类", "当前分类", "哪个分类", "category"]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in keywords)

    def _on_send_clicked(self):
        """处理发送按钮点击事件"""
        user_message = self.message_input.toPlainText().strip()
        if not user_message:
            return

        # Check context mode requirement (handled by ViewModel, but UI can provide feedback)
        if self._view_model.use_news_context and not self._view_model.current_news:
            # Add a temporary error message bubble (optional, could be a status bar message)
            self._add_message("""
            <div style='font-family: "Microsoft YaHei", "Segoe UI", sans-serif; line-height: 1.8; color: #F44336;'>
                请先从新闻列表中选择一篇新闻，或取消勾选"使用新闻上下文"。
            </div>
            """, is_user=False) # Display as system/error message
            return

        self.message_input.clear()
        self.logger.debug("--- message_input cleared ---") # ADDED LOGGING
        self._view_model.send_message(user_message) # ViewModel handles busy state and history update

    def _add_message(self, text, is_user=False):
        """向聊天区域添加消息气泡 (使用QTextBrowser确保正确高度计算)"""
        self.logger.info(f"+++ METHOD _add_message ENTERED. is_user={is_user}. Content: '{str(text)[:50]}...' +++")
        if not isinstance(text, str):
            text = str(text)

        # Remove old typing indicator before adding new message
        self._remove_typing_indicator()

        # --- Revert to QTextBrowser with a QWidget wrapper --- 
        bubble = QTextBrowser()
        bubble.setFrameShape(QFrame.NoFrame)
        bubble.setReadOnly(True)
        bubble.setOpenExternalLinks(True)
        bubble.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        bubble.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Key: Allow vertical expansion, width driven by CSS max-width
        bubble.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)

        bubble.setObjectName("UserMessageBubble" if is_user else "AssistantMessageBubble")
        bubble.setProperty("is_user", str(is_user).lower())

        # 设置样式和文本 (Set QTextBrowser background to transparent, move visual styles to wrapper)
        # CRUCIAL: max-width for word wrapping, transparent background
        bubble.setStyleSheet(f"""
            QTextBrowser#{bubble.objectName()} {{
                background-color: transparent;
                border: none;
                max-width: 220px; /* Approx 12-15 CJK chars + internal space */
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
                font-size: 14px;
                color: #333333; /* Dark text color for good contrast */
                padding: 0px; /* Explicitly no padding */
                margin: 0px; /* Explicitly no margin */
            }}
        """)
        # Removed specific background/color/margin styles for QTextBrowser variants here

        bubble.setHtml(text)
        bubble.document().adjustSize() # CRUCIAL: Force document to lay out with constraints
        content_height = bubble.document().size().toSize().height()
        bubble.setFixedHeight(content_height) # Set fixed height for the QTextBrowser
        bubble.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed) # Width preferred, Height fixed


        # --- Wrap bubble in a QWidget for better layout behavior and styling ---
        bubble_wrapper = QWidget()
        bubble_wrapper.setObjectName("BubbleWrapper") # Give wrapper an object name
        bubble_wrapper.setProperty("is_user", str(is_user).lower()) # Pass property to wrapper
        # bubble_wrapper.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred) # Let it wrap its content
        # Set wrapper to fixed height as well, based on bubble's fixed height + padding
        bubble_wrapper.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)


        wrapper_layout = QVBoxLayout(bubble_wrapper)
        wrapper_layout.setContentsMargins(10, 10, 10, 10) # Apply padding to the wrapper's layout
        wrapper_layout.addWidget(bubble)

        wrapper_vertical_margins = wrapper_layout.contentsMargins().top() + wrapper_layout.contentsMargins().bottom()
        bubble_wrapper.setFixedHeight(bubble.height() + wrapper_vertical_margins) # Use bubble.height() which is now fixed


        # Apply visual styles (background, border, radius) to the wrapper
        bubble_wrapper.setStyleSheet(f"""
            QWidget#BubbleWrapper {{
                 margin-bottom: 8px; /* Margin for spacing between bubbles */
                 border-radius: 12px;
                 border: 1px solid #d0d0d0; /* Slightly lighter border for better theme blend */
            }}
            QWidget#BubbleWrapper[is_user="false"] {{
                 background-color: #f0f0f0; /* Assistant: Light neutral gray */
                 /* border-color: #d0d0d0; */
            }}
             QWidget#BubbleWrapper[is_user="true"] {{
                 background-color: #e6f2ff; /* User: Very light blue/greenish tint */
                 /* border-color: #c0d0e0; */ /* Can have slightly different border for user if desired */
             }}
        """)

        # --- Add bubble_wrapper to alignment layout (QHBoxLayout) --- 
        bubble_layout = QHBoxLayout()
        bubble_layout.setContentsMargins(0, 0, 0, 0)
        if is_user:
             bubble_layout.addStretch()
             bubble_layout.addWidget(bubble_wrapper)
        else:
             bubble_layout.addWidget(bubble_wrapper)
             bubble_layout.addStretch()

        # --- Logging Bubble Size --- 
        log_content = text[:100] + ('...' if len(text) > 100 else '')
        self.logger.debug(f"Setting bubble content (len={len(text)}): '{log_content}'")
        # Defer size check slightly to allow layout to process
        # QTimer.singleShot(0, lambda b=bubble: self.logger.debug(f"Bubble role='{'user' if is_user else 'assistant'}' | Size Hint: {b.sizeHint()} | Actual Size: {b.size()} | Doc Size: {b.document().size().toSize()}"))

        # --- Add the bubble_layout (QHBoxLayout) to the main chat_layout (QVBoxLayout) ---
        self.chat_layout.addLayout(bubble_layout)

        self.logger.info(f"+++ Bubble wrapper added to alignment layout for role={bubble.property('is_user')}. +++")

        if not is_user:
            self.current_assistant_bubble = bubble # Store the QTextBrowser for assistant messages
            self.logger.debug(f"Set current_assistant_bubble for assistant message.")
        else:
            self.current_assistant_bubble = None # Clear for user messages, next assistant msg will be new
            self.logger.debug(f"Cleared current_assistant_bubble due to user message.")

        # Scroll to bottom after adding the new message bubble
        # Use a QTimer to ensure the layout has been updated before scrolling
        QTimer.singleShot(250, self._scroll_to_bottom) # Reverted to simple scroll bottom

        self.logger.info(f"<<< Exiting _add_message for {'user' if is_user else 'assistant/error'} >>>") # Log exit

    def _clear_chat(self):
        """清空聊天记录"""
        self.logger.info("Clearing chat history.")
        # Clear the layout (remove all bubbles and indicator)
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif layout is not None:
                # Recursively clear nested layouts if any (like the bubble HBoxLayout)
                while layout.count():
                    sub_item = layout.takeAt(0)
                    sub_widget = sub_item.widget()
                    if sub_widget is not None:
                        sub_widget.deleteLater()
                layout.deleteLater()
        # Clear ViewModel history
        self._view_model.clear_chat_history()

    def _adjust_input_height(self):
        """根据内容动态调整输入框高度"""
        doc = self.message_input.document()
        metrics = QFontMetrics(doc.defaultFont())
        line_height = metrics.lineSpacing()
        margins = self.message_input.contentsMargins()
        num_lines = doc.blockCount()

        # Calculate preferred height
        preferred_height = line_height * num_lines + margins.top() + margins.bottom() + 5 # Add small buffer

        # Clamp height between 1 line and ~5 lines
        min_height = line_height + margins.top() + margins.bottom() + 5
        max_height = line_height * 5 + margins.top() + margins.bottom() + 10 # Allow slightly more space for max

        clamped_height = max(min_height, min(preferred_height, max_height))

        # Set fixed height to control resizing
        self.message_input.setFixedHeight(int(clamped_height))

        # Adjust button height to match input height
        new_button_height = int(clamped_height)
        self.button_size = QSize(new_button_height, new_button_height) # Update stored size
        self.send_button.setFixedSize(self.button_size)
        self.stop_button.setFixedSize(self.button_size)
        # Re-adjust icon size if needed
        icon_size = QSize(new_button_height // 2, new_button_height // 2)
        self.send_button.setIconSize(icon_size)
        self.stop_button.setIconSize(icon_size)
        # Update font size for text-based button
        self.send_button.setStyleSheet(f"font-size: {int(new_button_height * 0.5)}px; padding-bottom: 4px;")


    def _connect_view_model(self):
        """Connect signals from ViewModel to UI slots."""
        self.logger.info("Connecting ViewModel signals to ChatPanel slots...")
        self._view_model.history_updated.connect(self._handle_history_update)
        self._view_model.error_occurred.connect(self._handle_error)
        self._view_model.busy_changed.connect(self._handle_busy_changed)
        # self._view_model.context_changed.connect(self._handle_context_mode_change_ui) # OLD
        # self._view_model.context_changed.connect(self._handle_current_news_change_ui) # OLD
        # Connect new, specific signals
        self._view_model.context_mode_changed.connect(self._handle_context_mode_change_ui)
        self._view_model.context_news_changed.connect(self._handle_current_news_change_ui)
        self._view_model.new_message_added.connect(self._on_new_message_added)

        # Connect to the new signal for updating the label - Keep this connection, triggered by mode change
        # self._view_model.context_changed.connect(self._update_selected_news_label) # OLD
        self._view_model.context_mode_changed.connect(self._update_selected_news_label)
        self._view_model.context_news_changed.connect(self._update_selected_news_label)

        self.logger.info("ViewModel signals connected successfully.")

    @pyqtSlot(list)
    def _handle_history_update(self, history: list):
        """处理来自 ViewModel 的聊天记录更新信号"""
        self.logger.info(f"_handle_history_update called with {len(history)} messages.")
        # 移除旧的 Typing Indicator (以防万一在添加新内容之前它还在)
        self._remove_typing_indicator()
        
        # 清空现有布局
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # 重新填充
        for message in history:
            if isinstance(message, ChatMessage):
                self.logger.debug(f"Adding message bubble for Role: {message.role}, Content: {message.content[:50]}...")
                self._add_message(message.content, message.role == 'user')
            else:
                self.logger.warning(f"_handle_history_update received non-ChatMessage object: {type(message)}")

        # 在所有消息添加完毕后，检查是否应该重新显示 Typing Indicator
        if self._view_model.is_busy:
            self.logger.debug("Busy state is true after history update, adding typing indicator.")
            self._add_typing_indicator()

        # 滚动到底部
        # 使用 QTimer 延迟滚动，确保布局更新完成
        QTimer.singleShot(250, self._scroll_to_bottom) # Reverted to simple scroll bottom

    @pyqtSlot(str)
    def _handle_error(self, error_msg: str):
        """处理来自 ViewModel 的错误信息 - 显示通用消息"""
        self.logger.error(f"Received error signal. Raw msg (first 100 chars): {error_msg[:100]}...")
        # Display a generic user-friendly message instead of raw error
        friendly_error_html = """
        <div style='font-family: "Microsoft YaHei", "Segoe UI", sans-serif; color: #D32F2F; padding: 10px; background-color: #FFEBEE; border-radius: 8px; border-left: 4px solid #D32F2F; margin: 10px 0;'>
            <strong>请求处理失败</strong>
            <p style='margin-top: 5px; margin-bottom: 0;'>请检查网络连接或稍后重试。</p>
        </div>
        """
        self._add_message(friendly_error_html, is_user=False)
        QTimer.singleShot(50, self._scroll_to_bottom) # Scroll to show error
        # Reset busy state might be needed if error comes from stream callback
        self._view_model._set_busy(False) # Ensure busy is false on error

    @pyqtSlot(bool)
    def _handle_busy_changed(self, is_busy: bool):
        """Update UI based on busy state (show/hide stop button, indicator)."""
        self.logger.debug(f"_handle_busy_changed: is_busy={is_busy}") # ADDED LOGGING
        if is_busy:
            self.send_button.hide()
            self.stop_button.show()
            self._add_typing_indicator()
        else:
            self.stop_button.hide()
            self.send_button.show()
            self._remove_typing_indicator()

    def _add_typing_indicator(self):
        """Adds a visual indicator that the assistant is processing."""
        if not self.typing_indicator:
            self.typing_indicator = QLabel("思考中...")
            self.typing_indicator.setObjectName("TypingIndicator")
            # Basic styling, enhance with QSS
            self.typing_indicator.setStyleSheet("""
                QLabel#TypingIndicator {
                    font-style: italic;
                    color: #666;
                    padding: 10px;
                    background-color: #f0f0f0; /* Light grey background */
                    border-radius: 10px;
                    border: 1px solid #e0e0e0;
                    max-width: 150px; /* Limit width */
                    margin-bottom: 5px;
                    margin-left: 15px; /* Align left like assistant bubble */
                }
            """)
            self.typing_indicator.setFixedHeight(self.typing_indicator.sizeHint().height() + 5)

            # Add to a layout to control alignment
            indicator_layout = QHBoxLayout()
            indicator_layout.setContentsMargins(0, 0, 0, 0)
            indicator_layout.addWidget(self.typing_indicator)
            indicator_layout.addStretch()
            self.chat_layout.addLayout(indicator_layout)
            # Ensure the indicator is visible using ensureWidgetVisible
            QTimer.singleShot(50, lambda: self.chat_area.ensureWidgetVisible(self.typing_indicator) if self.typing_indicator else None) # Keep this for indicator

    def _remove_typing_indicator(self):
        """Removes the typing indicator if it exists."""
        if self.typing_indicator:
            # Find the layout containing the indicator
            for i in range(self.chat_layout.count()):
                item = self.chat_layout.itemAt(i)
                if isinstance(item, QHBoxLayout) and item.itemAt(0).widget() == self.typing_indicator:
                    # Remove widgets within the layout
                    while item.count():
                        sub_item = item.takeAt(0)
                        widget = sub_item.widget()
                        if widget:
                            widget.deleteLater()
                    # Remove the layout itself
                    self.chat_layout.takeAt(i)
                    item.deleteLater()
                    break
            self.typing_indicator = None

    def _scroll_to_bottom(self):
        """Scrolls the chat area to the absolute bottom."""
        # self.logger.warning("_scroll_to_bottom called, but _scroll_to_last_bubble is preferred.")
        scrollbar = self.chat_area.verticalScrollBar()
        # Give a tiny delay for layout to potentially settle before scrolling
        QTimer.singleShot(10, lambda: scrollbar.setValue(scrollbar.maximum()))

    def _scroll_to_bottom_on_range_change(self, min_val, max_val):
        """Slot to scroll to bottom when scrollbar range changes (content added)."""
        # Only scroll if the user hasn't scrolled up significantly
        scrollbar = self.chat_area.verticalScrollBar()
        if scrollbar.value() >= scrollbar.maximum() - (scrollbar.pageStep() * 1.5):
             QTimer.singleShot(0, lambda: scrollbar.setValue(scrollbar.maximum()))
        # self.logger.debug(f"Scroll range changed: {min_val}-{max_val}. Current value: {scrollbar.value()}, PageStep: {scrollbar.pageStep()}")
        # scrollbar.setValue(scrollbar.maximum())

    @pyqtSlot(bool)
    def _handle_context_mode_change_ui(self, is_context_mode: bool):
        """Handles context mode changes from ViewModel."""
        self.logger.debug(f"ChatPanel._handle_context_mode_change_ui called with: {is_context_mode}")
        self.context_checkbox.setChecked(is_context_mode)
        self._update_selected_news_label() # Update label visibility/content

    @pyqtSlot(NewsArticle)
    def _handle_current_news_change_ui(self, news_article: Optional[NewsArticle]):
        """Handles current news changes from ViewModel."""
        self.logger.debug(f"ChatPanel._handle_current_news_change_ui called with article: {news_article.title if news_article else 'None'}")
        if self._view_model.use_news_context:
            if news_article:
                title_short = (news_article.title[:50] + '...') if len(news_article.title) > 50 else news_article.title
                self.selected_news_label.setText(f"上下文新闻: {title_short}")
                self.selected_news_label.setToolTip(f"当前聊天将使用以下新闻作为上下文：\n标题：{news_article.title}\n链接：{news_article.link}")
            else:
                self.selected_news_label.setText("上下文模式已启用，请在左侧选择新闻")
                self.selected_news_label.setToolTip("")
        else:
            self.selected_news_label.hide()
            self.selected_news_label.setToolTip("")

    @pyqtSlot() # Make it a slot to connect to the signal
    def _update_selected_news_label(self):
        """Update the label showing the currently selected news article."""
        if self._view_model.use_news_context:
            self.selected_news_label.show()
            news = self._view_model.current_news
            if news:
                # Ensure title is truncated if too long
                title = news.title
                max_len = 80 # Max characters for the title
                truncated_title = (title[:max_len] + '...') if len(title) > max_len else title
                self.selected_news_label.setText(f"上下文新闻: {truncated_title}")
                self.selected_news_label.setToolTip(f"当前聊天将使用以下新闻作为上下文：\n标题：{news.title}\n链接：{news.link}")
            else:
                self.selected_news_label.setText("上下文模式已启用，请在左侧选择新闻")
                self.selected_news_label.setToolTip("")
        else:
            self.selected_news_label.hide()
            self.selected_news_label.setToolTip("")

    @pyqtSlot(ChatMessage)
    def _on_new_message_added(self, message: ChatMessage):
        self.logger.info(f">>> SLOT _on_new_message_added RECEIVED signal for role: {message.role}. Content: '{message.content[:50]}...' <<<")

        if message.role == "user":
            self.logger.info(f"---> Calling _add_message for new user message.")
            self._add_message(message.content, is_user=True) 
            # self.current_assistant_bubble is set to None by _add_message when is_user is True
        
        elif message.role == "assistant":
            # Check ViewModel's _assistant_message_added flag to see if a stream is active
            is_continuing_stream = self.current_assistant_bubble is not None and \
                                 hasattr(self._view_model, '_assistant_message_added') and \
                                 self._view_model._assistant_message_added
            
            if is_continuing_stream:
                self.logger.info(f"---> Updating existing assistant bubble. Content: '{message.content[:50]}...'")
                self.current_assistant_bubble.setHtml(message.content)
                self._scroll_to_bottom() 
            else:
                # This is a new assistant message (either first chunk of a stream, or a non-streamed full message)
                self.logger.info(f"---> Calling _add_message for NEW assistant message.")
                self._add_message(message.content, is_user=False) # This will set self.current_assistant_bubble via _add_message

        # If the ViewModel signals that the assistant is no longer adding to a message (stream ended/errored),
        # clear our reference to the bubble so the next assistant message starts fresh.
        # This check should be safe even if _assistant_message_added doesn't exist on VM for some reason.
        if message.role == "assistant" and \
           hasattr(self._view_model, '_assistant_message_added') and \
           not self._view_model._assistant_message_added:
            self.logger.info("ViewModel indicates assistant message stream ended. Clearing current_assistant_bubble.")
            self.current_assistant_bubble = None

# Example Usage (if run standalone for testing)
# if __name__ == '__main__':
#     import sys
#     from PySide6.QtWidgets import QApplication
#     from src.core.app_service import AppService # Dummy AppService for testing
#     # Need dummy implementations or mocks for dependencies
#     from src.storage import NewsStorage
#     from src.llm.llm_service import LLMService
#     from src.llm.prompt_manager import PromptManager

#     logging.basicConfig(level=logging.DEBUG)

#     app = QApplication(sys.argv)

#     # Create dummy dependencies
#     # storage = NewsStorage('./data') # Adjust path
#     # prompt_manager = PromptManager('./src/prompts') # Adjust path
#     # llm_service = LLMService(api_key="DUMMY", base_url="DUMMY", model="DUMMY", prompt_manager=prompt_manager)
#     # app_service = AppService(storage=storage, llm_service=llm_service) # Add other required args
#     # view_model = ChatPanelViewModel(app_service)

#     # panel = ChatPanel(view_model)
#     # panel.show()

#     # # Simulate receiving data
#     # dummy_news = NewsArticle(link="http://example.com", title="Dummy News", content="Content...", source="TestSource", category="测试", publish_time=None)
#     # view_model.handle_current_news_change(dummy_news)
#     # view_model.handle_context_mode_change(True)
#     # view_model.handle_chat_history_update([
#     #     ChatMessage(role='user', content='Hello'),
#     #     ChatMessage(role='assistant', content='Hi there! How can I help?')
#     # ])

#     sys.exit(app.exec()) 