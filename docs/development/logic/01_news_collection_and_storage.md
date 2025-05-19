# 01 - 新闻采集与存储逻辑

## 1. 核心组件

*(基于代码分析)*

- **`AppService`**: (旧) ~~协调整个刷新流程，调用 `SourceManager` 和 `Collectors`，处理结果，并调用 `NewsStorage` 保存。~~ (新) 主要负责协调UI、`NewsUpdateService`、`HistoryService`、`AnalysisService` 等，并管理内存中的 `news_cache`。
- **`NewsUpdateService`**: (新) 负责实际的新闻刷新逻辑，包括调用 `SourceManager` 获取源配置，调用 `Collectors` 抓取数据，处理数据，并调用 `NewsStorage` 将新获取的文章存入数据库。它会发出信号通知 `AppService` 有新的文章。
- **`SourceManager`**: (旧) ~~管理新闻源配置 (从 `QSettings` 或其他文件加载/保存，提供启用的源列表)。~~ (新) 负责新闻源配置的加载（从 `NewsStorage`）、管理 (内存中) 和修改 (通过 `NewsStorage` 持久化到数据库)。提供启用的源列表给 `NewsUpdateService`。它还包含逻辑 (`_ensure_default_sources_exist`)，用于在数据库中不存在预定义的默认新闻源（如澎湃新闻和默认RSS源）时自动填充它们，确保在首次使用或数据库清空后仍有一组基本的新闻源可用。澎湃新闻的 `custom_config` (包含CSS选择器) 也会在此过程中正确设置。
- **`Collectors` (基类与子类 - `RSSCollector`, `PengpaiCollector`, `JSONFeedCollector`)**: 实现从具体来源 (RSS, 澎湃网站, JSON Feed URL) 抓取原始新闻数据 (字典列表) 的逻辑。
    - `PengpaiCollector`: 特别地，此收集器使用 Selenium WebDriver 动态加载和解析澎湃新闻的页面。它实现了多选择器策略（通过逗号分隔的CSS选择器字符串配置在新闻源的 `custom_config` 中），以适应标准新闻和视频新闻等不同页面布局，从而提取标题、内容、发布时间和作者。它还包含逻辑 (`_parse_relative_or_absolute_time`) 来解析如 "X小时前" 这样的相对时间以及多种绝对时间格式。
- **`NewsStorage`**: 负责新闻数据、新闻源配置、浏览历史、LLM分析结果等核心数据的持久化存储 (基于 SQLite 数据库 `news_data.db`) 和读取。

## 2. 刷新流程 (用户触发或定时触发)

*(基于 `NewsUpdateService._do_refresh`, `AppService._handle_news_refreshed`, `Collectors.collect`, `NewsStorage.upsert_articles_batch` 等方法的代码分析)*

1.  **触发**: UI 或定时任务调用 `AppService.refresh_all_sources()`。
2.  **委托**: `AppService` 将刷新请求委托给 `NewsUpdateService.refresh_all_sources()`。
3.  **启动 (NewsUpdateService)**: `NewsUpdateService` 检查是否已在刷新，若否则设置状态为 `True`，重置取消标志，发射 `refresh_started` 信号，并启动后台任务 (如线程) 执行 `_do_refresh`。
4.  **获取源 (NewsUpdateService)**: `_do_refresh` 从 `SourceManager` 获取所有**已启用**的新闻源配置列表。
5.  **并发采集 (NewsUpdateService)**: `_do_refresh` 遍历源配置列表：
    -   根据源类型 (`source.type`) 选择对应的 `Collector` 实例。
    -   调用该 `Collector` 实例的 `collect(source_config)` 方法，返回原始新闻数据列表 (字典列表)。
    -   (采集过程可能并发执行)。
6.  **收集结果 (NewsUpdateService)**: `_do_refresh` 收集所有成功执行的 `Collector` 返回的原始新闻数据列表 (`all_raw_news_items`)。
7.  **处理与转换 (NewsUpdateService)**: `_do_refresh` 对收集到的 `all_raw_news_items` 进行处理：
    -   将其转换为 `NewsArticle` 对象列表 (`converted_articles`)。
    -   为每个 `NewsArticle` 设置 `category` 属性 (基于 `source_config.category`)。
    -   与数据库中已有的文章链接进行去重，并确保本次刷新批次内的文章链接唯一，得到 `newly_fetched_unique_articles`。
