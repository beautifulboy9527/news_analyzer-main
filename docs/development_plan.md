# news_analyzer 项目扩展可行性分析与规划

## 1. 详细可行性分析

| 功能点                     | 技术可行性 | 潜在难点                                                                 | 所需技术栈 (新增以 * 标注)                                                                                                                               | 预估复杂度 |
| :------------------------- | :--------- | :----------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------- |
| **集成更多 RSS 源**        | 高         | 无明显难点，主要是配置管理和 UI 交互。                                       | Python, requests/feedparser (现有)                                                                                                                       | 低         |
| **制作 RSS 源 (监控社交媒体)** | 中         | <li>反爬虫机制 (IP 限制, 验证码, JS 混淆)</li><li>API 变化频繁</li><li>不同平台差异大</li><li>需要维护登录状态 (Cookies/Tokens)</li> | Python, requests, BeautifulSoup4, Playwright (现有), *特定平台 API 库 (可选), *数据库/文件存储 (用于状态持久化), *Web 框架 (如 FastAPI/Flask, 用于生成 Feed) | 高         |
| **增强信息采集能力**       |            |                                                                          |                                                                                                                                                          |            |
|   - 支持 Atom/JSON Feed    | 高         | feedparser 库已支持 Atom，需要增加对 JSON Feed 的解析逻辑。                  | Python, feedparser (现有), *json (标准库)                                                                                                                | 低         |
|   - 处理需登录内容         | 中         | <li>维护登录状态 (Cookies/Tokens)</li><li>处理登录流程 (可能需要模拟浏览器)</li><li>安全性考虑 (存储凭证)</li> | Python, requests (Session), Playwright (现有), *安全存储机制 (如 keyring, cryptography)                                                                    | 中         |
| **同一新闻多来源信息汇总聚合** | 中         | <li>新闻去重/相似度计算 (文本相似度算法)</li><li>信息关联与聚类 (需要设计合适的算法和数据结构)</li><li>实时性要求高</li> | Python, *Scikit-learn/spaCy/NLTK (文本处理/相似度), *数据库索引优化 (用于快速查找), SQLAlchemy/PyMongo (现有)                                                | 高         |
| **自动定时更新和收集**     | 高         | 需要可靠的调度机制，处理任务失败和重试。                                     | Python, *APScheduler / Celery / 系统 Cron                                                                                                                | 低-中      |
| **利用 LLM 进行内容创作**  | 中         | <li>Prompt Engineering (设计高效、稳定的 Prompt)</li><li>控制生成内容的质量和风格</li><li>成本控制 (LLM API 调用费用)</li><li>处理长文本输入/输出</li> | Python, Langchain, 各 LLM API (现有), *更精细的 Prompt 管理/模板库                                                                                       | 中         |
| **自动同步内容到自媒体平台** | 低-高      | <li>各平台 API 差异大，文档不完善或缺失</li><li>API 授权和 Token 管理复杂</li><li>需要处理发布频率限制和内容审核</li><li>维护成本高 (API 经常变动)</li> | Python, requests (现有), *各平台官方/非官方 SDK, *OAuth 库, *更健壮的任务队列 (如 Celery, 用于处理异步发布和重试)                                          | 高         |

**复杂度说明:**

*   **低**: 改动较小，主要在现有框架内调整或增加简单功能。
*   **中**: 需要引入新库或设计新模块，涉及一定的算法或流程设计。
*   **高**: 涉及复杂算法、第三方集成、反爬虫对抗、架构调整或大量开发工作。

## 2. 参考项目借鉴

*   **RSSNext/Folo**:
    *   **借鉴点**:
        *   **Web 化 RSS 生成**: Folo 核心是基于 Web 服务生成 RSS，这对于我们"制作 RSS 源"和"自动同步"功能有参考价值，可以将核心处理逻辑与发布分离。
        *   **规则化内容提取**: Folo 可能使用了基于 CSS 选择器或其他规则来从网页提取内容生成 Feed，这对于抓取无 RSS 的网站有帮助。
        *   **缓存机制**: 高效的缓存对于降低源站压力和提高响应速度至关重要。
