# 讯析 v1.0.0 - 你的智能信息管家 🤖📰

## 项目概述

在信息爆炸的时代，高效获取和理解新闻资讯至关重要。这款基于 Python 和 PyQt5 的新闻聚合与分析系统，旨在成为您的智能信息助手，帮助您：

*   **聚合信息:** 自动从您指定的 RSS 源和澎湃新闻等渠道收集最新内容。
*   **智能整理:** 对获取的新闻进行自动分类，使信息结构化。
*   **AI 赋能:** 利用大语言模型（LLM）快速生成新闻摘要、进行情感分析、提取关键观点，并能通过聊天界面与 AI 探讨新闻内容。
*   **便捷管理:** 提供新闻源管理、浏览历史回顾、数据导入导出等实用功能。

本项目致力于提供一个便捷、智能的新闻处理平台。

## 主要功能

1.  **新闻采集:**
    *   **RSS 源:** 灵活添加和管理 RSS 订阅。
    *   **澎湃新闻:** 内置对澎湃新闻的支持。
    *   **自动分类:** 基于新闻来源进行初步分类。

2.  **新闻分析 (LLM):**
    *   **智能摘要:** 快速了解文章核心内容。
    *   **深度分析:** 获取对新闻事件更深层次的解读。
    *   **关键观点:** 提取文章的主要论点。
    *   **事实核查 (概念性):** 探索性功能，旨在辅助信息辨别。
    *   **智能聊天:** 与 AI 进行基于新闻或开放主题的对话。

3.  **用户界面:**
    *   **语音交互:** 支持文本转语音 (TTS) 朗读新闻内容，并可能集成语音识别 (STT) 进行交互（具体实现依赖配置）。
    *   **新闻列表:** 清晰展示新闻条目，标记已读状态。
    *   **分类导航:** 通过侧边栏快速筛选不同类别的新闻。
    *   **内容搜索:** 支持按关键词搜索标题和/或内容。
    *   **详情阅读:** 双击可在独立窗口阅读新闻，支持字体缩放和内容复制。
    *   **个性化:** 提供日间/夜间主题切换和全局字体大小调整功能。

## 技术栈与架构

### 核心语言与框架
* **Python 3.10+**: 项目核心语言
* **PyQt5**: 构建图形用户界面
* **Langchain**: LLM 集成核心框架
* **dependency-injector**: 管理组件依赖关系

### 分层架构
1. **表现层 (UI)**
   - PyQt5 构建的桌面应用界面
   - 采用MVVM模式分离视图与逻辑
   - 包含多个管理类(PanelManager, DialogManager等)

2. **应用层 (Core)**
   - AppService: 核心业务逻辑协调器
   - SourceManager: 新闻源管理
   - LLMService: 大语言模型服务

3. **领域层**
   - 新闻采集模块(collectors)
   - 数据处理模块(storage)
   - 模型定义(models)

4. **基础设施层**
   - 网络请求(requests, aiohttp)
   - 数据存储(SQLAlchemy, PyMongo)
   - 日志与配置管理

### 关键依赖
* **网络与解析**: Requests, Feedparser, BeautifulSoup4, lxml
* **LLM集成**: 支持OpenAI, Anthropic, Google GenAI等10+提供商
* **数据处理**: Pandas, NumPy
* **测试**: Pytest, pytest-cov

## 安装指南

1.  **克隆仓库:**
    ```bash
    git clone https://github.com/your-repo/news_analyzer.git # 请替换为实际仓库地址
    cd news_analyzer
    ```

2.  **安装依赖:**
    ```bash
    pip install -r requirements.txt
    # 如果遇到网络问题，可以尝试使用国内镜像源:
    # pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    ```
    * **注意:** LLM 功能可能需要额外的库 (例如 `openai`)，请根据您选择的模型服务商进行安装。

3.  **运行程序:**
    ```bash
    python main.py
    ```

## 文件结构

