# 00. 总体架构与核心组件职责 (v3)

本文档描述 news_analyzer v3 版本的总体软件架构和核心组件的职责。

## 1. 架构概述 (分层架构)

v3 版本采用更清晰的分层架构，旨在提高模块化、可测试性和可维护性。

```mermaid
graph TD
    subgraph "用户界面层 (UI Layer)"
        direction LR
        MainWindow --> PanelManager;
        PanelManager --> NewsListPanel;
        PanelManager --> NewsDetailPanel;
        PanelManager --> AnalysisPanel;
        PanelManager --> HistoryPanel;
        PanelManager --> SettingsPanel;
        SettingsPanel --> SourceManagementDialog;
        SettingsPanel --> LLMSettingsDialog;

        NewsListPanel --> NewsListViewModel;
        NewsDetailPanel --> NewsDetailViewModel;
        AnalysisPanel --> AnalysisViewModel;
        HistoryPanel --> BrowsingHistoryViewModel;
        SourceManagementDialog --> SourceViewModel;
        LLMSettingsDialog --> LLMSettingsViewModel;
    end

    subgraph "视图模型层 (ViewModel Layer)"
        direction LR
        NewsListViewModel;
        NewsDetailViewModel;
        AnalysisViewModel;
        BrowsingHistoryViewModel;
        SourceViewModel;
        LLMSettingsViewModel;
    end

    subgraph "应用服务层 (Application Service Layer)"
        direction TB
        AppService --> SourceManager;
        AppService --> NewsStorage;
        AppService --> LLMService;
        AppService --> NewsUpdateService;
        AppService --> AnalysisService;
        AppService --> HistoryService; # Added HistoryService dependency
    end

    subgraph "核心业务逻辑层 (Core Business Logic)"
        direction TB
        NewsUpdateService --> CollectorFactory;
        NewsUpdateService --> NewsStorage;
        NewsUpdateService --> SourceManager;
        NewsUpdateService --> SchedulerService; # Added SchedulerService dependency
        CollectorFactory --> RSSCollector;
        CollectorFactory --> PengpaiCollector;
        CollectorFactory --> BaseCollector[BaseCollector];
        AnalysisService --> LLMService;
        AnalysisService --> NewsStorage;
        AnalysisService --> EventAnalyzer;
        HistoryService --> NewsStorage; # HistoryService depends on NewsStorage
        EventAnalyzer --> LLMService;
        EventAnalyzer --> PromptManager;
        LLMService --> LLMConfigManager;
        LLMService --> PromptManager;
        LLMService --> ApiClient;
        SourceManager --> NewsStorage;
    end

    subgraph "基础设施层 (Infrastructure Layer)"
        direction TB
        NewsStorage[NewsStorage (SQLite for core data, JSON for specific configs/cache)];
        LLMConfigManager[LLMConfigManager (JSON/DB)];
        PromptManager[PromptManager (Files/DB)];
        ApiClient[ApiClient (requests)];
        SchedulerService[SchedulerService (APScheduler)];
    end

    %% ViewModel -> AppService / Other Services
    NewsListViewModel --> AppService;
    NewsListViewModel --> HistoryService;
    NewsDetailViewModel --> AppService;
    NewsDetailViewModel --> AnalysisService;
    NewsDetailViewModel --> HistoryService;
    AnalysisViewModel --> AppService;
    AnalysisViewModel --> AnalysisService;
    BrowsingHistoryViewModel --> HistoryService;
    SourceViewModel --> AppService;
    LLMSettingsViewModel --> AppService;
    LLMSettingsViewModel --> LLMService;
    LLMSettingsViewModel --> LLMConfigManager;


    %% Style Adjustments
    classDef ui fill:#f9f,stroke:#333,stroke-width:2px;
    classDef vm fill:#ccf,stroke:#333,stroke-width:2px;
    classDef app fill:#9cf,stroke:#333,stroke-width:2px;
    classDef core fill:#cfc,stroke:#333,stroke-width:2px;
    classDef infra fill:#eee,stroke:#333,stroke-width:2px;

    class MainWindow,PanelManager,NewsListPanel,NewsDetailPanel,AnalysisPanel,HistoryPanel,SettingsPanel,SourceManagementDialog,LLMSettingsDialog ui;
    class NewsListViewModel,NewsDetailViewModel,AnalysisViewModel,BrowsingHistoryViewModel,SourceViewModel,LLMSettingsViewModel vm;
    class AppService app;
    class NewsUpdateService,CollectorFactory,RSSCollector,PengpaiCollector,BaseCollector,AnalysisService,HistoryService,EventAnalyzer,LLMService,SourceManager,PromptManager,ApiClient,LLMConfigManager,SchedulerService core;
    class NewsStorage,LLMConfigManager,PromptManager,ApiClient,SchedulerService infra;

```

