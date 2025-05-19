# 03 - LLM 交互逻辑

## 1. 核心组件

*(基于代码分析)*

- **`AppService`**: (当前) 接收来自 UI 的 LLM 请求 (分析、聊天)，调用 `LLMService`，并将结果通过信号传递回 UI。
- **`LLMService`**: 核心服务，封装与 LLM API 的交互。
    - 管理活跃的 LLM Provider 实例 (实现了 `LLMProviderInterface`)。
    - 使用 `ApiClient` 发送 HTTP 请求。
    - 处理普通和流式响应。所有已知的与 Ollama 的集成问题（如错误的端点、方法调用、参数错误、重复消息、格式问题）均已修复，Ollama 现在可以正常用于聊天和分析。
    - 提供 `analyze_news`, `chat`, `test_connection` 等方法。
- **`LLMConfigManager`**: 管理不同 LLM Provider 的配置 (API Key, Base URL, Model Name, temperature 等)，可能存储在 `.env` 或 `QSettings` (通过 NewsAnalyzer/NewsAggregator 应用程序名)。
- **`PromptManager`**: 加载和格式化存储在文件 (`src/prompts/`) 中的 Prompt 模板。
- **`LLM Providers` (`src/llm/providers/*.py`)**: 具体 Provider 实现 (e.g., `OpenAIProvider`, `OllamaProvider`, `AnthropicProvider`, `GeminiProvider`)，均已更新以符合 `LLMProviderInterface` 的最新定义 (例如，实现了 `process_stream_line` 方法替代了旧的 `parse_stream_chunk`)。它们负责构造特定 API 的请求头/体，解析响应。
- **`ApiClient` (`src/utils/api_client.py`)**: 通用的 HTTP 请求客户端，被 `LLMService` 使用。
- **`EventAnalyzer`**: *仍然需要确认其具体实现*，推测是使用 `LLMService` 对聚类事件进行多维度分析。
- **UI 面板 (`LLMPanel`, `ChatPanel`, `ClassificationPanel`)**: 用户交互界面，调用 `AppService` 发起 LLM 请求，连接信号以展示结果。

## 2. 主要流程

*(基于 `LLMService`, `AppService`, `PromptManager` 等的代码分析)*

1.  **初始化**: `LLMService` 在初始化时：
    -   从 `LLMConfigManager` 加载活动配置。
    -   根据配置名称或 URL 确定 Provider 类型。
    -   实例化对应的 Provider (`OpenAIProvider`, `OllamaProvider` 等)。
2.  **单篇文章分析 (`LLMPanel` -> `AppService` -> `LLMService.analyze_news`):**
    1.  UI (`LLMPanel`) 触发分析，调用 `AppService` 的某个方法 (例如 `perform_llm_action`)，传递 `NewsArticle` 对象和分析类型 (e.g., '摘要')。
    2.  `AppService` 调用 `LLMService.analyze_news(news_item, analysis_type)`。
    3.  `LLMService`:
        -   检查 Provider 是否已配置 (`self.provider is not None`)。
        -   将 `news_item` (可能是对象) 转换为字典。
        -   调用 `self.prompt_manager.get_formatted_prompt()` 获取针对该 `analysis_type` 和 `news_item` 数据的最终 Prompt 字符串。
        -   调用 `self.provider.prepare_request_payload()` 准备 API 请求体 (通常包含 `messages` 列表)。
        -   调用 `self.provider.get_headers()` 获取 API 请求头。
        -   调用 `self.api_client.post()` 发送请求到 `self.provider.api_url`。
        -   调用 `self.provider.parse_response()` 解析 API 返回的 JSON 数据，提取主要内容。
        -   使用 `LLMResponseFormatter.format_analysis_result()` 格式化结果 (可能为 HTML)。
        -   返回包含格式化结果的字典 `{'analysis': result}`。
    4.  `AppService` 接收到结果，通过信号 (例如 `analysis_completed`) 将结果传递回 `LLMPanel` (或其 `ViewModel`) 进行显示。
3.  **事件分析 (`ClassificationPanel` -> `AppService` -> `EventAnalyzer` -> `LLMService`):**
    1.  *推测流程 (需代码确认)*: `ClassificationPanel` 触发对某个事件的分析。
    2.  调用 `AppService` 的方法，传递事件数据和分析维度。
    3.  `AppService` 调用 `EventAnalyzer.analyze()`。
    4.  `EventAnalyzer` 根据分析维度和事件数据，调用 `PromptManager` 获取模板，构建最终 Prompt。
    5.  `EventAnalyzer` 调用 `LLMService` 的某个分析方法 (可能是 `analyze_with_prompt` 或类似的)。
    6.  `LLMService` 执行类似单篇分析的流程 (获取 Prompt, 准备请求, 调用 API, 解析响应)。
    7.  结果通过 `EventAnalyzer` -> `AppService` -> 信号 -> `ClassificationPanel` 返回。
