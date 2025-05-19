import logging
import threading
import time # 导入 time 模块
from typing import List, Optional, Dict, Any, Callable # 确保导入 Callable
from PySide6.QtCore import QObject, Signal as pyqtSignal, Slot as pyqtSlot, QTimer, QRunnable, QThreadPool # Use PySide6, alias Signal/Slot, Add QRunnable, QThreadPool
# from PySide6.QtWidgets import QApplication # <-- CORRECT Import for QApplication <-- Remove this explicit import if needed elsewhere only
from datetime import datetime # 导入 datetime

# 导入模型和核心服务
from src.models import NewsArticle, ChatMessage # 导入 ChatMessage
from src.core.app_service import AppService # 确保 AppService 被导入
from src.llm.llm_service import LLMService # 导入 LLMService
from src.llm.formatter import LLMResponseFormatter # 修正导入路径

# --- Worker for running chat in background --- Added
class ChatWorker(QRunnable):
    def __init__(self, llm_service: LLMService, messages: list, parent_logger):
        super().__init__()
        self.llm_service = llm_service
        self.messages = messages
        self.logger = parent_logger # Use the ViewModel's logger

    @pyqtSlot()
    def run(self):
        self.logger.info("ChatWorker starting in background thread...")
        try:
            # Call chat without the callback, relying on signals now
            self.llm_service.chat(self.messages, stream=True) # Ensure streaming is True
            self.logger.info("ChatWorker finished llm_service.chat call.")
        except Exception as e:
            # Log error, signal emission will be handled by LLMService's error signal
            self.logger.error(f"Exception in ChatWorker run: {e}", exc_info=True)
            # Optionally emit an immediate error if LLMService doesn't guarantee it
            # error_html = LLMResponseFormatter.format_error_html(f"聊天工作线程出错: {e}")
            # Use QTimer to emit from main thread if needed, but rely on LLMService signal first.
            # QTimer.singleShot(0, lambda err=error_html: self.error_occurred.emit(err)) # Requires access to emit signal
# --- End Worker ---

