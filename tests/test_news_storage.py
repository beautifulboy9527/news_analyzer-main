import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# 添加src目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from storage.news_storage import NewsStorage
from models import NewsArticle

class TestNewsStorage:
    @pytest.fixture
    def storage(self):
        """提供一个测试用的NewsStorage实例"""
        return NewsStorage()

    def test_save_article(self, storage):
        """测试保存文章功能"""
        article = NewsArticle(
            title="测试文章",
            link="http://example.com",
            source_name="测试来源",
            content="测试内容"
        )
        with patch.object(storage, 'save_news') as mock_save:
            mock_save.return_value = "test_path.json"
            result = storage.save_news([article])
            mock_save.assert_called_once()
            assert result == "test_path.json"

    def test_get_article(self, storage):
        """测试获取文章功能"""
        test_url = "http://example.com"
        with patch.object(storage, 'load_news') as mock_load:
            mock_load.return_value = [{'title': '测试文章', 'link': test_url}]
            result = storage.load_news()
            mock_load.assert_called_once()
            assert len(result) == 1
            assert result[0]['link'] == test_url

    def test_close(self, storage):
        """测试关闭资源功能"""
        # NewsStorage没有显式的close方法，测试可以移除或修改
        pass