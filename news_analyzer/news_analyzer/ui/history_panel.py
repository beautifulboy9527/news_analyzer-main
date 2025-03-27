"""
历史新闻面板

提供浏览和加载已保存的历史新闻功能。
"""

import os
import json
import logging
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QListWidgetItem, QLabel, QTextBrowser, 
                             QPushButton, QSplitter, QComboBox, QFrame,
                             QMessageBox, QFileDialog, QProgressBar, 
                             QTabWidget, QGridLayout)
from PyQt5.QtCore import Qt, pyqtSignal, QSize


class HistoryPanel(QWidget):
    """历史新闻面板组件"""
    
    # 自定义信号：历史新闻加载完成
    history_loaded = pyqtSignal(list)
    
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        
        self.logger = logging.getLogger('news_analyzer.ui.history_panel')
        self.storage = storage
        
        # 初始化状态标签（提前创建防止错误）
        self.status_label = QLabel("就绪")
        
        # 显式设置新闻数据存储目录路径
        self.news_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'news')
        if not os.path.exists(self.news_dir):
            # 备选路径 - 直接使用绝对路径
            self.news_dir = r"C:\Users\Administrator\Desktop\news_analyzer\data\news"
            if not os.path.exists(self.news_dir):
                # 如果仍不存在，创建该目录
                try:
                    os.makedirs(self.news_dir, exist_ok=True)
                except Exception as e:
                    self.logger.error(f"创建目录失败: {str(e)}")
        
        self.logger.info(f"历史新闻目录: {self.news_dir}")
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 标题标签
        title_label = QLabel("历史新闻")
        title_label.setStyleSheet("""
            font-weight: bold; 
            font-size: 16px; 
            color: #1976D2;
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
        """)
        layout.addWidget(title_label)
        
        # 创建标签页控件
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane { 
                border: 1px solid #cccccc; 
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #f8f8f8;
                border: 1px solid #cccccc;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 6px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover {
                background-color: #f0f0f0;
            }
        """)
        
        # 创建浏览标签页
        browse_tab = QWidget()
        self._setup_browse_tab(browse_tab)
        tab_widget.addTab(browse_tab, "浏览历史")
        
        # 创建导入/导出标签页
        import_tab = QWidget()
        self._setup_import_tab(import_tab)
        tab_widget.addTab(import_tab, "导入/导出")
        
        layout.addWidget(tab_widget, 1)  # 占据主要空间
        
        # 更新状态标签样式
        self.status_label.setStyleSheet("color: #757575;")
        layout.addWidget(self.status_label)
    
    def _setup_browse_tab(self, tab):
        """设置浏览历史标签页"""
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 10, 0, 0)
        
        # 控制面板
        control_layout = QHBoxLayout()
        
        # 创建时间范围选择下拉框
        self.time_range = QComboBox()
        self.time_range.addItem("全部时间")
        self.time_range.addItem("今天")
        self.time_range.addItem("本周")
        self.time_range.addItem("本月")
        self.time_range.setStyleSheet("""
            QComboBox {
                border: 1px solid #BDBDBD;
                border-radius: 4px;
                padding: 4px 8px;
                min-width: 100px;
                background-color: white;
            }
        """)
        control_layout.addWidget(QLabel("时间范围:"))
        control_layout.addWidget(self.time_range)
        
        # 刷新按钮
        self.refresh_button = QPushButton("刷新列表")
        self.refresh_button.setFixedSize(100, 30)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #ECEFF1;
                border: 1px solid #CFD8DC;
                border-radius: 4px;
                padding: 4px 8px;
                color: #455A64;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #CFD8DC;
            }
        """)
        self.refresh_button.clicked.connect(self._refresh_history_list)
        control_layout.addWidget(self.refresh_button)
        
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # 创建分割器 - 左侧是历史文件列表，右侧是预览
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧历史文件列表
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.history_list = QListWidget()
        self.history_list.setAlternatingRowColors(True)
        self.history_list.itemClicked.connect(self._on_history_selected)
        self.history_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                background-color: white;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #F5F5F5;
            }
            QListWidget::item:selected {
                background-color: #E3F2FD;
                color: #1976D2;
            }
        """)
        left_layout.addWidget(self.history_list)
        
        # 右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 新闻计数和信息标签
        self.info_label = QLabel("请选择历史文件")
        self.info_label.setStyleSheet("color: #757575; font-style: italic;")
        right_layout.addWidget(self.info_label)
        
        # 新闻列表
        self.news_list = QListWidget()
        self.news_list.setAlternatingRowColors(True)
        self.news_list.itemClicked.connect(self._on_news_selected)
        self.news_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                background-color: white;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:selected {
                background-color: #E3F2FD;
            }
        """)
        right_layout.addWidget(self.news_list, 2)  # 新闻列表占2/3空间
        
        # 新闻详情预览
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        self.preview.setStyleSheet("""
            QTextBrowser {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                background-color: white;
                padding: 10px;
            }
        """)
        right_layout.addWidget(self.preview, 1)  # 预览占1/3空间
        
        # 加载数据到主界面的按钮
        load_button = QPushButton("加载到主界面")
        load_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1E88E5;
            }
        """)
        load_button.clicked.connect(self._load_to_main)
        right_layout.addWidget(load_button)
        
        # 添加进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
            }
        """)
        right_layout.addWidget(self.progress_bar)
        
        # 设置面板到分割器
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        
        # 设置初始宽度比例（左:右 = 1:2）
        splitter.setSizes([1, 2])
        
        layout.addWidget(splitter)
    
    def _setup_import_tab(self, tab):
        """设置导入/导出标签页"""
        layout = QVBoxLayout(tab)
        
        # 添加说明文字
        instr_label = QLabel("在此页面中，您可以导入外部JSON新闻文件或导出现有新闻数据。")
        instr_label.setWordWrap(True)
        instr_label.setStyleSheet("font-size: 14px; margin-bottom: 15px;")
        layout.addWidget(instr_label)
        
        # 导入部分
        import_group = QFrame()
        import_group.setFrameShape(QFrame.StyledPanel)
        import_group.setStyleSheet("""
            QFrame {
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                background-color: #F5F5F5;
                margin-bottom: 15px;
                padding: 15px;
            }
        """)
        import_layout = QVBoxLayout(import_group)
        
        import_title = QLabel("导入JSON新闻文件")
        import_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #1976D2;")
        import_layout.addWidget(import_title)
        
        import_desc = QLabel("选择一个JSON文件导入到系统。文件应包含新闻条目列表。")
        import_desc.setWordWrap(True)
        import_layout.addWidget(import_desc)
        
        import_button = QPushButton("选择并导入JSON文件")
        import_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
                padding: 10px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #1E88E5;
            }
        """)
        import_button.clicked.connect(self._import_news_file)
        import_layout.addWidget(import_button)
        
        # 导出部分
        export_group = QFrame()
        export_group.setFrameShape(QFrame.StyledPanel)
        export_group.setStyleSheet("""
            QFrame {
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                background-color: #F5F5F5;
                padding: 15px;
            }
        """)
        export_layout = QVBoxLayout(export_group)
        
        export_title = QLabel("导出新闻数据")
        export_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #1976D2;")
        export_layout.addWidget(export_title)
        
        export_desc = QLabel("选择并导出系统中的历史新闻数据。")
        export_desc.setWordWrap(True)
        export_layout.addWidget(export_desc)
        
        # 创建历史文件下拉选择框
        self.export_combo = QComboBox()
        self.export_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #BDBDBD;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
            }
        """)
        export_layout.addWidget(self.export_combo)
        
        # 加载下拉框选项
        self._refresh_export_combo()
        
        # 刷新和导出按钮
        button_layout = QHBoxLayout()
        
        refresh_export_button = QPushButton("刷新列表")
        refresh_export_button.setStyleSheet("""
            QPushButton {
                background-color: #ECEFF1;
                border: 1px solid #CFD8DC;
                border-radius: 4px;
                padding: 8px;
                color: #455A64;
            }
        """)
        refresh_export_button.clicked.connect(self._refresh_export_combo)
        button_layout.addWidget(refresh_export_button)
        
        export_button = QPushButton("导出所选文件")
        export_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1E88E5;
            }
        """)
        export_button.clicked.connect(self._export_selected_file)
        button_layout.addWidget(export_button)
        
        export_layout.addLayout(button_layout)
        
        # 添加到主布局
        layout.addWidget(import_group)
        layout.addWidget(export_group)
        layout.addStretch()
    
    def _refresh_export_combo(self):
        """刷新导出文件下拉框"""
        self.export_combo.clear()
        
        try:
            # 确保目录存在
            if not os.path.exists(self.news_dir):
                return
                
            # 获取所有JSON文件
            files = [f for f in os.listdir(self.news_dir) if f.endswith('.json')]
            files.sort(reverse=True)  # 最新的文件排在前面
            
            for filename in files:
                try:
                    # 从文件名提取日期时间
                    if filename.startswith("news_") and filename.endswith(".json"):
                        date_str = filename.replace("news_", "").replace(".json", "")
                        date_time = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                        display_text = f"{date_time.strftime('%Y-%m-%d %H:%M:%S')} ({filename})"
                    else:
                        display_text = filename
                        
                    self.export_combo.addItem(display_text, filename)
                except:
                    self.export_combo.addItem(filename, filename)
            
            if self.export_combo.count() > 0:
                self.status_label.setText(f"找到 {self.export_combo.count()} 个可导出文件")
            else:
                self.status_label.setText("未找到可导出文件")
                
        except Exception as e:
            self.status_label.setText(f"加载文件列表失败: {str(e)}")
    
    def _refresh_history_list(self):
        """刷新历史文件列表"""
        self.history_list.clear()
        
        try:
            # 确保数据目录存在
            if not os.path.exists(self.news_dir):
                try:
                    os.makedirs(self.news_dir, exist_ok=True)
                except Exception as e:
                    self.status_label.setText(f"创建目录失败: {str(e)}")
                    return
                    
            # 获取所有JSON文件
            history_files = []
            for filename in os.listdir(self.news_dir):
                if filename.endswith('.json'):
                    history_files.append(filename)
            
            # 按时间排序
            history_files.sort(reverse=True)
            
            if not history_files:
                self.status_label.setText("没有找到历史新闻文件")
                return
            
            # 添加到列表，显示更友好的日期格式
            for filename in history_files:
                try:
                    # 从文件名提取日期时间（格式：news_YYYYMMDD_HHMMSS.json）
                    if filename.startswith("news_") and filename.endswith(".json"):
                        date_str = filename.replace("news_", "").replace(".json", "")
                        date_time = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                        display_text = date_time.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        display_text = filename
                    
                    item = QListWidgetItem(display_text)
                    item.setData(Qt.UserRole, filename)  # 存储实际文件名
                    self.history_list.addItem(item)
                except:
                    # 如果无法解析日期，直接使用文件名
                    item = QListWidgetItem(filename)
                    item.setData(Qt.UserRole, filename)
                    self.history_list.addItem(item)
            
            self.status_label.setText(f"共找到 {len(history_files)} 个历史文件")
            self.logger.info(f"刷新历史文件列表，找到 {len(history_files)} 个文件")
            
        except Exception as e:
            self.status_label.setText(f"加载历史文件失败: {str(e)}")
            self.logger.error(f"加载历史文件失败: {str(e)}")
    
    def _on_history_selected(self, item):
        """处理历史文件选择事件"""
        # 获取文件名
        filename = item.data(Qt.UserRole)
        
        # 构建完整文件路径
        file_path = os.path.join(self.news_dir, filename)
        
        # 加载该文件中的新闻
        try:
            # 直接从文件读取内容
            with open(file_path, 'r', encoding='utf-8') as f:
                news_items = json.load(f)
            
            # 清空新闻列表和预览
            self.news_list.clear()
            self.preview.clear()
            
            if not news_items:
                self.info_label.setText(f"文件 {filename} 中没有新闻")
                return
            
            # 更新信息标签
            self.info_label.setText(f"文件 {filename} 中包含 {len(news_items)} 条新闻")
            
            # 添加新闻到列表
            for news in news_items:
                title = news.get('title', '无标题')
                source = news.get('source_name', '未知来源')
                pub_date = news.get('pub_date', '')
                
                # 创建列表项
                list_item = QListWidgetItem(f"{title}\n{source} - {pub_date}")
                list_item.setData(Qt.UserRole, news)  # 存储完整新闻数据
                self.news_list.addItem(list_item)
            
            self.status_label.setText(f"已加载 {len(news_items)} 条历史新闻")
            self.logger.info(f"从文件 {filename} 加载了 {len(news_items)} 条新闻")
            
        except Exception as e:
            self.info_label.setText(f"加载文件失败: {str(e)}")
            self.status_label.setText("加载失败")
            self.logger.error(f"加载历史新闻失败: {str(e)}")
    
    def _on_news_selected(self, item):
        """处理新闻选择事件"""
        # 获取新闻数据
        news_data = item.data(Qt.UserRole)
        
        # 更新预览
        title = news_data.get('title', '无标题')
        source = news_data.get('source_name', '未知来源')
        date = news_data.get('pub_date', '未知日期')
        description = news_data.get('description', '无内容')
        link = news_data.get('link', '')
        
        # 创建HTML内容
        html = f"""
        <div style='font-family: "Segoe UI", "Microsoft YaHei", sans-serif;'>
            <h2 style='color: #1976D2;'>{title}</h2>
            <p><strong>来源:</strong> {source} | <strong>日期:</strong> {date}</p>
            <hr style='border: 1px solid #E0E0E0;'>
            <p>{description}</p>
        """
        
        if link:
            html += f'<p><a href="{link}" style="color: #1976D2; text-decoration: none;" target="_blank">阅读原文</a></p>'
        
        html += "</div>"
        
        # 设置HTML内容
        self.preview.setHtml(html)
    
    def _load_to_main(self):
        """将选中的历史新闻加载到主界面"""
        # 检查是否有选中的历史文件
        if self.history_list.currentItem() is None:
            QMessageBox.warning(self, "提示", "请先选择一个历史文件")
            return
        
        # 获取文件名
        filename = self.history_list.currentItem().data(Qt.UserRole)
        file_path = os.path.join(self.news_dir, filename)
        
        # 加载该文件中的新闻
        try:
            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # 直接从文件读取
            with open(file_path, 'r', encoding='utf-8') as f:
                news_items = json.load(f)
            
            # 更新进度
            self.progress_bar.setValue(50)
            
            if not news_items:
                self.progress_bar.setVisible(False)
                QMessageBox.information(self, "提示", "所选文件不包含新闻数据")
                return
            
            # 发送加载完成信号
            self.history_loaded.emit(news_items)
            
            # 完成进度
            self.progress_bar.setValue(100)
            
            self.status_label.setText(f"已将 {len(news_items)} 条新闻加载到主界面")
            self.logger.info(f"将历史文件 {filename} 中的 {len(news_items)} 条新闻加载到主界面")
            
            # 显示成功消息
            QMessageBox.information(self, "加载成功", f"已成功加载 {len(news_items)} 条历史新闻到主界面")
            
            # 隐藏进度条
            self.progress_bar.setVisible(False)
            
        except Exception as e:
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "加载失败", f"加载历史新闻失败: {str(e)}")
            self.status_label.setText("加载失败")
            self.logger.error(f"加载历史新闻到主界面失败: {str(e)}")
    
    def _import_news_file(self):
        """导入外部新闻文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入新闻文件", "", "JSON Files (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                news_items = json.load(f)
            
            if not isinstance(news_items, list):
                QMessageBox.warning(self, "格式错误", "文件格式不正确，应为新闻条目列表")
                return
            
            # 生成新的文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"news_{timestamp}.json"
            new_path = os.path.join(self.news_dir, new_filename)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            
            # 保存到数据目录
            with open(new_path, 'w', encoding='utf-8') as f:
                json.dump(news_items, f, ensure_ascii=False, indent=2)
            
            # 刷新列表
            self._refresh_history_list()
            self._refresh_export_combo()
            
            # 显示成功消息
            QMessageBox.information(
                self, "导入成功", 
                f"成功导入 {len(news_items)} 条新闻\n保存为 {new_filename}"
            )
            
            self.status_label.setText(f"已导入 {len(news_items)} 条新闻")
            
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"导入新闻文件失败: {str(e)}")
            self.logger.error(f"导入新闻文件失败: {str(e)}")
    
    def _export_selected_file(self):
        """导出当前选中的文件"""
        # 检查是否有选中的文件
        if self.export_combo.count() == 0:
            QMessageBox.warning(self, "提示", "没有可导出的文件")
            return
            
        # 获取文件名
        selected_index = self.export_combo.currentIndex()
        if selected_index < 0:
            QMessageBox.warning(self, "提示", "请选择要导出的文件")
            return
            
        filename = self.export_combo.itemData(selected_index)
        display_name = self.export_combo.currentText()
        
        # 构建完整文件路径
        file_path = os.path.join(self.news_dir, filename)
        
        # 选择保存路径
        export_path, _ = QFileDialog.getSaveFileName(
            self, "导出新闻", filename, "JSON Files (*.json)"
        )
        
        if not export_path:
            return
        
        try:
            # 直接复制文件
            with open(file_path, 'r', encoding='utf-8') as src_file:
                news_items = json.load(src_file)
                
            with open(export_path, 'w', encoding='utf-8') as dst_file:
                json.dump(news_items, dst_file, ensure_ascii=False, indent=2)
            
            QMessageBox.information(
                self, "导出成功", 
                f"成功导出 {len(news_items)} 条新闻到:\n{export_path}"
            )
            
            self.status_label.setText(f"已导出 {len(news_items)} 条新闻")
            self.logger.info(f"已将 {len(news_items)} 条新闻导出到 {export_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出新闻失败: {str(e)}")
            self.status_label.setText("导出失败")
            self.logger.error(f"导出新闻失败: {str(e)}")