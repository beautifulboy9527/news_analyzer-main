# 新闻聚合与分析系统开发规范

## 1. 代码规范

### 1.1 通用规范
- 所有代码必须遵循PEP 8规范
- 使用有意义的变量名和函数名
- 保持一致的代码缩进（使用4个空格）
- 每行代码不超过120个字符
- 在适当的地方添加中文注释，解释复杂逻辑

### 1.2 后端规范 (Python)
- 使用类型注解（Type Hints）
- 遵循SOLID原则
- 使用依赖注入进行组件管理 *(注意: 当前 AppService/MainWindow 中手动实例化较多，此为目标状态或需调整规则)*
- 错误处理必须使用try-except块
- 日志记录必须使用logging模块
- 配置文件使用.env文件管理 *(并结合 QSettings 用于 UI/源配置)*
- 数据库操作必须使用事务 *(如果使用数据库)*
- API接口必须包含参数验证

### 1.3 前端规范
- 使用语义化HTML标签
- CSS类名使用BEM命名规范
- JavaScript代码必须使用严格模式
- 使用ES6+语法特性
- 组件化开发，保持单一职责
- 响应式设计，适配不同设备

## 2. 项目结构规范

### 2.1 目录结构
```
project_root/
├── src/                # 源代码目录
│   ├── core/           # 核心业务逻辑 (AppService, NewsClusterer等)
│   ├── ui/             # 用户界面代码
│   │   ├── components/   #   - 可复用UI组件
│   │   ├── managers/     #   - UI 管理器 (除Theme/Settings外)
│   │   ├── viewmodels/   #   - 视图模型
│   │   ├── themes/       #   - QSS 主题文件
│   │   └── ...           #   - 其他UI面板/对话框/管理器 (如ThemeManager)
│   ├── collectors/     #   - 新闻源数据收集器
│   ├── config/         #   - 应用配置管理 (LLMConfigManager等)
│   ├── data/           #   - 运行时数据目录 (由Storage管理)
│   ├── llm/            #   - LLM 相关服务/配置/提示/Providers
│   ├── storage/        #   - 数据存储逻辑 (NewsStorage)
│   ├── utils/          #   - 通用工具函数
│   ├── models.py       #   - 核心数据模型
│   └── containers.py   #   - (如果使用) 依赖注入容器
├── tests/              # 测试代码
├── data/               # (此处的 data/ 目录通常由 NewsStorage 内部创建和使用)
├── logs/               # 日志文件
├── docs/               # 文档 (包括 development/, memory_bank/)
├── drivers/            # WebDriver (如果需要)
├── .cursor/            # Cursor IDE 配置/规则
├── .vscode/            # VS Code 配置 (如果使用)
├── main.py             # 主入口
├── requirements.txt    # 依赖列表
├── README.md           # 项目说明
├── .gitignore          # Git 忽略配置
└── pytest.ini          # Pytest 配置
```

### 2.2 文件命名
- Python文件使用小写字母和下划线
- 类文件首字母大写
- 测试文件以test_开头
- 配置文件以config_开头 *(注: QSettings 使用内部 key, .env 文件通常为 `.env`)*

## 3. 开发流程规范

### 3.1 版本控制
- 使用Git进行版本控制
- 遵循Git Flow工作流 *(或团队商定的其他流程, 如 GitHub Flow)*
- 提交信息必须清晰描述改动
- 禁止直接提交到main分支 *(或 master/开发主分支)*

### 3.2 代码审查
- 所有代码必须经过代码审查
- 使用Pull Request进行代码合并
- 确保代码符合规范
- 测试覆盖率必须达到80%以上 *(或团队商定的目标)*

### 3.3 测试规范
- 单元测试必须覆盖核心功能
- 使用pytest进行测试
- 测试文件必须放在tests目录
- 测试用例必须包含边界条件

### 3.4 测试驱动开发与信号/Mock最佳实践

- **信号测试**：
  - 推荐使用 `pytest-qt` 的 `qtbot.waitSignal` 监听信号发射，避免直接 patch/mocking Qt 信号的 `emit` 方法（该属性只读，patch 会报错）。
  - 用 `qtbot.waitSignal` 可断言信号是否发射、参数是否正确，适用于 PySide6/PyQt5。
