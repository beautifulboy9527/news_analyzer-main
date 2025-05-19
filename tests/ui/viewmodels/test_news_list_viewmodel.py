import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import Qt

from src.ui.viewmodels.news_list_viewmodel import NewsListViewModel
from src.models import NewsItem

# ---- Fixtures ----
@pytest.fixture
def mock_app_service():
    mock = MagicMock()
    # 模拟 news_cache 属性和信号
    mock.news_cache = []
    mock.news_cache_updated = MagicMock()
    mock.set_selected_news = MagicMock()
    # 模拟 history_service
    mock.history_service = MagicMock()
    mock.history_service.is_read.return_value = False
    mock.history_service.mark_as_read = MagicMock()
    return mock

@pytest.fixture
def sample_news_list():
    # 构造典型的新闻数据
    return [
        NewsItem(title="新闻A", link="a", source_name="源1", content="内容A", category="科技", publish_time=None),
        NewsItem(title="新闻B", link="b", source_name="源2", content="内容B", category="财经", publish_time=None),
        NewsItem(title="新闻C", link="c", source_name="源1", content="内容C", category="科技", publish_time=None),
    ]

# ---- 测试用例 ----
def test_init(mock_app_service):
    """测试 ViewModel 初始化"""
    mock_app_service.news_cache = sample_news_list
    vm = NewsListViewModel(app_service=mock_app_service)
    assert vm._app_service is mock_app_service
    assert vm._history_service is mock_app_service.history_service


def test_filter_by_category(mock_app_service, sample_news_list):
    """测试分类过滤功能"""
    # mock_app_service.news_cache = sample_news_list # 这行对ViewModel内部状态没有直接影响，除非信号被触发
    vm = NewsListViewModel(app_service=mock_app_service)

    # 手动初始化 ViewModel 的内部新闻列表，模拟初始加载完成的状态
    vm._all_news = list(sample_news_list) # 使用副本以防意外修改原始sample_news_list
    vm._apply_filters_and_sort()   # 应用初始过滤和排序（此时应该显示所有新闻）

    # 验证初始状态下，newsList 包含所有样本新闻
    assert len(vm.newsList) == len(sample_news_list), f"Expected initial list length {len(sample_news_list)}, got {len(vm.newsList)}"

    vm.filter_by_category("科技")
    # 验证过滤后只剩下"科技"分类的新闻，并且数量正确
    expected_tech_news_count = sum(1 for item in sample_news_list if item.category == "科技")
    assert len(vm.newsList) == expected_tech_news_count, f"Expected {expected_tech_news_count} '科技' news, got {len(vm.newsList)}"
    assert all(n.category == "科技" for n in vm.newsList)

    vm.filter_by_category("所有")
    # 验证切换回"所有"分类后，newsList 恢复为包含所有样本新闻
    assert len(vm.newsList) == len(sample_news_list), f"Expected list length {len(sample_news_list)} after filtering by '所有', got {len(vm.newsList)}"


def test_search_news(mock_app_service, sample_news_list):
    """测试搜索功能（标题和内容）"""
    # mock_app_service.news_cache = sample_news_list # 这行对ViewModel内部状态没有直接影响
    vm = NewsListViewModel(app_service=mock_app_service)

    # 手动初始化 ViewModel 的内部新闻列表
    vm._all_news = list(sample_news_list)
    vm._apply_filters_and_sort() # 初始应用，确保 newsList 有内容

    # 验证搜索 "新闻A"
    vm.search_news("新闻A", "标题和内容")
    assert len(vm.newsList) > 0, "搜索'新闻A'后列表不应为空"
    assert any("新闻A" in n.title for n in vm.newsList), "未能在标题中找到'新闻A'"

    # 验证搜索 "不存在" (确保列表变空)
    vm.search_news("不存在", "标题和内容")
    assert len(vm.newsList) == 0, f"搜索'不存在'后列表应为空, 实际长度: {len(vm.newsList)}"


def test_sort_news(mock_app_service, sample_news_list):
    """测试排序功能"""
    vm = NewsListViewModel(app_service=mock_app_service)
    # 构造带有不同标题的新闻
    news = [NewsItem(title=t, link=t, source_name="源", category="科技") for t in ["C", "A", "B"]]
    vm._all_news = news
    vm.sort_news("title", Qt.AscendingOrder)
    titles = [n.title for n in vm.newsList]
    assert titles == sorted(titles)
    vm.sort_news("title", Qt.DescendingOrder)
    titles_desc = [n.title for n in vm.newsList]
    assert titles_desc == sorted(titles, reverse=True)


