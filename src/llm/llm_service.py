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
from typing import Callable, Dict, List, Optional, Union, Any, Tuple
import dataclasses # Import dataclasses
import requests # <-- 新增导入
from PySide6.QtCore import QObject, Signal as pyqtSignal
 
# --- 导入内部模块 ---
from src.config.llm_config_manager import LLMConfigManager
from .prompt_manager import PromptManager
from .providers.base import LLMProviderInterface
from .providers.openai import OpenAIProvider
from .providers.anthropic import AnthropicProvider
from .providers.ollama import OllamaProvider
from .providers.google import GeminiProvider # <-- Import new provider
from .formatter import LLMResponseFormatter
from src.utils.api_client import ApiClient # <-- 新增导入
# Import ChatMessage for type checking during conversion
from src.models import ChatMessage, NewsArticle
# --- FIX: Import LLMError --- Added
from .exception import LLMError


class LLMService(QObject):
    """
    LLM 服务类，协调配置、提示和 Provider 实现。
    """
    # --- ADD SIGNALS --- Added
    chat_chunk_received = pyqtSignal(str)
    chat_finished = pyqtSignal(str) # Emits final accumulated message on success
    chat_error = pyqtSignal(str)    # Emits error message (HTML formatted potentially)

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
        super().__init__()
        self.logger = logging.getLogger('news_analyzer.llm.service') # Renamed logger
        self.config_manager = config_manager
        self.prompt_manager = prompt_manager
        self.api_client = api_client
        self._cancel_requested = False # 添加停止标志
        self._current_stream_thread: threading.Thread | None = None # Track the stream thread
        self._emitted_final_for_stream = False # Add new flag

        # --- Load initial configuration and instantiate provider --- Modified
        initial_config = self._load_initial_config(
            override_api_key, override_api_url, override_model,
            override_temperature, override_max_tokens, override_timeout,
            override_provider_name
        )
        
        self.provider: Optional[LLMProviderInterface] = None # Ensure provider is initialized
        if initial_config:
            self._initialize_provider(initial_config)
        else:
            self.logger.warning("LLMService initialized without a valid initial configuration.")

        # Log initial state (moved logging inside _initialize_provider)

    def _load_initial_config(self, override_api_key, override_api_url, override_model,
                             override_temperature, override_max_tokens, override_timeout,
                             override_provider_name) -> Optional[Dict[str, Any]]:
        """Loads configuration, prioritizing overrides, then manager's active config."""
        self.logger.debug("Loading initial LLM configuration...")
        config_source = "override" if any([override_api_key, override_api_url, override_model]) else "manager"

        loaded_api_key: Optional[Union[str, List[str]]] = None # Can be list for Gemini
        loaded_api_url: Optional[str] = None
        loaded_model: Optional[str] = None
        loaded_temperature: Optional[float] = None
        loaded_max_tokens: Optional[int] = None
        loaded_timeout: Optional[int] = None
        active_name: Optional[str] = None

        if config_source == "manager":
            active_config_dict = self.config_manager.get_active_config()
            if active_config_dict:
                loaded_api_key = active_config_dict.get('api_key')
                loaded_api_url = active_config_dict.get('api_url')
                loaded_model = active_config_dict.get('model')
                loaded_temperature = active_config_dict.get('temperature', 0.7)
                loaded_max_tokens = active_config_dict.get('max_tokens', 2048)
                loaded_timeout = active_config_dict.get('timeout', 60)
                active_name = self.config_manager.get_active_config_name()
            else:
                 self.logger.warning("No active LLM configuration found via manager during init.")

        # Apply overrides
        final_api_key = override_api_key if override_api_key is not None else loaded_api_key
        final_api_url = override_api_url if override_api_url is not None else loaded_api_url
        final_model = override_model if override_model is not None else loaded_model
        final_temperature = override_temperature if override_temperature is not None else (loaded_temperature if loaded_temperature is not None else 0.7)
        final_max_tokens = override_max_tokens if override_max_tokens is not None else (loaded_max_tokens if loaded_max_tokens is not None else 2048)
        final_timeout = override_timeout if override_timeout is not None else (loaded_timeout if loaded_timeout is not None else 60)
        final_name = override_provider_name if override_provider_name else active_name # Use override name if provided, else active name
        
        if not final_api_url or not final_model:
            self.logger.warning("Initial config load resulted in missing API URL or Model.")
            return None
        
        # Return a consistent config dictionary
        return {
            'name': final_name,
            'api_key': final_api_key,
            'api_url': final_api_url,
            'model': final_model,
            'temperature': final_temperature,
            'max_tokens': final_max_tokens,
            'timeout': final_timeout,
            '_source': config_source # Keep track of where it came from for logging
        }

    def _initialize_provider(self, config: Dict[str, Any]) -> bool:
        """Instantiates the LLM provider based on the given configuration dict."""
        self.logger.info(f"--- LLMService._initialize_provider: Received config for initialization: {config}")
        self.logger.info(f"Attempting to initialize LLM provider with config: {config.get('name', 'N/A')}")
        _api_key = config.get('api_key')
        _api_url = config.get('api_url')
        _model = config.get('model')
        _name = config.get('name') # Get name from config dict

        if not _api_url or not _model:
             self.logger.error("Cannot initialize provider: API URL or Model missing in config.")
             self.provider = None
             return False

        provider_type_str = self._determine_provider_type_string(_name, _api_url)
        self.provider_type_string = provider_type_str # <-- Ensure this line is present
        
        # Create provider config dict for instantiation
        # Ensure keys match ProviderConfig definition if strict type checking occurs later
        provider_config_args = {
            'temperature': config.get('temperature', 0.7),
            'max_tokens': config.get('max_tokens', 2048),
            'timeout': config.get('timeout', 60)
            # Add other potential config args here if base provider uses them
        }
        # Convert to dataclass if providers expect it? For now, pass dict.
        # provider_config_obj = ProviderConfig(**provider_config_args) 

        # --- FIX: Remove incomplete try block --- Removed 
        # try: <--- Remove this line
        new_provider: Optional[LLMProviderInterface] = None
        if provider_type_str == "anthropic":
            if not _api_key or not isinstance(_api_key, str):
                self.logger.error("Anthropic provider requires a single string API key.")
            else:
                self.logger.debug(f"Attempting to initialize AnthropicProvider for '{_name}'. Config params: {provider_config_args}")
                new_provider = AnthropicProvider(api_key=str(_api_key) if _api_key else '', api_url=_api_url, model=_model, config=provider_config_args)
        elif provider_type_str == "google":
            # Gemini expects a list of keys
            api_keys_list = []
            if isinstance(_api_key, list):
                api_keys_list = _api_key
            elif isinstance(_api_key, str) and _api_key:
                api_keys_list = [_api_key]
                
            if not api_keys_list:
                self.logger.error("Google Gemini provider requires a non-empty API key or list.")
            else:
                # Pass the dict directly, GeminiProvider expects dict now
                self.logger.debug(f"Attempting to initialize GeminiProvider for '{_name}'. Config params: {provider_config_args}")
                new_provider = GeminiProvider(api_keys=api_keys_list, api_url=_api_url, model=_model, config=provider_config_args)
        elif provider_type_str == "ollama":
            # Ollama might not need a key, pass None if _api_key is falsy
            # Ensure provider_config_args doesn't contain keys Ollama doesn't expect
            ollama_config = {k: v for k, v in provider_config_args.items() if k in ['temperature', 'timeout']}
            # Pass config as kwargs
            # --- FIX: Ensure parenthesis are closed --- Modified
            self.logger.debug(f"Attempting to initialize OllamaProvider for '{_name}'. API URL: {_api_url}, Model: {_model}, Config params: {ollama_config}")
            new_provider = OllamaProvider(api_url=_api_url, model=_model, api_key=None, config=ollama_config)
        # --- FIX: Correct indentation --- Modified
        elif provider_type_str in ["openai", "xai", "mistral", "fireworks", "volcengine_ark", "generic"]:
            if not _api_key or not isinstance(_api_key, str):
                 self.logger.error(f"{provider_type_str.capitalize()} provider requires a single string API key.")
            else:
                 # Ensure provider_config_args doesn't contain keys OpenAIProvider doesn't expect
                 self.logger.debug(f"Attempting to initialize OpenAIProvider (compatible) for '{_name}'. Config params: {provider_config_args}")
                 new_provider = OpenAIProvider(
                     api_key=str(_api_key) if _api_key else '',
                     api_url=_api_url,
                     model=_model,
                     config=provider_config_args
                 )
        else:
            self.logger.error(f"No specific provider implementation found for type '{provider_type_str}'. Cannot initialize.")

        # --- Catch exceptions around the whole block --- Added try...except
        try:
            if new_provider:
                self.provider = new_provider
                provider_id = self.provider.get_identifier() if self.provider else "None"
                log_key = '***' if _api_key else 'None'
                if isinstance(_api_key, list): log_key = f'List[{len(_api_key)}]'
                self.logger.info(f"LLM Provider Initialized/Reloaded: Name='{_name}', Provider='{provider_id}', Key={log_key}, URL='{_api_url}', Model='{_model}'")
                return True # Initialization successful
            else:
                 # Logged specific error inside the if/elif block already
                 self.logger.error(f"Provider object is None after attempting initialization for type '{provider_type_str}'.")
                 self.provider = None
                 return False # Initialization failed
        except Exception as e:
            self.logger.error(f"Exception during provider assignment or logging ('{provider_type_str}'): {e}", exc_info=True)
            self.provider = None
            return False # Initialization failed

    def reload_active_config(self) -> bool:
        """Reloads the active configuration from the manager and re-initializes the provider."""
        self.logger.info("Reloading active LLM configuration...")
        active_config = self.config_manager.get_active_config()
        if active_config:
            # Add the config name to the dict for _initialize_provider
            active_name = self.config_manager.get_active_config_name()
            active_config['name'] = active_name
            active_config['_source'] = 'manager (reloaded)'
            return self._initialize_provider(active_config)
        else:
            self.logger.warning("Could not find active configuration to reload. LLMService provider remains unchanged.")
            return False

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

    # --- ADDED: Extracted method for preparing messages ---
    def _prepare_messages_for_analysis(self, article_content: Union[str, NewsArticle, Dict[str, Any]], analysis_type: str, custom_prompt_key: Optional[str] = None) -> List[Dict[str, str]]:
        """Helper method to prepare messages for LLM analysis."""
        
        prompt_data: Dict[str, Any]

        if isinstance(article_content, NewsArticle):
            # Convert NewsArticle object to a dictionary
            prompt_data = article_content.to_dict() if hasattr(article_content, 'to_dict') else vars(article_content)
        elif isinstance(article_content, dict):
            prompt_data = article_content.copy()
        elif isinstance(article_content, str): # Handle plain string content if needed
            # This might need a more structured approach if plain strings are common
            prompt_data = {'content': article_content, 'title': 'N/A', 'source': 'N/A', 'pub_date': 'N/A'} 
        else:
            self.logger.error(f"Unsupported article_content type: {type(article_content)}")
            raise TypeError(f"Unsupported article_content type: {type(article_content)}")

        # Ensure common keys for prompt formatting, similar to original logic
        prompt_data['source'] = prompt_data.get('source_name', prompt_data.get('source'))
        prompt_data['content'] = prompt_data.get('content', prompt_data.get('summary', prompt_data.get('description')))
        prompt_data['pub_date'] = str(prompt_data.get('pub_date', prompt_data.get('publish_time')))
        
        self.logger.debug(f"Prepared news data dict for prompt: {list(prompt_data.keys())}")

        # Use custom_prompt_key if provided, otherwise derive template_name from analysis_type
        template_name_to_use: Optional[str] = None
        if custom_prompt_key:
            # Assuming custom_prompt_key IS the template name for custom prompts
            template_name_to_use = custom_prompt_key 
            self.logger.debug(f"Using custom_prompt_key as template_name: {template_name_to_use}")
        
        # If not using a custom_prompt_key, then analysis_type drives template selection (implicitly by PromptManager)
        # The get_formatted_prompt method in PromptManager handles mapping analysis_type to a template if template_name is None

        prompt = self.prompt_manager.get_formatted_prompt(
            template_name=template_name_to_use, 
            data=prompt_data,
            analysis_type=analysis_type if not template_name_to_use else None # Pass analysis_type only if template_name is not set by custom_prompt_key
        )
            
        if not prompt or prompt.startswith("错误："):
             self.logger.error(f"Error getting formatted prompt: {prompt}")
             # Raise an error or return empty messages to be handled by caller
             raise ValueError(f"Failed to get formatted prompt: {prompt}")

        messages = [{"role": "user", "content": prompt}]
        return messages
    # --- END ADDED METHOD ---

    # analyze_news (original version around line 284, modified)
    # This version of analyze_news seems to be the one actually being called by UI based on stack trace
    # I will ensure THIS version uses the new _prepare_messages_for_analysis
    # And then remove the duplicate analyze_news at the end of the file.
    
    # --- This is the analyze_news that was likely intended to be used by the UI ---
    # --- It's around line 284 in the full file provided ---
    # --- We will ensure it calls the new _prepare_messages_for_analysis ---
    def analyze_news(self, news_item: NewsArticle, analysis_type='摘要'): # Parameter name matches usage
        """使用配置的 LLM 分析单个新闻项目。

        Args:
            news_item (NewsArticle): 要分析的新闻文章对象。
            analysis_type (str): 分析类型 ('摘要', '深度分析', '关键观点', '事实核查')。

        Returns:
            str: 格式化的 HTML 分析结果，或包含错误信息的 HTML。

        Raises:
            ValueError: 如果 news_item 为空。
        """
        if not news_item:
            raise ValueError("News item cannot be None for analysis.")

        if not self.is_configured():
            self.logger.warning(f"LLM provider not configured. Returning mock analysis for type: {analysis_type}")
            news_item_dict = news_item.to_dict() if hasattr(news_item, 'to_dict') else {}
            return LLMResponseFormatter.mock_analysis(news_item_dict, analysis_type)

        try:
            # --- MODIFIED: Call the new helper method ---
            # The 'article_content' parameter of _prepare_messages_for_analysis is news_item here
            messages = self._prepare_messages_for_analysis(news_item, analysis_type, custom_prompt_key=None) # Pass news_item directly
            # --- END MODIFIED ---
            
            self.logger.info(f"Sending analysis request (type: {analysis_type}) via provider: {self.provider.get_identifier()}")

            # --- MODIFIED SECTION (from previous step, ensuring it's in the correct analyze_news) ---
            if isinstance(self.provider, GeminiProvider):
                self.logger.debug("Using GeminiProvider._send_chat_request for analysis.")
                raw_response_data = self.provider._send_chat_request(self.api_client, messages)
                analysis_result = self.provider.parse_response(raw_response_data)
                self.logger.info(f"LLM analysis successful via GeminiProvider. Result length: {len(analysis_result)}")
            else:
                self.logger.debug(f"Using direct ApiClient.post for provider {self.provider.get_identifier()}. This provider might not have advanced retry/key rotation.")
                payload = self.provider.prepare_request_payload(messages, stream=False)
                request_url = getattr(self.provider, 'chat_generate_url', self.provider.api_url)
                if request_url == self.provider.api_url and isinstance(self.provider, GeminiProvider):
                    self.logger.warning("Fallback: Constructing Gemini URL manually in LLMService (direct post) - not ideal.")
                    current_key = self.provider._get_current_key()
                    request_url = self.provider.CHAT_URL_TEMPLATE.format(
                        api_url=self.provider.api_url.rstrip('/'), model=self.provider.model, api_key=current_key
                    )
                raw_response_data = self.api_client.post(
                    url=request_url,
                    headers=self.provider.get_headers(),
                    json_payload=payload,
                    timeout=self.provider._get_config_value('timeout', 60)
                )
                analysis_result = self.provider.parse_response(raw_response_data)
                self.logger.info(f"LLM analysis successful via direct ApiClient.post. Result length: {len(analysis_result)}")
            # --- END MODIFIED SECTION ---

            if not analysis_result: # Check if result is empty
                self.logger.warning("--- LLMService.analyze_news: Content from provider.parse_response was None or empty. --- ")
                return LLMResponseFormatter.format_error_html("API 返回的内容为空或无法解析。")

            formatted_html_output = LLMResponseFormatter.format_analysis_result(analysis_result, analysis_type)
            return formatted_html_output

        except LLMError as e:
            self.logger.error(f"LLM analysis failed: {e}", exc_info=True)
            return LLMResponseFormatter.format_error_html(f"分析请求失败: {e}")
        except ValueError as ve: # Catch specific ValueError from _prepare_messages
            self.logger.error(f"Error preparing messages for analysis: {ve}", exc_info=True)
            return LLMResponseFormatter.format_error_html(f"准备分析请求时出错: {ve}")
        except Exception as e:
            self.logger.error(f"Unexpected error during news analysis: {e}", exc_info=True)
            return LLMResponseFormatter.format_error_html(f"分析过程中发生意外错误: {e}")

    def analyze_news_similarity(self, news_items: List[Dict], analysis_type='新闻相似度分析'):
        """分析多篇新闻的相似度
        
        Args:
            news_items: 新闻列表，每个元素是一个新闻字典
            analysis_type: 分析类型，默认为'新闻相似度分析'，也可以是'多角度整合'、'对比分析'等
            
        Returns:
            分析结果HTML
        """
        if not news_items or len(news_items) < 2:
            raise ValueError("需要至少两篇新闻才能进行相似度分析")

        if not self.provider:
            self.logger.warning(f"LLM provider not configured. Returning mock analysis for '{analysis_type}'.")
            return LLMResponseFormatter.format_analysis_result(f"<p style='color: red;'>LLM服务未配置，无法进行{analysis_type}</p>", analysis_type)
        
        # 准备新闻数据文本
        news_text_list = []
        for i, news in enumerate(news_items):
            if hasattr(news, '__dict__'):
                news_dict = vars(news)
            elif isinstance(news, dict):
                news_dict = news
            else:
                self.logger.error(f"Unsupported news item type for prompt generation: {type(news)}")
                continue
                
            title = news_dict.get('title', '无标题')
            source = news_dict.get('source_name', news_dict.get('source', '未知来源'))
            pub_date = str(news_dict.get('pub_date', news_dict.get('publish_time', '未知日期')))
            content = news_dict.get('content', news_dict.get('summary', news_dict.get('description', '无内容')))
            
            news_text = f"新闻{i+1}:\n标题: {title}\n来源: {source}\n日期: {pub_date}\n内容: {content}\n\n"
            news_text_list.append(news_text)
        
        # 合并所有新闻文本
        all_news_text = "\n".join(news_text_list)
        
        # 准备提示数据
        prompt_data = {
            'news_items': all_news_text
        }
        
        # 获取格式化的提示
        prompt = self.prompt_manager.get_formatted_prompt(
            template_name=None,
            data=prompt_data,
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

            # Determine the correct request URL based on the provider type
            request_url = ""
            try:
                from src.llm.providers.google import GeminiProvider # Lazy import
                if isinstance(self.provider, GeminiProvider):
                    request_url = self.provider.chat_generate_url
                    self.logger.debug(f"Using Gemini generate URL for similarity analysis: {request_url[:70]}...")
                else:
                    request_url = self.provider.api_url
                    self.logger.debug(f"Using standard provider URL for similarity analysis: {request_url}")
            except ImportError:
                self.logger.error("Failed to import GeminiProvider for URL determination.")
                request_url = self.provider.api_url # Fallback
            
            if not request_url:
                self.logger.error("Request URL for LLM analysis could not be determined.")
                raise LLMError("无法确定LLM请求的URL。")

            # --- Revert to using ApiClient directly --- Added
            result_json = self.api_client.post(
                url=request_url, # Use determined request_url
                headers=headers,
                json_payload=payload,
                timeout=self.provider._get_config_value('timeout', 120) # Use longer timeout
            )
            # --- End Revert ---
            self.logger.info(f"--- SIMILARITY RAW RESPONSE from ApiClient (type: {type(result_json)}) ---")
            self.logger.debug(f"--- SIMILARITY RAW RESPONSE content: {str(result_json)[:1000]} ---") # Log first 1000 chars

            content = self.provider.parse_response(result_json)
            self.logger.info(f"--- SIMILARITY PARSED CONTENT from provider (type: {type(content)}) ---")
            if content:
                self.logger.debug(f"--- SIMILARITY PARSED CONTENT value (first 1000 chars): {str(content)[:1000]} ---")
            else:
                self.logger.warning("--- SIMILARITY PARSED CONTENT is None or empty. ---")

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

    def chat(self, messages: List[Union[Dict[str, str], ChatMessage]], context: str = "", stream: bool = True) -> Optional[Union[str, threading.Thread]]:
        """
        与 LLM 进行聊天交互。(强制非流式)

        Args:
            messages: 聊天历史消息列表 (可以是 ChatMessage 对象或字典)。
            context: 额外上下文。
            stream: 是否启用流式响应 (此参数在此版本中被忽略，强制非流式)。

        Returns:
            - 返回响应字符串或错误 HTML。
            - 如果 LLM 未配置，返回错误信息。
        """
        self.logger.info(f"Executing chat method. Current provider type string: '{self.provider_type_string}'") # <-- Add logging
        self._cancel_requested = False # 重置停止标志
        if not self.provider:
            mock_response = "LLM 未配置。请检查环境变量或在设置中选择有效的配置。"
            self.logger.warning(mock_response)
            # Use formatter for error message
            error_html = LLMResponseFormatter.format_error_html(mock_response)
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

        # --- Decide whether to stream based on provider type --- ADDED BLOCK
        should_stream = stream # Start with the requested mode
        # --- FIX: Force non-streaming for Google Gemini as well --- Modified
        # if self.provider_type_string == "volcengine_ark":
        if self.provider_type_string in ["volcengine_ark", "google"]:
            if should_stream:
                self.logger.info(f"Forcing non-streaming chat request for {self.provider_type_string} provider.")
            should_stream = False # Force non-streaming
        # --- End FIX ---

        if not should_stream:
            # --- Execute Non-Streaming Request --- ADDED BLOCK
            self.logger.info("Executing non-streaming chat request.")
            # --- FIX: Correct indentation and structure for try/except/finally --- Modified
            try:
                # --- FIX: Use provider specific method if available, else generic --- Modified
                if hasattr(self.provider, '_send_chat_request') and callable(getattr(self.provider, '_send_chat_request')):
                    self.logger.info(f"Calling self.provider._send_chat_request for non-stream... Provider: {type(self.provider)}")
                    # Provider handles the request internally (e.g., Gemini with rotation)
                    response_data = self.provider._send_chat_request(self.api_client, processed_messages)
                    response_content = self.provider.parse_response(response_data)
                else:
                    # Generic approach for providers without _send_chat_request (e.g., OpenAIProvider)
                    self.logger.info(f"Provider {type(self.provider)} lacks _send_chat_request, using generic api_client.post...")
                    request_url = self.provider.api_url # Assuming api_url is the correct endpoint
                    headers = self.provider.get_headers()
                    payload = self.provider.prepare_request_payload(processed_messages, stream=False)
                    self.logger.debug(f"Generic Non-Stream Payload for {request_url}: {json.dumps(payload, indent=2, ensure_ascii=False)}")
                    response_data = self.api_client.post(
                        url=request_url,
                        headers=headers,
                        json_payload=payload,
                        timeout=self.provider._get_config_value('timeout', 120) # Use longer timeout
                    )
                    response_content = self.provider.parse_response(response_data)
                # --- End FIX ---

                # Success: Emit chat_finished signal
                self.chat_finished.emit(response_content)
                return None # Non-streaming successful, signal emitted
            except requests.exceptions.Timeout as e: # Keep specific error handling
                error_msg = f"错误：网络连接超时 ({e})"
                self.logger.error(error_msg, exc_info=True)
                self.chat_error.emit(LLMResponseFormatter.format_error_html(error_msg))
                return None # Return None on error too
            except requests.exceptions.RequestException as e:
                # Extract status code if possible
                status_code_str = f" (Status: {e.response.status_code})" if e.response is not None else ""
                error_msg = f"错误：网络请求失败{status_code_str} ({e})"
                self.logger.error(error_msg, exc_info=True)
                self.chat_error.emit(LLMResponseFormatter.format_error_html(error_msg))
                return None # Return None on error too
            except LLMError as e: # Catch LLMErrors raised by provider's _send_chat_request
                error_msg = f"错误：API 请求失败 ({e})"
                self.logger.error(error_msg, exc_info=True)
                self.chat_error.emit(LLMResponseFormatter.format_error_html(error_msg))
                return None
            except Exception as e:
                error_msg = f"错误：处理聊天请求时发生意外错误 ({e})"
                self.logger.error(error_msg, exc_info=True)
                self.chat_error.emit(LLMResponseFormatter.format_error_html(error_msg))
                return None # Return None on error too
        else:
            # --- Execute Streaming Request --- ADDED BLOCK (original logic moved here)
            self.logger.info(f"Initiating STREAMING chat request for provider type: {self.provider_type_string}.")
            # --- REMOVE CALLBACK --- Modified
            # if not callback:
            #     self.logger.error("Streaming requires a callback function.")
            #     raise ValueError("Streaming requires a callback function.")

            self._cancel_requested = False
            self._current_stream_thread = threading.Thread(
                target=self._stream_chat_response_thread_target,
                args=(processed_messages,), # Removed callback from args
                daemon=True
            )
            self._current_stream_thread.start()
            return self._current_stream_thread # Return the thread

    def _stream_chat_response_thread_target(self, messages: List[Dict[str, str]]): 
        """包装流式请求以捕获和报告错误 (使用信号) (后台线程)""" 
        self.logger.info(f"--- Stream Thread STARTED for provider: {self.provider.get_identifier() if self.provider else 'N/A'} ---")
        self._cancel_requested = False
        self._emitted_final_for_stream = False # Reset flag for new stream

        full_response_content = ""
        error_occurred = False
        error_message_html = "" # To store formatted error message
        stream_ended_naturally_via_final_chunk_signal = False

        try:
            if not self.provider:
                raise LLMError("LLM provider is not initialized.")

            target_url = ""
            request_payload = {}

            if isinstance(self.provider, OllamaProvider):
                target_url = self.provider.chat_generate_url
                request_payload = self.provider.prepare_request_payload(messages, stream=True)
            elif self.provider: # For other providers, assuming a generic way or specific handling
                target_url = self.provider.get_stream_url() # Hypothetical generic method
                request_payload = self.provider.prepare_request_payload(messages, stream=True)
            else: # Should have been caught by the None check already
                raise LLMError("Provider not available for streaming.")

            self.logger.debug(f"Streaming from URL: {target_url}")
            self.logger.debug(f"Request payload: {json.dumps(request_payload, indent=2, ensure_ascii=False)}")

            line_iterator = self.api_client.stream_post(
                url=target_url,
                headers=self.provider.get_headers(),
                json_payload=request_payload,
                timeout=self.provider._get_config_value('timeout', 120) 
            )
            
            for line in line_iterator:
                if self._cancel_requested:
                    self.logger.info("Streaming cancelled by request.")
                    break 
                
                try:
                    processed_chunk, is_final_chunk = self.provider.process_stream_line(line)
                    
                    if processed_chunk is not None: # Ensure there's content to process/emit
                        full_response_content += processed_chunk
                        self.chat_chunk_received.emit(processed_chunk)
                        
                        if is_final_chunk:
                            stream_ended_naturally_via_final_chunk_signal = True
                            self.logger.info("Final chunk processed from stream (is_final_chunk=True received).") # Clarified log

                except LLMError as e: # MODIFIED: Catch LLMError instead of undefined LLMProcessingError
                    self.logger.error(f"LLMError while processing stream line for {self.provider.get_identifier()}: {e}", exc_info=True)
                    # MODIFIED: Use format_error_html and construct a detailed message string
                    chunk_error_details = f"处理来自 {self.provider.get_identifier()} 的流数据块时出错: {str(e)}"
                    chunk_error_message = LLMResponseFormatter.format_error_html(chunk_error_details)
                    if not self._emitted_final_for_stream: # Only send chunk error if no final message (error or not) sent
                         self.chat_error.emit(chunk_error_message) # Emit error message
                    
                    error_occurred = True 
                    # MODIFIED: Construct a single string for format_error_html
                    error_details_str = f"Provider: {self.provider.get_identifier()}, Type: StreamProcessingError, Details: Error processing a chunk from the stream: {str(e)}"
                    error_message_html = LLMResponseFormatter.format_error_html(error_details_str)
                    break 
                except Exception as e: # Generic error while processing a single chunk
                    self.logger.error(f"Generic error processing stream line for {self.provider.get_identifier()}: {e}", exc_info=True)
                    # MODIFIED: Use format_error_html and construct a detailed message string
                    generic_chunk_error_details = f"处理来自 {self.provider.get_identifier()} 的流数据块时发生一般错误: {str(e)}"
                    chunk_error_message = LLMResponseFormatter.format_error_html(generic_chunk_error_details)
                    if not self._emitted_final_for_stream:
                        self.chat_error.emit(chunk_error_message)
                    
                    error_occurred = True 
                    # MODIFIED: Construct a single string for format_error_html
                    generic_error_details_str = f"Provider: {self.provider.get_identifier()}, Type: StreamProcessingError, Details: A generic error occurred while processing a chunk: {str(e)}"
                    error_message_html = LLMResponseFormatter.format_error_html(generic_error_details_str)
                    break 
            
            # --- ADDED: Handle natural stream completion ---
            if not error_occurred and not self._cancel_requested and stream_ended_naturally_via_final_chunk_signal:
                if full_response_content and not self._emitted_final_for_stream:
                    self.logger.info("Stream ended naturally. Emitting full_response_content.")
                    self.chat_finished.emit(full_response_content)
                    self._emitted_final_for_stream = True
                elif not full_response_content and not self._emitted_final_for_stream:
                    self.logger.info("Stream ended naturally but no content accumulated. Emitting empty string for chat_finished.")
                    self.chat_finished.emit("") # Emit empty string if no content but stream finished
                    self._emitted_final_for_stream = True


            if error_occurred: # If loop was exited due to a CHUNK error (LLMProcessingError or generic Exception)
                if not self._emitted_final_for_stream: # Check before sending the overall stream error
                    self.chat_error.emit(error_message_html) # Emit error message
                    self._emitted_final_for_stream = True
            elif self._cancel_requested:
                self.logger.info("Stream thread was cancelled.")
                if full_response_content and not stream_ended_naturally_via_final_chunk_signal and not self._emitted_final_for_stream:
                    self.logger.info("Emitting partially accumulated content as final due to cancellation.")
                    self.chat_finished.emit(full_response_content) # Emit partial as final
                    self._emitted_final_for_stream = True
                else:
                    self.logger.info("Stream ended and no content accumulated, no final message to send.")


        except requests.exceptions.RequestException as e: # MODIFIED: Catch requests.exceptions.RequestException
            self.logger.error(f"RequestException in stream: {e}", exc_info=True)
            if not self._emitted_final_for_stream:
                # MODIFIED: Construct a single string for format_error_html
                error_details = f"Provider: {self.provider.get_identifier() if self.provider else 'Unknown'}, Type: {e.__class__.__name__}, Details: {str(e)}"
                error_message_html = LLMResponseFormatter.format_error_html(error_details)
                self.chat_error.emit(error_message_html)
                self._emitted_final_for_stream = True
        except LLMError as e: # Other LLM specific errors (e.g. provider not initialized, config errors)
            self.logger.error(f"LLMError in stream: {e}", exc_info=True)
            if not self._emitted_final_for_stream:
                # MODIFIED: Construct a single string for format_error_html
                error_details = f"Provider: {self.provider.get_identifier() if self.provider else 'Unknown'}, Type: {e.__class__.__name__}, Details: {str(e)}"
                error_message_html = LLMResponseFormatter.format_error_html(error_details)
                self.chat_error.emit(error_message_html)
                self._emitted_final_for_stream = True
        except Exception as e: # Catch-all for other unexpected errors
            self.logger.error(f"Unhandled exception in stream chat thread: {e}", exc_info=True)
            if not self._emitted_final_for_stream:
                # MODIFIED: Construct a single string for format_error_html
                error_details = f"Provider: {self.provider.get_identifier() if self.provider else 'N/A'}, Type: UnhandledStreamingError, Details: An unexpected error occurred: {str(e)}"
                error_message_html = LLMResponseFormatter.format_error_html(error_details)
                self.chat_error.emit(error_message_html)
                self._emitted_final_for_stream = True
        finally:
            self.logger.info(f"--- Stream Thread ENDED for provider: {self.provider.get_identifier() if self.provider else 'N/A'} --- Resetting _current_stream_thread.")
            self._current_stream_thread = None
            self.logger.info(f"--- Stream ENDED for provider: {self.provider.get_identifier() if self.provider else 'N/A'} --- Resetting _current_stream_thread.")

    def _send_chat_request(self, messages: List[Dict[str, str]]) -> str:
        """发送非流式聊天请求 (使用 Provider)"""
        if not self.provider:
             raise ConnectionError("LLM Provider not initialized.")

        messages_as_dicts = messages

        # --- Log before the API call --- Added
        self.logger.info(f"[_send_chat_request] Attempting non-stream POST to {self.provider.api_url}...")
        try:
            result_json = self.api_client.post(
                url=self.provider.api_url, # Use base api_url
                headers=self.provider.get_headers(),
                json_payload=self.provider.prepare_request_payload(messages_as_dicts, stream=False),
                timeout=self.provider._get_config_value('timeout', 120) # Use longer timeout for non-stream
            )
            # --- Log after the API call --- Added
            self.logger.info("[_send_chat_request] Non-stream POST call completed.")
        except Exception as e:
            # --- Log if the post call itself fails --- Added
            self.logger.error(f"[_send_chat_request] api_client.post failed: {e}", exc_info=True)
            raise # Re-raise the exception to be caught by the caller (LLMService.chat)
        
        # --- Log the raw response --- Added
        self.logger.debug(f"Raw non-stream response JSON: {result_json}")
        # --- End Revert ---
            
        return self.provider.parse_response(result_json)
            
    # This entire method definition replaces the old one, explicitly removing the problematic comment
    def analyze_with_custom_prompt(self, data: Dict[str, Any], custom_prompt: str, template_name: Optional[str] = None):
        """
        使用自定义提示词进行分析
        
        Args:
            data: 分析数据，包含新闻内容等信息
            custom_prompt: 自定义提示词内容
            template_name: 模板名称，用于记录日志和格式化结果
            
        Returns:
            分析结果
        """
        if not self.provider:
            self.logger.warning(f"LLM provider not configured. Returning mock analysis for custom prompt.")
            return LLMResponseFormatter.format_analysis_result(
                f"<p style='color: red;'>LLM服务未配置，无法使用自定义提示词进行分析</p>", 
                template_name or "自定义分析"
            )
        
        self.logger.info(f"使用自定义提示词进行分析，模板: {template_name or '未指定'}")
        
        # 准备提示词
        try:
            # 使用提供的自定义提示词，并进行格式化
            formatted_prompt = custom_prompt
            
            # 尝试使用数据中的变量替换占位符
            try:
                # 确保所有必要的键都存在于数据中
                format_data = {
                    'title': data.get('title', '无标题'),
                    'source': data.get('source', '未知来源'),
                    'pub_date': str(data.get('pub_date', '未知日期')),
                    'content': data.get('content', '无内容'),
                    'news_items': data.get('news_items', '')
                }
                
                # 格式化提示词
                formatted_prompt = custom_prompt.format(**format_data)
            except KeyError as e:
                self.logger.warning(f"格式化自定义提示词时出错: {e}，将使用原始提示词")
            
            # 发送请求
            headers = self.provider.get_headers()
            messages_for_payload = [{'role': 'user', 'content': formatted_prompt}]
            payload = self.provider.prepare_request_payload(
                messages=messages_for_payload,
                stream=False
            )

            # Revert to using ApiClient directly
            result_json = self.api_client.post(
                url=self.provider.api_url,
                headers=headers,
                json_payload=payload,
                timeout=self.provider._get_config_value('timeout', 60)
            )

            content = self.provider.parse_response(result_json)

            if not content:
                self.logger.warning(f"使用自定义提示词的分析返回了空内容")
                return LLMResponseFormatter.format_analysis_result(
                    "<p style='color: orange;'>分析成功，但模型未返回有效内容。</p>", 
                    template_name or "自定义分析"
                )

            # 解析结果中的重要程度和立场信息
            result = LLMResponseFormatter.extract_metrics_from_content(content)
            result['analysis'] = content
            
            return result

        except Exception as e:
            self.logger.error(f"使用自定义提示词进行分析时出错: {e}", exc_info=True)
            error_html = LLMResponseFormatter.format_error_html(f"分析时发生错误: {e}")
            return {'analysis': error_html}

    # --- Stream Control ---
    def cancel_stream(self):
        """Sets the cancel flag for the current streaming operation."""
        if self._current_stream_thread and self._current_stream_thread.is_alive():
            self.logger.info("Stream cancellation requested.")
            self._cancel_requested = True
        else:
            self.logger.debug("No active stream to cancel or thread not alive.")

    def test_connection_with_config(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """
        使用提供的配置字典测试与 LLM Provider 的连接。
        这会创建一个临时的 Provider 实例进行测试。

        Args:
            config: 包含待测试配置的字典，应包含 'name', 'api_url', 'api_key', 'model',
                    以及可选的 'temperature', 'max_tokens', 'timeout', 'provider'.

        Returns:
            一个元组 (bool, str)，表示连接是否成功以及相应的消息。
        """
        logger = self.logger  # Use instance's logger
        temp_provider: Optional[LLMProviderInterface] = None

        config_name = config.get('name')
        api_url = config.get('api_url')
        api_key_from_config = config.get('api_key') # This could be a string or list for Gemini
        model = config.get('model')
        
        # Determine provider type string
        # Use 'provider' field from config if available, otherwise infer
        provider_type_str = config.get('provider')
        if not provider_type_str:
            provider_type_str = self._determine_provider_type_string(config_name, api_url)
        
        logger.info(f"Attempting to test connection for config: '{config_name}', Provider type: '{provider_type_str}'")

        if not api_url and provider_type_str not in ['ollama']: # Ollama might not always need a URL if using a local default
            msg = f"API URL not provided for '{config_name}' (Provider: {provider_type_str})."
            logger.warning(msg)
            return False, msg
        
        if not model and provider_type_str not in ['gemini']: # Gemini model is often part of the URL path for testing
            # For many providers, model is essential for any API call, including tests.
            # However, some like Gemini, the test endpoint might be generic or model specified in URL.
            # Let's be a bit lenient here and let the provider's test logic handle it if model is missing.
            logger.debug(f"Model not explicitly provided for '{config_name}'. Provider's test logic will proceed.")


        # --- Instantiate temporary Provider ---
        try:
            # Create a temporary config for provider initialization
            # This primarily passes through settings like temperature, max_tokens, timeout
            # The core api_url, api_key, model are handled directly by the provider
            provider_init_kwargs = {
                'temperature': config.get('temperature', 0.7),
                'max_tokens': config.get('max_tokens', 2048),
                'timeout': config.get('timeout', 60) 
            }
            
            # Note: The LLMProviderInterface's __init__ expects (api_key, api_url, model, **config),
            # but specific implementations might vary slightly or handle api_key differently (e.g., Gemini with list).
            
            if provider_type_str == "google": # Gemini
                # GeminiProvider expects api_keys (plural) as List[str]
                # The api_key_from_config for Gemini should ideally be a list from the UI/ViewModel.
                # If it's a single string (e.g. from older storage or direct input), wrap it.
                keys_for_gemini = api_key_from_config
                if isinstance(api_key_from_config, str):
                    keys_for_gemini = [api_key_from_config]
                elif not isinstance(api_key_from_config, list) and api_key_from_config is not None: # Handle other unexpected types
                    logger.warning(f"Gemini test expected API key as list or string, got {type(api_key_from_config)}. Converting to list of string.")
                    keys_for_gemini = [str(api_key_from_config)]
                elif api_key_from_config is None: # No key provided
                     keys_for_gemini = []


                if not keys_for_gemini:
                     logger.warning(f"No API key(s) provided for Gemini test config '{config_name}'. Test will likely fail if key is required by endpoint.")
                
                # GeminiProvider's __init__ takes api_keys: List[str]
                # We pass the list here. The test logic inside GeminiProvider or this method might iterate.
                temp_provider = GeminiProvider(api_keys=keys_for_gemini, api_url=api_url, model=model, config=provider_init_kwargs)

            elif provider_type_str == "volcengine_ark":
                # VolcengineProvider expects api_key as a dict {'access_key': '...', 'secret_key': '...'} or a single string API Token
                # This instantiation might need to be specific if VolcengineProvider has a unique __init__
                # For testing, if its __init__ is compatible with OpenAIProvider or LLMProviderInterface base:
                logger.debug(f"Instantiating temporary provider for Volcengine (likely OpenAI compatible for test structure): {config_name}")
                temp_provider = OpenAIProvider(api_key=str(api_key_from_config) if api_key_from_config else None, api_url=api_url, model=model, config=provider_init_kwargs)

            elif provider_type_str == "ollama":
                logger.debug(f"Instantiating temporary OllamaProvider for test: {config_name}")
                # OllamaProvider's __init__ is (self, api_url: str, model: str, config: Optional[Dict[str, Any]] = None)
                temp_provider = OllamaProvider(api_url=api_url, model=model, config=provider_init_kwargs)
            
            elif provider_type_str in ["openai", "anthropic", "azure", "xai", "mistral", "fireworks", "moonshot", "baidu", "generic"]:
                logger.debug(f"Instantiating temporary provider {provider_type_str} (or OpenAI compatible) for test: {config_name}")
                # These providers generally expect a single string API key.
                if not isinstance(api_key_from_config, str) and api_key_from_config is not None:
                    logger.warning(f"Provider '{provider_type_str}' expected API key as string, got {type(api_key_from_config)}. Converting.")
                    api_key_for_provider = str(api_key_from_config)
                else:
                    api_key_for_provider = api_key_from_config

                if not api_key_for_provider and provider_type_str not in ["generic", "ollama"]: # Generic/Ollama might not need key
                    logger.warning(f"API key not provided for '{provider_type_str}' test config '{config_name}'. Test may fail if required.")

                if provider_type_str == "openai":
                    temp_provider = OpenAIProvider(api_key=api_key_for_provider, api_url=api_url, model=model, config=provider_init_kwargs)
                elif provider_type_str == "anthropic":
                    temp_provider = AnthropicProvider(api_key=api_key_for_provider, api_url=api_url, model=model, config=provider_init_kwargs)
                elif provider_type_str == "azure":
                    # Azure might need more specific config like api_base, api_version, deployment_id
                    # These should be part of the 'config' dictionary if needed by AzureProvider
                    # For now, basic instantiation:
                    azure_specific_config = config.get('azure_config', {}) # Example
                    provider_init_kwargs.update(azure_specific_config)
                    temp_provider = OpenAIProvider(api_key=api_key_for_provider, api_url=api_url, model=model, config=provider_init_kwargs)
                # Add other specific provider instantiations here if they differ significantly
                # ... XAI, Mistral, Fireworks, Moonshot, Baidu ...
                else: # Fallback to OpenAIProvider for generic compatible ones if not explicitly handled
                    logger.debug(f"Using OpenAIProvider as a base for testing '{provider_type_str}'")
                    temp_provider = OpenAIProvider(api_key=api_key_for_provider, api_url=api_url, model=model, config=provider_init_kwargs)
            else:
                msg = f"Unsupported provider type for testing: '{provider_type_str}'"
                logger.error(msg)
                return False, msg

        except Exception as e:
            msg = f"Failed to instantiate provider '{provider_type_str}' for testing: {e}"
            logger.error(msg, exc_info=True)
            return False, msg

        if not temp_provider: # Double check
             return False, f"Provider instance for '{provider_type_str}' could not be created."

        # --- Perform Test ---
        test_timeout = temp_provider._get_config_value('timeout', 60) # Use provider's configured timeout for the test call itself, or a general test timeout

        try:
            # 从 provider 获取测试连接所需的 payload
            payload = temp_provider.test_connection_payload()
            self.logger.debug(f"Provider test payload for '{config_name}': {payload}")

            test_url = temp_provider.get_test_connection_url() # USE THE NEW METHOD
            headers = temp_provider.get_headers()

            logger.info(f"Sending test request for '{config_name}' (Provider: {temp_provider.get_identifier()}) to: {test_url}")
            
            # Special handling for Gemini if it still needs to test multiple keys internally
            # For now, we assume GeminiProvider.get_test_connection_url() and get_headers() are sufficient
            # if it was initialized with a list of keys.
            # If GeminiProvider's test_connection_payload or get_test_connection_url handles key rotation, great.
            # Otherwise, specific Gemini multi-key test logic might need to be here or inside GeminiProvider.
            # For simplicity, we'll assume the provider instance itself (temp_provider) now manages how it uses its key(s) for tests.

            if temp_provider.PROVIDER_NAME == 'ollama':
                self.logger.info(f"Sending GET request for Ollama test to: {test_url}")
                response_text = self.api_client.get(
                    url=test_url,
                    headers=headers,
                    timeout=test_timeout
                )
                # For Ollama base URL check, the response_text itself is what we check.
                success = temp_provider.check_test_connection_response(response_text)
                message = f"连接成功: {response_text[:100]}..." if success else f"连接失败: 未在响应中找到预期内容。响应: {response_text[:100]}..."
            else:
                self.logger.info(f"Sending POST request for '{config_name}' (Provider: {temp_provider.PROVIDER_NAME}) to: {test_url}")
                response_json = self.api_client.post(
                    url=test_url,
                    headers=headers,
                    json_payload=payload,
                    timeout=test_timeout
                )
                success = temp_provider.check_test_connection_response(response_json)
                message = "连接测试成功。" if success else "连接测试失败: 响应内容未通过验证。"

            self.logger.info(f"Test connection for '{config_name}' result: Success={success}, Message='{message}'")
            return success, message

        except LLMError as e: # Catch errors from ApiClient.post or provider methods
            logger.error(f"LLMError during test connection for '{config_name}': {e}", exc_info=True)
            return False, f"测试连接时发生错误: {e}"
        except Exception as e:
            logger.error(f"Unexpected error during test connection for '{config_name}': {e}", exc_info=True)
            return False, f"测试连接时发生意外错误: {e}"

    def analyze_multiple_news(self, news_items: list, analysis_type: str = "多角度整合") -> str:
        """分析多条新闻，支持多种分析类型
        
        Args:
            news_items: 新闻数据列表
            analysis_type: 分析类型，如"多角度整合"、"对比分析"等
            
        Returns:
            分析结果文本
        """
        if not news_items:
            raise ValueError("新闻数据列表不能为空")
            
        if not self.provider:
            self.logger.warning(f"LLM provider not configured. Returning mock analysis for multiple news '{analysis_type}'.")
            return LLMResponseFormatter.mock_multiple_analysis(news_items, analysis_type)
            
        # 准备新闻数据文本
        news_text = ""
        for i, news in enumerate(news_items, 1):
            title = news.get('title', '')
            content = news.get('content', '')
            source = news.get('source', '')
            pub_date = news.get('publish_time', '')
            
            news_text += f"新闻 {i}:\n"
            news_text += f"标题: {title}\n"
            news_text += f"来源: {source}\n" if source else ""
            news_text += f"发布时间: {pub_date}\n" if pub_date else ""
            news_text += f"内容: {content}\n\n"
        
        # 获取提示模板
        template_name = None
        if analysis_type == "多角度整合":
            template_name = "news_similarity"
        elif analysis_type == "对比分析":
            template_name = "news_similarity"
        elif analysis_type == "事实核查":
            template_name = "fact_check"
        elif analysis_type == "时间线梳理":
            template_name = "news_similarity"
        elif analysis_type == "信源多样性分析":
            template_name = "news_similarity_enhanced"
        
        prompt_template = self.prompt_manager.load_template(template_name)
        if not prompt_template:
            self.logger.error(f"Failed to load prompt template for analysis type '{analysis_type}'")
            return LLMResponseFormatter.format_analysis_result(f"<p style='color: red;'>错误：无法加载'{analysis_type}'的提示模板。</p>", analysis_type)
        
        # 格式化提示
        prompt = prompt_template.replace("{news_items}", news_text)
        
        try:
            headers = self.provider.get_headers()
            messages_for_payload = [{'role': 'user', 'content': prompt}]
            payload = self.provider.prepare_request_payload(
                messages=messages_for_payload,
                stream=False
            )

            # Revert to using ApiClient directly
            result_json = self.api_client.post(
                url=self.provider.api_url,
                headers=headers,
                json_payload=payload,
                timeout=self.provider._get_config_value('timeout', 60)
            )

            content = self.provider.parse_response(result_json)

            if not content:
                self.logger.warning(f"LLM multiple news analysis via provider '{self.provider.get_identifier()}' returned empty content for type '{analysis_type}'.")
                return LLMResponseFormatter.format_analysis_result("<p style='color: orange;'>分析成功，但模型未返回有效内容。</p>", analysis_type)

            return LLMResponseFormatter.format_analysis_result(content, analysis_type)

        except requests.exceptions.RequestException as e:
            self.logger.error(f"LLM API request failed: {e}", exc_info=True)
            error_html = LLMResponseFormatter.format_error_html(f"请求错误: {e}")
            return error_html
        except Exception as e:
            self.logger.error(f"LLM multiple news analysis failed unexpectedly: {e}", exc_info=True)
            error_html = LLMResponseFormatter.format_error_html(f"分析时发生意外错误: {e}")
            return error_html
    
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
            
    def analyze_with_prompt(self, prompt_data: Dict, template_name: Optional[str] = None, analysis_type: Optional[str] = None):
        """使用指定的提示模板和数据进行分析
        
        Args:
            prompt_data: 提示数据字典
            template_name: 模板名称，如果为None则根据analysis_type选择
            analysis_type: 分析类型，用于在template_name为None时选择模板
            
        Returns:
            分析结果HTML
        """
        if not self.provider:
            self.logger.warning(f"LLM provider not configured. Returning mock analysis for '{analysis_type or template_name or 'custom'}'")
            return LLMResponseFormatter.format_analysis_result(
                f"<p style='color: red;'>LLM服务未配置，无法进行分析</p>", 
                analysis_type or template_name or "自定义分析")
        
        # 获取格式化的提示
        prompt = self.prompt_manager.get_formatted_prompt(
            template_name=template_name,
            data=prompt_data,
            analysis_type=analysis_type
        )
        
        if not prompt or prompt.startswith("错误："):
            self.logger.error(f"Failed to get prompt from PromptManager: {prompt}")
            return LLMResponseFormatter.format_analysis_result(f"<p style='color: red;'>{prompt}</p>", analysis_type or template_name or "自定义分析")

        try:
            headers = self.provider.get_headers()
            messages_for_payload = [{'role': 'user', 'content': prompt}]
            payload = self.provider.prepare_request_payload(
                messages=messages_for_payload,
                stream=False
            )

            # Revert to using ApiClient directly
            result_json = self.api_client.post(
                url=self.provider.api_url,
                headers=headers,
                json_payload=payload,
                timeout=self.provider._get_config_value('timeout', 60)
            )

            content = self.provider.parse_response(result_json)

            if not content:
                self.logger.warning(f"LLM analysis via provider '{self.provider.get_identifier()}' returned empty content.")
                return LLMResponseFormatter.format_analysis_result("<p style='color: orange;'>分析成功，但模型未返回有效内容。</p>", analysis_type or template_name or "自定义分析")

            return LLMResponseFormatter.format_analysis_result(content, analysis_type or template_name or "自定义分析")

        except requests.exceptions.RequestException as e:
            self.logger.error(f"LLM API request failed: {e}", exc_info=True)
            error_html = LLMResponseFormatter.format_error_html(f"请求错误: {e}")
            return error_html
        except Exception as e:
            self.logger.error(f"LLM analysis failed unexpectedly: {e}", exc_info=True)
            error_html = LLMResponseFormatter.format_error_html(f"分析时发生意外错误: {e}")
            return error_html
            
    def analyze_with_custom_prompt(self, prompt_data: Dict, custom_prompt: str):
        """使用自定义提示词进行分析
        
        Args:
            prompt_data: 提示数据字典
            custom_prompt: 自定义提示词内容
            
        Returns:
            分析结果HTML
        """
        if not self.provider:
            self.logger.warning("LLM provider not configured. Returning mock analysis for custom prompt")
            return LLMResponseFormatter.format_analysis_result(
                f"<p style='color: red;'>LLM服务未配置，无法进行分析</p>", 
                "自定义分析")
        
        # 格式化自定义提示词
        try:
            # 提取数据安全地使用.get并提供默认值
            format_data = {
                'title': prompt_data.get('title', '无标题'),
                'source': prompt_data.get('source_name', prompt_data.get('source', '未知来源')),
                'pub_date': str(prompt_data.get('pub_date', prompt_data.get('publish_time', '未知日期'))),
                'content': prompt_data.get('content', prompt_data.get('summary', prompt_data.get('description', '无内容'))),
                'news_items': prompt_data.get('news_items', '')
            }
            
            # 格式化提示词
            formatted_prompt = custom_prompt.format(**format_data)
        except KeyError as e:
            self.logger.error(f"Missing key in custom prompt for data: {e}")
            return LLMResponseFormatter.format_analysis_result(
                f"<p style='color: red;'>错误：自定义提示词格式化失败，缺少占位符 {e}</p>", 
                "自定义分析")
        except Exception as e:
            self.logger.error(f"Failed to format custom prompt: {e}")
            return LLMResponseFormatter.format_analysis_result(
                f"<p style='color: red;'>错误：自定义提示词格式化失败 - {e}</p>", 
                "自定义分析")

        try:
            headers = self.provider.get_headers()
            messages_for_payload = [{'role': 'user', 'content': formatted_prompt}]
            payload = self.provider.prepare_request_payload(
                messages=messages_for_payload,
                stream=False
            )

            # Revert to using ApiClient directly
            result_json = self.api_client.post(
                url=self.provider.api_url,
                headers=headers,
                json_payload=payload,
                timeout=self.provider._get_config_value('timeout', 60)
            )

            content = self.provider.parse_response(result_json)

            if not content:
                self.logger.warning(f"LLM analysis with custom prompt via provider '{self.provider.get_identifier()}' returned empty content.")
                return LLMResponseFormatter.format_analysis_result("<p style='color: orange;'>分析成功，但模型未返回有效内容。</p>", "自定义分析")

            return LLMResponseFormatter.format_analysis_result(content, "自定义分析")

        except requests.exceptions.RequestException as e:
            self.logger.error(f"LLM API request failed: {e}", exc_info=True)
            error_html = LLMResponseFormatter.format_error_html(f"请求错误: {e}")
            return error_html
        except Exception as e:
            self.logger.error(f"LLM analysis failed unexpectedly: {e}", exc_info=True)
            error_html = LLMResponseFormatter.format_error_html(f"分析时发生意外错误: {e}")
            return error_html