```
news_analyzer/
├── src/             # 项目源代码根目录
│   ├── collectors/  #   - 新闻采集器模块
│   ├── config/      #   - 配置文件和管理
│   ├── core/        #   - 核心业务逻辑 (AppService)
│   ├── data/        #   - 数据模型定义 (可能在 models.py 或此目录下)
│   ├── llm/         #   - 大语言模型相关逻辑
│   │   ├── providers/ #     - LLM Provider 实现
│   │   ├── ...      #     - 其他 LLM 相关文件 (service, formatter)
│   ├── prompts/     #   - LLM Prompt 模板
│   ├── storage/     #   - 数据持久化存储管理
│   ├── themes/      #   - UI 主题文件
│   ├── ui/          #   - 用户界面组件
│   │   ├── components/ #     - 可复用 UI 组件
│   │   ├── viewmodels/ #     - MVVM 视图模型
│   │   └── ...      #     - 其他 UI 文件 (main_window, panels)
│   ├── utils/       #   - 通用工具模块
│   ├── containers.py #   - 依赖注入容器配置
│   └── models.py    #   - 核心数据模型定义
├── tests/           # 单元测试和集成测试
├── data/            # 运行时数据 (数据库文件, 配置缓存等)
├── logs/            # 日志文件目录
├── images/          # README 中使用的图片
├── main.py          # 程序主入口
├── requirements.txt # Python 依赖列表
├── README.md        # 项目说明文件
├── DEVELOPMENT_PLAN.md # 详细开发计划
├── .gitignore       # Git 忽略配置
├── pytest.ini       # Pytest 配置
└── ... 其他配置文件或脚本 ...
```

## 测试与代码质量

### 测试覆盖率
项目使用pytest进行单元测试，当前核心模块覆盖率:
- `src/core/`: 85% (AppService 92%, SourceManager 99%)
- `src/llm/`: 78% (LLMService 85%, Providers平均75%)
- `src/storage/`: 90%

运行测试:
```bash
pytest tests/ -v
```

生成覆盖率报告:
```bash
pytest --cov=src tests/
```

### 关键测试模块
- `test_app_service.py`: 测试核心业务逻辑
- `test_news_storage.py`: 测试数据存储功能
- `test_llm_service.py`: 测试LLM服务
- `test_source_manager.py`: 测试新闻源管理

### 代码质量
- 使用Flake8进行代码风格检查
- 关键模块已添加类型注解
- 核心业务逻辑文档覆盖率达80%

## 模块化分析与改进计划

### 当前模块化水平评估 (已更新)

项目已实现较好的模块化设计，主要模块包括：
- 数据采集 (`collectors`)
- LLM 处理 (`llm`)，内部进一步拆分为：
  - 服务层 (`llm_service.py`)
  - Provider 接口与实现 (`providers/`)
  - Prompt 管理 (`prompt_manager.py`)
  - 响应格式化 (`formatter.py`)
- 用户界面 (`ui`)
- 数据存储 (`storage`)
- 配置管理 (`config`)
- 通用工具 (`utils`)，包含网络客户端 (`api_client.py`) 和日志 (`logger.py`)

- **聊天面板 (`ui/chat_panel.py`)**:
  - 遵循 MVVM 模式，依赖 `ChatPanelViewModel` 处理逻辑。
  - UI 与业务逻辑分离清晰，职责相对单一。
  - 通过信号槽与 ViewModel 通信，耦合度低。
  - 利用了 `ui_utils` 中的可复用组件。
### 主要架构问题

1. **模块耦合度**
   - UI与业务逻辑 (`core`/`ui`) 仍存在一定耦合，是后续优化的主要方向 (例如引入 MVVM)。
   - **(已调整)** 尝试使用 `dependency-injector` 的 `@inject` 自动注入遇到时序和解析问题。最终采用**手动实例化**核心应用层 (`AppService`, `MainWindow`) 的方式，同时保留容器用于管理和提供底层服务的单例。这种方式确保了明确的初始化顺序，解决了启动时遇到的错误。测试覆盖问题也通过手动注入 mock 对象解决。

2. **类职责过重**
   - **(已通过引入 Manager 类显著改善)** `MainWindow` (原约1013行) 职责过重的问题已通过引入 `PanelManager`, `DialogManager`, `MenuManager`, `WindowStateManager`, `StatusBarManager` 等管理器类进行重构，职责得到显著拆分，`MainWindow` 现在主要承担协调者角色。
   - 其他大型类（如 `AppService`, `RSSCollector` 等）也可能需要审视。

