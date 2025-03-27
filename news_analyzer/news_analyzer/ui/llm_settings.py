"""
语言模型设置对话框

提供配置LLM API的界面，支持OpenAI等多种API格式。
"""

import os
import logging
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                            QLineEdit, QComboBox, QPushButton, QLabel, 
                            QMessageBox, QGroupBox, QCheckBox, QTabWidget,
                            QWidget)  # Added QWidget import
from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtGui import QIcon


class LLMSettingsDialog(QDialog):
    """语言模型设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.logger = logging.getLogger('news_analyzer.ui.llm_settings')
        
        self.setWindowTitle("语言模型设置")
        self.setMinimumWidth(550)
        self.setMinimumHeight(400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self._init_ui()
        self._load_settings()
    
    def _init_ui(self):
        """初始化UI"""
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 标签页
        tabs = QTabWidget()
        
        # ==========基本设置标签页==========
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        basic_layout.setSpacing(15)
        
        # 创建API设置组
        api_group = QGroupBox("API设置")
        api_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        api_layout = QFormLayout()
        api_layout.setSpacing(10)
        api_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        
        # API URL
        self.api_url = QLineEdit()
        self.api_url.setPlaceholderText("例如: https://api.openai.com/v1/chat/completions")
        api_layout.addRow("API端点URL:", self.api_url)
        
        # API密钥
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("输入API密钥")
        api_layout.addRow("API密钥:", self.api_key)
        
        # 模型名称
        self.model_name = QLineEdit()
        self.model_name.setPlaceholderText("例如: gpt-3.5-turbo")
        api_layout.addRow("模型名称:", self.model_name)
        
        # 保存API密钥选项
        self.save_key = QCheckBox("保存API密钥 (注意：密钥将以明文存储)")
        self.save_key.setToolTip("选中后，API密钥将保存在本地配置中")
        api_layout.addRow("", self.save_key)
        
        api_group.setLayout(api_layout)
        basic_layout.addWidget(api_group)
        
        # 预设模型组
        presets_group = QGroupBox("预设模型")
        presets_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        presets_layout = QVBoxLayout()
        presets_layout.setSpacing(8)
        
        # 创建预设按钮样式
        preset_button_style = """
            QPushButton {
                padding: 8px;
                border-radius: 4px;
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """
        
        # 预设模型按钮
        openai_button = QPushButton("OpenAI GPT-3.5-Turbo")
        openai_button.setStyleSheet(preset_button_style)
        openai_button.clicked.connect(self._use_openai_preset)
        presets_layout.addWidget(openai_button)
        
        openai_button_4 = QPushButton("OpenAI GPT-4o")
        openai_button_4.setStyleSheet(preset_button_style)
        openai_button_4.clicked.connect(self._use_openai_4_preset)
        presets_layout.addWidget(openai_button_4)
        
        claude_button = QPushButton("Anthropic Claude")
        claude_button.setStyleSheet(preset_button_style)
        claude_button.clicked.connect(self._use_claude_preset)
        presets_layout.addWidget(claude_button)
        
        local_button = QPushButton("本地模型 (Ollama)")
        local_button.setStyleSheet(preset_button_style)
        local_button.clicked.connect(self._use_local_preset)
        presets_layout.addWidget(local_button)
        
        presets_group.setLayout(presets_layout)
        basic_layout.addWidget(presets_group)
        
        # 添加弹性空间
        basic_layout.addStretch(1)
        
        # ==========高级设置标签页==========
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        advanced_layout.setSpacing(15)
        
        # 模型参数设置
        params_group = QGroupBox("模型参数")
        params_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        params_layout = QFormLayout()
        params_layout.setSpacing(10)
        
        # 温度参数
        self.temperature = QLineEdit("0.7")
        self.temperature.setPlaceholderText("值范围: 0.0-1.0")
        params_layout.addRow("温度 (Temperature):", self.temperature)
        
        # 最大Token
        self.max_tokens = QLineEdit("4096")
        self.max_tokens.setPlaceholderText("例如: 2048")
        params_layout.addRow("最大生成长度:", self.max_tokens)
        
        # 系统提示
        self.system_prompt = QLineEdit()
        self.system_prompt.setPlaceholderText("为模型设置默认行为的系统提示")
        params_layout.addRow("系统提示:", self.system_prompt)
        
        params_group.setLayout(params_layout)
        advanced_layout.addWidget(params_group)
        
        # API请求设置
        request_group = QGroupBox("API请求设置")
        request_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        request_layout = QFormLayout()
        request_layout.setSpacing(10)
        
        # 超时设置
        self.timeout = QLineEdit("60")
        self.timeout.setPlaceholderText("单位: 秒")
        request_layout.addRow("请求超时:", self.timeout)
        
        # 重试次数
        self.retry_count = QLineEdit("3")
        request_layout.addRow("重试次数:", self.retry_count)
        
        request_group.setLayout(request_layout)
        advanced_layout.addWidget(request_group)
        
        # 添加弹性空间
        advanced_layout.addStretch(1)
        
        # 添加标签页
        tabs.addTab(basic_tab, "基本设置")
        tabs.addTab(advanced_tab, "高级设置")
        layout.addWidget(tabs)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # 测试连接按钮
        self.test_button = QPushButton("测试连接")
        self.test_button.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                background-color: #4b6eaf;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3c5c99;
            }
            QPushButton:pressed {
                background-color: #2e4677;
            }
        """)
        self.test_button.clicked.connect(self._test_connection)
        button_layout.addWidget(self.test_button)
        
        # 占位空间
        button_layout.addStretch()
        
        # 取消按钮
        cancel_button = QPushButton("取消")
        cancel_button.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        # 保存按钮
        save_button = QPushButton("保存")
        save_button.setDefault(True)
        save_button.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        save_button.clicked.connect(self.accept)
        button_layout.addWidget(save_button)
        
        layout.addLayout(button_layout)
    
    def _load_settings(self):
        """加载设置"""
        settings = QSettings("NewsAnalyzer", "NewsAggregator")
        
        self.api_url.setText(settings.value("llm/api_url", ""))
        if settings.value("llm/save_key", False, type=bool):
            self.api_key.setText(settings.value("llm/api_key", ""))
            self.save_key.setChecked(True)
        
        self.model_name.setText(settings.value("llm/model_name", ""))
        self.temperature.setText(settings.value("llm/temperature", "0.7"))
        self.max_tokens.setText(settings.value("llm/max_tokens", "2048"))
        self.system_prompt.setText(settings.value("llm/system_prompt", ""))
        self.timeout.setText(settings.value("llm/timeout", "60"))
        self.retry_count.setText(settings.value("llm/retry_count", "3"))
    
    def save_settings(self):
        """保存设置"""
        settings = QSettings("NewsAnalyzer", "NewsAggregator")
        
        # 保存基本设置
        settings.setValue("llm/api_url", self.api_url.text())
        settings.setValue("llm/model_name", self.model_name.text())
        settings.setValue("llm/save_key", self.save_key.isChecked())
        if self.save_key.isChecked():
            settings.setValue("llm/api_key", self.api_key.text())
        else:
            settings.remove("llm/api_key")
        
        # 保存高级设置
        settings.setValue("llm/temperature", self.temperature.text())
        settings.setValue("llm/max_tokens", self.max_tokens.text())
        settings.setValue("llm/system_prompt", self.system_prompt.text())
        settings.setValue("llm/timeout", self.timeout.text())
        settings.setValue("llm/retry_count", self.retry_count.text())
        
        # 设置环境变量
        os.environ["LLM_API_URL"] = self.api_url.text()
        os.environ["LLM_API_KEY"] = self.api_key.text()
        os.environ["LLM_MODEL"] = self.model_name.text()
        
        self.logger.info("已保存LLM设置")
    
    def get_settings(self):
        """获取设置值
        
        Returns:
            dict: 设置值字典
        """
        return {
            "api_url": self.api_url.text(),
            "api_key": self.api_key.text(),
            "model_name": self.model_name.text(),
            "temperature": float(self.temperature.text() or "0.7"),
            "max_tokens": int(self.max_tokens.text() or "2048"),
            "system_prompt": self.system_prompt.text(),
            "timeout": int(self.timeout.text() or "60"),
            "retry_count": int(self.retry_count.text() or "3")
        }
    
    def _use_openai_preset(self):
        """使用OpenAI GPT-3.5预设"""
        self.api_url.setText("https://api.openai.com/v1/chat/completions")
        self.model_name.setText("gpt-3.5-turbo")
        self.system_prompt.setText("你是一个专业的新闻分析助手，可以提供客观、全面的新闻分析和解读。")
    
    def _use_openai_4_preset(self):
        """使用OpenAI GPT-4预设"""
        self.api_url.setText("https://api.openai.com/v1/chat/completions")
        self.model_name.setText("gpt-4o")
        self.system_prompt.setText("你是一个专业的新闻分析助手，可以提供客观、全面的新闻分析和解读。")
    
    def _use_claude_preset(self):
        """使用Claude预设"""
        self.api_url.setText("https://api.anthropic.com/v1/messages")
        self.model_name.setText("claude-3-opus-20240229")
        self.system_prompt.setText("你是一个专业的新闻分析助手，可以提供客观、全面的新闻分析和解读。")
    
    def _use_local_preset(self):
        """使用本地模型预设"""
        self.api_url.setText("http://localhost:11434/api/chat")
        self.model_name.setText("llama3")
        self.system_prompt.setText("你是一个专业的新闻分析助手，可以提供客观、全面的新闻分析和解读。")
    
    def _test_connection(self):
        """测试API连接"""
        from news_analyzer.llm.llm_client import LLMClient
        
        api_url = self.api_url.text()
        api_key = self.api_key.text()
        model_name = self.model_name.text()
        
        if not api_url or not api_key:
            QMessageBox.warning(self, "输入错误", "请输入API URL和API密钥")
            return
        
        self.test_button.setEnabled(False)
        self.test_button.setText("正在测试...")
        
        try:
            # 创建临时客户端进行测试
            client = LLMClient(api_key=api_key, api_url=api_url, model=model_name)
            result = client.test_connection()
            
            self.test_button.setEnabled(True)
            self.test_button.setText("测试连接")
            
            if result:
                QMessageBox.information(self, "连接成功", "已成功连接到API服务！")
            else:
                QMessageBox.warning(self, "连接失败", "无法连接到API服务，请检查设置。")
        
        except Exception as e:
            self.test_button.setEnabled(True)
            self.test_button.setText("测试连接")
            QMessageBox.critical(self, "连接错误", f"测试连接时发生错误:\n{str(e)}")