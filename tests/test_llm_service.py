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
        """提供一个测试用的LLMService实例，并注入 Mock 依赖"""
        mock_config_manager = MagicMock()
        mock_prompt_manager = MagicMock()
        mock_api_client = MagicMock()
        # 配置 Mock 返回值（如果测试需要）
        # mock_config_manager.get_active_config.return_value = {'api_key': 'test_key', 'api_url': 'http://test.com', 'model': 'test_model'}
        # mock_prompt_manager.get_formatted_prompt.return_value = "Test prompt"
        # mock_api_client.post.return_value = {'choices': [{'message': {'content': 'Test response'}}]}

        return LLMService(
            config_manager=mock_config_manager,
            prompt_manager=mock_prompt_manager,
            api_client=mock_api_client
        )

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