8.  **持久化存储 (NewsUpdateService & NewsStorage)**:
    -   `NewsUpdateService._do_refresh` 将 `newly_fetched_unique_articles` (List[NewsArticle]) 转换为字典列表。
    -   调用 `NewsStorage.upsert_articles_batch()` 方法，将这些新文章的字典列表批量插入或更新到 SQLite 数据库的 `articles` 表中。
9.  **通知AppService (NewsUpdateService)**: `NewsUpdateService._do_refresh` 发射 `news_refreshed` 信号，携带 `newly_fetched_unique_articles` (List[NewsArticle])。
10. **更新缓存 (AppService)**: `AppService` 中的槽函数 (`_handle_news_refreshed`) 接收到 `news_refreshed` 信号后：
    -   将 `newly_fetched_unique_articles` (其中每篇文章，尤其是 `publish_time` 等字段，都经过了必要的转换和解析，以确保数据格式的正确性) 合并到其内存缓存 `self.news_cache`。具体做法是：
        -   遍历 `newly_fetched_unique_articles` 中的每一篇文章。
        - 检查该文章的链接是否存在于 `self.news_cache` 中已有的文章。
        - 如果存在，则用当前获取的较新的文章对象替换缓存中的旧文章对象。
        - 如果不存在，则将新文章添加到 `self.news_cache` 的前端（通常是列表的开头）。
        - 这个过程确保了 `self.news_cache` 中文章链接的唯一性，并优先保留了最新的文章信息。
    - 发射 `news_cache_updated` 信号，携带更新后的完整 `self.news_cache`。
11. **完成 (NewsUpdateService)**: `_do_refresh` 发射 `refresh_complete` 信号 (包含成功状态和消息)。
12. **重置状态 (NewsUpdateService)**: `_do_refresh` 重置刷新状态。

*注意: 刷新过程中 `NewsUpdateService` 会发射 `refresh_progress` 信号来更新进度。*

## 3. 存储细节 (`NewsStorage` - 基于 SQLite)

`NewsStorage` 组件负责应用程序核心数据的持久化管理。在 v3 版本中，数据存储已迁移到以 SQLite 数据库 (`data/news_data.db`) 为核心的方案，以提高性能、数据一致性和查询能力。部分特定配置或临时数据可能仍采用 JSON 文件或其他机制辅助存储（例如，UI相关的设置通过 `QSettings` 管理，Prompt 模板元数据通过 `src/prompts/prompts_metadata.json` 管理，这些不由 `NewsStorage` 直接处理）。

### 3.1. 数据库连接与管理

-   **数据库文件**: 核心数据存储在工作区根目录下的 `data/news_data.db` SQLite 文件中。
-   **连接建立与管理**: `NewsStorage` 在初始化时建立与 SQLite 数据库的连接。对于桌面应用的典型场景，通常会维护一个在 `NewsStorage` 生命周期内持久的连接，以减少连接/断开的开销。*(具体连接策略需代码确认)*
-   **表初始化/迁移**:
    -   数据库表结构在应用首次启动或 `NewsStorage` 初始化时，通过执行 `CREATE TABLE IF NOT EXISTS ...` SQL语句来创建。这确保了即使数据库文件不存在或为空，应用也能正常初始化所需的表。
    -   *(当前文档未涉及复杂的数据库版本控制或迁移方案 (如 Alembic)。若后续表结构有重大变更，可能需要引入此类机制或手动管理迁移脚本。)*

### 3.2. 核心数据表结构 (高层次概述)

`NewsStorage` 通过 SQLite 数据库管理以下核心实体的数据。详细的表结构、字段类型和约束请直接参考 `src/storage/news_storage.py` 中的实际 SQL DDL 语句或 ORM 定义 (如果使用了 ORM)。