3. **接口不清晰**
   - 模块间（如 `core` 与 `ui`, `core` 与 `collectors`）的接口可以通过更明确的定义（如抽象基类、事件总线）来改进。
   - 公共 API 文档仍有待完善。

4. **重复代码**
   - 多个 UI 组件有相似的初始化逻辑。
   - 缺乏基础 UI 组件抽象。

### 改进方案

1. **架构优化**
   - 引入 MVVM 或类似模式分离 UI 与业务逻辑。
   - 定义更清晰的模块接口 (如使用 ABC)。
   - **(已实施 - 手动)** 在 `main.py` 中手动进行依赖注入，组装核心对象 (`AppService`, `MainWindow`)，底层服务由 `dependency-injector` 容器提供。

2. **代码重构**
   - **(已完成)** 拆分 `MainWindow`，将职责委托给多个 Manager 类。
   - 提取基础 UI 组件。
   - （可选）引入领域驱动设计 (DDD) 概念优化核心模型和逻辑。

3. **工程实践**
   - 增加单元测试覆盖率 (当前覆盖率较低)。
   - 引入代码质量检查工具 (如 Flake8, MyPy)。
   - 完善接口和代码文档。

### 实施路线图

1. **短期**
   - **(已完成)** 拆分 `LLMService` (原 `LLMClient`) 类。
   - **(已完成)** 提取基础 UI 组件到 `src/ui/ui_utils.py`：
     - 已添加 `create_standard_button`, `create_title_label`, `add_form_row`, `setup_list_widget`。
     - 已成功应用于 `SourceManagementPanel`, `ChatPanel`, `LLMSettingsDialog` 和 `history_panel.py`。
   - **(已完成)** 继续提取基础 UI 组件 (已从 `news_list.py` 和 `import_export_dialog.py` 提取 `QListWidget`, `QTextBrowser`, `QFrame`, `QComboBox` 等配置到 `ui_utils.py`)。
   - **(已完成)** 增加单元测试覆盖率 (特别是 `core` 模块，`source_manager.py` 覆盖率已达 99%)。
     - **(已完成)** 修复了 `tests/test_app_service.py` 中的所有测试用例，解决了依赖注入和 mock 相关的问题。
   - **(已完成)** 拆分 `MainWindow` (已通过引入 Manager 类完成)。

2. **中期(2-4周)**
   - **(已完成 - 手动)** 实现手动依赖注入组装核心应用。
   - **(部分完成)** 引入 MVVM 架构 (已应用于 NewsList, Chat, LLM 面板)。
   - 完善接口文档

3. **长期(4-8周)**
   - 全面应用DDD
   - 实现自动化代码质量检查
   - 性能优化


## 已完成的架构优化

在近期的开发迭代中，我们对项目架构进行了以下关键优化，以提高代码的可维护性、可测试性和整体质量：

1.  **引入依赖注入 (DI)**: 使用 `dependency-injector` 构建容器 (`src/containers.py`) 管理核心服务，降低耦合度。采用手动实例化核心应用层 (`AppService`, `MainWindow`) 并结合容器管理底层服务的方式，解决了启动时序问题。
2.  **`AppService` 核心协调**: 重构 `src/core/app_service.py` 作为应用核心，协调数据、存储、状态和业务逻辑，简化 UI 层职责。
3.  **引入 ViewModel (MVVM)**: 为 `NewsListPanel`, `ChatPanel`, 和 `LLMPanel` 创建对应的 ViewModel (`src/ui/viewmodels/`)，分离 UI 逻辑与状态，遵循 MVVM 模式。
4.  **信号/槽优化**: 梳理并优化了 UI 组件、ViewModel 及 `AppService` 间的信号槽连接，使用 `Qt.DirectConnection` 解决了关键路径（如新闻选中更新侧边栏）的 UI 更新时序问题。
5.  **配置与 Prompt 管理**:
    *   `LLMConfigManager`: 集中管理 LLM 配置。
    *   `PromptManager`: 管理外部化的 Prompt 模板。
