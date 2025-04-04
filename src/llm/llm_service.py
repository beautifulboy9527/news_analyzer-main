"""
LLM客户端 (重构为 LLMService)

协调 LLM 配置、Prompt 管理和 Provider 选择，提供核心 LLM 功能接口。
"""

import os
import json
import logging
import requests
import time
import threading
from typing import Callable, Dict, List, Optional, Union, Any # 确保 List 被导入
import dataclasses # Import dataclasses
import requests # <-- 新增导入 requests
 
# --- 导入内部模块 ---
from src.config.llm_config_manager import LLMConfigManager
from .prompt_manager import PromptManager
from .providers.base import LLMProviderInterface
from .providers.openai import OpenAIProvider
from .providers.anthropic import AnthropicProvider
from .providers.ollama import OllamaProvider
from .formatter import LLMResponseFormatter
from src.utils.api_client import ApiClient # <-- 新增导入
# Import ChatMessage for type checking during conversion
from src.models import ChatMessage


class LLMService:
    """
    LLM 服务类，协调配置、提示和 Provider 实现。
    """

    def __init__(self,
                 config_manager: LLMConfigManager,
                 prompt_manager: PromptManager,
                 api_client: ApiClient,
                 # 保留这些参数以允许直接覆盖配置，但优先使用 manager
                 override_api_key: Optional[str] = None,
                 override_api_url: Optional[str] = None,
                 override_model: Optional[str] = None,
                 override_temperature: Optional[float] = None,
                 override_max_tokens: Optional[int] = None,
                 override_timeout: Optional[int] = None,
                 override_provider_name: Optional[str] = None
                 ):
        """
        初始化 LLM 服务。
        使用注入的管理器和客户端，加载配置，选择并实例化合适的 Provider。
        """
        self.logger = logging.getLogger('news_analyzer.llm.service') # Renamed logger
        self.config_manager = config_manager
        self.prompt_manager = prompt_manager
        self.api_client = api_client
        self._cancel_requested = False # 添加停止标志
        self._current_stream_thread: threading.Thread | None = None # Track the stream thread

        # --- 确定配置来源 ---
        config_source = "override" if any([override_api_key, override_api_url, override_model]) else "manager"

        # --- 加载配置 ---
        loaded_api_key: Optional[str] = None
        loaded_api_url: Optional[str] = None
        loaded_model: Optional[str] = None
        loaded_temperature: Optional[float] = None
        loaded_max_tokens: Optional[int] = None
        loaded_timeout: Optional[int] = None
        active_name: Optional[str] = None

        if config_source == "manager":
            active_config = self.config_manager.get_active_config()
            if active_config:
                loaded_api_key = active_config.get('api_key')
                loaded_api_url = active_config.get('api_url')
                loaded_model = active_config.get('model')
                loaded_temperature = active_config.get('temperature', 0.7)
                loaded_max_tokens = active_config.get('max_tokens', 2048)
                loaded_timeout = active_config.get('timeout', 60)
                active_name = self.config_manager.get_active_config_name()
            else:
                 self.logger.warning("No active LLM configuration found via manager.")

        # --- 设置最终使用的配置值 (优先使用 override 参数) ---
        _api_key = override_api_key if override_api_key is not None else loaded_api_key
        _api_url = override_api_url if override_api_url is not None else loaded_api_url
        _model = override_model if override_model is not None else loaded_model
        _temperature = override_temperature if override_temperature is not None else (loaded_temperature if loaded_temperature is not None else 0.7)
        _max_tokens = override_max_tokens if override_max_tokens is not None else (loaded_max_tokens if loaded_max_tokens is not None else 2048)
        _timeout = override_timeout if override_timeout is not None else (loaded_timeout if loaded_timeout is not None else 60)

        # --- 选择并实例化 Provider ---
        self.provider: Optional[LLMProviderInterface] = None
        effective_name = override_provider_name if override_provider_name else active_name
        url_for_type_check = _api_url

        provider_type_str = self._determine_provider_type_string(effective_name, url_for_type_check)

        provider_config = {
            'temperature': _temperature,
            'max_tokens': _max_tokens,
            'timeout': _timeout
        }

        if not _api_url or not _model:
             self.logger.warning("API URL or Model is not configured. Cannot instantiate provider.")
        else:
            try:
                if provider_type_str == "anthropic":
                    if not _api_key:
                        self.logger.warning("Anthropic provider requires an API key.")
                    else:
                        self.provider = AnthropicProvider(_api_key, _api_url, _model, **provider_config)
                elif provider_type_str == "ollama":
                    self.provider = OllamaProvider(_api_key, _api_url, _model, **provider_config)
                elif provider_type_str in ["openai", "xai", "mistral", "fireworks", "volcengine_ark", "generic"]:
                    if not _api_key:
                        self.logger.warning(f"{provider_type_str.capitalize()} provider requires an API key.")
                    else:
                        self.provider = OpenAIProvider(_api_key, _api_url, _model, **provider_config)
                else:
                    self.logger.warning(f"No specific provider implementation found for type '{provider_type_str}'.")

            except Exception as e:
                 self.logger.error(f"Failed to instantiate provider '{provider_type_str}': {e}", exc_info=True)
                 self.provider = None

        # --- Provider 实例化结束 ---

        init_source_msg = f"from {config_source}"
        if config_source == "manager" and active_name:
            init_source_msg += f" (active: '{active_name}')"
        elif config_source == "override" and override_provider_name:
             init_source_msg += f" (provider hint: '{override_provider_name}')"

        provider_id = self.provider.get_identifier() if self.provider else "None"
        self.logger.info(f"LLMService initialized {init_source_msg}: "
                         f"Provider='{provider_id}', Key={'***' if _api_key else 'None'}, "
                         f"URL='{_api_url}', Model='{_model}', Temp={_temperature}, "
                         f"MaxTokens={_max_tokens}, Timeout={_timeout}")

        if not self.provider:
             self.logger.warning("LLM Provider could not be instantiated. LLM features will likely fail.")
        elif config_source == "manager" and not active_config:
             self.logger.warning("LLM features may rely on manager config, but none was active.")


   # 将 _determine_provider_type_string 改为静态方法，以便新方法调用
    @staticmethod
    def _determine_provider_type_string(config_name: Optional[str], api_url: Optional[str]) -> str:
        """根据配置名称和URL确定用于选择Provider的类型字符串 (静态方法)"""
        if not config_name and not api_url:
            return "generic"

        if config_name:
            name_lower = config_name.lower()
            if "openai" in name_lower: return "openai"
            if "anthropic" in name_lower: return "anthropic"
            if "google" in name_lower or "gemini" in name_lower: return "google"
            if "mistral" in name_lower: return "mistral"
            if "fireworks" in name_lower: return "fireworks"
            if "ollama" in name_lower: return "ollama"
            if "bailian" in name_lower: return "bailian"
            if "dashscope" in name_lower: return "dashscope"
            if "zhipu" in name_lower: return "zhipu"
            if "xai" in name_lower or "grok" in name_lower: return "xai"
            if "volcengine" in name_lower or "ark" in name_lower or "火山方舟" in config_name or "deepseek" in name_lower:
                 return "volcengine_ark"

        if api_url:
            url_lower = api_url.lower()
            if "openai.com" in url_lower: return "openai"
            if "anthropic.com" in url_lower: return "anthropic"
            if "googleapis.com" in url_lower: return "google"
            if "mistral.ai" in url_lower: return "mistral"
            if "fireworks.ai" in url_lower: return "fireworks"
            if "localhost" in url_lower or "127.0.0.1" in url_lower: return "ollama"
            if "bailian.aliyuncs.com" in url_lower: return "bailian"
            if "dashscope.aliyuncs.com" in url_lower: return "dashscope"
            if "bigmodel.cn" in url_lower: return "zhipu"
            if "api.x.ai" in url_lower: return "xai"
            if "volces.com" in url_lower: return "volcengine_ark"

        return "generic"

    def is_configured(self) -> bool:
        """检查客户端是否已成功配置并实例化了 Provider"""
        return self.provider is not None

    def analyze_news(self, news_item, analysis_type='摘要'):
        """分析新闻"""
        if not news_item:
            raise ValueError("新闻数据不能为空")

        if not self.provider:
            self.logger.warning(f"LLM provider not configured. Returning mock analysis for '{analysis_type}'.")
            if hasattr(news_item, '__dict__'): news_item_dict = vars(news_item)
            elif isinstance(news_item, dict): news_item_dict = news_item
            else: news_item_dict = {}
            return LLMResponseFormatter.mock_analysis(news_item_dict, analysis_type)

        if hasattr(news_item, '__dict__'):
            news_item_dict = vars(news_item)
        elif isinstance(news_item, dict):
            news_item_dict = news_item
        else:
            self.logger.error(f"Unsupported news_item type for prompt generation: {type(news_item)}")
            return LLMResponseFormatter.format_analysis_result(f"<p style='color: red;'>错误：不支持的新闻数据类型。</p>", analysis_type)

        prompt = self.prompt_manager.get_formatted_prompt(
            template_name=None,
            data=news_item_dict,
            analysis_type=analysis_type
        )
        if not prompt or prompt.startswith("错误："):
             self.logger.error(f"Failed to get prompt from PromptManager for analysis type '{analysis_type}': {prompt}")
             return LLMResponseFormatter.format_analysis_result(f"<p style='color: red;'>{prompt}</p>", analysis_type)

        try:
            headers = self.provider.get_headers()
            messages_for_payload = [{'role': 'user', 'content': prompt}]
            payload = self.provider.prepare_request_payload(
                messages=messages_for_payload,
                stream=False
            )

            result_json = self.api_client.post(
                url=self.provider.api_url,
                headers=headers,
                json_payload=payload,
                timeout=self.provider._get_config_value('timeout', 60)
            )

            content = self.provider.parse_response(result_json)

            if not content:
                self.logger.warning(f"LLM analysis via provider '{self.provider.get_identifier()}' returned empty content for type '{analysis_type}'.")
                return LLMResponseFormatter.format_analysis_result("<p style='color: orange;'>分析成功，但模型未返回有效内容。</p>", analysis_type)

            return LLMResponseFormatter.format_analysis_result(content, analysis_type)

        except requests.exceptions.RequestException as e:
            self.logger.error(f"LLM API request failed: {e}", exc_info=True)
            error_html = LLMResponseFormatter.format_error_html(f"请求错误: {e}")
            return error_html
        except Exception as e:
            self.logger.error(f"LLM analysis failed unexpectedly: {e}", exc_info=True)
            error_html = LLMResponseFormatter.format_error_html(f"分析时发生意外错误: {e}")
            return error_html

    def chat(self, messages: List[Union[Dict[str, str], ChatMessage]], context: str = "", stream: bool = True, callback: Optional[Callable[[str, bool], None]] = None) -> Optional[Union[str, threading.Thread]]:
        """
        与 LLM 进行聊天交互。(强制非流式)

        Args:
            messages: 聊天历史消息列表 (可以是 ChatMessage 对象或字典)。
            context: 额外上下文。
            stream: 是否启用流式响应 (此参数在此版本中被忽略，强制非流式)。
            callback: 响应完成或出错时的回调函数。

        Returns:
            - 返回响应字符串或错误 HTML。
            - 如果 LLM 未配置，返回错误信息。
        """
        self._cancel_requested = False # 重置停止标志
        if not self.provider:
            mock_response = "LLM 未配置。请检查环境变量或在设置中选择有效的配置。"
            self.logger.warning(mock_response)
            # Use formatter for error message
            error_html = LLMResponseFormatter.format_error_html(mock_response)
            if callback: # 仍然调用回调以通知错误
                callback(error_html, True)
            return error_html # 非流式直接返回错误

        # 准备消息列表 (确保转换为字典)
        processed_messages = []
        system_prompt_template = self.prompt_manager.load_template('chat_system') or "你是一个专业的新闻分析助手。"
        system_content = f"{system_prompt_template}\n\n相关新闻信息:\n{context}" if context else system_prompt_template
        if system_content.strip():
            processed_messages.append({'role': 'system', 'content': system_content.strip()})

        for msg in messages:
            if isinstance(msg, ChatMessage):
                processed_messages.append({'role': msg.role, 'content': msg.content})
            elif isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                 processed_messages.append({'role': msg['role'], 'content': msg['content']})
            else:
                 self.logger.warning(f"Skipping invalid message format in chat history: {msg}")

        # --- 强制执行非流式请求 ---
        self.logger.info("Forcing non-streaming chat request.")
        try:
            response_content = self._send_chat_request(processed_messages)
            if callback: # 仍然调用回调以通知完成
                callback(response_content, True)
            return response_content
        except Exception as e:
            # Errors are logged within _send_chat_request
            error_html = LLMResponseFormatter.format_error_html(f"发送聊天请求失败: {e}")
            if callback:
                callback(error_html, True)
            return error_html # Return error HTML


    def _stream_chat_response_thread_target(self, messages: List[Dict[str, str]], callback: Callable[[str, bool], None]):
        """包装流式请求以捕获和报告错误给回调函数 (使用 Provider) - 在非流式模式下不再直接调用"""
        # (此方法在强制非流式模式下不再被 chat 方法直接调用，但保留以备将来恢复流式)
        if not self.provider:
            self.logger.error("Cannot start stream: LLM Provider not initialized.")
            callback(LLMResponseFormatter.format_error_html("LLM Provider 未初始化"), True)
            return

        collected_message = ""
        response = None
        messages_as_dicts = messages

        try:
            headers = self.provider.get_headers()
            payload = self.provider.prepare_request_payload(messages_as_dicts, stream=True)
            stop_signal = self.provider.get_stream_stop_signal()
            timeout = self.provider._get_config_value('timeout', 60)

            line_iterator = self.api_client.stream_post(
                url=self.provider.api_url,
                headers=headers,
                json_payload=payload,
                timeout=timeout
            )

            for line in line_iterator:
                if self._cancel_requested:
                    self.logger.info("Stream cancelled by request.")
                    break

                if not line:
                    continue

                try:
                     decoded_line = line.decode('utf-8')
                except UnicodeDecodeError:
                     self.logger.warning(f"Failed to decode stream line as UTF-8: {line!r}")
                     continue

                if stop_signal and decoded_line.strip() == stop_signal:
                     break

                content_chunk = self.provider.parse_stream_chunk(decoded_line)

                if content_chunk is not None:
                     # 注意：这里仍然传递累积消息给回调，如果恢复流式，需要决定是传增量还是完整
                     collected_message += content_chunk
                     callback(collected_message, False) # 或者 callback(content_chunk, False) 如果要传增量

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Stream connection failed: {e}", exc_info=True)
            error_html = LLMResponseFormatter.format_error_html(f"连接流式 API 失败: {e}")
            callback(error_html, True)
        except Exception as e:
            self.logger.error(f"Stream processing failed unexpectedly: {e}", exc_info=True)
            error_html = LLMResponseFormatter.format_error_html(f"处理流式响应时发生意外错误: {e}")
            callback(error_html, True)
        finally:
            callback(collected_message, True) # 确保最后调用回调
            self.logger.debug(f"Stream finished for provider '{self.provider.get_identifier() if self.provider else 'None'}'. Cancelled: {self._cancel_requested}")
            self._current_stream_thread = None


    def _send_chat_request(self, messages: List[Dict[str, str]]) -> str:
        """发送非流式聊天请求 (使用 Provider)"""
        if not self.provider:
             raise ConnectionError("LLM Provider not initialized.")

        messages_as_dicts = messages

        try:
            headers = self.provider.get_headers()
            payload = self.provider.prepare_request_payload(messages_as_dicts, stream=False)
            # timeout = self.provider._get_config_value('timeout', 60)
 # 原代码
            timeout = 120 # 强制增加超时时间到 120 秒

            result_json = self.api_client.post(
                url=self.provider.api_url,
                headers=headers,
                json_payload=payload,
                timeout=timeout
            )

            content = self.provider.parse_response(result_json)

            if content is None:
                 self.logger.warning(f"Non-stream chat via provider '{self.provider.get_identifier()}' returned null/empty content. Response: {result_json}")
                 return ""
            return content

        except requests.exceptions.RequestException as e:
             self.logger.error(f"Non-stream chat request failed: {e}", exc_info=True)
             raise ConnectionError(f"API request failed: {e}") from e
        except Exception as e:
             self.logger.error(f"Non-stream chat processing failed unexpectedly: {e}", exc_info=True)
             raise RuntimeError(f"Unexpected error during chat processing: {e}") from e


    # --- Stream Control ---
    def cancel_stream(self):
        """Sets the flag to request cancellation of the current stream."""
        # 在非流式模式下，这个方法作用有限，但保留标志位
        if self._current_stream_thread and self._current_stream_thread.is_alive():
            self.logger.info("Setting cancel flag for stream thread (effect may be limited for non-streaming).")
            self._cancel_requested = True
        else:
            self.logger.warning("Cancel stream requested, but no active stream thread found.")


    # --- Testing and Other Utilities ---

    def test_connection_with_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """
        使用提供的配置字典测试与 LLM Provider 的连接。
        这会创建一个临时的 Provider 实例进行测试。

        Args:
            config: 包含待测试配置的字典，应包含 'name', 'api_url', 'api_key', 'model',
                    以及可选的 'temperature', 'max_tokens', 'timeout'。

        Returns:
            一个元组 (bool, str)，表示连接是否成功以及相应的消息。
        """
        logger = self.logger # 使用实例的 logger
        provider: Optional[LLMProviderInterface] = None

        # 从传入的 config 字典中提取值
        config_name = config.get('name') # 用于类型提示
        api_url = config.get('api_url')
        api_key = config.get('api_key')
        model = config.get('model')
        temperature = config.get('temperature')
        max_tokens = config.get('max_tokens')
        # 使用传入的 timeout 或默认测试 timeout
        timeout_override = config.get('timeout')
        test_timeout = 15 # 短超时用于测试

        provider_type_str = LLMService._determine_provider_type_string(config_name, api_url)

        provider_config = {
            'temperature': temperature if temperature is not None else 0.7,
            'max_tokens': max_tokens if max_tokens is not None else 2048,
            # 注意：这里的 timeout 是 Provider 内部配置，测试请求本身使用 test_timeout
            'timeout': timeout_override if timeout_override is not None else 60
        }

        if not api_url or not model:
            msg = "API URL 或模型未在测试配置中提供。"
            logger.warning(msg)
            return False, msg

        # --- 实例化临时 Provider ---
        try:
            if provider_type_str == "anthropic":
                if not api_key: msg = "Anthropic 需要 API Key"; logger.warning(msg); return False, msg
                provider = AnthropicProvider(api_key, api_url, model, **provider_config)
            elif provider_type_str == "ollama":
                provider = OllamaProvider(api_key, api_url, model, **provider_config)
            elif provider_type_str in ["openai", "xai", "mistral", "fireworks", "volcengine_ark", "generic"]:
                # 对于 OpenAI 兼容类型，检查 API Key 是否必需
                # （注意：Ollama 可能不需要 key，但上面已处理）
                if not api_key and provider_type_str != "ollama":
                     msg = f"{provider_type_str.capitalize()} 提供者通常需要 API Key 进行测试。"
                     # 允许测试没有 key 的通用或 Ollama 类型
                     logger.warning(msg + " (将尝试连接，但可能失败)")
                     # 不直接返回 False，让请求尝试
                provider = OpenAIProvider(api_key, api_url, model, **provider_config)
            else:
                msg = f"未找到用于测试的 Provider 实现: '{provider_type_str}'"
                logger.warning(msg)
                return False, msg

        except Exception as e:
            msg = f"实例化 Provider '{provider_type_str}' 进行测试时失败: {e}"
            logger.error(msg, exc_info=True)
            return False, msg
        # --- Provider 实例化结束 ---

        # --- 执行测试 ---
        if not provider: # 双重检查
             return False, "未能实例化 Provider 进行测试。"

        try:
            headers = provider.get_headers()
            payload = provider.test_connection_payload()

            log_headers = {k: v for k, v in headers.items() if k.lower() not in ['authorization', 'x-api-key']}
            if 'authorization' in headers: log_headers['Authorization'] = 'Bearer ***'
            if 'x-api-key' in headers: log_headers['x-api-key'] = '***'
            logger.info(f"发送测试请求 (使用配置: '{config_name}') 到: {provider.api_url} 使用 provider {provider.get_identifier()}")
            logger.debug(f"测试请求头: {log_headers}")
            logger.debug(f"测试请求体: {payload}")

            # 使用 LLMService 实例持有的 api_client
            result_json = self.api_client.post(
                url=provider.api_url,
                headers=headers,
                json_payload=payload,
                timeout=test_timeout # 使用短测试超时
            )

            if provider.check_test_connection_response(result_json):
                msg = f"连接成功: {provider.get_identifier()} @ {provider.api_url}"
                logger.info(msg)
                return True, msg
            else:
                # 尝试从错误响应中提取更多信息
                error_details = ""
                if isinstance(result_json, dict):
                    error_info = result_json.get('error')
                    if isinstance(error_info, dict):
                        error_details = f" 类型: {error_info.get('type')}, 消息: {error_info.get('message')}"
                    elif isinstance(error_info, str):
                         error_details = f" 错误信息: {error_info}"

                msg = f"连接失败: Provider '{provider.get_identifier()}' 响应无效。{error_details} 完整响应: {str(result_json)[:200]}..." # 限制响应长度
                logger.warning(msg)
                return False, msg

        except requests.exceptions.Timeout:
            msg = f"连接超时 ({test_timeout}s): {provider.api_url}"
            logger.warning(msg)
            return False, msg
        except requests.exceptions.RequestException as e:
            msg = f"连接错误: {e}"
            logger.error(msg, exc_info=True)
            # 尝试提取更具体的错误信息
            response_text = str(getattr(e.response, 'text', ''))[:200]
            if response_text:
                 msg += f" - 响应: {response_text}..."
            return False, msg
        except Exception as e:
            msg = f"测试连接时发生意外错误: {e}"
            logger.error(msg, exc_info=True)
            return False, msg

    # --- Testing and Other Utilities ---
    def test_connection(self) -> tuple[bool, str]:
        """测试与当前配置的 LLM Provider 的 API 连接。"""
        if not self.provider:
            msg = "LLM 客户端未配置或初始化失败。"
            self.logger.warning(f"Cannot test connection: {msg}")
            return False, msg

        try:
            headers = self.provider.get_headers()
            payload = self.provider.test_connection_payload()
            timeout = 15 # Shorter timeout for testing

            log_headers = {k: v for k, v in headers.items() if k.lower() not in ['authorization', 'x-api-key']}
            if 'authorization' in headers: log_headers['Authorization'] = 'Bearer ***'
            if 'x-api-key' in headers: log_headers['x-api-key'] = '***'
            self.logger.info(f"Sending test request to: {self.provider.api_url} using provider {self.provider.get_identifier()}")
            self.logger.debug(f"Test request headers: {log_headers}")
            self.logger.debug(f"Test request body: {payload}")

            result_json = self.api_client.post(
                url=self.provider.api_url,
                headers=headers,
                json_payload=payload,
                timeout=timeout
            )

            if self.provider.check_test_connection_response(result_json):
                msg = f"连接成功: {self.provider.get_identifier()} @ {self.provider.api_url}"
                self.logger.info(msg)
                return True, msg
            else:
                msg = f"连接失败: Provider '{self.provider.get_identifier()}' 响应无效。响应: {result_json}"
                self.logger.warning(msg)
                return False, msg

        except requests.exceptions.Timeout:
            msg = f"连接超时 ({timeout}s): {self.provider.api_url}"
            self.logger.warning(msg)
            return False, msg
        except requests.exceptions.RequestException as e:
            msg = f"连接错误: {e}"
            self.logger.error(msg, exc_info=True)
            return False, msg
        except Exception as e:
            msg = f"测试连接时发生意外错误: {e}"
            self.logger.error(msg, exc_info=True)
            return False, msg

    def translate_text(self, text: str, target_language: str = "English") -> str:
        """使用 LLM 翻译文本"""
        if not self.provider:
            return f"[翻译错误: LLM 未配置]"

        prompt = self.prompt_manager.get_formatted_prompt(
            template_name='translate',
            data={'text': text, 'target_language': target_language}
        )
        if not prompt or prompt.startswith("错误："):
            return f"[翻译错误: {prompt}]"

        try:
            messages = [{'role': 'user', 'content': prompt}]
            translated_text = self._send_chat_request(messages)
            return translated_text if translated_text else "[翻译失败: 模型未返回内容]"
        except Exception as e:
            self.logger.error(f"Translation failed: {e}", exc_info=True)
            return f"[翻译错误: {e}]"