*   **plenaryapp/awesome-rss-feeds**:
    *   **借鉴点**:
        *   **信息源发现**: 这是一个高质量 RSS 源的集合，可以作为我们"集成更多 RSS 源"的参考列表，甚至可以考虑集成其列表作为推荐源。
*   **imsyy/DailyHotApi**:
    *   **借鉴点**:
        *   **聚合不同来源的热点信息**: 该项目聚合了多个平台的热榜，思路与我们的"同一新闻多来源信息汇总聚合"类似，可以参考其数据源和可能的聚合方式。
        *   **API 设计**: 提供标准化的 API 接口，方便不同客户端或服务调用，这对于未来可能的平台化扩展有意义。
        *   **特定平台适配**: DailyHotApi 对接了多个国内平台，其适配代码(如果开源)可能对我们"制作 RSS 源 (监控社交媒体)"和"自动同步内容"有直接参考价值。

## 3. 开发计划 (分阶段路线图)

基于可行性分析和复杂度评估，建议采用分阶段迭代的方式进行开发：

```mermaid
graph TD
    subgraph "阶段一 (基础增强与易实现功能)"
        A[集成更多 RSS 源 (UI 与配置)] --> B(支持 Atom/JSON Feed);
        B --> C(自动定时更新与收集 - 基础版 APScheduler);
    end

    subgraph "阶段二 (核心采集与处理能力提升)"
        C --> D(增强采集: 处理需登录内容);
        D --> E(利用 LLM 进行内容创作 - Prompt 优化与集成);
    end

    subgraph "阶段三 (高级功能与平台化探索)"
        E --> F(制作 RSS 源 - 监控社交媒体);
        F --> G(同一新闻多来源信息汇总聚合);
        G --> H(自动同步内容到自媒体平台 - 试点1-2个平台);
    end

    subgraph "持续优化"
        I(性能优化与代码重构);
        J(错误处理与日志监控);
        K(用户反馈与功能迭代);
    end

    C --> I;
    E --> I;
    H --> I;
    C --> J;
    E --> J;
    H --> J;
    H --> K;

```

**阶段目标与主要任务:**

*   **阶段一: 基础增强与易实现功能 (复杂度: 低-中)**
    *   **目标**: 快速提升现有功能易用性，实现低复杂度新需求。
    *   **任务**:
        1.  **集成更多 RSS 源**: 优化 UI，方便用户添加、编辑、删除 RSS 源；提供导入/导出 OPML 功能。 (低)
        2.  **支持 Atom/JSON Feed**: 修改 `RSSCollector` 或增加新的 Collector，使用 `feedparser` 处理 Atom，增加 JSON Feed 解析逻辑。 (低)
        3.  **自动定时更新**: 集成 `APScheduler`，提供简单的 UI 配置定时任务(如每小时、每天)，实现后台自动调用 `refresh_all_sources`。 (低-中)
*   **阶段二: 核心采集与处理能力提升 (复杂度: 中)**
    *   **目标**: 增强获取信息和利用 LLM 处理信息的核心能力。
    *   **任务**:
        1.  **增强采集 (登录内容)**: 设计安全存储用户 Cookies/Tokens 的方案；更新 `requests` 或 `Playwright` 相关逻辑以携带认证信息；提供 UI 让用户配置登录信息或引导完成登录。 (中)
        2.  **LLM 内容创作**: 深入研究 Langchain 的 Prompt 模板和链式调用；设计更灵活、可配置的 Prompt 管理机制；在 UI 中集成内容创作入口，允许用户选择文章、选择创作模式(摘要、改写、评论等)并调用 LLM 服务。 (中)
