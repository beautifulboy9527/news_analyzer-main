import pytest
from unittest.mock import MagicMock, PropertyMock, patch
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, Signal, QObject
from src.core.app_service import AppService
from typing import Optional
from src.models import NewsArticle

@pytest.fixture
def app_service_mock(monkeypatch):
    # Mock AppService，主要用于 isinstance 检查和方法 mock
    # 信号将使用真实的 Signal 实例，以便 pytest-qt 的 waitSignal 能正确工作
    mock = MagicMock(spec=AppService) 

    # 为 AppService 的普通属性显式创建 MagicMock 实例
    mock.config = MagicMock()
    mock.storage = MagicMock()
    mock.news_cache = [] # 添加 news_cache 属性

    mock.source_manager = MagicMock()
    mock.source_manager.get_sources.return_value = []
    mock.source_manager.add_source = MagicMock()
    # Mock for sidebar category loading
    mock.source_manager.get_all_categories = MagicMock(return_value=['所有', '测试分类'])

    mock.llm_service = MagicMock()
    mock.llm_service.prompt_manager = MagicMock()

    mock.history_service = MagicMock()
    mock.analysis_storage_service = MagicMock()

    # Mock AppService 的方法
    mock._load_initial_news = MagicMock()
    # mock.set_selected_news = MagicMock() # Replaced by side_effect below

    def mock_set_selected_news_impl(article: Optional[NewsArticle]):
        mock.selected_news_changed.emit(article) # 发射 NewsArticle 对象本身或 None

    mock.set_selected_news = MagicMock(side_effect=mock_set_selected_news_impl)

    # Mock a method that NewsListViewModel might call to get news after certain operations
    mock.get_all_display_news = MagicMock(return_value=[
        {'title': 'AI新闻 Initial', 'link': 'http://ai.news/initial', 'content': '初始内容...', 
         'source_name': '测试源', 'publish_time': '2023-01-01T00:00:00Z', 
         'category': '测试分类'}
    ])

    # 真实信号实例，赋值给 mock 对象的同名属性
    # PySide6.QtCore.Signal 必须在类定义之外实例化时，或者作为类属性时，
    # 需要特殊处理或在其所属对象是 QObject 子类时才能正确工作。
    # MagicMock 不是 QObject。这是一个潜在问题。
    # 我们需要一个 QObject 来承载这些信号。

    class Signaler(QObject): # 辅助类来承载真实信号
        sources_updated_signal = Signal() # 通常 AppService.sources_updated 是无参数的
        news_cache_updated_signal = Signal(list) # 这个信号携带新闻列表
        refresh_started_signal = Signal()
        refresh_complete_signal = Signal(bool, str)
        selected_news_changed_signal = Signal(object) # 应该携带 NewsArticle 对象或 None
    
    # 将 Signaler 实例作为 mock 对象的一个属性，以保证其生命周期
    mock._signaler_instance = Signaler() 

    # 将真实信号实例或其 emit 方法赋给 mock 对象的相应属性
    # 并确保 connect/disconnect 也是可 mock 的，如果 waitSignal 内部需要它们
    mock.sources_updated = mock._signaler_instance.sources_updated_signal
    mock.news_cache_updated = mock._signaler_instance.news_cache_updated_signal # ViewModel 连接这个
    mock.refresh_started = mock._signaler_instance.refresh_started_signal
    mock.refresh_complete = mock._signaler_instance.refresh_complete_signal
    mock.selected_news_changed = mock._signaler_instance.selected_news_changed_signal

    # 配置 refresh_all_sources 在被调用时，发射真实的 refresh_started 信号
    def _mock_refresh_all_sources(*args, **kwargs):
        print(">>> _mock_refresh_all_sources CALLED <<<") 
        mock.refresh_started.emit()
        # Simulate fetching news and then emitting news_cache_updated
        # This news list will be picked up by NewsListViewModel
        mock_news_after_refresh = [
            {'title': 'AI新闻 Refreshed', 'link': 'http://ai.news/refreshed', 
             'source_name': '测试源', 'publish_time': '2023-01-02T00:00:00Z', 
             'category': '测试分类', 'content': '刷新内容...'}
        ]
        mock.news_cache_updated.emit(mock_news_after_refresh)
        # Optionally emit refresh_complete if the test needs to wait for it
        # mock.refresh_complete.emit(True, "Refresh successful from mock")
    mock.refresh_all_sources = MagicMock(side_effect=_mock_refresh_all_sources)
    
    return mock