def test_mark_as_read_and_is_read(mock_app_service, sample_news_list):
    """测试已读状态相关方法"""
    vm = NewsListViewModel(app_service=mock_app_service)
    vm._all_news = sample_news_list
    link = sample_news_list[0].link
    vm.mark_as_read(link)
    mock_app_service.history_service.mark_as_read.assert_called_with(link)
    # 测试 is_read 调用
    vm.is_read(link)
    mock_app_service.history_service.is_read.assert_called_with(link)


def test_signals_emitted(mock_app_service, sample_news_list, qtbot):
    """测试信号是否正确发射"""
    vm = NewsListViewModel(app_service=mock_app_service)
    vm._all_news = sample_news_list
    with qtbot.waitSignal(vm.news_list_changed, timeout=1000):
        vm.filter_by_category("科技")
    with qtbot.waitSignal(vm.news_list_changed, timeout=1000):
        vm.search_news("新闻A", "标题和内容")
    with qtbot.waitSignal(vm.news_list_changed, timeout=1000):
        vm.clear_search()


def test_empty_news_list(mock_app_service):
    """测试空新闻列表下的行为"""
    mock_app_service.news_cache = []
    vm = NewsListViewModel(app_service=mock_app_service)
    vm.filter_by_category("科技")
    assert vm.newsList == []
    vm.search_news("任意", "标题和内容")
    assert vm.newsList == []
    vm.sort_news("title", Qt.AscendingOrder)
    assert vm.newsList == []


def test_invalid_category(mock_app_service, sample_news_list):
    """测试无效分类过滤（应返回空列表或全部）"""
    mock_app_service.news_cache = sample_news_list
    vm = NewsListViewModel(app_service=mock_app_service)
    vm.filter_by_category("不存在的分类")
    assert vm.newsList == []


def test_invalid_search_field(mock_app_service, sample_news_list):
    """测试无效搜索字段描述（应默认搜索标题和内容）"""
    # mock_app_service.news_cache = sample_news_list # 这行对ViewModel内部状态没有直接影响
    vm = NewsListViewModel(app_service=mock_app_service)

    # 手动初始化 ViewModel 的内部新闻列表
    vm._all_news = list(sample_news_list)
    vm._apply_filters_and_sort() # 初始应用

    # 传入错误的字段描述
    vm.search_news("新闻A", "错误字段")
    # 验证是否至少有一条新闻的标题包含"新闻A"（因为默认应搜索标题和内容）
    assert len(vm.newsList) > 0, "使用无效字段搜索'新闻A'后列表不应为空"
    # 只要标题或内容包含即可 (这里我们测试的样本数据中，"新闻A"在标题里)
    assert any("新闻A" in n.title for n in vm.newsList), "使用无效字段搜索时未能在标题中找到'新闻A'"


def test_none_and_empty_fields(mock_app_service):
    """测试新闻标题/内容为 None 或空字符串时的健壮性"""
    news = [
        NewsItem(title=None, link="a", source_name="源", content=None, category="科技"),
        NewsItem(title="", link="b", source_name="源", content="", category="科技"),
    ]
    mock_app_service.news_cache = news
    vm = NewsListViewModel(app_service=mock_app_service)
    # 搜索任意关键词不应抛异常
    vm.search_news("新闻", "标题和内容")
    assert isinstance(vm.newsList, list)


def test_history_service_none(sample_news_list):
    """测试 history_service 为 None 时的健壮性（如只读操作不抛异常）"""
    mock_app_service = MagicMock()
    mock_app_service.news_cache = sample_news_list
    mock_app_service.news_cache_updated = MagicMock()
    mock_app_service.set_selected_news = MagicMock()
    mock_app_service.history_service = None  # 关键：无历史服务
    vm = NewsListViewModel(app_service=mock_app_service)
    # 调用 is_read/mark_as_read 不应抛异常
    try:
        vm.is_read("a")
        vm.mark_as_read("a")
    except Exception as e:
        pytest.fail(f"history_service 为 None 时抛异常: {e}")


def is_read(self, link: str) -> bool:
    """检查新闻是否已读 (通过 HistoryService)"""
    if self._history_service is None:
        self.logger.warning("HistoryService is None, is_read 默认返回 False")
        return False
    return self._history_service.is_read(link)

def mark_as_read(self, link: str):
    """标记指定链接的新闻为已读，并更新内部状态"""
    if self._history_service is None:
        self.logger.warning("HistoryService is None, mark_as_read 跳过")
        return 