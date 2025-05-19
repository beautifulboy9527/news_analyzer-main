"""
分析面板UI组件

提供新闻分析整合面板所需的UI组件和渲染逻辑，
将UI组件逻辑从主面板类中分离，提高代码可维护性。
"""

import logging
from typing import List, Dict, Optional, Callable, Any, Set
from datetime import datetime

from PySide6.QtWidgets import (QListWidget, QListWidgetItem, QTreeWidget, 
                             QTreeWidgetItem, QHeaderView, QMessageBox)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QIcon, QFont, QColor, QCursor, QAction

# Import should remain the same as both views and components are one level down from src
from ...collectors.categories import STANDARD_CATEGORIES


class NewsListManager:
    """
    新闻列表管理器，负责新闻列表的渲染和交互
    """
    
    def __init__(self, news_list: QListWidget):
        """
        初始化新闻列表管理器
        
        Args:
            news_list: 新闻列表控件
        """
        self.logger = logging.getLogger('news_analyzer.ui.views.news_list_manager') # Updated logger name
        self.news_list = news_list
        
    def populate_news_list(self, news_items: List[Dict]):
        """
        填充新闻列表控件
        
        Args:
            news_items: 新闻数据列表
        """
        self.news_list.clear()
        
        if not news_items:
            item = QListWidgetItem("该类别下没有新闻")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)  # 不可选
            self.news_list.addItem(item)
            return
        
        for i, news in enumerate(news_items):
            title = news.get('title', '无标题')
            source = news.get('source_name', '未知来源')
            
            # 尝试解析发布时间
            pub_time_str = ''
            pub_time = news.get('publish_time', '')
            if pub_time:
                if isinstance(pub_time, str):
                    try:
                        pub_time_dt = datetime.fromisoformat(pub_time)
                        pub_time_str = pub_time_dt.strftime('%Y-%m-%d %H:%M')
                    except (ValueError, TypeError):
                        pub_time_str = pub_time
                elif isinstance(pub_time, datetime):
                    pub_time_str = pub_time.strftime('%Y-%m-%d %H:%M')
            
            # 获取新闻分类（如果有）
            category_str = news.get('category_name', '')
            
            # 构建显示文本，使用更清晰的格式
            display_text = f"{title}"
            meta_info = []
            
            if source:
                meta_info.append(f"来源: {source}")
            if pub_time_str:
                meta_info.append(f"时间: {pub_time_str}")
            if category_str:
                meta_info.append(f"分类: {category_str}")
                
            if meta_info:
                display_text += f"\n{' | '.join(meta_info)}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, i)  # 存储索引以便后续获取完整数据
            
            # 为所有新闻项统一设置样式
            # 使用统一的浅色背景，确保视觉一致性
            item.setBackground(QColor(245, 245, 250))  # 统一的浅色背景
            
            # 设置统一的字体样式
            font = item.font()
            font.setPointSize(9)  # 统一字体大小
            item.setFont(font)
            
            # 设置统一的图标
            item.setIcon(QIcon.fromTheme("text-x-generic", QIcon("")))
            
            self.news_list.addItem(item)
    
    def select_all_news(self):
        """
        选择所有新闻
        """
        for i in range(self.news_list.count()):
            item = self.news_list.item(i)
            if item.flags() & Qt.ItemIsSelectable:  # 确保项目可选
                item.setSelected(True)
    
    def deselect_all_news(self):
        """
        取消选择所有新闻
        """
        self.news_list.clearSelection()
    
    def get_selected_news_indices(self) -> List[int]:
        """
        获取选中的新闻索引列表
        
        Returns:
            索引列表
        """
        indices = []
        for item in self.news_list.selectedItems():
            index = item.data(Qt.UserRole)
            if isinstance(index, int):
                indices.append(index)
        return indices


