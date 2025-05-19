"""
提示词管理UI组件

提供提示词模板的选择、编辑和应用功能的UI组件，
可以被多个面板复用。
"""

import logging
from typing import Dict, Optional

from PySide6.QtWidgets import (QGroupBox, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QComboBox, QTextEdit, QSizePolicy)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

# Adjusted import for managers being one level up
from ..managers.prompt_manager import PromptManagerService


class PromptManagerWidget(QGroupBox):
    """
    提示词管理UI组件，提供提示词模板的选择、编辑和应用功能
    """
    
    # 定义信号
    prompt_selected = Signal(str, str)  # 模板名称, 模板内容
    prompt_edited = Signal(str)  # 编辑后的提示词内容
    prompt_applied = Signal(str, str)  # 模板名称, 模板内容
    
    def __init__(self, prompt_manager_service: PromptManagerService, parent=None):
        """
        初始化提示词管理UI组件
        
        Args:
            prompt_manager_service: 提示词管理服务
            parent: 父组件
        """
        super().__init__("提示词管理", parent)
        
        self.logger = logging.getLogger('news_analyzer.ui.views.prompt_manager_widget') # Updated logger name
        self.prompt_manager_service = prompt_manager_service
        
        # 初始化UI
        self._init_ui()
        
        # 连接信号
        self._connect_signals()
        
        # 加载模板数据
        self._populate_templates()
    
    def _init_ui(self):
        """
        初始化UI布局和控件
        """
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 15, 10, 10)
        
        # 模板选择区域
        template_layout = QHBoxLayout()
        
        template_label = QLabel("选择提示词模板:")
        template_label.setStyleSheet("font-weight: bold;")
        template_layout.addWidget(template_label)
        
        self.template_combo = QComboBox()
        self.template_combo.setMinimumWidth(200)
        self.template_combo.setStyleSheet("""
            QComboBox { 
                border: 1px solid #C0C0C0; 
                border-radius: 4px; 
                padding: 5px; 
            }
            QComboBox::drop-down { 
                subcontrol-origin: padding; 
                subcontrol-position: top right; 
                width: 20px; 
                border-left: 1px solid #C0C0C0;
            }
        """)
        template_layout.addWidget(self.template_combo)
        
        # 管理按钮
        self.manage_button = QPushButton("管理模板")
        self.manage_button.setIcon(QIcon.fromTheme("document-properties"))
        self.manage_button.setStyleSheet("""
            QPushButton { 
                background-color: #F0F0F0; 
                border: 1px solid #C0C0C0; 
                border-radius: 4px; 
                padding: 6px 12px; 
            }
            QPushButton:hover { 
                background-color: #E0E0E0;
            }
            QPushButton:pressed { 
                background-color: #D0D0D0;
            }
        """)
        template_layout.addWidget(self.manage_button)
        
        layout.addLayout(template_layout)
        
        # 提示词编辑区域
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("请选择一个提示词模板...")
        self.prompt_edit.setMinimumHeight(150)
        self.prompt_edit.setStyleSheet("""
            QTextEdit { 
                border: 1px solid #C4C4C4; 
                border-radius: 4px; 
                padding: 8px; 
                background-color: #FFFFFF;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.prompt_edit)
        
        # 提示信息
        hint_label = QLabel("提示: 使用 {title}, {source}, {pub_date}, {content} 等占位符表示新闻数据")
        hint_label.setStyleSheet("color: #666; font-style: italic; font-size: 12px;")
        layout.addWidget(hint_label)
        
        # 底部按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.apply_button = QPushButton("应用模板")
        self.apply_button.setIcon(QIcon.fromTheme("dialog-ok-apply"))
        self.apply_button.setStyleSheet("""
            QPushButton { 
                background-color: #4CAF50; 
                color: white; 
                border: none; 
                border-radius: 4px; 
                padding: 6px 12px; 
                font-weight: bold;
            }
            QPushButton:hover { 
                background-color: #45a049;
            }
            QPushButton:pressed { 
                background-color: #3d8b40;
            }
            QPushButton:disabled { 
                background-color: #CCCCCC; 
                color: #666666;
            }
        """)
        self.apply_button.setEnabled(False)  # 初始禁用
        button_layout.addWidget(self.apply_button)
        
        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """
        连接信号和槽
        """
        # 连接UI控件信号
        self.template_combo.currentTextChanged.connect(self._on_template_selected)
        self.manage_button.clicked.connect(self._open_template_manager)
        self.prompt_edit.textChanged.connect(self._on_prompt_edited)
        self.apply_button.clicked.connect(self._apply_template)
        
        # 连接服务信号
        self.prompt_manager_service.templates_updated.connect(self._populate_templates)
        self.prompt_manager_service.template_loaded.connect(self._on_template_loaded)
        self.prompt_manager_service.template_edited.connect(self._on_template_content_updated)
    
    def _populate_templates(self):
        """
        填充模板下拉框
        """
        self.template_combo.clear()
        
        # 添加默认选项
        self.template_combo.addItem("-- 选择提示词模板 --")
        
        # 获取所有模板名称
        template_names = self.prompt_manager_service.get_template_names()
        
        # 添加到下拉框，使用更友好的显示名称
        for template_name in sorted(template_names):
            display_name = self._get_display_name(template_name)
            self.template_combo.addItem(display_name, template_name)
    
    def _get_display_name(self, template_name: str) -> str:
        """
        将模板名称转换为更友好的显示名称
        
        Args:
            template_name: 模板名称
            
        Returns:
            显示名称
        """
        name_map = {
            "news_analysis": "新闻分析",
            "importance": "重要程度分析",
            "importance_stance": "重要程度和立场分析",
            "stance": "立场分析",
            "fact_check": "事实核查",
            "summary": "摘要生成",
            "deep_analysis": "深度分析",
            "key_points": "关键观点提取",
            "news_similarity": "新闻相似度分析",
            "news_similarity_enhanced": "增强型新闻相似度分析",
            "chat_system": "系统提示词"
        }
        
        return name_map.get(template_name, template_name)
    
    def _get_template_name(self, display_name: str) -> str:
        """
        将显示名称转换回模板名称
        
        Args:
            display_name: 显示名称
            
        Returns:
            模板名称
        """
        for i in range(self.template_combo.count()):
            if self.template_combo.itemText(i) == display_name:
                return self.template_combo.itemData(i)
        return display_name
    
    def _on_template_selected(self, display_name: str):
        """
        当选择模板时更新编辑区域
        
        Args:
            display_name: 显示名称
        """
        if display_name == "-- 选择提示词模板 --":
            self.prompt_edit.clear()
            self.prompt_edit.setEnabled(False)
            self.apply_button.setEnabled(False)
            return
        
        template_name = self._get_template_name(display_name)
        
        # 通过服务选择模板
        self.prompt_manager_service.select_template(template_name)
    
    def _on_template_loaded(self, template_name: str, template_content: str):
        """
        当模板加载时更新UI
        
        Args:
            template_name: 模板名称
            template_content: 模板内容
        """
        self.prompt_edit.setEnabled(True)
        self.prompt_edit.setText(template_content)
        self.apply_button.setEnabled(True)
        
        # 发射信号，通知外部内容已加载
        self.prompt_selected.emit(template_name, template_content)
    
    def _on_prompt_edited(self):
        """
        当编辑区域内容改变时发射信号
        """
        current_text = self.prompt_edit.toPlainText()
        self.prompt_edited.emit(current_text)
        
        # 如果当前有模板被选中，则启用应用按钮
        current_display_name = self.template_combo.currentText()
        self.apply_button.setEnabled(current_display_name != "-- 选择提示词模板 --")
    
    def _on_template_content_updated(self, content: str):
        """
        当服务端的模板内容更新时（例如外部编辑后），更新编辑区域
        
        Args:
            content: 新的模板内容
        """
        # 避免信号循环：只有当内容确实不同时才更新
        if self.prompt_edit.toPlainText() != content:
            self.prompt_edit.setText(content)
    
    def _apply_template(self):
        """
        应用当前选中的模板（或编辑后的内容）
        """
        current_display_name = self.template_combo.currentText()
        if current_display_name == "-- 选择提示词模板 --":
            return
            
        template_name = self._get_template_name(current_display_name)
        content = self.prompt_edit.toPlainText()
        
        self.logger.info(f"应用提示词模板 '{template_name}'")
        self.prompt_applied.emit(template_name, content)
    
    def _open_template_manager(self):
        """
        打开提示词管理对话框（通过服务）
        """
        self.logger.debug("请求打开提示词管理对话框...")
        self.prompt_manager_service.open_manager_dialog()
    
    def get_current_template(self) -> tuple:
        """
        获取当前选中的模板名称和内容
        
        Returns:
            (template_name, content) 或 (None, content) 如果未选模板
        """
        current_display_name = self.template_combo.currentText()
        content = self.prompt_edit.toPlainText()
        
        if current_display_name == "-- 选择提示词模板 --":
            return None, content
        else:
            template_name = self._get_template_name(current_display_name)
            return template_name, content

    def set_template(self, template_name: str) -> bool:
        """
        以编程方式设置选定的模板
        
        Args:
            template_name: 要设置的模板名称
        
        Returns:
            True 如果成功设置，False 如果未找到该模板
        """
        display_name = self._get_display_name(template_name)
        index = self.template_combo.findText(display_name)
        if index >= 0:
            self.template_combo.setCurrentIndex(index)
            # _on_template_selected 会被触发，进而加载内容
            return True
        else:
            self.logger.warning(f"尝试设置不存在的模板: {template_name}")
            return False 