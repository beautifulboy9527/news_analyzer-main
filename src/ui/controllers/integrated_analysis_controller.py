# src/ui/controllers/integrated_analysis_controller.py
"""
新闻分析整合面板控制器

负责协调新闻数据处理器、分析引擎和UI组件之间的交互，
实现MVC架构，提高代码可维护性和可测试性。
"""

import logging
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime

from PySide6.QtWidgets import QMessageBox, QApplication, QFileDialog
from PySide6.QtCore import QObject, Signal, Slot

from src.storage.news_storage import NewsStorage
from src.llm.llm_service import LLMService
from src.core.news_data_processor import NewsDataProcessor
from src.core.news_analysis_engine import NewsAnalysisEngine
from src.ui.components.analysis_panel_components import NewsListManager, CategoryTreeManager, GroupTreeManager
from src.ui.news_detail_dialog import NewsDetailDialog
from src.models import NewsArticle


class IntegratedAnalysisController(QObject):
    """
    新闻分析整合面板控制器，负责协调数据处理、分析和UI交互
    """
    
    # 定义信号
    data_loaded = Signal(list)  # 数据加载完成信号
    analysis_started = Signal()  # 分析开始信号
    analysis_completed = Signal(dict)  # 分析完成信号
    analysis_failed = Signal(str)  # 分析失败信号
    progress_updated = Signal(int, int)  # 进度更新信号
    
    def __init__(self, storage: NewsStorage, llm_service: LLMService, parent=None):
        """
        初始化控制器
        
        Args:
            storage: 新闻存储服务
            llm_service: LLM服务
            parent: 父对象
        """
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.controllers.integrated_analysis_controller')
        
        # 服务和处理器
        self.storage = storage
        self.llm_service = llm_service
        self.data_processor = NewsDataProcessor(storage)
        self.analysis_engine = NewsAnalysisEngine(llm_service, self.data_processor)
        
        # 数据容器
        self.all_news_items: List[Dict] = []
        self.selected_news_items: List[Dict] = []
        self.current_category = "all"  # 当前选中的类别
        self.current_group_items = []  # 当前组内的新闻项
        
        # 提示词管理相关
        self.current_template_name = ""  # 当前选择的提示词模板名称
        self.current_template_content = ""  # 当前选择的提示词模板内容
        
        # UI组件管理器
        self.news_list_manager = None
        self.category_tree_manager = None
        self.group_tree_manager = None
    
    def set_ui_managers(self, news_list_manager: NewsListManager, 
                       category_tree_manager: CategoryTreeManager,
                       group_tree_manager: GroupTreeManager):
        """
        设置UI组件管理器
        
        Args:
            news_list_manager: 新闻列表管理器
            category_tree_manager: 分类树管理器
            group_tree_manager: 分组树管理器
        """
        self.news_list_manager = news_list_manager
        self.category_tree_manager = category_tree_manager
        self.group_tree_manager = group_tree_manager
    
    def load_news_data(self):
        """
        加载新闻数据
        """
        try:
            # 使用数据处理器加载数据
            self.all_news_items = self.data_processor.load_news_data()
            
            if not self.all_news_items:
                QMessageBox.information(None, "提示", "没有找到新闻数据")
                return
            
            # 更新UI
            if self.category_tree_manager:
                self.category_tree_manager.populate_category_tree(
                    len(self.all_news_items),
                    self.data_processor.categorized_news
                )
            
            if self.news_list_manager:
                self.news_list_manager.populate_news_list(self.all_news_items)
            
            # 设置当前组内新闻
            self.current_group_items = self.all_news_items
            
            # 发送数据加载完成信号
            self.data_loaded.emit(self.all_news_items)
            
        except Exception as e:
            self.logger.error(f"加载新闻数据时出错: {e}", exc_info=True)
            QMessageBox.critical(None, "错误", f"加载新闻数据失败: {e}")
    
    def on_category_selected(self, category_id: str):
        """
        处理分类选择事件
        
        Args:
            category_id: 类别ID
        """
        self.current_category = category_id
        
        # 获取选中类别的新闻
        news_items = self.data_processor.get_news_by_category(category_id)
        self.current_group_items = news_items
        
        # 更新新闻列表
        if self.news_list_manager:
            self.news_list_manager.populate_news_list(news_items)
    
    def on_news_selection_changed(self, indices: List[int]):
        """
        处理新闻选择变化事件
        
        Args:
            indices: 选中的新闻索引列表
        """
        self.selected_news_items = []
        
        for index in indices:
            if 0 <= index < len(self.all_news_items):
                self.selected_news_items.append(self.all_news_items[index])
        
        self.logger.debug(f"已选择 {len(self.selected_news_items)} 条新闻")
    
    def on_group_selection_changed(self, indices: List[int]):
        """
        处理分组树选择变化事件
        
        Args:
            indices: 选中的新闻索引列表
        """
        self.selected_news_items = []
        
        for index in indices:
            if 0 <= index < len(self.all_news_items):
                self.selected_news_items.append(self.all_news_items[index])
        
        self.logger.debug(f"已选择 {len(self.selected_news_items)} 条新闻")
    
    def auto_group_news(self, method: str = "title_similarity"):
        """
        自动分组新闻
        
        Args:
            method: 分组方法，'title_similarity'或'multi_feature'
        """
        if not self.current_group_items:
            QMessageBox.information(None, "提示", "当前类别下没有可分组的新闻数据")
            return
        
        try:
            # 显示进度开始
            self.analysis_started.emit()
            
            # 使用数据处理器进行分组
            groups = self.data_processor.auto_group_news(self.current_group_items, method)
            
            if not groups:
                QMessageBox.information(None, "分组结果", "未找到相似度足够高的新闻组。")
                return
            
            # 更新分组树
            if self.group_tree_manager:
                self.group_tree_manager.populate_group_tree(groups, self.all_news_items)
            
            # 生成简要分析结果文本
            result_text = f"已自动分组 {len(groups)} 组相关新闻。\n\n"
            result_text += "请在左侧\"分组视图\"标签页中查看详细分组结果，\n"
            result_text += "选择感兴趣的新闻组后点击\"开始分析\"按钮进行深度分析。"
            
            # 发送分析完成信号
            self.analysis_completed.emit({"analysis": result_text})
            
            QMessageBox.information(None, "分组完成", f"已自动分组 {len(groups)} 组相关新闻，请在分组视图中查看。")
            
        except Exception as e:
            self.logger.error(f"自动分组新闻时出错: {e}", exc_info=True)
            self.analysis_failed.emit(f"自动分组新闻失败: {e}")
            QMessageBox.critical(None, "错误", f"自动分组新闻失败: {e}")
    
    def analyze_selected_news(self, analysis_type: str):
        """
        分析选中的新闻
        
        Args:
            analysis_type: 分析类型
        """
        if not self.selected_news_items:
            QMessageBox.information(None, "提示", "请先选择要分析的新闻")
            return
            
        if not self.llm_service:
            QMessageBox.critical(None, "错误", "LLM服务不可用，无法进行AI分析")
            return
        
        try:
            # 发送分析开始信号
            self.analysis_started.emit()
            
            # 使用自定义提示词（如果有）
            custom_prompt = None
            if self.current_template_name and self.current_template_content:
                custom_prompt = self.current_template_content
            
            # 使用分析引擎进行分析
            result = self.analysis_engine.analyze_news(
                news_items=self.selected_news_items,
                analysis_type=analysis_type,
                custom_prompt=custom_prompt
            )
            
            if "error" in result:
                self.analysis_failed.emit(result["error"])
                QMessageBox.critical(None, "分析失败", result["error"])
                return
            
            # 构建更结构化的分析结果显示
            analysis_text = result.get('analysis', '')
            
            # 添加分类和分组信息
            categories = set(self.data_processor.get_news_categories(self.selected_news_items))
            sources = set(news.get('source_name') for news in self.selected_news_items if news.get('source_name'))
            titles = [news.get('title') for news in self.selected_news_items if news.get('title')]
            
            # 添加元数据到分析结果
            formatted_text = f"分析类型: {analysis_type}\n"
            
            # 添加使用的提示词模板信息
            if self.current_template_name:
                formatted_text += f"使用模板: {self.current_template_name}\n"
                
            formatted_text += f"新闻数量: {len(self.selected_news_items)}\n"
            if categories:
                formatted_text += f"涉及分类: {', '.join(categories)}\n"
            if sources:
                formatted_text += f"新闻来源: {', '.join(sources)}\n"
            formatted_text += "\n" + analysis_text
            
            # 更新结果
            result["formatted_text"] = formatted_text
            
            # 发送分析完成信号
            self.analysis_completed.emit(result)
            
        except Exception as e:
            self.logger.error(f"分析新闻时出错: {e}", exc_info=True)
            self.analysis_failed.emit(f"分析新闻失败: {e}")
            QMessageBox.critical(None, "错误", f"分析新闻失败: {e}")
    
    def on_prompt_selected(self, template_name: str, template_content: str):
        """
        处理提示词模板选择事件
        
        Args:
            template_name: 模板名称
            template_content: 模板内容
        """
        self.logger.debug(f"已选择提示词模板: {template_name}")
        
        # 存储当前选择的模板信息，以便在分析时使用
        self.current_template_name = template_name
        self.current_template_content = template_content
    
    def on_prompt_edited(self, edited_content: str):
        """
        处理提示词内容编辑事件
        
        Args:
            edited_content: 编辑后的提示词内容
        """
        self.logger.debug("提示词内容已被编辑")
        
        # 更新当前模板内容
        self.current_template_content = edited_content
    
    def show_news_detail(self, news_index: int):
        """
        显示新闻详情
        
        Args:
            news_index: 新闻索引
        """
        if 0 <= news_index < len(self.all_news_items):
            news = self.all_news_items[news_index]
            
            # 转换为NewsArticle对象
            # 处理publish_time字段，确保类型正确
            publish_time = news.get('publish_time')
            if publish_time and not isinstance(publish_time, datetime):
                # 如果是字符串，保持原样，NewsDetailDialog会处理
                publish_time = publish_time
            elif not publish_time:
                publish_time = datetime.now()
            
            article = NewsArticle(
                title=news.get('title', '无标题'),
                content=news.get('content', ''),
                summary=news.get('summary', ''),
                link=news.get('link', ''),
                source_name=news.get('source_name', '未知来源'),
                publish_time=publish_time
            )
            
            dialog = NewsDetailDialog(article, None)
            dialog.show()
    
    def copy_result_to_clipboard(self, text: str):
        """
        复制分析结果到剪贴板
        
        Args:
            text: 要复制的文本
        """
        if text:
            QApplication.clipboard().setText(text)
            self.logger.info("已复制分析结果到剪贴板")
    
    def save_result_to_file(self, text: str):
        """
        保存分析结果到文件
        
        Args:
            text: 要保存的文本
        """
        if not text:
            return
        
        try:
            # 获取保存路径
            file_path, _ = QFileDialog.getSaveFileName(
                None, "保存分析结果", "", "文本文件 (*.txt);;所有文件 (*)"
            )
            
            if not file_path:
                return  # 用户取消
            
            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            self.logger.info(f"已保存分析结果到文件: {file_path}")
            QMessageBox.information(None, "保存成功", f"已保存分析结果到文件: {file_path}")
            
        except Exception as e:
            self.logger.error(f"保存分析结果到文件时出错: {e}", exc_info=True)
            QMessageBox.critical(None, "保存失败", f"保存分析结果到文件失败: {e}")