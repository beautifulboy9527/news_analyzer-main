# 05 - UI 组件与数据流: SourceManagementPanel

本文档描述 `SourceManagementPanel` (新闻源管理面板) UI 组件如何与后端服务（特别是 `AppService`，后者代理 `SourceManager`）交互，以实现新闻源的查看、添加、编辑和删除功能。重点关注数据如何在UI和存储之间流动，尤其是在 SQLite 数据库迁移之后。

## 1. 概述

`SourceManagementPanel` 是一个 `QDialog`，允许用户管理应用程序的新闻源。它通过 `AppService` 实例与核心逻辑层通信。所有新闻源数据最终都通过 `NewsStorage` 持久化到 SQLite 数据库的 `news_sources` 表中。

**核心交互流程**: UI 操作 -> `SourceManagementPanel` 方法 -> `AppService` 方法 -> `SourceManager` 方法 -> `NewsStorage` 方法 -> SQLite DB.

## 2. 组件初始化与数据加载

-   **实例化**: `DialogManager` 负责创建 `SourceManagementPanel` 实例，并将 `AppService` 和 `ThemeManager` 实例注入其构造函数。`SourceManagementPanel` 的 `__init__` 方法因此会接收 `app_service` 和 `theme_manager` 作为参数。
-   **初始加载**:
    1.  `SourceManagementPanel.__init__` 调用 `self.update_sources()`。
    2.  `update_sources()` 方法调用 `self.app_service.get_sources()`。
    3.  `AppService.get_sources()` 委托给 `self.source_manager.get_sources()`。
    4.  `SourceManager.get_sources()` 返回当前从数据库加载并缓存在内存中的 `List[NewsSource]` 对象。
    5.  `SourceManagementPanel` 遍历此列表，为每个 `NewsSource` 对象调用 `_create_source_item_widget()` 来生成列表中的UI项。
-   **动态更新**:
    1.  `SourceManagementPanel.__init__` 将 `self.app_service.sources_updated` 信号连接到 `self.update_sources` 槽函数。
    2.  当后端（如 `SourceManager`）通过 `AppService` 成功添加、删除或修改新闻源并发出 `sources_updated` 信号后，`SourceManagementPanel` 的 `update_sources()` 方法会自动被调用，从而刷新UI列表以反映最新数据。
-   **主题应用**: `SourceManagementPanel` 使用注入的 `ThemeManager` (例如，通过调用 `self.theme_manager.get_current_theme()`) 来获取当前主题信息，并在其内部方法（如 `_update_widget_status`）中应用主题相关的样式，确保UI元素（如状态指示器的颜色）与全局主题一致。

## 3. 新闻源操作

### 3.1. 添加新闻源 (RSS)

1.  用户点击 "添加RSS源" 按钮，触发 `SourceManagementPanel._show_add_rss_dialog()`。
2.  `AddRssDialog` (一个内部对话框) 弹出，用户输入 RSS URL、名称（可选）和分类。
3.  用户确认后，`_show_add_rss_dialog()` 从 `AddRssDialog` 获取输入值 (`url`, `name`, `category`)。
4.  创建一个新的 `NewsSource` 对象实例，例如:
    ```python
    new_source = NewsSource(
        name=name_from_dialog or derived_name, # 如果名称为空，可能会基于URL生成
        type='rss',
        url=url_from_dialog,
        category=category_from_dialog or "未分类",
        enabled=True,
        is_user_added=True # 明确标记为用户添加
        # id 会在存入数据库后由 NewsStorage 自动生成并填充
        # custom_config 对于 RSS 源通常为空或不适用
    )
    ```
5.  调用 `self.app_service.add_source(new_source)`。
6.  `AppService.add_source()` 委托给 `self.source_manager.add_source(new_source)`。
7.  `SourceManager.add_source()`:
    -   将 `NewsSource` 对象通过其 `to_storage_dict()` 方法转换为适合数据库的字典。
    -   调用 `self.storage.add_news_source(source_dict)` 将数据存入 `news_sources` 表。
    -   如果成功，更新其内部的 `self.news_sources` 列表，并发出 `sources_updated` 信号。
