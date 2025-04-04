    def filter_news_by_category(self, category):
        """按分类过滤新闻"""
        if category is None:
            # 显示所有新闻
            self.newsList = self.allNews.copy()
        else:
            # 过滤指定分类的新闻
            self.newsList = [news for news in self.allNews if news.category == category]
        self.newsListUpdated.emit(self.newsList)