**核心分层:**

1.  **用户界面层 (UI Layer)**: 使用 PySide6 构建，负责用户交互和数据显示。包含主窗口 (`MainWindow`)、各种面板 (`NewsListPanel`, `NewsDetailPanel` 等) 和对话框 (`SettingsDialog` 等)。直接与 ViewModel 层交互。
2.  **视图模型层 (ViewModel Layer)**: 作为 UI 和核心服务之间的桥梁。每个主要的 UI 组件对应一个 ViewModel (`NewsListViewModel`, `AnalysisViewModel` 等)。负责处理 UI 事件，调用应用服务获取和处理数据，并将数据转换为 UI 可以直接使用的格式。持有 `AppService` 或其他特定核心服务的引用。
3.  **应用服务层 (Application Service Layer)**:
    *   **`AppService`**: (职责已减轻) 充当一个**高级协调器和部分 UI 状态的管理者**。它**不再直接处理新闻刷新、已读/历史记录**等具体业务，而是**持有并协调**其他核心服务 (`SourceManager`, `NewsStorage`, `LLMService`, `NewsUpdateService`, `AnalysisService`, `HistoryService`) 的实例。
    *   它负责初始化依赖关系、连接部分核心服务的信号，并维护一些跨多个 UI 组件共享的状态（如当前选中的新闻 `selected_news`）和缓存 (`news_cache`，在接收到新文章后，通过基于链接的去重逻辑高效更新此缓存，确保其内容的唯一性)。它还将一些核心服务发出的信号（如状态更新、刷新状态）转发给 UI 层。
4.  **核心业务逻辑层 (Core Business Logic)**: 包含执行具体业务逻辑的服务和组件。
    *   **`NewsUpdateService`**: (新增) 负责新闻源的**刷新和更新**。管理 Collector、处理并发、去重、调用存储保存新文章。
    *   **`CollectorFactory` / `Collectors`**: 负责从不同类型的新闻源（RSS, 澎湃等）获取数据。
    *   **`SourceManager`**: 管理新闻源（订阅列表）的增删改查和状态。
    *   **`AnalysisService`**: (新增) 负责**调用 LLM 进行新闻分析**（单篇、多篇、事件）。
    *   **`HistoryService`**: (新增) 负责管理**已读状态和浏览历史**。
    *   **`EventAnalyzer`**: (新增) 使用 LLM 进行更复杂的事件脉络分析。
    *   **`LLMService`**: 封装与 LLM API 的交互逻辑，包括调用、重试、错误处理。
    *   **`SchedulerService`**: (新增) 负责定时任务的管理和执行（例如定时刷新）。
    *   **`LLMConfigManager`**, **`PromptManager`**: 管理 LLM 配置和 Prompt 模板。
5.  **基础设施层 (Infrastructure Layer)**: 提供底层支持。
    *   **`NewsStorage`**: 负责新闻数据、配置、历史记录等的持久化存储（目前使用 SQLite 和 JSON）。
    *   **`ApiClient`**: 封装通用的 HTTP 请求逻辑。
    *   其他: 日志、配置加载等工具。 (图中未完全展示)

## 2. 核心组件职责

