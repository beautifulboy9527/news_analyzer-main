# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch, MagicMock
import requests # 导入 requests 用于 Mock
from datetime import datetime, timezone, timedelta

from urllib.parse import urljoin # 导入 urljoin
# 导入需要测试的类和模型
from src.collectors.pengpai_collector import PengpaiCollector
from src.models import NewsSource # 修正：使用 NewsSource，不再需要 NewsItem，因为 collect 返回 dict
# 不再需要 ApiClient

# 定义一些模拟数据和常量
MOCK_URL = "https://www.thepaper.cn/"
# MOCK_SOURCE_ID = "pengpai" # 移除不再需要的 ID
MOCK_SOURCE_NAME = "澎湃新闻"

# 模拟有效的 HTML 响应内容 (包含新闻列表)
VALID_HTML_CONTENT = """
<html>
<body>
  <div class="news_list">
    <div class="news_li">
      <h5><a href="https://www.thepaper.cn/newsDetail_forward_27000001" target="_blank">新闻标题1</a></h5>
      <div class="pdtt_trbs">
        <span class="trbszan">摘要1...</span>
        <span class="pdtt_rq">2025-04-05 10:00</span>
      </div>
    </div>
    <div class="news_li">
      <h5><a href="https://www.thepaper.cn/newsDetail_forward_27000002" target="_blank">新闻标题2</a></h5>
      <div class="pdtt_trbs">
        <span class="trbszan">摘要2...</span>
        <span class="pdtt_rq">2025-04-05 11:30</span>
      </div>
    </div>
    <div class="news_li">
      <h5><a href="https://www.thepaper.cn/newsDetail_forward_27000003" target="_blank">新闻标题3</a></h5>
      <div class="pdtt_trbs">
        <span class="trbszan">摘要3...</span>
        <span class="pdtt_rq">今天 09:15</span>
      </div>
    </div>
     <div class="news_li">
      <h5><a href="https://www.thepaper.cn/newsDetail_forward_27000004" target="_blank">新闻标题4</a></h5>
      <div class="pdtt_trbs">
        <span class="trbszan">摘要4...</span>
        <span class="pdtt_rq">1小时前</span>
      </div>
    </div>
  </div>
</body>
</html>
"""

# 模拟空的 HTML 响应内容 (没有新闻条目)
EMPTY_HTML_CONTENT = """
<html>
<body>
  <div class="news_list">
    <!-- No news items here -->
  </div>
</body>
</html>
"""

# 模拟无效的 HTML 响应内容
INVALID_HTML_CONTENT = """
<html><body><p>This is not the expected structure.</p></body></html>
"""

# 模拟网络请求错误
MOCK_NETWORK_ERROR = ConnectionError("Failed to connect")

# 模拟 HTTP 错误
MOCK_HTTP_ERROR = Exception("HTTP Error 404: Not Found") # 实际中 ApiClient 可能抛出自定义异常