-   **`articles` (新闻文章表)**:
    -   存储新闻文章的详细信息。
    -   **主要字段示例**:
        -   `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
        -   `title` (TEXT)
        -   `content` (TEXT)
        -   `link` (TEXT UNIQUE NOT NULL) - 文章的唯一链接，用于去重和关联。
        -   `source_name` (TEXT) - 新闻来源的名称。
        -   `source_url` (TEXT) - 新闻来源的 URL。
        -   `publish_time` (TEXT or INTEGER) - 文章发布时间 (通常存储为 ISO8601 格式的字符串或 Unix 时间戳)。此字段可能为 `NULL`，如果源数据中未提供有效的发布时间。系统中包含一个一次性的清理机制 (`NewsStorage.delete_articles_with_null_publish_time()`)，在应用启动时由 `main.py` 调用，以移除这类数据，防止显示 "未知时间"。
        -   `retrieval_time` (TEXT or INTEGER) - 文章抓取时间。
        -   `category_name` (TEXT) - 文章所属分类的名称。 *(如果分类是动态的或有独立管理，可能需要外键关联到 `categories` 表)*
        -   `image_url` (TEXT, NULLABLE)
        -   `is_read` (INTEGER DEFAULT 0) - 标记文章是否已读 (0 未读, 1 已读)。
        -   `llm_summary` (TEXT, NULLABLE) - LLM 生成的摘要。
        -   `llm_analysis_points` (TEXT, NULLABLE) - LLM 生成的其他分析点 (可能是 JSON 字符串)。
        -   *(其他可能的分析结果字段，如 `sentiment`, `importance_score` 等)*
    -   **数据模型映射**: 此表结构将原先 JSON 对象中的平铺或嵌套字段映射为表列。对于列表或复杂嵌套对象（如多个作者、标签云），若不创建关联表，则可能序列化为 JSON 字符串存储在 TEXT 类型的字段中。

-   **`news_sources` (新闻源配置表)**:
    -   存储用户添加的新闻源配置。
    -   **主要字段示例**:
        -   `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
        -   `name` (TEXT UNIQUE NOT NULL) - 用户定义的源名称。
        -   `url` (TEXT NOT NULL) - 源的 URL (RSS/JSON Feed URL 或网站 URL)。
        -   `type` (TEXT NOT NULL) - 源类型 (e.g., 'RSS', 'JSON', 'Pengpai')。
        -   `category_name` (TEXT) - 用户为此源指定的默认分类名称。
        -   `is_enabled` (INTEGER DEFAULT 1) - 是否启用此源 (0 禁用, 1 启用)。
        -   `last_checked_time` (TEXT or INTEGER, NULLABLE)
        -   `custom_config` (TEXT, NULLABLE) - 用于存储特定源类型的额外配置 (例如，澎湃新闻的 CSS 选择器)，通常为 JSON 字符串。

-   **`browsing_history` (浏览历史表)**:
    -   记录用户查看过的新闻文章。
    -   **主要字段示例**:
        -   `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
        -   `article_id` (INTEGER NOT NULL) - 被浏览文章的ID，外键关联到 `articles.id`。 (之前为 article_link)
        -   `view_time` (TEXT or INTEGER NOT NULL) - 查看时间。
    -   *(可能会有定期清理策略或数量上限，但这通常由 `HistoryService` 层面控制)*

-   **`llm_analyses` (LLM分析结果表)**:
    -   存储由LLM执行的各类分析任务的结果。
    -   **主要字段示例**:
        -   `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
        -   `analysis_timestamp` (TEXT NOT NULL) - 分析执行的时间。
        -   `analysis_type` (TEXT NOT NULL) - 分析的类型 (e.g., 'similarity_analysis', 'summary_generation')。
        -   `analysis_result_text` (TEXT) - 分析结果的主要文本内容 (如生成的摘要、分析报告等)。
        -   `meta_article_ids` (TEXT) - 参与分析的文章ID列表 (JSON字符串格式, e.g., '[1, 2, 3]')。
        -   `meta_news_titles` (TEXT) - 参与分析的新闻标题列表 (JSON字符串格式)。
        -   `meta_news_sources` (TEXT) - 参与分析的新闻来源列表 (JSON字符串格式)。
        -   `meta_analysis_params` (TEXT) - 分析时使用的参数 (JSON字符串格式, e.g., {"model": "gemini-pro"})。
        -   `meta_prompt_hash` (TEXT) - 分析使用的Prompt的哈希值，用于追溯。
        -   `meta_error_info` (TEXT, NULLABLE) - 如果分析出错，记录错误信息。

