import logging
import threading
import time # 导入 time 模块
from typing import List, Optional, Dict, Any, Callable # 确保导入 Callable
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer # 导入 QTimer
from datetime import datetime # 导入 datetime

# 导入模型和核心服务
from src.models import NewsArticle, ChatMessage # 导入 ChatMessage
from src.core.app_service import AppService # 确保 AppService 被导入
from src.llm.llm_service import LLMService # 导入 LLMService
from src.llm.formatter import LLMResponseFormatter # 修正导入路径

class ChatPanelViewModel(QObject):
    """
    聊天面板的 ViewModel。

    管理聊天历史、与 LLMService 交互、处理上下文，并通知视图更新。
    """

    # --- 信号 ---
    history_updated = pyqtSignal(list) # 发射 List[ChatMessage]
    error_occurred = pyqtSignal(str) # 发射格式化后的 HTML 错误信息
    busy_changed = pyqtSignal(bool) # 发射忙碌状态
    context_changed = pyqtSignal() # NEW: Signal when news or category context changes

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

        self._connect_signals()
        self.logger.info("ChatPanelViewModel initialized.")

    def _connect_signals(self):
        """连接必要的信号"""
        self._app_service.selected_news_changed.connect(self.set_current_news)

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
        self.logger.debug(f"ViewModel: Setting current news context to: {news_article.title if news_article else 'None'}")
        self._current_news = news_article
        self.context_changed.emit() # NEW: Emit context change signal

    @pyqtSlot(str)
    def set_current_category(self, category: str):
        """设置当前用于上下文的新闻分类"""
        self.logger.debug(f"ViewModel: Setting current category context to: {category}")
        self._current_category = category
        self.context_changed.emit() # NEW: Emit context change signal

    @pyqtSlot(bool)
    def set_use_news_context(self, use_context: bool):
        """设置是否使用新闻上下文"""
        self.logger.debug(f"ViewModel: Setting use_news_context to: {use_context}")
        self._use_news_context = use_context

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

    # --- 新增：用于 QTimer 回调的方法 ---
    @pyqtSlot()
    def _emit_history_update_slot(self):
        self.logger.info("Slot _emit_history_update_slot executing...")
        self.history_updated.emit(self._chat_history[:])

    @pyqtSlot()
    def _set_busy_false_slot(self):
        self.logger.info("Slot _set_busy_false_slot executing...")
        self._set_busy(False)

    @pyqtSlot(str)
    def _emit_error_occurred_slot(self, error_html: str):
        self.logger.info("Slot _emit_error_occurred_slot executing...")
        self.error_occurred.emit(error_html)
    # --- 回调方法结束 ---

    @pyqtSlot(str)
    def send_message(self, user_message: str):
        if self._is_busy or not user_message.strip():
            return

        self._set_busy(True)

        user_chat_message = ChatMessage(role="user", content=user_message)
        self._chat_history.append(user_chat_message)
        # **立即发射信号，只包含用户消息**
        self.logger.debug("Emitting history_updated signal with user message...")
        # 使用 QTimer 调用槽函数
        QTimer.singleShot(0, self._emit_history_update_slot)
        self.logger.debug("QTimer for user history_updated requested.")

        messages_to_send = self._prepare_llm_messages(user_message)

        self.logger.info("Starting background thread for chat request...")

        def request_thread_target():
            self.logger.debug("Background thread started.")
            response_content = ""
            try:
                # --- 恢复实际 API 调用 ---
                self.logger.debug("Calling LLMService.chat (non-streaming) in background thread...")
                response_content = self._llm_service.chat(messages_to_send, "", False, None) # 获取完整响应
                self.logger.debug("LLMService.chat call returned.")
                # --- 修正日志变量名 ---
                self.logger.debug(f"LLMService.chat returned response (len={len(response_content)}): '{response_content[:200]}...'")


                if response_content and not response_content.startswith("<p style='color: red;'>"):
                    self.logger.info("Received valid non-streaming response.")
                    self.logger.debug("Appending assistant message to history...")
                    assistant_message = ChatMessage(role="assistant", content=response_content)
                    self._chat_history.append(assistant_message)
                    self.logger.debug("Assistant message appended.")
                    self.logger.debug("Requesting QTimer to call _emit_history_update_slot...")
                    QTimer.singleShot(0, self._emit_history_update_slot) # 调用槽函数
                    self.logger.debug("QTimer for history_updated requested.")
                else:
                    self.logger.error(f"Chat request failed or returned error/empty: {response_content}")
                    error_html = response_content if response_content else LLMResponseFormatter.format_error_html("模型未返回有效内容。")
                    self.logger.debug("Requesting QTimer to call _emit_error_occurred_slot...")
                    QTimer.singleShot(0, lambda err=error_html: self._emit_error_occurred_slot(err)) # 调用槽函数 (带参数需要 lambda)
                    self.logger.debug("QTimer for error_occurred requested.")

            except Exception as e:
                self.logger.error(f"Error in chat request thread: {e}", exc_info=True)
                error_html = LLMResponseFormatter.format_error_html(f"处理聊天请求时出错: {e}")
                self.logger.debug("Requesting QTimer to call _emit_error_occurred_slot due to exception...")
                QTimer.singleShot(0, lambda err=error_html: self._emit_error_occurred_slot(err)) # 调用槽函数 (带参数需要 lambda)
                self.logger.debug("QTimer for error_occurred (exception) requested.")
            finally:
                self.logger.debug("Requesting QTimer to call _set_busy_false_slot...")
                QTimer.singleShot(0, self._set_busy_false_slot) # 调用槽函数
                self.logger.debug("QTimer for set busy False requested.")
                self.logger.debug("Background thread finished.")


        thread = threading.Thread(target=request_thread_target)
        thread.daemon = True
        thread.start()

    @pyqtSlot()
    def stop_chat(self):
        self.logger.warning("Stop requested for non-streaming chat, which cannot be easily interrupted.")
        self._set_busy(False)
        pass

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
