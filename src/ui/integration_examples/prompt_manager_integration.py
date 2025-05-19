# src/ui/integration_examples/prompt_manager_integration.py
"""
提示词管理器集成示例

展示如何在应用程序中集成模块化的提示词管理功能，
包括在主窗口菜单栏和分析面板中使用提示词管理组件。
"""

import logging
from typing import Optional

from PySide6.QtWidgets import QMainWindow, QMenu, QAction, QMessageBox
from PySide6.QtCore import QObject, Signal, Slot

from src.llm.llm_service import LLMService
from src.ui.managers.menu_prompt_manager import MenuPromptManager
from src.ui.managers.prompt_manager import PromptManagerService
from src.ui.components.prompt_manager_widget import PromptManagerWidget


"""
集成到主窗口的示例代码

以下代码展示如何在主窗口中集成提示词管理功能：
1. 导入必要的模块
2. 在主窗口初始化中创建MenuPromptManager实例
3. 连接信号处理模板选择事件
"""

'''
# 在主窗口类中添加以下代码

from src.ui.managers.menu_prompt_manager import MenuPromptManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ... 其他初始化代码 ...
        
        # 初始化LLM服务
        self.llm_service = app_service.llm_service
        
        # 创建提示词管理菜单
        self.prompt_menu_manager = MenuPromptManager(self, self.llm_service.prompt_manager)
        
        # 连接信号
        self.prompt_menu_manager.template_selected.connect(self._on_template_selected)
    
    def _on_template_selected(self, template_name: str, template_content: str):
        """处理模板选择事件"""
        # 可以在这里处理模板选择事件，例如：
        # 1. 更新当前活动面板的提示词
        # 2. 打开相应的分析面板并应用提示词
        # 3. 显示提示词预览
        
        # 示例：如果当前有活动的分析面板，则应用提示词
        if hasattr(self, "current_analysis_panel") and self.current_analysis_panel:
            if hasattr(self.current_analysis_panel, "prompt_manager_widget"):
                self.current_analysis_panel.prompt_manager_widget.set_template(template_name)
'''


"""
集成到分析面板的示例代码

以下代码展示如何在分析面板中使用模块化的提示词管理组件：
1. 导入必要的模块
2. 创建PromptManagerService实例
3. 创建PromptManagerWidget实例并添加到面板
4. 连接信号处理提示词相关事件
"""

'''
# 在分析面板类中添加以下代码

from src.ui.managers.prompt_manager import PromptManagerService
from src.ui.components.prompt_manager_widget import PromptManagerWidget

class AnalysisPanel(QDialog):
    def __init__(self, storage, llm_service, parent=None):
        super().__init__(parent)
        # ... 其他初始化代码 ...
        
        # 初始化提示词管理服务
        self.prompt_manager_service = PromptManagerService(llm_service.prompt_manager)
        
        # 在UI初始化中添加提示词管理组件
        def _init_ui(self):
            # ... 其他UI初始化代码 ...
            
            # 添加提示词管理组件到右侧面板
            right_layout = QVBoxLayout(right_panel)
            
            # 创建提示词管理组件
            self.prompt_manager_widget = PromptManagerWidget(self.prompt_manager_service)
            self.prompt_manager_widget.prompt_selected.connect(self._on_prompt_selected)
            self.prompt_manager_widget.prompt_edited.connect(self._on_prompt_edited)
            self.prompt_manager_widget.prompt_applied.connect(self._on_prompt_applied)
            right_layout.addWidget(self.prompt_manager_widget)
            
            # ... 其他UI组件 ...
        
        # 处理提示词相关事件
        def _on_prompt_selected(self, template_name: str, template_content: str):
            """当选择提示词模板时"""
            self.current_template_name = template_name
            self.current_template_content = template_content
        
        def _on_prompt_edited(self, content: str):
            """当提示词内容被编辑时"""
            self.current_template_content = content
        
        def _on_prompt_applied(self, template_name: str, template_content: str):
            """当应用提示词模板时"""
            self.current_template_name = template_name
            self.current_template_content = template_content
            
            # 可以在这里添加应用模板后的额外逻辑，例如自动开始分析
            if self.selected_news_items and self.analyze_button.isEnabled():
                self._analyze_selected_news()
'''


"""
使用说明

要完成提示词管理功能的模块化重构，请按照以下步骤操作：

1. 将以下文件添加到项目中：
   - src/ui/managers/prompt_manager.py - 提示词管理服务
   - src/ui/components/prompt_manager_widget.py - 提示词管理UI组件
   - src/ui/managers/menu_prompt_manager.py - 提示词管理菜单集成

2. 在主窗口中集成提示词管理菜单：
   - 导入MenuPromptManager
   - 创建MenuPromptManager实例
   - 连接template_selected信号

3. 在分析面板中使用模块化的提示词管理组件：
   - 导入PromptManagerService和PromptManagerWidget
   - 创建PromptManagerService实例
   - 创建PromptManagerWidget实例并添加到面板
   - 连接相关信号

4. 删除原有的integrated_analysis_panel_prompt_manager.py文件，使用新的模块化组件替代

这种模块化设计的优势：
- 提高代码的可维护性和复用性
- 降低主面板的复杂度
- 提供全局访问提示词模板的能力
- 使提示词管理功能在整个应用中更加一致
"""