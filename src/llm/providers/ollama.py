import json
import logging
from typing import List, Dict, Optional, Union, Any

from .base import LLMProviderInterface

logger = logging.getLogger('news_analyzer.llm.provider.ollama')

class OllamaProvider(LLMProviderInterface):
    """LLM Provider implementation for Ollama API."""
    PROVIDER_NAME = "ollama"

    def __init__(self, api_url: str, model: str, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        # Ollama doesn't use an API key in the traditional sense for local instances.
        # We accept api_key for consistency but always pass api_key=None to the superclass constructor.
        # The actual 'config' dict (like temperature, timeout) is passed to super's config.
        super().__init__(api_key=None, api_url=api_url, model=model, config=config)
        logger.debug(f"OllamaProvider initialized for model: {model} at URL: {api_url}. API key param was present but ignored. Config: {config}")

    def get_identifier(self) -> str:
        return "ollama"

    def get_headers(self) -> Dict[str, str]:
        """Ollama typically doesn't require authentication headers."""
        return {'Content-Type': 'application/json'}

    def prepare_request_payload(self, messages: List[Dict[str, str]], stream: bool, **kwargs) -> Dict[str, Any]:
        """Prepares the JSON payload for Ollama API."""
        # Ollama's /api/chat endpoint (newer versions) accepts 'messages' format similar to OpenAI.
        # Older versions might only accept /api/generate with a single 'prompt'.
        # We'll primarily target the /api/chat format.
        payload = {
            'model': self.model,
            'messages': messages, # Use messages format
            'stream': stream
        }

        # Add optional parameters under 'options'
        options = {}
        temperature = self._get_config_value('temperature')
        if temperature is not None:
            options['temperature'] = temperature

        # Ollama uses 'num_predict' for max tokens in non-streaming,
        # but it might be ignored or behave differently in streaming.
        # We include it based on the original code's logic for non-streaming.
        if not stream:
            max_tokens = self._get_config_value('max_tokens')
            if max_tokens is not None:
                # Ollama calls it num_predict
                options['num_predict'] = max_tokens

        if options:
            payload['options'] = options

        # Allow overriding via kwargs
        payload.update(kwargs)
        return payload

    def parse_response(self, response_data: Dict[str, Any]) -> str:
        """Parses the content from a non-streaming Ollama response (/api/chat)."""
        try:
            # Newer Ollama /api/chat non-streaming response puts content in message.content
            content = response_data.get('message', {}).get('content', '')
            # Fallback for older /api/generate non-streaming response
            if not content and 'response' in response_data:
                 content = response_data.get('response', '')
            return content.strip()
        except (KeyError, TypeError) as e:
            logger.error(f"Failed to extract content from '{self.get_identifier()}' response: {e}. Response: {response_data}", exc_info=True)
            return ""

    def process_stream_line(self, chunk_data: Union[str, bytes]) -> tuple[Optional[str], bool]:
        """Parses a single chunk from an Ollama stream (/api/chat) and indicates if it's the final chunk."""
        # Ollama stream returns JSON objects line by line
        if isinstance(chunk_data, bytes):
            try:
                decoded_chunk = chunk_data.decode('utf-8').strip()
            except UnicodeDecodeError:
                logger.warning(f"Failed to decode stream chunk as UTF-8: {chunk_data!r}")
                return None, False # Not final if error occurs mid-stream typically
        else:
            decoded_chunk = chunk_data.strip()

        if not decoded_chunk:
            return None, False # Empty line, not final

        try:
            data = json.loads(decoded_chunk)
            is_done = data.get('done', False)
            
            # Extract content from message.content
            content_obj = data.get('message', {})
            content = None
            if isinstance(content_obj, dict): # Ensure message is a dict before .get()
                content = content_obj.get('content')

            # Fallback for older stream format using 'response'
            if content is None and 'response' in data:
                 content = data.get('response')

            # If 'done' is true, this is the final chunk. It might or might not have content.
            # Return the content (even if None or empty if that's what provider sends on 'done') and True for is_final.
            if is_done:
                return (content if content is not None else ""), True 
            else:
                # If not done, return the content (or empty string if no content key but not done)
                return (content if content is not None else ""), False

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Error parsing '{self.get_identifier()}' stream chunk: {e}. Data: {decoded_chunk}")
            return None, False # Error parsing, assume not final

    def get_stream_stop_signal(self) -> Optional[str]:
        """Ollama stream indicates stop with 'done: true' in the JSON chunk."""
        # The parsing logic in process_stream_line handles this by returning None.
        return None # No specific data string signal

    def check_test_connection_response(self, response_data: Any) -> bool:
        """Checks if the test connection response for Ollama API is valid.
        For a GET request to the base URL, expects 'Ollama is running'.
        The response_data here will be the raw text from the response.
        """
        if isinstance(response_data, str):
            is_valid = "Ollama is running" in response_data
            logger.debug(f"Checking Ollama test connection response (raw text). Valid: {is_valid}. Response text snippet: {response_data[:100]}")
            return is_valid
        
        # Fallback for older way if response_data was accidentally parsed as JSON (though it shouldn't be for this new test)
        elif isinstance(response_data, dict): # Should not happen for base URL GET
            logger.warning("Ollama check_test_connection_response received a dict, expecting raw string. This indicates a potential issue in request type.")
            # A successful non-streaming /api/chat response should contain a 'message' object
            # or fallback 'response' key for older versions. This logic is kept as a safeguard.
            has_message = 'message' in response_data and isinstance(response_data.get('message'), dict)
            has_response_fallback = 'response' in response_data # Check for older format
            return has_message or has_response_fallback
        
        logger.error(f"Ollama check_test_connection_response received unexpected data type: {type(response_data)}")
        return False

    def get_test_connection_url(self) -> str:
        """Ollama test should go to the base API URL."""
        return self.api_url.rstrip('/')

    def test_connection_payload(self) -> Optional[Dict[str, Any]]:
        """No payload needed for a GET request to the base Ollama URL."""
        return None

    @property
    def chat_generate_url(self) -> str:
        return f"{self.api_url.rstrip('/')}/api/chat"