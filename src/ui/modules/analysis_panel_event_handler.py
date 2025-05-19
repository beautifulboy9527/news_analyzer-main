# src/ui/modules/analysis_panel_event_handler.py
"""
分析面板事件处理器

负责新闻分析整合面板的事件处理，
连接UI组件与数据管理器，实现交互逻辑。
"""

import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

from PySide6.QtWidgets import QMessageBox, QFileDialog, QMenu
from PySide6.QtCore import QObject, Slot, Qt, QPoint
from PySide6.QtGui import QCursor, QAction

from src.storage.news_storage import NewsStorage
from src.llm.llm_service import LLMService
from src.ui.modules.analysis_panel_data_manager import AnalysisPanelDataManager
from src.ui.news_detail_dialog import NewsDetailDialog


class AnalysisPanelEventHandler(QObject):
    """
    分析面板事件处理器，负责处理UI事件和连接UI组件与数据管理器
    """
    
    def __init__(self, panel, data_manager: AnalysisPanelDataManager, 
                 storage: NewsStorage, llm_service: LLMService):
        """
        初始化事件处理器
        
        Args:
            panel: 父面板实例
            data_manager: 数据管理器
            storage: 新闻存储服务
            llm_service: LLM服务
        """
        super().__init__()
        self.panel = panel
        self.data_manager = data_manager
        self.storage = storage
        self.llm_service = llm_service
        self.logger = logging.getLogger('news_analyzer.ui.modules.analysis_panel_event_handler')
        
        # 获取UI组件引用
        self.ui_components = self.panel.ui_builder.get_ui_components()
        self.ui_managers = self.panel.ui_builder.get_managers()
    
    def connect_signals(self):
        """
        连接所有信号和槽
        """
        # 顶部控制区域
        self.ui_components["refresh_button"].clicked.connect(self._on_refresh_clicked)
        self.ui_components["analysis_type"].currentTextChanged.connect(self._on_analysis_type_changed)
        self.ui_components["analyze_button"].clicked.connect(self._on_analyze_clicked)
        
        # 左侧面板
        self.ui_components["category_tree"].itemClicked.connect(self._on_category_selected)
        self.ui_components["news_list"].itemSelectionChanged.connect(self._on_selection_changed)
        self.ui_components["news_list"].itemDoubleClicked.connect(self._on_news_double_clicked)
        self.ui_components["news_list"].customContextMenuRequested.connect(self._show_context_menu)
        
        self.ui_components["news_tab"].currentChanged.connect(self._on_tab_changed)
        
        self.ui_components["group_tree"].itemSelectionChanged.connect(self._on_group_selection_changed)
        self.ui_components["group_tree"].customContextMenuRequested.connect(self._show_group_context_menu)
        self.ui_components["group_tree"].itemDoubleClicked.connect(self._on_group_item_double_clicked)
        
        self.ui_components["select_all_button"].clicked.connect(self._select_all_news)
        self.ui_components["deselect_all_button"].clicked.connect(self._deselect_all_news)
        self.ui_components["auto_group_button"].clicked.connect(self._auto_group_news)
        
        # 右侧面板
        self.ui_components["prompt_manager_widget"].prompt_selected.connect(self._on_prompt_selected)
        self.ui_components["prompt_manager_widget"].prompt_edited.connect(self._on_prompt_edited)
        
        # 底部按钮
        self.ui_components["export_button"].clicked.connect(self._export_analysis_result)
        self.ui_components["close_button"].clicked.connect(self.panel.close)
    
    def load_news_data(self):
        """
        加载新闻数据
        """
        try:
            # 显示进度条
            self.panel.progress_bar.setVisible(True)
            self.panel.progress_bar.setValue(10)
            
            # 使用数据管理器加载数据
            news_items = self.data_manager.load_news_data(self.storage)
            
            self.panel.progress_bar.setValue(50)
            
            if not news_items:
                QMessageBox.information(self.panel, "提示", "没有找到新闻数据")
                self.panel.progress_bar.setVisible(False)
                return
            
            # 更新UI
            self.ui_managers["category_tree_manager"].populate_category_tree(
                len(news_items),
                self.data_manager.categorized_news
            )
            
            self.ui_managers["news_list_manager"].populate_news_list(news_items)
            
            self.panel.progress_bar.setValue(100)
            self.panel.progress_bar.setVisible(False)
            
        except Exception as e:
            self.logger.error(f"加载新闻数据时出错: {e}", exc_info=True)
            QMessageBox.critical(self.panel, "错误", f"加载新闻数据失败: {e}")
            self.panel.progress_bar.setVisible(False)
    
    def _on_refresh_clicked(self):
        """
        处理刷新按钮点击事件
        """
        self.load_news_data()
    
    def _on_analysis_type_changed(self, analysis_type: str):
        """
        处理分析类型变更事件
        
        Args:
            analysis_type: 新的分析类型
        """
        # 可以在这里添加根据分析类型调整UI的逻辑
        self.logger.debug(f"分析类型已变更为: {analysis_type}")
    
    def _on_category_selected(self, item, column):
        """
        处理分类选择事件
        
        Args:
            item: 选中的树项
            column: 选中的列
        """
        category_id = item.data(0, Qt.UserRole)
        if not category_id:
            return
        
        self.data_manager.current_category = category_id
        
        # 获取选中类别的新闻
        news_items = self.data_manager.get_news_by_category(category_id)
        self.data_manager.current_group_items = news_items
        
        # 更新新闻列表
        self.ui_managers["news_list_manager"].populate_news_list(news_items)
        
        # 切换到普通列表标签页
        self.ui_components["news_tab"].setCurrentIndex(0)
    
    def _on_selection_changed(self):
        """
        处理新闻选择变化事件
        """
        # 获取选中的新闻索引
        indices = self.ui_managers["news_list_manager"].get_selected_news_indices()
        
        # 更新数据管理器中的选中新闻
        self.data_manager.set_selected_news(indices)
        
        # 更新分析按钮状态
        self.ui_components["analyze_button"].setEnabled(len(indices) > 0)
    
    def _on_group_selection_changed(self):
        """
        处理分组树选择变化事件
        """
        selected_items = self.ui_components["group_tree"].selectedItems()
        selected_news = []
        
        for item in selected_items:
            # 只处理子项（新闻项）
            if item.parent():
                news_index = item.data(0, Qt.UserRole)
                if isinstance(news_index, int) and 0 <= news_index < len(self.data_manager.all_news_items):
                    selected_news.append(self.data_manager.all_news_items[news_index])
        
        self.data_manager.selected_news_items = selected_news
        
        # 更新分析按钮状态
        self.ui_components["analyze_button"].setEnabled(len(selected_news) > 0)
    
    def _on_tab_changed(self, index):
        """
        处理标签页切换事件
        
        Args:
            index: 新的标签页索引
        """
        # 根据标签页更新选择按钮状态
        is_normal_list = (index == 0)
        
        self.ui_components["select_all_button"].setEnabled(is_normal_list)
        self.ui_components["deselect_all_button"].setEnabled(is_normal_list)
    
    def _select_all_news(self):
        """
        选择所有新闻
        """
        self.ui_managers["news_list_manager"].select_all_news()
    
    def _deselect_all_news(self):
        """
        取消选择所有新闻
        """
        self.ui_managers["news_list_manager"].deselect_all_news()
    
    def _auto_group_news(self):
        """
        自动分组新闻
        """
        if not self.data_manager.current_group_items:
            QMessageBox.information(self.panel, "提示", "当前类别下没有可分组的新闻数据")
            return
        
        try:
            # 显示进度条
            self.panel.progress_bar.setVisible(True)
            self.panel.progress_bar.setValue(10)
            
            # 获取分组方法
            method = self.ui_components["clustering_method"].currentData()
            
            # 使用数据管理器进行分组
            groups = self.data_manager.auto_group_news(method)
            
            self.panel.progress_bar.setValue(70)
            
            if not groups:
                QMessageBox.information(self.panel, "分组结果", "未找到相似度足够高的新闻组。")
                self.panel.progress_bar.setVisible(False)
                return
            
            # 更新分组树
            self.ui_managers["group_tree_manager"].populate_group_tree(groups, self.data_manager.all_news_items)
            
            # 生成简要分析结果文本
            result_text = f"已自动分组 {len(groups)} 组相关新闻。\n\n"
            result_text += "请在左侧\"分组视图\"标签页中查看详细分组结果，\n"
            result_text += "选择感兴趣的新闻组后点击\"开始分析\"按钮进行深度分析。"
            
            # 更新结果文本
            self.ui_components["result_edit"].setText(result_text)
            
            # 切换到分组视图标签页
            self.ui_components["news_tab"].setCurrentIndex(1)
            
            self.panel.progress_bar.setValue(100)
            self.panel.progress_bar.setVisible(False)
            
            QMessageBox.information(self.panel, "分组完成", f"已自动分组 {len(groups)} 组相关新闻，请在分组视图中查看。")
            
        except Exception as e:
            self.logger.error(f"自动分组新闻时出错: {e}", exc_info=True)
            QMessageBox.critical(self.panel, "错误", f"自动分组新闻失败: {e}")
            self.panel.progress_bar.setVisible(False)
    
    def _on_analyze_clicked(self):
        """
        处理分析按钮点击事件
        """
        if not self.data_manager.selected_news_items:
            QMessageBox.information(self.panel, "提示", "请先选择要分析的新闻")
            return
        
        try:
            # 显示进度条
            self.panel.progress_bar.setVisible(True)
            self.panel.progress_bar.setValue(10)
            
            # 获取分析类型
            analysis_type = self.ui_components["analysis_type"].currentText()
            
            # 使用数据管理器进行分析
            result = self.data_manager.analyze_news(self.llm_service, analysis_type)
            
            self.panel.progress_bar.setValue(90)
            
            if "error" in result:
                QMessageBox.warning(self.panel, "分析失败", result["error"])
                self.panel.progress_bar.setVisible(False)
                return
            
            # 更新结果文本
            self.ui_components["result_edit"].setText(result.get("analysis", "分析完成，但未返回结果文本。"))
            
            # 更新可视化组件
            if "importance" in result or "stance" in result:
                self.ui_components["analysis_visualizer"].update_visualization(
                    result.get("importance", 0),
                    result.get("stance", 0)
                )
            
            # 启用导出按钮
            self.ui_components["export_button"].setEnabled(True)
            
            # 发送分析完成信号
            self.panel.analysis_completed.emit(result)
            
            self.panel.progress_bar.setValue(100)
            self.panel.progress_bar.setVisible(False)
            
        except Exception as e:
            self.logger.error(f"分析新闻时出错: {e}", exc_info=True)
            QMessageBox.critical(self.panel, "错误", f"分析新闻失败: {e}")
            self.panel.progress_bar.setVisible(False)
    
    def _on_news_double_clicked(self, item):
        """
        处理新闻双击事件
        
        Args:
            item: 双击的列表项
        """
        index = item.data(Qt.UserRole)
        if not isinstance(index, int) or index < 0 or index >= len(self.data_manager.current_group_items):
            return
        
        news = self.data_manager.current_group_items[index]
        self._show_news_detail(news)
    
    def _on_group_item_double_clicked(self, item, column):
        """
        处理分组树项双击事件
        
        Args:
            item: 双击的树项
            column: 双击的列
        """
        # 只处理子项（新闻项）
        if not item.parent():
            return
        
        news_index = item.data(0, Qt.UserRole)
        if isinstance(news_index, int) and 0 <= news_index < len(self.data_manager.all_news_items):
            news = self.data_manager.all_news_items[news_index]
            self._show_news_detail(news)
    
    def _show_news_detail(self, news: Dict):
        """
        显示新闻详情对话框
        
        Args:
            news: 新闻数据
        """
        dialog = NewsDetailDialog(news, self.panel)
        dialog.exec()
    
    def _show_context_menu(self, pos: QPoint):
        """
        显示新闻列表上下文菜单
        
        Args:
            pos: 鼠标位置
        """
        item = self.ui_components["news_list"].itemAt(pos)
        if not item:
            return
        
        menu = QMenu(self.panel)
        
        view_action = QAction("查看详情", self.panel)
        view_action.triggered.connect(lambda: self._on_news_double_clicked(item))
        menu.addAction(view_action)
        
        menu.exec(QCursor.pos())
    
    def _show_group_context_menu(self, pos: QPoint):
        """
        显示分组树上下文菜单
        
        Args:
            pos: 鼠标位置
        """
        item = self.ui_components["group_tree"].itemAt(pos)
        if not item:
            return
        
        menu = QMenu(self.panel)
        
        # 只为子项（新闻项）添加查看详情选项
        if item.parent():
            view_action = QAction("查看详情", self.panel)
            view_action.triggered.connect(lambda: self._on_group_item_double_clicked(item, 0))
            menu.addAction(view_action)
        
        menu.exec(QCursor.pos())
    
    def _on_prompt_selected(self, template_name: str, template_content: str):
        """
        处理提示词模板选择事件
        
        Args:
            template_name: 模板名称
            template_content: 模板内容
        """
        self.data_manager.set_template(template_name, template_content)
    
    def _on_prompt_edited(self, content: str):
        """
        处理提示词内容编辑事件
        
        Args:
            content: 编辑后的内容
        """
        if self.data_manager.current_template_name:
            self.data_manager.current_template_content = content
    
    def _export_analysis_result(self):
        """
        导出分析结果
        """
        if not self.ui_components["result_edit"].toPlainText():
            QMessageBox.information(self.panel, "提示", "没有可导出的分析结果")
            return
        
        try:
            # 获取保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                self.panel,
                "导出分析结果",
                os.path.expanduser("~/Documents/新闻分析结果.txt"),
                "文本文件 (*.txt);;所有文件 (*)"
            )
            
            if not file_path:
                return
            
            # 准备导出内容
            content = "新闻分析结果\n"
            content += "=============\n\n"
            content += f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            content += f"分析类型: {self.ui_components['analysis_type'].currentText()}\n"
            content += f"分析新闻数: {len(self.data_manager.selected_news_items)}\n\n"
            
            # 添加新闻标题列表
            content += "分析的新闻:\n"
            for i, news in enumerate(self.data_manager.selected_news_items, 1):
                content += f"{i}. {news.get('title', '无标题')}\n"
            
            content += "\n分析结果:\n"
            content += "-------------\n"
            content += self.ui_components["result_edit"].toPlainText()
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            QMessageBox.information(self.panel, "导出成功", f"分析结果已导出到: {file_path}")
            
        except Exception as e:
            self.logger.error(f"导出分析结果时出错: {e}", exc_info=True)
            QMessageBox.critical(self.panel, "错误", f"导出分析结果失败: {e}")