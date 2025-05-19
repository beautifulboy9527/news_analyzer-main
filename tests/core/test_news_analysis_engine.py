# tests/core/test_news_analysis_engine.py
"""
新闻分析引擎测试

测试新闻分析引擎的功能，包括新闻相似度分析、重要程度和立场分析等功能。
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.core.news_analysis_engine import NewsAnalysisEngine, DataProcessingError, LLMServiceError
from src.core.news_data_processor import NewsDataProcessor
from src.llm.llm_service import LLMService


@pytest.fixture
def mock_llm_service():
    """提供一个模拟的LLMService实例"""
    # Create mock with spec first
    mock = MagicMock(spec=LLMService, name="MockLLMService")

    # Explicitly add methods called by AnalysisProcessor as MagicMock attributes
    # This ensures they exist even if not directly in the LLMService spec used by MagicMock
    mock.analyze_news = MagicMock(return_value = {'analysis': 'Mock Base Analysis', 'formatted_text': 'Mock Base Formatted'})
    mock.analyze_news_similarity = MagicMock(return_value = {'analysis': 'Mock Similarity Analysis', 'formatted_text': 'Mock Similarity Formatted'})
    mock.analyze_importance_stance = MagicMock(return_value = {'importance': 0.8, 'stance': -0.5})
    mock.analyze_with_custom_prompt = MagicMock(return_value = {'analysis': 'Mock Custom Analysis', 'formatted_text': 'Mock Custom Formatted'})

    # # Old way - might fail if methods not in spec
    # mock.analyze_news.return_value = {'analysis': 'Mock Base Analysis', 'formatted_text': 'Mock Base Formatted'} # For single news
    # mock.analyze_news_similarity.return_value = {'analysis': 'Mock Similarity Analysis', 'formatted_text': 'Mock Similarity Formatted'} # For multiple news
    # # CORRECTED: Return a dictionary for importance/stance
    # mock.analyze_importance_stance.return_value = {'importance': 0.8, 'stance': -0.5}
    # mock.analyze_with_custom_prompt.return_value = {'analysis': 'Mock Custom Analysis', 'formatted_text': 'Mock Custom Formatted'}

    return mock


@pytest.fixture
def mock_data_processor():
    """提供一个模拟的NewsDataProcessor实例"""
    mock = MagicMock(spec=NewsDataProcessor, name="MockDataProcessor")
    
    # Add methods that the engine calls directly on the processor
    mock.save_analysis_result = MagicMock()
    # mock.prepare_news_for_analysis is NOT called by the engine directly for analysis
    # Remove process_multiple_news and process_single_news - they are on the internal AnalysisProcessor
    # mock.process_multiple_news = MagicMock(return_value = {'analysis': 'mock_analysis', 'formatted_text': 'mock_formatted'})
    # mock.process_single_news = MagicMock(return_value = {'importance': 0.7, 'stance': 0.1, 'analysis': 'mock_single_analysis', 'formatted_text': 'mock_single_formatted'})
    
    return mock


@pytest.fixture
def engine(mock_llm_service, mock_data_processor):
    """提供一个NewsAnalysisEngine实例"""
    return NewsAnalysisEngine(mock_llm_service, mock_data_processor)


def test_analyze_news_similarity(engine, mock_llm_service, mock_data_processor):
    """测试新闻相似度分析功能"""
    # 准备测试数据
    test_news = [
        {'id': '1', 'title': '测试新闻1', 'content': 'abc'}, # Added content for preprocessing
        {'id': '2', 'title': '测试新闻2', 'content': 'def'}
    ]
    processed_news = engine._preprocess_news_data(test_news) # Get expected processed data

    # 执行测试
    result = engine.analyze_news(test_news, '新闻相似度分析') # Analysis type might be different internally

    # 验证LLM服务调用
    # Engine calls processor.process_multiple_news, which calls llm_service.analyze_news_similarity
    # and llm_service.analyze_importance_stance
    mock_llm_service.analyze_news_similarity.assert_called_once_with(processed_news)
    mock_llm_service.analyze_importance_stance.assert_called_once_with(processed_news[0])
    # 验证数据处理器保存结果的调用
    mock_data_processor.save_analysis_result.assert_called_once()

    # 验证结果 (来自 mock_llm_service 的组合)
    assert 'error' not in result
    assert result['analysis'] == 'Mock Similarity Analysis' # From analyze_news_similarity mock
    assert result['importance'] == 0.8 # From analyze_importance_stance mock
    assert result['stance'] == -0.5 # From analyze_importance_stance mock
    assert 'formatted_text' in result # Check if formatted text is generated
    assert '分析类型: 新闻相似度分析' in result['formatted_text']


def test_analyze_importance_stance(engine, mock_llm_service, mock_data_processor):
    """测试重要程度和立场分析功能 (通过公共接口)"""
    # 准备测试数据
    test_news = {'id': '1', 'title': '测试新闻1', 'content': 'xyz'} # Added content
    processed_news = engine._preprocess_news_data([test_news]) # Get expected processed data

    # 模拟LLM服务被调用的行为 - already done in fixture

    # 执行测试 - 调用公共方法
    result = engine.analyze_news([test_news], '重要程度和立场分析') # Pass as list

    # 验证LLM服务调用
    # Engine calls processor.process_single_news, which calls llm_service.analyze_news
    # It does NOT call analyze_importance_stance again if type matches
    mock_llm_service.analyze_news.assert_called_once_with(processed_news[0], '重要程度和立场分析')
    mock_llm_service.analyze_importance_stance.assert_not_called() # Should not be called again
    # 验证数据处理器保存结果的调用
    mock_data_processor.save_analysis_result.assert_called_once()

    # 验证结果 (来自 analyze_news mock, engine adds defaults if missing)
    assert 'error' not in result
    assert result['analysis'] == 'Mock Base Analysis'
    # Importance/stance might not be in the result if analyze_news mock doesn't return them
    # Check based on what analyze_news fixture returns, AND how engine handles missing keys
    assert 'importance' in result
    assert 'stance' in result
    assert 'formatted_text' in result
    assert '分析类型: 重要程度和立场分析' in result['formatted_text']


def test_analyze_with_custom_prompt(engine, mock_llm_service, mock_data_processor):
    """测试使用自定义提示词进行分析的功能 (通过公共接口)"""
    # 准备测试数据
    test_news = [
        {'id': '1', 'title': '测试新闻1', 'content': 'ghi'},
        {'id': '2', 'title': '测试新闻2', 'content': 'jkl'}
    ]
    custom_prompt = "这是一个自定义提示词"
    processed_news = engine._preprocess_news_data(test_news) # Get expected processed data

    # 模拟LLM服务被调用的行为 - already done in fixture

    # 执行测试 - 调用公共方法
    result = engine.analyze_news(test_news, '自定义提示词分析', custom_prompt=custom_prompt)

    # 验证LLM服务调用
    # Engine calls processor.process_custom_analysis, which calls llm_service.analyze_with_custom_prompt
    mock_llm_service.analyze_with_custom_prompt.assert_called_once_with(processed_news, custom_prompt)
    # 验证数据处理器保存结果的调用
    mock_data_processor.save_analysis_result.assert_called_once()

    # 验证结果 (来自 analyze_with_custom_prompt mock)
    assert 'error' not in result
    assert result['analysis'] == 'Mock Custom Analysis'
    assert 'formatted_text' in result
    assert '分析类型: 自定义提示词分析' in result['formatted_text']


def test_analyze_news_empty_input(engine):
    """测试空输入的情况"""
    # 验证当输入为空列表时，是否引发 DataProcessingError
    with pytest.raises(DataProcessingError, match="没有提供新闻数据"):
        # 执行测试
        engine.analyze_news([], '新闻相似度分析')


def test_analyze_news_llm_service_unavailable(mock_data_processor):
    """测试LLM服务不可用的情况"""
    # 创建一个没有LLM服务的引擎
    engine = NewsAnalysisEngine(None, mock_data_processor)

    # 验证当 LLM 服务未初始化时，是否引发 LLMServiceError
    with pytest.raises(LLMServiceError, match="LLM服务未初始化"):
        # 执行测试
        engine.analyze_news([{'id': '1', 'title': '测试新闻'}], '新闻相似度分析')


def test_get_analysis_result(engine):
    """测试获取分析结果的功能"""
    # 准备测试数据
    engine.analysis_results = {
        'group_1': {'analysis': '分析结果1'},
        'group_2': {'analysis': '分析结果2'}
    }
    
    # 测试获取存在的结果
    result = engine.get_analysis_result('group_1')
    assert result == {'analysis': '分析结果1'}
    
    # 测试获取不存在的结果
    result = engine.get_analysis_result('non_existent')
    assert result is None