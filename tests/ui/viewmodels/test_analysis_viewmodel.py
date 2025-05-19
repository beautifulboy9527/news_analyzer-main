import pytest
from unittest.mock import MagicMock
from src.ui.viewmodels.analysis_viewmodel import AnalysisViewModel

# ---- Fixtures ----
@pytest.fixture
def mock_analysis_service():
    service = MagicMock()
    service.analysis_completed = MagicMock()
    service.analysis_failed = MagicMock()
    return service

@pytest.fixture
def analysis_viewmodel(mock_analysis_service):
    return AnalysisViewModel(analysis_service=mock_analysis_service)

# ---- 测试用例 ----
def test_analyze_success(analysis_viewmodel, mock_analysis_service, qtbot):
    """
    测试分析请求成功，监听 analysis_completed 信号。
    """
    article = {'id': 1, 'title': 'test'}
    mock_analysis_service.analyze_single_article.return_value = None
    # 假设 AnalysisViewModel 连接了 analysis_service.analysis_completed 信号
    with qtbot.waitSignal(analysis_viewmodel.analysis_completed, timeout=1000) as blocker:
        analysis_viewmodel.analyze_article(article, 'summary')
        # 手动触发 service 的信号
        analysis_viewmodel._on_analysis_completed('summary', {'summary': 'ok'})
    assert blocker.args[0] == 'summary'
    assert blocker.args[1] == {'summary': 'ok'}

def test_analyze_failed(analysis_viewmodel, mock_analysis_service, qtbot):
    """
    测试分析请求失败，监听 analysis_failed 信号。
    """
    article = {'id': 1, 'title': 'test'}
    mock_analysis_service.analyze_single_article.return_value = None
    with qtbot.waitSignal(analysis_viewmodel.analysis_failed, timeout=1000) as blocker:
        analysis_viewmodel.analyze_article(article, 'summary')
        analysis_viewmodel._on_analysis_failed('summary', 'error')
    assert blocker.args[0] == 'summary'
    assert blocker.args[1] == 'error'

def test_analyze_article_no_service():
    """
    analysis_service 为 None 时，analyze_article 不应抛异常。
    """
    vm = AnalysisViewModel(analysis_service=None)
    try:
        vm.analyze_article({'id': 1}, 'summary')
    except Exception as e:
        pytest.fail(f"analyze_article raised exception when service is None: {e}")

def test_init_no_signal_attrs():
    """
    analysis_service 无 analysis_completed/failed 信号属性时，初始化不应抛异常。
    """
    class DummyService:  # 不带信号属性
        def analyze_single_article(self, article, analysis_type):
            pass
    try:
        vm = AnalysisViewModel(analysis_service=DummyService())
    except Exception as e:
        pytest.fail(f"Init raised exception when service has no signals: {e}")

def test_multiple_analyze_requests(analysis_viewmodel, mock_analysis_service, qtbot):
    """
    连续多次分析请求，信号参数应隔离。
    """
    article1 = {'id': 1, 'title': 'A'}
    article2 = {'id': 2, 'title': 'B'}
    with qtbot.waitSignal(analysis_viewmodel.analysis_completed, timeout=1000) as blocker1:
        analysis_viewmodel.analyze_article(article1, 'summary')
        analysis_viewmodel._on_analysis_completed('summary', {'summary': 'A'})
    assert blocker1.args[0] == 'summary'
    assert blocker1.args[1] == {'summary': 'A'}
    with qtbot.waitSignal(analysis_viewmodel.analysis_completed, timeout=1000) as blocker2:
        analysis_viewmodel.analyze_article(article2, 'summary')
        analysis_viewmodel._on_analysis_completed('summary', {'summary': 'B'})
    assert blocker2.args[0] == 'summary'
    assert blocker2.args[1] == {'summary': 'B'}

def test_analyze_article_edge_cases(analysis_viewmodel, mock_analysis_service):
    """
    analyze_article 传入 None、空 dict、未知 analysis_type 等边界情况。
    """
    # None 作为 article
    try:
        analysis_viewmodel.analyze_article(None, 'summary')
    except Exception as e:
        pytest.fail(f"analyze_article raised exception with None article: {e}")
    # 空 dict
    try:
        analysis_viewmodel.analyze_article({}, 'summary')
    except Exception as e:
        pytest.fail(f"analyze_article raised exception with empty dict: {e}")
    # analysis_type 为 None
    try:
        analysis_viewmodel.analyze_article({'id': 1}, None)
    except Exception as e:
        pytest.fail(f"analyze_article raised exception with None analysis_type: {e}")
    # analysis_type 为未知类型
    try:
        analysis_viewmodel.analyze_article({'id': 1}, 'unknown_type')
    except Exception as e:
        pytest.fail(f"analyze_article raised exception with unknown analysis_type: {e}") 