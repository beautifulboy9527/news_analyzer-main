from typing import Optional, List, Dict
from datetime import datetime, timezone
from PyQt5.QtCore import Slot

class NewsListViewModel:
    def update_news_list(self, new_articles: Optional[List[NewsArticle]] = None, new_article_data: Optional[List[Dict]] = None):
        """处理来自AppService的新闻更新，并相应地更新内部列表和视图。"""
        self.logger.info(f"NewsListViewModel.update_news_list called. new_articles count: {len(new_articles) if new_articles else 'None'}, new_article_data count: {len(new_article_data) if new_article_data else 'None'}")

        updated_article_links = set()
        actually_new_articles_to_add = []

        if new_articles:
            for article in new_articles:
                if article.link not in self._news_list:
                    actually_new_articles_to_add.append(article)
                else:
                    updated_article_links.add(article.link)

        if new_article_data:
            for data in new_article_data:
                if data['link'] not in self._news_list:
                    actually_new_articles_to_add.append(NewsArticle(link=data['link'], title=data['title'], publish_time=data['publish_time']))
                else:
                    updated_article_links.add(data['link'])

        if actually_new_articles_to_add or updated_article_links:
            self._news_list.extend(actually_new_articles_to_add)
            self._news_list.sort(key=lambda x: x.publish_time if x.publish_time else datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            self.logger.info(f"NewsListViewModel: Emitting news_list_changed after updating. Total items in _news_list: {len(self._news_list)}. Added: {len(actually_new_articles_to_add)}, Updated: {len(updated_article_links) - len(actually_new_articles_to_add)}")
            self.news_list_changed.emit()
        else:
            self.logger.info("NewsListViewModel.update_news_list: No changes to news list, not emitting signal.")

    @Slot(str)
    def handle_article_clicked(self, link: str):
        # Implementation of handle_article_clicked method
        pass 