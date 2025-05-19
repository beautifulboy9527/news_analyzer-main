import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime # 添加 datetime 导入

# 添加src目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from storage.news_storage import NewsStorage
# from models import NewsArticle # NewsArticle 不再直接用于 storage 方法的参数

class TestNewsStorage:
    @pytest.fixture
    def storage(self):
        """提供一个测试用的NewsStorage实例"""
        # Use in-memory database for tests to avoid file system issues
        storage_instance = NewsStorage(db_name=":memory:")
        # 移除 _skip_db_setup_for_mock_tests = True 以允许表创建
        return storage_instance

    def test_upsert_and_get_article(self, storage):
        """测试保存和获取文章功能"""
        article_data = {
            "title": "测试文章",
            "link": "http://example.com/test", # 确保 link 是唯一的
            "source_name": "测试来源",
            "content": "测试内容",
            "publish_time": datetime.now().isoformat(), # 添加 publish_time
            "retrieval_time": datetime.now().isoformat() # 添加 retrieval_time
        }
        
        # 测试 upsert_article
        article_id = storage.upsert_article(article_data)
        assert article_id is not None
        assert isinstance(article_id, int)

        # 测试 get_article_by_link
        retrieved_article = storage.get_article_by_link(article_data["link"])
        assert retrieved_article is not None
        assert retrieved_article["title"] == article_data["title"]
        assert retrieved_article["link"] == article_data["link"]
        assert retrieved_article["id"] == article_id

        # 测试 get_article_by_id
        retrieved_by_id = storage.get_article_by_id(article_id)
        assert retrieved_by_id is not None
        assert retrieved_by_id["link"] == article_data["link"]

    def test_get_all_articles_empty(self, storage):
        """测试在没有文章时获取所有文章"""
        articles = storage.get_all_articles()
        assert isinstance(articles, list)
        assert len(articles) == 0

    def test_get_all_articles_with_data(self, storage):
        """测试在有文章时获取所有文章"""
        article_data1 = {
            "title": "文章1", "link": "http://example.com/1", "content": "内容1",
            "publish_time": datetime.now().isoformat(), "retrieval_time": datetime.now().isoformat()
        }
        article_data2 = {
            "title": "文章2", "link": "http://example.com/2", "content": "内容2",
            "publish_time": datetime.now().isoformat(), "retrieval_time": datetime.now().isoformat()
        }
        storage.upsert_article(article_data1)
        storage.upsert_article(article_data2)
        
        articles = storage.get_all_articles()
        assert len(articles) == 2
        
        # 验证文章链接（顺序可能依赖于排序，这里简单检查是否存在）
        links_in_results = [a["link"] for a in articles]
        assert "http://example.com/1" in links_in_results
        assert "http://example.com/2" in links_in_results

    def test_close(self, storage):
        """测试关闭资源功能"""
        # 调用实际的 close 方法
        try:
            storage.close()
            # 验证 conn 和 cursor 是否被设置为 None
            assert storage.conn is None
            assert storage.cursor is None
        except Exception as e:
            pytest.fail(f"storage.close() threw an exception: {e}")

# 移除了旧的 test_save_article 和 test_get_article
#         pass