*   **阶段三: 高级功能与平台化探索 (复杂度: 高)**
    *   **目标**: 实现复杂度较高的新功能，探索自动化发布。
    *   **任务**:
        1.  **制作 RSS 源 (社交媒体)**: 选择 1-2 个目标平台(如微博)；研究其 API 或网页结构；使用 `Playwright` 或 `requests` + Cookies 模拟登录和抓取；设计 Feed 生成逻辑并提供访问端点(可能需要简单的 Web 服务)。 (高)
        2.  **信息汇总聚合**: 研究文本相似度算法 (如 TF-IDF, Doc2Vec, Sentence Transformers)；设计新闻去重和聚类逻辑；改造数据模型和存储，支持新闻关联；在 UI 中展示聚合后的信息。 (高)
        3.  **自动同步内容**: 选择 1-2 个目标自媒体平台(如微信公众号草稿箱、知乎专栏)；研究其 API 或发布机制；实现内容格式转换和 API 调用；处理授权流程；在 UI 中提供配置和触发入口。 (高)
*   **持续优化**:
    *   **目标**: 贯穿所有阶段，保证系统稳定性、性能和可维护性。
    *   **任务**:
        1.  **性能优化**: 分析瓶颈，优化数据库查询、并发处理、内存使用等。
        2.  **错误处理与监控**: 完善错误捕获、日志记录，增加关键指标监控。
        3.  **代码重构**: 保持代码整洁，优化架构。
        4.  **用户反馈**: 根据用户使用情况持续迭代。

**优先级建议:**

1.  **阶段一**: 优先级最高，投入产出比较高，能快速提升用户体验。
2.  **阶段二**: 优先级次之，增强核心竞争力。
3.  **阶段三**: 优先级最低，复杂度高，风险大，建议在核心功能稳定后再投入资源。可以先做技术预研和小范围试点。

### 3.1 模块化重构策略与风险控制建议 (针对 AppService 分解)

在执行模块化重构（特别是分解 `AppService`）时，为减少潜在的数据接口错乱和 UI 混乱，建议遵循以下策略：

1.  **严格遵循迭代方法:** 不要一次性重构所有功能。按照 `.cursor/rules/modularization_guidelines.md` 的指引，先聚焦一个职责领域（如新闻更新），完成迁移和测试，稳定后再进行下一个。
2.  **先定义接口再迁移代码:** 在移动代码前，清晰定义新服务（如 `NewsUpdateService`）的公共方法、信号和依赖关系。
3.  **显式依赖管理:**
    *   明确新服务的实例化位置（如 `main.py` 或 `MainWindow`）。
    *   规划如何将新服务实例注入到需要的组件中（如更新 ViewModel 的 `__init__` 参数）。
4.  **小步提交与测试:**
    *   在专门的分支上进行重构。
    *   频繁进行小步提交，每次提交对应一个小的逻辑迁移或依赖更新。
    *   在关键步骤后，手动运行应用并**重点测试受影响的功能**，确保其行为符合预期。利用自动化测试（如果存在）。
5.  **精确的信号/槽迁移:**
    *   在将信号从 `AppService` 移到新服务时，必须找到所有旧的连接。
    *   断开旧连接，并重新连接到新服务的信号。
6.  **考虑临时适配器 (可选):** 如果直接修改所有调用方（如多个 ViewModel）风险较大，可以考虑让 `AppService` 暂时保留旧接口，内部调用新服务。待新服务稳定后，再逐步修改调用方直接依赖新服务。
7.  **关注 UI 行为:** 除了后端逻辑，需仔细验证 UI 是否按预期响应了新服务的信号和数据变化。
8.  **遵循文档同步规则:** 每次完成一个功能领域的重构后，及时更新 `docs/development/logic/` 下的相关文档。

### 3.2 近期完成的修复与改进 (截至 2025-05-08)

