import json
import logging
from typing import List, Dict, Optional, Union, Any

from .base import LLMProviderInterface

logger = logging.getLogger('news_analyzer.llm.provider.ollama')

class OllamaProvider(LLMProviderInterface):
    """LLM Provider implementation for Ollama API."""

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

    def parse_stream_chunk(self, chunk_data: Union[str, bytes]) -> Optional[str]:
        """Parses a single chunk from an Ollama stream (/api/chat)."""
        # Ollama stream returns JSON objects line by line
        if isinstance(chunk_data, bytes):
            try:
                decoded_chunk = chunk_data.decode('utf-8').strip()
            except UnicodeDecodeError:
                logger.warning(f"Failed to decode stream chunk as UTF-8: {chunk_data!r}")
                return None
        else:
            decoded_chunk = chunk_data.strip()

        if not decoded_chunk:
            return None

        try:
            data = json.loads(decoded_chunk)
            # Check if the stream is done
            if data.get('done', False):
                return None # Signal end implicitly by returning None

            # Extract content from message.content
            content = data.get('message', {}).get('content')

            # Fallback for older stream format using 'response'
            if content is None and 'response' in data:
                 content = data.get('response')

            return content if content is not None else "" # Return empty string if key exists but content is null/empty

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Error parsing '{self.get_identifier()}' stream chunk: {e}. Data: {decoded_chunk}")
            return None

    def get_stream_stop_signal(self) -> Optional[str]:
        """Ollama stream indicates stop with 'done: true' in the JSON chunk."""
        # The parsing logic in parse_stream_chunk handles this by returning None.
        return None # No specific data string signal

    def test_connection_payload(self) -> Dict[str, Any]:
        """Returns a minimal payload for testing Ollama connections (/api/chat)."""
        # Using /api/chat for testing consistency
        return {
            'model': self.model,
            'messages': [{'role': 'user', 'content': 'Say "Hello"'}],
            'stream': False,
            'options': {'num_predict': 5} # Limit output for test
        }

    def check_test_connection_response(self, response_data: Dict[str, Any]) -> bool:
        """Checks if the test connection response for Ollama API is valid."""
        # A successful non-streaming /api/chat response should contain a 'message' object
        # or fallback 'response' key for older versions.
        has_message = 'message' in response_data and isinstance(response_data.get('message'), dict)
        has_response_fallback = 'response' in response_data # Check for older format
        return has_message or has_response_fallback