# 05 - 设置与主题逻辑

## 1. 核心组件

*(基于代码分析)*

- **`ThemeManager` (`src/ui/theme_manager.py`)**: 负责查找 (`_find_themes`)、加载 (`load_theme_stylesheet`)、应用 (`apply_theme`, `apply_initial_theme`) 和保存 (`apply_theme` 内部调用 `QSettings`) 主题设置 (当前主题名称，如 'light', 'dark')。
- **`UISettingsManager` (`src/ui/ui_settings_manager.py`)**: 负责管理全局字体大小。加载 (`_load_font_size`)、应用 (`_apply_font_size`, `adjust_font_size`) 和保存 (`_save_font_size`) 字体大小到 `QSettings`。
- **`SettingsDialog` (`src/ui/views/settings_dialog.py`)**: 提供用户界面让用户选择主题和调整字体大小，内部会调用 `ThemeManager` 和 `UISettingsManager` 的方法。
- **`AutomationSettingsDialog` (`src/ui/views/automation_settings_dialog.py`)**: 提供用户界面管理自动化相关设置，目前主要包括新闻自动刷新功能的启用和刷新间隔（小时、分钟）。该对话框与 `SchedulerService` 交互以读取和更新调度配置。
- **`SchedulerService` (`src/services/scheduler_service.py`)**: 管理后台任务调度，特别是新闻源的定时刷新。使用 `QSettings` 持久化其配置。
- **`DialogManager` (`src/ui/managers/dialog_manager.py`)**: 负责管理各种对话框的创建与显示，包括 `SettingsDialog` 和 `AutomationSettingsDialog`。
- **`MenuManager` (`src/ui/managers/menu_manager.py`)**: 创建和管理菜单栏，包含打开 `SettingsDialog` (编辑 -> 应用程序设置) 和 `AutomationSettingsDialog` (工具 -> 自动化设置) 的菜单项。
- **`QSettings` (`PySide6.QtCore`)**: Qt 提供的用于持久化存储设置的机制 (使用 \"NewsAnalyzer\" / \"NewsAggregator\" 作为组织/应用名)。
    - Theme Key: `ui/theme`
    - Font Size Key: `ui/font_size`
    - Scheduler Enabled Key: `scheduler/enabled` (由 `SchedulerService` 管理)
    - Scheduler Interval Key: `scheduler/interval_minutes` (由 `SchedulerService` 管理)

## 2. 关键流程

*(基于相关代码分析和对话框交互)*

1.  **加载初始设置 (应用启动时):**
    1.  `main.py` 或 `MainWindow` 创建 `ThemeManager`, `UISettingsManager`, 和 `SchedulerService` 实例。
    2.  `ThemeManager.apply_initial_theme()` 从 `QSettings` 读取 `ui/theme` 并应用初始主题。
    3.  `UISettingsManager` 在初始化时从 `QSettings` 读取 `ui/font_size`。`MainWindow` 或启动逻辑随后应用此字体大小。
    4.  `SchedulerService` 在初始化时从 `QSettings` 读取 `scheduler/enabled` 和 `scheduler/interval_minutes`，并在 `start()` 时根据这些设置配置后台任务。

2.  **通过应用程序设置对话框更改外观 (`SettingsDialog`):**
    1.  用户通过菜单 (编辑 -> 应用程序设置) 打开 `SettingsDialog`。
    2.  `SettingsDialog` 从 `ThemeManager.get_current_theme()` 和 `UISettingsManager.get_current_font_size()` 获取当前设置，初始化界面控件 (主题选择 `QComboBox`，字体大小 `QSlider`)。
    3.  用户修改控件值。
    4.  用户点击"确定" (`accept()`):
        -   对话框获取控件当前选择的主题名称和字体大小。
        -   如果主题更改，调用 `ThemeManager.apply_theme(new_theme_name)` (内部保存到 `QSettings`)。
        -   如果字体大小更改，调用 `UISettingsManager.adjust_font_size(delta)` (内部保存到 `QSettings` 并应用)。
    5.  用户点击"取消" (`reject()`): 对话框关闭，不保存或应用任何更改 (除非对话框设计为实时预览，当前版本非实时)。

    *(`DialogManager` 负责创建这些对话框，并会传递必要的依赖，例如将 `ThemeManager` 实例传递给需要主题感知能力的对话框，如 `SourceManagementPanel`。)*

3.  **通过自动化设置对话框更改刷新配置 (`AutomationSettingsDialog`):**
    1.  用户通过菜单 (工具 -> 自动化设置) 打开 `AutomationSettingsDialog`。
    2.  对话框从 `SchedulerService.get_schedule_config()` 获取当前的自动刷新启用状态和刷新间隔（总分钟数）。
    3.  UI 将总分钟数转换为小时和分钟，并填充到对应的 `QCheckBox` 和 `QSpinBox` 控件中。
    4.  用户修改启用复选框、小时或分钟微调框。
    5.  用户点击"确定" (`accept()`):
        -   对话框获取复选框状态以及小时和分钟微调框的值。
        -   将小时和分钟转换为总刷新间隔（分钟）。
        -   进行最小间隔验证（例如，至少5分钟）。如果低于阈值，可能会提示用户或自动调整。
        -   调用 `SchedulerService.update_schedule(new_enabled, new_total_interval_minutes)`。
        -   `SchedulerService.update_schedule` 方法会将新配置保存到 `QSettings` (使用 `scheduler/enabled` 和 `scheduler/interval_minutes` 键) 并重新配置或启动/停止其内部的 `BackgroundScheduler` 任务。
    6.  用户点击"取消" (`reject()`): 对话框关闭，不应用任何更改到 `SchedulerService` 或 `QSettings`。

4.  **通过视图菜单直接操作 (部分功能可能已移至对话框):**
    *   **主题切换**: 如果菜单中仍保留直接的主题切换选项 (如旧版中的日间/夜间模式)，`QAction` 的 `triggered` 信号会连接到 `MainWindow` 或 `MenuManager` 的槽函数，进而调用 `ThemeManager.apply_theme()`。
    *   **字体调整**: 类似地，如果菜单中有直接的字体增大/减小/重置选项，它们会调用 `UISettingsManager` 的相应方法。*(注意: 这些操作更推荐通过 `SettingsDialog` 进行集中管理)*。

## 3. 状态同步与刷新问题

-   **应用机制**: 主题通过 `QApplication.setStyleSheet()` 应用，字体通过 `QApplication.setFont()` 应用。自动刷新通过 `SchedulerService` 控制 `apscheduler` 实现。
-   **持久化**: 主题、字体大小、调度器配置均使用 `QSettings` 进行持久化。
-   **刷新**:
    -   `ThemeManager.apply_theme` 调用 `QApplication.setStyleSheet()`。
    -   `UISettingsManager._apply_font_size` 调用 `QApplication.setFont()`。
    -   `SchedulerService.update_schedule` 会重新配置 `apscheduler`。
    -   **UI 刷新**:
        -   主题和字体大小更改后，依赖 Qt 的样式传播和重绘机制。有时可能需要显式调用 `widget.update()` 或 `widget.style().unpolish(widget); widget.style().polish(widget);` 来强制刷新复杂或自定义绘制的控件。
        -   硬编码在 `ThemeManager.load_theme_stylesheet` 中的 QSS 字符串（`override_styles`）是全局样式的一部分。
        -   若 `SettingsDialog` 或 `AutomationSettingsDialog` 的更改需要主界面或其他面板响应（例如，状态栏显示调度器状态），则需要通过信号/槽机制或回调进行通知。

## 4. 注意事项与潜在改进

-   `SettingsDialog` 和 `AutomationSettingsDialog` 的父窗口是 `MainWindow`，确保了模态行为和正确的父子关系。
-   `SchedulerService` 依赖于 `AppService` 来执行实际的新闻刷新操作 (`_app_service.refresh_all_sources()`)。
-   当前的 `_validate_min_interval` 逻辑在 `AutomationSettingsDialog` 中，用于确保刷新间隔不小于设定下限，并在用户输入时提供反馈。
-   错误处理：`_save_settings` 在 `AutomationSettingsDialog` 和 `SettingsDialog` 中应包含错误处理（例如，如果 `QSettings` 写入失败）。
-   模块化：将自动化设置分离到 `AutomationSettingsDialog` 提高了模块化程度，便于未来扩展更多自动化功能。 