-   **`article_analysis_mappings` (文章与分析结果关联表)**:
    -   一个多对多连接表，用于关联 `articles` 表和 `llm_analyses` 表。
    -   **主要字段示例**:
        -   `article_id` (INTEGER NOT NULL) - 外键关联到 `articles.id`。
        -   `analysis_id` (INTEGER NOT NULL) - 外键关联到 `llm_analyses.id`。
        -   PRIMARY KEY (`article_id`, `analysis_id`)

-   **`read_status` (已读状态实现)**:
    -   已读状态直接通过 `articles` 表中的 `is_read` (INTEGER) 字段进行管理和持久化。不再需要单独的 `read_status.json` 文件或独立的已读状态表。

### 3.3. 数据操作 (CRUD) 与格式适配

`NewsStorage` 提供了一系列方法来执行数据的创建 (Create)、读取 (Read)、更新 (Update) 和删除 (Delete) 操作。这些方法封装了 SQL 语句的执行，并处理 Python 对象与数据库记录之间的转换。

-   **通用模式与数据格式适配**:
    -   `NewsStorage` 的接口方法通常接收或返回 Python 字典或自定义的数据类实例 (如 `NewsArticle` 对象)。
    -   **写入数据库**: 当接收到 Python 对象/字典时，`NewsStorage` 内部会将其转换为适合对应表结构的元组或字典，用于参数化 SQL INSERT 或 UPDATE 语句。
        -   例如，`datetime` 对象会转换为 ISO8601 字符串或 Unix 时间戳。
        -   列表或字典等复杂类型若要存入单一 TEXT 字段，会在此处进行 JSON 序列化 (e.g., `json.dumps()`)。
    -   **从数据库读取**: 当从数据库查询数据后，`NewsStorage` 会将返回的行 (通常是元组) 转换为 Python 字典或实例化为相应的数据类对象。
        -   例如，存储为 ISO8601 字符串的时间会被解析回 `datetime` 对象。
        -   存储为 JSON 字符串的字段会被反序列化 (e.g., `json.loads()`)。
-   **主要操作示例 (基于已实现的 `NewsStorage` v3)**:
    -   **新闻文章 (`articles`)**:
        -   `upsert_article(article_data: Dict_or_ArticleObject) -> Optional[int]`: 插入或更新单条文章 (基于`link`冲突)。成功则返回文章ID。
        -   `upsert_articles_batch(articles_data: List[Dict_or_ArticleObject]) -> List[Optional[int]]`: 批量插入或更新文章。返回ID列表。
        -   `get_article_by_id(article_id: int) -> Optional[ArticleObject]`: 根据ID获取文章。
        -   `get_article_by_link(link: str) -> Optional[ArticleObject]`: 根据链接获取文章。
        -   `get_all_articles(filters: Optional[Dict]=None, sort_by: Optional[str]=None, sort_order: str='DESC', limit: Optional[int]=None, offset: Optional[int]=None, with_content: bool=True) -> List[ArticleObject]`: 获取文章列表，支持多种过滤条件、排序、分页，以及是否包含文章内容。
        -   `set_article_read_status(article_link_or_id: Union[str, int], is_read: bool)`: 设置文章已读状态。
        -   `get_total_articles_count(filters: Optional[Dict]=None) -> int`: 获取符合过滤条件的文章总数。
        -   *旧的 `save_news` 和 `load_news` 已基于这些新方法重构或移除。*
    -   **新闻源 (`news_sources`)**:
        -   `add_news_source(source_data: Dict_or_NewsSourceObject) -> Optional[int]`: 添加新闻源，返回源ID。
        -   `update_news_source(source_id: int, update_data: Dict)`: 更新指定ID的新闻源。
        -   `get_news_source_by_id(source_id: int) -> Optional[NewsSourceObject]`: 根据ID获取新闻源。
        -   `get_news_source_by_name(name: str) -> Optional[NewsSourceObject]`: 根据名称获取新闻源。
        -   `get_all_news_sources(enabled_only: bool = False) -> List[NewsSourceObject]`: 获取所有或仅启用的新闻源。
        -   `delete_news_source(source_id: int)`: 删除新闻源。
    -   **浏览历史 (`browsing_history`)**:
        -   `add_browsing_history(article_id: int, viewed_at: datetime) -> Optional[int]`: 添加一条浏览历史，返回历史记录ID。
        -   `get_browsing_history(limit: Optional[int] = None, offset: Optional[int] = None) -> List[HistoryEntryObject]`: 获取浏览历史列表 (包含文章详情)，支持分页。
        -   `delete_browsing_history_item(history_id: int)`: 删除单条历史记录。
        -   `clear_all_browsing_history()`: 清空所有浏览历史。
    -   **LLM分析 (`llm_analyses`, `article_analysis_mappings`)**:
        -   `add_llm_analysis(analysis_data: Dict, article_ids: Optional[List[int]] = None) -> Optional[int]`: 添加一条LLM分析结果，并可选地关联到多篇文章。返回分析记录ID。
        -   `get_llm_analysis_by_id(analysis_id: int) -> Optional[LLMAnalysisObject]`: 根据ID获取分析结果。
        -   `get_llm_analyses_for_article(article_id: int) -> List[LLMAnalysisObject]`: 获取指定文章的所有相关分析结果。
        -   `get_all_llm_analyses(limit: Optional[int]=None, offset: Optional[int]=None, analysis_type: Optional[str]=None) -> List[LLMAnalysisObject]`: 获取LLM分析列表，支持分页和按类型过滤。
    -   *(请注意 `Dict_or_...Object` 表示方法可能接受字典或特定的数据类对象作为参数/返回值，具体参考 `NewsStorage` 代码。)*