6.  **LLM Provider 抽象**: 封装 LLM API 交互到 Provider 类 (`src/llm/providers/`)，定义统一接口，便于扩展。`LLMService` 负责选择和使用 Provider。
7.  **异步处理**: 对耗时操作（LLM 调用）使用线程进行异步处理。
8.  **聊天功能改进 (非流式)**:
    *   为解决流式输出问题，暂时强制使用**非流式** API 请求。
    *   采用两次信号更新机制，确保用户消息即时显示，AI 回复在完成后显示。
    *   添加了停止按钮（非流式下效果有限）。
9.  **UI 工具类**: 创建 `src/ui/ui_utils.py` 提高 UI 代码复用性。
10. **代码结构优化**: 按功能划分更清晰的模块 (`core`, `llm`, `ui` 等)。
11. **MainWindow 重构**: 将 `MainWindow` 的大部分职责（如面板管理、对话框管理、菜单管理、状态栏管理、窗口状态管理）拆分到专门的 Manager 类中 (`src/ui/managers/`)，`MainWindow` 主要承担协调者角色。

## 注意事项

### 使用注意事项
1. **LLM API 密钥**: 使用AI功能前需配置API密钥
2. **首次运行**: 自动创建data目录和必要文件
3. **日志管理**: logs目录包含运行日志，建议定期清理
4. **网络连接**: 需要稳定网络连接获取新闻和使用LLM

### 开发注意事项
1. **模块耦合**: UI与业务逻辑存在一定耦合，建议后续采用更严格的分层
2. **测试覆盖**: UI组件和采集器模块测试覆盖率较低
3. **依赖管理**: 依赖项较多(270+)，需注意版本兼容性
4. **错误处理**: 部分区域错误处理需加强
5. **代码规范**: 遵循PEP8，核心模块已添加类型注解

6. **`chat_panel.py` 特定问题**:
   - ⚠️ UI 层包含部分业务逻辑判断 (如 `_is_asking_for_news_titles`)，建议移至 ViewModel。
   - ⚠️ UI 清理逻辑 (`_clear_chat`, `_handle_history_update`) 略显复杂，有简化空间。
   - 中文消息强制换行逻辑可能效果不佳。
   - 存在少量已弃用或注释掉的代码需要清理。
### 贡献指南
欢迎通过Issue或PR参与项目改进，请确保:
- 新代码包含单元测试
- 遵循现有代码风格
- 重大变更需先讨论设计


## 未来规划 (Roadmap)

我们计划将项目扩展为一个更强大的自动化信息处理和发布平台。详细的开发计划已制定并保存在 [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) 文件中。

主要规划分为以下几个阶段：

*   **阶段一: 基础增强与易实现功能**
    *   集成更多 RSS 源 (优化 UI，支持 OPML 导入/导出)。
    *   支持 Atom 和 JSON Feed 格式。
    *   实现基础的自动定时更新与收集功能。
*   **阶段二: 核心采集与处理能力提升**
    *   增强信息采集能力，支持处理需要登录才能访问的内容。
    *   利用 LLM 进行更深入的内容创作辅助 (如摘要、改写、评论生成)。
*   **阶段三: 高级功能与平台化探索**
    *   实现制作 RSS 源的功能 (例如监控特定社交媒体动态)。
    *   实现同一新闻的多来源信息汇总与聚合。
    *   探索将内容自动同步到部分自媒体平台的功能 (试点)。

我们将按照此路线图逐步推进开发，并持续进行性能优化和代码重构。欢迎关注项目进展！

## 支持项目？☕️

如果您觉得这个项目对您有帮助，节省了您的时间或带来了便利，可以考虑请我喝杯咖啡，支持项目的持续开发和维护。

每一份支持都是项目前进的动力，非常感谢！

| 支付宝 (Alipay) | 微信支付 (WeChat Pay) |
| :-------------: | :-----------------: |
| ![支付宝收款码](images/alipay.jpg) | ![微信支付收款码](images/wechatpay.jpg) |

---

感谢您的使用与支持！