*   **修复 SchedulerService 关闭错误**: 解决了程序关闭时因调用不存在的 `shutdown` 方法导致的 `AttributeError`。
*   **修复 Gemini API 密钥轮询**: 确保在 API 调用超时 (HTTP 408) 时，系统能正确触发密钥轮换并重试，增强了对网络不稳定的容错性。
*   **实现历史新闻备份**: 修改了 `AppService` 的保存逻辑，在写入 `latest_news.json` 前，将旧文件备份为带时间戳的 `news_YYYYMMDD_HHMMSS.json` 文件，从而保留了历史新闻批次。
*   **优化导入/导出 UI**: 修正了"导出历史新闻批次"下拉菜单，使其能正确显示所有历史批次文件（包括 `latest_news.json` 和时间戳文件），并优化了显示文本，避免冗余。
*   **确认自动排序**: 验证了 `NewsListViewModel` 的逻辑，确认新闻列表在数据更新后会默认按发布时间降序自动排序。
*   **统一历史记录管理面板**: 
    *   创建了新的 `HistoryPanel` 和 `HistoryViewModel` 用于统一管理浏览历史、分析历史和聊天历史。
    *   **浏览历史功能**: 已成功实现并修复了数据显示问题。用户现在可以在"历史记录管理"面板的"浏览历史"标签页中查看、刷新、删除单条和清空所有浏览过的新闻记录。
    *   修复了打开新闻详情时未正确记录浏览历史的问题。
    *   解决了多次打开/关闭历史面板可能导致的 `RuntimeError`。
    *   统一了界面中文化，并修复了面板显示为空白框的问题。

*   **修复新闻分析与整合面板 (IntegratedAnalysisPanel)**:
        *   **核心修复**: 解决了在进行新闻分析（如相似度分析）后，分析结果无法在UI界面 (`result_edit`) 中正确显示的问题。此问题最终通过以下步骤解决：
            *   确保 `IntegratedAnalysisPanel` 内部的 `analysis_completed` 信号在 `__init__` 方法中正确连接到其自身的 `_on_analysis_completed` 槽函数。
            *   调试并优化了 `_analyze_selected_news` 方法，确保其能正确处理从 `LLMService` 返回的分析结果（无论是字典还是预格式化的HTML字符串），并将其完整地通过 `analysis_completed` 信号发出。
            *   重构并简化了 `_on_analysis_completed` 槽函数，使其能够可靠地接收信号传递的数据，并根据数据类型（HTML或普通文本）正确更新 `self.result_edit` 控件的内容。
    *   **修复主界面搜索功能失效**:\n        *   **问题**: 由于模块化重构 (特别是 `AppService` 分解后)，导致 `SearchPanel` 的信号未能正确连接，使得主界面的搜索框输入关键词后无任何反应。\n        *   **修复过程**:\n            *   确认 `SearchPanel` 定义了 `search_requested` (携带搜索参数) 和 `search_cleared` (清空搜索时) 信号。\n            *   确认 `MainWindow` 具有 `_handle_search_request(params: dict)` 槽函数，用于接收搜索参数并调用 `NewsListViewModel.search_news(term, field)`。\n            *   确认 `NewsListViewModel` 具有 `search_news(term, field)` 和 `clear_search()` 方法。\n            *   **解决方案**: 在 `MainWindow` 的 `_connect_manager_signals` 方法中，添加了对 `SearchPanel` 实例的信号连接：\n                *   将 `SearchPanel.search_requested` 信号连接到 `MainWindow._handle_search_request` 槽。\n                *   将 `SearchPanel.search_cleared` 信号连接到 `NewsListViewModel.clear_search` 槽。\n            *   同时，确保了 `_handle_search_request` 方法从传递的 `params` 字典中正确使用键名 `\'query\'` (而不是之前的 `\'term\'`) 来获取搜索词，以匹配 `SearchPanel`发出的信号内容。\n        *   **结果**: 主界面的搜索功能恢复正常，用户可以输入关键词进行搜索，并且在清空搜索框后，新闻列表也能正确更新以显示所有内容。\n*   **修复LLM服务API调用**:\n    *   修正了 `LLMService` 类中的 `analyze_news_similarity` 方法。此前该方法在提供者为 `GeminiProvider` 时错误地使用了基础的 `api_url`，导致API请求404。现已确保其在此情况下正确使用 `GeminiProvider` 特有的 `chat_generate_url`。