4.  **聊天 (`ChatPanel` -> `AppService` -> `LLMService.chat`):**
    1.  `ChatPanel` 发送用户消息，调用 `AppService.send_chat_message()`，可能附带上下文和历史消息。
    2.  `AppService` 调用 `LLMService.chat(messages, context, stream=True, callback=...)`。
    3.  `LLMService`:
        -   将输入的 `ChatMessage` 对象 (如果需要) 转换为 API 需要的字典格式 (`{'role': ..., 'content': ...}`)。
        -   如果 `stream=True`:
            -   启动一个新线程 (`_stream_chat_response_thread_target`)。
            -   在该线程中，调用 `self.provider.prepare_request_payload()` 准备请求，然后通过 `self.api_client.stream_post()` （或类似流式请求方法）调用 Provider 的聊天生成 URL (例如 Ollama 的 `/api/chat`)。
            -   该流式方法会迭代接收来自 API 的数据块。
            -   对每个数据块调用 `self.provider.process_stream_line()` 解析，该方法返回处理后的文本块和是否为最终块的标志。
            -   通过传入的 `callback` 函数 (连接到 `LLMService` 的 `chat_chunk_received` 和 `chat_finished` 信号)，实时将解析出的文本块或完整消息传递回调用者 (`AppService` -> `ChatPanelViewModel`)。
            -   包含停止机制 (`self._cancel_requested`)。
        -   如果 `stream=False`:
            -   调用 `_send_chat_request()`。
            -   准备请求体，使用 `self.api_client.post()` 发送请求。
            -   调用 `self.provider.parse_response()` 解析完整响应。
            -   返回完整的响应字符串。
    4.  `AppService`:
        -   (流式) 将 `callback` 连接到 UI 更新槽位，或者通过 `chat_response_received` 信号传递接收到的文本块。
        -   (非流式) 通过信号传递完整的响应。

## 3. Prompt 管理 (增强型)

*(基于 `PromptManager`, `PromptManagerService`, `PromptTemplateManager` Dialog 的分析)*

当前的提示词管理系统经过了显著增强，涉及以下几个核心组件和流程：

### 3.1. `PromptManager` (`src/llm/prompt_manager.py`) - 核心逻辑层

-   **职责**: 负责提示词模板文件和元数据的底层存储与操作。
-   **模板文件**: 提示词内容存储在 `src/prompts/` 目录下的 `.txt` 文件中。
-   **元数据**: 
    -   关键元数据（如模板分类、已定义的分类列表）存储在 `src/prompts/prompts_metadata.json` 文件中。
    -   该 JSON 文件包含两个主要键：
        -   `_templates`: 一个字典，键为模板文件名 (e.g., `my_prompt.txt`)，值为其所属的分类名称 (字符串) 或 `None` (未分类)。
        -   `_defined_categories`: 一个列表，存储用户显式定义的所有分类名称。
-   **主要功能**:
    -   加载和保存单个模板文件的内容。
    -   加载和保存 `prompts_metadata.json` 文件。
    -   获取/设置指定模板的分类信息（读写元数据）。
    -   管理已定义的分类列表（添加、删除、重命名分类，并更新元数据）。
    -   列出所有模板文件名。
    -   获取所有唯一的分类名称（合并来自 `_defined_categories` 和 `_templates` 中实际使用的分类）。
    -   提供 `get_formatted_prompt(template_name, data_dict)` 方法：根据模板名称加载其内容，并使用 `data_dict` 中的值替换模板中的占位符 (e.g., `{title}`, `{content}`), 返回最终的 Prompt 字符串。此方法被 `LLMService` 等调用。

### 3.2. `PromptManagerService` (`src/ui/managers/prompt_manager.py`) - 服务层 (UI与核心逻辑的桥梁)

-   **职责**: 作为 UI (`PromptTemplateManager` 对话框) 和核心逻辑 (`PromptManager`) 之间的中介。
-   **封装操作**: 向 UI 层暴露更高级别的、面向用户任务的操作。
-   **主要功能**:
    -   获取所有模板名称列表。
    -   获取特定模板的详细信息（内容和当前分类）。
    -   保存模板（包括内容和分类）：调用 `PromptManager` 保存模板文件内容，并更新元数据中的分类信息。
    -   删除模板：调用 `PromptManager` 删除模板文件及其在元数据中的条目。
    -   管理（添加、重命名、删除）已定义的分类：调用 `PromptManager` 中对应的分类管理方法。
    -   获取所有已定义的分类名称列表，供 UI 显示。
-   **信号**: 当提示词或分类数据发生变更时，会发射信号 (e.g., `templates_updated`)，通知 UI 层刷新视图。

