import unittest
import json
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import requests

# 假设 models.py 在 src 目录下，并且可以被导入
# 如果 PYTHONPATH 没有设置，可能需要调整导入路径
try:
    from src.models import NewsSource
    from src.collectors.json_feed_collector import JSONFeedCollector
except ImportError:
    # 如果直接运行测试脚本，可能需要添加 src 到 sys.path
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
    from src.models import NewsSource
    from src.collectors.json_feed_collector import JSONFeedCollector

# --- Mock 数据 ---

# 有效的 JSON Feed v1.1 数据
VALID_FEED_DATA = {
    "version": "https://jsonfeed.org/version/1.1",
    "title": "Test JSON Feed",
    "home_page_url": "https://example.org/",
    "feed_url": "https://example.org/feed.json",
    "items": [
        {
            "id": "item-1",
            "url": "https://example.org/item-1",
            "title": "First Item Title",
            "content_html": "<p>This is the first item content.</p>",
            "summary": "Summary for item 1",
            "date_published": "2023-10-26T10:00:00+00:00", # RFC3339
            "tags": ["tag1", "tag2"]
        },
        {
            "id": "item-2-no-html",
            "external_url": "https://external.example.com/item-2", # 使用 external_url
            "title": "Second Item Title",
            "content_text": "This is the second item content (text only).",
            # 无 date_published
            "author": {"name": "Test Author"}
        },
        {
            "id": "item-3-no-title", # 缺少 title
            "url": "https://example.org/item-3",
            "content_text": "Content for item without a title.",
            "date_published": "2023-10-26T12:30:00Z" # 另一种 RFC3339 格式
        },
        {
            "id": "item-4-only-id", # 只有 id
        }
    ]
}

# items 为空的 Feed
EMPTY_ITEMS_FEED_DATA = {
    "version": "https://jsonfeed.org/version/1.1",
    "title": "Empty Feed",
    "items": []
}

# 缺少 'items' 键的 Feed
MISSING_ITEMS_KEY_FEED_DATA = {
    "version": "https://jsonfeed.org/version/1.1",
    "title": "Missing Items Key Feed"
    # 'items' key is missing
}

# 缺少 'version' 键的 Feed
MISSING_VERSION_KEY_FEED_DATA = {
    "title": "Missing Version Key Feed",
    "items": [{"id": "1"}]
}

# items 不是列表的 Feed
INVALID_ITEMS_TYPE_FEED_DATA = {
    "version": "https://jsonfeed.org/version/1.1",
    "title": "Invalid Items Type Feed",
    "items": {"not": "a list"}
}

# 无效的 JSON 字符串
INVALID_JSON_STRING = "{'invalid_json': "

# --- 测试类 ---

