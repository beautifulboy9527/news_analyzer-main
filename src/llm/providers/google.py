"""
Provider implementation for Google AI Gemini models.
"""
import logging
import json
from typing import Dict, Any, Optional, List, Iterator, Tuple
import time # Import time for potential backoff in retries (optional)

import requests # Ensure requests is imported

from .base import LLMProviderInterface, ProviderConfig
from src.utils.api_client import ApiClient # Assuming ApiClient is needed
from src.llm.formatter import LLMResponseFormatter # For error formatting
from src.llm.exception import LLMError # Only import base error

logger = logging.getLogger(__name__)

class GeminiProvider(LLMProviderInterface):
    """
    LLM Provider for Google Gemini models via the REST API.
    Handles both standard and streaming content generation.
    """

    PROVIDER_NAME = "google"
    # Define chat stream URL structure based on API docs
    # Example: v1beta/models/gemini-pro:streamGenerateContent?key=YOUR_API_KEY
    CHAT_STREAM_URL_TEMPLATE = "{api_url}/v1beta/models/{model}:streamGenerateContent?key={api_key}"
    # Define non-streaming URL structure
    # Example: v1beta/models/gemini-pro:generateContent?key=YOUR_API_KEY
    CHAT_URL_TEMPLATE = "{api_url}/v1beta/models/{model}:generateContent?key={api_key}"
    # Define retryable HTTP status codes
    RETRYABLE_STATUS_CODES = {400, 403, 429, 408} # Codes GeminiProvider itself will try to rotate key on

    # --- ADDED: Constants for new retry logic ---
    MAX_POLLING_CYCLES = 3  # How many times to retry the entire key rotation process
    POLLING_CYCLE_BASE_DELAY_SECONDS = 5  # Base delay in seconds for retries between polling cycles
    # --- END ADDED ---

    def __init__(self, api_keys: List[str], api_url: str, model: str, config: Dict[str, Any]):
        # Initialize GeminiProvider specific attributes first
        if not api_keys:
            raise ValueError("GeminiProvider requires a non-empty list of API keys.")
        self.api_keys = api_keys  # Store the list of keys
        self._current_key_index = 0
        
        # Get the first key for the base class constructor
        # The self.api_key attribute in GeminiProvider will be kept in sync by _rotate_key and this initial set.
        self.api_key = self._get_current_key() 
        
        # Call super().__init__ with a single API key (self.api_key), api_url, and model.
        # The base class (LLMProviderInterface) __init__ will set its own self.api_key, self.api_url, self.model.
        super().__init__(self.api_key, api_url, model)

        # Initialize logger for this provider instance
        self.logger = logging.getLogger(f'news_analyzer.llm.provider.gemini.{model}')
        self.logger.info(f"--- GeminiProvider.__init__: Initializing with model='{model}', api_url='{api_url}', num_keys={len(self.api_keys)}")
        
        # Store other config values specific to GeminiProvider, from the passed 'config' dict
        self._temperature = config.get('temperature', 0.7) # Default from base or specific
        self._max_tokens = config.get('max_tokens') # Gemini uses maxOutputTokens, handle in prepare_payload
        self._timeout = config.get('timeout', 60)
        
        self.logger.info(f"GeminiProvider initialized for model '{self.model}'. Key count: {len(self.api_keys)}")
        self.logger.debug(f"  Configured Temp: {self._temperature}, MaxTokens: {self._max_tokens}, Timeout: {self._timeout}")

    # --- Key Rotation Methods --- Added
    def _get_current_key(self) -> str:
        """Gets the currently active API key."""
        return self.api_keys[self._current_key_index]

    def _rotate_key(self) -> bool:
        """Rotates to the next API key, returning True if successful, False if wrapped around."""
        initial_index = self._current_key_index
        self._current_key_index = (self._current_key_index + 1) % len(self.api_keys)
        self.api_key = self._get_current_key() # Update the base class attribute if needed
        logger.debug(f"Rotated Gemini key from index {initial_index} to {self._current_key_index}")
        return self._current_key_index != 0 # Returns False if we are back at the start

    def get_identifier(self) -> str:
        return f"{self.PROVIDER_NAME}:{self.model}"

    def get_headers(self) -> Dict[str, str]:
        # Gemini uses API key in URL, standard headers are sufficient
        return {
            'Content-Type': 'application/json',
        }

    def prepare_request_payload(self, messages: List[Dict[str, str]], stream: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Prepare the payload for the Gemini API.
        Gemini uses 'contents' instead of 'messages'.
        It also has a different role mapping ('model' instead of 'assistant').
        """
        processed_contents = []
        system_instruction = None
        first_user_message_processed = False

        # Extract system prompt if present (Gemini handles it separately)
        if messages and messages[0]['role'] == 'system':
            system_instruction = {"role": "system", "parts": [{"text": messages[0]['content']}]}
            messages = messages[1:]
            
        # Convert remaining messages to Gemini 'contents' format
        for msg in messages:
            role = msg.get('role')
            content = msg.get('content')
            if not role or not content:
                continue
                
            # Map roles: user -> user, assistant -> model
            gemini_role = "user" if role == "user" else "model"
            
            if role == "system" and not first_user_message_processed:
                # Prepend system instruction to the first user message content
                content = f"{system_instruction['parts'][0]['text']}\\n\\n{content}"
                system_instruction = None # Clear it after use
                first_user_message_processed = True
            
            processed_contents.append({
                "role": gemini_role,
                "parts": [{"text": content}]
            })

        payload = {
            "contents": processed_contents,
            "generationConfig": {
                "temperature": self._temperature,
                "maxOutputTokens": self._max_tokens,
            },
            # Add safety settings if needed
            # "safetySettings": [...] 
        }

        # Add system instruction if extracted
        if system_instruction:
             payload["systemInstruction"] = system_instruction
             
        logger.debug(f"Gemini Payload Prepared (stream={stream}): {payload}")
        return payload

    def parse_response(self, response_data: Dict[str, Any]) -> str:
        """
        Parse the standard (non-streaming) response from Gemini API.
        """
        # --- ADD RAW RESPONSE LOGGING --- Added
        logger.debug(f"Raw Gemini response received: {response_data}")
        # --- End RAW RESPONSE LOGGING ---
        try:
            # Extract text from the first candidate's content parts
            candidates = response_data.get('candidates', [])
            if candidates:
                content = candidates[0].get('content', {})
                parts = content.get('parts', [])
                if parts:
                    # Concatenate text from all parts
                    full_text = "".join(part.get('text', '') for part in parts)
                    logger.debug(f"Parsed Gemini response text (length={len(full_text)})")
                    return full_text.strip()
            
            # Handle potential finish reasons like safety blocks
            finish_reason = candidates[0].get('finishReason', 'UNKNOWN') if candidates else 'UNKNOWN'
            safety_ratings = candidates[0].get('safetyRatings', []) if candidates else []
            if finish_reason != 'STOP':
                 logger.warning(f"Gemini response finished with reason: {finish_reason}. Safety: {safety_ratings}")
                 # Return an informative message if blocked
                 if finish_reason == 'SAFETY':
                     return "[响应因安全设置被阻止]"
                 if finish_reason == 'RECITATION':
                      return "[响应因疑似引用受保护内容被阻止]"
                 # Add other reasons if needed
                 
            logger.warning(f"Could not extract text from Gemini response. Finish Reason: {finish_reason}. Data: {response_data}")
            return "[未能从响应中提取有效内容]"
            
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Error parsing Gemini response: {e}. Data: {response_data}", exc_info=True)
            return f"[解析响应时出错: {e}]"
            
    def process_stream_line(self, chunk_str: str) -> Tuple[Optional[str], bool]:
        """
        Parse a chunk string from the Gemini streaming API (Server-Sent Events).
        Returns the text content and a boolean indicating if this is the final chunk.
        Assumes input is a decoded string from an SSE data field.
        """
        processed_line = chunk_str.strip()
        logger.debug(f"Raw Gemini stream line received: {processed_line!r}")

        # Gemini stream is expected to be a series of JSON objects, possibly prefixed with "data: "
        # The httpx-sse client should ideally handle the "data: " prefix removal.
        # However, if raw lines are passed, we might need to handle it here.
        # For now, assume chunk_str is the JSON payload itself or prefixed with "data: ".
        
        actual_json_str = processed_line
        if processed_line.startswith('data: '):
            actual_json_str = processed_line[len('data: '):].strip()

        if not actual_json_str:
            # This can happen if the line was just "data: " or an empty line after stripping prefix
            logger.debug("Received empty JSON string after stripping 'data: ' prefix, or empty line.")
            return None, False # Not an error, but no content and not final.

        try:
            data = json.loads(actual_json_str)
            logger.debug(f"Parsed Gemini stream JSON: {data}")
            
            text_content: Optional[str] = None
            is_final_chunk = False

            candidates = data.get('candidates', [])
            if candidates:
                candidate = candidates[0]
                # Extract text content
                content_parts = candidate.get('content', {}).get('parts', [])
                if content_parts:
                    text_content = "".join(part.get('text', '') for part in content_parts if 'text' in part)
                
                # Check for finish reason
                finish_reason = candidate.get('finishReason')
                if finish_reason:
                    is_final_chunk = True # Any finishReason indicates the end of this candidate's stream part
                    logger.debug(f"Gemini stream candidate finished with reason: {finish_reason}. Safety: {candidate.get('safetyRatings')}")
                    # Handle specific non-STOP reasons by appending to text_content or logging
                    if finish_reason == 'SAFETY':
                        safety_message = "\n[响应因安全设置被阻止]"
                        text_content = (text_content + safety_message) if text_content else safety_message
                    elif finish_reason == 'RECITATION':
                        recitation_message = "\n[响应因疑似引用受保护内容被阻止]"
                        text_content = (text_content + recitation_message) if text_content else recitation_message
                    elif finish_reason not in ['STOP', 'MAX_TOKENS']: # MAX_TOKENS is also a valid stop, but might not be "error"
                         logger.warning(f"Gemini stream finished with non-standard reason: {finish_reason}")
            else:
                # This might be a chunk without candidates, e.g. prompt feedback
                prompt_feedback = data.get('promptFeedback')
                if prompt_feedback:
                    logger.info(f"Received Gemini prompt feedback: {prompt_feedback}")
                    # Check if this feedback implies stream end, though typically finishReason in candidates does.
                    # For now, assume promptFeedback itself doesn't inherently signal the *final* text chunk unless accompanied by finishReason.
                    # If it can, is_final_chunk logic would need adjustment.
                    block_reason = prompt_feedback.get('blockReason')
                    if block_reason:
                        logger.warning(f"Gemini prompt blocked. Reason: {block_reason}")
                        text_content = f"\n[请求因 {block_reason} 被阻止]"
                        is_final_chunk = True # A blocked prompt is a final state for this request.
                else:
                    logger.warning(f"Gemini stream chunk has no candidates and no recognized prompt feedback: {data}")

            return text_content, is_final_chunk
            
        except json.JSONDecodeError:
            logger.warning(f"Failed to decode JSON from Gemini stream line: {actual_json_str!r}")
            return None, False # Error, not final
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Error processing Gemini stream JSON: {e}. Data: {actual_json_str!r}", exc_info=False)
            return None, False # Error, not final

    def get_stream_stop_signal(self) -> Optional[str]:
        # Gemini stream doesn't use a simple stop signal like some others.
        # It indicates stop via the 'finishReason' in the final JSON chunk.
        return None 

    def test_connection_payload(self) -> Dict[str, Any]:
        """Payload for a simple connection test."""
        # Try a very minimal payload, some APIs are picky.
        # Ensure the text is not empty or too trivial.
        return {
             "contents": [{"role": "user", "parts": [{"text": "Hello. Please respond with a single word."}]}]
             # Temporarily remove generationConfig to see if it's the cause
             # "generationConfig": {"maxOutputTokens": 1}
        }
        
    def check_test_connection_response(self, response_data: Dict[str, Any]) -> bool:
        """Check if the test connection response is valid."""
        # Check if 'candidates' array exists, indicating a successful response structure
        is_valid = 'candidates' in response_data
        logger.debug(f"Checking test connection response. Valid: {is_valid}. Response: {response_data}")
        return is_valid

    # --- ADDED: Override get_test_connection_url ---
    def get_test_connection_url(self) -> str:
        """Returns the URL for non-streaming content generation (used for tests)."""
        current_key = self._get_current_key()
        # Ensure api_url doesn't have trailing slash before formatting,
        # and CHAT_URL_TEMPLATE starts appropriately or handles it.
        # Example: self.api_url is "https://generativelanguage.googleapis.com"
        # CHAT_URL_TEMPLATE is "{api_url}/v1beta/models/{model}:generateContent?key={api_key}"
        return self.CHAT_URL_TEMPLATE.format(
            api_url=self.api_url.rstrip('/'), 
            model=self.model,
            api_key=current_key
        )
    # --- END ADDED ---

    # --- Specific methods for chat URL construction ---
    @property
    def chat_generate_url(self) -> str:
        # --- Modified: Use current key directly, don't rotate here ---
        return self.CHAT_URL_TEMPLATE.format(
            api_url=self.api_url.rstrip('/'), model=self.model, api_key=self.api_key
        )
        # --- End Modified ---
        
    @property
    def chat_stream_url(self) -> str:
        # --- Modified: Use current key directly, don't rotate here ---
        return self.CHAT_STREAM_URL_TEMPLATE.format(
            api_url=self.api_url.rstrip('/'), model=self.model, api_key=self.api_key
        )
        # --- End Modified ---
        
    # Override _send_chat_request to use the correct URL AND implement retry/rotation
    def _send_chat_request(self, api_client: ApiClient, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Sends a non-streaming chat request using ApiClient with multi-cycle key rotation and retry logic."""
        headers = self.get_headers()
        payload = self.prepare_request_payload(messages, stream=False)
        
        last_error_from_any_cycle: Optional[LLMError] = None

        for polling_cycle_num in range(self.MAX_POLLING_CYCLES):
            self.logger.info(f"GeminiProvider: Starting polling cycle {polling_cycle_num + 1}/{self.MAX_POLLING_CYCLES} for non-streaming request.")
            
            # Reset to the first key for this new polling cycle
            self._current_key_index = 0
            self.api_key = self._get_current_key() # Ensure self.api_key (used by chat_generate_url) is updated
            
            initial_key_index_this_cycle = self._current_key_index
            
            # Inner loop: Try each key once within this polling cycle
            # Loop will break if a key succeeds, or if all keys in this cycle are tried.
            while True: 
                current_key_for_attempt = self._get_current_key() # Get current key for logging/debugging
                url = self.chat_generate_url # Property uses self.api_key which is self._get_current_key() via _rotate_key or init
                
                self.logger.debug(f"Polling Cycle {polling_cycle_num + 1}, Key Index {self._current_key_index} (Key ending ...{current_key_for_attempt[-6:]}): Attempting POST to ...{url[-40:]}")

                try:
                    response_data = api_client.post(
                        url=url, 
                        headers=headers, 
                        json_payload=payload, 
                        timeout=self._timeout,
                        fast_fail_on_status_codes=[429, 403, 400] # GeminiProvider wants to handle these by rotating key
                    )
                    self.logger.info(f"Polling Cycle {polling_cycle_num + 1}, Key Index {self._current_key_index}: Successfully sent non-streaming request.")
                    return response_data # SUCCESS
                except LLMError as e:
                    self.logger.warning(f"Polling Cycle {polling_cycle_num + 1}, Key Index {self._current_key_index}: LLMError (Status: {e.status_code}) - {e.message}")
                    last_error_from_any_cycle = e # Store this error

                    if e.status_code in self.RETRYABLE_STATUS_CODES:
                        # Attempt to rotate to the next key
                        self._rotate_key() # This updates self._current_key_index and self.api_key

                        # Check if we've tried all keys in this current polling cycle
                        if self._current_key_index == initial_key_index_this_cycle:
                            self.logger.warning(f"Polling Cycle {polling_cycle_num + 1}: All keys tried. Last error for this cycle: {e.message}")
                            break # Exit inner `while True` loop (key rotation for this cycle)
                        else:
                            self.logger.info(f"Rotated to key index {self._current_key_index}. Retrying in current polling cycle.")
                            # Continue to the next iteration of the inner `while True` loop (next key)
                    else: # Non-retryable LLMError (not in GeminiProvider's RETRYABLE_STATUS_CODES)
                        self.logger.error(f"Polling Cycle {polling_cycle_num + 1}: Non-retryable LLMError status {e.status_code} encountered. Failing operation: {e.message}")
                        raise e # Fail the entire operation immediately
                except Exception as e_unhandled: # Catch any other unexpected exceptions
                    self.logger.error(f"Polling Cycle {polling_cycle_num + 1}, Key Index {self._current_key_index}: Unexpected error: {e_unhandled}", exc_info=True)
                    last_error_from_any_cycle = LLMError(f"Unexpected error during non-streaming request: {e_unhandled}")
                    # Assume unexpected errors mean this key/cycle fails, try next cycle if available
                    break # Exit inner `while True` loop

            # End of inner `while True` loop (one full key rotation for this polling_cycle_num completed or non-retryable error)
            # If we are here, it means the inner loop completed without returning a success.
            
            if polling_cycle_num < self.MAX_POLLING_CYCLES - 1: # If there are more polling cycles left
                delay = self.POLLING_CYCLE_BASE_DELAY_SECONDS * (2 ** polling_cycle_num)
                self.logger.info(f"Polling Cycle {polling_cycle_num + 1} failed. Delaying {delay}s before next cycle.")
                time.sleep(delay)
            else: # All polling cycles are exhausted
                self.logger.error(f"All {self.MAX_POLLING_CYCLES} polling cycles failed for non-streaming request.")
                if last_error_from_any_cycle:
                    raise LLMError(
                        f"非流式请求失败，所有API密钥在 {self.MAX_POLLING_CYCLES} 轮尝试后均失败。最后错误: {last_error_from_any_cycle.message}", 
                        status_code=last_error_from_any_cycle.status_code
                    ) from last_error_from_any_cycle
                else: # Should ideally not happen if at least one attempt was made
                    raise LLMError(f"非流式请求失败，所有API密钥在 {self.MAX_POLLING_CYCLES} 轮尝试后均失败，且未记录特定错误。")
        
        # Should be logically unreachable due to return on success or raise on failure after all cycles
        raise LLMError("GeminiProvider _send_chat_request logic error: exited loops without success or definitive failure.")

    # Override _stream_chat_response to use the correct URL AND implement retry/rotation
    def _stream_chat_response(self, api_client: ApiClient, messages: List[Dict[str, str]]) -> Iterator[bytes]:
        """Handles the streaming chat response using ApiClient with multi-cycle key rotation and retry logic for initial connection."""
        headers = self.get_headers()
        payload = self.prepare_request_payload(messages, stream=True)
        
        last_error_from_any_cycle: Optional[LLMError] = None

        for polling_cycle_num in range(self.MAX_POLLING_CYCLES):
            self.logger.info(f"GeminiProvider: Starting polling cycle {polling_cycle_num + 1}/{self.MAX_POLLING_CYCLES} for streaming request.")
            
            self._current_key_index = 0
            self.api_key = self._get_current_key()
            initial_key_index_this_cycle = self._current_key_index
            
            while True:
                current_key_for_attempt = self._get_current_key()
                url = self.chat_stream_url
                self.logger.debug(f"Polling Cycle {polling_cycle_num + 1}, Key Index {self._current_key_index} (Key ending ...{current_key_for_attempt[-6:]}): Attempting stream POST to ...{url[-40:]}")

                try:
                    stream_iterator = api_client.stream_post(
                        url=url, 
                        headers=headers, 
                        json_payload=payload, 
                        timeout=self._timeout,
                        fast_fail_on_status_codes=[429, 403, 400] # Codes for fast fail
                    )
                    self.logger.info(f"Polling Cycle {polling_cycle_num + 1}, Key Index {self._current_key_index}: Stream connection initiated. Yielding iterator.")
                    yield from stream_iterator # If connection is successful, yield from it.
                    self.logger.info(f"Polling Cycle {polling_cycle_num + 1}, Key Index {self._current_key_index}: Successfully finished yielding stream.")
                    return # SUCCESS
                except LLMError as e: # Errors from ApiClient.stream_post during connection
                    self.logger.warning(f"Polling Cycle {polling_cycle_num + 1}, Key Index {self._current_key_index}: LLMError (Status: {e.status_code}) during stream connection - {e.message}")
                    last_error_from_any_cycle = e

                    if e.status_code in self.RETRYABLE_STATUS_CODES:
                        self._rotate_key()
                        if self._current_key_index == initial_key_index_this_cycle:
                            self.logger.warning(f"Polling Cycle {polling_cycle_num + 1}: All keys tried for stream connection. Last error: {e.message}")
                            break 
                        else:
                            self.logger.info(f"Rotated to key index {self._current_key_index} for stream. Retrying connection in current polling cycle.")
                    else:
                        self.logger.error(f"Polling Cycle {polling_cycle_num + 1}: Non-retryable LLMError status {e.status_code} for stream. Failing operation: {e.message}")
                        raise e
                except Exception as e_unhandled: # Catch any other unexpected exceptions
                    self.logger.error(f"Polling Cycle {polling_cycle_num + 1}, Key Index {self._current_key_index}: Unexpected error during stream connection: {e_unhandled}", exc_info=True)
                    last_error_from_any_cycle = LLMError(f"Unexpected error during stream connection: {e_unhandled}")
                    break # Exit inner `while True` loop

            # End of inner `while True` loop for stream connection attempts in this cycle
            if polling_cycle_num < self.MAX_POLLING_CYCLES - 1:
                delay = self.POLLING_CYCLE_BASE_DELAY_SECONDS * (2 ** polling_cycle_num)
                self.logger.info(f"Polling Cycle {polling_cycle_num + 1} for stream failed. Delaying {delay}s.")
                time.sleep(delay)
            else:
                self.logger.error(f"All {self.MAX_POLLING_CYCLES} polling cycles failed for streaming request.")
                if last_error_from_any_cycle:
                    raise LLMError(
                        f"流式请求失败，所有API密钥在 {self.MAX_POLLING_CYCLES} 轮尝试后均失败。最后错误: {last_error_from_any_cycle.message}", 
                        status_code=last_error_from_any_cycle.status_code
                    ) from last_error_from_any_cycle
                else:
                    raise LLMError(f"流式请求失败，所有API密钥在 {self.MAX_POLLING_CYCLES} 轮尝试后均失败，且未记录特定错误。")
        
        raise LLMError("GeminiProvider _stream_chat_response logic error: exited loops without success or definitive failure.")

# Helper function to map roles if needed elsewhere, or keep logic within prepare_request_payload
def map_role_to_gemini(role: str) -> str:
    if role == "assistant":
        return "model"
    elif role == "user":
        return "user"
    else: # system or other
        logger.warning(f"Unsupported role '{role}' mapped to 'user' for Gemini.")
        return "user" # Default or raise error? Gemini uses systemInstruction 