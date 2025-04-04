import os
import logging
from typing import Optional, Dict, Any

class PromptManager:
    """
    Manages loading and formatting of LLM prompt templates.
    """
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

        if not os.path.isdir(self.prompts_dir):
             self.logger.warning(f"Prompts directory does not exist or is not a directory: {self.prompts_dir}")
        else:
             self.logger.info(f"PromptManager initialized. Prompts directory: {self.prompts_dir}")


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
                 '关键观点': 'key_points', '事实核查': 'fact_check'
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
                        'content': data.get('content', data.get('summary', data.get('description', '无内容'))) # Flexible content source
                    }
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