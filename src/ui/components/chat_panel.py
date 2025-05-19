from src.ui.components.message_bubble import MessageBubble # Import the custom bubble widget

class ChatPanel(QWidget):
    """聊天面板 UI"""
    @pyqtSlot(str)
    def _handle_error(self, error_msg: str):
        """处理错误信息，显示在聊天区域"""
        self.logger.error(f"Displaying error message: {error_msg}")
        # Simplify error display to avoid complex HTML rendering issues
        plain_error_text = f"错误： {error_msg}"
        self._add_message(plain_error_text, is_user=False)

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
        """添加"思考中..."指示器"""
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
        """移除"思考中..."指示器"""
        if self.typing_indicator:
            self.logger.debug("Removing typing indicator...")
            self.typing_indicator.deleteLater() # Schedule deletion
            self.typing_indicator = None # Reset reference
        else:
             self.logger.debug("Attempted to remove typing indicator, but it was already None.")

    def _scroll_to_bottom(self):
        """滚动到聊天区域底部"""
        scroll_bar = self.chat_scroll_area.verticalScrollBar()
        if scroll_bar:
            scroll_bar.setValue(scroll_bar.maximum())

    def _add_message(self, content: str, is_user: bool):
        """向聊天布局中添加消息气泡 (重构后)"""
        # Remove the initial stretch item if it exists
        if self.chat_layout.count() > 0 and isinstance(self.chat_layout.itemAt(self.chat_layout.count() - 1), QSpacerItem):
             item = self.chat_layout.takeAt(self.chat_layout.count() - 1)
             del item

        bubble = MessageBubble(content, is_user)
        bubble.setProperty("is_user", "true" if is_user else "false") # For QSS styling

        # Use QHBoxLayout to control alignment within the chat_layout row
        row_layout = QHBoxLayout()
        if is_user:
            row_layout.addStretch(1) # Push bubble to the right
            row_layout.addWidget(bubble)
        else:
            row_layout.addWidget(bubble)
            row_layout.addStretch(1) # Push bubble to the left

        # Add the row layout to the main chat layout
        self.chat_layout.addLayout(row_layout)

        # Add the stretch back at the end
        self.chat_layout.addStretch(1)

        # Schedule scroll to bottom
        QTimer.singleShot(10, self._scroll_to_bottom)

    # --- SLOTS --- # (Ensure this section exists)
    @pyqtSlot(list) # Receive List[ChatMessage]
    def _handle_history_update(self, messages: List[ChatMessage]):

    @pyqtSlot(bool) 

    def _add_message(self, content: str, is_user: bool):
        # --- Updated _add_message --- Add this comment if not present
        pass 

    def setText(self, text):
        self.label.setText(text)
        self.updateGeometry() # Hint layout system about size change

    def minimumSizeHint(self):
        # --- Simplify Size Hint --- Modified
        # return self.layout.minimumSize()
        hint = self.layout.sizeHint()
        # Add a minimum width to prevent tiny bubbles
        min_width = 100
        return QSize(max(min_width, hint.width()), hint.height())

    def sizeHint(self):
        # --- Simplify Size Hint --- Modified
        # Calculate hint based on label's wrapped size
        # ... (previous complex calculation removed) ...
        # Rely on the layout's calculation, but ensure minimum width
        hint = self.layout.sizeHint()
        min_width = 100
        return QSize(max(min_width, hint.width()), hint.height()) 

    def __init__(self, viewmodel: ChatPanelViewModel, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.viewmodel = viewmodel
        self.typing_indicator: Optional[QLabel] = None # Initialize typing indicator reference

        self._init_ui()
        self._setup_styles() # <-- Add call to setup styles
        self._connect_signals()
        self._connect_viewmodel()
        self.logger.info("ChatPanel initialized.")

    def _init_ui(self):
        self.input_layout = QHBoxLayout() # Horizontal layout for input + button
        self.message_input = QTextEdit() # Using QTextEdit
        self.message_input.setPlaceholderText("输入消息，按Enter发送...")
        self.message_input.setObjectName("messageInput")
        # --- Set Fixed Height for Input --- Modified
        # self.message_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        font_metrics = self.message_input.fontMetrics()
        line_height = font_metrics.height()
        margins = self.message_input.contentsMargins()
        # Calculate height for approx 2 lines + vertical margins
        fixed_height = (line_height * 2) + margins.top() + margins.bottom() + 5 # Add some padding
        self.message_input.setFixedHeight(fixed_height)
        self.message_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed) # Expand width, Fixed height

        self.send_button = QPushButton("发送")
        self.send_button.setIcon(QIcon(":/icons/send")) # Assuming icon is in resources

        self.stop_button = QPushButton("停止")
        self.stop_button.setIcon(QIcon(":/icons/stop")) # Assuming icon is in resources

        self.input_layout.addWidget(self.message_input)
        self.input_layout.addWidget(self.send_button)
        self.input_layout.addWidget(self.stop_button)

        self.layout.addLayout(self.input_layout)

        self.chat_layout = QVBoxLayout()
        self.chat_scroll_area = QScrollArea()
        self.chat_scroll_area.setWidgetResizable(True)
        self.chat_scroll_area.setObjectName("chatScrollArea")

        self.chat_layout.addStretch(1)
        self.chat_scroll_area.setWidget(QWidget(self))
        self.chat_scroll_area.widget().setLayout(self.chat_layout)

        self.layout.addWidget(self.chat_scroll_area)

        self.setLayout(self.layout)

        self.layout.addStretch(1)

        self.layout.setSizeConstraint(QLayout.SetMinAndMaxSize) 

    @pyqtSlot(ChatMessage)
    def _handle_new_message(self, message: ChatMessage):
        """处理从 ViewModel 收到的新消息"""
        self.logger.info(f"[SLOT] _handle_new_message received: Role={message.role}, Content='{message.content[:50]}...'" ) # <-- Add logging
        # self.logger.debug(f"Received new message: Role={message.role}, Content='{message.content[:50]}...'")
        self._add_message(message.content, message.role == 'user')

    @pyqtSlot(str)
    def _handle_new_message(self, content: str):
        # This method is not defined in the original file or the new implementation
        # It's assumed to exist as it's called in the _handle_new_message slot
        pass 