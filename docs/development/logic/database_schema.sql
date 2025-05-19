-- Database Schema for News Analyzer (SQLite)

-- Stores individual news articles
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    content TEXT,
    link TEXT UNIQUE NOT NULL,
    source_name TEXT,                 -- Name of the news source (e.g., "CNN", "BBC News")
    source_url TEXT,                  -- URL of the news source (feed URL or website URL)
    publish_time TEXT,                -- ISO8601 datetime string (e.g., "2023-10-26T10:00:00Z")
    retrieval_time TEXT NOT NULL,     -- ISO8601 datetime string, when the article was fetched
    category_name TEXT,               -- Category assigned to the article (e.g., "Technology", "Politics")
    image_url TEXT,                   -- URL of a representative image for the article
    is_read INTEGER DEFAULT 0 NOT NULL, -- 0 for unread, 1 for read
    llm_summary TEXT                  -- Optional LLM-generated summary for the article
);

-- Stores configuration for news sources
CREATE TABLE IF NOT EXISTS news_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,        -- User-defined name for the source
    url TEXT NOT NULL,                -- URL of the news feed (RSS, Atom, JSON Feed) or website
    type TEXT NOT NULL,               -- Type of the source (e.g., "RSS", "JSON", "HTML_PENGPAI")
    category_name TEXT,               -- Default category to assign to articles from this source
    is_enabled INTEGER DEFAULT 1 NOT NULL, -- 0 for disabled, 1 for enabled
    last_checked_time TEXT,           -- ISO8601 datetime string, when the source was last checked for new articles
    notes TEXT,                       -- Optional user notes for the source
    is_user_added INTEGER DEFAULT 1,  -- Indicates if the source was added by user or is a default one
    custom_config TEXT                -- JSON string for source-specific configurations (e.g., CSS selectors for HTML scraping)
);

-- Stores browsing history of articles
CREATE TABLE IF NOT EXISTS browsing_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    view_time TEXT NOT NULL,          -- ISO8601 datetime string, when the article was viewed
    FOREIGN KEY (article_id) REFERENCES articles (id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Stores results of LLM analysis tasks
CREATE TABLE IF NOT EXISTS llm_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_timestamp TEXT NOT NULL, -- ISO8601 datetime string, when the analysis was performed
    analysis_type TEXT NOT NULL,      -- Type of analysis (e.g., "Similarity Analysis", "Sentiment Analysis")
    analysis_result_text TEXT,        -- The main textual output of the analysis
    meta_news_count INTEGER,          -- Number of news items involved in this analysis
    meta_news_titles TEXT,            -- JSON array of strings (titles of news involved)
    meta_news_sources TEXT,           -- JSON array of strings (source names of news involved)
    meta_categories TEXT,             -- JSON array of strings (categories of news involved)
    meta_groups TEXT                  -- JSON string representing grouping information from the analysis
);

-- Maps articles to LLM analyses (many-to-many relationship)
CREATE TABLE IF NOT EXISTS article_analysis_mappings (
    article_id INTEGER NOT NULL,
    analysis_id INTEGER NOT NULL,
    PRIMARY KEY (article_id, analysis_id),
    FOREIGN KEY (article_id) REFERENCES articles (id) ON DELETE CASCADE,
    FOREIGN KEY (analysis_id) REFERENCES llm_analyses (id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_articles_link ON articles (link);
CREATE INDEX IF NOT EXISTS idx_articles_publish_time ON articles (publish_time);
CREATE INDEX IF NOT EXISTS idx_articles_is_read ON articles (is_read);
CREATE INDEX IF NOT EXISTS idx_articles_category_name ON articles (category_name);

CREATE INDEX IF NOT EXISTS idx_news_sources_name ON news_sources (name);
CREATE INDEX IF NOT EXISTS idx_news_sources_is_enabled ON news_sources (is_enabled);

CREATE INDEX IF NOT EXISTS idx_browsing_history_article_id ON browsing_history (article_id);
CREATE INDEX IF NOT EXISTS idx_browsing_history_view_time ON browsing_history (view_time);

CREATE INDEX IF NOT EXISTS idx_llm_analyses_timestamp ON llm_analyses (analysis_timestamp);
CREATE INDEX IF NOT EXISTS idx_llm_analyses_type ON llm_analyses (analysis_type);

CREATE INDEX IF NOT EXISTS idx_article_analysis_mappings_article_id ON article_analysis_mappings (article_id);
CREATE INDEX IF NOT EXISTS idx_article_analysis_mappings_analysis_id ON article_analysis_mappings (analysis_id); 