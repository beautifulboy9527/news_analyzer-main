"""聊天面板

提供与大语言模型交互的聊天界面。
支持独立聊天和新闻上下文聊天模式。 (非流式，但有等待提示)
"""

import logging
from typing import List, Optional # 导入 List 和 Optional

import re # 添加 re 模块导入
import math
# import threading # 不再需要
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
                             QScrollArea, QLabel, QTextBrowser, QFrame, QSizePolicy,
                             QCheckBox, QApplication, QSpacerItem, QStyle) # QSizePolicy, QStyle is already imported
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize, pyqtSlot, QEvent # Removed unused imports
from PyQt5.QtGui import QIcon, QKeyEvent, QFontMetrics # Removed unused imports, Added QFontMetrics

from PyQt5.QtGui import QTextOption # Import QTextOption
# LLMService is now accessed via ViewModel
# from src.llm.llm_service import LLMService
from src.models import NewsArticle, ChatMessage # Use absolute import from src
from .ui_utils import create_standard_button, create_title_label # <-- 添加 create_title_label
from .viewmodels.chat_panel_viewmodel import ChatPanelViewModel # Import the ViewModel


class ChatPanel(QWidget):
    """聊天面板组件"""
    message_sent = pyqtSignal(str) # Keep if external components need to know about user messages

    def __init__(self, view_model: ChatPanelViewModel, parent=None): # 参数改回 ViewModel
        super().__init__(parent)
        self.setObjectName("ChatPanel") # Add objectName for QSS targeting
        self.logger = logging.getLogger('news_analyzer.ui.chat_panel')
        self._view_model = view_model # 使用 ViewModel
        self.typing_indicator = None # Will hold the indicator label (QLabel)
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
        self._adjust_input_height() # Call initial adjustment


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
        pass

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
        self._view_model.send_message(user_message) # ViewModel handles busy state and history update

    def _add_message(self, text, is_user=False):
        """向聊天区域添加消息气泡 (使用QTextBrowser确保正确高度计算)"""
        self.logger.debug(f"_add_message called: is_user={is_user}, text='{str(text)[:100]}...'")
        if not isinstance(text, str):
            text = str(text)

        # Remove old typing indicator before adding new message
        self._remove_typing_indicator()

        # 中文换行处理 (每20个字符插入<br>)
        processed_text = []
        for line in text.split('\n'):
            for i in range(0, len(line), 20):  # Adjusted to 20 characters per line
                processed_text.append(line[i:i+20])
            processed_text.append('<br>')
        processed_text = '<br>'.join(processed_text[:-1])

        # --- Create QTextBrowser for the message ---
        bubble = QTextBrowser()
        bubble.setFrameShape(QTextBrowser.NoFrame)
        bubble.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        bubble.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        bubble.setOpenLinks(True)
        bubble.setOpenExternalLinks(True)
        bubble.setObjectName("UserMessageBubble" if is_user else "AssistantMessageBubble")
        bubble.setProperty("is_user", str(is_user).lower())
        
        # 设置样式和文本
        bubble.setStyleSheet("""
            QTextBrowser {
                background-color: #f0f0f0;
                border-radius: 15px;
                padding: 10px 15px;
                margin: 5px 0;
            }
            QTextBrowser[is_user="true"] {
                background-color: #e3f2fd;
            }
        """)
        
        bubble.setHtml(f"<div style='font-family: Microsoft YaHei;'>{processed_text}</div>")
        bubble.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        bubble.document().adjustSize()
        
        # --- Create Container Widget ---
        bubble_container = QWidget()
        layout = QHBoxLayout(bubble_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(bubble)
        
        # 设置容器最小高度为文本高度+边距
        text_height = bubble.document().size().height()
        bubble_container.setMinimumHeight(int(text_height) + 20)
        
        # --- Add to Main Layout ---
        alignment = Qt.AlignRight if is_user else Qt.AlignLeft
        self.chat_layout.addWidget(bubble_container, 0, alignment)
        
        QTimer.singleShot(10, self._scroll_to_bottom)
        self.logger.info("Message bubble added with accurate height calculation.")

    def _clear_chat(self):
        """清空聊天记录和界面"""
        self.logger.info("Clearing chat UI...")
        # Clear UI elements
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            layout = item.layout() # Check if the item itself is a layout
            if widget:
                # Check if it's the typing indicator before deleting
                if widget != self.typing_indicator: # Check if it's the indicator label
                    widget.deleteLater()
            elif layout:
                 # Properly delete items within the nested layout first
                 while layout.count():
                     inner_item = layout.takeAt(0)
                     inner_widget = inner_item.widget()
                     inner_layout = inner_item.layout() # Check for layouts within layouts
                     if inner_widget:
                         inner_widget.deleteLater()
                     elif inner_layout:
                         # Handle nested layouts if necessary (recursive deletion might be safer)
                         pass # For this specific case, likely only widgets or spacers
                     elif inner_item.spacerItem():
                         pass # Spacers are managed by the layout
                 layout.deleteLater() # Delete the QHBoxLayout itself

        # Reset indicator references
        self._remove_typing_indicator() # Ensure indicator label is removed

        # Tell ViewModel to clear history and reset state
        self._view_model.clear_chat_history()
        self._view_model.reset_state() # Ensure busy is false, etc.

        self.logger.info("Chat cleared.")


    def _adjust_input_height(self):
        """根据内容动态调整输入框高度"""
        document = self.message_input.document()
        doc_height = document.size().height()

        # Consider margins and frame width
        margins = self.message_input.contentsMargins()
        frame_width = self.message_input.frameWidth()

        buffer = 5
        content_height = doc_height + margins.top() + margins.bottom() + (frame_width * 2) + buffer

        font_metrics = self.message_input.fontMetrics()
        line_height = font_metrics.height()

        frame_margins = self.message_input.parent().layout().contentsMargins()
        padding = frame_margins.top() + frame_margins.bottom()

        min_h = line_height + padding + buffer
        max_h = (line_height * 10) + padding + buffer  # 增加到10行最大高度

        final_height = max(min_h, min(content_height, max_h))

        current_height = self.message_input.height()
        if abs(current_height - final_height) > 2:
            self.message_input.setFixedHeight(int(final_height))
            # 统一按钮大小设置
            btn_size = min(int(final_height * 1.2), 50)  # 限制最大50px
            self.button_size = QSize(btn_size, btn_size)
            self.stop_button.setFixedSize(self.button_size)
            self.send_button.setFixedSize(self.button_size)
            # 精确设置图标大小
            icon_size = QSize(btn_size - 10, btn_size - 10)
            self.stop_button.setIconSize(icon_size)
            self.send_button.setIconSize(icon_size)
            self.send_button.setStyleSheet(f"""
                font-size: {icon_size.height()}px;
                padding: 0;
                margin: 0;
                qproperty-iconSize: {icon_size.width()}px;
            """)


    def _connect_view_model(self):
        """连接ViewModel的信号到此面板的槽"""
        self.logger.info("Connecting ViewModel signals to ChatPanel slots...")
        try:
            self._view_model.history_updated.connect(self._handle_history_update)
            self._view_model.error_occurred.connect(self._handle_error)
            self._view_model.busy_changed.connect(self._handle_busy_changed)
            self._view_model.context_changed.connect(self._update_selected_news_label) # Connect context change signal
            self.logger.info("ViewModel signals connected successfully.")
        except Exception as e:
            self.logger.exception(f"Error connecting ViewModel signals: {e}")


    @pyqtSlot(list)
    def _handle_history_update(self, history: list):
        """处理来自ViewModel的历史记录更新 (清空重绘逻辑)"""
        self.logger.info(f"Handling history update. History length: {len(history)}")
        # Clear existing messages (excluding indicator if present)
        while self.chat_layout.count():
            item = self.chat_layout.itemAt(0)
            widget = item.widget()
            # Check if it's the typing indicator widget before removing
            if widget == self.typing_indicator: # Check if it's the indicator label
                 if self.chat_layout.count() > 1:
                     item_to_remove = self.chat_layout.itemAt(1) # Remove the one after indicator
                 else:
                     break # Only indicator left
            else:
                 item_to_remove = self.chat_layout.itemAt(0) # Remove the first item

            widget_to_delete = item_to_remove.widget()
            layout_to_delete = item_to_remove.layout() # Check if the item itself is a layout

            if widget_to_delete:
                widget_to_delete.deleteLater()
                self.chat_layout.removeItem(item_to_remove)
            elif layout_to_delete:
                 # Properly delete items within the nested layout first
                 while layout_to_delete.count():
                     inner_item = layout_to_delete.takeAt(0)
                     inner_widget = inner_item.widget()
                     inner_layout = inner_item.layout()
                     if inner_widget:
                         inner_widget.deleteLater()
                     elif inner_layout:
                         pass # Handle nested layouts if needed
                     elif inner_item.spacerItem():
                         pass # Spacers are managed by the layout
                 layout_to_delete.deleteLater() # Delete the QHBoxLayout itself
                 self.chat_layout.removeItem(item_to_remove) # Remove item from layout
            else:
                 # If it's neither widget nor layout (e.g., spacer directly in chat_layout), remove it
                 self.chat_layout.removeItem(item_to_remove)


        # Add messages from history
        if history:
            for msg in history:
                # Ensure content is string, handle potential None or other types
                self.logger.debug(f"Processing message {history.index(msg)}: Role={msg.role}, Content='{str(msg.content)[:50]}...' ({type(msg)}) ")
                content = str(msg.content) if msg.content is not None else ""
                self._add_message(content, msg.role == 'user') # 这是正确的调用方式

        # Re-add indicator if it should be visible (based on busy state)
        if self._view_model.is_busy and not self.typing_indicator: # Check indicator label directly
             self._add_typing_indicator()
        elif not self._view_model.is_busy:
             self._remove_typing_indicator() # Ensure it's removed if not busy

        QTimer.singleShot(0, self._scroll_to_bottom) # Ensure scroll after update
        self.logger.debug("Chat history UI updated.")


    @pyqtSlot(str)
    def _handle_error(self, error_msg: str):
        """处理错误信息，显示在聊天区域"""
        self.logger.error(f"Displaying error message: {error_msg}")
        error_html = f"<div style='color: #F44336; font-weight: bold;'>错误：{error_msg}</div>"
        self._add_message(error_html, is_user=False)


    @pyqtSlot(bool)
    def _handle_busy_changed(self, is_busy: bool):
        """处理繁忙状态变化，显示/隐藏等待指示器和按钮"""
        self.logger.info(f"Busy state changed: {is_busy}")
        if is_busy:
            self._add_typing_indicator()
            self.send_button.hide()
            self.stop_button.show()
            self.message_input.setEnabled(False)
        else:
            self._remove_typing_indicator()
            self.stop_button.hide()
            self.send_button.show()
            self.message_input.setEnabled(True)
            self.message_input.setFocus() # Return focus to input


    def _add_typing_indicator(self):
        """添加“思考中...”指示器"""
        if self.typing_indicator: # Check if indicator label already exists
            return
        self.logger.debug("Adding typing indicator...")

        self.typing_indicator = QLabel("思考中...") # Use QLabel
        self.typing_indicator.setObjectName("typingIndicator") # QSS target
        self.typing_indicator.setProperty("is_user", "false") # Style as assistant message
        # --- Ensure size policy allows it to be visible ---
        self.typing_indicator.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.typing_indicator.adjustSize() # Calculate initial size
        self.logger.debug(f"Typing indicator initial sizeHint: {self.typing_indicator.sizeHint()}")

        # Add the indicator directly to the main layout, aligned left
        self.chat_layout.addWidget(self.typing_indicator, 0, Qt.AlignLeft)

        QTimer.singleShot(10, self._scroll_to_bottom) # Scroll down

    def _remove_typing_indicator(self):
        """移除“思考中...”指示器"""
        if self.typing_indicator:
            self.logger.debug("Removing typing indicator...")
            self.typing_indicator.deleteLater()
            self.typing_indicator = None # Reset reference
            self.logger.debug("Typing indicator removed.")


    def _scroll_to_bottom(self):
        """滚动聊天区域到底部"""
        # self.logger.debug("Scrolling to bottom...")
        scrollbar = self.chat_area.verticalScrollBar()
        # Only scroll if the user is already near the bottom
        is_at_bottom = scrollbar.value() >= (scrollbar.maximum() - scrollbar.pageStep())
        # self.logger.debug(f"Scroll check: value={scrollbar.value()}, max={scrollbar.maximum()}, pageStep={scrollbar.pageStep()}, is_at_bottom={is_at_bottom}")
        if is_at_bottom:
            scrollbar.setValue(scrollbar.maximum())
        # else:
            # self.logger.debug("User scrolled up, not auto-scrolling.")

    def _scroll_to_bottom_on_range_change(self, min_val, max_val):
        """Callback for scrollbar range change to auto-scroll"""
        # self.logger.debug(f"Scroll range changed: {min_val}-{max_val}. Scrolling to bottom.")
        # Check if scrollbar is near the bottom before auto-scrolling on range change too
        scrollbar = self.chat_area.verticalScrollBar()
        # A small tolerance might be needed here as well
        if scrollbar.value() >= (min_val + (max_val - min_val) * 0.9): # Example: if scrolled down 90%
             scrollbar.setValue(max_val)


    # --- UI Update Slots Connected to ViewModel ---

    @pyqtSlot(bool)
    def _handle_context_mode_change_ui(self, is_context_mode: bool):
        """更新UI以反映上下文模式的变化"""
        self.logger.debug(f"Updating UI for context mode change: {is_context_mode}")
        self.context_checkbox.setChecked(is_context_mode)
        self._update_selected_news_label() # Update label based on new mode and current news

    @pyqtSlot(NewsArticle)
    def _handle_current_news_change_ui(self, news_article: Optional[NewsArticle]):
        """更新UI以反映当前新闻的变化"""
        self.logger.debug(f"Updating UI for current news change: {news_article.title if news_article else 'None'}")
        self._update_selected_news_label()

    @pyqtSlot() # Make it a slot to connect to the signal
    def _update_selected_news_label(self):
        """根据ViewModel的状态更新显示选定新闻的标签"""
        self.logger.debug("Updating selected news label based on ViewModel state...")
        current_news = self._view_model.current_news
        is_context_mode = self._view_model.use_news_context

        if is_context_mode and current_news:
            title = current_news.title if current_news.title else '无标题'
            display_text = f"上下文: {title[:30]}..."
            self.selected_news_label.setText(display_text)
            self.selected_news_label.setToolTip(f"当前聊天上下文基于新闻：\n{title}")
            self.selected_news_label.setVisible(True)
            self.logger.debug(f"Label set to: '{display_text}' (Visible)")
        elif is_context_mode and not current_news:
            self.selected_news_label.setText("上下文模式已启用，请选择新闻")
            self.selected_news_label.setToolTip("请从左侧新闻列表中选择一项以用于聊天上下文。")
            self.selected_news_label.setVisible(True)
            self.logger.debug("Label set to: '上下文模式已启用，请选择新闻' (Visible)")
        else: # Context mode disabled
            self.selected_news_label.setText("未启用新闻上下文") # Or simply hide it
            self.selected_news_label.setToolTip("")
            self.selected_news_label.setVisible(False) # Hide label when context is off
            self.logger.debug("Label hidden (Context mode disabled)")

        self.update() # Request repaint
