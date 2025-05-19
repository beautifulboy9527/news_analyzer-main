import logging
from typing import List, Optional, Tuple
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit, 
    QComboBox, QDialogButtonBox
)

class AddTemplateDialog(QDialog):
    """Dialog to get name and initial category for a new prompt template."""

    NO_CATEGORY_PLACEHOLDER = "<无分类>"

    def __init__(self, existing_categories: List[str], parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.dialogs.add_template')
        self.setWindowTitle("添加新模板")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        form_layout.addRow("模板名称:", self.name_edit)

        self.category_combo = QComboBox()
        self.category_combo.addItem(self.NO_CATEGORY_PLACEHOLDER)
        self.category_combo.addItems(existing_categories)
        form_layout.addRow("选择分类:", self.category_combo)

        layout.addLayout(form_layout)

        # Dialog Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("确定")
        button_box.button(QDialogButtonBox.Cancel).setText("取消")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.name_edit.setFocus() # Set focus to name input initially

    def get_template_details(self) -> Optional[Tuple[str, Optional[str]]]:
        """Returns the entered name and selected category, or None if cancelled."""
        if self.result() == QDialog.Accepted:
            name = self.name_edit.text().strip()
            category_text = self.category_combo.currentText()
            category = None if category_text == self.NO_CATEGORY_PLACEHOLDER else category_text
            
            if not name:
                # Optional: Add validation message here if needed, 
                # but primary validation happens after dialog closes for now.
                self.logger.warning("Attempted to accept dialog with empty name.")
                # We might want to prevent closing if name is empty, 
                # but let's keep it simple and validate in the caller.
                return None # Indicate invalid input
                
            return name, category
        return None 