- **Mock 依赖**：
  - mock 时要与被测对象实际依赖的接口/方法名保持一致（如 storage.is_item_read、add_read_item 等），否则断言无效。
  - 优先 mock 外部依赖（如存储、网络、服务），保持测试隔离。
- **TDD 流程建议**：
  - 新功能/重构前先写或同步写测试用例，覆盖核心逻辑、边界条件和异常分支。
  - 重构时先保证原有测试通过，再逐步调整实现，持续运行测试确保行为一致。
  - 复杂逻辑建议分步提交，每步都伴随测试。
- **特殊场景注意**：
  - PySide6 信号不可 patch emit，必须用监听法。
  - 异步/多线程场景下，优先用 pytest-qt、pytest-asyncio 等工具。
  - 依赖注入场景，建议通过 fixture/mocker 注入 mock 实例，提升可测性。

### 3.5 实战经验补充：信号链测试、Mock依赖与边界健壮性

- **信号链测试**：
  - 推荐用 `pytest-qt` 的 `qtbot.waitSignal` 监听信号发射，断言参数是否正确。
  - 对于"服务层信号→ViewModel信号→UI"链路，建议在测试用例中手动触发 service 的信号，再断言 ViewModel 是否正确转发。
  - 多次信号发射时，建议分别监听并断言参数隔离，防止串扰。
  - 典型案例：AnalysisViewModel 测试中，手动触发 analysis_service 的信号，断言 ViewModel 的 analysis_completed/failed 信号参数。

- **Mock依赖**：
  - Mock 时要与被测对象实际依赖的接口/方法名保持一致，否则断言无效。
  - 优先 mock 外部依赖（如存储、网络、服务），保持测试隔离。
  - 对于依赖信号的 service，mock 时可用 MagicMock() 代替信号属性，或自定义 DummyService。
  - 典型案例：BrowsingHistoryViewModel、AnalysisViewModel 测试均通过 fixture 注入 mock service，保证测试可控。

- **边界与健壮性测试**：
  - 建议覆盖 service 为 None、信号属性缺失、参数为 None/空/非法类型等场景，确保 ViewModel 不抛异常。
  - 连续多次请求、异常分支、极端参数等均应测试。
  - 典型案例：AnalysisViewModel 测试补充了 service 为 None、无信号属性、参数为 None/空/未知类型等边界用例。

- **实战建议**：
  - 复杂信号链建议画时序图/流程图，便于团队理解和测试设计。
  - 测试用例应含中文注释，说明测试目的和关键断言。
  - 所有新功能/重构建议先写或同步写测试，重构时先保证原有测试通过。

### 3.6 实战经验补充：QSettings mock、无效参数校验与异常保护

- **QSettings mock**：
  - 单元测试涉及 QSettings 时，推荐用 monkeypatch 或自定义 DummySettings 替换 QSettings，避免真实写入注册表/磁盘，保证测试隔离与可控。
  - 典型用法：pytest fixture 中 monkeypatch.setattr('src.core.source_manager.QSettings', lambda *a, **k: DummySettings())。
  - 适用于 SourceManager、配置管理等依赖 QSettings 的模块测试。

- **无效参数校验**：
  - 业务核心方法（如 add_source）应对关键参数（如 RSS 源 URL）做非空/格式校验，发现无效参数时及时抛出 ValueError，防止脏数据进入系统。
  - 建议在接口入口处校验，便于定位和维护。
  - 典型用法：SourceManager.add_source 检查 type='rss' 且 url 为空时抛异常。

- **异常保护**：
  - 配置加载、外部依赖等高风险操作建议用 try/except 包裹，捕获异常后记录日志并保证系统可用（如初始化不抛出致命异常，内部状态置空并发信号）。
  - 典型用法：SourceManager._load_sources_config 外层 try/except，QSettings 读取异常时不影响主流程。

- **实战建议**：
  - 关键依赖（如 QSettings、数据库等）mock 后要覆盖边界和异常分支，提升测试覆盖率。
  - 校验与异常保护逻辑建议同步补充单元测试，确保健壮性。
  - 相关经验可沉淀到团队测试/开发规范文档，便于新成员快速上手。

### 3.7 集成测试设计、Mock与信号链实战经验