| 组件                     | 主要职责                                                                                                                                                              | 关键依赖                                                                 |
| :----------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------- |
| **`MainWindow` (UI)**    | 应用程序主窗口容器，管理面板切换、菜单栏、状态栏。                                                                                                                      | `PanelManager`, `AppService`, `AnalysisService`, `SchedulerService`          |
| **`PanelManager` (UI)**  | 管理和切换不同的内容面板（新闻列表、详情、分析等）。                                                                                                                    | 各 Panel 类                                                              |
| **各 Panel/Dialog (UI)** | 显示特定内容或提供特定交互界面，与对应的 ViewModel 交互。                                                                                                               | 对应的 ViewModel                                                           |
| **各 ViewModel (VM)**    | <li>处理对应 UI 的事件。</li><li>调用 `AppService` 或其他核心服务执行操作、获取数据。</li><li>管理 UI 状态。</li><li>将数据格式化供 UI 显示。</li><li>发出信号通知 UI 更新。</li> | `AppService` (用于协调和获取通用状态/缓存), 可能直接依赖 `AnalysisService`, `HistoryService`, `LLMConfigManager`, `LLMService` 等特定服务 |
| **`AppService` (App)**   | <li>**高级协调器**: 持有并初始化核心服务实例。</li><li>**信号转发**: 转发来自核心服务的状态信号 (如刷新状态、**刷新进度**)。</li><li>**缓存管理**: 维护 `news_cache`，通过精确的去重逻辑（基于文章链接）确保缓存中文章的唯一性，并**确保文章对象（包括日期等字段）在存入缓存前得到正确解析和格式化**。</li><li>**选择状态**: 管理当前选中的新闻。</li><li>**启动/关闭协调**: 协调应用的启动和关闭流程。</li> | `NewsStorage`, `SourceManager`, `LLMService`, `NewsUpdateService`, `AnalysisService`, `HistoryService` |
| **`NewsUpdateService` (Core)** | <li>**新闻刷新**: 调度和执行新闻源数据的获取和更新。</li><li>**并发控制**: 管理 Collector 的并发执行。</li><li>**数据处理**: 调用 Collector 获取数据，进行初步处理和去重。</li><li>**存储调用**: 将新文章写入 `NewsStorage`。</li><li>**状态通知**: 发出刷新开始、进度、完成、失败等信号。</li> | `SourceManager`, `NewsStorage`, `CollectorFactory`, `SchedulerService`         |
| **`CollectorFactory`/`Collectors` (Core)** | 根据新闻源类型创建并执行相应的 Collector，从源站点获取原始数据。`PengpaiCollector` 使用 WebDriver 和多选择器策略处理复杂页面。                                                                                                        | `ApiClient`, (具体的 HTML/XML 解析库, Selenium for Pengpai)                                      |
| **`SourceManager` (Core)** | <li>**源管理**: 提供新闻源的增、删、改、查接口。</li><li>**状态维护**: (可选) 跟踪每个源的检查状态、错误信息。</li><li>**存储交互**: 从 `NewsStorage` 加载和保存源配置。</li><li>**信号通知**: 发出 `sources_updated` 信号。</li> | `NewsStorage`                                                            |
| **`AnalysisService` (Core)** | <li>**LLM 分析**: 封装调用 `LLMService` 进行单篇/多篇/事件分析的逻辑。</li><li>**结果处理**: 处理 LLM 返回结果，更新 `NewsStorage` 中的分析字段。</li><li>**状态通知**: 发出分析开始、完成、失败等信号。</li> | `LLMService`, `NewsStorage`, `EventAnalyzer`                               |
| **`HistoryService` (Core)** | <li>**已读管理**: 提供标记已读/未读、检查已读状态的接口。</li><li>**历史记录**: 提供记录浏览历史、获取浏览历史的接口。</li><li>**存储交互**: 调用 `NewsStorage` 读写已读状态和历史记录。</li> | `NewsStorage`                                                            |
| **`EventAnalyzer` (Core)** | (待细化) 使用 LLM 对新闻事件进行更深层次的分析，如提取时间线、关键实体关系等。                                                                                           | `LLMService`, `PromptManager`                                              |
| **`LLMService` (Core)**    | <li>**API 封装**: 封装对不同 LLM 提供商 API 的调用，与包括 Ollama 在内的各类 Provider 交互稳定。</li><li>**配置管理**: 从 `LLMConfigManager` 获取 API Key、模型名称等配置。</li><li>**Prompt 组装**: 从 `PromptManager` 获取模板，组装最终的 Prompt。</li><li>**错误处理/重试**: 实现 API 调用的错误处理和重试逻辑。</li> | `LLMConfigManager`, `PromptManager`, `ApiClient`                           |
| **`SchedulerService` (Core)** | <li>**任务调度**: 使用 APScheduler 管理定时任务（如自动刷新）。</li><li>**持久化**: (可选) 将任务计划持久化。</li><li>**UI 交互**: (可选) 提供接口供 UI 控制定时任务。</li> | `QSettings` (用于加载配置), (可能需要 `NewsUpdateService` 等来执行任务)          |
| **`NewsStorage` (Infra)**  | <li>**数据持久化**: 提供接口用于存储和检索新闻文章、新闻源配置、已读状态、浏览历史、分析结果等。能够处理文章 `publish_time` 为空的情况。</li><li>**存储实现**: 主要使用 SQLite 数据库 (`data/news_data.db`) 进行核心数据（新闻文章、历史记录、已读状态等）的持久化。部分特定配置（如 Prompt 模板元数据）或旧格式数据可能仍涉及 JSON 文件。</li>              | (文件系统 API, `sqlite3` 库)                                             |
| **`LLMConfigManager` (Infra)** | 管理 LLM 服务的配置信息（API Key, URL, 模型参数等）。                                                                                                                   | (文件系统 API 或数据库)                                                  |
| **`PromptManager` (Infra)** | 管理用于与 LLM 交互的 Prompt 模板。                                                                                                                              | (文件系统 API 或数据库)                                                  |
| **`ApiClient` (Infra)**    | 提供通用的 HTTP 请求功能（GET, POST 等），处理 User-Agent、超时、代理等。                                                                                                  | `requests` 库                                                            |