*   **(进行中) 核心重构: 数据存储迁移 (截至 2025-05-11)**:
    *   **阶段一: 准备与设计**: **已完成**。数据库表结构已在 `docs/development/logic/database_schema.sql` 中最终确定。`NewsStorage` 的新接口已规划完毕。
    *   **阶段二: `NewsStorage` 核心实现与初步迁移**: **已完成**。`src/storage/news_storage.py` 已使用 `sqlite3` 重写，实现了对新表结构的CRUD操作。数据迁移脚本 `tools/migrate_json_to_sqlite.py` 已开发完成，能够将旧JSON数据导入新SQLite数据库。
    *   **阶段三: 服务层、ViewModel适配及集成测试**: **进行中**。
        *   已适配的服务：
            *   `src/core/history_service.py`
            *   `src/core/app_service.py` (大部分功能，如历史记录、已读状态、新闻文章模型、新闻刷新后的处理)
            *   `src/core/news_update_service.py` (文章保存逻辑)
            *   `src/core/source_manager.py` (新闻源的数据库持久化)
            *   `src/config/llm_config_manager.py` (LLM配置的保存与加载)
        *   已适配的UI组件：
            *   `src/ui/source_management_panel.py` (及相关ViewModel)
            *   `src/ui/llm_settings.py` (LLMSettingsDialog 及其 ViewModel)
        *   进行中的测试工作：
            *   `tests/core/test_source_manager.py` (重构和适配已取得显著进展)
        *   待进行的适配与测试：
            *   `AnalysisService` (如果涉及数据库存储) 的适配。
            *   其他直接或间接依赖旧数据存储方式的UI组件和ViewModel的全面审查与适配。
            *   `tests/test_source_manager.py` 的重构与适配。
            *   针对已适配服务的其他单元测试和集成测试（如 `AppService`, `NewsUpdateService`, `HistoryService`）。
            *   数据迁移脚本 `tools/migrate_json_to_sqlite.py` 的全面测试和验证。
            *   全面的端到端集成测试。
    *   **阶段四: 错误排除、性能优化与最终验证**: 尚未开始。

### 3.3 下一步重点规划与待办事项

*   **(高优先级 - 验证) 历史记录UI功能**:
    *   **任务**: 确认 `BrowsingHistoryPanel` 在与 `BrowsingHistoryViewModel` 和 `HistoryService` 集成后，能够正确显示浏览历史记录。验证过滤、删除单条/全部历史、刷新列表等功能是否按预期工作。特别关注从 `HistoryService` 发出的 `browsing_history_updated` 信号是否能正确触发 `BrowsingHistoryViewModel` 的数据刷新，并最终更新UI。
    *   **状态**: 待验证

*   **(高优先级 - 验证) 无效RSS源删除后UI更新**:
    *   **任务**: 确认在 `SourceManagementPanel` 中删除无效RSS源后，由于 `AppService` 已修复了对 `SourceManager.sources_updated` 信号的转发，UI列表是否能正确、及时地移除被删除的源。
    *   **状态**: 待验证

*   **(高优先级 - 修复) 导入/导出功能**:
    *   **任务**: 全面排查 `ImportExportDialog` 及相关逻辑，定位并修复导入导出功能未按预期工作的问题。这可能涉及文件读写、数据格式转换、与 `AppService` 或 `NewsStorage` 的交互等。
    *   **状态**: 待排查与修复

*   **(中优先级 - 确认) 新闻持久化与加载机制**:
    *   **任务**: 最终确认以下流程是否按预期工作：
        *   通过 `NewsUpdateService` 刷新新闻时，去重后的新闻是否被正确写入 SQLite 数据库的 `articles` 表。
        *   应用程序启动时，`AppService._load_initial_news()` 是否能从数据库正确加载已有的新闻数据到 `news_cache` 并显示在UI上。
    *   **状态**: 待最终确认

