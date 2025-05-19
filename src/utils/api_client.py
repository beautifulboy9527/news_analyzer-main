"""
通用的 API 客户端，封装 HTTP 请求逻辑。
"""
import logging
import requests
import json # Import json for JSONDecodeError handling
from typing import Dict, Any, Optional, Callable, Iterator, List
from src.llm.exception import LLMError
import time # Added for sleep in retry

logger = logging.getLogger('news_analyzer.utils.api_client')

class ApiClient:
    """封装 HTTP 请求，支持流式和非流式 POST。"""

    def __init__(self):
        """Initialize the ApiClient with a logger."""
        self.logger = logging.getLogger(__name__)

    def post(self, url: str, headers: Dict[str, str], json_payload: Dict[str, Any], timeout: int, fast_fail_on_status_codes: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        发送非流式 POST 请求并返回 JSON 响应。

        Args:
            url: 请求 URL。
            headers: 请求头。
            json_payload: JSON 请求体。
            timeout: 请求超时时间（秒）。
            fast_fail_on_status_codes: 一个可选的状态码列表。如果响应状态码在此列表中，则立即失败而不进行内部重试。

        Returns:
            包含 JSON 响应内容的字典。

        Raises:
            requests.exceptions.RequestException: 如果请求失败（包括 HTTP 错误）。
            json.JSONDecodeError: 如果响应体不是有效的 JSON。
        """
        self.logger.debug(f"ApiClient.post called for URL: {url}") # Added for context
        self.logger.debug(f"  Received fast_fail_on_status_codes: {fast_fail_on_status_codes} (Type: {type(fast_fail_on_status_codes)})") # DEBUG LOGGING

        last_exception = None
        # 重试逻辑现在更通用，特定于429的退避在内部处理
        max_retries = 3
        base_delay = 1  # seconds

        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(f"ApiClient: Sending POST to {url} (Attempt {attempt + 1}/{max_retries + 1})")
                response = requests.post(
                    url,
                    headers=headers,
                    json=json_payload,
                    timeout=timeout
                )
                self.logger.debug(f"ApiClient: Received status code {response.status_code} from {url}")
                
                # Check for fast fail before raise_for_status
                if fast_fail_on_status_codes and response.status_code in fast_fail_on_status_codes:
                    self.logger.info(f"ApiClient: Fast failing on status {response.status_code} for {url} as requested.")
                    # We still call raise_for_status() to get a proper HTTPError, then convert it.
                    # Or, construct LLMError directly. Let's construct directly for clarity.
                    try:
                        response.raise_for_status() # To get the error message text if possible
                    except requests.exceptions.HTTPError as http_err_for_fast_fail:
                        raise LLMError(f"API request failed (fast fail on {response.status_code}): {http_err_for_fast_fail}", status_code=response.status_code) from http_err_for_fast_fail
                    # Should not be reached if raise_for_status() worked as expected for an error code
                    raise LLMError(f"API request failed (fast fail on {response.status_code})", status_code=response.status_code)

                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx) if not fast-failed

                content_type = response.headers.get('content-type', 'N/A')
                self.logger.debug(f"ApiClient: Response Content-Type: {content_type}")
                self.logger.debug("ApiClient: Attempting to parse response as JSON...")
                json_response = response.json()
                self.logger.info("ApiClient: Successfully parsed and returning JSON response.")
                return json_response
            except requests.exceptions.Timeout as e:
                self.logger.error(f"API request TIMEOUT ({timeout}s) for {url} (Attempt {attempt + 1}): {e}", exc_info=True)
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    self.logger.info(f"Retrying after {delay}s due to timeout...")
                    time.sleep(delay)
                    continue
                raise LLMError(f"Request timed out after {timeout}s: {e}", status_code=408) from e
            except requests.exceptions.HTTPError as e: # This will catch errors from raise_for_status if not fast-failed earlier
                status_code = e.response.status_code if e.response is not None else None
                self.logger.error(f"API request failed with HTTPError (status {status_code}) for {url} (Attempt {attempt + 1}): {e}", exc_info=True)

                # If fast_fail_on_status_codes was None or didn't include this code, standard retry logic applies:
                if status_code == 429 and attempt < max_retries:
                    retry_after_header = e.response.headers.get("Retry-After") if e.response is not None else None
                    if retry_after_header:
                        try:
                            delay = int(retry_after_header)
                            self.logger.info(f"Rate limit hit (429). 'Retry-After' header found. Retrying after {delay}s...")
                        except ValueError:
                            delay = base_delay * (2 ** attempt)
                            self.logger.info(f"Rate limit hit (429). 'Retry-After' non-integer. Retrying after {delay}s (exponential backoff)...")
                    else:
                        delay = base_delay * (2 ** attempt)
                        self.logger.info(f"Rate limit hit (429). No 'Retry-After' header. Retrying after {delay}s (exponential backoff)...")
                    time.sleep(delay)
                    continue
                # For other HTTP errors or if max_retries reached for 429
                raise LLMError(f"API request failed: {e}", status_code=status_code) from e
            except requests.exceptions.RequestException as e:
                self.logger.error(f"API request failed (non-HTTPError, non-Timeout) for {url} (Attempt {attempt + 1}): {e}", exc_info=True)
                status_code = getattr(e.response, 'status_code', None)
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    self.logger.info(f"Retrying after {delay}s due to RequestException: {e}")
                    time.sleep(delay)
                    continue
                raise LLMError(f"API request failed: {e}", status_code=status_code) from e
            except json.JSONDecodeError as e:
                 self.logger.error(f"Failed to decode JSON response from {url}: {e}", exc_info=True)
                 raise LLMError(f"Failed to decode JSON response: {e}", status_code=None) from e
        
        self.logger.error(f"Exhausted all retries for {url}.") # Should be unreachable if logic is correct
        raise LLMError(f"API request failed after {max_retries + 1} attempts for {url}.", status_code=None)

    def get(self, url: str, headers: Dict[str, str], timeout: int, params: Optional[Dict[str, Any]] = None, fast_fail_on_status_codes: Optional[List[int]] = None) -> str:
        """
        发送 GET 请求并返回文本响应。

        Args:
            url: 请求 URL。
            headers: 请求头。
            timeout: 请求超时时间（秒）。
            params: URL 查询参数 (可选)。
            fast_fail_on_status_codes: 一个可选的状态码列表。如果响应状态码在此列表中，则立即失败而不进行内部重试。

        Returns:
            包含响应文本内容的字符串。

        Raises:
            LLMError: 如果请求失败（包括 HTTP 错误或非文本响应）。
        """
        self.logger.debug(f"ApiClient.get called for URL: {url}")
        self.logger.debug(f"  Received fast_fail_on_status_codes: {fast_fail_on_status_codes}")

        max_retries = 3
        base_delay = 1  # seconds

        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(f"ApiClient: Sending GET to {url} (Attempt {attempt + 1}/{max_retries + 1})")
                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=timeout
                )
                self.logger.debug(f"ApiClient: Received status code {response.status_code} from {url}")

                if fast_fail_on_status_codes and response.status_code in fast_fail_on_status_codes:
                    self.logger.info(f"ApiClient: Fast failing GET on status {response.status_code} for {url} as requested.")
                    try:
                        response.raise_for_status()
                    except requests.exceptions.HTTPError as http_err_for_fast_fail:
                        raise LLMError(f"API GET request failed (fast fail on {response.status_code}): {http_err_for_fast_fail}", status_code=response.status_code) from http_err_for_fast_fail
                    raise LLMError(f"API GET request failed (fast fail on {response.status_code})", status_code=response.status_code)

                response.raise_for_status()

                # Ollama test expects text, so we return response.text
                self.logger.info("ApiClient: Successfully received GET response, returning text.")
                return response.text
            except requests.exceptions.Timeout as e:
                self.logger.error(f"API GET request TIMEOUT ({timeout}s) for {url} (Attempt {attempt + 1}): {e}", exc_info=True)
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    self.logger.info(f"Retrying GET after {delay}s due to timeout...")
                    time.sleep(delay)
                    continue
                raise LLMError(f"GET Request timed out after {timeout}s: {e}", status_code=408) from e
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response is not None else None
                self.logger.error(f"API GET request failed with HTTPError (status {status_code}) for {url} (Attempt {attempt + 1}): {e}", exc_info=True)
                if status_code == 429 and attempt < max_retries:
                    # Handle rate limiting with Retry-After header or exponential backoff
                    retry_after_header = e.response.headers.get("Retry-After") if e.response is not None else None
                    delay = base_delay * (2 ** attempt) # Default backoff
                    if retry_after_header:
                        try:
                            delay = int(retry_after_header)
                            self.logger.info(f"Rate limit hit (429) for GET. \'Retry-After\' header found. Retrying after {delay}s...")
                        except ValueError:
                            self.logger.info(f"Rate limit hit (429) for GET. \'Retry-After\' non-integer. Retrying after {delay}s (exponential backoff)....")
                    else:
                        self.logger.info(f"Rate limit hit (429) for GET. No \'Retry-After\' header. Retrying after {delay}s (exponential backoff)...")
                    time.sleep(delay)
                    continue
                raise LLMError(f"API GET request failed: {e}", status_code=status_code) from e
            except requests.exceptions.RequestException as e:
                self.logger.error(f"API GET request failed (non-HTTPError, non-Timeout) for {url} (Attempt {attempt + 1}): {e}", exc_info=True)
                status_code = getattr(e.response, 'status_code', None)
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    self.logger.info(f"Retrying GET after {delay}s due to RequestException: {e}")
                    time.sleep(delay)
                    continue
                raise LLMError(f"API GET request failed: {e}", status_code=status_code) from e

        self.logger.error(f"Exhausted all GET retries for {url}.")
        raise LLMError(f"API GET request failed after {max_retries + 1} attempts for {url}.", status_code=None)

    def stream_post(self, url: str, headers: Dict[str, str], json_payload: Dict[str, Any], timeout: int, fast_fail_on_status_codes: Optional[List[int]] = None) -> Iterator[bytes]:
        """
        发送流式 POST 请求并返回一个字节迭代器。
        NOTE: Fast-fail logic for stream_post primarily applies to the initial connection.
              Once the stream is established, errors are handled by the iterator.
        """
        self.logger.debug(f"Sending streaming POST request to {url}. Fast fail codes: {fast_fail_on_status_codes}")
        # For stream_post, the retry logic is trickier as it applies to connection establishment.
        # The existing ApiClient doesn't have explicit retry loops for stream_post connection.
        # It relies on the caller (GeminiProvider) to handle retries for stream connection.
        # We will add fast-fail for the initial response check.
        try:
            self.logger.debug(f"ApiClient: Sending streaming POST to {url}")
            response = requests.post(
                url,
                headers=headers,
                json=json_payload,
                stream=True,
                timeout=timeout
            )
            self.logger.info(f"Received initial stream response from {url}, status: {response.status_code}")

            if fast_fail_on_status_codes and response.status_code in fast_fail_on_status_codes:
                self.logger.info(f"ApiClient: Fast failing stream connection on status {response.status_code} for {url} as requested.")
                try:
                    response.raise_for_status()
                except requests.exceptions.HTTPError as http_err_for_fast_fail:
                    raise LLMError(f"Stream connection failed (fast fail on {response.status_code}): {http_err_for_fast_fail}", status_code=response.status_code) from http_err_for_fast_fail
                raise LLMError(f"Stream connection failed (fast fail on {response.status_code})", status_code=response.status_code)

            response.raise_for_status() # Check status for non-fast-fail cases or if status was initially OK
            
            self.logger.info(f"Streaming POST connection to {url} successful. Iterating response...")
            # Iterate over the response content line by line
            try:
                # --- Add Logging --- Added
                self.logger.debug(f"Entering stream iteration loop for {url}...")
                lines_yielded = 0
                # --- End Logging ---
                for line in response.iter_lines():
                    if line:
                        # --- Add Logging --- Added
                        lines_yielded += 1
                        # Log only the first few yields to avoid flooding logs
                        if lines_yielded <= 5:
                            self.logger.debug(f"Stream POST yielding line {lines_yielded} for {url}: {line[:100]}...") # Log partial line
                        # --- End Logging ---
                        yield line # Yield the raw byte line
                # --- Add Logging --- Added
                self.logger.debug(f"Finished stream iteration loop for {url}. Total lines yielded: {lines_yielded}")
                if lines_yielded == 0:
                     self.logger.warning(f"Stream POST for {url} yielded 0 lines.")
                # --- End Logging ---
            except requests.exceptions.ChunkedEncodingError as e:
                self.logger.error(f"Stream POST chunked encoding error for {url}: {e}", exc_info=True)
                raise LLMError(f"Stream chunked encoding error: {e}", status_code=getattr(e.response, 'status_code', None)) from e
            except Exception as e:
                self.logger.error(f"Unexpected error during stream iteration for {url}: {e}", exc_info=True)
                raise LLMError(f"Unexpected stream iteration error: {e}") from e
            finally:
                response.close() # Ensure the response is closed
        except requests.exceptions.RequestException as e: # This catches connection errors, including timeouts for stream
            self.logger.error(f"Stream POST request failed for {url}: {e}", exc_info=True)
            status_to_set = getattr(e.response, 'status_code', None)
            # If it's a timeout, ApiClient's post() sets 408. Mimic for stream connection timeout.
            if isinstance(e, requests.exceptions.Timeout):
                status_to_set = 408
            
            # If it was an HTTPError that should fast_fail, it would have been caught above.
            # This handles other RequestExceptions (like connection errors) or HTTPError not in fast_fail_on_status_codes.
            raise LLMError(f"Stream request failed: {e}", status_code=status_to_set) from e

# 可以在这里添加 GET 或其他方法的封装