## 3. 数据流概述

*   **新闻获取**: `NewsUpdateService` 定期或手动触发 -> `SourceManager` 获取源列表 -> `CollectorFactory` 创建 `Collector` -> `Collector` 获取数据 -> `NewsUpdateService` 处理、去重 -> `NewsStorage` 保存新文章 -> `NewsUpdateService` 发出 `news_refreshed` 信号 -> `AppService` 接收信号，通过去重逻辑更新 `news_cache` (如果文章已存在于缓存中，则用新获取的版本替换；如果不存在，则添加至缓存)，确保缓存的唯一性 -> `AppService` 发出 `news_cache_updated` 信号 -> `NewsListViewModel` 接收信号，更新列表 -> `NewsListPanel` 显示。
*   **新闻阅读**: 用户在 `NewsListPanel` 点击文章 -> `NewsListViewModel` 调用 `HistoryService.mark_as_read()` 和 `HistoryService.record_browsing_history()` -> `HistoryService` 调用 `NewsStorage` 更新状态/记录 -> `NewsListViewModel` (可能)更新 UI 状态。
*   **新闻分析**: 用户在 UI (如 `AnalysisPanel`) 发起分析 -> `AnalysisViewModel` 调用 `AnalysisService.analyze_xxx()` -> `AnalysisService` 调用 `LLMService` -> `LLMService` 调用 LLM API -> `AnalysisService` 处理结果，调用 `NewsStorage` 更新文章分析字段 -> `AnalysisService` 发出完成信号 -> `AnalysisViewModel` 更新 UI。

## 4. 关键设计决策

*   **依赖注入**: 使用 `dependency-injector` 管理服务实例和依赖关系，提高可测试性和灵活性。
*   **ViewModel 模式**: 解耦 UI 和业务逻辑，使 UI 更专注于显示和交互。
*   **服务拆分**: 将 `AppService` 的职责进一步拆分到 `NewsUpdateService`, `AnalysisService`, `HistoryService` 等，实现单一职责原则。
*   **信号/槽**: 使用 Qt 的信号/槽机制进行组件间的异步通信。
*   **异步处理**: 对于耗时操作（如网络请求、LLM 调用），应使用异步方式（如 `QThreadPool`, `asyncio` - 具体实现待定）执行，避免阻塞 UI。

## 5. 后续演进方向

*   **完善异步处理**: 在 `NewsUpdateService`, `AnalysisService`, `LLMService` 中全面引入异步操作。
*   **数据库优化**: 考虑更健壮的数据库方案（如 PostgreSQL）或对 SQLite 进行优化（索引、连接管理）。
*   **配置系统**: 完善配置加载和管理机制。
*   **错误处理**: 建立更全面的错误处理和报告机制。
*   **测试覆盖**: 增加单元测试和集成测试覆盖率。