### 3.4. 数据迁移

-   **从 JSON 到 SQLite**: 由于项目早期版本使用 JSON 文件存储数据，在迁移到 SQLite 后，通过一次性运行的迁移脚本 `tools/migrate_json_to_sqlite.py` 实现数据迁移。该脚本在版本升级时由用户手动执行，或由程序在首次检测到新版本且数据库为空时提示执行（具体触发机制待定）。
    -   迁移逻辑会读取旧的 JSON 文件 (`latest_news.json`, `news_*.json`, `read_status.json`, `browsing_history.json`, `analysis_*.json` 等)，将其数据模型转换为新的数据库表结构，并插入到 SQLite 数据库中。
    -   一旦迁移完成，旧的 JSON 文件可能会被归档或提示用户删除。

### 3.5. 事务管理与数据一致性

-   对于涉及多个写操作的原子性需求（例如，批量保存文章时，每条文章的保存都应成功，或者全部回滚），`NewsStorage` (应)使用 SQLite 的事务 (`BEGIN TRANSACTION`, `COMMIT`, `ROLLBACK`) 来确保数据的一致性。
-   例如，`save_articles` 方法应该在一个事务中执行所有插入/更新操作。

### 3.6. 错误处理

-   `NewsStorage` 的方法会捕获并处理在数据库交互过程中可能发生的 `sqlite3.Error` 及其子类异常（如 `sqlite3.IntegrityError` 用于处理唯一约束冲突，`sqlite3.OperationalError` 用于处理数据库文件问题等）。
-   错误可能会被记录到日志，并根据情况向上层调用者抛出自定义异常或返回错误指示符。

### 3.7. 性能与优化考虑

-   **索引**: 关键查询字段上都建立了数据库索引以加速查询。例如：
    -   `articles.link` (UNIQUE INDEX，用于快速查找和去重)
    -   `articles.publish_time` (用于排序和按时间范围查询)
    -   `articles.is_read`
    -   `articles.category_name`
    -   `news_sources.name` (UNIQUE INDEX)
    -   `browsing_history.article_id`
    -   `browsing_history.view_time`

## 核心服务交互与测试说明

### NewsStorage

- **数据库交互**: `NewsStorage` 是所有结构化数据（新闻文章、新闻源、分析结果、阅读历史等）的SQLite持久化层。
- **初始化与表结构**: 
    - 构造时接收数据库文件路径（默认为 `data/news_data.db`）。
    - `_create_tables()` 方法负责根据 `docs/development/logic/database_schema.sql` 文件中的 DDL 语句创建所有必要的表。