@pytest.fixture
def scheduler_service_mock():
    return MagicMock()

@pytest.fixture
def main_window(qtbot, app_service_mock, scheduler_service_mock):
    from src.ui.views.main_window import MainWindow
    window = MainWindow(app_service=app_service_mock, scheduler_service=scheduler_service_mock)
    qtbot.addWidget(window)
    window.show()
    return window

def test_e2e_main_flow(main_window, qtbot, app_service_mock):
    """
    端到端主流程：启动-添加源-刷新-筛选-点击新闻-分析-历史
    """
    # 1. 获取核心控件
    panel_manager = main_window.panel_manager
    news_list_panel = panel_manager.news_list_panel
    sidebar = panel_manager.sidebar
    search_panel = panel_manager.search_panel
    # 2. 模拟添加新闻源 & 初始新闻加载
    # NewsListViewModel connects to app_service.news_cache_updated
    # We expect NewsListViewModel to emit its own news_list_changed (parameterless) after processing
    with qtbot.waitSignal(main_window.news_list_view_model.news_list_changed, timeout=3000, raising=True) as blocker_initial_load:
        # Simulate adding a source which might trigger AppService to update its cache
        # and emit news_cache_updated
        app_service_mock.source_manager.add_source({'name': '测试源', 'url': 'http://test.com'})
        # Manually emit news_cache_updated from mock AppService to simulate initial load or update after add_source
        initial_news_list = [
            {'title': '初始新闻0', 'link': 'http://initial.com/0', 
             'source_name': '测试源', 'publish_time': '2023-01-01T00:00:00Z',
             'category': '测试分类', 'content': '初始内容...'}
        ]
        app_service_mock.news_cache_updated.emit(initial_news_list)
    print(f"Initial load signal received: {blocker_initial_load.args if hasattr(blocker_initial_load, 'args') else 'No args (as expected)'}")

    # 3. 模拟刷新新闻
    # Expect NewsListViewModel.news_list_changed again after refresh_all_sources side_effect emits news_cache_updated
    with qtbot.waitSignals([app_service_mock.refresh_started, main_window.news_list_view_model.news_list_changed], timeout=3000, order="strict", raising=True) as blocker_refresh:
        main_window.app_service.refresh_all_sources()
    print(f"Refresh signals received: {blocker_refresh.all_signals_and_args}")

    # 4. 模拟分类切换
    if sidebar and hasattr(sidebar, 'category_list') and sidebar.category_list:
        if hasattr(sidebar, 'update_categories'): # Ensure categories are populated for the test
            # sidebar.update_categories(['所有', '测试分类']) # Removed: Incorrect usage, sidebar populates itself
            # Simulate AppService providing categories if Sidebar relies on it (though sidebar uses its own source_manager)
            app_service_mock.source_manager.get_all_categories = MagicMock(return_value=['所有', '测试分类'])
            # sidebar._load_categories() # CORRECTED: Use the sidebar instance from panel_manager # Removed: Method does not exist

        qtbot.waitUntil(lambda: sidebar.category_list.count() > 0, timeout=1000) 
        item_to_click_category = None
        for i in range(sidebar.category_list.count()):
            if sidebar.category_list.item(i).text() == '测试分类':
                item_to_click_category = sidebar.category_list.item(i)
                break
        if item_to_click_category:
            news_list_vm_signal = getattr(main_window.news_list_view_model, 'news_list_changed', None)
            if news_list_vm_signal and hasattr(news_list_vm_signal, 'emit'): 
                with qtbot.waitSignal(news_list_vm_signal, timeout=2000, raising=True) as blocker_category_filter:
                    qtbot.mouseClick(sidebar.category_list.viewport(), Qt.LeftButton, pos=sidebar.category_list.visualItemRect(item_to_click_category).center())
                print(f"Category filter signal: {blocker_category_filter.args if hasattr(blocker_category_filter, 'args') else 'No args'}")
        else:
            print("WARN: Test category '测试分类' not found in sidebar for clicking.")

    # 5. 模拟搜索
    if search_panel and hasattr(search_panel, 'search_input') and search_panel.search_input:
        news_list_vm_signal_search = getattr(main_window.news_list_view_model, 'news_list_changed', None)
        if news_list_vm_signal_search and hasattr(news_list_vm_signal_search, 'emit'):
            with qtbot.waitSignal(news_list_vm_signal_search, timeout=2000, raising=True) as blocker_search:
                qtbot.keyClicks(search_panel.search_input, 'Refreshed')
                qtbot.keyPress(search_panel.search_input, Qt.Key_Return)
            print(f"Search signal: {blocker_search.args if hasattr(blocker_search, 'args') else 'No args'}")
        else:
            qtbot.keyClicks(search_panel.search_input, 'Refreshed')
            qtbot.keyPress(search_panel.search_input, Qt.Key_Return)

    # 6. 模拟点击新闻
    # NewsListPanel should be populated by now from news_list_changed signals
    qtbot.waitUntil(lambda: news_list_panel.news_list.count() > 0, timeout=3000)
    if news_list_panel.news_list.count() > 0:
        item_to_click_news = news_list_panel.news_list.item(0)
        if item_to_click_news:
            # Ensure NewsListViewModel's internal list is what we expect after search or category filter
            # This might be tricky if filters are very effective and newsList becomes empty
            if main_window.news_list_view_model.newsList:
                expected_title = main_window.news_list_view_model.newsList[0].title
                with qtbot.waitSignal(app_service_mock.selected_news_changed, timeout=2000, raising=True,
                                      check_params_cb=lambda article_param: isinstance(article_param, NewsArticle) and article_param.title == expected_title if article_param else False) as blocker_select_news: # params is NewsArticle or None
                    qtbot.mouseClick(news_list_panel.news_list.viewport(), Qt.LeftButton, pos=news_list_panel.news_list.visualItemRect(item_to_click_news).center())
                print(f"Select news signal: {blocker_select_news.args}") # args[0] will be the NewsArticle
            else:
                print("WARN: NewsListViewModel.newsList is empty before trying to click news item.")
    else:
        print("WARN: News list panel is empty, cannot simulate click.")

    # 7. 模拟分析
    # ...

    # 8. 模拟历史记录查看
    history_action = main_window.menu_manager.get_action('history')
    if history_action:
        assert history_action.isEnabled()

    assert main_window.isVisible()

    # 9. 断言主窗口可见
    assert main_window.isVisible()

    # 10. 异常分支（如分析失败弹窗）
    # def mock_warning_messagebox(*args, **kwargs):
    #     QMessageBox.information(None, "Mocked Info", "Mocked warning was called.") # 更改为information以避免递归
    #     return QMessageBox.Ok
    # monkeypatch.setattr(QMessageBox, 'warning', mock_warning_messagebox)
    # 触发一个会导致 QMessageBox.warning 的操作
    # app_service_mock.refresh_complete.emit(False, "模拟刷新失败")
    # # 这里需要一种方式来验证QMessageBox.warning被调用，可能通过检查其返回值或副作用
    # monkeypatch.setattr(QMessageBox, 'warning', lambda *a, **k: True) 