8.  `SourceManagementPanel` 接收到 `sources_updated` 信号，刷新列表。

### 3.2. 编辑新闻源

1.  用户在列表中选择一个新闻源，并点击其对应的 "编辑" 按钮。此按钮的 `clicked` 信号连接到一个 `lambda` 函数，该函数调用 `SourceManagementPanel._show_edit_source_dialog()` 并传入对应的 `NewsSource` 对象。
2.  `_show_edit_source_dialog(source: NewsSource)` 方法执行:
    -   创建 `EditSourceDialog` 实例，并将选中的 `NewsSource` 对象传递给它。
3.  `EditSourceDialog` 根据传入的 `NewsSource` 对象初始化其界面字段：
    -   **通用字段**: `name`, `category`, `notes`。
    -   **URL**: 如果 `source.type == 'rss'`，则显示并允许编辑 `source.url`。
    -   **澎湃新闻特定配置 (`custom_config`)**: 如果 `source.type == 'pengpai'`，则从 `source.custom_config` (这是一个字典) 中读取 CSS 选择器，并填充到对应的 `QLineEdit` 中。如果 `source.custom_config` 为 `None` 或空，则输入框显示为空或预设提示文本。
4.  用户在 `EditSourceDialog` 中修改信息并确认。
5.  `_show_edit_source_dialog()` 从 `EditSourceDialog.get_values()` 获取一个包含所有已修改字段的字典 (`updated_values`)。
    -   对于澎湃新闻源，`updated_values` 字典中会包含一个 `custom_config` 键，其值是一个包含所有 CSS 选择器键值对的新字典。
    ```python
    # updated_values 示例:
    # 对于 RSS:
    # { 'name': 'New Name', 'url': 'new_url', 'category': 'New Cat', 'notes': '...' }
    # 对于澎湃:
    # { 'name': 'New Pengpai', 'category': 'New Cat', 'notes': '...', 
    #   'custom_config': { 'news_list_selector': '...', 'title_selector': '...', ... } }
    ```
6.  调用 `self.app_service.update_source(source.name, updated_values)`。注意：`source.name` 是原始名称，用于查找。如果名称本身被修改，`updated_values` 中会包含新的 `name`。
7.  `AppService.update_source()` 委托给 `self.source_manager.update_source(original_name, updated_data_dict)`。
8.  `SourceManager.update_source()`:
    -   根据 `original_name` 找到内存中的 `NewsSource` 对象。
    -   遍历 `updated_data_dict`，将新值赋给 `NewsSource` 对象的相应属性。特别地，如果 `updated_data_dict` 中有 `custom_config`，它会更新 `NewsSource` 对象的 `custom_config` 属性（该属性应为字典）。
    -   调用 `NewsSource` 对象的 `to_storage_dict()` 方法，该方法会将 `custom_config` 字典序列化为 JSON 字符串。
    -   调用 `self.storage.update_news_source(source_id, storage_dict)` 更新数据库。
    -   如果成功，发出 `sources_updated` 信号。
9.  `SourceManagementPanel` 接收到 `sources_updated` 信号，刷新列表。

### 3.3. 删除新闻源

1.  用户在列表中选择一个新闻源，并点击其对应的 "删除" 按钮。此按钮的 `clicked` 信号连接到一个 `lambda` 函数，该函数调用 `SourceManagementPanel._remove_selected_source()` 并传入对应的 `NewsSource` 对象。
2.  `_remove_selected_source(source: NewsSource)` 方法执行:
    -   弹出一个确认对话框。
    -   如果用户确认删除，调用 `self.app_service.remove_source(source.name)`。
