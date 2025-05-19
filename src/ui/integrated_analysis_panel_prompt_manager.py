# src/ui/integrated_analysis_panel_prompt_manager.py
"""
新闻分析整合面板的提示词管理集成

将提示词模板管理功能集成到新闻分析整合面板中，
允许用户根据新闻内容选择合适的提示词模板进行分析。
"""

import logging
from typing import Dict, Optional

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QComboBox, QGroupBox, QTextEdit,
                             QMessageBox, QSizePolicy)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from src.llm.prompt_manager import PromptManager
from src.ui.managers.prompt_template_manager import PromptTemplateManager


class PromptManagerWidget(QGroupBox):
    """
    提示词管理组件，集成到新闻分析整合面板中
    """
    
    # 定义信号
    prompt_selected = Signal(str, str)  # 模板名称, 模板内容
    prompt_edited = Signal(str)  # 编辑后的提示词内容
    
    def __init__(self, prompt_manager: PromptManager, parent=None):
        super().__init__("提示词管理", parent)
        
        self.logger = logging.getLogger('news_analyzer.ui.prompt_manager_widget')
        self.prompt_manager = prompt_manager
        self.templates_dict = {}  # 存储模板名称和内容
        self.current_template_name = ""
        self.current_template_content = ""
        
        # 初始化UI
        self._init_ui()
        
        # 加载模板数据
        self._load_templates()
    
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
        self.template_combo.currentTextChanged.connect(self._on_template_selected)
        template_layout.addWidget(self.template_combo)
        
        # 管理按钮
        self.manage_button = QPushButton("管理模板")
        self.manage_button.setIcon(QIcon.fromTheme("document-properties"))
        self.manage_button.clicked.connect(self._open_template_manager)
        template_layout.addWidget(self.manage_button)
        
        layout.addLayout(template_layout)
        
        # 提示词编辑区域
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("请选择一个提示词模板...")
        self.prompt_edit.setMinimumHeight(150)
        self.prompt_edit.textChanged.connect(self._on_prompt_edited)
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
        self.apply_button.clicked.connect(self._apply_template)
        self.apply_button.setEnabled(False)  # 初始禁用
        button_layout.addWidget(self.apply_button)
        
        layout.addLayout(button_layout)
    
    def _load_templates(self):
        """
        加载所有提示词模板
        """
        self.template_combo.clear()
        self.templates_dict = {}
        
        # 添加默认选项
        self.template_combo.addItem("-- 选择提示词模板 --")
        
        # 获取提示词目录中的所有txt文件
        prompts_dir = self.prompt_manager.prompts_dir
        if not prompts_dir or not self.prompt_manager:
            self.logger.error("提示词管理器未正确初始化")
            return
        
        try:
            import os
            for filename in os.listdir(prompts_dir):
                if filename.endswith(".txt"):
                    template_name = os.path.splitext(filename)[0]
                    template_path = os.path.join(prompts_dir, filename)
                    
                    try:
                        with open(template_path, 'r', encoding='utf-8') as f:
                            template_content = f.read()
                            self.templates_dict[template_name] = template_content
                            
                            # 添加到下拉框，使用更友好的显示名称
                            display_name = self._get_display_name(template_name)
                            self.template_combo.addItem(display_name, template_name)
                    except Exception as e:
                        self.logger.error(f"读取模板文件失败: {template_path} - {e}")
        except Exception as e:
            self.logger.error(f"加载提示词模板失败: {e}")
    
    def _get_display_name(self, template_name: str) -> str:
        """
        将模板名称转换为更友好的显示名称
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
        """
        for i in range(self.template_combo.count()):
            if self.template_combo.itemText(i) == display_name:
                return self.template_combo.itemData(i)
        return display_name
    
    def _on_template_selected(self, display_name: str):
        """
        当选择模板时更新编辑区域
        """
        if display_name == "-- 选择提示词模板 --":
            self.prompt_edit.clear()
            self.prompt_edit.setEnabled(False)
            self.apply_button.setEnabled(False)
            self.current_template_name = ""
            self.current_template_content = ""
            return
        
        template_name = self._get_template_name(display_name)
        self.current_template_name = template_name
        template_content = self.templates_dict.get(template_name, "")
        self.current_template_content = template_content
        
        self.prompt_edit.setText(template_content)
        self.prompt_edit.setEnabled(True)
        self.apply_button.setEnabled(True)
        
        # 发送信号
        self.prompt_selected.emit(template_name, template_content)
    
    def _on_prompt_edited(self):
        """
        当提示词内容被编辑时
        """
        if self.current_template_name:
            self.current_template_content = self.prompt_edit.toPlainText()
            self.prompt_edited.emit(self.current_template_content)
    
    def _apply_template(self):
        """
        应用当前编辑的提示词
        """
        if not self.current_template_name:
            return
        
        # 发送信号
        self.prompt_selected.emit(self.current_template_name, self.current_template_content)
    
    def _open_template_manager(self):
        """
        打开提示词模板管理器
        """
        dialog = PromptTemplateManager(self.prompt_manager, self)
        dialog.template_changed.connect(self._on_template_changed)
        dialog.exec()
        
        # 重新加载模板
        self._load_templates()
    
    def _on_template_changed(self, template_name: str, template_content: str):
        """
        当模板被修改时更新
        """
        self.templates_dict[template_name] = template_content
        
        # 如果当前正在编辑该模板，则更新编辑区域
        if self.current_template_name == template_name:
            self.prompt_edit.setText(template_content)
            self.current_template_content = template_content
    
    def get_current_template(self) -> Dict[str, str]:
        """
        获取当前选择的模板信息
        """
        return {
            "name": self.current_template_name,
            "content": self.current_template_content
        }
    
    def set_template_by_name(self, template_name: str) -> bool:
        """
        根据模板名称设置当前模板
        """
        # 查找对应的显示名称
        for i in range(self.template_combo.count()):
            if self.template_combo.itemData(i) == template_name:
                self.template_combo.setCurrentIndex(i)
                return True
        return False
    
    def set_template_by_analysis_type(self, analysis_type: str) -> bool:
        """
        根据分析类型设置合适的模板
        """
        type_map = {
            "新闻相似度分析": "news_similarity_enhanced",
            "增强型多特征分析": "news_similarity_enhanced",
            "重要程度和立场分析": "importance_stance",
            "摘要": "summary",
            "深度分析": "deep_analysis",
            "关键观点": "key_points",
            "事实核查": "fact_check"
        }
        
        template_name = type_map.get(analysis_type)
        if template_name:
            return self.set_template_by_name(template_name)
        return False