- **集成测试设计原则**：
  - 集成测试应覆盖主业务流程（如"添加源-采集-分析-历史记录"），验证各模块协作、信号链路和数据流。
  - 推荐以"用户视角"设计典型场景，兼顾主流程与异常分支。
  - 可采用 pytest+qtbot，模拟信号链路和用户操作。

- **Mock/Fake 依赖技巧**：
  - 集成测试中可用 Fake/Mock Service、ViewModel 替代真实依赖，聚焦流程链路和信号交互。
  - Fake 组件应实现核心信号和最小业务逻辑，便于灵活组合和扩展。
  - 典型用法：FakeSourceManager、FakeNewsListViewModel、FakeAnalysisService、FakeHistoryService。

- **信号链路断言方法**：
  - 用 qtbot.waitSignal 监听信号发射，断言参数和时序。
  - 复杂链路可通过 connect 回调自动触发下游操作（如分析完成后自动写入历史）。
  - 异常分支可用 pytest.raises 或 try/except 断言。

- **典型集成测试案例**：
  - 主流程：添加源→采集新闻→分析→写入历史，逐步断言信号和数据。
  - 扩展场景：新闻已读状态变更、多源采集去重、分析历史同步、采集/分析异常等。
  - 所有用例均含中文注释，便于团队理解和维护。

- **实战建议**：
  - 集成测试应与单元测试互补，重点覆盖跨模块协作和信号链。
  - 推荐将集成测试经验、典型用例和信号链路图沉淀到 docs，便于团队复用和新成员快速理解。

## 4. 文档规范

### 4.1 代码文档
- 所有公共API必须包含文档字符串
- 使用Google风格的文档字符串
- 复杂算法必须包含详细注释
- 配置项必须说明用途

### 4.2 项目文档
- README必须包含项目说明
- 必须包含安装和运行说明
- API文档必须及时更新 *(包括内部服务接口)*
- 变更日志必须记录重要更新
- *核心逻辑文档 (`docs/development/logic/`) 需与代码保持同步 (参考 `.cursor/rules/documentation_sync.md`)*

## 5. 安全规范

### 5.1 数据安全
- 敏感信息必须加密存储 *(例如 LLM API Keys)*
- 禁止硬编码密钥
- 使用环境变量管理配置 *(或安全的配置管理机制，结合 QSettings 的使用场景)*
- 定期备份重要数据 *(如 `data/` 目录)*

### 5.2 代码安全
- 输入数据必须验证 *(UI 输入、API 响应等)*
- 防止SQL注入 *(如果使用数据库)*
- 防止XSS攻击 *(如果渲染 HTML 内容)*
- 使用HTTPS传输数据 *(与外部 API 通信时)*

## 6. 性能规范

### 6.1 后端性能
- 数据库查询必须优化 *(如果使用数据库)*
- 使用缓存减少重复计算 *(考虑新闻缓存、LLM 结果缓存等)*
- 异步处理耗时操作 *(如新闻刷新、LLM 调用)*
- 监控系统资源使用

### 6.2 前端性能
- 减少HTTP请求 *(主要针对与 LLM/外部 API 的交互)*
- 压缩静态资源 *(QSS, 图标等)*
- 使用CDN加速 *(不适用于桌面应用)*
- 优化页面加载速度 *(应用启动速度、面板切换流畅度)*

## 7. 错误处理

### 7.1 异常处理
- 使用自定义异常类
- 记录详细的错误信息 (`logging` 模块)
- 提供友好的错误提示 (UI层面, `QMessageBox`)
- 实现优雅的降级策略 *(例如 LLM 服务不可用时的处理)*

### 7.2 日志记录
- 使用不同级别的日志 (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- 记录关键操作信息、错误堆栈
- 定期归档日志文件 *(或使用日志轮转)*
- 监控异常日志

## 8. 部署规范
*(对于桌面应用，主要关注打包和分发)*

### 8.1 环境配置
- 使用虚拟环境 (`venv`)
- 配置文件区分环境 *(如果需要测试/生产不同配置)*
- 自动化部署脚本 *(打包脚本, e.g., using PyInstaller, cx_Freeze)*
- 监控部署状态 *(打包过程日志)*

### 8.2 发布流程
- 版本号遵循语义化版本 (`MAJOR.MINOR.PATCH`)
- 更新变更日志 (`CHANGELOG.md`?)
- 进行回归测试
- 备份重要数据 