3.  `AppService.remove_source()` 委托给 `self.source_manager.remove_source(source_name)`。
4.  `SourceManager.remove_source()`:
    -   根据 `source_name` 找到 `NewsSource` 对象及其 `id`。
    -   调用 `self.storage.delete_news_source(source_id)` 从数据库删除。
    -   如果成功，从其内部的 `self.news_sources` 列表中移除该对象，并发出 `sources_updated` 信号。
5.  `SourceManagementPanel` 接收到 `sources_updated` 信号，刷新列表。

### 3.4. 启用/禁用新闻源

1.  用户在列表项中点击 "启用" 复选框。该复选框的 `stateChanged` 信号连接到 `_toggle_source_enabled` 方法（通过 `lambda` 传递 `NewsSource` 对象和新的布尔状态）。
2.  `_toggle_source_enabled(source: NewsSource, enabled: bool)` 方法执行:
    -   创建一个更新字典: `updated_data = {'enabled': enabled}`。
    -   调用 `self.app_service.update_source(source.name, updated_data)`。
3.  后续流程同 **3.2. 编辑新闻源** 的步骤 7-9，`SourceManager` 会更新该源的 `is_enabled` 状态并持久化。

## 4. 状态显示与检查 (澎湃新闻)

-   `_create_source_item_widget()` 为澎湃新闻源创建一个 "检查状态" 按钮。
-   点击此按钮触发 `_refresh_source_status(source)`，该方法（目前）通过 `app_service.news_update_service.check_specific_rss_source_status(source)` 来检查（这里可能需要调整为通用的检查或澎湃特定的检查逻辑）。
-   检查结果通过信号 (`rss_status_check_complete`) 返回，并由 `_on_rss_check_complete` 处理，然后更新UI上显示的源状态信息。
    *(注意: `check_specific_rss_source_status` 可能需要泛化或为澎湃提供专门的检查机制，并更新 `SourceManager` 中源的 `status`, `last_error`, `last_checked_time` 等字段。)*

## 5. 总结

`SourceManagementPanel` 通过 `AppService` 抽象层与 `SourceManager` 和 `NewsStorage` 进行交互，实现了对新闻源的完整 CRUD 操作。数据模型 `NewsSource` 的变动（如 `custom_config` 的引入）已在UI层和数据处理流程中得到体现。信号和槽机制确保了UI在数据变更时能够及时响应和刷新。

## UI组件行为与测试详解

以下章节详细描述了特定UI组件的行为、与其ViewModel的交互方式，以及在测试过程中需要注意的关键点。

### LLMSettingsDialog & LLMSettingsViewModel

-   **职责**:
    -   `LLMSettingsDialog`: 作为View层，负责展示LLM配置相关的UI元素（如配置列表、表单字段、操作按钮），并将用户的交互（如点击、编辑）转发给 `LLMSettingsViewModel`。它监听ViewModel的信号以更新自身显示。
    -   `LLMSettingsViewModel`: 作为ViewModel层，负责处理所有LLM配置相关的业务逻辑和状态管理。其主要职责包括：
        -   通过注入的 `LLMConfigManager` 服务进行配置的加载、保存、读取、增、删、改、查。
        -   管理当前选中的配置、活动配置的状态。
        -   通过注入的 `LLMService` 服务测试指定配置的有效性。
        -   管理UI相关的状态（例如，各种操作按钮的启用/禁用状态、API密钥的可见性等）。
        -   向 `LLMSettingsDialog` 提供必要的数据，并通过信号通知其进行UI更新。
