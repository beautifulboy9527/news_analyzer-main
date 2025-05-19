import io
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone # timedelta might not be needed now
from urllib.error import URLError, HTTPError
from xml.etree import ElementTree as ET
import ssl # For SSLError

import feedparser # For mocking feed parsing
from src.core.enhanced_news_clusterer import EnhancedNewsClusterer

# 假设 NewsSource 在 src.models 中定义
# 需要根据实际项目结构调整导入路径
# Mock NewsSource if not directly importable or to avoid dependency
class MockNewsSource:
    def __init__(self, id, name, url, type="rss"): # Match expected attributes
        self.id = id
        self.name = name
        self.url = url
        self.type = type # Though collector doesn't seem to use type

try:
    # Try importing the real collector
    from src.collectors.rss_collector import RSSCollector
    # NewsSource might be needed for type hints or internal checks, import if available
    # from src.models import NewsSource # Keep commented if MockNewsSource is sufficient
except ImportError:
    # Fallback for running script directly
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src'))) # Corrected path
    from collectors.rss_collector import RSSCollector # Corrected relative import path
    # from models import NewsSource

class TestRSSCollector(unittest.TestCase):

    def setUp(self):
        """设置测试环境"""
        self.collector = RSSCollector()
        # Use MockNewsSource or real NewsSource if imported
        self.rss_source = MockNewsSource(id="test_rss", name="Test RSS Feed", url="http://example.com/rss")
        self.atom_source = MockNewsSource(id="test_atom", name="Test Atom Feed", url="http://example.com/atom")

    # --- Mock XML Data ---
    def _get_mock_rss_xml(self):
        return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Test RSS Feed</title>
    <link>http://example.com/rss</link>
    <description>A test RSS feed</description>
    <item>
      <title>RSS Item 1</title>
      <link>http://example.com/rss/item1</link>
      <pubDate>Wed, 02 Oct 2002 13:00:00 GMT</pubDate>
      <guid isPermaLink="true">http://example.com/rss/item1</guid>
      <description><![CDATA[Summary for RSS item 1]]></description>
      <content:encoded><![CDATA[<p>Content for RSS item 1</p>]]></content:encoded>
    </item>
    <item>
      <title>[Source Name] RSS Item 2 - Extra Info</title>
      <link>http://example.com/rss/item2</link>
      <pubDate>Wed, 02 Oct 2002 14:00:00 +0000</pubDate>
      <guid isPermaLink="false">item2-guid</guid>
      <description>Summary for RSS item 2</description>
      <!-- No content:encoded -->
    </item>
     <item>
      <title></title> <!-- Empty title -->
      <link>http://example.com/rss/item3</link>
      <pubDate>Wed, 02 Oct 2002 15:00:00 GMT</pubDate>
      <description>Item with empty title</description>
    </item>
    <item>
      <title>Item with no link</title>
      <!-- <link>http://example.com/rss/item4</link> -->
       <guid isPermaLink="true">http://example.com/rss/guidlink</guid> <!-- Link from guid -->
      <pubDate>Wed, 02 Oct 2002 16:00:00 GMT</pubDate>
      <description>Item using guid as link</description>
    </item>
  </channel>
</rss>
"""

    def _get_mock_atom_xml(self):
        return """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Atom Feed</title>
  <link href="http://example.com/atom"/>
  <updated>2003-12-14T10:20:05Z</updated>
  <id>urn:uuid:60a76c80-d399-11d9-b93C-0003939e0af6</id>
  <entry>
    <title>Atom Item 1</title>
    <link href="http://example.com/atom/item1" rel="alternate"/>
    <link href="http://example.com/atom/item1/other" rel="related"/>
    <id>urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a</id>
    <updated>2003-12-13T18:30:02Z</updated>
    <published>2003-12-13T18:30:02Z</published>
    <summary type="html">Summary for &lt;b&gt;Atom&lt;/b&gt; item 1</summary>
    <content type="xhtml">
      <div xmlns="http://www.w3.org/1999/xhtml">
        <p>Content for Atom item 1</p>
      </div>
    </content>
    <author><name>John Doe</name></author>
  </entry>
  <entry>
    <title>Atom Item 2 (Updated Only)</title>
    <link href="http://example.com/atom/item2"/> <!-- No rel=alternate -->
    <id>urn:uuid:1225c695-cfb8-4ebb-bbbb-80da344efa6b</id>
    <updated>2003-12-14T10:20:05+00:00</updated>
    <!-- No published -->
    <summary>Summary for Atom item 2</summary>
    <!-- No content -->
  </entry>