*   **(高优先级) 核心重构: 数据存储迁移**: 将新闻数据（包括文章内容、元数据）、新闻源配置、浏览历史、已读状态以及相关的LLM分析结果从当前的 JSON 文件存储方式全面迁移到 SQLite 数据库。
    *   **目标**:\n        *   从根本上解决 JSON 文件在数据量增大时带来的性能瓶颈（加载慢、内存占用高、查询效率低）。\n        *   提高数据操作的原子性和一致性。\n        *   为未来更复杂的数据分析和功能扩展（如高级搜索、数据关联）奠定坚实基础。\n        *   确保程序在迁移后功能完整、运行稳定、无数据操作相关错误。\n    *   **复杂度**: 高 (涉及核心模块重写、代码大范围适配和全面测试)\n    *   **详细实施步骤与策略**:\n\n        1.  **阶段一: 准备与设计 (Foundational Setup & Design)** - **已完成**
            *   **1.1. 最终确定数据库表结构**:\n                *   **任务**: 基于 `docs/development/logic/01_news_collection_and_storage.md` 中的草案，并结合对现有JSON数据结构的全面分析，最终确定 SQLite 数据库的详细表结构（表名、字段名、数据类型、约束如 NOT NULL, UNIQUE, PRIMARY KEY, FOREIGN KEY）。\n                *   **状态**: **已完成**。产出为 `docs/development/logic/database_schema.sql`。
            *   **1.2. 规划 `NewsStorage` 新接口**:\n                *   **任务**: 设计新 `NewsStorage` 类的公共方法签名。这些方法应能满足上层服务（`AppService`, `HistoryService`等）对数据的所有CRUD需求。\n                *   **状态**: **已完成**。接口体现在重写后的 `src/storage/news_storage.py` 中。

        2.  **阶段二: `NewsStorage` 核心实现与初步迁移 (Core Implementation & Initial Migration)** - **已完成**
            *   **2.1. 重写 `NewsStorage` 模块**:\n                *   **任务**: 基于新的表结构和接口规划，使用 `sqlite3` 模块完全重写 `src/storage/news_storage.py`。\n                *   **状态**: **已完成**。包括数据库连接管理、表初始化、参数化SQL查询执行、事务管理、错误处理等。针对新 `NewsStorage` 的独立单元测试已初步设想（待全面编写）。
            *   **2.2. 开发数据迁移脚本/逻辑**:\n                *   **任务**: 创建一个健壮的迁移工具/脚本（例如 `tools/migrate_json_to_sqlite.py`）。\n                *   **状态**: **已完成**。脚本能够读取旧JSON文件，转换数据模型，并批量插入SQLite。

        3.  **阶段三: 服务层与ViewModel适配及集成测试 (Service & ViewModel Adaptation, Integration Testing)** - **进行中**
            *   **3.1. 逐个适配依赖 `NewsStorage` 的服务**:
                *   **任务**: 从最底层或依赖最少的服务开始，逐步向上适配。
                *   **状态**: **进行中**。
                    *   `src/core/history_service.py`: **已适配**。
                    *   `src/core/app_service.py`: **大部分已适配** (历史记录、已读状态、文章模型、新闻获取后处理等)。
                    *   `src/core/news_update_service.py`: **已适配** (文章保存至数据库)。
                    *   `src/core/source_manager.py`: **已适配** (新闻源配置的数据库持久化)。
                    *   `src/config/llm_config_manager.py`: **已适配** (LLM配置的保存与加载)。
            *   **3.2. 适配ViewModel层**:
                *   **任务**: 修改所有直接或间接依赖数据存储的ViewModel。
                *   **状态**: **进行中**。
                    *   `SourceManagementPanel` 相关的ViewModel: **已适配**。
                    *   其他ViewModel: 待审查和适配。
            *   **3.3. 全面集成测试**:
                *   **任务**: 执行端到端测试，覆盖从用户操作 -> UI -> ViewModel -> 服务层 -> `NewsStorage` -> 数据库，再反向到UI的完整数据流。对已迁移模块编写和更新单元/集成测试。
                *   **状态**: **进行中**。
                    *   `tests/core/test_source_manager.py`: 重构和适配进展显著。
                    *   `tests/test_source_manager.py`: 待重构和适配。
                    *   其他服务的测试: 待更新/编写。
                    *   数据迁移脚本 `tools/migrate_json_to_sqlite.py`: 待全面测试。
        *   **适配UI组件与ViewModel**:
            *   `src/ui/viewmodels/browsing_history_viewmodel.py`: **已适配**以使用 `HistoryService` 并响应其信号。
            *   `src/ui/browsing_history_panel.py`: **已适配**以使用 `BrowsingHistoryViewModel`。
            *   `src/ui/managers/dialog_manager.py`: **已适配**以正确实例化和管理新的历史记录面板 (`BrowsingHistoryPanel`) 及其ViewModel (`BrowsingHistoryViewModel`)。
        *   **适配核心服务**:
            *   `src/core/app_service.py`: **已适配**在其 `_initialize_dependencies` 方法中连接 `self.source_manager.sources_updated` 到自身的 `sources_updated` 信号，以确保新闻源的变更能够正确通知到监听 `AppService` 的UI组件。

        4.  **阶段四: 错误排除、性能优化与最终验证 (Bug Fixing, Performance Tuning & Final Validation)** - 待开始
            *   **4.1. 集中错误排除**:\n                *   **状态**: 待开始。
            *   **4.2. 性能评估与优化**:\n                *   **状态**: 待开始。
            *   **4.3. 清理与收尾**:\n                *   **状态**: 待开始。
            *   **4.4. 回归测试**: \n                *   **状态**: 待开始。