-   **ViewModel交互**:
    -   **Dialog -> ViewModel**: `LLMSettingsDialog` 通过调用 `LLMSettingsViewModel` 的方法来触发操作和请求/同步数据。关键方法包括：
        -   `load_initial_data()`: 初始化加载配置列表和活动配置。
        -   `select_config(config_name: str)`: 当用户在列表中选择一个配置时调用。
        -   `clear_selection()`: 当需要清除当前选择和表单时调用。
        -   `add_new_config(name: str)`: 添加新配置。
        -   `delete_selected_config(config_name: str)`: 删除当前选中的配置。
        -   `save_current_config(config_data: dict)`: 保存当前表单中的配置数据。
        -   `activate_selected_config()`: 激活当前选中的配置。
        -   `test_current_config(config_data: dict)`: 测试当前表单中的配置数据。
        -   `update_current_config_field(field_name: str, value: Any)`: 当表单字段内容改变时，通知ViewModel更新其内部的临时配置数据，并管理dirty状态。
    -   **ViewModel -> Dialog**: `LLMSettingsViewModel` 通过发射信号来通知 `LLMSettingsDialog` 更新UI或显示消息。关键信号包括：
        -   `config_list_changed(config_names: List[str])`: 配置名称列表更新时发射。
        -   `active_config_changed(active_config_name: Optional[str])`: 活动配置变更时发射。
        -   `current_config_loaded(config_data: Optional[Dict[str, Any]])`: 当前选中配置的数据加载完成时发射，用于填充表单。
        -   `config_cleared()`: 配置选择被清除，表单应重置时发射。
        -   `save_enabled_changed(enabled: bool)`: 保存按钮的启用状态改变时发射。
        -   `activate_enabled_changed(enabled: bool)`: 激活按钮的启用状态改变时发射。
        -   `test_enabled_changed(enabled: bool)`: 测试按钮的启用状态改变时发射。
        -   `test_result_received(success: bool, message: str)`: 测试操作完成后发射，携带结果。
        -   `save_status_received(success: bool, message: str)`: 保存操作完成后发射。
        -   `delete_status_received(success: bool, message: str)`: 删除操作完成后发射。
        -   `add_status_received(success: bool, message: str)`: 添加操作完成后发射。
        -   `activate_status_received(success: bool, message: str)`: 激活操作完成后发射。
        -   `error_occurred(message: str)`: 发生错误时发射，用于通知Dialog显示错误信息。
    -   **关键信号交互 (以激活配置为例)**:
        1.  `LLMSettingsDialog` 调用 `LLMSettingsViewModel.activate_selected_config()`。
        2.  `LLMSettingsViewModel` 成功激活配置后 (通过 `LLMConfigManager` 和 `LLMService`)：
            a.  更新内部的活动配置名称 (`_active_config_name`)。
            b.  发射 `activate_status_received(True, ...)`。
            c.  发射 `active_config_changed(new_active_name)`。
            d.  **发射 `config_list_changed(all_config_names)` 以通知UI列表刷新其活动标记。**
        3.  `LLMSettingsDialog` 响应这些信号：
            a.  `activate_status_received` -> 显示成功消息。
            b.  `active_config_changed` -> `_on_active_config_updated` 被调用 (通常记录日志或做轻量处理)。
            c.  `config_list_changed` -> `_on_config_list_updated` 被调用，该方法会重新填充列表，并根据 `ViewModel.get_active_config_name()` 的最新值正确标记活动项。
-   **DialogManager的角色**:
    -   `DialogManager` (位于 `src/ui/managers/dialog_manager.py`) 负责实例化 `LLMSettingsDialog`。
    -   在创建 `LLMSettingsDialog` 之前，`DialogManager` 会首先创建 `LLMSettingsViewModel` 的实例。
    -   创建 `LLMSettingsViewModel` 时，`DialogManager` 会从 `AppService` 获取并注入 `LLMConfigManager` 和 `LLMService` 这两个核心服务依赖。
    -   然后，`DialogManager` 将准备好的 `LLMSettingsViewModel` 实例注入到 `LLMSettingsDialog` 的构造函数中。
-   **测试要点**:
    -   在测试 `LLMSettingsDialog` 时，应使用 mock 的 `LLMSettingsViewModel`。
    -   验证 `LLMSettingsDialog` 是否正确显示从 `LLMSettingsViewModel` 获取的配置列表。
    -   验证 `LLMSettingsDialog` 是否正确响应 `LLMSettingsViewModel` 的信号并更新UI。
    -   特别注意API Key的处理：UI上应能正确显示从ViewModel获取的API Key（或其占位符），并允许用户临时输入，ViewModel负责将此临时密钥传递给 `LLMService` 进行测试，但不应直接保存临时输入的密钥，除非用户明确执行保存操作。

