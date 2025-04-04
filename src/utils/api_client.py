"""
通用的 API 客户端，封装 HTTP 请求逻辑。
"""
import logging
import requests
import json # Import json for JSONDecodeError handling
from typing import Dict, Any, Optional, Callable, Iterator

logger = logging.getLogger('news_analyzer.utils.api_client')

class ApiClient:
    """封装 HTTP 请求，支持流式和非流式 POST。"""

    def post(self, url: str, headers: Dict[str, str], json_payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        """
        发送非流式 POST 请求并返回 JSON 响应。

        Args:
            url: 请求 URL。
            headers: 请求头。
            json_payload: JSON 请求体。
            timeout: 请求超时时间（秒）。

        Returns:
            包含 JSON 响应内容的字典。

        Raises:
            requests.exceptions.RequestException: 如果请求失败（包括 HTTP 错误）。
            json.JSONDecodeError: 如果响应体不是有效的 JSON。
        """
        logger.debug(f"Sending POST request to {url}")
        try:
            response = requests.post(
                url,
                headers=headers,
                json=json_payload,
                timeout=timeout
            )
            response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}", exc_info=True)
            raise # Re-raise the exception for the caller to handle
        except json.JSONDecodeError as e:
             logger.error(f"Failed to decode JSON response from {url}: {e}", exc_info=True)
             raise # Re-raise the exception

    def stream_post(self, url: str, headers: Dict[str, str], json_payload: Dict[str, Any], timeout: int) -> Iterator[bytes]:
        """
        发送流式 POST 请求并返回一个字节迭代器。

        Args:
            url: 请求 URL。
            headers: 请求头。
            json_payload: JSON 请求体。
            timeout: 请求超时时间（秒）。

        Returns:
            一个迭代器，逐行产生响应的原始字节。

        Raises:
            requests.exceptions.RequestException: 如果连接失败或收到错误的 HTTP 状态码。
        """
        logger.debug(f"Sending streaming POST request to {url}")
        try:
            response = requests.post(
                url,
                headers=headers,
                json=json_payload,
                stream=True,
                timeout=timeout
            )
            response.raise_for_status()
            # 返回迭代器，让调用者处理解码和解析
            return response.iter_lines()
        except requests.exceptions.RequestException as e:
            logger.error(f"Streaming API request failed: {e}", exc_info=True)
            raise # Re-raise the exception

# 可以在这里添加 GET 或其他方法的封装