class TestJSONFeedCollector(unittest.TestCase):

    def setUp(self):
        """设置测试环境"""
        self.collector = JSONFeedCollector()
        self.test_source = NewsSource(name="Test JSON Source", type="json", url="http://test.com/feed.json", category="Test", enabled=True) # Added type, removed id, fixed is_enabled typo
        # Mock time.strftime to return a fixed value
        self.patcher = patch('src.collectors.json_feed_collector.time.strftime')
        self.mock_strftime = self.patcher.start()
        self.mock_strftime.return_value = "2024-01-01 12:00:00"

    def tearDown(self):
        """清理测试环境"""
        self.patcher.stop()

    def _create_mock_response(self, status_code=200, json_data=None, text_data=None, raise_for_status_error=None):
        """辅助函数创建 Mock Response 对象"""
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = status_code
        mock_resp.url = self.test_source.url

        if json_data is not None:
            mock_resp.json.return_value = json_data
            # 同时设置 text 以防 json 解析失败时记录日志
            mock_resp.text = json.dumps(json_data)
        elif text_data is not None:
            mock_resp.text = text_data
            # 如果提供了 text_data，模拟 json() 抛出异常
            mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)

        if raise_for_status_error:
            mock_resp.raise_for_status.side_effect = raise_for_status_error
        else:
            # 默认情况下，如果状态码 >= 400，raise_for_status 应该抛出异常
            if status_code >= 400:
                 mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(f"{status_code} Client Error", response=mock_resp)
            else:
                 mock_resp.raise_for_status.return_value = None # 显式设置成功时不抛异常

        return mock_resp

    @patch('src.collectors.json_feed_collector.requests.Session.get')
    def test_collect_success(self, mock_get):
        """测试成功获取和解析有效的 JSON Feed"""
        mock_response = self._create_mock_response(status_code=200, json_data=VALID_FEED_DATA)
        mock_get.return_value = mock_response

        results = self.collector.collect(self.test_source)

        mock_get.assert_called_once_with(self.test_source.url, timeout=20)
        mock_response.raise_for_status.assert_called_once()
        self.assertEqual(len(results), 4) # item-4 只有 id，但当前实现允许无链接条目，所以包含在内

        # 验证第一个 item 的映射
        item1 = results[0]
        self.assertEqual(item1['title'], "First Item Title")
        self.assertEqual(item1['link'], "https://example.org/item-1")
        self.assertEqual(item1['content'], "<p>This is the first item content.</p>")
        self.assertEqual(item1['summary'], "Summary for item 1")
        # 检查日期是否被正确解析和格式化 (如果 dateutil 可用)
        # 注意：JSONFeedCollector._parse_date 会尝试转为 ISO 格式
        # 这里我们直接比较原始字符串，因为 mock 可能没有 dateutil
        # 或者，如果确定 dateutil 可用，可以比较 datetime 对象
        expected_date_item1 = "2023-10-26T10:00:00+00:00"
        # 如果 dateutil 可用，它会被解析并转回 ISO 格式
        try:
            from dateutil import parser
            expected_date_item1 = parser.isoparse(expected_date_item1).isoformat()
        except ImportError:
            pass # 保留原始字符串
        self.assertEqual(item1['publish_time'], expected_date_item1)
        self.assertEqual(item1['source_name'], self.test_source.name)
        self.assertEqual(item1['collected_at'], "2024-01-01 12:00:00")
        self.assertIn('"id": "item-1"', item1['raw_data'])

        # 验证第二个 item (使用 external_url, 无日期)
        item2 = results[1]
        self.assertEqual(item2['title'], "Second Item Title")
        self.assertEqual(item2['link'], "https://external.example.com/item-2")
        self.assertEqual(item2['content'], "This is the second item content (text only).")
        self.assertTrue(item2['summary'].startswith("This is the second item content")) # 自动生成摘要
        self.assertIsNone(item2['publish_time']) # 无日期
        self.assertEqual(item2['source_name'], self.test_source.name)

        # 验证第三个 item (无 title, 自动生成)
        item3 = results[2]
        self.assertTrue(item3['title'].startswith("Content for item without a title.")) # 自动生成标题
        self.assertEqual(item3['link'], "https://example.org/item-3")
        self.assertEqual(item3['content'], "Content for item without a title.")
        expected_date_item3 = "2023-10-26T12:30:00Z"
        try:
            from dateutil import parser
            expected_date_item3 = parser.isoparse(expected_date_item3).isoformat()
        except ImportError:
            pass
        self.assertEqual(item3['publish_time'], expected_date_item3)
        self.assertEqual(item3['source_name'], self.test_source.name)


    @patch('src.collectors.json_feed_collector.requests.Session.get')
    def test_collect_empty_items(self, mock_get):
        """测试处理 items 为空的 Feed"""
        mock_response = self._create_mock_response(status_code=200, json_data=EMPTY_ITEMS_FEED_DATA)
        mock_get.return_value = mock_response

        results = self.collector.collect(self.test_source)

        mock_get.assert_called_once_with(self.test_source.url, timeout=20)
        self.assertEqual(len(results), 0)

    @patch('src.collectors.json_feed_collector.requests.Session.get')
    def test_collect_missing_items_key(self, mock_get):
        """测试处理缺少 'items' 键的 Feed"""
        mock_response = self._create_mock_response(status_code=200, json_data=MISSING_ITEMS_KEY_FEED_DATA)
        mock_get.return_value = mock_response

        results = self.collector.collect(self.test_source)

        mock_get.assert_called_once_with(self.test_source.url, timeout=20)
        self.assertEqual(len(results), 0)

    @patch('src.collectors.json_feed_collector.requests.Session.get')
    def test_collect_missing_version_key(self, mock_get):
        """测试处理缺少 'version' 键的 Feed"""
        mock_response = self._create_mock_response(status_code=200, json_data=MISSING_VERSION_KEY_FEED_DATA)
        mock_get.return_value = mock_response

        results = self.collector.collect(self.test_source)

        mock_get.assert_called_once_with(self.test_source.url, timeout=20)
        self.assertEqual(len(results), 0)

    @patch('src.collectors.json_feed_collector.requests.Session.get')
    def test_collect_invalid_items_type(self, mock_get):
        """测试处理 'items' 不是列表的 Feed"""
        mock_response = self._create_mock_response(status_code=200, json_data=INVALID_ITEMS_TYPE_FEED_DATA)
        mock_get.return_value = mock_response

        results = self.collector.collect(self.test_source)

        mock_get.assert_called_once_with(self.test_source.url, timeout=20)
        self.assertEqual(len(results), 0)

    @patch('src.collectors.json_feed_collector.requests.Session.get')
    def test_collect_invalid_json(self, mock_get):
        """测试处理无效的 JSON 响应"""
        mock_response = self._create_mock_response(status_code=200, text_data=INVALID_JSON_STRING)
        # _create_mock_response 已经设置了 json() 抛出 JSONDecodeError
        mock_get.return_value = mock_response

        results = self.collector.collect(self.test_source)

        mock_get.assert_called_once_with(self.test_source.url, timeout=20)
        self.assertEqual(len(results), 0)
        # 可以添加日志检查，确认记录了错误

    @patch('src.collectors.json_feed_collector.requests.Session.get')
    def test_collect_timeout_error(self, mock_get):
        """测试处理网络超时错误"""
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        results = self.collector.collect(self.test_source)

        mock_get.assert_called_once_with(self.test_source.url, timeout=20)
        self.assertEqual(len(results), 0)
        # 可以添加日志检查，确认记录了超时错误

    @patch('src.collectors.json_feed_collector.requests.Session.get')
    def test_collect_request_exception(self, mock_get):
        """测试处理其他网络请求错误"""
        mock_get.side_effect = requests.exceptions.RequestException("Connection error")

        results = self.collector.collect(self.test_source)

        mock_get.assert_called_once_with(self.test_source.url, timeout=20)
        self.assertEqual(len(results), 0)
        # 可以添加日志检查，确认记录了网络错误

    @patch('src.collectors.json_feed_collector.requests.Session.get')
    def test_collect_http_error_4xx(self, mock_get):
        """测试处理 HTTP 4xx 错误"""
        mock_response = self._create_mock_response(status_code=404, text_data="Not Found")
        # _create_mock_response 会自动设置 raise_for_status 抛出 HTTPError
        mock_get.return_value = mock_response

        results = self.collector.collect(self.test_source)

        mock_get.assert_called_once_with(self.test_source.url, timeout=20)
        mock_response.raise_for_status.assert_called_once()
        self.assertEqual(len(results), 0)
        # 可以添加日志检查，确认记录了 HTTP 错误

    @patch('src.collectors.json_feed_collector.requests.Session.get')
    def test_collect_http_error_5xx(self, mock_get):
        """测试处理 HTTP 5xx 错误"""
        mock_response = self._create_mock_response(status_code=500, text_data="Server Error")
        mock_get.return_value = mock_response

        results = self.collector.collect(self.test_source)

        mock_get.assert_called_once_with(self.test_source.url, timeout=20)
        mock_response.raise_for_status.assert_called_once()
        self.assertEqual(len(results), 0)
        # 可以添加日志检查，确认记录了 HTTP 错误

    @patch('src.collectors.json_feed_collector.requests.Session.get')
    def test_collect_item_missing_id(self, mock_get):
        """测试处理 item 缺少 'id' 的情况"""
        feed_data_missing_id = {
            "version": "https://jsonfeed.org/version/1.1",
            "title": "Feed with Missing ID",
            "items": [
                {"title": "Item without ID", "url": "http://no.id"} # 缺少 id
            ]
        }
        mock_response = self._create_mock_response(status_code=200, json_data=feed_data_missing_id)
        mock_get.return_value = mock_response

        results = self.collector.collect(self.test_source)

        self.assertEqual(len(results), 0) # 缺少 id 的 item 应该被跳过

    @patch('src.collectors.json_feed_collector.requests.Session.get')
    def test_collect_item_invalid_type(self, mock_get):
        """测试处理 item 不是字典的情况"""
        feed_data_invalid_item = {
            "version": "https://jsonfeed.org/version/1.1",
            "title": "Feed with Invalid Item Type",
            "items": [
                "not a dictionary", # 无效的 item 类型
                {"id": "valid-item", "title": "Valid Item"}
            ]
        }
        mock_response = self._create_mock_response(status_code=200, json_data=feed_data_invalid_item)
        mock_get.return_value = mock_response

        results = self.collector.collect(self.test_source)

        self.assertEqual(len(results), 1) # 无效 item 被跳过，有效 item 被处理
        self.assertEqual(results[0]['title'], "Valid Item")

    @patch('src.collectors.json_feed_collector.requests.Session.get')
    def test_collect_cancel_checker_after_get(self, mock_get):
        """测试在 get 请求后检查到取消信号"""
        mock_response = self._create_mock_response(status_code=200, json_data=VALID_FEED_DATA)
        mock_get.return_value = mock_response
        mock_cancel_checker = MagicMock(return_value=True) # 模拟取消信号

        results = self.collector.collect(self.test_source, cancel_checker=mock_cancel_checker)

        mock_get.assert_called_once()
        mock_cancel_checker.assert_called_once() # 应该在 get 之后检查一次
        self.assertEqual(len(results), 0) # 因为取消了，所以返回空

    @patch('src.collectors.json_feed_collector.requests.Session.get')
    def test_collect_cancel_checker_during_parse(self, mock_get):
        """测试在解析 item 过程中检查到取消信号"""
        mock_response = self._create_mock_response(status_code=200, json_data=VALID_FEED_DATA)
        mock_get.return_value = mock_response

        # 让 cancel_checker 在第二次调用时返回 True (处理第二个 item 时取消)
        mock_cancel_checker = MagicMock(side_effect=[False, False, True]) # 第一次 get 后检查 False, 第一个 item 检查 False, 第二个 item 检查 True

        results = self.collector.collect(self.test_source, cancel_checker=mock_cancel_checker)

        mock_get.assert_called_once()
        self.assertEqual(mock_cancel_checker.call_count, 3) # get 后一次，每个 item 一次 (直到取消)
        self.assertEqual(len(results), 1) # 只收集到了第一个 item

    def test_parse_date_with_dateutil(self):
        """测试 _parse_date 在 dateutil 可用时的情况"""
        # 模拟 dateutil 可用
        with patch('src.collectors.json_feed_collector._HAS_DATEUTIL', True):
             # 模拟 dateutil.parser.isoparse
             with patch('src.collectors.json_feed_collector.dateutil_parser.isoparse') as mock_isoparse:
                mock_dt = datetime(2023, 10, 26, 10, 0, 0, tzinfo=timezone.utc)
                mock_isoparse.return_value = mock_dt

                date_str = "2023-10-26T10:00:00Z"
                parsed = self.collector._parse_date(date_str)
                mock_isoparse.assert_called_once_with(date_str)
                self.assertEqual(parsed, mock_dt.isoformat())

                # 测试无效日期
                mock_isoparse.side_effect = ValueError("Invalid date")
                invalid_date_str = "invalid-date"
                parsed_invalid = self.collector._parse_date(invalid_date_str)
                self.assertEqual(parsed_invalid, invalid_date_str) # 解析失败，返回原字符串

                # 测试 None 输入
                self.assertIsNone(self.collector._parse_date(None))

    def test_parse_date_without_dateutil(self):
        """测试 _parse_date 在 dateutil 不可用时的情况"""
        # 模拟 dateutil 不可用
        with patch('src.collectors.json_feed_collector._HAS_DATEUTIL', False):
            date_str = "2023-10-26T10:00:00Z"
            parsed = self.collector._parse_date(date_str)
            # 不尝试解析，直接返回原字符串
            self.assertEqual(parsed, date_str)

            # 测试 None 输入
            self.assertIsNone(self.collector._parse_date(None))


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)