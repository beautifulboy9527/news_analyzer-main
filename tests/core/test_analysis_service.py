# tests/core/test_analysis_service.py

import pytest
from unittest.mock import Mock, patch, call, MagicMock, ANY
from datetime import datetime
import json

# Assuming pytest-qt is used for signal testing
from pytestqt.qt_compat import qt_api
from pytestqt.exceptions import TimeoutError as QtSignalTimeoutError # Import specific exception

from src.core.analysis_service import AnalysisService
from src.models import NewsArticle

# Helper for signal spying
class SignalSpy:
    def __init__(self, qtbot, signal_name="signal"):
        self.qtbot = qtbot
        self.signal_name = signal_name
        self.called = False
        self.args = None
        self.all_args = [] # Store all calls
        self.call_count = 0

    def __call__(self, *args):
        # print(f"SignalSpy ({self.signal_name}) CALLED with args: {args}")
        self.called = True
        self.args = args # Last call args
        self.all_args.append(args)
        self.call_count += 1

    def assert_called_once_with(self, *expected_args):
        debug_file_path = "test_signal_spy_output.log"
        with open(debug_file_path, "a", encoding="utf-8") as f: # Open in append mode
            f.write(f"--- New Assert Call ({self.signal_name}) ---\n")
            # self.qtbot.wait(50) # Moved wait to after action in test
            if self.call_count == 0:
                f.write(f"ERROR: Expected signal '{self.signal_name}' to be emitted once, but was not emitted.\n")
                raise AssertionError(f"Expected signal '{self.signal_name}' to be emitted once, but was not emitted.")
            if self.call_count > 1:
                pass # Allow multiple calls
            
            match_found = False
            f.write(f"SignalSpy ({self.signal_name}) ASSERTING: expected_args = {repr(expected_args)} (type: {type(expected_args)})\n")
            for i, recorded_args in enumerate(self.all_args):
                f.write(f"SignalSpy ({self.signal_name}) comparing with recorded_args[{i}] = {repr(recorded_args)} (type: {type(recorded_args)})\n")
                if recorded_args == expected_args:
                    f.write(f"SignalSpy ({self.signal_name}) MATCH FOUND with recorded_args[{i}]\n")
                    match_found = True
                    break
                else:
                    f.write(f"SignalSpy ({self.signal_name}) NO MATCH with recorded_args[{i}]\n")
                    if len(recorded_args) == len(expected_args) and len(recorded_args) > 0:
                        for j in range(len(recorded_args)):
                            if recorded_args[j] != expected_args[j]:
                                f.write(f"  Element mismatch at index {j}:\n")
                                f.write(f"    recorded: {repr(recorded_args[j])} (type: {type(recorded_args[j])})\n")
                                f.write(f"    expected: {repr(expected_args[j])} (type: {type(expected_args[j])})\n")

            if not match_found:
                f.write(f"ERROR: Signal '{self.signal_name}' expected with {expected_args} but no such call was recorded. All calls: {self.all_args}\n")
                raise AssertionError(f"Signal '{self.signal_name}' expected with {expected_args} but no such call was recorded. All calls: {self.all_args}")
            f.write(f"--- End Assert Call ({self.signal_name}) ---\n")

    def assert_not_called(self):
        # self.qtbot.wait(50) # Moved wait to after action in test
        assert not self.called, f"Expected signal '{self.signal_name}' not to be emitted, but it was."
    
    def get_last_args(self):
        return self.args

    def was_called_with_substring(self, substring_to_find):
        for recorded_args_tuple in self.all_args:
            if isinstance(recorded_args_tuple, tuple) and len(recorded_args_tuple) > 0:
                if isinstance(recorded_args_tuple[0], str) and substring_to_find in recorded_args_tuple[0]:
                    return True
        return False

# Mock dependencies
@pytest.fixture
def mock_dependencies():
    return {
        'llm_service': MagicMock(),
        'news_storage': MagicMock(),
        'event_analyzer': MagicMock(),
    }

@pytest.fixture
def analysis_service(mock_dependencies):
    return AnalysisService(
        llm_service=mock_dependencies['llm_service'], 
        news_storage=mock_dependencies['news_storage'],
        event_analyzer=mock_dependencies['event_analyzer']
    )

@pytest.fixture
def mock_event_analyzer():
    return Mock()

@pytest.fixture
def sample_article_obj():
    """Provides a sample NewsArticle object for testing."""
    return NewsArticle(
        id=123,
        title="Test Article Title",
        link="http://example.com/test",
        content="Test content.",
        source_name="TestSource",
        publish_time=datetime.now()
    )

# --- Tests for analyze_single_article --- 