class CategoryTreeManager:
    """
    分类树管理器，负责分类树的渲染和交互
    """
    
    def __init__(self, category_tree: QTreeWidget):
        """
        初始化分类树管理器
        
        Args:
            category_tree: 分类树控件
        """
        self.logger = logging.getLogger('news_analyzer.ui.views.category_tree_manager') # Updated logger name
        self.category_tree = category_tree
    
    def populate_category_tree(self, all_news_count: int, categorized_news: Dict[str, List[Dict]]):
        """
        填充分类树控件
        
        Args:
            all_news_count: 所有新闻的数量
            categorized_news: 按类别分类的新闻字典
        """
        self.category_tree.clear()
        
        # 添加"所有新闻"
        all_item = QTreeWidgetItem(self.category_tree)
        all_item.setText(0, f"所有新闻 ({all_news_count})")
        all_item.setData(0, Qt.UserRole, "all")
        
        # 添加各个分类节点
        for category_id, news_list in categorized_news.items():
            if len(news_list) == 0:
                continue  # 跳过空类别
                
            # 获取分类名称
            if category_id == "uncategorized":
                category_name = "未分类"
            elif category_id == "military" and category_id not in STANDARD_CATEGORIES:
                category_name = "军事新闻"
            else:
                category_name = STANDARD_CATEGORIES.get(category_id, {}).get("name", "未分类")
                
            # 创建分类节点
            category_item = QTreeWidgetItem(self.category_tree)
            category_item.setText(0, f"{category_name} ({len(news_list)})")
            category_item.setData(0, Qt.UserRole, category_id)
            
            # 为所有类别统一设置图标和样式
            # 根据类别ID选择合适的图标
            icon_map = {
                "politics": "user-bookmarks",
                "military": "security-high",
                "sports": "applications-games",
                "technology": "applications-science",
                "business": "accessories-calculator",
                "international": "applications-internet",
                "science": "applications-education-science",
                "entertainment": "applications-multimedia",
                "health": "applications-healthcare",
                "culture": "applications-education",
                "general": "folder-documents",
                "uncategorized": "folder"
            }
            
            # 获取对应的图标，如果没有特定映射则使用默认图标
            theme_icon = icon_map.get(category_id, "folder-documents")
            category_item.setIcon(0, QIcon.fromTheme(theme_icon, QIcon("")))
            
            # 统一设置字体样式
            font = category_item.font(0)
            font.setBold(True)
            category_item.setFont(0, font)
        
        # 展开所有节点
        self.category_tree.expandAll()
        
        # 默认选中"所有新闻"
        self.category_tree.setCurrentItem(all_item)


