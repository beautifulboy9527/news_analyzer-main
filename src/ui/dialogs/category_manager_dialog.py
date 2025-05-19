import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, 
    QPushButton, QMessageBox, QInputDialog, QDialogButtonBox, QWidget,
    QLineEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

# Assuming PromptManagerService is accessible via relative import or adjusted path
# If this file is in src/ui/dialogs, then service is in src/ui/managers
from ..managers.prompt_manager import PromptManagerService 

class CategoryManagementDialog(QDialog):
    """Dialog for managing prompt categories (add, rename, delete)."""

    def __init__(self, prompt_service: PromptManagerService, parent=None):
        super().__init__(parent)
        self.prompt_service = prompt_service
        self.logger = logging.getLogger('news_analyzer.ui.dialogs.category_manager')
        
        self.setWindowTitle("管理提示词分类")
        self.setMinimumSize(400, 300)
        # self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint) # 注释掉，尝试恢复X按钮

        self._init_ui()
        self._load_categories()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # List Widget
        self.category_list = QListWidget()
        self.category_list.currentItemChanged.connect(self._update_button_states)
        main_layout.addWidget(self.category_list)

        # Action Buttons Layout
        action_layout = QHBoxLayout()
        self.add_button = QPushButton(" 新建分类")
        self.add_button.setIcon(QIcon.fromTheme("list-add"))
        self.add_button.clicked.connect(self._add_category)
        action_layout.addWidget(self.add_button)

        self.rename_button = QPushButton(" 重命名")
        self.rename_button.setIcon(QIcon.fromTheme("document-edit"))
        self.rename_button.clicked.connect(self._rename_category)
        action_layout.addWidget(self.rename_button)

        self.delete_button = QPushButton(" 删除")
        self.delete_button.setIcon(QIcon.fromTheme("list-remove"))
        self.delete_button.clicked.connect(self._delete_category)
        action_layout.addWidget(self.delete_button)
        action_layout.addStretch()
        
        # Add action layout wrapper if needed for margins/spacing
        action_container = QWidget()
        action_container.setLayout(action_layout)
        main_layout.addWidget(action_container) # Add container widget

        self._update_button_states() # Initial state

    def _load_categories(self):
        """Loads categories from the service and populates the list."""
        self.category_list.clear()
        try:
            categories = self.prompt_service.get_all_category_names()
            self.category_list.addItems(categories)
            self.logger.info(f"Loaded {len(categories)} categories into management dialog.")
        except Exception as e:
            self.logger.error(f"Failed to load categories: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"加载分类列表失败:\n{e}")
        self._update_button_states()

    def _update_button_states(self):
        """Enable/disable rename and delete buttons based on selection."""
        selected_item = self.category_list.currentItem()
        is_selected = selected_item is not None
        self.rename_button.setEnabled(is_selected)
        self.delete_button.setEnabled(is_selected)

    def _add_category(self):
        """Handles adding a new category."""
        dialog = QInputDialog(self)
        dialog.setWindowTitle("新建分类")
        dialog.setLabelText("请输入新的分类名称:")
        dialog.setTextValue("") # Ensure it starts empty
        dialog.setOkButtonText("确定")
        dialog.setCancelButtonText("取消")

        dialog_result = dialog.exec() # Call exec() only once

        if dialog_result == QDialog.Accepted:
            new_name = dialog.textValue().strip()
            if not new_name:
                 QMessageBox.warning(self, "输入无效", "分类名称不能为空。")
                 return
            # Check if exists (case-insensitive check might be good)
            existing_categories = [item.text().lower() for item in self.category_list.findItems("*", Qt.MatchWildcard)]
            if new_name.lower() in existing_categories:
                 QMessageBox.warning(self, "名称已存在", f"分类 '{new_name}' 已存在。")
                 return

            if self.prompt_service.add_category_definition(new_name):
                self.logger.info(f"Successfully added category: {new_name}")
                self._load_categories() # Refresh list
            else:
                self.logger.error(f"Service failed to add category: {new_name}")
                QMessageBox.critical(self, "错误", f"添加分类 '{new_name}' 失败。")
        # No specific action needed for QDialog.Rejected (cancel)
        # The previous warning for empty name on reject was incorrect.

    def _rename_category(self):
        """Handles renaming the selected category."""
        current_item = self.category_list.currentItem()
        if not current_item:
            return
        old_name = current_item.text()
        
        dialog = QInputDialog(self)
        dialog.setWindowTitle("重命名分类")
        dialog.setLabelText(f"请输入 '{old_name}' 的新名称:")
        dialog.setTextValue(old_name)
        dialog.setOkButtonText("确定")
        dialog.setCancelButtonText("取消")

        # Store the result of exec_() once
        dialog_result = dialog.exec()

        if dialog_result == QDialog.Accepted:
            new_name = dialog.textValue().strip()
            if not new_name:
                 QMessageBox.warning(self, "输入无效", "新分类名称不能为空。")
                 return
            if new_name == old_name:
                return # No change

            # Check if new name conflicts
            existing_categories = [item.text().lower() for item in self.category_list.findItems("*", Qt.MatchWildcard) if item.text() != old_name]
            if new_name.lower() in existing_categories:
                 QMessageBox.warning(self, "名称冲突", f"分类名称 '{new_name}' 已被其他分类使用。")
                 return

            if self.prompt_service.rename_prompt_category(old_name, new_name):
                self.logger.info(f"Successfully renamed category '{old_name}' to '{new_name}'.")
                self._load_categories() # Refresh list
            else:
                self.logger.error(f"Service failed to rename category '{old_name}' to '{new_name}'.")
                QMessageBox.critical(self, "错误", f"重命名分类 '{old_name}' 失败。")
        # else: user cancelled (dialog_result == QDialog.Rejected)
        # No further action needed for cancel

    def _delete_category(self):
        """Handles deleting the selected category."""
        current_item = self.category_list.currentItem()
        if not current_item:
            return
        name_to_delete = current_item.text()

        # Manually create QMessageBox for translation
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("确认删除")
        msg_box.setText(f"确定要删除分类 '{name_to_delete}' 吗？\n所有属于此分类的提示词将被设为未分类。")
        msg_box.setIcon(QMessageBox.Question)
        yes_button = msg_box.addButton("是", QMessageBox.YesRole) # Chinese "Yes"
        no_button = msg_box.addButton("否", QMessageBox.NoRole)   # Chinese "No"
        msg_box.setDefaultButton(no_button)
        
        msg_box.exec()

        if msg_box.clickedButton() == yes_button:
            # Service method handles unassigning by default
            if self.prompt_service.delete_category_definition(name_to_delete):
                self.logger.info(f"Successfully deleted category: {name_to_delete}")
                self._load_categories() # Refresh list
            else:
                self.logger.error(f"Service failed to delete category: {name_to_delete}")
                QMessageBox.critical(self, "错误", f"删除分类 '{name_to_delete}' 失败。")
        # else: user clicked No or closed the dialog 