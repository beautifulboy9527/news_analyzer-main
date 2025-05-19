# src/ui/modules/__init__.py
"""
新闻分析整合面板模块化组件包

包含用于构建新闻分析整合面板的各个模块化组件，
采用MVC架构设计，提高代码可维护性和可测试性。
"""

from src.ui.modules.analysis_panel_ui_builder import AnalysisPanelUIBuilder
from src.ui.modules.analysis_panel_data_manager import AnalysisPanelDataManager
from src.ui.modules.analysis_panel_event_handler import AnalysisPanelEventHandler

__all__ = [
    'AnalysisPanelUIBuilder',
    'AnalysisPanelDataManager',
    'AnalysisPanelEventHandler'
]