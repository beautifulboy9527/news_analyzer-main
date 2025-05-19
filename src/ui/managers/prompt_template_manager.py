# src/ui/managers/prompt_template_manager.py
"""
提示词模板管理界面

允许用户查看、编辑、添加和删除提示词模板，
支持根据新闻类型选择合适的提示词模板。
"""

import os
import logging
from typing import Dict, List, Optional

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QLabel, QTextEdit, QPushButton,
                             QSplitter, QMessageBox, QInputDialog, QComboBox,
                             QGroupBox, QFormLayout, QWidget, QSizePolicy,
                             QToolBar, QDialogButtonBox, QLineEdit, QMenu)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QFont

from src.llm.prompt_manager import PromptManager
# from ..dialogs.category_manager_dialog import CategoryManagementDialog # Moved to method
from ..dialogs.add_template_dialog import AddTemplateDialog # Import the new dialog


class PromptTemplateManager(QDialog):
    """
    提示词模板管理对话框
    """
    
    NO_CATEGORY_PLACEHOLDER = "<无分类>" # Define placeholder text
    
    # 模板名称和显示名称的对应关系
    TEMPLATE_DISPLAY_NAMES = {
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
    
    def __init__(self, prompt_manager_service: 'PromptManagerService', parent=None):
        """
        初始化提示词模板管理对话框
        
        Args:
            prompt_manager_service: 提示词管理服务实例
            parent: 父窗口
        """
        super().__init__(parent)
        self.prompt_manager_service = prompt_manager_service
        self.logger = logging.getLogger('news_analyzer.ui.managers.prompt_template_manager')
        
        self.setWindowTitle("提示词模板管理")
        self.setMinimumSize(800, 600)
        
        # 创建界面
        self._create_ui()
        
        # 加载模板列表
        self._load_templates()
    
    def _create_ui(self):
        """创建界面"""
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Horizontal)

        # 2. 模板列表区域 (Becomes Left Pane)
        left_pane_widget = QWidget() # Create a container widget for the left pane
        left_pane_layout = QVBoxLayout(left_pane_widget) # Main layout for the left pane
        left_pane_layout.setContentsMargins(0,0,0,0) # No margins for the container layout
        left_pane_layout.setSpacing(8)

        # --- New Action Buttons Layout (replaces toolbar) ---
        action_button_layout = QHBoxLayout()
        action_button_layout.setSpacing(8)

        self.add_template_button = QPushButton(" 添加模板") # Leading space for icon room
        self.add_template_button.setIcon(QIcon.fromTheme("list-add", QIcon(":/icons/add.png"))) # Fallback icon
        self.add_template_button.setToolTip("添加新的提示词模板")
        self.add_template_button.clicked.connect(self._add_template)
        self.add_template_button.setFixedHeight(32) # Consistent height
        action_button_layout.addWidget(self.add_template_button)

        self.delete_template_button = QPushButton(" 删除模板")
        self.delete_template_button.setIcon(QIcon.fromTheme("list-remove", QIcon(":/icons/delete.png"))) # Fallback icon
        self.delete_template_button.setToolTip("删除选中的模板")
        self.delete_template_button.clicked.connect(self._delete_template)
        self.delete_template_button.setEnabled(False) # Disabled until an item is selected
        self.delete_template_button.setFixedHeight(32)
        action_button_layout.addWidget(self.delete_template_button)

        self.manage_categories_button = QPushButton(" 管理分类")
        self.manage_categories_button.setIcon(QIcon.fromTheme("document-properties", QIcon(":/icons/settings.png")))
        self.manage_categories_button.setToolTip("添加、删除或重命名提示词分类")
        self.manage_categories_button.clicked.connect(self._open_category_manager)
        self.manage_categories_button.setFixedHeight(32)
        action_button_layout.addWidget(self.manage_categories_button)

        action_button_layout.addStretch()
        left_pane_layout.addLayout(action_button_layout) # Add to left pane layout
        # --- End New Action Buttons Layout ---

        # Search and (removed) Category Filter Layout
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索模板...")
        self.search_edit.textChanged.connect(self._filter_templates)
        search_layout.addWidget(self.search_edit, 1) # Give search edit more stretch

        # # 分类下拉框 (REMOVED)
        # self.category_combo = QComboBox()
        # self.category_combo.addItems(["全部", "新闻分析", "立场分析", "事实核查", "摘要", "其他"]) # Initial items, populated by _populate_category_combos
        # self.category_combo.currentTextChanged.connect(self._filter_templates)
        # search_layout.addWidget(self.category_combo)
        
        left_pane_layout.addLayout(search_layout)

        # 模板列表
        self.template_list = QListWidget()
        self.template_list.setSelectionMode(QListWidget.SingleSelection)
        self.template_list.currentItemChanged.connect(self._on_template_selected)
        self.template_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.template_list.customContextMenuRequested.connect(self._show_template_context_menu)
        left_pane_layout.addWidget(self.template_list) # Add template_list to left_pane_layout

        splitter.addWidget(left_pane_widget) # Add the new container widget to splitter

        # 3. 编辑区域 (Becomes Right Pane)
        edit_group = QGroupBox("")
        edit_group.setStyleSheet("QGroupBox { border: none; }")
        edit_layout = QVBoxLayout()
        edit_layout.setContentsMargins(0, 5, 0, 0)
        
        # 模板信息
        info_layout = QFormLayout()
        self.template_name_label = QLabel("未选择模板")
        self.template_name_label.setStyleSheet("font-weight: bold;")
        info_layout.addRow("模板名称:", self.template_name_label)

        self.category_assign_combo = QComboBox()
        self.category_assign_combo.setToolTip("为此模板选择或分配一个分类")
        # self.category_assign_combo.setEditable(True) # Allow users to type new categories directly for now
        # self.category_assign_combo.lineEdit().setPlaceholderText("选择或输入新分类...")
        info_layout.addRow("模板分类:", self.category_assign_combo)

        edit_layout.addLayout(info_layout)
        
        # 内容编辑器
        self.content_editor = QTextEdit()
        self.content_editor.setPlaceholderText("选择模板以查看或编辑内容")
        self.content_editor.setMinimumHeight(200)
        edit_layout.addWidget(self.content_editor)

        # --- Placeholder Buttons (replaces old hint_label) ---
        placeholder_widget = QWidget() # Create a container for the placeholder buttons and label
        placeholder_layout = QHBoxLayout(placeholder_widget)
        placeholder_layout.setContentsMargins(0, 5, 0, 0) # Add some top margin
        placeholder_layout.setSpacing(6)
        
        placeholders = ["{title}", "{source}", "{pub_date}", "{content}", "{news_items}"]
        
        placeholder_text_label = QLabel("插入占位符:") # Changed variable name to avoid conflict
        placeholder_layout.addWidget(placeholder_text_label)

        for placeholder_text_value in placeholders: # Changed variable name to avoid conflict
            btn = QPushButton(placeholder_text_value)
            btn.setToolTip(f"点击插入 {placeholder_text_value}")
            # btn.setStyleSheet("""QPushButton {
            #         padding: 4px 8px;
            #         border: 1px solid #D0D0D0;
            #         border-radius: 4px;
            #         background-color: #F0F0F0;
            #         font-size: 12px;
            #     }
            #     QPushButton:hover { background-color: #E0E0E0; }
            #     QPushButton:pressed { background-color: #C8C8C8; }""") # 移除样式
            # Corrected lambda to pass the placeholder text properly
            btn.clicked.connect(lambda checked=False, p=placeholder_text_value: self._insert_placeholder(p))
            placeholder_layout.addWidget(btn)
        placeholder_layout.addStretch()
        edit_layout.addWidget(placeholder_widget) # Add the container widget to the edit_layout
        # --- End Placeholder Buttons ---
        
        edit_group.setLayout(edit_layout)
        splitter.addWidget(edit_group) # Added to splitter

        # Set initial sizes for the splitter panes (optional, but good for default view)
        splitter.setSizes([250, 550]) # Adjust as needed, e.g., 1/3 list, 2/3 editor

        main_layout.addWidget(splitter, 1) # Add stretch factor for splitter to expand

        # 4. 操作按钮区域
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Save).setText("保存")
        button_box.button(QDialogButtonBox.Cancel).setText("取消")
        button_box.accepted.connect(self._save_template)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        
        self.setLayout(main_layout)
    
    def _load_templates(self):
        """加载模板列表，按分类分组显示，并确保显示名称唯一"""
        self.template_list.clear()
        self._populate_category_combos() # Ensure assignment combo is populated

        all_template_names = self.prompt_manager_service.get_template_names()
        templates_by_category: Dict[Optional[str], List[str]] = {}

        # Populate templates_by_category
        for template_name in all_template_names:
            _content, category = self.prompt_manager_service.get_template_details(template_name)
            if category not in templates_by_category:
                templates_by_category[category] = []
            templates_by_category[category].append(template_name)

        # Get all defined categories to ensure even empty ones can be listed as headers
        defined_categories = self.prompt_manager_service.get_all_category_names()
        
        # Sort categories: None (uncategorized) first, then alphabetically
        sorted_categories = sorted(
            [cat for cat in defined_categories if cat is not None] + 
            [cat for cat in templates_by_category if cat is not None and cat not in defined_categories] # Add categories from templates not in defined_list
        )
        
        # Process uncategorized first, if any
        uncategorized_templates = templates_by_category.get(None, [])
        if uncategorized_templates:
            header_item = QListWidgetItem(f"--- {self.NO_CATEGORY_PLACEHOLDER} ---")
            header_item.setFlags(header_item.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled)
            header_item.setData(Qt.UserRole, {"type": "category_header", "name": None})
            self.template_list.addItem(header_item)
            for template_name in sorted(uncategorized_templates):
                self._add_template_item_to_list(template_name)
        
        # Process categorized templates
        for category_name in sorted_categories:
            if category_name is None: continue # Already handled

            header_item = QListWidgetItem(f"--- {category_name} ---")
            header_item.setFlags(header_item.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled)
            header_item.setData(Qt.UserRole, {"type": "category_header", "name": category_name}) # Store category name for context
            self.template_list.addItem(header_item)
            
            category_templates = templates_by_category.get(category_name, [])
            for template_name in sorted(category_templates):
                self._add_template_item_to_list(template_name)
            
            # If a defined category has no templates yet, it will just show its header
            if not category_templates and category_name in defined_categories:
                pass # Header already added

    def _add_template_item_to_list(self, template_name: str):
        """Helper to add a single template item to the list, ensuring unique display name.
           This is a simplified version focusing on adding one item, not managing a global unique set.
           Uniqueness within the list is less critical if grouped, but good practice."""
        # For simplicity, this helper won't try to ensure global display name uniqueness across categories.
        # That logic was complex and less critical when items are visually grouped.
        # We will use the internal name if display name is not unique for that specific template.
        display_name = self.TEMPLATE_DISPLAY_NAMES.get(template_name, template_name)
        
        # Minimal check for immediate duplicates in the list (less robust than before but simpler)
        # existing_items_texts = [self.template_list.item(i).text() for i in range(self.template_list.count())]
        # if display_name in existing_items_texts:
        #     display_name = f"{display_name} ({template_name})"

        item = QListWidgetItem(display_name)
        item.setData(Qt.UserRole, {"type": "template", "name": template_name})  # Store type and actual template name
        self.template_list.addItem(item)

    def _add_template(self):
        """添加新模板，使用自定义对话框获取名称和分类"""
        self.logger.debug("Opening add template dialog.")
        
        # Get current categories for the dialog
        all_categories = self.prompt_manager_service.get_all_category_names()
        # Ensure placeholder is not in the list passed to the dialog, it adds its own
        all_categories = [cat for cat in all_categories if cat != self.NO_CATEGORY_PLACEHOLDER]

        dialog = AddTemplateDialog(all_categories, self)
        
        if dialog.exec() == QDialog.Accepted:
            details = dialog.get_template_details()
            if not details: # Should ideally be handled by dialog not closing, or by returning error
                QMessageBox.warning(self, "添加失败", "模板名称不能为空。")
                return

            name, category = details
            
            if not name: # Double check, though AddTemplateDialog's get_template_details should prevent this
                QMessageBox.warning(self, "添加失败", "模板名称不能为空。")
                return

            if name in self.prompt_manager_service.get_template_names():
                QMessageBox.warning(self, "名称已存在", f"模板 '{name}' 已存在。")
                return

            # Save the new template (initially with empty content)
            if self.prompt_manager_service.save_template(name, "", category=category):
                self.logger.info(f"New template '{name}' (Category: {category}) created via dialog.")
                self._load_templates()  # Reload the list
                
                # Try to select the newly added template
                items = self.template_list.findItems(name, Qt.MatchExactly | Qt.MatchRecursive) # Check display name
                if not items: # If display name mapping exists and name is different
                    # We need to find by internal name via UserRole
                    for i in range(self.template_list.count()):
                        item = self.template_list.item(i)
                        if item.data(Qt.UserRole) == name:
                            items = [item]
                            break
                
                if items:
                    self.template_list.setCurrentItem(items[0])
                self.content_editor.setFocus() # Focus editor for new content
            else:
                QMessageBox.critical(self, "错误", f"创建模板 '{name}' 失败。")
        else:
            self.logger.debug("Add template dialog cancelled.")
    
    def _edit_template(self):
        """编辑模板"""
        current_item = self.template_list.currentItem()
        if not current_item:
            return
        
        template_name = current_item.data(Qt.UserRole)
        content = self.prompt_manager_service.get_template_content(template_name)
        self.content_editor.setPlainText(content)
    
    def _delete_template(self):
        """删除模板"""
        current_item = self.template_list.currentItem()
        if not current_item:
            return
        
        item_data = current_item.data(Qt.UserRole)
        if not item_data or item_data.get("type") != "template":
            # Potentially trying to delete a category header - should not happen with button states
            return

        template_name_str = item_data.get("name") # Get the actual string name
        if not template_name_str:
            self.logger.error("Delete action: Selected item has no template name in data.")
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除模板 '{self.TEMPLATE_DISPLAY_NAMES.get(template_name_str, template_name_str)}' 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.prompt_manager_service.delete_template(template_name_str):
                self._load_templates()
                self.content_editor.clear()
            else:
                QMessageBox.warning(self, "错误", "删除模板失败")
    
    def _save_template(self):
        """保存模板"""
        current_item = self.template_list.currentItem()
        if not current_item: # or not (current_item.flags() & Qt.ItemIsSelectable):
             # Check if it's a header or no selection
            if current_item and not (current_item.flags() & Qt.ItemIsSelectable):
                QMessageBox.information(self, "提示", "请选择一个实际的模板进行保存，而不是分类标题。")
            return # No actual template selected
        
        item_data = current_item.data(Qt.UserRole)
        if not item_data or item_data.get("type") != "template":
            QMessageBox.information(self, "提示", "请选择一个实际的模板进行保存。")
            return

        template_name_str = item_data.get("name") # Get the actual string name
        if not template_name_str:
            self.logger.error("Save action: Selected item has no template name in data.")
            return
        
        content = self.content_editor.toPlainText()
        
        selected_assign_text = self.category_assign_combo.currentText()
        category_to_save = None if selected_assign_text == self.NO_CATEGORY_PLACEHOLDER else selected_assign_text
        
        _original_content, original_category = self.prompt_manager_service.get_template_details(template_name_str)

        if self.prompt_manager_service.save_template(template_name_str, content, category_to_save):
            QMessageBox.information(self, "保存成功", f"模板 '{self.TEMPLATE_DISPLAY_NAMES.get(template_name_str, template_name_str)}' 已保存。")
            
            if original_category != category_to_save:
                self.logger.debug(f"Category changed for '{template_name_str}' from '{original_category}' to '{category_to_save}'. Refreshing selection after save.")
                self._load_templates()
                found_item_to_reselect = None
                for i in range(self.template_list.count()):
                    item = self.template_list.item(i)
                    # Ensure we are checking template items only for re-selection
                    reselect_item_data = item.data(Qt.UserRole)
                    if reselect_item_data and reselect_item_data.get("type") == "template" and reselect_item_data.get("name") == template_name_str:
                        found_item_to_reselect = item
                        break
                
                if found_item_to_reselect:
                    self.template_list.setCurrentItem(found_item_to_reselect)
                else:
                    self.logger.warning(f"Could not re-select template '{template_name_str}' after category change and list reload.")

        else:
            QMessageBox.warning(self, "错误", "保存模板失败")
    
    def _filter_templates(self):
        """根据搜索词筛选模板. Now respects category grouping visually but filters flatly."""
        # This simple filter will hide/show items. Category headers remain.
        # More advanced filtering would rebuild the grouped list based on search.
        search_text = self.search_edit.text().lower()

        for i in range(self.template_list.count()):
            item = self.template_list.item(i)
            item_data = item.data(Qt.UserRole)

            if item_data and item_data.get("type") == "template":
                template_name = item_data.get("name")
                # Use the actual item text which is the display name for filtering
                display_name = item.text() # self.TEMPLATE_DISPLAY_NAMES.get(template_name, template_name)
                
                if search_text:
                    item.setHidden(search_text not in display_name.lower())
                else:
                    item.setHidden(False)
            elif item_data and item_data.get("type") == "category_header":
                # Optionally, hide headers if all their children are hidden by search.
                # For now, keep headers visible.
                item.setHidden(False) 
    
    def _on_template_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        """当选择模板时更新编辑区域. Handles non-selectable items."""
        if current is None or not (current.flags() & Qt.ItemIsSelectable):
            # If item is None or a non-selectable header
            if current and not (current.flags() & Qt.ItemIsSelectable) : # It's a header
                 self.template_list.setCurrentItem(None) # Clear actual selection
            
            self.template_name_label.setText("未选择模板或分类标题")
            self.content_editor.clear()
            self.content_editor.setEnabled(False)
            self.delete_template_button.setEnabled(False)
            self.category_assign_combo.setCurrentIndex(-1)
            self.category_assign_combo.setEnabled(False)
            return
        
        item_data = current.data(Qt.UserRole)
        if not item_data or item_data.get("type") != "template":
            # Should not happen if non-selectable items are handled above, but as a safeguard
            return

        template_name_str = item_data.get("name") # Get the actual string name
        if not template_name_str:
            self.logger.error("Selected item has no template name in data.")
            return

        content, category = self.prompt_manager_service.get_template_details(template_name_str)
        
        display_name_label_text = self.TEMPLATE_DISPLAY_NAMES.get(template_name_str, template_name_str)
        self.template_name_label.setText(display_name_label_text)
        self.content_editor.setPlainText(content)
        self.content_editor.setEnabled(True)
        self.delete_template_button.setEnabled(True)
        self.category_assign_combo.setEnabled(True)

        # Set category in the assignment combo
        if category:
            index = self.category_assign_combo.findText(category, Qt.MatchFixedString)
            if index >= 0:
                self.category_assign_combo.setCurrentIndex(index)
            else:
                self.logger.warning(f"Category '{category}' for template '{template_name_str}' not found in assignment combo. Setting to uncategorized.")
                placeholder_index = self.category_assign_combo.findText(self.NO_CATEGORY_PLACEHOLDER)
                self.category_assign_combo.setCurrentIndex(placeholder_index if placeholder_index >= 0 else -1) 
        else:
            placeholder_index = self.category_assign_combo.findText(self.NO_CATEGORY_PLACEHOLDER)
            self.category_assign_combo.setCurrentIndex(placeholder_index if placeholder_index >= 0 else -1) 

    def _insert_placeholder(self, placeholder_text: str):
        """Inserts the given placeholder text into the content editor at the current cursor position."""
        self.content_editor.insertPlainText(placeholder_text)

    def _open_category_manager(self):
        """Opens the dialog to manage categories."""
        from ..dialogs.category_manager_dialog import CategoryManagementDialog # Import moved here
        self.logger.debug("Opening category management dialog.")
        dialog = CategoryManagementDialog(self.prompt_manager_service, self)
        dialog.exec() # Show modally
        self.logger.debug("Category management dialog closed. Repopulating category combos and reloading template list.")
        self._populate_category_combos() # Refresh category lists in this dialog
        self._load_templates() # Reload the main template list to reflect category definition changes (e.g., deleted category headers)

    def _populate_category_combos(self):
        """Populates category combo boxes. Now only populates assignment combo."""
        # current_filter_category = self.category_combo.currentText() # REMOVED
        current_assign_category = self.category_assign_combo.currentText()

        # self.category_combo.clear() # REMOVED
        self.category_assign_combo.clear()

        all_categories = self.prompt_manager_service.get_all_category_names()
        
        # For filter combo (left pane) - REMOVED
        # self.category_combo.addItem("全部")
        # self.category_combo.addItems(all_categories)

        # For assignment combo (right pane)
        self.category_assign_combo.addItem(self.NO_CATEGORY_PLACEHOLDER) # Add placeholder first
        self.category_assign_combo.addItems(all_categories)

        # Restore previous selections if possible
        # filter_idx = self.category_combo.findText(current_filter_category) # REMOVED
        # if filter_idx >= 0: self.category_combo.setCurrentIndex(filter_idx) # REMOVED
        # else: self.category_combo.setCurrentIndex(0) # REMOVED

        assign_idx = self.category_assign_combo.findText(current_assign_category)
        if assign_idx >= 0: self.category_assign_combo.setCurrentIndex(assign_idx)
        # No else for assign, it will be set by _on_template_selected

    def _show_template_context_menu(self, position):
        """Shows a context menu for template items in the list."""
        item = self.template_list.itemAt(position)
        if not item:
            return

        item_data = item.data(Qt.UserRole)
        if not item_data or item_data.get("type") != "template":
            return # Not a template item, no context menu

        template_name_str = item_data.get("name") # Get the actual string name
        if not template_name_str:
            return

        menu = QMenu(self)
        # Apply QSS for modern minimalist style
        menu_qss = """
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                padding: 4px;
                border-radius: 4px;
            }
            QMenu::item {
                padding: 6px 20px 6px 20px;
                background-color: transparent;
                color: #333333;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #F0F0F0;
                color: #000000;
            }
            QMenu::item:disabled {
                color: #A0A0A0;
                background-color: transparent;
            }
            QMenu::separator {
                height: 1px;
                background-color: #E0E0E0;
                margin-left: 5px;
                margin-right: 5px;
            }
        """
        menu.setStyleSheet(menu_qss)
        
        # --- Move to Category submenu ---
        move_to_menu = menu.addMenu("移动到分类...")
        
        all_categories = [self.NO_CATEGORY_PLACEHOLDER] + self.prompt_manager_service.get_all_category_names()
        unique_categories_for_menu = []
        if self.NO_CATEGORY_PLACEHOLDER not in unique_categories_for_menu:
            unique_categories_for_menu.append(self.NO_CATEGORY_PLACEHOLDER)
        for cat in self.prompt_manager_service.get_all_category_names():
            if cat not in unique_categories_for_menu:
                 unique_categories_for_menu.append(cat)

        template_name_str_for_context = item_data.get("name") # Get string name for context menu logic
        if not template_name_str_for_context:
            return # Should not happen if we got this far

        _current_content, current_category = self.prompt_manager_service.get_template_details(template_name_str_for_context)

        for category_name_for_action in unique_categories_for_menu:
            action = move_to_menu.addAction(category_name_for_action)
            target_category_to_save = None if category_name_for_action == self.NO_CATEGORY_PLACEHOLDER else category_name_for_action
            
            # Disable action if it's the current category
            if target_category_to_save == current_category:
                action.setEnabled(False)

            action.triggered.connect(
                lambda checked=False, tn=template_name_str_for_context, tc=target_category_to_save, content=_current_content: 
                self._handle_move_template(tn, content, tc)
            )
        
        menu.exec(self.template_list.mapToGlobal(position))

    def _handle_move_template(self, template_name_str: str, content: str, target_category: Optional[str]):
        """Handles moving a template to a new category via context menu."""
        self.logger.info(f"Attempting to move template '{template_name_str}' to category '{target_category}'.")
        if self.prompt_manager_service.save_template(template_name_str, content, target_category):
            self.logger.info(f"Template '{template_name_str}' successfully moved to category '{target_category}'. Reloading list.")
            self._load_templates()
        else:
            self.logger.error(f"Failed to move template '{template_name_str}' to category '{target_category}'.")
            QMessageBox.warning(self, "移动失败", f"将模板 '{template_name_str}' 移动到分类 '{target_category}' 失败。")


# 测试代码
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from src.llm.prompt_manager import PromptManager
    
    app = QApplication(sys.argv)
    prompt_manager = PromptManager()
    dialog = PromptTemplateManager(prompt_manager)
    dialog.show()
    sys.exit(app.exec())