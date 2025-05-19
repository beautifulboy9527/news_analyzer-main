import os
import logging
import json
from typing import Optional, Dict, Any, List

class PromptManager:
    """
    Manages loading and formatting of LLM prompt templates, including category metadata.
    """
    METADATA_FILENAME = "prompts_metadata.json"

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initializes the PromptManager.

        Args:
            base_dir: The base directory where the 'prompts' subdirectory is located.
                      If None, it defaults relative to this file's location (assuming src/llm).
        """
        self.logger = logging.getLogger('news_analyzer.llm.prompt_manager')

        if base_dir:
            self.prompts_dir = os.path.join(base_dir, 'prompts')
        else:
            # Default: Assume this file is in src/llm, prompts is in src/prompts
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Go up one level (from src/llm to src) then into prompts
            self.prompts_dir = os.path.join(os.path.dirname(current_dir), 'prompts')

        self.metadata_path = os.path.join(self.prompts_dir, self.METADATA_FILENAME)
        self.metadata: Dict[str, Any] = self._load_metadata()
        # Ensure top-level keys for templates and defined categories exist
        if "_templates" not in self.metadata:
            self.metadata["_templates"] = {}
        if "_defined_categories" not in self.metadata:
            self.metadata["_defined_categories"] = []    

        if not os.path.isdir(self.prompts_dir):
             self.logger.warning(f"Prompts directory does not exist or is not a directory: {self.prompts_dir}")
        else:
             self.logger.info(f"PromptManager initialized. Prompts directory: {self.prompts_dir}")
        self.logger.info(f"Metadata will be loaded from/saved to: {self.metadata_path}")

    def _load_metadata(self) -> Dict[str, Any]:
        """Loads metadata from the JSON file. Returns structured dict if not found or error."""
        if not os.path.exists(self.metadata_path):
            self.logger.info(f"Metadata file not found: {self.metadata_path}. Returning new structured metadata.")
            return {"_templates": {}, "_defined_categories": []}
        try:
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
                # Ensure structure
                if not isinstance(loaded_data, dict):
                    self.logger.warning(f"Metadata is not a dict. Reinitializing.")
                    return {"_templates": {}, "_defined_categories": []}
                if "_templates" not in loaded_data or not isinstance(loaded_data["_templates"], dict):
                    loaded_data["_templates"] = {}
                if "_defined_categories" not in loaded_data or not isinstance(loaded_data["_defined_categories"], list):
                    loaded_data["_defined_categories"] = []
                
                num_templates = len(loaded_data.get("_templates", {}))
                num_categories = len(loaded_data.get("_defined_categories", []))
                self.logger.info(f"Successfully loaded metadata for {num_templates} templates and {num_categories} defined categories from {self.metadata_path}")
                return loaded_data
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON from metadata file: {self.metadata_path}. Returning new structured metadata.", exc_info=True)
            return {"_templates": {}, "_defined_categories": []}
        except Exception as e:
            self.logger.error(f"Failed to load metadata file: {self.metadata_path} - {e}. Returning new structured metadata.", exc_info=True)
            return {"_templates": {}, "_defined_categories": []}

    def _save_metadata(self) -> bool:
        """Saves the current metadata to the JSON file."""
        try:
            # Ensure prompts_dir exists before trying to save metadata file in it
            if not os.path.exists(self.prompts_dir):
                os.makedirs(self.prompts_dir, exist_ok=True)
                self.logger.info(f"Created prompts directory {self.prompts_dir} before saving metadata.")

            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=4)
            num_templates = len(self.metadata.get("_templates", {}))
            num_categories = len(self.metadata.get("_defined_categories", []))
            self.logger.info(f"Successfully saved metadata for {num_templates} templates and {num_categories} defined categories to {self.metadata_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save metadata file: {self.metadata_path} - {e}", exc_info=True)
            return False

    def get_template_category(self, template_name: str) -> Optional[str]:
        """Gets the category for a given template name (without .txt extension)."""
        template_filename = f"{template_name}.txt"
        return self.metadata.get("_templates", {}).get(template_filename, {}).get("category")

    def set_template_category(self, template_name: str, category: Optional[str]) -> bool:
        """Sets the category for a given template name (without .txt extension). Saves metadata."""
        template_filename = f"{template_name}.txt"
        templates_meta = self.metadata.setdefault("_templates", {})

        if template_filename not in templates_meta:
            templates_meta[template_filename] = {}
        
        if category is None:
            if "category" in templates_meta[template_filename]:
                del templates_meta[template_filename]["category"]
                self.logger.info(f"Removed category for template '{template_filename}'.")
        else:
            templates_meta[template_filename]["category"] = category
            self.logger.info(f"Set category for template '{template_filename}' to '{category}'.")
            # Ensure this category is in defined list
            if category not in self.metadata.get("_defined_categories", []):
                self.metadata.setdefault("_defined_categories", []).append(category)
                self.logger.info(f"Implicitly added category '{category}' to defined list.")

        return self._save_metadata()

    def get_all_categories(self) -> List[str]:
        """Returns a sorted list of unique category names from defined list and template assignments."""
        defined_categories = set(self.metadata.get("_defined_categories", []))
        assigned_categories = set()
        for item_metadata in self.metadata.get("_templates", {}).values():
            category = item_metadata.get("category")
            if category:
                assigned_categories.add(category)
        
        all_unique_categories = defined_categories.union(assigned_categories)
        return sorted(list(all_unique_categories))
    
    def add_defined_category(self, category_name: str) -> bool:
        """Adds a category to the list of defined categories if not already present. Saves metadata."""
        if not category_name:
            self.logger.warning("Cannot add empty category name.")
            return False
        defined_list = self.metadata.setdefault("_defined_categories", [])
        if category_name not in defined_list:
            defined_list.append(category_name)
            self.logger.info(f"Added '{category_name}' to defined categories.")
            return self._save_metadata()
        self.logger.info(f"Category '{category_name}' already in defined list.")
        return True # Already exists, considered success

    def delete_defined_category(self, category_name: str, unassign_from_templates: bool = True) -> bool:
        """Deletes a category from the defined list. Optionally unassigns it from all templates. Saves metadata."""
        defined_list = self.metadata.get("_defined_categories", [])
        changed_meta = False
        if category_name in defined_list:
            defined_list.remove(category_name)
            self.logger.info(f"Removed '{category_name}' from defined categories.")
            changed_meta = True
        else:
            self.logger.warning(f"Category '{category_name}' not found in defined list for deletion.")
            # Still proceed to unassign if requested, as it might exist in template assignments

        if unassign_from_templates:
            templates_meta = self.metadata.get("_templates", {})
            for template_filename, item_meta in templates_meta.items():
                if item_meta.get("category") == category_name:
                    del item_meta["category"]
                    self.logger.info(f"Unassigned category '{category_name}' from template '{template_filename}'.")
                    changed_meta = True
        
        if changed_meta:
            return self._save_metadata()
        return True # No changes needed or category wasn't defined

    def rename_defined_category(self, old_category_name: str, new_category_name: str) -> bool:
        """Renames a category in the defined list and updates all template assignments. Saves metadata."""
        if not old_category_name or not new_category_name or old_category_name == new_category_name:
            self.logger.warning(f"Invalid rename: old='{old_category_name}', new='{new_category_name}'.")
            return False

        defined_list = self.metadata.get("_defined_categories", [])
        renamed_in_defined = False
        if old_category_name in defined_list:
            defined_list.remove(old_category_name)
            if new_category_name not in defined_list:
                 defined_list.append(new_category_name)
            renamed_in_defined = True
            self.logger.info(f"Renamed '{old_category_name}' to '{new_category_name}' in defined categories.")
        else:
            # If old_name is not in defined list, but new_name is, we might have an issue or user intent is to just ensure new_name is defined.
            # For now, if old_name not defined, we proceed to rename in templates only if there is something to rename.
             self.logger.warning(f"Category '{old_category_name}' not found in defined list for renaming.")

        renamed_in_templates = False
        templates_meta = self.metadata.get("_templates", {})
        for item_meta in templates_meta.values():
            if item_meta.get("category") == old_category_name:
                item_meta["category"] = new_category_name
                renamed_in_templates = True
        
        if renamed_in_templates:
            self.logger.info(f"Updated template assignments from '{old_category_name}' to '{new_category_name}'.")
            # Ensure new category is in defined list if it came from templates
            if new_category_name not in self.metadata.get("_defined_categories", []) :
                self.metadata.setdefault("_defined_categories", []).append(new_category_name)
                self.logger.info(f"Implicitly added renamed category '{new_category_name}' to defined list.")

        if renamed_in_defined or renamed_in_templates:
            return self._save_metadata()
        
        self.logger.info(f"Rename category: No changes made for '{old_category_name}' to '{new_category_name}'.")
        return True # No changes were necessary

    def remove_template_metadata(self, template_name: str) -> bool:
        """Removes all metadata for a given template name (without .txt extension). Saves metadata."""
        template_filename = f"{template_name}.txt"
        templates_meta = self.metadata.get("_templates", {})
        if template_filename in templates_meta:
            del templates_meta[template_filename]
            self.logger.info(f"Removed metadata for template '{template_filename}'.")
            return self._save_metadata()
        self.logger.warning(f"Attempted to remove metadata for non-existent template: '{template_filename}'.")
        return False # Or True if not finding it is also considered a success for removal

    def load_template(self, template_name: str) -> Optional[str]:
        """Loads the content of a specific prompt template file."""
        # Ensure template name doesn't have extension
        template_name = os.path.splitext(template_name)[0]
        file_path = os.path.join(self.prompts_dir, f"{template_name}.txt")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            self.logger.error(f"Prompt template file not found: {file_path}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to read prompt template file: {file_path} - {e}", exc_info=True)
            return None

    def get_formatted_prompt(self, template_name: Optional[str], data: Dict[str, Any], analysis_type: Optional[str] = None) -> str:
        """
        Loads a template, formats it with the provided data, and returns the final prompt.
        Handles specific logic for analysis types if template_name is derived from it.
        """
        effective_template_name = template_name

        # Map analysis type to template name if template_name is not provided
        if analysis_type and not effective_template_name:
             template_name_map = {
                 '摘要': 'summary', '深度分析': 'deep_analysis',
                 '关键观点': 'key_points', '事实核查': 'fact_check',
                 '重要程度和立场分析': 'importance_stance',
                 '新闻相似度分析': 'news_similarity_enhanced', '多角度整合': 'news_similarity_enhanced',
                 '对比分析': 'news_similarity_enhanced', '时间线梳理': 'news_similarity_enhanced',
                 '信源多样性分析': 'news_similarity_enhanced'
                 # Add other mappings as needed
             }
             effective_template_name = template_name_map.get(analysis_type)

        if effective_template_name:
            template = self.load_template(effective_template_name)
            if template:
                try:
                    # Ensure all necessary keys are present in data for formatting
                    # Extract data safely using .get with defaults
                    format_data = {
                        'title': data.get('title', '无标题'),
                        'source': data.get('source_name', data.get('source', '未知来源')), # Allow 'source' as fallback
                        'pub_date': str(data.get('pub_date', data.get('publish_time', '未知日期'))), # Ensure pub_date is string
                        'content': data.get('content', data.get('summary', data.get('description', '无内容'))), # Flexible content source
                        'news_items': data.get('news_items', '') # 添加对news_items占位符的支持
                    }
                    
                    # 特殊处理news_similarity模板，确保news_items存在
                    if (effective_template_name == 'news_similarity' or effective_template_name == 'news_similarity_enhanced') and 'news_items' not in data:
                        self.logger.warning(f"Missing 'news_items' key for {effective_template_name} template, using empty string")
                        # 已经在format_data中设置了默认值，不需要额外处理
                    return template.format(**format_data)
                except KeyError as e:
                    self.logger.error(f"Missing key in prompt template '{effective_template_name}' for data: {e}")
                    error_type = analysis_type or effective_template_name
                    return f"错误：无法生成 '{error_type}' 的提示，模板占位符错误。"
            else:
                error_type = analysis_type or effective_template_name
                self.logger.error(f"Could not load prompt template: {effective_template_name}.txt")
                return f"错误：无法加载 '{error_type}' 的提示模板。"
        else:
            # Fallback to generic prompt if no specific template found or requested
            self.logger.warning(f"No specific prompt template found for analysis type: '{analysis_type}'. Using generic prompt.")
            # Extract data safely for generic prompt
            title = data.get('title', '无标题')
            source = data.get('source_name', data.get('source', '未知来源'))
            pub_date = str(data.get('pub_date', data.get('publish_time', '未知日期')))
            content = data.get('content', data.get('summary', data.get('description', '无内容')))
            effective_analysis_type = analysis_type or "分析" # Use "分析" if type is None
            return f"请对以下新闻进行{effective_analysis_type}。\n\n新闻标题: {title}\n新闻来源: {source}\n发布日期: {pub_date}\n新闻内容:\n{content}"

    def save_prompt_content(self, template_name: str, content: str) -> bool:
        """Saves the content of a specific prompt template file."""
        template_filename = f"{template_name}.txt"
        file_path = os.path.join(self.prompts_dir, template_filename)
        try:
            if not os.path.exists(self.prompts_dir):
                 os.makedirs(self.prompts_dir, exist_ok=True)
                 self.logger.info(f"Prompts directory created: {self.prompts_dir} before saving {template_filename}")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.logger.info(f"Saved prompt content for '{template_filename}' to {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save prompt file: {file_path} - {e}", exc_info=True)
            return False

    def delete_prompt_file(self, template_name: str) -> bool:
        """Deletes a specific prompt template file."""
        template_filename = f"{template_name}.txt"
        file_path = os.path.join(self.prompts_dir, template_filename)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info(f"Deleted prompt file: {file_path}")
                return True
            else:
                self.logger.warning(f"Attempted to delete non-existent prompt file: {file_path}")
                return True # Or False, depending on desired strictness
        except Exception as e:
            self.logger.error(f"Failed to delete prompt file: {file_path} - {e}", exc_info=True)
            return False

# Example usage (for testing within this file)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    # Assume prompts are in ../prompts relative to this file (src/llm -> src/prompts)
    # Create dummy prompts dir and files for testing
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompts_test_dir = os.path.join(os.path.dirname(script_dir), 'prompts_test_temp')
    os.makedirs(prompts_test_dir, exist_ok=True)
    summary_template_path = os.path.join(prompts_test_dir, 'summary.txt')
    chat_system_template_path = os.path.join(prompts_test_dir, 'chat_system.txt')
    deep_analysis_template_path = os.path.join(prompts_test_dir, 'deep_analysis.txt')


    print(f"Creating dummy templates in: {prompts_test_dir}")
    with open(summary_template_path, 'w', encoding='utf-8') as f:
        f.write("请为以下新闻生成摘要：\n标题: {title}\n来源: {source}\n日期: {pub_date}\n内容: {content}")
    with open(chat_system_template_path, 'w', encoding='utf-8') as f:
        f.write("你是一个乐于助人的AI助手。")
    with open(deep_analysis_template_path, 'w', encoding='utf-8') as f:
        f.write("请对以下新闻进行深度分析：\n标题: {title}\n内容: {content}")


    # Initialize pointing to the test directory's parent
    pm = PromptManager(base_dir=os.path.dirname(script_dir))
    # Override prompts_dir for testing
    pm.prompts_dir = prompts_test_dir
    print(f"Using test prompts dir: {pm.prompts_dir}")


    # Test loading a template
    print("\n--- Testing load_template ---")
    summary_tmpl = pm.load_template('summary')
    print(f"Loaded 'summary' template:\n{summary_tmpl}")
    missing_tmpl = pm.load_template('non_existent')
    print(f"Loaded 'non_existent' template: {missing_tmpl}")

    # Test formatting a prompt
    print("\n--- Testing get_formatted_prompt ---")
    news_data_dict = {
        'title': '测试新闻',
        'source_name': '测试来源',
        'publish_time': '2024-01-01',
        'content': '这是一条测试新闻内容。'
    }
    # Simulate a NewsArticle object
    class MockNewsArticle:
        def __init__(self, title, source_name, publish_time, content, summary=None):
            self.title = title
            self.source_name = source_name
            self.publish_time = publish_time # Assume datetime object or string
            self.content = content
            self.summary = summary
    news_data_obj = MockNewsArticle(
        title='测试对象新闻',
        source_name='对象来源',
        publish_time='2024-01-02 10:00:00',
        content='这是来自对象的新闻内容。',
        summary='对象摘要'
    )


    print("\n--- Formatting with Dict Data ---")
    summary_prompt_dict = pm.get_formatted_prompt(template_name='summary', data=news_data_dict)
    print(f"Formatted 'summary' prompt (dict):\n{summary_prompt_dict}")

    analysis_prompt_dict = pm.get_formatted_prompt(template_name=None, data=news_data_dict, analysis_type='深度分析')
    print(f"\nFormatted '深度分析' prompt (dict, using map):\n{analysis_prompt_dict}")

    generic_prompt_dict = pm.get_formatted_prompt(template_name=None, data=news_data_dict, analysis_type='未知类型')
    print(f"\nFormatted '未知类型' prompt (dict, fallback to generic):\n{generic_prompt_dict}")

    print("\n--- Formatting with Object Data ---")
    # Convert object to dict before passing, as get_formatted_prompt expects dict
    news_data_obj_dict = {
         'title': news_data_obj.title,
         'source_name': news_data_obj.source_name,
         'publish_time': news_data_obj.publish_time,
         'content': news_data_obj.content,
         'summary': news_data_obj.summary
    }
    summary_prompt_obj = pm.get_formatted_prompt(template_name='summary', data=news_data_obj_dict)
    print(f"Formatted 'summary' prompt (obj):\n{summary_prompt_obj}")

    analysis_prompt_obj = pm.get_formatted_prompt(template_name=None, data=news_data_obj_dict, analysis_type='深度分析')
    print(f"\nFormatted '深度分析' prompt (obj, using map):\n{analysis_prompt_obj}")


    # Test loading chat system prompt
    print("\n--- Testing load chat_system ---")
    chat_system_prompt = pm.load_template('chat_system')
    print(f"Loaded 'chat_system' template: {chat_system_prompt}")


    # Clean up dummy files/dir
    try:
        print("\nCleaning up test files and directory...")
        os.remove(summary_template_path)
        os.remove(chat_system_template_path)
        os.remove(deep_analysis_template_path)
        os.rmdir(prompts_test_dir)
        print("Cleanup complete.")
    except OSError as e:
        print(f"Error during cleanup: {e}")