def test_analyze_single_article_success(analysis_service, mock_dependencies, sample_article_obj, qtbot):
    """
    测试单篇分析流程，LLMService 正常返回，结果正确保存，监听 single_analysis_completed 信号。
    """
    article_to_analyze = sample_article_obj
    analysis_type = 'summary'
    llm_result_data = {'summary_text': 'This is a great summary.', 'confidence': 0.9, 'params': {'model': 'gpt-test'}}
    
    mock_dependencies['llm_service'].analyze_news.return_value = llm_result_data
    mock_dependencies['news_storage'].add_llm_analysis.return_value = 789 # Dummy analysis ID

    with qtbot.waitSignal(analysis_service.single_analysis_completed, timeout=1000) as blocker:
        analysis_service.analyze_single_article(article_to_analyze, analysis_type)
    
    assert blocker.args[0] == analysis_type
    assert blocker.args[1] == llm_result_data
    
    mock_dependencies['llm_service'].analyze_news.assert_called_once_with(
        article=article_to_analyze,
        analysis_type=analysis_type,
        custom_prompt=None
    )

    # Service logic for main_result_text:
    # result_data.get('analysis_text', result_data.get('summary', result_data.get('result', str(result_data))))
    # Since llm_result_data does not contain 'analysis_text', 'summary', or 'result',
    # it will use str(llm_result_data).
    expected_analysis_result_text = str(llm_result_data)

    expected_payload = {
        "analysis_timestamp": ANY, 
        "analysis_type": analysis_type,
        "analysis_result_text": expected_analysis_result_text, 
        "meta_news_titles": json.dumps([article_to_analyze.title]),
        "meta_news_sources": json.dumps([article_to_analyze.source_name]),
        "meta_analysis_params": json.dumps(llm_result_data.get("params", {})),
        "meta_prompt_hash": llm_result_data.get("prompt_hash"),
        "meta_error_info": llm_result_data.get("error")
    }
    mock_dependencies['news_storage'].add_llm_analysis.assert_called_once_with(
        expected_payload,
        article_ids_to_map=[article_to_analyze.id]
    )

def test_analyze_single_article_llm_exception(analysis_service, mock_dependencies, sample_article_obj, qtbot):
    """
    测试 LLMService 抛异常，监听 analysis_failed 信号。
    """
    article_to_analyze = sample_article_obj
    mock_dependencies['llm_service'].analyze_news.side_effect = Exception('llm error')
    with qtbot.waitSignal(analysis_service.analysis_failed, timeout=1000) as blocker:
        analysis_service.analyze_single_article(article_to_analyze, 'summary')
    assert blocker.args[0] == 'summary'
    assert 'llm error' in blocker.args[1]
    mock_dependencies['news_storage'].add_llm_analysis.assert_not_called()

def test_analyze_single_article_storage_save_fails(analysis_service, mock_dependencies, sample_article_obj, qtbot):
    """Test that if news_storage.add_llm_analysis fails, appropriate signals are emitted."""
    article_to_analyze = sample_article_obj
    analysis_type = "stance"
    llm_result_data = {"stance": "neutral", "analysis_text": "Neutral stance."}
    storage_error_message = "DB connection lost"

    mock_dependencies['llm_service'].analyze_news.return_value = llm_result_data
    mock_dependencies['news_storage'].add_llm_analysis.side_effect = Exception(storage_error_message)

    spy_status_updated = SignalSpy(qtbot, signal_name='status_message_updated_save_fail')
    analysis_service.status_message_updated.connect(spy_status_updated)

    completed_signal_ok = False
    def check_completed_cb(type_arg, result_arg):
        nonlocal completed_signal_ok
        if type_arg == analysis_type and result_arg == llm_result_data:
            completed_signal_ok = True
            return True
        return False

    try:
        with qtbot.waitSignal(analysis_service.single_analysis_completed, 
                              timeout=1000, 
                              check_params_cb=check_completed_cb) as blocker_completed:
            analysis_service.analyze_single_article(article_to_analyze, analysis_type)
        
        assert completed_signal_ok, "single_analysis_completed signal criteria not met."

        # After the action, process events and check the spy for the specific status update
        qtbot.wait(100) # Process events to ensure spy has captured signals

        expected_status_substring = f"分析结果保存失败 ({analysis_type})"
        assert spy_status_updated.was_called_with_substring(expected_status_substring), \
               f"Expected status_message_updated to contain '{expected_status_substring}'. All calls: {spy_status_updated.all_args}"

    finally:
        try:
            analysis_service.status_message_updated.disconnect(spy_status_updated)
        except RuntimeError:
            pass # In case it was already disconnected or never connected

    mock_dependencies['llm_service'].analyze_news.assert_called_once()
    mock_dependencies['news_storage'].add_llm_analysis.assert_called_once()