class TestPengpaiCollector(unittest.TestCase):

    def setUp(self):
        """测试前的准备工作"""
        # 修正：使用 NewsSource 并传入正确的参数
        self.source = NewsSource(name=MOCK_SOURCE_NAME, type="pengpai", url=MOCK_URL, custom_config={
            # 提供测试用的选择器配置，模拟实际情况
            'news_list_selector': 'div.news_list div.news_li a[href*="/newsDetail_forward_"]',
            'title_selector': 'h5', # 假设列表页标题在 h5 内
            'content_selector': 'div.index_cententWrap__Jv8jK', # 详情页内容选择器
            'time_selector': 'span.pdtt_rq', # 详情页时间选择器 (模拟)
            'author_selector': 'div.author' # 详情页作者选择器 (模拟)
        })
        # 修正：PengpaiCollector 初始化不需要参数
        self.collector = PengpaiCollector()
        # 获取当前日期用于比较 "今天" 和 "X小时前" - 注意：日期解析现在发生在 _fetch_detail 的模拟中
        self.today = datetime.now(timezone(timedelta(hours=8))).date() # 假设服务器/测试环境为 UTC+8

    @patch('requests.Session.get')
    @patch.object(PengpaiCollector, '_fetch_detail') # Mock _fetch_detail 方法
    def test_fetch_news_success(self, mock_fetch_detail, mock_session_get):
        """测试成功获取和解析新闻列表，并模拟详情获取"""
        # 配置 mock_session_get
        mock_response = MagicMock()
        mock_response.text = VALID_HTML_CONTENT
        mock_response.raise_for_status.return_value = None
        mock_response.encoding = 'utf-8' # 确保编码设置
        mock_session_get.return_value = mock_response

        # 配置 mock_fetch_detail 的返回值
        # 模拟不同链接返回不同的详情数据
        def side_effect_fetch_detail(url, selector_config, source_name):
            if "27000001" in url:
                return {'pub_date': '2025-04-05 10:00', 'content': '新闻内容1', 'author': '作者1'}
            elif "27000002" in url:
                return {'pub_date': '2025-04-05 11:30', 'content': '新闻内容2', 'author': '作者2'}
            elif "27000003" in url:
                # 模拟 "今天" 的情况，返回具体日期时间字符串
                today_str = self.today.strftime("%Y-%m-%d")
                return {'pub_date': f'{today_str} 09:15', 'content': '新闻内容3', 'author': '作者3'}
            elif "27000004" in url:
                 # 模拟 "X小时前" 的情况，返回具体日期时间字符串
                now_dt = datetime.now(timezone(timedelta(hours=8)))
                one_hour_ago = now_dt - timedelta(hours=1)
                return {'pub_date': one_hour_ago.strftime("%Y-%m-%d %H:%M"), 'content': '新闻内容4', 'author': '作者4'}
            else:
                return {'pub_date': None, 'content': None, 'author': None}
        mock_fetch_detail.side_effect = side_effect_fetch_detail

        # 修正：调用 collect 方法
        news_items_dicts = self.collector.collect(self.source)

        # 验证 mock_session_get 被调用
        mock_session_get.assert_called_once_with(self.collector.MOBILE_URL, timeout=20)

        # 验证 mock_fetch_detail 被调用了 4 次，并检查参数
        self.assertEqual(mock_fetch_detail.call_count, 4)
        # 修正：expected_calls 应使用从 HTML 提取的实际绝对 URL
        expected_calls = [
            unittest.mock.call('https://www.thepaper.cn/newsDetail_forward_27000001', self.source.custom_config, self.source.name),
            unittest.mock.call('https://www.thepaper.cn/newsDetail_forward_27000002', self.source.custom_config, self.source.name),
            unittest.mock.call('https://www.thepaper.cn/newsDetail_forward_27000003', self.source.custom_config, self.source.name),
            unittest.mock.call('https://www.thepaper.cn/newsDetail_forward_27000004', self.source.custom_config, self.source.name),
        ]
        mock_fetch_detail.assert_has_calls(expected_calls, any_order=True) # 顺序可能因解析而异，使用 any_order

        # 验证返回的字典列表
        self.assertEqual(len(news_items_dicts), 4)

        # 验证第一条新闻字典
        item1_dict = next(item for item in news_items_dicts if "27000001" in item['link']) # 通过 link 查找确保顺序无关
        self.assertIsInstance(item1_dict, dict)
        self.assertEqual(item1_dict['title'], "新闻标题1")
        self.assertEqual(item1_dict['link'], 'https://www.thepaper.cn/newsDetail_forward_27000001') # 修正：验证实际的绝对链接
        self.assertEqual(item1_dict['pub_date'], '2025-04-05 10:00') # 验证从 mock 获取的日期字符串
        self.assertEqual(item1_dict['content'], '新闻内容1')
        # self.assertEqual(item1_dict['author'], '作者1') # 如果需要验证作者

        # 验证第二条新闻字典
        item2_dict = next(item for item in news_items_dicts if "27000002" in item['link'])
        self.assertEqual(item2_dict['title'], "新闻标题2")
        self.assertEqual(item2_dict['link'], 'https://www.thepaper.cn/newsDetail_forward_27000002') # 修正：验证实际的绝对链接
        self.assertEqual(item2_dict['pub_date'], '2025-04-05 11:30')

        # 验证第三条新闻字典 ("今天 HH:MM")
        item3_dict = next(item for item in news_items_dicts if "27000003" in item['link'])
        self.assertEqual(item3_dict['title'], "新闻标题3")
        today_str = self.today.strftime("%Y-%m-%d")
        self.assertEqual(item3_dict['pub_date'], f'{today_str} 09:15')

        # 验证第四条新闻字典 ("X小时前")
        item4_dict = next(item for item in news_items_dicts if "27000004" in item['link'])
        self.assertEqual(item4_dict['title'], "新闻标题4")
        # 对于 "X小时前"，我们只验证日期部分是今天，因为精确时间取决于 mock_fetch_detail 的模拟
        # Verify the format is YYYY-MM-DD HH:MM instead of checking against today's date
        # This avoids issues running tests near midnight.
        self.assertRegex(item4_dict['pub_date'], r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}')

        # 再次移除残留的旧断言

        # 移除验证 NewsItem 对象的旧断言块，因为 collect 返回的是字典列表

    @patch('requests.Session.get')
    @patch.object(PengpaiCollector, '_fetch_detail') # 仍然需要 Mock _fetch_detail，即使它不应被调用
    def test_fetch_news_empty_list(self, mock_fetch_detail, mock_session_get):
        """测试 HTML 中没有新闻条目的情况"""
        # 配置 mock_session_get
        mock_response = MagicMock()
        mock_response.text = EMPTY_HTML_CONTENT
        mock_response.raise_for_status.return_value = None
        mock_response.encoding = 'utf-8'
        mock_session_get.return_value = mock_response

        # 修正：调用 collect 方法
        news_items_dicts = self.collector.collect(self.source)

        # 验证 mock_session_get 被调用
        mock_session_get.assert_called_once_with(self.collector.MOBILE_URL, timeout=20)
        # 验证 _fetch_detail 没有被调用
        mock_fetch_detail.assert_not_called()
        # 验证返回空列表
        self.assertEqual(len(news_items_dicts), 0)

    @patch('requests.Session.get')
    @patch.object(PengpaiCollector, '_fetch_detail')
    def test_fetch_news_invalid_html(self, mock_fetch_detail, mock_session_get):
        """测试无效 HTML 的情况 (选择器找不到匹配)"""
        # 配置 mock_session_get
        mock_response = MagicMock()
        mock_response.text = INVALID_HTML_CONTENT
        mock_response.raise_for_status.return_value = None
        mock_response.encoding = 'utf-8'
        mock_session_get.return_value = mock_response

        # 修正：调用 collect 方法
        news_items_dicts = self.collector.collect(self.source)

        # 验证 mock_session_get 被调用
        mock_session_get.assert_called_once_with(self.collector.MOBILE_URL, timeout=20)
        # 验证 _fetch_detail 没有被调用
        mock_fetch_detail.assert_not_called()
        # 验证返回空列表
        self.assertEqual(len(news_items_dicts), 0) # 预期解析失败返回空列表

    @patch('requests.Session.get')
    @patch.object(PengpaiCollector, '_fetch_detail')
    def test_fetch_news_network_error(self, mock_fetch_detail, mock_session_get):
        """测试网络请求发生错误的情况 (requests 异常)"""
        # 配置 mock_session_get 抛出异常
        mock_session_get.side_effect = requests.exceptions.ConnectionError("Failed to connect")

        # 修正：调用 collect 方法
        news_items_dicts = self.collector.collect(self.source)

        # 验证 mock_session_get 被调用
        mock_session_get.assert_called_once_with(self.collector.MOBILE_URL, timeout=20)
        # 验证 _fetch_detail 没有被调用
        mock_fetch_detail.assert_not_called()
        # 验证返回空列表
        self.assertEqual(len(news_items_dicts), 0) # 预期捕获异常并返回空列表

    @patch('requests.Session.get')
    @patch.object(PengpaiCollector, '_fetch_detail')
    def test_fetch_news_http_error(self, mock_fetch_detail, mock_session_get):
        """测试网络请求返回 HTTP 错误的情况 (raise_for_status 抛出异常)"""
        # 配置 mock_session_get
        mock_response = MagicMock()
        mock_response.text = "Server Error"
        # 模拟 raise_for_status 抛出 HTTPError
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_response.encoding = 'utf-8'
        mock_session_get.return_value = mock_response

        # 修正：调用 collect 方法
        news_items_dicts = self.collector.collect(self.source)

        # 验证 mock_session_get 被调用
        mock_session_get.assert_called_once_with(self.collector.MOBILE_URL, timeout=20)
        # 验证 _fetch_detail 没有被调用
        mock_fetch_detail.assert_not_called()
        # 验证返回空列表
        self.assertEqual(len(news_items_dicts), 0) # 预期捕获异常并返回空列表

    # 可以添加更多测试用例，例如测试 _fetch_detail 返回无效数据等

if __name__ == '__main__':
    unittest.main()