### 3.3. `PromptTemplateManager` 对话框 (`src/ui/managers/prompt_template_manager.py`) - 用户界面

-   **职责**: 提供用户友好的图形界面，用于管理提示词模板和分类。
-   **主要特性与功能**:
    -   **模板列表 (`QListWidget`)**: 
        -   以可视化的方式按分类对模板进行分组显示（每个分类有非可选的标题项）。
        -   未分类的模板显示在特定的 "<无分类>" 组下。
    -   **搜索/筛选**: 用户可以输入文本以筛选模板列表。
    -   **模板操作**:
        -   **添加**: 通过 `AddTemplateDialog` 对话框添加新模板，允许用户在创建时指定模板名称和初始分类。
        -   **编辑**: 在文本编辑区域修改选中模板的内容。
        -   **分类指派**: 使用下拉框 (`QComboBox`) 为当前选中的模板选择或更改分类。
        -   **保存**: 保存对模板内容或分类的修改。
        -   **删除**: 删除选中的模板。
        -   **移动到分类**: 通过右键上下文菜单，快速将模板移动到其他分类。
    -   **分类管理**: 
        -   通过 "管理分类" 按钮打开 `CategoryManagementDialog` 对话框。
        -   在 `CategoryManagementDialog` 中，用户可以添加新的分类、重命名现有分类或删除分类。
        -   **占位符插入**: 提供按钮，方便用户将常用的占位符 (e.g., `{title}`, `{content}`) 点击插入到模板内容编辑器中。
-   **交互逻辑**: 该对话框的所有操作都通过调用 `PromptManagerService` 的方法来完成。

### 3.4. 与 LLMService 的交互

-   `LLMService` 在需要构建特定任务的 Prompt 时 (例如在 `analyze_news` 方法中)，会调用 `PromptManager` 的 `get_formatted_prompt(template_name, data_dict)` 方法。
-   `template_name` 通常由 `LLMService` 根据当前的分析类型 (`analysis_type`) 决定 (可能通过一个映射关系)，或者直接指定。
-   `data_dict` 包含了需要填充到模板中的动态数据 (如新闻文章的标题、内容等)。

*(原有对 analyze_with_custom_prompt 的描述可以保留，因为它代表了不经过模板管理器的直接 Prompt 使用方式)*
-   系统也支持直接使用自定义 Prompt 字符串 (`analyze_with_custom_prompt` 等流程)，这种情况下不直接涉及 `PromptManager` 对模板文件的加载，但 `LLMService` 仍会处理该自定义字符串以与 Provider 交互。

## 4. LLM 配置 (`LLMConfigManager`)

*(基于 `LLMConfigManager`, `LLMSettingsViewModel`, 和 `LLMService` 调用分析)*

-   `LLMConfigManager` 负责加载、保存和管理多个 LLM Provider 的配置。它与 `LLMSettingsViewModel` 紧密协作，后者驱动 `LLMSettingsDialog` UI，允许用户查看、创建、修改、删除、激活和测试这些配置。
-   配置项包括: `api_key`, `api_url`, `model`, `temperature`, `max_tokens`, `timeout`, `provider` (类型)等。
-   `LLMConfigManager` 提供方法如：
    -   `get_config_names()`: 获取所有配置的名称列表。
    -   `get_config(name)`: 获取指定名称的详细配置 (字典)。
    -   `add_or_update_config(name, config_data)`: 添加新配置或更新现有配置。
    -   `delete_config(name)`: 删除指定名称的配置。
    -   `get_active_config_name()`: 获取当前激活的 Provider 名称。
    -   `set_active_config_name(name)`: 设置活动配置，并返回操作是否成功 (布尔值)。
    -   `get_active_config()`: 获取当前激活的 Provider 详细配置。
-   `LLMSettingsViewModel` 调用这些方法来响应用户在 `LLMSettingsDialog` 中的操作。例如，当用户点击"保存"时，ViewModel 会调用 `add_or_update_config`；点击"激活"时，会调用 `set_active_config_name`，并根据返回结果更新UI和通知 `LLMService.reload_active_config()`。
-   配置的持久化通过 `QSettings` 完成。
-   `LLMService` 在初始化时以及活动配置发生变化时（通过 `reload_active_config` 方法，该方法由 `LLMSettingsViewModel` 在成功激活配置后调用），会从 `LLMConfigManager` 获取最新的活动配置来实例化和配置其内部的 `LLMProviderInterface`。

## 5. Token 计数

-   Token 计数逻辑在 `LLMService` 的代码片段中未明确体现。
-   推测 Token 计数可能在具体的 `Provider` 实现中处理，或者通过解析 API 返回的 `usage` 字段 (如果 API 提供的话)。
-   `AppService` 有一个 `token_usage_updated` 信号，表明 Token 计数信息最终会传递到应用层面，但具体计算位置需进一步探查 Provider 代码。 