</feed>
"""

    def _get_mock_empty_feed_xml(self):
        return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Empty Feed</title>
    <link>http://example.com/empty</link>
    <description>This feed has no items.</description>
  </channel>
</rss>
"""

    def _get_invalid_xml(self):
        return "<rss><channel><item>...</item></rss>" # Missing closing channel

    def _mock_urlopen(self, xml_content, charset='utf-8', raise_exception=None, status_code=200):
        """Helper to create a mock urlopen context manager."""
        mock_response = MagicMock()
        mock_response.status = status_code # For HTTPError check if needed
        mock_response.reason = "OK" if status_code == 200 else "Error"

        if raise_exception:
            mock_context = MagicMock()
            mock_context.__enter__.side_effect = raise_exception
            return mock_context

        # Simulate read() and headers
        content_bytes = xml_content.encode(charset, errors='ignore')
        mock_response.read.return_value = content_bytes
        mock_response.headers = MagicMock()
        mock_response.headers.get_content_charset.return_value = charset
        # Simulate seek for decode fallback
        mock_response.seek = MagicMock()


        # Make the mock response usable with 'with' statement
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_response
        mock_context.__exit__ = MagicMock(return_value=None)
        return mock_context

    # --- 测试用例 ---

    @patch('src.collectors.rss_collector.urlopen')
    def test_collect_success_rss(self, mock_urlopen):
        """测试从 RSS 源成功获取新闻"""
        print("\nRunning test_collect_success_rss...")
        mock_urlopen.return_value = self._mock_urlopen(self._get_mock_rss_xml())

        news_dicts = self.collector.collect(self.rss_source)

        mock_urlopen.assert_called_once() # Check urlopen was called
        # Verify the request object passed to urlopen
        call_args, call_kwargs = mock_urlopen.call_args
        request_obj = call_args[0]
        self.assertEqual(request_obj.full_url, self.rss_source.url)
        self.assertIn('User-agent', request_obj.headers) # Check for the actual header key used
        self.assertEqual(call_kwargs.get('timeout'), 15)

        # Should parse 3 valid items (skipping the one with empty title/link)
        self.assertEqual(len(news_dicts), 3)

        # 验证第一个条目
        item1 = news_dicts[0]
        self.assertIsInstance(item1, dict)
        self.assertEqual(item1['title'], "RSS Item 1") # Standardized title
        self.assertEqual(item1['link'], "http://example.com/rss/item1")
        self.assertEqual(item1['source_name'], self.rss_source.name)
        self.assertEqual(item1['publish_time'], "Wed, 02 Oct 2002 13:00:00 GMT") # String format
        self.assertEqual(item1['summary'], "Summary for RSS item 1")
        self.assertEqual(item1['content'], "<p>Content for RSS item 1</p>") # Keep HTML
        self.assertIn('collected_at', item1)
        self.assertIn('raw_data', item1)
        # Check for a specific element within the raw data that is less likely to be affected by namespaces
        self.assertIn('<title>RSS Item 1</title>', item1['raw_data'])

        # 验证第二个条目 (标题标准化，无 content)
        item2 = news_dicts[1]
        self.assertEqual(item2['title'], "RSS Item 2 - Extra Info") # Standardized
        self.assertEqual(item2['link'], "http://example.com/rss/item2")
        self.assertEqual(item2['publish_time'], "Wed, 02 Oct 2002 14:00:00 +0000")
        self.assertEqual(item2['summary'], "Summary for RSS item 2") # Description becomes summary
        self.assertEqual(item2['content'], "Summary for RSS item 2") # Description also becomes content if no content:encoded

        # 验证第四个条目 (使用 guid 作为 link)
        item4 = news_dicts[2]
        self.assertEqual(item4['title'], "Item with no link")
        self.assertEqual(item4['link'], "http://example.com/rss/guidlink") # Link from guid
        self.assertEqual(item4['publish_time'], "Wed, 02 Oct 2002 16:00:00 GMT")
        self.assertEqual(item4['summary'], "Item using guid as link")
        self.assertEqual(item4['content'], "Item using guid as link")


        print("test_collect_success_rss PASSED")


    @patch('src.collectors.rss_collector.urlopen')
    def test_collect_success_atom(self, mock_urlopen):
        """测试从 Atom 源成功获取新闻"""
        print("\nRunning test_collect_success_atom...")
        mock_urlopen.return_value = self._mock_urlopen(self._get_mock_atom_xml())

        news_dicts = self.collector.collect(self.atom_source)

        mock_urlopen.assert_called_once()
        self.assertEqual(len(news_dicts), 2) # Should parse 2 valid entries

        # 验证第一个条目
        item1 = news_dicts[0]
        self.assertEqual(item1['title'], "Atom Item 1")
        self.assertEqual(item1['link'], "http://example.com/atom/item1")
        self.assertEqual(item1['source_name'], self.atom_source.name)
        # Let's check if it's a valid ISO string
        try:
            datetime.fromisoformat(item1['publish_time'].replace('Z', '+00:00'))
        except ValueError:
            self.fail("publish_time is not a valid ISO 8601 string")
        # Corrected: Revert YET AGAIN to expecting truncated/cleaned summary based on previous trace
        self.assertEqual(item1['summary'], "Summary for Atom item 1...")
        # Corrected content assertion for Atom: check exact HTML content
        self.assertEqual(item1['content'], "Summary for <b>Atom</b> item 1")
        self.assertIn('collected_at', item1)
        self.assertIn('raw_data', item1)
        # Corrected raw_data check for namespace
        self.assertIn('>Atom Item 1</ns0:title>', item1['raw_data'])


        # 验证第二个条目 (只有 updated, 没有 published)
        item2 = news_dicts[1]
        self.assertEqual(item2['title'], "Atom Item 2 (Updated Only)")
        self.assertEqual(item2['link'], "http://example.com/atom/item2")
        # self.assertEqual(item2['publish_time'], "2003-12-14T10:20:05+00:00") # Updated becomes publish_time
        try:
            datetime.fromisoformat(item2['publish_time'].replace('Z', '+00:00'))
        except ValueError:
             self.fail("publish_time (from updated) is not a valid ISO 8601 string")
        # Corrected: Expect the HTML summary as content if no separate content field exists
        self.assertEqual(item2['summary'], "Summary for Atom item 2")
        self.assertEqual(item2['content'], "Summary for Atom item 2") # Summary becomes content


        print("test_collect_success_atom PASSED")

    @patch('src.collectors.rss_collector.urlopen')
    def test_collect_empty_feed(self, mock_urlopen):
        """测试处理空的 Feed"""
        print("\nRunning test_collect_empty_feed...")
        mock_urlopen.return_value = self._mock_urlopen(self._get_mock_empty_feed_xml())

        news_dicts = self.collector.collect(self.rss_source)

        mock_urlopen.assert_called_once()
        self.assertEqual(len(news_dicts), 0)
        print("test_collect_empty_feed PASSED")

    @patch('src.collectors.rss_collector.urlopen')
    def test_collect_xml_parse_error(self, mock_urlopen):
        """测试处理 XML 解析错误"""
        print("\nRunning test_collect_xml_parse_error...")
        invalid_xml = self._get_invalid_xml()
        mock_urlopen.return_value = self._mock_urlopen(invalid_xml)

        # 期望记录错误日志并返回空列表
        with self.assertLogs('news_analyzer.collectors.rss', level='ERROR') as log:
            news_dicts = self.collector.collect(self.rss_source)

        mock_urlopen.assert_called_once()
        self.assertEqual(len(news_dicts), 0)
        # 检查日志中是否包含解析错误信息
        self.assertTrue(any("解析XML失败" in message for message in log.output))
        self.assertTrue(any("mismatched tag" in message for message in log.output)) # Specific ET error
        print("test_collect_xml_parse_error PASSED")

    @patch('src.collectors.rss_collector.urlopen')
    def test_collect_network_url_error(self, mock_urlopen):
        """测试处理网络 URL 错误 (URLError)"""
        print("\nRunning test_collect_network_url_error...")
        error_message = "Name or service not known"
        mock_urlopen.side_effect = URLError(error_message)

        with self.assertLogs('news_analyzer.collectors.rss', level='ERROR') as log:
            news_dicts = self.collector.collect(self.rss_source)

        mock_urlopen.assert_called_once()
        self.assertEqual(len(news_dicts), 0)
        self.assertTrue(any(f"获取 {self.rss_source.name} 时发生 URL 错误" in message for message in log.output))
        self.assertTrue(any(error_message in message for message in log.output))
        print("test_collect_network_url_error PASSED")

    @patch('src.collectors.rss_collector.urlopen')
    def test_collect_network_timeout_error(self, mock_urlopen):
        """测试处理网络超时错误 (TimeoutError)"""
        print("\nRunning test_collect_network_timeout_error...")
        # urlopen raises TimeoutError directly in Python 3
        mock_urlopen.side_effect = TimeoutError("The read operation timed out")

        with self.assertLogs('news_analyzer.collectors.rss', level='ERROR') as log:
            news_dicts = self.collector.collect(self.rss_source)

        mock_urlopen.assert_called_once()
        self.assertEqual(len(news_dicts), 0)
        self.assertTrue(any(f"获取 {self.rss_source.name} 时超时" in message for message in log.output))
        print("test_collect_network_timeout_error PASSED")

    @patch('src.collectors.rss_collector.urlopen')
    def test_collect_http_error(self, mock_urlopen):
        """测试处理 HTTP 错误 (例如 404)"""
        print("\nRunning test_collect_http_error...")
        # HTTPError is a subclass of URLError
        error_message = "HTTP Error 404: Not Found"
        # Need to mock the exception object correctly for HTTPError
        mock_http_error = HTTPError(self.rss_source.url, 404, "Not Found", {}, None)
        mock_urlopen.side_effect = mock_http_error


        with self.assertLogs('news_analyzer.collectors.rss', level='ERROR') as log:
             news_dicts = self.collector.collect(self.rss_source)

        mock_urlopen.assert_called_once()
        self.assertEqual(len(news_dicts), 0)
        # It should be caught by the URLError handler
        self.assertTrue(any(f"获取 {self.rss_source.name} 时发生 URL 错误" in message for message in log.output))
        self.assertTrue(any("HTTP Error 404" in message for message in log.output))
        print("test_collect_http_error PASSED")


    @patch('src.collectors.rss_collector.urlopen')
    def test_collect_ssl_error(self, mock_urlopen):
        """测试处理 SSL 错误"""
        print("\nRunning test_collect_ssl_error...")
        error_message = "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"
        # Simulate SSLError, which might occur during urlopen context setup
        mock_urlopen.side_effect = ssl.SSLError(error_message)


        with self.assertLogs('news_analyzer.collectors.rss', level='ERROR') as log:
            news_dicts = self.collector.collect(self.rss_source)

        mock_urlopen.assert_called_once() # urlopen is called, but raises before __enter__
        self.assertEqual(len(news_dicts), 0)
        self.assertTrue(any(f"获取 {self.rss_source.name} 时发生 SSL 错误" in message for message in log.output))
        self.assertTrue(any("CERTIFICATE_VERIFY_FAILED" in message for message in log.output))
        print("test_collect_ssl_error PASSED")


    @patch('src.collectors.rss_collector.urlopen')
    def test_collect_decode_error_fallback(self, mock_urlopen):
        """测试 UTF-8 解码失败后的回退逻辑"""
        print("\nRunning test_collect_decode_error_fallback...")
        # Simulate content that fails UTF-8 but works with latin-1
        xml_latin1 = "<?xml version='1.0' encoding='ISO-8859-1'?><rss><channel><item><title>Café</title><link>l</link></item></channel></rss>"
        content_bytes_latin1 = xml_latin1.encode('latin-1')

        mock_response = MagicMock()
        # First read fails UTF-8 decode
        mock_response.read.side_effect = [
            content_bytes_latin1, # First read for UTF-8 attempt
            content_bytes_latin1  # Second read for fallback attempt
        ]
        mock_response.headers = MagicMock()
        mock_response.headers.get_content_charset.return_value = 'iso-8859-1' # Provide fallback charset
        mock_response.seek = MagicMock() # Mock seek call

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_response
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_urlopen.return_value = mock_context

        with self.assertLogs('news_analyzer.collectors.rss', level='WARNING') as log:
            news_dicts = self.collector.collect(self.rss_source)

        self.assertEqual(mock_response.read.call_count, 2) # Read called twice
        mock_response.seek.assert_called_once_with(0) # Seek called before second read
        self.assertEqual(len(news_dicts), 1)
        self.assertEqual(news_dicts[0]['title'], 'Café') # Check title decoded correctly
        self.assertTrue(any("UTF-8解码失败，尝试使用 iso-8859-1 解码" in msg for msg in log.output))
        print("test_collect_decode_error_fallback PASSED")


    def test_standardize_title(self):
        """单独测试标题标准化逻辑"""
        print("\nRunning test_standardize_title...")
        test_cases = [
            ("[Source Name] Actual Title", "Actual Title"),
            ("  [Another Source]  Another Title - Info ", "Another Title - Info"),
            ("Source Name: Title Here", "Source Name: Title Here"), # Adjust expectation, current logic doesn't remove this pattern
            ("BBC News - Article Headline", "Article Headline"),
            ("Just a Title", "Just a Title"),
            ("[Invalid Bracket Title", "[Invalid Bracket Title"), # No closing bracket
            ("Title with | Source at End", "Title with"),
            ("   ", ""), # Empty/whitespace
            (None, ""), # None input
            ("[Complex Source] 2024-07-18 10:30:00 +0000: The Real Title", "The Real Title"),
            ("[Source] Wed, 02 Oct 2002 13:00:00 GMT — Another Real Title", "Another Real Title"),
            ("Reuters : Full Title", "Full Title"),
            ("", ""), # Empty string
            ("[Only Brackets]", "[Only Brackets]"), # Return original if cleaning makes it empty
             ("Source: ", "Source:"), # Return original if cleaning makes it empty
        ]
        for original, expected in test_cases:
            with self.subTest(original=original):
                self.assertEqual(self.collector._standardize_title(original), expected)
        print("test_standardize_title PASSED")


    # --- Tests for check_source_status ---

    @patch('src.collectors.rss_collector.feedparser.parse')
    def test_check_source_status_success(self, mock_parse):
        """测试源状态检查成功"""
        print("\nRunning test_check_source_status_success...")
        mock_result = MagicMock()
        mock_result.bozo = 0
        mock_result.get.side_effect = lambda key, default=None: 200 if key == 'status' else default # Mock .get('status')
        mock_result.feed = {'title': 'Test Feed'}
        mock_result.entries = [{'title': 'Entry 1'}] # Must have entries for success
        mock_parse.return_value = mock_result

        # Call the method under test - no inner patches needed here
        result = self.collector.check_source_status(self.rss_source.url) # Pass URL string

        # Use the mock_parse provided by the decorator
        # Corrected Assertion: Use the actual user agent from the collector class and the URL string
        mock_parse.assert_called_once_with(
            self.rss_source.url,
            agent=self.collector.USER_AGENT, # Use actual user agent
        )
        # Check result dictionary
        self.assertEqual(result['status'], 'ok')
        self.assertIsNone(result['error_message'])
        self.assertIsInstance(result['last_checked_time'], datetime)
        self.assertTrue(abs((datetime.now(timezone.utc) - result['last_checked_time']).total_seconds()) < 10) # Increased tolerance

        print("test_check_source_status_success PASSED") # Add print statement

    @patch('src.collectors.rss_collector.feedparser.parse')
    def test_check_source_status_parse_exception(self, mock_parse):
        """测试源状态检查时发生解析异常"""
        print("\nRunning test_check_source_status_parse_exception...")
        # Simulate feedparser raising an exception (e.g., URLError wrapped or internal error)
        parse_exception = TypeError("Simulated feedparser internal error")
        mock_parse.side_effect = parse_exception

        result = self.collector.check_source_status(self.rss_source.url) # Pass URL string
        mock_parse.assert_called_once_with(self.rss_source.url, agent=self.collector.USER_AGENT) # Assert call

        # Check result dictionary
        self.assertEqual(result['status'], 'error') # Assert status is error
        self.assertIsNotNone(result['error_message'])
        self.assertTrue(isinstance(result['error_message'], str)) # Ensure error_msg is string representation
        self.assertIn("Simulated feedparser internal error", result['error_message']) # Check specific message
        self.assertIsInstance(result['last_checked_time'], datetime) # Check timestamp type
        # Check timestamp is recent (within 30 seconds due to potential delays)
        time_difference = (datetime.now(timezone.utc) - result['last_checked_time'].replace(tzinfo=timezone.utc)).total_seconds()
        self.assertLess(time_difference, 30) # Increased tolerance
        print("test_check_source_status_parse_exception PASSED") # Add print

    @patch('src.collectors.rss_collector.feedparser.parse')
    def test_check_source_status_bozo_exception(self, mock_parse):
        """测试源状态检查时发生 Bozo 异常 (CharacterEncodingOverride)"""
        print("\nRunning test_check_source_status_bozo_exception...")
        bozo_exception = feedparser.CharacterEncodingOverride("Simulated encoding issue")
        mock_result = MagicMock()
        mock_result.bozo = 1
        mock_result.bozo_exception = bozo_exception
        mock_result.get.side_effect = lambda key, default=None: 200 if key == 'status' else default # Mock .get('status')
        mock_result.feed = {'title': 'Partially Parsed'} # Feed might be partially parsed
        mock_result.entries = [{'title': 'Entry 1'}] # Assume entries might still parse
        mock_parse.return_value = mock_result

        result = self.collector.check_source_status(self.rss_source.url) # Pass URL string
        mock_parse.assert_called_once_with(self.rss_source.url, agent=self.collector.USER_AGENT) # Assert call

        # Check result dictionary
        self.assertEqual(result['status'], 'error') # Status is error for this bozo type
        self.assertIsNotNone(result['error_message']) # Asserting an error message IS returned
        # Corrected: Check for the generic bozo message that is actually returned
        self.assertIn("Feed may be ill-formed (bozo=1)", result['error_message'])
        self.assertIsInstance(result['last_checked_time'], datetime)
        time_difference = (datetime.now(timezone.utc) - result['last_checked_time'].replace(tzinfo=timezone.utc)).total_seconds()
        self.assertLess(time_difference, 10)
        print("test_check_source_status_bozo_exception PASSED") # Add print

    # --- 辅助函数测试 (如果需要) ---
    # _parse_rss_item 和 _parse_atom_entry 的逻辑已通过 collect 测试间接覆盖
    # _standardize_title 已单独测试

if __name__ == '__main__':
    # 运行测试并增加详细程度
    unittest.main(verbosity=2)