class ChatPanelViewModel(QObject):
    """
    聊天面板的 ViewModel。

    管理聊天历史、与 LLMService 交互、处理上下文，并通知视图更新。
    """

    # --- 信号 ---
    history_updated = pyqtSignal(list) # 发射 List[ChatMessage] (用于清空等操作)
    new_message_added = pyqtSignal(ChatMessage) # <-- 新增信号，发射单个消息
    error_occurred = pyqtSignal(str) # 发射简单的错误文本
    busy_changed = pyqtSignal(bool) # 发射忙碌状态
    context_mode_changed = pyqtSignal(bool) # Signal for context mode checkbox state
    context_news_changed = pyqtSignal(NewsArticle) # Signal for the actual article change (allows None via Optional[NewsArticle] in slot)

    def __init__(self, app_service: AppService, llm_service: LLMService, parent: Optional[QObject] = None):
        """
        初始化 ChatPanelViewModel。

        Args:
            app_service (AppService): 应用程序核心服务实例。
            llm_service (LLMService): LLM 服务实例。
            parent (Optional[QObject]): 父对象，用于 Qt 对象树管理。
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self._app_service = app_service
        self._llm_service = llm_service
        self._chat_history: List[ChatMessage] = []
        self._current_news: Optional[NewsArticle] = None
        self._current_category: str = "所有"
        self._use_news_context: bool = False
        self._is_busy: bool = False
        self._assistant_message_added: bool = False # <-- Initialize the flag

        self._connect_signals()
        self.logger.info(f"--- ChatPanelViewModel Logger Test ({self.logger.name}) ---") 
        self.logger.info("ChatPanelViewModel initialized.")

    def _connect_signals(self):
        """连接必要的信号"""
        self._app_service.selected_news_changed.connect(self.set_current_news)
        # --- Connect LLMService chat signals --- Added
        self._llm_service.chat_chunk_received.connect(self._on_chat_chunk)
        self._llm_service.chat_finished.connect(self._on_chat_finish)
        self._llm_service.chat_error.connect(self._on_chat_error)
        self.logger.info("Connected to LLMService chat signals.")

    # --- 属性 ---
    @property
    def is_busy(self) -> bool:
        return self._is_busy

    @property
    def use_news_context(self) -> bool:
        """获取是否使用新闻上下文的状态"""
        return self._use_news_context


    @property
    def current_news(self) -> Optional[NewsArticle]:
        """获取当前用于上下文的新闻文章"""
        return self._current_news

    # --- 公共方法/槽 ---
    @pyqtSlot(NewsArticle)
    def set_current_news(self, news_article: Optional[NewsArticle]):
        """设置当前用于上下文的新闻文章"""
        if self._current_news is not news_article:
            self.logger.debug(f"ViewModel: Setting current news context to: {news_article.title if news_article else 'None'}")
            self._current_news = news_article
            self.context_news_changed.emit(self._current_news)

    @pyqtSlot(str)
    def set_current_category(self, category: str):
        """设置当前用于上下文的新闻分类"""
        self.logger.debug(f"ViewModel: Setting current category context to: {category}")
        self._current_category = category

    @pyqtSlot(bool)
    def set_use_news_context(self, use_context: bool):
        """设置是否使用新闻上下文"""
        if self._use_news_context != use_context:
            self.logger.debug(f"ViewModel: Setting use_news_context to: {use_context}")
            self._use_news_context = use_context
            self.context_mode_changed.emit(self._use_news_context)

    def _set_busy(self, busy: bool):
        """设置忙碌状态并发出信号"""
        self.logger.debug(f"Attempting to set busy state to {busy} (current: {self._is_busy})")
        if self._is_busy != busy:
            self._is_busy = busy
            self.logger.debug(f"Emitting busy_changed({busy}) signal...")
            self.busy_changed.emit(busy)
            self.logger.debug(f"busy_changed({busy}) signal emitted.")
        else:
            self.logger.debug(f"Busy state already {busy}, not emitting signal.")

    # --- Rewriting slot methods to ensure @pyqtSlot decorator is present ---
    @pyqtSlot()
    def _emit_history_update_slot(self):
        """Slot to emit history_updated signal via QTimer."""
        self.logger.info("Slot _emit_history_update_slot executing...")
        self.history_updated.emit(self._chat_history[:])

    @pyqtSlot()
    def _set_busy_false_slot(self):
        """Slot to set busy state to False via QTimer."""
        self.logger.info("Slot _set_busy_false_slot executing...")
        self._set_busy(False)

    @pyqtSlot(str)
    def _emit_error_occurred_slot(self, error_html: str):
        """Slot to emit error_occurred signal via QTimer."""
        self.logger.info("Slot _emit_error_occurred_slot executing...")
        self.error_occurred.emit(error_html)
    # --- End Rewriting Slots ---

    @pyqtSlot(str)
    def send_message(self, user_message: str):
        self.logger.info("--- send_message entered ---")
        if self._is_busy or not user_message.strip():
            return

        self._set_busy(True)

        user_chat_message = ChatMessage(role="user", content=user_message)
        self._chat_history.append(user_chat_message)
        # **立即发射信号，只包含用户消息**
        self.logger.debug("Requesting new_message_added signal emission via QTimer for user message...")
        # 使用 QTimer 调用新信号
        # --- REMOVE QTIMER --- 
        # def _emit_user_msg():
        #     self.logger.info(f"[QTIMER] Emitting new_message_added for user: {user_chat_message.content[:30]}...")
        #     self.new_message_added.emit(user_chat_message)
        # QTimer.singleShot(0, _emit_user_msg)
        # --- EMIT DIRECTLY --- 
        self.logger.info(f"Emitting new_message_added DIRECTLY for user: {user_chat_message.content[:30]}...")
        self.new_message_added.emit(user_chat_message)
        # Force UI update before potentially blocking call
        # QApplication.processEvents() # REMOVED - Threading handles unblocking
        # self.logger.debug("--- QApplication.processEvents() called after emitting user message ---")
        # Remove old timer for history_updated
        # QTimer.singleShot(0, self._emit_history_update_slot)

        messages_to_send = self._prepare_llm_messages(user_message)

        # --- Run LLM Call in Background Thread --- Modified
        self.logger.info("Submitting ChatWorker to QThreadPool...")
        worker = ChatWorker(self._llm_service, messages_to_send, self.logger)
        # No explicit callback needed here; signals from LLMService handle results
        QThreadPool.globalInstance().start(worker)
        self.logger.info("ChatWorker submitted.")
        # --- End Background Thread Execution ---

    def _prepare_llm_messages(self, user_message: str) -> list[dict]: # Return list of dicts
        system_prompt = "你是一个乐于助人的助手。" # Example system prompt
        context_prompt = ""

        if self._use_news_context:
            self.logger.debug("News context mode is ENABLED.")
            if self._current_news:
                title = self._current_news.title or "无标题"
                summary = self._current_news.summary or self._current_news.content or "无内容"
                context_prompt += f"\n当前讨论的新闻是 '{title}'.\n新闻摘要:\n{summary[:500]}..." # Limit context length
            elif self._current_category != "所有":
                self.logger.debug(f"Context mode enabled but no specific news selected, category is {self._current_category}")
            else:
                 self.logger.debug("Context mode enabled but no news or category selected.")
        else:
            self.logger.debug("News context mode is DISABLED.")
            context_prompt = ""

        prepared_messages = []
        system_content = (system_prompt + context_prompt).strip()
        if system_content:
            prepared_messages.append({'role': 'system', 'content': system_content}) # Use dict

        history_to_convert = self._chat_history[:-1] if self._chat_history else []
        processed_history = [{'role': msg.role, 'content': msg.content} for msg in history_to_convert if isinstance(msg, ChatMessage)]
        prepared_messages.extend(processed_history)

        current_user_msg_dict = {'role': 'user', 'content': user_message}
        prepared_messages.append(current_user_msg_dict)


        log_messages = [f"Role: {msg.get('role', 'unknown')}, Content: '{msg.get('content', '')[:100]}...'" for msg in prepared_messages]
        self.logger.debug(f"Prepared messages for LLM ({len(prepared_messages)} total):\n" + "\n".join(log_messages))

        return prepared_messages # Return list of dicts


    def get_history(self) -> list[ChatMessage]:
         """Returns a copy of the current chat history."""
         return self._chat_history[:]

    def reset_state(self):
        """重置 ViewModel 状态，例如在清空聊天时调用"""
        self.logger.debug("Resetting ChatPanelViewModel state.")
        self._set_busy(False)

    @pyqtSlot()
    def clear_chat_history(self):
        """清空聊天记录并通知视图更新"""
        self.logger.info("Clearing chat history...")
        self._chat_history.clear()
        self.logger.debug("Chat history cleared. Emitting history_updated signal with empty list.")
        self.history_updated.emit([]) # 发射空列表信号
        self.logger.info("Chat history cleared and signal emitted.")

    # --- New Slots for LLMService Signals --- Added
    @pyqtSlot(str)
    def _on_chat_chunk(self, chunk: str):
        """Handles receiving a chunk of the chat response. Now only marks stream as active."""
        if not self._assistant_message_added:
            self.logger.debug(f"First chunk received for a stream: {chunk[:50]}... Setting _assistant_message_added=True.")
            self._assistant_message_added = True
        # No accumulation or signal emission here. UI will update on _on_chat_finish.

    @pyqtSlot(str)
    def _on_chat_finish(self, final_message: str):
        """Handles the successful completion of the chat stream. Emits one new_message_added signal."""
        self.logger.info(f"_on_chat_finish received. Final raw message length: {len(final_message)}. Content snippet: '{final_message[:100]}...' ")

        if final_message: # Ensure there's content to process
            final_html_content = LLMResponseFormatter._format_content(final_message)
            self.logger.debug(f"_on_chat_finish: Final formatted HTML length: {len(final_html_content)}. Snippet: '{final_html_content[:150]}...'")

            assistant_message = ChatMessage(role="assistant", content=final_html_content)
            self._chat_history.append(assistant_message) # Add the complete message to history

            self.logger.info(f"---> Emitting new_message_added from _on_chat_finish for assistant message: {assistant_message.content[:50]}...")
            self.new_message_added.emit(assistant_message) # Emit signal for the UI
        else:
            self.logger.warning("_on_chat_finish: final_message is empty. Nothing to add or emit.")

        self._assistant_message_added = False # Reset flag, stream is finished
        self._set_busy(False) # Set busy to false

        # Reset temporary raw accumulation if it was used elsewhere (though not in this new _on_chat_chunk)
        if hasattr(self, '_raw_assistant_response'): # Should be _accumulated_raw_assistant_response if we were using it
            self.logger.debug("Clearing _raw_assistant_response attribute if it exists.")
            del self._raw_assistant_response
        if hasattr(self, '_accumulated_raw_assistant_response'): # Clear the one we might have defined
            self.logger.debug("Clearing _accumulated_raw_assistant_response attribute.")
            self._accumulated_raw_assistant_response = ""

    @pyqtSlot(str)
    def _on_chat_error(self, error_html: str):
        """Handles errors received from the chat stream."""
        self.logger.error(f"_on_chat_error received: {error_html[:100]}...")
        # Errors are already formatted as HTML by LLMService/Formatter
        self.error_occurred.emit(error_html) # Emit the error signal for the view
        self._assistant_message_added = False # Reset flag
        # Reset temporary raw accumulation if it exists
        if hasattr(self, '_raw_assistant_response'):
             del self._raw_assistant_response
        self._set_busy(False) # Set busy to false
    # --- End New Slots ---

    @pyqtSlot()
    def stop_chat(self):
        self.logger.warning("Stop requested for non-streaming chat, which cannot be easily interrupted.")
        self._set_busy(False)
        pass
