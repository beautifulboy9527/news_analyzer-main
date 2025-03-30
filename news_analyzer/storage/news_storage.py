"""
新闻数据存储

负责保存和加载新闻数据。
"""

import os
import json
import logging
import shutil
from datetime import datetime


class NewsStorage:
    """新闻数据存储类"""

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

    def _ensure_dir(self, directory):
        """确保目录存在

        Args:
            directory: 目录路径
        """
        if not os.path.exists(directory):
            os.makedirs(directory)
            self.logger.info(f"创建目录: {directory}")

    def save_news(self, news_items, filename=None):
        """保存新闻数据

        Args:
            news_items: 新闻条目列表 (应为字典列表)
            filename: 文件名（可选，默认使用时间戳）

        Returns:
            str: 保存的文件路径 或 None
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
            if news_items and not isinstance(news_items[0], dict):
                 self.logger.error(f"save_news 接收到的 news_items 内容不是字典，第一项类型: {type(news_items[0])}")
                 # 可以在这里尝试转换，或者直接返回错误
                 # news_items = self._convert_articles_to_dicts(news_items) # 假设有转换方法
                 return None

            self.logger.info(f"准备写入 {len(news_items)} 条新闻 (字典格式) 到临时文件: {temp_filepath}")
            # if news_items: # 记录第一条数据样本
            #     self.logger.debug(f"写入数据样本: {json.dumps(news_items[0], ensure_ascii=False)}") # 使用 json.dumps 记录样本

            try:
                with open(temp_filepath, 'w', encoding='utf-8') as f:
                    json.dump(news_items, f, ensure_ascii=False, indent=2)
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


    def load_news(self, filename=None):
        """加载新闻数据

        Args:
            filename: 文件名（可选，默认加载最新的文件）

        Returns:
            list: 新闻条目列表 (字典列表)
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


    def list_news_files(self):
        """列出所有新闻文件

        Returns:
            list: 文件名列表，按日期排序
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
            return []