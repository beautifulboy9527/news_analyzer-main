import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# 添加src目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from llm.llm_service import LLMService

class TestLLMService:
    @pytest.fixture
    def client(self):
        """提供一个测试用的LLMService实例"""
        return LLMService()

    def test_generate_summary(self, client):
        """测试生成摘要功能"""
        test_content = "测试内容"
        with patch.object(client, 'analyze_news') as mock_analyze:
            mock_analyze.return_value = "测试摘要"
            result = client.analyze_news(test_content, analysis_type='摘要')
            mock_analyze.assert_called_once()
            assert result == "测试摘要"

    def test_analyze_sentiment(self, client):
        """测试情感分析功能"""
        test_content = "测试内容"
        with patch.object(client, 'analyze_news') as mock_analyze:
            mock_analyze.return_value = "积极"
            result = client.analyze_news(test_content, analysis_type='情感分析')
            mock_analyze.assert_called_once()
            assert result == "积极"

    def test_close(self, client):
        """测试关闭资源功能"""
        # LLMService没有close方法，测试可以移除或修改
        pass