def test_analyze_single_article_invalid_input(analysis_service, mock_dependencies, qtbot):
    """Test analysis with invalid input (e.g., missing link)."""
    invalid_article = NewsArticle(id=2, title="Invalid", link=None, content="", source_name="", publish_time=None)
    analysis_type = "summary"

    with qtbot.waitSignal(analysis_service.analysis_failed, timeout=1000) as blocker:
        analysis_service.analyze_single_article(invalid_article, analysis_type)

    assert blocker.args[0] == analysis_type
    assert blocker.args[1] == "无效的文章数据" 
    
    mock_dependencies['llm_service'].analyze_news.assert_not_called()
    mock_dependencies['news_storage'].add_llm_analysis.assert_not_called()

# --- Tests for LLM Analysis Data Management ---

def test_get_llm_analysis_by_id_found(analysis_service, mock_dependencies):
    analysis_id = 1
    expected_data = {"id": 1, "analysis_type": "summary", "result": "Test summary"}
    mock_dependencies['news_storage'].get_llm_analysis_by_id.return_value = expected_data
    
    result = analysis_service.get_llm_analysis_by_id(analysis_id)
    
    assert result == expected_data
    mock_dependencies['news_storage'].get_llm_analysis_by_id.assert_called_once_with(analysis_id)

def test_get_llm_analysis_by_id_not_found(analysis_service, mock_dependencies):
    analysis_id = 99
    mock_dependencies['news_storage'].get_llm_analysis_by_id.return_value = None
    
    result = analysis_service.get_llm_analysis_by_id(analysis_id)
    
    assert result is None
    mock_dependencies['news_storage'].get_llm_analysis_by_id.assert_called_once_with(analysis_id)

def test_get_llm_analyses_for_article_found(analysis_service, mock_dependencies):
    article_id = 10
    expected_data = [{"id": 1, "result": "Summary"}, {"id": 2, "result": "Stance"}]
    mock_dependencies['news_storage'].get_llm_analyses_for_article.return_value = expected_data
    
    result = analysis_service.get_llm_analyses_for_article(article_id)
    
    assert result == expected_data
    mock_dependencies['news_storage'].get_llm_analyses_for_article.assert_called_once_with(article_id)

def test_get_llm_analyses_for_article_not_found(analysis_service, mock_dependencies):
    article_id = 99
    mock_dependencies['news_storage'].get_llm_analyses_for_article.return_value = []
    
    result = analysis_service.get_llm_analyses_for_article(article_id)
    
    assert result == []
    mock_dependencies['news_storage'].get_llm_analyses_for_article.assert_called_once_with(article_id)

def test_get_all_llm_analyses(analysis_service, mock_dependencies):
    expected_data = [{"id": 1}, {"id": 2}]
    mock_dependencies['news_storage'].get_all_llm_analyses.return_value = expected_data
    
    result = analysis_service.get_all_llm_analyses(limit=10, offset=0)
    
    assert result == expected_data
    mock_dependencies['news_storage'].get_all_llm_analyses.assert_called_once_with(limit=10, offset=0)

def test_delete_llm_analysis_failure(analysis_service, mock_dependencies, qtbot):
    analysis_id = 99
    mock_dependencies['news_storage'].delete_llm_analysis.return_value = False
    
    spy_status_updated = SignalSpy(qtbot, signal_name='status_message_updated_delete_fail')
    analysis_service.status_message_updated.connect(spy_status_updated)

    try:
        success = analysis_service.delete_llm_analysis(analysis_id)
        qtbot.wait(100) # Wait for signal to be processed by spy
        
        assert success is False
        mock_dependencies['news_storage'].delete_llm_analysis.assert_called_once_with(analysis_id)
        spy_status_updated.assert_called_once_with(f"删除分析记录 ID {analysis_id} 失败。")
    finally:
        try:
            analysis_service.status_message_updated.disconnect(spy_status_updated)
        except RuntimeError: 
            pass

def test_delete_all_llm_analyses_success(analysis_service, mock_dependencies, qtbot):
    mock_dependencies['news_storage'].delete_all_llm_analyses.return_value = True
    
    success = analysis_service.delete_all_llm_analyses()
        
    assert success is True
    mock_dependencies['news_storage'].delete_all_llm_analyses.assert_called_once()

def test_delete_all_llm_analyses_failure(analysis_service, mock_dependencies, qtbot):
    mock_dependencies['news_storage'].delete_all_llm_analyses.return_value = False
    
    spy_status_updated = SignalSpy(qtbot, signal_name='status_message_updated_delete_all_fail')
    analysis_service.status_message_updated.connect(spy_status_updated)

    try:
        success = analysis_service.delete_all_llm_analyses()
        qtbot.wait(100) # Wait for signal to be processed by spy
        
        assert success is False
        mock_dependencies['news_storage'].delete_all_llm_analyses.assert_called_once()
        spy_status_updated.assert_called_once_with("删除所有LLM分析记录失败。")
    finally:
        try:
            analysis_service.status_message_updated.disconnect(spy_status_updated)
        except RuntimeError:
            pass

# TODO: Add tests for analyze_article_group (requires mocking EventAnalyzer methods)
# TODO: Add tests for handle_chat_message (if implemented) 