### BrowsingHistoryPanel & BrowsingHistoryViewModel

-   **职责**:
    -   `BrowsingHistoryPanel`: 作为View层，负责展示用户的浏览历史记录列表和选中记录的详情。它将用户的交互（如刷新、删除、清空）转发给 `BrowsingHistoryViewModel`，并监听ViewModel的信号以更新自身显示。
    -   `BrowsingHistoryViewModel`: 作为ViewModel层，负责浏览历史相关的业务逻辑和状态管理。其主要职责包括：
        -   通过注入的 `HistoryService` 进行历史记录的加载、删除和清空。
        -   管理历史记录的过滤（例如按时间范围、关键词）。
        -   向 `BrowsingHistoryPanel` 提供格式化后的历史数据，并通过信号通知其进行UI更新。
-   **ViewModel交互**:
    -   **Dialog -> ViewModel**: `BrowsingHistoryPanel` 通过调用 `BrowsingHistoryViewModel` 的方法来触发操作。
        -   `load_history()`: 加载或刷新历史记录。
        -   `set_filter_text(text: str)`: 设置文本过滤器。
        -   `set_filter_days(days: int)`: 设置时间范围过滤器。
        -   `delete_history_entries(entries_to_delete: list)`: (如果实现) 删除指定的历史条目。
        -   `clear_history()`: 清空所有历史记录。
    -   **ViewModel -> Dialog**: `BrowsingHistoryViewModel` 通过发射信号来通知 `BrowsingHistoryPanel` 更新UI。
        -   `history_changed(filtered_history: List[Dict])`: 当历史记录（加载后或过滤后）发生变化时发射，携带处理过的历史条目列表。
        -   `error_occurred(message: str)`: 发生错误时发射，用于通知Panel显示错误信息。
-   **DialogManager的角色**:
    -   `DialogManager` 负责实例化 `BrowsingHistoryPanel`。
    -   在创建 `BrowsingHistoryPanel` 之前，`DialogManager` 会首先创建 `BrowsingHistoryViewModel` 的实例。
    -   创建 `BrowsingHistoryViewModel` 时，`DialogManager` 会从 `AppService` 获取并注入 `HistoryService` 依赖。
    -   然后，`DialogManager` 将准备好的 `BrowsingHistoryViewModel` 实例注入到 `BrowsingHistoryPanel` 的构造函数中。
-   **数据流与连接**:
    -   `BrowsingHistoryViewModel` 在初始化时，会尝试连接到 `HistoryService.browsing_history_updated` 信号。当 `HistoryService` 内部的历史数据（如通过 `add_history_item` 添加新记录后）发生变化并发出此信号时，`BrowsingHistoryViewModel` 的 `load_history` 方法会被调用，从而刷新其内部数据并通过 `history_changed` 信号通知UI更新。
    -   `BrowsingHistoryPanel` 在其UI中执行操作（如点击"刷新"、"删除"）时，会调用 `BrowsingHistoryViewModel` 的相应方法，ViewModel再调用 `HistoryService` 的方法，`HistoryService` 操作数据库后，若数据有变，则发出 `browsing_history_updated`，触发ViewModel的更新，最终反馈到UI。
-   **测试要点**:
    -   测试 `BrowsingHistoryPanel` 时，应使用 mock 的 `BrowsingHistoryViewModel`。
    -   验证 `BrowsingHistoryPanel` 在初始化或刷新时是否调用 `ViewModel.load_history()`。
    -   验证UI操作是否正确调用ViewModel的方法。
    -   验证 `BrowsingHistoryPanel` 是否正确响应 `ViewModel.history_changed` 信号并更新列表。
    -   验证 `BrowsingHistoryViewModel` 是否正确连接到 `HistoryService.browsing_history_updated` 并能响应信号。