## 5. 总结报告

本项目采纳了"以测试驱动和保障的增量式重构与开发"策略（详见 4.3 节），以应对当前模块化和测试覆盖的挑战，并指导后续的稳健发展。`news_analyzer` 项目具备扩展为自动化信息处理和发布平台的潜力，但挑战与机遇并存。

*   **可行性**: 大部分用户需求在技术上是可行的，但"制作 RSS 源 (监控社交媒体)"、"信息汇总聚合"和"自动同步内容"这三项功能复杂度高，需要投入较多研发资源，并可能面临反爬、API 动等外部风险。
*   **技术栈**: 项目现有技术栈(Python, PyQt5, Langchain, SQLAlchemy/PyMongo, Playwright)为扩展奠定了良好基础。主要需引入任务调度库 (APScheduler/Celery)、可能的文本处理库 (Scikit-learn/spaCy)、Web 框架 (FastAPI/Flask) 以及特定平台的 API/SDK。
*   **参考项目**: Folo、awesome-rss-feeds 和 DailyHotApi 在 Web 化服务、信息源发现、API 设计和特定平台适配方面提供了有价值的参考。
*   **开发计划**: 建议采用分三阶段的迭代开发策略：
    1.  **阶段一**: 聚焦基础增强(更多 RSS 源、Atom/JSON 支持、定时更新)。
    2.  **阶段二**: 提升核心能力(处理登录内容、LLM 内容创作)。
    3.  **阶段三**: 攻坚高级功能(制作社交媒体 RSS、信息聚合、自动发布试点)。
    同时，持续进行性能优化、错误处理和代码重构。

**建议**:

*   优先完成阶段一，快速交付价值。
*   阶段二和阶段三的功能可以根据资源和优先级进一步细化和调整。
*   对于复杂度高的功能(特别是阶段三)，建议先进行充分的技术预研和原型验证。
*   在开发过程中，持续关注参考项目的进展和社区的最佳实践。 

def test_news_cache_updated_signal(mock_dependencies, qtbot):
    """
    测试新闻缓存更新信号发射。
    不能 patch Qt 信号的 emit，需用 qtbot.waitSignal 监听信号。
    """
    app_service = AppService(**mock_dependencies)
    # 监听信号并调用 _load_initial_news
    with qtbot.waitSignal(app_service.news_cache_updated, timeout=1000) as blocker:
        app_service._load_initial_news()
    # 可选：assert isinstance(blocker.args[0], list) 

def __init__(self, storage: NewsStorage):
    super().__init__()
    self.logger = logging.getLogger(__name__)
    if storage is None:
        self.logger.warning("NewsStorage instance is None. HistoryService will run in degraded mode.")
    self.storage = storage
    self.logger.debug("HistoryService initialized.")

def mark_as_read(self, link: str):
    if not link or not self.storage:
        return
    # ...原有逻辑...

def is_read(self, link: str) -> bool:
    if not link or not self.storage:
        return False
    # ...原有逻辑... 