# 讯析 v3.1.0 - 你的智能信息管家 🤖📰

## 项目概述

在信息爆炸的时代，高效获取和理解新闻资讯至关重要。这款基于 Python 和 PySide6 的新闻聚合与分析系统，旨在成为您的智能信息助手，帮助您：

*   **聚合信息:** 自动从您指定的 RSS 源、澎湃新闻、JSON Feed 等渠道收集最新内容，并通过高效的去重机制确保信息列表的简洁性。
*   **智能整理:** 对获取的新闻进行自动分类（基于来源或内容关键词），并将相似报道聚合成单一事件。
*   **AI 赋能:** 利用大语言模型（LLM）快速生成新闻摘要、进行情感分析、提取关键观点、分析事件重要性和立场，并能通过聊天界面与 AI 探讨新闻内容。
*   **便捷管理:** 提供新闻源管理、浏览历史回顾、数据导入导出、主题和字体大小调整等实用功能。

本项目致力于提供一个便捷、智能的新闻处理平台。

## 主要功能

1.  **新闻采集:**
    *   **RSS 源:** 灵活添加和管理 RSS/Atom 订阅。
    *   **澎湃新闻:** 内置对澎湃新闻的支持，通过 WebDriver 实现内容抓取，并采用多选择器策略以适应不同页面布局 (可能需要用户配置或更新选择器)。
    *   **JSON Feed:** 支持 JSON Feed 格式的新闻源。
    *   **自动分类:** 基于新闻来源或内容关键词进行初步分类。
    *   **事件聚类:** 自动识别并聚合相似新闻报道为单一事件。

2.  **新闻分析 (LLM):**
    *   **智能摘要:** 快速了解文章核心内容。
    *   **深度分析:** 获取对新闻事件更深层次的解读。
    *   **关键观点:** 提取文章的主要论点。
    *   **事实与观点分离:** 尝试区分报道中的客观事实和主观观点。
    *   **智能聊天:** 与 AI 进行基于新闻或开放主题的对话。
    *   **重要程度和立场分析:** 评估新闻事件的重要性和报道的观点倾向。
    *   **自定义分析:** 通过灵活的提示词管理系统（支持模板创建、分类、编辑和占位符填充）进行自定义分析。详见 `docs/development/logic/03_llm_interaction.md` 中关于 Prompt 管理的描述。

3.  **用户界面:**
    *   **新闻列表:** 清晰展示新闻条目，标记已读/未读状态。
    *   **分类导航:** 通过侧边栏快速筛选不同类别或来源的新闻。
    *   **事件视图:** 在"分类与分析"面板中查看聚类后的事件。
    *   **内容搜索:** 支持按关键词搜索标题和/或内容。
    *   **详情阅读:** 双击可在独立窗口阅读新闻，支持字体缩放和内容复制。
    *   **个性化:** 通过"编辑"菜单下的"应用程序设置"对话框提供日间/夜间主题切换和全局字体大小调整功能。
    *   **自动化设置:** 通过"工具"菜单下的"自动化设置"对话框配置后台任务，如新闻自动刷新间隔。
    *   **LLM分析面板:** 针对单个选定新闻进行快速摘要或分析。
    *   **分类与分析面板:** (原新闻分析整合面板) 查看聚类事件、事件详情、媒体原文，进行多维度LLM分析（重要性、立场、事实观点等），并管理分析提示词。
    *   **历史记录管理:** 在统一的专用面板中回顾和管理浏览历史（分析历史和聊天历史功能规划中）。

## 技术栈与架构

### 核心语言与框架
* **Python 3.10+**: 项目核心语言
* **PySide6**: 构建图形用户界面
* **scikit-learn**: 用于新闻聚类 (TF-IDF, DBSCAN)
* **LLM 集成**: 主要通过自定义的 Provider (`src/llm/providers/`) 与各大语言模型 API (包括 OpenAI, Ollama, Anthropic, Gemini等) 直接交互，以实现灵活控制和优化，目前集成稳定。
* **依赖注入**: 使用 `dependency-injector` (`src/containers.py`) 管理核心服务实例和依赖关系，以提高模块化和可测试性。详见 `docs/development/logic/00_overview_architecture.md`。
* **数据存储**: 核心数据（新闻、配置、历史等）使用 **SQLite 数据库** (`data/news_data.db`) 进行持久化，部分配置和缓存可能仍使用 JSON 文件。

### 分层架构 (v3)
项目采用清晰的分层架构，旨在提高模块化、可测试性和可维护性。主要分为：用户界面层、视图模型层、应用服务层、核心业务逻辑层和基础设施层。

*   **用户界面层 (UI - `src/ui`)**: 使用 PySide6 构建，负责用户交互和数据显示。
*   **视图模型层 (ViewModel - `src/ui/viewmodels`)**: 作为 UI 和核心服务之间的桥梁，处理 UI 事件，调用应用服务，并管理视图状态。
*   **应用服务层 (`AppService` - `src/core/app_service.py`)**:
    *   `AppService` 经过重构，现主要充当**高级协调器和部分 UI 状态的管理者**。它持有并协调其他核心服务的实例，负责部分应用级别的状态维护（如新闻缓存 `news_cache`，通过基于链接的精确去重逻辑确保其唯一性；以及当前选中项）和信号转发。
*   **核心业务逻辑层 (Core Services - `src/core/` 及 `src/services/`)**: 包含执行具体业务逻辑的独立服务，例如：
    *   `NewsUpdateService`: 负责新闻源的刷新和更新。
    *   `AnalysisService`: 负责调用 LLM 进行新闻分析。
    *   `HistoryService`: 负责管理已读状态和浏览历史。
    *   `LLMService`: 封装与 LLM API 的底层交互。
    *   `SchedulerService`: 管理后台定时任务（如自动刷新）。
    *   其他如 `SourceManager`, `EventAnalyzer`, `PromptManager` 等。
