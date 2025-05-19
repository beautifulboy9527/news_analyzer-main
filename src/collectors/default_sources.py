"""
预设新闻源模块

提供默认的RSS新闻源列表，按标准类别组织。
"""

from .categories import STANDARD_CATEGORIES

def get_default_rss_sources(): # 重命名函数
    """
    获取默认的 RSS 新闻源列表

    Returns:
        list: 包含预设 RSS 新闻源信息的字典列表
    """
    # 只返回 RSS 源
    all_sources = [
        # 综合新闻
        {
            "url": "https://rsshub.app/bbc/zhongwen/simp",
            "name": "BBC中文网",
            "category": "general"
        },
        {
            "url": "https://rsshub.app/jmdian/topic/119",
            "name": "界面新闻",
            "category": "general"
        },
        {
            "url": "https://rsshub.app/yicai/brief",
            "name": "第一财经",
            "category": "business"
        },
        {
            "url": "https://rsshub.app/infzm/",
            "name": "南方周末",
            "category": "general"
        },
        {
            "url": "https://rsshub.app/xinhua/whxw",
            "name": "新华社新闻",
            "category": "general"
        },
        {
            "url": "https://rsshub.app/cctv/news",
            "name": "央视新闻",
            "category": "general"
        },
        {
            "url": "https://rsshub.app/people/paper/rmrb",
            "name": "人民日报",
            "category": "general"
        },
        {
            "url": "https://rsshub.app/gmw/paper/gmrb",
            "name": "光明日报",
            "category": "general"
        },
        {
            "url": "https://rsshub.app/chinadaily/dual",
            "name": "中国日报双语新闻",
            "category": "general"
        },

        # 国际新闻
        {
            "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
            "name": "纽约时报国际",
            "category": "international"
        },
        {
            "url": "https://feeds.washingtonpost.com/rss/world",
            "name": "华盛顿邮报国际",
            "category": "international"
        },
        {
            "url": "https://www.theguardian.com/world/rss",
            "name": "卫报国际",
            "category": "international"
        },
        {
            "url": "https://www.aljazeera.com/xml/rss/all.xml",
            "name": "半岛电视台",
            "category": "international"
        },
        {
            "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
            "name": "BBC国际",
            "category": "international"
        },
        {
            "url": "http://rss.cnn.com/rss/cnn_world.rss",
            "name": "CNN国际",
            "category": "international"
        },
        {
            "url": "https://www.nhk.or.jp/rss/news/cat6.xml",
            "name": "NHK国际",
            "category": "international"
        },
        {
            "url": "https://rsshub.app/wsj/cn",
            "name": "华尔街日报中文版",
            "category": "international"
        },
        {
            "url": "https://rsshub.app/nytimes/dual",
            "name": "纽约时报中文网",
            "category": "international"
        },

        # 科技新闻
        {
            "url": "https://www.engadget.com/rss.xml",
            "name": "Engadget",
            "category": "technology"
        },
        {
            "url": "https://www.theverge.com/rss/index.xml",
            "name": "The Verge",
            "category": "technology"
        },
        {
            "url": "https://techcrunch.com/feed/",
            "name": "TechCrunch",
            "category": "technology"
        },
        {
            "url": "https://feeds.arstechnica.com/arstechnica/index",
            "name": "Ars Technica",
            "category": "technology"
        },
        {
            "url": "https://www.solidot.org/index.rss",
            "name": "Solidot",
            "category": "technology"
        },
        {
            "url": "https://rsshub.app/ifanr/app",
            "name": "爱范儿",
            "category": "technology"
        },

        # 商业与金融
        {
            "url": "https://www.economist.com/finance-and-economics/rss.xml",
            "name": "经济学人",
            "category": "business"
        },
        {
            "url": "https://www.businessinsider.com/rss",
            "name": "商业内幕",
            "category": "business"
        },
        {
            "url": "https://www.cnbc.com/id/10001147/device/rss/rss.html",
            "name": "CNBC财经",
            "category": "business"
        },
        {
            "url": "https://rsshub.app/bloomberg/markets",
            "name": "彭博市场",
            "category": "business"
        },

        # 政治新闻
        {
            "url": "https://www.realclearpolitics.com/index.xml",
            "name": "RealClearPolitics",
            "category": "politics"
        },
        {
            "url": "https://thehill.com/feed",
            "name": "The Hill",
            "category": "politics"
        },
        {
            "url": "https://feeds.nbcnews.com/nbcnews/public/politics",
            "name": "NBC政治",
            "category": "politics"
        },
        {
            "url": "https://feeds.bbci.co.uk/news/politics/rss.xml",
            "name": "BBC政治",
            "category": "politics"
        },
        {
            "url": "https://rsshub.app/apnews/topics/politics",
            "name": "美联社政治",
            "category": "politics"
        },
        {
            "url": "https://rsshub.app/nikkei/asia",
            "name": "日经亚洲",
            "category": "politics"
        },

        # 科学新闻
        {
            "url": "https://www.science.org/rss/news_current.xml",
            "name": "Science",
            "category": "science"
        },
        {
            "url": "https://www.nature.com/nature.rss",
            "name": "Nature",
            "category": "science"
        },
        {
            "url": "https://feeds.newscientist.com/science-news",
            "name": "New Scientist",
            "category": "science"
        },
        {
            "url": "https://phys.org/rss-feed/",
            "name": "Phys.org",
            "category": "science"
        },
        {
            "url": "https://www.space.com/feeds/all",
            "name": "Space.com",
            "category": "science"
        },

        # 体育新闻
        {
            "url": "https://www.espn.com/espn/rss/news",
            "name": "ESPN",
            "category": "sports"
        },
        {
            "url": "https://www.skysports.com/rss/12040",
            "name": "Sky Sports",
            "category": "sports"
        },
        {
            "url": "https://rss.nytimes.com/services/xml/rss/nyt/Sports.xml",
            "name": "纽约时报体育",
            "category": "sports"
        },
        {
            "url": "https://api.foxsports.com/v1/rss?partnerKey=zBaFxRyGKCfxBagJG9b8pqLyndmvo7UU",
            "name": "Fox Sports",
            "category": "sports"
        },
        {
            "url": "https://www.theguardian.com/sport/rss",
            "name": "卫报体育",
            "category": "sports"
        },
        {
            "url": "https://rsshub.app/qq/sports",
            "name": "腾讯体育",
            "category": "sports"
        },

        # 娱乐新闻
        {
            "url": "https://www.hollywoodreporter.com/feed/",
            "name": "好莱坞记者",
            "category": "entertainment"
        },
        {
            "url": "https://variety.com/feed/",
            "name": "Variety",
            "category": "entertainment"
        },
        {
            "url": "https://deadline.com/feed/",
            "name": "Deadline",
            "category": "entertainment"
        },
        {
            "url": "https://rsshub.app/douban/movie/classification",
            "name": "豆瓣电影",
            "category": "entertainment"
        },
        {
            "url": "https://rsshub.app/bilibili/ranking/0/1",
            "name": "哔哩哔哩热门",
            "category": "entertainment"
        },

        # 健康与医疗
        {
            "url": "https://tools.cdc.gov/api/v2/resources/media/316422.rss",
            "name": "CDC",
            "category": "health"
        },
        {
            "url": "https://rsshub.app/who/news",
            "name": "世界卫生组织",
            "category": "health"
        },

        # 文化与教育
        {
            "url": "https://www.insidehighered.com/rss/feed/ihe",
            "name": "Inside Higher Ed",
            "category": "culture"
        },
        {
            "url": "https://rsshub.app/moe/news",
            "name": "教育部新闻",
            "category": "culture"
        },

        # 澎湃新闻
        {
            "url": "PENGPAI_CUSTOM", # 特殊标记，表示非 RSS
            "name": "澎湃新闻",
            "category": "general",
            "collector_type": "pengpai", # 指定使用 PengpaiCollector
            "custom_config": {
                "news_list_selector": "a[href^=\"/newsDetail_forward_\"]",
                "title_selector": "h3.index_title__aGAqD",
                "content_selector": "#__next > div > main > div > div.index_wrapbox__VFyXe > div.index_wrapper__L_zqV > div.index_cententWrapBox__bh0OY > div.index_cententWrap__Jv8jK,#__next > div > main > div > div.index_wrapper__mHU4q > div.index_summary__ONV_r",
                "time_selector": "#__next > div > main > div > div.index_wrapbox__VFyXe > div.index_wrapper__L_zqV > div.index_headerContent__sASF4 > div > div.ant-space.ant-space-horizontal.ant-space-align-center > div > span,#__next > div > main > div > div.index_wrapper__mHU4q > div.index_headerContent__mOJJb > span.index_nowrap__rmdw_",
                "author_selector": "#__next > div > main > div > div.index_wrapbox__VFyXe > div.index_wrapper__L_zqV > div.index_headerContent__sASF4 > div > div:nth-child(1)"
            }
        },

        # --- 东方财富 ---
    ]
    # 只返回 RSS 源
    return [s for s in all_sources if s.get('type', 'rss') == 'rss']


# 移除 initialize_sources 函数，因为 SourceManager 会直接使用 get_default_rss_sources
# def initialize_sources(rss_collector): ...
