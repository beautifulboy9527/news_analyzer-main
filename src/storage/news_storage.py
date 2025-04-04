"""
新闻数据存储

负责保存和加载新闻数据。
"""

import os
import json
import logging
import shutil
from typing import List, Dict, Optional # 确保导入
from datetime import datetime
from src.models import NewsArticle # 导入 NewsArticle


def convert_datetime_to_iso(obj):
    """递归转换数据结构中的 datetime 对象为 ISO 格式字符串"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: convert_datetime_to_iso(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime_to_iso(item) for item in obj]
    return obj


class NewsStorage:
    """新闻数据存储类"""

    HISTORY_FILE_NAME = "browsing_history.json"
    READ_STATUS_FILE_NAME = "read_status.json" # 新增：用于存储已读链接的文件名
    MAX_HISTORY_ITEMS = 1000 # 定义最大历史记录条数

    def __init__(self, data_dir="data"):
        """初始化存储器

        Args:
            data_dir: 数据存储目录
        """
        self.logger = logging.getLogger('news_analyzer.storage')

        # 优先使用相对路径，兼容运行位置
        self.app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(self.app_root, data_dir)

        # 如果上述路径不存在，尝试使用绝对路径
        if not os.path.exists(self.data_dir):
            self.data_dir = os.path.abspath(data_dir)

        # 如果仍然不存在，尝试使用 C:\Users\Administrator\Desktop\news_analyzer\data (根据需要调整)
        # if not os.path.exists(self.data_dir):
        #     self.data_dir = r"C:\Users\Administrator\Desktop\news_analyzer\data"

        # 确保目录存在
        self._ensure_dir(self.data_dir)
        self._ensure_dir(os.path.join(self.data_dir, "news"))
        self._ensure_dir(os.path.join(self.data_dir, "analysis"))

        self.logger.info(f"数据存储目录: {self.data_dir}")

        # 加载已读状态到内存中的集合
        self.read_items: set[str] = self._load_read_status()
        self.logger.info(f"已加载 {len(self.read_items)} 条已读状态记录")

    def _ensure_dir(self, directory):
        """确保目录存在

        Args:
            directory: 目录路径
        """
        if not os.path.exists(directory):
            os.makedirs(directory)
            self.logger.info(f"创建目录: {directory}")

    def save_news(self, news_items: List[Dict], filename: Optional[str] = None) -> Optional[str]:
        """保存新闻数据到 JSON 文件。

        使用原子写入方式（先写入临时文件，再替换原文件）以保证数据完整性。

        Args:
            news_items (List[Dict]): 要保存的新闻条目列表，每个条目应为字典。
            filename (Optional[str], optional): 要保存的文件名。
                                              如果为 None，则使用当前时间戳生成文件名。
                                              默认为 None。

        Returns:
            Optional[str]: 成功保存的文件路径，如果保存失败则返回 None。
        """
        if not news_items:
            self.logger.warning("没有新闻数据可保存")
            return None

        # 如果没有指定文件名，使用时间戳
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"news_{timestamp}.json"

        filepath = os.path.join(self.data_dir, "news", filename)
        temp_filepath = filepath + ".tmp" # 临时文件名

        try:
            # 1. 写入临时文件
            # 确认 news_items 是列表且内容是字典
            if not isinstance(news_items, list):
                 self.logger.error(f"save_news 接收到的 news_items 不是列表，类型: {type(news_items)}")
                 return None
            # Check if list is not empty before checking the first item's type
            if news_items and not isinstance(news_items[0], dict):
                 self.logger.error(f"save_news 接收到的 news_items 内容不是字典，第一项类型: {type(news_items[0])}")
                 # 可以在这里尝试转换，或者直接返回错误
                 # news_items = self._convert_articles_to_dicts(news_items) # 假设有转换方法
                 return None

            self.logger.info(f"准备写入 {len(news_items)} 条新闻 (字典格式) 到临时文件: {temp_filepath}")
            # if news_items: # 记录第一条数据样本
            #     self.logger.debug(f"写入数据样本: {json.dumps(news_items[0], ensure_ascii=False)}") # 使用 json.dumps 记录样本

            # --- 在写入前转换 datetime 对象 ---
            try:
                serializable_news_items = convert_datetime_to_iso(news_items)
                self.logger.debug("已将 news_items 中的 datetime 对象转换为 ISO 字符串")
            except Exception as convert_e:
                 self.logger.error(f"转换 datetime 对象时出错: {convert_e}", exc_info=True)
                 # 如果转换失败，可以选择不保存或保存原始数据（可能导致 TypeError）
                 # 这里选择不保存以避免错误
                 return None
            # --- 转换结束 ---

            try:
                with open(temp_filepath, 'w', encoding='utf-8') as f:
                    # 使用转换后的数据进行 dump
                    json.dump(serializable_news_items, f, ensure_ascii=False, indent=2)
                self.logger.debug(f"成功写入 JSON 数据到临时文件: {temp_filepath}")
            except TypeError as te:
                 self.logger.error(f"JSON 序列化失败 (TypeError): {te}", exc_info=True)
                 raise # 重新抛出异常，让外层捕获
            except Exception as dump_e:
                 self.logger.error(f"写入临时文件时发生未知错误: {dump_e}", exc_info=True)
                 raise # 重新抛出异常

            # 2. 写入成功后，替换原文件
            try:
                 os.replace(temp_filepath, filepath)
            except OSError: # 例如在某些系统上跨设备移动时可能失败
                 shutil.move(temp_filepath, filepath) # shutil.move 更通用

            self.logger.info(f"保存了 {len(news_items)} 条新闻到 {filepath}")
            return filepath

        except Exception as e:
            self.logger.error(f"保存新闻数据失败: {e}", exc_info=True)
            # 如果写入或替换过程中出错，尝试删除临时文件
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                    self.logger.info(f"已删除写入失败的临时文件: {temp_filepath}")
                except OSError as remove_e:
                     self.logger.error(f"删除临时文件 {temp_filepath} 失败: {remove_e}")
            return None


    def load_news(self, filename: Optional[str] = None) -> List[Dict]:
        """从 JSON 文件加载新闻数据。

        如果未指定文件名，则尝试加载最新的有效新闻文件。
        如果加载过程中遇到 JSON 解析错误，会将损坏的文件重命名并尝试加载下一个。

        Args:
            filename (Optional[str], optional): 要加载的特定文件名。
                                              如果为 None，则加载最新的有效文件。
                                              默认为 None。

        Returns:
            List[Dict]: 加载的新闻条目列表（字典列表）。如果加载失败或没有找到文件，则返回空列表。
        """
        news_dir = os.path.join(self.data_dir, "news")

        # 如果没有指定文件名，加载最新的有效文件
        if not filename:
            files = self.list_news_files() # 获取未损坏的 .json 文件列表，已排序
            if not files:
                self.logger.warning("没有找到有效的新闻数据文件")
                return []

            # --- 从最新文件开始尝试加载 ---
            for fname in reversed(files): # 从列表末尾（最新）开始
                filepath = os.path.join(news_dir, fname)
                self.logger.info(f"尝试加载文件: {filepath}")
                try:
                    # 检查文件是否存在（理论上 list_news_files 后应该存在）
                    if not os.path.exists(filepath):
                        self.logger.warning(f"文件在尝试加载时消失了: {filepath}")
                        continue

                    with open(filepath, 'r', encoding='utf-8') as f:
                        news_items = json.load(f)
                        # 验证加载的是列表
                        if not isinstance(news_items, list):
                             self.logger.error(f"文件内容不是列表格式: {filepath}")
                             raise json.JSONDecodeError("文件内容不是列表", "", 0)

                    self.logger.info(f"成功从 {filepath} 加载了 {len(news_items)} 条新闻")
                    return news_items # 加载成功，返回结果

                except json.JSONDecodeError as json_e:
                    self.logger.error(f"加载新闻数据失败 (JSONDecodeError): {filepath} - {json_e}")
                    # 重命名损坏文件
                    try:
                        corrupted_filepath = filepath + ".corrupted_" + datetime.now().strftime("%Y%m%d%H%M%S")
                        os.rename(filepath, corrupted_filepath)
                        self.logger.warning(f"已将损坏的文件重命名为: {corrupted_filepath}")
                    except OSError as rename_e:
                        self.logger.error(f"重命名损坏文件失败: {rename_e}")
                    # 继续尝试下一个（更旧的）文件
                    continue
                except Exception as e:
                    self.logger.error(f"加载新闻数据时发生未知错误: {filepath} - {e}", exc_info=True)
                    # 继续尝试下一个文件
                    continue

            # 如果循环结束都没有成功加载
            self.logger.warning("尝试加载所有有效新闻文件均失败")
            return []
            # --- 加载最新有效文件逻辑结束 ---

        # --- 如果指定了 filename，则只加载该文件 ---
        else:
            filepath = os.path.join(news_dir, filename)
            try:
                if not os.path.exists(filepath):
                    self.logger.warning(f"指定的文件不存在: {filepath}")
                    return []

                with open(filepath, 'r', encoding='utf-8') as f:
                    news_items = json.load(f)
                    if not isinstance(news_items, list):
                         self.logger.error(f"指定文件内容不是列表格式: {filepath}")
                         raise json.JSONDecodeError("文件内容不是列表", "", 0)

                self.logger.info(f"从指定文件 {filepath} 加载了 {len(news_items)} 条新闻")
                return news_items

            except json.JSONDecodeError as json_e: # 捕获特定的 JSON 解析错误
                self.logger.error(f"加载指定新闻数据失败 (JSONDecodeError): {filepath} - {json_e}")
                # 重命名损坏文件
                try:
                    corrupted_filepath = filepath + ".corrupted_" + datetime.now().strftime("%Y%m%d%H%M%S")
                    os.rename(filepath, corrupted_filepath)
                    self.logger.warning(f"已将损坏的指定文件重命名为: {corrupted_filepath}")
                except OSError as rename_e:
                    self.logger.error(f"重命名损坏的指定文件失败: {rename_e}")
                return [] # 返回空列表
            except Exception as e: # 捕获其他可能的异常
                self.logger.error(f"加载指定新闻数据时发生未知错误: {filepath} - {e}", exc_info=True)
                return []


    def list_news_files(self) -> List[str]:
        """列出 `data/news` 目录下所有有效的新闻文件名。

        排除包含 '.corrupted_' 的文件，并按文件名（通常是时间戳）排序。

        Returns:
            List[str]: 有效新闻文件名的列表，按字母顺序排序（通常对应时间顺序）。
                       如果目录不存在或发生错误，返回空列表。
        """
        news_dir = os.path.join(self.data_dir, "news")
        if not os.path.exists(news_dir):
            self.logger.warning(f"新闻目录不存在: {news_dir}")
            return []

        try:
            # 只列出 .json 文件，排除包含 .corrupted_ 的文件
            files = [f for f in os.listdir(news_dir) if f.endswith('.json') and '.corrupted_' not in f]
            return sorted(files)
        except Exception as e:
            self.logger.error(f"列出新闻文件失败: {str(e)}")
            return [] # Return empty list on error
    def add_history_entry(self, article: NewsArticle):
        """从 NewsArticle 对象创建并保存一条浏览历史记录。

        Args:
            article (NewsArticle): 要记录的新闻文章对象。
        """
        if not isinstance(article, NewsArticle):
            self.logger.error(f"add_history_entry 接收到的参数不是 NewsArticle 对象，类型: {type(article)}")
            return

        entry = {
            "title": article.title,
            "link": article.link,
            "source_name": article.source_name,
            "viewed_at": datetime.now().isoformat() # 添加浏览时间戳
        }
        self.logger.info(f"准备添加浏览历史: {article.title[:30]}...")
        self.save_history_entry(entry)



    def save_history_entry(self, entry: Dict):
        self.logger.info("NewsStorage: save_history_entry 方法被调用") # Added log
        """保存单条浏览历史记录到 JSON 文件。

        将新的历史记录添加到列表开头，移除具有相同链接的旧记录，
        并截断列表以保持在 `MAX_HISTORY_ITEMS` 限制内。
        使用原子写入方式保存。

        Args:
            entry (Dict): 要保存的单条历史记录字典，应包含 'link', 'title', 'source_name', 'browsed_at' 等键。
        """
        history_filepath = os.path.join(self.data_dir, self.HISTORY_FILE_NAME)
        self.logger.debug(f"准备保存浏览历史到: {history_filepath}")

        history: List[Dict] = []
        # 1. 加载现有历史
        if os.path.exists(history_filepath):
            try:
                with open(history_filepath, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                if isinstance(loaded_data, list):
                    history = loaded_data
                else:
                    self.logger.warning(f"历史文件 {history_filepath} 格式不正确，将重置为空列表。")
                    history = []
            except (json.JSONDecodeError, IOError) as e:
                self.logger.error(f"读取浏览历史文件 {history_filepath} 失败: {e}，将重置为空列表。")
                history = []
            except Exception as e:
                 self.logger.error(f"加载浏览历史时发生未知错误: {e}", exc_info=True)
                 history = [] # 保守起见，重置历史

        # 2. 移除具有相同链接的旧条目（确保最新浏览时间）
        link_to_check = entry.get('link')
        if link_to_check:
            history = [item for item in history if item.get('link') != link_to_check]
            self.logger.debug(f"移除了链接为 {link_to_check} 的旧历史条目 (如果存在)")

        # 3. 将新条目插入到列表开头
        history.insert(0, entry)
        self.logger.debug(f"将新历史条目插入列表开头: {entry.get('title', '')[:30]}...")

        # 4. 截断历史记录到最大长度
        if len(history) > self.MAX_HISTORY_ITEMS:
            history = history[:self.MAX_HISTORY_ITEMS]
            self.logger.debug(f"历史记录已截断至 {self.MAX_HISTORY_ITEMS} 条")

        # 5. 保存更新后的历史记录到临时文件
        temp_filepath = history_filepath + ".tmp"
        try:
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2) # 在 try 块中执行写入
            self.logger.debug(f"成功写入浏览历史到临时文件: {temp_filepath}")

            # 6. 替换旧文件
            try:
                 os.replace(temp_filepath, history_filepath)
            except OSError:
                 shutil.move(temp_filepath, history_filepath) # shutil.move 更通用

            # 7. 记录成功日志
            self.logger.info(f"成功将 {len(history)} 条浏览历史写入到 {history_filepath}") # 明确记录写入成功和数量

        except Exception as e:
            # 8. 记录详细错误日志
            self.logger.error(f"写入浏览历史文件 {history_filepath} 失败: {e}", exc_info=True) # 记录写入失败的原因
            # 尝试删除临时文件
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                    self.logger.info(f"已删除写入失败的历史临时文件: {temp_filepath}")
                except OSError as remove_e:
                     self.logger.error(f"删除历史临时文件 {temp_filepath} 失败: {remove_e}")
            # Consider re-raising or returning an error indicator if needed

    def load_history(self) -> List[Dict]:
        self.logger.info("NewsStorage: load_history 方法被调用") # Added log
        """加载浏览历史记录。

        Returns:
            List[Dict]: 包含历史记录字典的列表，按浏览时间降序排列。
                       如果文件不存在或加载失败，返回空列表。
        """
        history_filepath = os.path.join(self.data_dir, self.HISTORY_FILE_NAME)
        if not os.path.exists(history_filepath):
            self.logger.info("浏览历史文件不存在。")
            return []
        try:
            with open(history_filepath, 'r', encoding='utf-8') as f:
                history = json.load(f)
            if not isinstance(history, list):
                self.logger.warning(f"历史文件 {history_filepath} 格式不正确，返回空列表。")
                return []
            self.logger.info(f"成功加载 {len(history)} 条浏览历史记录。")
            return history
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"读取浏览历史文件 {history_filepath} 失败: {e}，返回空列表。")
            return []
        except Exception as e:
            self.logger.error(f"加载浏览历史时发生未知错误: {e}", exc_info=True)
            return []

    # --- 已读状态管理 ---
    def _load_read_status(self) -> set[str]:
        """从文件加载已读链接集合"""
        filepath = os.path.join(self.data_dir, self.READ_STATUS_FILE_NAME)
        if not os.path.exists(filepath):
            return set()
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return set(data)
            else:
                self.logger.warning(f"已读状态文件 {filepath} 格式不正确，应为列表。将重置。")
                return set()
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"读取已读状态文件 {filepath} 失败: {e}。将重置。")
            return set()
        except Exception as e:
            self.logger.error(f"加载已读状态时发生未知错误: {e}", exc_info=True)
            return set()

    def _save_read_status(self):
        """将内存中的已读项目 ID 集合保存到文件"""
        filepath = os.path.join(self.data_dir, self.READ_STATUS_FILE_NAME)
        temp_filepath = filepath + ".tmp"
        try:
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                json.dump(list(self.read_items), f, ensure_ascii=False, indent=2)
            try:
                 os.replace(temp_filepath, filepath)
            except OSError:
                 shutil.move(temp_filepath, filepath)
            self.logger.debug(f"已读状态已保存到 {filepath}")
        except Exception as e:
            self.logger.error(f"保存已读状态到 {filepath} 失败: {e}", exc_info=True)
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except OSError as remove_e:
                     self.logger.error(f"删除已读状态临时文件 {temp_filepath} 失败: {remove_e}")

    def is_item_read(self, item_id: str) -> bool:
        """检查给定的新闻标识符是否存在于已读集合中。

        Args:
            item_id (str): 要检查的新闻标识符 (例如 URL 或 ID)。

        Returns:
            bool: 如果已读则返回 True，否则返回 False。
        """
        # self.logger.debug(f"检查项目是否已读: {item_id}") # 可以取消注释以进行调试
        return item_id in self.read_items

    def add_read_item(self, item_id: str):
        """将一个新闻标识符添加到已读集合中，并确保持久化存储。

        Args:
            item_id (str): 要标记为已读的新闻标识符 (例如 URL 或 ID)。
        """

    def get_read_items(self) -> set[str]:
        """返回内存中存储的所有已读新闻的标识符集合"""
        # self.logger.debug("获取所有已读项目") # 可以取消注释以进行调试
        return self.read_items
        self.logger.info(f"标记项目为已读: {item_id}")
        if item_id not in self.read_items:
            self.read_items.add(item_id)
            self._save_read_status() # 保存更改
            self.logger.debug(f"项目 {item_id} 已添加到已读集合并保存")
        else:
            self.logger.debug(f"项目 {item_id} 已存在于已读集合中")

    # --- 新增：删除历史记录 ---
    def delete_history_entry(self, link: str) -> bool:
        """
        从浏览历史记录文件中删除指定链接的条目
        """
        self.logger.info(f"NewsStorage: 请求删除历史记录: {link}")
        history_filepath = os.path.join(self.data_dir, self.HISTORY_FILE_NAME)
        if not os.path.exists(history_filepath):
            self.logger.warning("无法删除历史记录：历史文件不存在。")
            return False

        history = self.load_history() # 加载当前历史
        original_length = len(history)
        new_history = [item for item in history if item.get('link') != link]
        items_removed = original_length - len(new_history)

        if items_removed > 0:
            self.logger.debug(f"从历史记录中移除了 {items_removed} 条链接为 {link} 的条目")
            # 保存修改后的历史
            temp_filepath = history_filepath + ".tmp"
            try:
                with open(temp_filepath, 'w', encoding='utf-8') as f:
                    json.dump(new_history, f, ensure_ascii=False, indent=2)
                try:
                     os.replace(temp_filepath, history_filepath)
                except OSError:
                     shutil.move(temp_filepath, history_filepath)
                self.logger.info(f"已更新浏览历史文件，移除了链接 {link}")
                return True
            except Exception as e:
                self.logger.error(f"保存删除后的浏览历史失败: {e}", exc_info=True)
                if os.path.exists(temp_filepath):
                    try:
                        os.remove(temp_filepath)
                    except OSError as remove_e:
                         self.logger.error(f"删除历史临时文件 {temp_filepath} 失败: {remove_e}")
                return False # 保存失败
        else:
            self.logger.warning(f"未在历史记录中找到要删除的链接: {link}")
            return False # 未找到或未删除

    def clear_all_history(self):
        """
        清空所有浏览历史记录
        """
        history_filepath = os.path.join(self.data_dir, self.HISTORY_FILE_NAME)
        self.logger.warning(f"请求清空所有浏览历史记录文件: {history_filepath}")
        try:
            if os.path.exists(history_filepath):
                os.remove(history_filepath)
                self.logger.info("浏览历史文件已删除。")
            else:
                self.logger.info("浏览历史文件不存在，无需删除。")
            return True
        except Exception as e:
            self.logger.error(f"清空浏览历史文件失败: {e}", exc_info=True)
            return False

    def clear_all_read_status(self):
        """
        清空所有已读状态记录
        """
        read_status_filepath = os.path.join(self.data_dir, self.READ_STATUS_FILE_NAME)
        self.logger.warning(f"请求清空所有已读状态文件: {read_status_filepath}")
        try:
            if os.path.exists(read_status_filepath):
                os.remove(read_status_filepath)
                self.logger.info("已读状态文件已删除。")
            else:
                self.logger.info("已读状态文件不存在，无需删除。")
            self.read_items = set() # 清空内存中的集合
            return True
        except Exception as e:
            self.logger.error(f"清空已读状态文件失败: {e}", exc_info=True)
            return False

    def close(self):
        """
        关闭存储资源(如果需要)
        """
        # 目前基于文件，不需要显式关闭
        self.logger.info("NewsStorage closed (no specific resources to release).")