*   **基础设施层 (`src/storage`, `src/utils`, etc.)**: 提供底层支持，如数据持久化 (`NewsStorage` - 主要对接 SQLite)、API 客户端、日志等。

**详细的组件职责、交互图和数据流请参阅架构文档: `docs/development/logic/00_overview_architecture.md`**

### 关键依赖
项目依赖于多个 Python 库来提供其功能。主要依赖包括 (请参考 `requirements.txt` 获取完整和最新的列表):
* **UI**: PySide6
* **数据处理与科学计算**: scikit-learn
* **LLM API 交互**: openai, google-generativeai (或其他根据配置使用的库)
* **网络与解析**: requests, feedparser, beautifulsoup4, lxml
* **任务调度**: APScheduler
* **依赖注入**: dependency-injector
* **测试**: pytest, pytest-cov
* **配置**: python-dotenv (如使用 `.env` 文件), PySide6 (QSettings)
* *(可能需要的其他库，如数据库驱动 sqlite3 等)*

## 未来展望

为了进一步提升系统性能、可扩展性和数据处理能力，我们计划进行以下关键改进。这些改进将遵循"以测试驱动和保障的增量式重构与开发"的核心策略（详见 `docs/development_plan.md`），以确保在功能增强的同时，系统的稳定性和代码质量得到持续提升：

*   **数据存储与优化:** 项目核心数据已迁移至 SQLite 数据库 (`data/news_data.db`)，显著提升了数据操作效率。未来的工作将聚焦于数据库性能的持续优化（如索引、查询调整）和更复杂数据分析功能的支持。
*   **AppService 持续模块化:** 在数据层迁移的基础上，继续审视和分解 `AppService` 的剩余职责，将其进一步拆分为更专注的服务或管理器，以提高代码的可维护性和模块化程度。
*   **增强分析能力:** 探索更高级的 LLM 应用，例如跨文章的事实核查、多角度观点对比等。
*   **(可选) 平台化扩展:** 根据用户需求，未来可能探索将部分功能（如特定信息源监控与 RSS 生成）封装为独立的 Web 服务。

## 安装指南

1.  **克隆仓库:**
    ```bash
    git clone https://github.com/your-repo/news_analyzer.git # 请替换为实际仓库地址
    cd news_analyzer
    ```

2.  **创建虚拟环境 (推荐):**
    ```bash
    python -m venv .venv
    # Windows
    .\.venv\Scripts\activate
    # macOS/Linux
    source .venv/bin/activate
    ```

3.  **安装依赖:**
    *   **使用脚本 (Windows):** 双击运行 `一键依赖.bat` (如果可用且配置正确)。
    *   **手动安装:**
        ```bash
        pip install -r requirements.txt
        # 如果遇到网络问题，可以尝试使用国内镜像源:
        # pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
        ```
    * **注意:**
        * LLM 功能需要安装对应的库 (例如 `

## 3.1.4 对话框 (Dialogs - `src/ui/dialogs`)
各种独立的对话框窗口：
- `NewsDetailDialog`: 新闻详情页。
- `SettingsDialog`: 应用设置。
- `SourceManagerDialog`: 新闻源管理。
- `LLMSettingsDialog`: LLM 配置管理。负责管理多个语言模型的配置（如 API 端点、模型选择、温度等参数）。通过 ViewModel 驱动，能够显示 API 密钥的加载状态（例如，从环境变量或 .env 文件加载），并允许用户输入临时密钥以进行连接测试。
- `PromptManagerDialog`: Prompt 模板管理。
- `ImportExportDialog`: 导入导出新闻。
- `AboutDialog`: 关于应用。
- `ConfirmDialog`: 通用确认对话框。

## 3.1.5 历史记录管理 (History - `src/ui/browsing_history_panel.py`, `src/ui/viewmodels/browsing_history_viewmodel.py`)
统一的面板 (`BrowsingHistoryPanel`) 及对应的视图模型 (`BrowsingHistoryViewModel`) 用于管理用户操作历史。
- **浏览历史**: 已实现，允许用户查看和管理他们打开过的新闻文章记录。`BrowsingHistoryPanel` 通过 `BrowsingHistoryViewModel` 从 `HistoryService` 获取数据并响应更新。
- **分析历史**: (规划中) 将用于展示 LLM 对新闻进行分析的记录。

## 4. 核心服务 (`src/core`)

- 历史记录无法删除（ViewModel/Service 层尚未完全实现）。

### 已知问题与待办事项

- [✓] **澎湃新闻内容获取**: `PengpaiCollector` 已更新以应对不同页面布局（包括视频新闻），采用多选择器策略，并能解析多种时间格式。
- [ ] **部分 RSS 源不稳定**: 一些 RSS 源（如 BBC, WSJ, WP, NYT）或其中继服务（如 rsshub.app）可能出现临时性访问错误（HTTP 5xx）。
- [ ] **RDF Feed 解析**: Nature 和 Science 的 RDF 格式 Feed 可能无法完全解析。
- [ ] **完善历史记录功能**: 实现历史记录的删除功能。
- [ ] **UI 细节优化**: 调整 UI 布局、样式，增加用户反馈。
    - [ ] LLM配置界面在不同配置间切换时，UI布局可能仍有轻微抖动，需要进一步观察和优化。
- [ ] **错误处理**: 增强对网络错误、解析错误等的处理和用户提示。
- [ ] **持续进行代码健壮性改进和内部错误修复**: 提升应用稳定性。
- [ ] **测试覆盖**: 增加单元测试和集成测试覆盖率。
- [ ] **文档完善**: 持续更新开发文档和用户手册。

### 技术栈