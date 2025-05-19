import json
import logging
from typing import List, Dict, Optional, Union, Any

from .base import LLMProviderInterface, ProviderConfig

logger = logging.getLogger('news_analyzer.llm.provider.openai')

class OpenAIProvider(LLMProviderInterface):
    """
    LLM Provider implementation for OpenAI and compatible APIs
    (e.g., X-AI, Mistral, Fireworks, Generic OpenAI-like endpoints).
    """
    PROVIDER_NAME = "openai_compatible"

    def __init__(self, api_key: str, api_url: str, model: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(api_key, api_url, model)

    def get_identifier(self) -> str:
        # Use a generic identifier as this class handles multiple OpenAI-like APIs
        # The specific type differentiation (like 'xai', 'mistral') happens
        # during provider selection based on config name or URL,
        # but the interaction logic is the same for this class.
        return "openai_compatible"

    def get_headers(self) -> Dict[str, str]:
        """Returns headers for OpenAI-compatible APIs."""
        if not self.api_key:
            logger.warning(f"API key is missing for provider '{self.get_identifier()}'. Request might fail.")
            return {'Content-Type': 'application/json'}
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

    def prepare_request_payload(self, messages: List[Dict[str, str]], stream: bool, **kwargs) -> Dict[str, Any]:
        """Prepares the JSON payload for OpenAI-compatible APIs."""
        payload = {
            'model': self.model,
            'messages': messages,
            'stream': stream
        }
        # Add optional parameters from config if they exist
        temperature = self._get_config_value('temperature')
        if temperature is not None:
            payload['temperature'] = temperature

        max_tokens = self._get_config_value('max_tokens')
        if max_tokens is not None:
            payload['max_tokens'] = max_tokens

        # Allow overriding specific parameters via kwargs if needed
        payload.update(kwargs)

        return payload

    def parse_response(self, response_data: Dict[str, Any]) -> str:
        """Parses the content from a non-streaming OpenAI-compatible response."""
        try:
            content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
            if content is None: # Handle null content explicitly
                 logger.warning(f"Provider '{self.get_identifier()}' received null content in response.")
                 return ""
            return content.strip()
        except (IndexError, KeyError, TypeError) as e:
            logger.error(f"Failed to extract content from '{self.get_identifier()}' response: {e}. Response: {response_data}", exc_info=True)
            return ""

    def process_stream_line(self, chunk_data: Union[str, bytes]) -> tuple[Optional[str], bool]:
        """Parses a single line from an OpenAI-compatible SSE stream.

        Returns:
            A tuple containing the text content (if any) and a boolean indicating if this is the final chunk.
        """
        if isinstance(chunk_data, bytes):
            try:
                decoded_chunk = chunk_data.decode('utf-8').strip()
            except UnicodeDecodeError:
                logger.warning(f"Failed to decode stream chunk as UTF-8: {chunk_data!r}")
                return None, False
        else:
            decoded_chunk = chunk_data.strip()

        if not decoded_chunk:  # Ignore empty lines
            return None, False

        if decoded_chunk == self.get_stream_stop_signal():
            logger.debug("Received SSE stop signal [DONE].")
            return None, True # Final chunk signal

        if decoded_chunk.startswith("data: "):
            json_str = decoded_chunk[len("data: "):].strip()
            if json_str == self.get_stream_stop_signal(): # Should be caught above, but defensive
                logger.debug("Received SSE stop signal [DONE] after data prefix.")
                return None, True # Final chunk signal
        else:
            logger.warning(f"Received unexpected SSE chunk format (not [DONE] and no 'data:' prefix): {decoded_chunk!r}")
            return None, False # Invalid chunk, not final

        if not json_str:
            # logger.debug("Received empty data chunk after prefix removal.")
            return "", False # Empty delta, not final

        logger.debug(f"Attempting to parse JSON string: {json_str!r}")
        try:
            data = json.loads(json_str)
            delta = data.get('choices', [{}])[0].get('delta', {})
            content = delta.get('content')
            return content if content is not None else "", False # Return content or empty string, not final
        except (json.JSONDecodeError, IndexError, KeyError, TypeError) as e:
            logger.warning(f"Error parsing '{self.get_identifier()}' SSE JSON: {e}. JSON String: {json_str!r}")
            return None, False # Error, not final

    def get_stream_stop_signal(self) -> Optional[str]:
        """Returns the stop signal for OpenAI SSE streams."""
        return "[DONE]"

    def test_connection_payload(self) -> Dict[str, Any]:
        """Returns a minimal payload for testing OpenAI-compatible connections."""
        return {
            'model': self.model,
            'messages': [{'role': 'user', 'content': 'Say "Hello"'}],
            'max_tokens': 5
        }

    def check_test_connection_response(self, response_data: Dict[str, Any]) -> bool:
        """Checks if the test connection response for OpenAI-compatible APIs is valid."""
        # Check if 'choices' key exists and is a list (even if empty)
        return 'choices' in response_data and isinstance(response_data.get('choices'), list)