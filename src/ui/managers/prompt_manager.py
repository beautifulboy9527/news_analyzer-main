# src/ui/managers/prompt_manager.py
"""
提示词管理器

提供提示词模板的管理功能，包括加载、编辑、保存和应用提示词模板。
作为一个独立的模块，可以被多个面板复用。
"""

import logging
import os
from typing import Dict, Optional, List, Tuple

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from src.llm.prompt_manager import PromptManager
# from src.ui.managers.prompt_template_manager import PromptTemplateManager # Moved to method


class PromptManagerService(QObject):
    """
    提示词管理服务，负责提示词模板的加载、编辑和应用
    """
    
    # 定义信号
    template_loaded = Signal(str, str)  # 模板名称, 模板内容
    template_applied = Signal(str, str)  # 模板名称, 模板内容
    template_edited = Signal(str)  # 编辑后的提示词内容
    templates_updated = Signal()  # 模板列表更新信号
    
    def __init__(self, prompt_manager: PromptManager, parent=None):
        """
        初始化提示词管理服务
        
        Args:
            prompt_manager: 提示词管理器实例
            parent: 父对象
        """
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.managers.prompt_manager')
        
        if not prompt_manager:
            self.logger.error("提示词管理器未正确初始化")
            raise ValueError("提示词管理器不能为空")
            
        self.prompt_manager = prompt_manager
        self.templates_dict: Dict[str, str] = {}  # 存储模板名称和内容
        self.current_template_name = ""
        self.current_template_content = ""
        self.current_template_category: Optional[str] = None
        
        # 加载模板数据
        self._load_templates()
    
    def _load_templates(self) -> Dict[str, str]:
        """
        加载所有提示词模板
        
        Returns:
            包含模板名称和内容的字典
        """
        self.templates_dict.clear()
        
        # 获取提示词目录中的所有txt文件
        prompts_dir = self.prompt_manager.prompts_dir
        if not prompts_dir or not os.path.exists(prompts_dir):
            self.logger.error(f"提示词目录不存在: {prompts_dir}")
            return {}
        
        try:
            for filename in os.listdir(prompts_dir):
                if filename.endswith(".txt"):
                    template_name = os.path.splitext(filename)[0]
                    template_path = os.path.join(prompts_dir, filename)
                    
                    try:
                        with open(template_path, 'r', encoding='utf-8') as f:
                            template_content = f.read()
                            self.templates_dict[template_name] = template_content
                    except Exception as e:
                        self.logger.error(f"读取模板文件失败: {template_path} - {e}")
            
            # 发送模板更新信号
            self.templates_updated.emit()
            return self.templates_dict
            
        except Exception as e:
            self.logger.error(f"加载提示词模板失败: {e}")
            return {}
    
    def get_template_names(self) -> List[str]:
        """
        获取所有模板名称
        
        Returns:
            模板名称列表
        """
        return list(self.templates_dict.keys())
    
    def get_template_content(self, template_name: str) -> str:
        """
        获取指定模板的内容
        
        Args:
            template_name: 模板名称
            
        Returns:
            模板内容，如果模板不存在则返回空字符串
        """
        return self.prompt_manager.load_template(template_name) or ""
    
    def get_template_details(self, template_name: str) -> Tuple[str, Optional[str]]:
        """Gets the content and category for a given template name."""
        content = self.prompt_manager.load_template(template_name) or ""
        category = self.prompt_manager.get_template_category(template_name)
        return content, category
    
    def select_template(self, template_name: str) -> bool:
        """
        选择指定的模板
        
        Args:
            template_name: 模板名称
            
        Returns:
            是否成功选择模板
        """
        if not template_name or template_name not in self.templates_dict:
            return False
        
        content, category = self.get_template_details(template_name)
        self.current_template_name = template_name
        self.current_template_content = content
        self.current_template_category = category
        
        # 发送模板加载信号
        self.template_loaded.emit(template_name, self.current_template_content)
        return True
    
    def update_current_template_content(self, content: str) -> None:
        """
        更新当前模板的内容
        
        Args:
            content: 新的模板内容
        """
        if self.current_template_name:
            self.current_template_content = content
            self.template_edited.emit(content)
    
    def apply_current_template(self) -> bool:
        """
        应用当前模板
        
        Returns:
            是否成功应用模板
        """
        if not self.current_template_name or not self.current_template_content:
            return False
        
        # 发送模板应用信号
        self.template_applied.emit(self.current_template_name, self.current_template_content)
        return True
    
    def save_template(self, template_name: str, content: str, category: Optional[str] = None) -> bool:
        """
        保存模板内容和其分类。
        
        Args:
            template_name: 模板名称
            content: 模板内容
            category: 模板分类 (Optional)
            
        Returns:
            是否成功保存模板
        """
        if not template_name:
            self.logger.warning("Service: Save template failed, template_name cannot be empty.")
            return False

        # Save content first
        if not self.prompt_manager.save_prompt_content(template_name, content):
            self.logger.error(f"Service: Failed to save content for template '{template_name}'.")
            return False
        self.logger.info(f"Service: Content for template '{template_name}' saved.")

        # Then save category metadata
        if not self.prompt_manager.set_template_category(template_name, category):
            self.logger.warning(f"Service: Failed to set category '{category}' for template '{template_name}', but content was saved.")
            # Decide if this is a partial success or full failure. For now, let's say content save is primary.
        else:
            self.logger.info(f"Service: Category '{category}' for template '{template_name}' saved.")

        # Update in-memory cache (templates_dict primarily stores content for quick access)
        self.templates_dict[template_name] = content
        if template_name == self.current_template_name:
            self.current_template_content = content
            self.current_template_category = category # Update current category as well
        
        self.templates_updated.emit() # Signal that list/data has changed
        self.logger.info(f"Service: Template '{template_name}' (content and category) processed for saving. templates_updated emitted.")
        return True
            
    def delete_template(self, template_name: str) -> bool:
        """
        删除模板
        
        Args:
            template_name: 模板名称
            
        Returns:
            是否成功删除模板
        """
        if not template_name or template_name not in self.templates_dict:
            self.logger.warning(f"Service: Attempted to delete non-existent template '{template_name}' from cache or unknown.")
            # Still try to delete file and metadata in case of desync
        
        file_deleted = self.prompt_manager.delete_prompt_file(template_name)
        metadata_removed = self.prompt_manager.remove_template_metadata(template_name)

        if not file_deleted:
            self.logger.warning(f"Service: Failed to delete prompt file for '{template_name}'.")
        if not metadata_removed:
            self.logger.warning(f"Service: Failed to remove metadata for '{template_name}'.")

        # Remove from memory cache
        if template_name in self.templates_dict:
            del self.templates_dict[template_name]
            self.logger.info(f"Service: Template '{template_name}' removed from memory cache.")
        
        if template_name == self.current_template_name:
            self.current_template_name = ""
            self.current_template_content = ""
            self.current_template_category = None
            self.logger.info(f"Service: Current template was '{template_name}', now cleared.")
        
        self.templates_updated.emit()
        # Return True if at least one operation (file or metadata deletion) was successful or reported success (e.g., file not found is ok for delete)
        # Or more strictly: return file_deleted and metadata_removed
        # For now, let's be lenient: if it's no longer effectively there, it's a success.
        self.logger.info(f"Service: Deletion processed for '{template_name}'. File deleted: {file_deleted}, Meta removed: {metadata_removed}")
        return True # Service layer signals general success of operation
    
    def get_all_category_names(self) -> List[str]:
        """Gets all unique category names from the PromptManager."""
        return self.prompt_manager.get_all_categories()

    def rename_prompt_category(self, old_category_name: str, new_category_name: str) -> bool:
        """Renames a category across all prompts and in the defined list."""
        if self.prompt_manager.rename_defined_category(old_category_name, new_category_name):
            self.templates_updated.emit() 
            self.logger.info(f"Service: Category '{old_category_name}' renamed to '{new_category_name}'. templates_updated emitted.")
            return True
        self.logger.warning(f"Service: Failed to rename category from '{old_category_name}' to '{new_category_name}'.")
        return False

    def add_category_definition(self, category_name: str) -> bool:
        """Adds a category to the centrally defined list of categories."""
        if self.prompt_manager.add_defined_category(category_name):
            self.templates_updated.emit() # So UI picklists can refresh
            self.logger.info(f"Service: Category '{category_name}' added to defined list. templates_updated emitted.")
            return True
        self.logger.warning(f"Service: Failed to add category '{category_name}' to defined list (it might already exist or be invalid)." )
        return False

    def delete_category_definition(self, category_name: str, unassign_from_templates: bool = True) -> bool:
        """Deletes a category from the defined list and optionally unassigns from templates."""
        if self.prompt_manager.delete_defined_category(category_name, unassign_from_templates):
            self.templates_updated.emit()
            self.logger.info(f"Service: Category '{category_name}' deleted from defined list (unassign: {unassign_from_templates}). templates_updated emitted.")
            return True
        self.logger.warning(f"Service: Failed to delete category '{category_name}' from defined list.")
        return False

    def show_template_manager_dialog(self, parent=None) -> None:
        """
        显示模板管理对话框
        
        Args:
            parent: 父窗口
        """
        from src.ui.managers.prompt_template_manager import PromptTemplateManager # Import moved here
        try:
            dialog = PromptTemplateManager(self, parent)
            dialog.exec()
            
            # 对话框关闭后重新加载模板
            self._load_templates()
            
        except Exception as e:
            self.logger.error(f"显示模板管理对话框失败: {e}")
            QMessageBox.critical(parent, "错误", f"显示模板管理对话框失败: {e}")