- **测试注意事项**:
    - **内存数据库 (`:memory:`)**: 
        - 为了单元测试的独立性和速度，可以使用 `:memory:` 作为 `db_name` 初始化 `NewsStorage`。
        - 当 `db_name` 为 `:memory:` 时，`NewsStorage.__init__` 的行为有所调整（截至目前的实现）：
            - 如果 DDL 文件 (`database_schema.sql`) 未找到，`_create_tables` 方法会记录一个警告并直接返回，而不是抛出 `FileNotFoundError`。这允许测试在 DDL 文件不可用（例如在某些 CI 环境或特定测试设置中）但测试本身完全 mock 了数据库方法调用的情况下继续进行。
            - 在最新的调整中，如果 `db_name == ":memory:"` 且实例上没有设置特定的 `_skip_db_setup_for_mock_tests` 属性（或类似的启发式标志），它仍会尝试连接并创建表。但如果设置了该标志（暗示测试将完全 mock 数据库交互），则 `_connect_db()` 和 `_create_tables()` 的调用会被跳过。这对于避免 `sqlite3.OperationalError: unable to open database file`（当 DDL 依赖的表无法创建时）在纯 mock 测试中非常关键。
    - **方法mocking**: 对于不直接测试数据库写入或读取逻辑的单元测试，应 mock `NewsStorage` 的具体方法 (如 `save_article`, `get_article_by_link` 等)。

### HistoryService

- **职责**: `HistoryService` 负责管理和提供文章的浏览历史和阅读状态。
- **与 NewsStorage 的关系**: 它依赖 `NewsStorage` 来持久化和检索历史数据 (例如，通过 `news_storage.get_browsing_history()` 和 `news_storage.add_read_item()`)。
- **核心方法与测试**: 
    - `get_all_history_items()`: 
        - 此方法是获取完整浏览历史的主要接口（替代了可能存在的旧版 `get_browsing_history()` 方法）。
        - 它内部调用 `self.storage.get_browsing_history()` (通常是 `NewsStorage` 实例)，该调用返回的是一个字典列表。
        - `get_all_history_items()` 负责将这些原始字典转换为 `HistoryEntry` 对象组成的列表 (`List[HistoryEntry]`) 后再返回。
        - 测试此方法时，需要 mock 底层的 `storage.get_browsing_history()`使其返回预期的字典列表，然后断言 `get_all_history_items()` 返回了正确转换和填充的 `HistoryEntry` 对象列表。
    - `mark_as_read(article_link: str)`: 记录一篇文章已被阅读。
    - `is_read(article_link: str) -> bool`: 检查一篇文章是否已被阅读。

### 状态管理与持久化

- **源状态加载**: `SourceManager` 从数据库加载新闻源时，会一并加载上次记录的状态 (`status`, `last_error`, `consecutive_error_count`)。**（已修正：之前版本会忽略这些字段，导致重启后状态丢失）**
- **状态检查**: `NewsUpdateService` 在刷新 RSS 源之前，会调用 `RSSCollector.check_source_status` 检查源的可访问性。**（已修正：修复了之前调用时传递参数类型错误导致所有检查失败的 Bug）**
- **状态更新**: `check_source_status` 返回结果（`ok` 或 `error` 及错误信息）后，`NewsUpdateService` 会更新对应 `NewsSource` 对象的内存状态（`status`, `last_checked_time`, `last_error`, `consecutive_error_count`）。状态的持久化依赖于 `SourceManager` 后续的保存操作（例如，通过 UI 面板触发的保存）。单次状态检查 `RSSSingleStatusCheckWorker` 会直接更新数据库。
- **连续错误**: `consecutive_error_count` 用于追踪连续检查或获取失败的次数，可用于 UI 提示或后续逻辑判断。

### 外部依赖与健壮性

- **网站结构变化**: 采集器（尤其是 `PengpaiCollector`）依赖于目标网站的 HTML 结构和 CSS 选择器。如果网站改版，选择器可能失效，导致内容获取失败。**（已通过多选择器策略和可配置性得到改善，但仍需监控）**
- **源可用性**: RSS 源本身可能因服务器问题、网络问题或内容提供商停止服务而无法访问。日志中记录的 HTTP 5xx 错误通常属于此类。
- **Feed 格式**: 某些 RSS 源（如 Nature, Science）可能使用非标准或 `feedparser` 难以完全解析的格式（如 RDF），导致无法获取文章。
- **日期解析**: Feed 中的日期格式多样，`dateutil` 库虽能处理大部分情况，但仍可能遇到无法识别的时区缩写等问题（通常为警告，不影响核心功能）。