class GroupTreeManager:
    """
    分组树管理器，负责分组树的渲染和交互
    """
    
    def __init__(self, group_tree: QTreeWidget):
        """
        初始化分组树管理器
        
        Args:
            group_tree: 分组树控件
        """
        self.logger = logging.getLogger('news_analyzer.ui.views.group_tree_manager') # Updated logger name
        self.group_tree = group_tree
    
    def populate_group_tree(self, groups: List[List[Dict]], all_news_items: List[Dict]):
        """
        填充分组树视图
        
        Args:
            groups: 分组后的新闻列表
            all_news_items: 所有新闻列表，用于查找索引
        """
        self.group_tree.clear()
        
        if not groups:
            item = QTreeWidgetItem(self.group_tree)
            item.setText(0, "未找到相似度足够高的新闻组")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)  # 不可选
            return
        
        # 添加分组到树视图
        for i, group in enumerate(groups):
            # 获取组内第一条新闻的标题作为组标题
            first_news = group[0]
            group_title = first_news.get('title', '无标题')
            
            # 提取组内所有新闻来源
            sources = set()
            for news in group:
                source_name = news.get('source_name', '未知来源')
                sources.add(source_name)
            sources_str = ", ".join(sorted(list(sources)))
            
            # 创建分组节点
            group_item = QTreeWidgetItem(self.group_tree)
            group_item.setText(0, f"{group_title} ({len(group)}条，来自: {sources_str})")
            group_item.setData(0, Qt.UserRole, {'type': 'group', 'group_index': i})
            
            # 添加组内新闻作为子节点
            for news in group:
                news_title = news.get('title', '无标题')
                # 尝试找到该新闻在 all_news_items 中的原始索引
                original_index = -1
                try:
                    # 假设 link 是唯一标识符
                    news_link = news.get('link')
                    if news_link:
                        original_index = next((idx for idx, item in enumerate(all_news_items) if item.get('link') == news_link), -1)
                    
                    if original_index == -1:
                       self.logger.warning(f"无法找到新闻 '{news_title[:30]}...' 在 all_news_items 中的索引。")
                except Exception as e:
                    self.logger.error(f"查找新闻 '{news_title[:30]}...' 索引时出错: {e}")
                
                # 获取发布时间和来源
                pub_time_str = '未知时间'
                pub_time = news.get('publish_time')
                if pub_time:
                    if isinstance(pub_time, str):
                        try:
                            pub_time_dt = datetime.fromisoformat(pub_time)
                            pub_time_str = pub_time_dt.strftime('%Y-%m-%d %H:%M')
                        except (ValueError, TypeError):
                            pub_time_str = pub_time # Use original string if parsing fails
                    elif isinstance(pub_time, datetime):
                         pub_time_str = pub_time.strftime('%Y-%m-%d %H:%M')
                         
                source_name = news.get('source_name', '未知来源')
                
                # 创建新闻子节点
                news_item = QTreeWidgetItem(group_item)
                news_item.setText(0, f"{news_title}")
                news_item.setText(1, source_name)
                news_item.setText(2, pub_time_str)
                
                # 存储必要数据以便后续操作
                news_item.setData(0, Qt.UserRole, {
                    'type': 'news', 
                    'group_index': i, 
                    'news_index_in_group': group.index(news), 
                    'original_news_index': original_index
                })
                
                # 设置统一的图标和样式
                news_item.setIcon(0, QIcon.fromTheme("text-x-generic", QIcon("")))
                news_item.setForeground(1, QColor('gray')) # 来源使用灰色
                news_item.setForeground(2, QColor('gray')) # 时间使用灰色
        
        # 展开所有分组节点
        self.group_tree.expandAll()
        
        # 调整列宽以适应内容
        self.group_tree.resizeColumnToContents(0)
        self.group_tree.resizeColumnToContents(1)
        self.group_tree.resizeColumnToContents(2)

    def get_selected_news_indices(self, news_groups: List[List[Dict]], all_news_items: List[Dict]) -> List[int]:
        """
        获取分组树中选中的新闻原始索引列表。
        如果选中了分组节点，则返回该分组下所有新闻的原始索引。
        如果选中了单个新闻节点，则返回该新闻的原始索引。
        
        Args:
            news_groups: 分组数据
            all_news_items: 所有新闻项，用于获取原始索引
        
        Returns:
            选中的新闻原始索引列表
        """
        selected_indices = set()  # 使用集合避免重复
        selected_items = self.group_tree.selectedItems()
        
        for item in selected_items:
            item_data = item.data(0, Qt.UserRole)
            if not isinstance(item_data, dict):
                continue
            
            item_type = item_data.get('type')
            
            if item_type == 'group':
                group_index = item_data.get('group_index')
                if group_index is not None and 0 <= group_index < len(news_groups):
                    group = news_groups[group_index]
                    for news in group:
                        # 查找原始索引
                        news_link = news.get('link')
                        if news_link:
                             original_index = next((idx for idx, orig_item in enumerate(all_news_items) if orig_item.get('link') == news_link), -1)
                             if original_index != -1:
                                 selected_indices.add(original_index)
            
            elif item_type == 'news':
                original_index = item_data.get('original_news_index')
                if original_index is not None and original_index != -1:
                    selected_indices.add(original_index)
            
            # 检查父节点是否也被选中，如果是，则已包含在父节点处理中，无需重复添加
            # （QTreeWidget 默认行为是如果父节点被选，子节点也会被视为选中状态返回）
        
        return sorted(list(selected_indices))

    def show_context_menu(self, position: QPoint, callback_view_detail: Callable, callback_analyze_single: Callable, 
                         callback_select_group: Callable, callback_analyze_group: Callable):
        """
        在指定位置显示上下文菜单。
        
        Args:
            position: 菜单显示的位置 (相对于 group_tree)
            callback_view_detail: 查看新闻详情的回调函数 (接收原始索引)
            callback_analyze_single: 分析单条新闻的回调函数 (接收原始索引)
            callback_select_group: 选中整个分组的回调函数 (接收分组索引)
            callback_analyze_group: 分析整个分组的回调函数 (接收分组索引)
        """
        item = self.group_tree.itemAt(position)
        if not item:
            return
        
        item_data = item.data(0, Qt.UserRole)
        if not isinstance(item_data, dict):
            return
        
        menu = self.group_tree.findChild(QWidget, "groupContextMenu")
        if not menu:
            self.logger.error("无法找到 groupContextMenu 控件！")
            return

        # 清除旧的动作
        menu.clear()

        item_type = item_data.get('type')
        group_index = item_data.get('group_index')
        original_news_index = item_data.get('original_news_index')

        if item_type == 'news' and original_news_index is not None and original_news_index != -1:
            action_view = QAction(f"查看详情 ({item.text(0)[:20]}...)", menu)
            action_view.triggered.connect(lambda: callback_view_detail(original_news_index))
            menu.addAction(action_view)
            
            action_analyze = QAction(f"单条分析 ({item.text(0)[:20]}...)", menu)
            action_analyze.triggered.connect(lambda: callback_analyze_single(original_news_index))
            menu.addAction(action_analyze)

        if item_type == 'group' or (item_type == 'news' and group_index is not None):
            menu.addSeparator()
            action_select_group = QAction(f"选中第 {group_index + 1} 组全部新闻", menu)
            action_select_group.triggered.connect(lambda: callback_select_group(group_index))
            menu.addAction(action_select_group)
            
            action_analyze_group = QAction(f"分析第 {group_index + 1} 组全部新闻", menu)
            action_analyze_group.triggered.connect(lambda: callback_analyze_group(group_index))
            menu.addAction(action_analyze_group)

        # 显示菜单
        if menu.actions():
            menu.popup(self.group_tree.viewport().mapToGlobal(position)) 