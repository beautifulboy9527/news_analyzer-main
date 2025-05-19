# src/llm/llm_client_adapter.py
import logging
from typing import List, Dict, Optional, Union, Callable
import threading
from PyQt5.QtCore import QObject, pyqtSignal

from src.llm.llm_service import LLMService
from src.models import ChatMessage

logger = logging.getLogger(__name__)

class LLMClientAdapter:
    """
    适配器类，模仿旧 LLMClient 的接口，内部调用 LLMService。
    主要用于兼容旧版 ChatPanel。
    """
    def __init__(self, llm_service: LLMService):
        self._llm_service = llm_service
        # 旧 StreamHandler 的功能现在由 ViewModel/ChatWorker 处理，
        # 但旧 ChatPanel 依赖这个回调接口。我们需要模拟它。
        # 我们创建一个简单的 QObject 来发射信号，模拟 StreamHandler
        self._stream_emitter = QObject()
        # 定义一个与 StreamHandler.update_signal 兼容的信号
        # 注意：虽然我们强制非流式，但旧 ChatPanel 的 _update_message 槽需要这个信号
        self._stream_emitter.update_signal = pyqtSignal(str, bool)


    def chat(self, messages: List[Dict[str, str]], context: str = "", stream: bool = True, callback: Optional[Callable[[str, bool], None]] = None):
        """
        提供与旧 LLMClient.chat 兼容的接口。
        注意：这个适配器强制使用非流式，因为流式逻辑在新架构中导致问题。
        它会调用 LLMService 的非流式 chat，并在完成后通过 callback 返回完整结果。
        """
        logger.info("LLMClientAdapter.chat called (forcing non-streaming)")

        # 准备回调，用于在后台线程完成后发射信号
        def handle_response_for_adapter(response_content: str, done: bool):
            # 这个回调由 LLMService 在主线程通过 QTimer.singleShot 调用
            if done and callback:
                logger.debug(f"Adapter received final response (len: {len(response_content)}), calling original callback.")
                # 直接调用旧 ChatPanel 传入的 callback (即 stream_handler.handle_stream)
                # 这个 callback 会触发旧 ChatPanel 的 _update_message
                callback(response_content, True)

        # 调用 LLMService 的 chat 方法（它现在内部强制非流式）
        # LLMService 会在后台线程执行并最终在主线程调用 handle_response_for_adapter
        self._llm_service.chat(messages, context, stream=False, callback=handle_response_for_adapter)

        # 对于非流式，我们不返回线程句柄
        return None

    # 可以根据需要添加其他旧 LLMClient 可能有的方法作为空实现或适配实现
    # def get_available_models(self):
    #     logger.warning("LLMClientAdapter.get_available_models not implemented.")
    #     return []