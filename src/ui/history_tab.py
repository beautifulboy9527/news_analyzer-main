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
                             QMessageBox, QFileDialog, QProgressBar)
from PyQt5.QtCore import Qt, pyqtSignal, QSize


class HistoryPanel(QWidget):
    """历史新闻面板组件"""
    
    # 自定义信号：历史新闻加载完成
    history_loaded = pyqtSignal(list)
    
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        
        self.logger = logging.getLogger('news_analyzer.ui.history_panel')
        self.storage = storage
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # 顶部标题和按钮
        header_layout = QHBoxLayout()
        
        # 标题标签
        title_label = QLabel("历史新闻")
        title_label.setStyleSheet("""
            font-weight: bold; 
            font-size: 16px; 
            color: #1976D2;
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
        """)
        header_layout.addWidget(title_label)
        
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
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #BDBDBD;
            }
        """)
        header_layout.addWidget(self.time_range)
        
        # 刷新按钮
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.setFixedSize(80, 30)
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
            QPushButton:pressed {
                background-color: #B0BEC5;
            }
        """)
        self.refresh_button.clicked.connect(self._refresh_history_list)
        header_layout.addWidget(self.refresh_button)
        
        # 导入按钮
        self.import_button = QPushButton("导入")
        self.import_button.setFixedSize(80, 30)
        self.import_button.setStyleSheet("""
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
            QPushButton:pressed {
                background-color: #B0BEC5;
            }
        """)
        self.import_button.clicked.connect(self._import_news_file)
        header_layout.addWidget(self.import_button)
        
        # 导出按钮
        self.export_button = QPushButton("导出")
        self.export_button.setFixedSize(80, 30)
        self.export_button.setStyleSheet("""
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
            QPushButton:pressed {
                background-color: #B0BEC5;
            }
        """)
        self.export_button.clicked.connect(self._export_current_news)
        header_layout.addWidget(self.export_button)
        
        layout.addLayout(header_layout)
        
        # 创建分割器 - 左侧是历史文件列表，右侧是预览
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧历史文件列表
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 历史文件列表
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
            QListWidget::item:hover {
                background-color: #F5F5F5;
            }
        """)
        left_layout.addWidget(self.history_list)
        
        # 右侧新闻预览
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
                border-bottom: 1px solid #F5F5F5;
            }
            QListWidget::item:selected {
                background-color: #E3F2FD;
                color: #1976D2;
            }
            QListWidget::item:hover {
                background-color: #F5F5F5;
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
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
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
            QPushButton:pressed {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
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
                background-color: #F5F5F5;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                width: 10px;
            }
        """)
        right_layout.addWidget(self.progress_bar)
        
        # 设置面板到分割器
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        
        # 设置初始宽度比例（左:右 = 1:2）
        splitter.setSizes([1, 2])
        
        layout.addWidget(splitter)
        
        # 加载历史文件列表
        self._refresh_history_list()
        
        # 添加状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #757575;")
        layout.addWidget(self.status_label)
    
    def _refresh_history_list(self):
        """刷新历史文件列表"""
        self.history_list.clear()
        
        try:
            # 获取所有历史文件
            history_files = self.storage.list_news_files()
            
            if not history_files:
                self.status_label.setText("没有找到历史新闻文件")
                return
            
            # 添加到列表，显示更友好的日期格式
            for filename in history_files:
                try:
                    # 从文件名提取日期时间（格式：news_YYYYMMDD_HHMMSS.json）
                    date_str = filename.replace("news_", "").replace(".json", "")
                    date_time = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                    display_text = date_time.strftime("%Y-%m-%d %H:%M:%S")
                    
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
        
        # 加载该文件中的新闻
        try:
            news_items = self.storage.load_news(filename)
            
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
        
        # 加载该文件中的新闻
        try:
            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # 加载新闻
            news_items = self.storage.load_news(filename)
            
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
            
            # 保存到数据存储
            saved_path = self.storage.save_news(news_items)
            
            if saved_path:
                # 刷新列表
                self._refresh_history_list()
                
                # 显示成功消息
                QMessageBox.information(
                    self, "导入成功", 
                    f"成功导入 {len(news_items)} 条新闻\n保存为 {os.path.basename(saved_path)}"
                )
            else:
                QMessageBox.warning(self, "导入失败", "保存导入的新闻失败")
            
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"导入新闻文件失败: {str(e)}")
            self.logger.error(f"导入新闻文件失败: {str(e)}")
    
    def _export_current_news(self):
        """导出当前选中的新闻集"""
        # 检查是否有选中的历史文件
        if self.history_list.currentItem() is None:
            QMessageBox.warning(self, "提示", "请先选择一个历史文件")
            return
        
        # 获取文件名
        filename = self.history_list.currentItem().data(Qt.UserRole)
        display_name = self.history_list.currentItem().text()
        
        # 选择保存路径
        export_path, _ = QFileDialog.getSaveFileName(
            self, "导出新闻", display_name + ".json", "JSON Files (*.json)"
        )
        
        if not export_path:
            return
        
        try:
            # 获取新闻数据
            news_items = self.storage.load_news(filename)
            
            if not news_items:
                QMessageBox.warning(self, "导出失败", "所选文件不包含新闻数据")
                return
            
            # 保存到选定路径
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(news_items, f, ensure_ascii=False, indent=2)
            
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
