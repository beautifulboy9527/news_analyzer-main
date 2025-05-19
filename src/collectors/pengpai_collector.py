#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
澎湃新闻收集器模块
"""

import logging
import requests
import re # 导入正则表达式模块
import os # 导入 os 模块
import uuid # 导入 uuid 模块
import shutil # 确保导入 shutil
# 移除了 tempfile, uuid, shutil, base64, BytesIO, PIL.Image

import json # 导入 json 模块
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, JavascriptException # 导入 JavascriptException
import time
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Callable, Any
from urllib.parse import urljoin
from PySide6.QtCore import QObject, Signal as pyqtSignal # 统一使用 PySide6
import platform # 需要导入 platform
import subprocess # 需要导入 subprocess
from datetime import datetime, timedelta
import threading # Add this import

from src.models import NewsSource
from src.collectors.pengpai import DEFAULT_PENGPAI_CONFIG # IMPORT ADDED

class PengpaiCollector(QObject): # 继承 QObject 以使用信号
    """
    负责从澎湃新闻网站抓取新闻的收集器。
    """
    # 定义选择器失效信号，传递源名称
    selector_failed = pyqtSignal(str)
    # 澎湃新闻手机版首页 URL
    MOBILE_URL = "https://m.thepaper.cn"
    _initial_cleanup_done = False # 类变量，用于标记启动清理是否已完成

    _webdriver_instance = None
    _webdriver_options = None
    _is_webdriver_initialized = False
    _lock = threading.Lock()

    def __init__(self):
        super().__init__() # 调用父类构造函数
        self.logger = logging.getLogger('news_analyzer.collectors.pengpai')
        self.logger.setLevel(logging.DEBUG) # Set logger to DEBUG

        # --- 启动时清理旧的配置文件 ---
        if not PengpaiCollector._initial_cleanup_done:
            self._cleanup_old_profiles()
            PengpaiCollector._initial_cleanup_done = True
        # --- 清理逻辑结束 ---

        self.session = requests.Session() # 使用 Session 保持连接和 cookies
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' # 使用桌面 User-Agent，Selenium 通常工作更好
        })

        # WebDriver 将在首次需要时延迟初始化
        self.driver = None
        self._webdriver_init_failed = False # 添加初始化失败标志
        self.logger.info("PengpaiCollector 初始化完成，WebDriver 将延迟加载。")

    def _cleanup_old_profiles(self):
        """清理 data/webdriver_profiles 目录下旧的配置文件"""
        profile_base_path = os.path.abspath(os.path.join('data', 'webdriver_profiles'))
        self.logger.info(f"开始清理旧的 WebDriver 配置文件目录: {profile_base_path}")
        if not os.path.exists(profile_base_path):
            self.logger.info("配置文件基目录不存在，无需清理。")
            return

        try:
            for item_name in os.listdir(profile_base_path):
                item_path = os.path.join(profile_base_path, item_name)
                # 检查是否是目录并且名称匹配模式
                if os.path.isdir(item_path) and item_name.startswith('edge_profile_'):
                    try:
                        self.logger.info(f"删除旧的配置文件目录: {item_path}")
                        shutil.rmtree(item_path)
                    except Exception as e:
                        self.logger.error(f"删除目录 {item_path} 时出错: {e}")
            self.logger.info("旧配置文件清理完成。")
        except Exception as e:
            self.logger.error(f"列出或处理配置文件目录 {profile_base_path} 时出错: {e}")

    def close(self):
        """关闭 WebDriver 并尝试强制结束驱动进程"""
        driver_closed = False
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Selenium WebDriver 已关闭 (driver.quit() 调用成功)")
                driver_closed = True
            except Exception as e:
                self.logger.error(f"关闭 WebDriver (driver.quit()) 时出错: {e}")
            finally:
                # 清理临时用户数据目录
                if hasattr(self, 'user_data_dir') and self.user_data_dir:
                    try:
                        import shutil
                        shutil.rmtree(self.user_data_dir)
                        self.logger.info(f"已删除临时用户数据目录: {self.user_data_dir}")
                    except Exception as cleanup_e:
                        self.logger.error(f"清理临时用户数据目录 {self.user_data_dir} 时出错: {cleanup_e}")
                    finally:
                        self.user_data_dir = None # 清除引用

                # --- 强制结束 msedgedriver.exe 进程 (作为后备措施) ---
                if platform.system() == "Windows":
                    try:
                        self.logger.info("尝试强制结束 msedgedriver.exe 进程...")
                        # /F 表示强制终止, /IM 指定镜像名称 (进程名)
                        # capture_output=True, text=True 可以捕获输出，方便调试
                        # check=False 避免在找不到进程时抛出异常
                        result = subprocess.run(["taskkill", "/F", "/IM", "msedgedriver.exe"], capture_output=True, text=True, check=False)
                        if result.returncode == 0:
                            self.logger.info("成功发送 taskkill 命令结束 msedgedriver.exe。")
                            self.logger.debug(f"Taskkill output: {result.stdout}")
                        elif result.returncode == 128: # 进程未找到的返回码
                             self.logger.info("未找到活动的 msedgedriver.exe 进程需要结束。")
                        else: # 其他错误
                             self.logger.warning(f"执行 taskkill 结束 msedgedriver.exe 时遇到问题。Return code: {result.returncode}, Error: {result.stderr}")
                    except FileNotFoundError:
                        self.logger.error("无法执行 taskkill 命令，请确保它在系统 PATH 中。")
                    except Exception as kill_e:
                        self.logger.error(f"尝试强制结束 msedgedriver.exe 时发生意外错误: {kill_e}")
                # --- 强制结束逻辑结束 ---

    def collect(self, source: NewsSource, progress_callback: Optional[Callable[[int, int], None]] = None, cancel_checker: Optional[Callable[[], bool]] = None) -> List[Dict[str, Any]]:
        """
        从澎湃新闻网站抓取新闻列表。
        注意：此方法依赖 WebDriver 和特定的HTML结构，可能因网站更新而失效。

        Args:
            source: 澎湃新闻源的配置对象
            progress_callback: 一个 callable 对象，用于报告进度
            cancel_checker: 一个 callable 对象，调用它返回 True 时应中断抓取。

        Returns:
            一个包含新闻信息的字典列表，每个字典应包含 'title', 'link' 等键。
            注意：这里返回的是原始字典列表，AppService 会负责将其转换为 NewsArticle 对象。
        """
        self.logger.info(f"PengpaiCollector.collect 方法开始执行，来源: {source.name}") # 更明确的入口日志
        self.logger.info(f"开始抓取澎湃新闻 (手机版): {source.name}")
        self._webdriver_init_failed = False # 重置 WebDriver 初始化失败标志
        news_items = []
        target_url = self.MOBILE_URL

        try:
            response = self.session.get(target_url, timeout=20) # 增加超时时间
            response.raise_for_status()
            # 澎湃手机版通常是 UTF-8
            response.encoding = 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')

            # --- 获取并使用 CSS 选择器配置 ---
            selectors = source.custom_config if isinstance(source.custom_config, dict) else {}
            # 提供默认值，以防配置不完整
            # 注意：这些默认选择器基于 m.thepaper.cn 在某个时间点的结构，可能会失效。
            # 推荐通过 NewsSource 配置提供准确的选择器。
            default_selectors = {
                'news_list_selector': 'a[href^="/newsDetail_forward_"]', # 查找所有匹配的链接，后续逻辑从中提取标题
                'title_selector': 'h3.index_title__aGAqD', # 列表页标题选择器 (更新)
                'link_selector': None, # 链接通常是 <a> 标签的 href
                'summary_selector': None, # 列表页通常没有摘要
                'time_selector': None, # 列表页通常没有时间
            }
            # 合并用户配置和默认值，用户配置优先
            final_selectors = {**default_selectors, **selectors} # 用户配置会覆盖默认配置中同名的键

            list_link_selector = final_selectors.get('news_list_selector')
            title_selector = final_selectors.get('title_selector') # 获取标题选择器

            if not list_link_selector:
                self.logger.error(f"澎湃新闻源 '{source.name}' 未配置 'news_list_selector'，无法抓取。")
                self.selector_failed.emit(source.name) # 发出信号
                return []

            # --- 查找新闻列表项 ---
            self.logger.info(f"尝试使用选择器 '{list_link_selector}' 查找新闻列表链接...")
            news_links = soup.select(list_link_selector)
            self.logger.info(f"使用选择器 '{list_link_selector}' 找到 {len(news_links)} 个链接元素")

            # --- 选择器失效检查 ---
            if not news_links:
                self.logger.error(f"澎湃新闻源 '{source.name}' 的新闻列表选择器 '{list_link_selector}' 失效，在 {target_url} 未找到任何匹配项。")
                self.selector_failed.emit(source.name) # 发出信号
                return [] # 返回空列表

            # 在循环前记录最终找到的链接数量
            self.logger.info(f"最终准备处理的新闻链接数量: {len(news_links)}")

            processed_links = set() # 用于简单去重

            for link_element in news_links:
                # *** 在循环开始处检查取消状态 ***
                if cancel_checker():
                    self.logger.info("抓取被用户取消 (在处理列表项时)")
                    break # 跳出循环

                try:
                    link = link_element.get('href')
                    if not link or link in processed_links:
                        continue

                    # 处理相对 URL
                    absolute_link = urljoin(self.MOBILE_URL, link)

                    # --- 使用配置的选择器提取标题 ---
                    title = ""
                    if title_selector:
                        # 在 link_element 内部查找标题元素
                        title_element = link_element.select_one(title_selector)
                        if title_element:
                            title = title_element.get_text(strip=True)
                            self.logger.debug(f"通过配置的选择器 '{title_selector}' 提取到标题: '{title[:30]}...'")

                    # 如果配置的选择器无效或未配置，回退到之前的逻辑
                    if not title:
                        # 尝试更具体的选择器组合 (之前的逻辑)
                        possible_title_tags = link_element.select('h3, h4, div.news_title, span.content_title, p.title')
                        if possible_title_tags:
                            for tag in possible_title_tags:
                                title = tag.get_text(strip=True)
                                if title:
                                    self.logger.debug(f"通过回退选择器 '{tag.name}.{tag.get('class', '')}' 提取到标题: '{title[:30]}...'")
                                    break
                        # 如果还是找不到，尝试获取 <a> 标签本身的直接文本
                        if not title:
                            direct_text = ''.join(link_element.find_all(string=True, recursive=False)).strip()
                            if direct_text and len(direct_text) > 5:
                                title = direct_text
                                self.logger.debug(f"通过 <a> 直接文本提取到标题: '{title[:30]}...'")
                            else: # 最后尝试获取所有文本
                                title = link_element.get_text(strip=True)
                                self.logger.debug(f"通过 <a> get_text() 提取到标题: '{title[:30]}...'")


                    # 清理和验证标题
                    title = title.strip()
                    self.logger.info(f"处理链接: {absolute_link}, 提取到初步标题: '{title}'") # 添加日志

                    # 检查标题是否有效（例如，不是纯数字、时间戳或过短）
                    is_invalid_title = (not title or len(title) < 5 or title.isdigit() or
                                        re.match(r'^\d{2}:\d{2}(\.\.\.)?$', title) or
                                        "广告" in title or "推广" in title or "视频" in title)

                    if is_invalid_title:
                        self.logger.warning(f"标题 '{title}' 被判断为无效，跳过链接 {absolute_link}") # 添加日志
                        continue
                    else:
                         self.logger.info(f"标题 '{title}' 有效，准备获取详情。") # 添加日志
                    # --- 标题提取结束 ---

                    processed_links.add(link) # 添加到已处理集合

                    # 获取详情页信息，传递选择器配置
                    self.logger.info(f"准备为链接调用 _fetch_detail: {absolute_link}")
                    detail_data = self._fetch_detail(absolute_link, source.custom_config if isinstance(source.custom_config, dict) else {}, source.name)
                    self.logger.info(f"_fetch_detail 调用返回，内容长度: {len(detail_data.get('content', '')) if detail_data.get('content') else 'None'}") # 添加调用后日志

                    # 如果获取详情失败（例如内容为空或出错），则跳过此条新闻
                    if not detail_data.get('content') or "失败" in detail_data.get('content', "") or "无效" in detail_data.get('content', ""):
                         self.logger.warning(f"获取详情页 {absolute_link} 失败或内容无效，将终止抓取澎湃新闻源 '{source.name}' 的本次剩余文章。错误信息: {detail_data.get('content')}")
                         break # 修改：不再继续尝试该源的其他文章

                    news_item = {
                        'title': title,
                        'link': absolute_link,
                        'summary': None, # 摘要可以考虑从正文生成，或在详情页提取
                        'pub_date': detail_data.get('pub_date'), # 使用详情页获取的日期
                        'content': detail_data.get('content'), # 使用详情页获取的内容
                        'author': detail_data.get('author'), # MODIFIED: Ensure author is included from detail_data
                        'source_name': source.name, # MODIFIED: Add source_name
                        'category': source.category if hasattr(source, 'category') and source.category else "news" # MODIFIED: Add category, default to news
                    }
                    news_items.append(news_item)
                    self.logger.debug(f"提取到新闻: Title='{title[:30]}...', Link='{absolute_link}', Date='{news_item['pub_date']}', Content Length={len(news_item['content']) if news_item['content'] else 0}")

                    # 添加延时，避免请求过快
                    time.sleep(0.5) # 休眠 0.5 秒

                except Exception as item_e:
                    self.logger.error(f"处理单个新闻链接时出错: {item_e}", exc_info=False)

        except requests.exceptions.RequestException as req_e:
            self.logger.error(f"请求澎湃新闻 URL {target_url} 失败: {req_e}")
        except Exception as e:
            self.logger.error(f"抓取澎湃新闻时发生未知错误: {e}", exc_info=True)

        self.logger.info(f"澎湃新闻抓取完成，初步获取 {len(news_items)} 条")
        self.logger.info(f"DEBUG - PengpaiCollector: collect 方法完成，最终返回 {len(news_items)} 条新闻。前 3 条: {news_items[:3]}") # DEBUG LOG
        return news_items

    def _fetch_detail(self, url: str, selector_config: Dict, source_name: str) -> Dict:
        """
        使用 Selenium 获取并解析新闻详情页，提取发布日期、正文等。
        使用用户提供的 CSS 选择器配置。

        Args:
            url: 新闻详情页的 URL。
            selector_config: 包含 CSS 选择器的字典。
            source_name: 新闻源名称，用于日志和信号。

        Returns:
            包含 'pub_date', 'content', 'author' 等的字典，如果提取失败则值为 None 或错误信息。
        """
        overall_start_time = time.perf_counter() # TIMING START
        self.logger.info(f"进入 _fetch_detail 方法，URL: {url}") # 在方法入口添加日志
        detail_data = {'pub_date': None, 'content': None, 'author': None}

        # --- 检查 WebDriver 初始化是否已失败 ---
        # --- 检查 WebDriver 初始化是否已失败 (暂时注释掉，强制每次尝试初始化以获取错误日志) ---
        # if self._webdriver_init_failed:
        #     self.logger.error("_webdriver_init_failed 标志为 True，跳过详情页获取。")
        #     detail_data['content'] = "WebDriver 初始化失败，无法获取详情。"
        #     return detail_data
        self.logger.debug("_webdriver_init_failed 标志为 False，继续执行。") # 添加日志

        # --- 检查 WebDriver 初始化是否已失败 ---
        if self._webdriver_init_failed:
            self.logger.error("WebDriver 初始化已失败，跳过详情页获取。")
            detail_data['content'] = "WebDriver 初始化失败，无法获取详情。"
            return detail_data

        # --- 延迟初始化 WebDriver ---
        if self.driver is None:
            self.logger.info("WebDriver 实例为 None，开始初始化...") # 简化日志
            
            # 检查Edge浏览器是否安装
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Edge") as key:
                    self.logger.info("检测到Microsoft Edge已安装")
            except Exception as edge_e:
                self.logger.warning(f"无法确认Microsoft Edge是否已安装: {edge_e}")
                self.logger.warning("如果Edge未安装，WebDriver将无法正常工作")
            try:
                # --- 使用应用数据目录下的唯一路径 ---
                profile_base_path = os.path.abspath(os.path.join('data', 'webdriver_profiles'))
                profile_dir_name = f"edge_profile_{uuid.uuid4()}"
                self.user_data_dir = os.path.join(profile_base_path, profile_dir_name)
                try:
                    os.makedirs(self.user_data_dir, exist_ok=True)
                    self.logger.info(f"为 WebDriver 创建用户数据目录: {self.user_data_dir}")
                except OSError as e:
                     self.logger.error(f"创建 WebDriver 用户数据目录失败: {e}", exc_info=True)
                     # 如果创建目录失败，则无法继续，直接返回错误
                     detail_data['content'] = f"创建 WebDriver 配置目录失败: {e}"
                     self._webdriver_init_failed = True # 标记初始化失败
                     return detail_data
                # --- 路径创建结束 ---

                options = webdriver.EdgeOptions()
                # 恢复 WebDriver 选项
                options.add_argument('--headless')
                options.add_argument('--disable-gpu')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--ignore-certificate-errors')
                options.add_argument('--allow-running-insecure-content')
                # 添加唯一的 user-data-dir 参数
                options.add_argument(f"--user-data-dir={self.user_data_dir}")
                # 添加额外参数尝试解决 session not created 问题 (这些可以保留，有助于稳定性)
                options.add_argument('--disable-extensions')
                options.add_argument('--remote-debugging-port=0')
                options.add_argument('--disable-background-networking')

                # 首先尝试使用项目内置的drivers目录中的msedgedriver.exe
                project_driver_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'drivers', 'msedgedriver.exe'))
                self.logger.info(f"尝试使用项目内置的EdgeDriver路径: {project_driver_path}")
                
                # 然后尝试从配置文件获取
                from PySide6.QtCore import QSettings
                settings = QSettings("NewsAnalyzer", "NewsAggregator")
                settings_driver_path = settings.value("msedgedriver_path", "")
                
                service = None
                # 优先使用项目内置驱动
                if os.path.exists(project_driver_path):
                    self.logger.info(f"使用项目内置的EdgeDriver: {project_driver_path}")
                    service = webdriver.EdgeService(executable_path=project_driver_path)
                # 其次使用配置文件中的路径
                elif settings_driver_path and os.path.exists(settings_driver_path):
                    self.logger.info(f"使用配置文件中指定的EdgeDriver路径: {settings_driver_path}")
                    service = webdriver.EdgeService(executable_path=settings_driver_path)
                # 最后尝试使用系统PATH
                else:
                    if settings_driver_path:
                        self.logger.warning(f"配置文件中指定的EdgeDriver路径无效或文件不存在: {settings_driver_path}")
                    
                    self.logger.info("未找到有效的EdgeDriver路径，将尝试使用系统PATH中的msedgedriver.exe")
                    self.logger.warning("请确保Microsoft Edge浏览器已安装，且msedgedriver.exe在系统PATH中或项目的drivers目录中")
                self.driver = webdriver.Edge(service=service, options=options)
                self.logger.info(f"webdriver.Edge(...) 执行完毕，WebDriver 实例: {'成功创建' if self.driver else '创建失败'}") # 添加初始化后日志
            except Exception as e:
                # 使用 CRITICAL 级别记录致命错误，并包含堆栈跟踪
                self.logger.critical(f"WebDriver 初始化过程中发生致命异常: {e}", exc_info=True)
                
                # 提供更详细的错误信息和解决方案
                error_details = str(e).lower()
                if "session not created" in error_details:
                    error_msg = (f"Edge WebDriver 版本与浏览器不匹配: {e}\n"
                                f"解决方案: 请确保msedgedriver.exe版本与您的Edge浏览器版本匹配。\n"
                                f"1. 检查Edge浏览器版本: 打开Edge，点击右上角'...'→'帮助和反馈'→'关于Microsoft Edge'\n"
                                f"2. 下载对应版本的msedgedriver.exe: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/\n"
                                f"3. 将下载的msedgedriver.exe替换到项目的drivers目录中")
                elif "chromedriver" in error_details or "chrome not found" in error_details:
                    error_msg = (f"Edge浏览器未找到: {e}\n"
                                f"解决方案: 请确保已安装Microsoft Edge浏览器")
                elif "executable needs to be in path" in error_details:
                    error_msg = (f"找不到msedgedriver.exe: {e}\n"
                                f"解决方案: 请确保msedgedriver.exe在以下位置之一:\n"
                                f"1. 项目的drivers目录中 (推荐)\n"
                                f"2. 系统环境变量PATH中\n"
                                f"3. 在软件设置中指定路径")
                else:
                    error_msg = (f"Edge WebDriver 初始化失败: {e}\n"
                                f"请确保已正确安装 Microsoft Edge 浏览器和对应版本的 EdgeDriver (msedgedriver.exe)，\n"
                                f"并将其路径添加到系统 PATH 或在设置中指定路径，或放置在项目的drivers目录中。")
                
                detail_data['content'] = error_msg # 将错误信息放入 content
                self.driver = None # 确保 driver 为 None
                self._webdriver_init_failed = True # 设置失败标志
                self.logger.critical("WebDriver 初始化失败，设置 _webdriver_init_failed = True。后续详情获取将被跳过。") # 明确说明后果
                return detail_data # 返回包含错误信息的字典
            self.logger.info("WebDriver 初始化代码块执行完毕。")
        else:
             self.logger.info("WebDriver 实例已存在，跳过初始化。") # 添加日志

        if not self.driver:
             self.logger.error("WebDriver 实例无效，无法获取详情页。")
             detail_data['content'] = "WebDriver 实例无效"
             return detail_data

        try:
            self.logger.info(f"尝试使用 WebDriver 获取详情页: {url}") # 提升日志级别
            if not self.driver:
                 self.logger.error("WebDriver 实例无效，无法继续。")
                 detail_data['content'] = "WebDriver 实例无效"
                 return detail_data

            self.logger.debug(f"WebDriver 状态: {self.driver.session_id if self.driver else 'None'}") # 记录 WebDriver 状态
            
            get_url_start_time = time.perf_counter() # TIMING
            self.driver.get(url)
            get_url_duration = time.perf_counter() - get_url_start_time # TIMING
            self.logger.debug(f"TIMING: driver.get(url) took {get_url_duration:.4f} seconds.") # TIMING - CHANGED TO DEBUG

            self.logger.info(f"WebDriver 已请求 URL: {url}") # 提升日志级别
            # --- 添加日志：记录页面源代码 ---
            # 等待页面某个基础元素加载完成
            wait_body_start_time = time.perf_counter() # TIMING
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            wait_body_duration = time.perf_counter() - wait_body_start_time # TIMING
            self.logger.debug(f"TIMING: WebDriverWait for body took {wait_body_duration:.4f} seconds.") # TIMING - CHANGED TO DEBUG

            self.logger.info(f"详情页 {url}: Body 元素已加载") # 提升日志级别

            # --- 添加日志：记录页面源代码 ---
            try:
                page_source_for_log = self.driver.page_source
                self.logger.debug(f"详情页 {url}: 页面源代码 (前 500 字符):\n{page_source_for_log[:500]}")
                # 可以考虑将完整源码写入临时文件进行调试
                # with open(f'page_source_{time.time()}.html', 'w', encoding='utf-8') as f:
                #     f.write(page_source_for_log)
            except Exception as ps_e:
                self.logger.warning(f'获取页面源代码时出错: {ps_e}')
            # --- 日志结束 ---

            # --- 使用传入的选择器配置 ---
            # !!! 重要: 下面的默认选择器很可能已过时，需要根据当前 m.thepaper.cn 网站结构进行更新 !!!
            # !!! 请使用浏览器开发者工具检查实际新闻详情页的 HTML 结构来获取正确的选择器 !!!
            # REMOVE THE HARDCODED default_detail_selectors HERE
            # default_detail_selectors = {
            #     'time_selector': 'div.newsbox_header_date', 
            #     'author_selector': 'span.name_text', 
            #     'content_selector': 'div.newsbox_body' 
            # }
            # final_detail_selectors = {**default_detail_selectors, **selector_config} # This line will also be affected

            # --- Corrected logic for content_selector ---
            content_selector_list = []
            if isinstance(selector_config, dict) and selector_config.get("content_selector"):
                custom_cs = selector_config["content_selector"]
                if isinstance(custom_cs, str) and custom_cs.strip():
                    content_selector_list.append(custom_cs)
                elif isinstance(custom_cs, list):
                    content_selector_list.extend([s for s in custom_cs if isinstance(s, str) and s.strip()])

            default_cs_from_config = DEFAULT_PENGPAI_CONFIG.get("content_selector")
            if default_cs_from_config:
                if isinstance(default_cs_from_config, str):
                    default_cs_list = [s.strip() for s in default_cs_from_config.split(',') if s.strip()]
                elif isinstance(default_cs_from_config, list): # Should not happen based on current DEFAULT_PENGPAI_CONFIG
                    default_cs_list = [s for s in default_cs_from_config if isinstance(s, str) and s.strip()]
                else:
                    default_cs_list = []
                
                for ds in default_cs_list:
                    if ds not in content_selector_list: # Avoid duplicates
                        content_selector_list.append(ds)
            
            if not content_selector_list:
                self.logger.error(f"澎湃新闻源 '{source_name}' 未配置 'content_selector' 且 DEFAULT_PENGPAI_CONFIG 中也无有效值。")
                # self.selector_failed.emit(source_name) # Emitting later if all attempts fail
                detail_data['content'] = "错误：内容选择器完全缺失"
                # Fallback to body if absolutely nothing is defined, though this is unlikely to be useful.
                content_selector_str_for_iteration = ['body'] 
            else:
                content_selector_str_for_iteration = content_selector_list

            # Use content_selector_str_for_iteration in the loop below instead of content_selector_str
            # --- 检查关键选择器是否存在 (using the new list) ---
            # content_selector_str = final_detail_selectors.get('content_selector') # Old logic
            # if not content_selector_str: # Old logic
            #    self.logger.error(f"澎湃新闻源 '{source_name}' 未配置详情页 'content_selector'，无法提取正文。")
            #    self.selector_failed.emit(source_name) 
            #    detail_data['content'] = "错误：未配置内容选择器"
            
            self.logger.debug(f"PENGPAI_SELECTOR_DEBUG: Source custom_config for {source_name} ({url}): {selector_config}")
            self.logger.debug(f"PENGPAI_SELECTOR_DEBUG: Compiled content_selectors for {url}: {content_selector_str_for_iteration}")


            # --- 尝试提取各个字段 ---
            content_html = None

            # 1. 优先提取 Content HTML
            content_extraction_start_time = time.perf_counter() # TIMING
            # if content_selector_str: # Old logic
            #    possible_content_selectors = [s.strip() for s in content_selector_str.split(',') if s.strip()] # Old logic
            
            if content_selector_str_for_iteration and not detail_data['content'] == "错误：内容选择器完全缺失": # Check if we have selectors to try
                for i, current_cs_selector in enumerate(content_selector_str_for_iteration): # Use the new list
                    self.logger.info(f"尝试使用内容选择器 #{i+1}/{len(content_selector_str_for_iteration)}: '{current_cs_selector}' 定位内容容器 (URL: {url})...")
                    try:
                        # 使用更长的等待时间，因为内容可能是动态加载的
                        content_wait_start = time.perf_counter()
                        content_container = WebDriverWait(self.driver, 7).until( # Reduced wait time for iterative attempts
                            EC.visibility_of_element_located((By.CSS_SELECTOR, current_cs_selector))
                        )
                        self.logger.debug(f"TIMING: WebDriverWait for content selector '{current_cs_selector}' took {time.perf_counter() - content_wait_start:.4f} s.") # TIMING - CHANGED TO DEBUG
                        
                        self.logger.info(f"SUCCESS: Content selector '{current_cs_selector}' succeeded for URL {url}.") # LOG SUCCESS
                        self.logger.info(f"成功定位到内容容器使用选择器 '{current_cs_selector}'")
                        
                        # 清理广告等 (保留之前的逻辑)
                        remove_ads_start_time = time.perf_counter() # TIMING
                        selectors_to_remove = [
                            '.ad', '.ad-container', '.video-container', '.recommend', '.related-reads', 'script',
                            'style', '.content_open_app', '.go_app', '.news_open_app_fixed', '.toutiao', '.sponsor',
                            '.adsbygoogle', '[id*="ad"]', '[class*="video"]' 
                            # Consider adding more specific selectors if needed, e.g., '.bottom-banner-wrapper'
                        ]
                        for sel_remove in selectors_to_remove:
                            try:
                                script = f"arguments[0].querySelectorAll('{sel_remove}').forEach(el => el.parentNode.removeChild(el));"
                                self.driver.execute_script(script, content_container)
                            except Exception as e_remove:
                                self.logger.debug(f"移除元素 '{sel_remove}' 时出错 (可能元素不存在): {e_remove}")
                        self.logger.debug(f"TIMING: Removing ads took {time.perf_counter() - remove_ads_start_time:.4f} seconds.") # TIMING - CHANGED TO DEBUG

                        get_html_start_time = time.perf_counter() # TIMING
                        content_html = content_container.get_attribute('innerHTML').strip()
                        self.logger.debug(f"TIMING: content_container.get_attribute('innerHTML') took {time.perf_counter() - get_html_start_time:.4f} seconds.") # TIMING - CHANGED TO DEBUG

                        self.logger.info(f"详情页 {url}: 获取到原始 innerHTML 使用选择器 '{current_cs_selector}' (前100字符): {content_html[:100]}")
                        detail_data['content'] = content_html # 存储成功提取的内容
                        break # 成功提取，跳出循环
                    except (TimeoutException, NoSuchElementException):
                        self.logger.warning(f"内容选择器 '{current_cs_selector}' 尝试失败 (URL: {url})。")
                        if i == len(content_selector_str_for_iteration) - 1: # 如果是最后一个选择器且失败
                            self.logger.error(f"FAILURE: All content selectors {content_selector_str_for_iteration} failed for URL {url}.") # LOG FAILURE
                            self.logger.error(f"澎湃新闻源 '{source_name}' 的所有内容选择器均失效，在 {url} 未找到匹配项。")
                            self.selector_failed.emit(source_name)
                            detail_data['content'] = f"错误：所有内容选择器均失效" 
                            # 不在此处返回，继续尝试提取其他字段
            elif not detail_data['content'] == "错误：内容选择器完全缺失": # Only log if not already marked as completely missing
                self.logger.error(f"澎湃新闻源 '{source_name}' 最终无有效内容选择器可供尝试。")
                detail_data['content'] = "错误：无有效内容选择器" # 标记错误，但仍继续
            
            content_extraction_duration = time.perf_counter() - content_extraction_start_time # TIMING
            self.logger.debug(f"TIMING: Content extraction section took {content_extraction_duration:.4f} seconds.") # TIMING - CHANGED TO DEBUG

            # 如果最终内容提取失败，记录一下
            if not detail_data.get('content') or "错误：" in str(detail_data.get('content')) :
                 self.logger.warning(f"最终未能为URL {url} 提取到有效的新闻正文内容。收集到的错误/内容: {detail_data.get('content')}")


            # 2. 提取其他字段 (Date, Author) - Title 通常从列表页获取
            other_fields_start_time = time.perf_counter() # TIMING
            # MODIFIED: Changed 'date' to 'pub_date' to match detail_data key
            field_mapping = {
                'pub_date': {'custom': selector_config.get('time_selector', ''), 'default': DEFAULT_PENGPAI_CONFIG.get('date_selector', '')},
                'author': {'custom': selector_config.get('author_selector', ''), 'default': DEFAULT_PENGPAI_CONFIG.get('author_selector', '')},
            }

            for field_key, selector_sources in field_mapping.items(): # field_key is 'pub_date' or 'author'
                 custom_selectors_str = selector_sources['custom']
                 default_selectors_str = selector_sources['default']

                 combined_selectors_list = []
                 if custom_selectors_str:
                     combined_selectors_list.extend(s.strip() for s in custom_selectors_str.split(',') if s.strip())
                 if default_selectors_str:
                     combined_selectors_list.extend(s.strip() for s in default_selectors_str.split(',') if s.strip())
                
                 # Remove duplicates while preserving order (Python 3.7+)
                 unique_selectors = list(dict.fromkeys(combined_selectors_list))

                 if not unique_selectors:
                     self.logger.debug(f"详情页 {url}: 未配置或找到任何有效的 \'{field_key}\' 选择器 (自定义或默认)，跳过提取。")
                     detail_data[field_key] = None # 确保字段在 detail_data 中存在，即使为 None
                     continue

                 extracted_field_value = None
                 self.logger.info(f"详情页 {url}: 提取字段 '{field_key}'，尝试组合/去重后的选择器列表: {unique_selectors}")

                 for i, current_field_sel in enumerate(unique_selectors):
                    self.logger.info(f"详情页 {url}: 提取字段 \'{field_key}\'，尝试选择器 #{i+1}/{len(unique_selectors)}: \'{current_field_sel}\'")
                    try:
                        element = WebDriverWait(self.driver, 1).until( # MODIFIED: Shorter timeout for these fields (was 3)
                            EC.visibility_of_element_located((By.CSS_SELECTOR, current_field_sel))
                        )
                        
                        field_text = element.text.strip()
                        if not field_text:
                            self.logger.warning(f"选择器 '{current_field_sel}' for '{field_key}' 找到元素但文本为空。")
                            continue # 尝试下一个选择器

                        if field_key == 'pub_date':
                            parsed_date = self._parse_relative_or_absolute_time(field_text)
                            detail_data[field_key] = field_text # Assign raw text
                            if parsed_date:
                                self.logger.info(f"SUCCESS: Field '{field_key}' selector '{current_field_sel}' succeeded. Parsed: {parsed_date}, Raw: '{field_text}'. URL: {url}") # LOG SUCCESS
                                self.logger.info(f"成功解析发布时间: {parsed_date} (来自文本 '{field_text}' 使用选择器 '{current_field_sel}')")
                            else:
                                self.logger.warning(f"Field '{field_key}' selector '{current_field_sel}' got text '{field_text}' but parsing failed. URL: {url}")
                        elif field_key == 'author':
                            extracted_field_value = field_text
                            self.logger.info(f"SUCCESS: Field '{field_key}' selector '{current_field_sel}' succeeded. Value: '{extracted_field_value}'. URL: {url}") # LOG SUCCESS
                            self.logger.info(f"成功提取作者: {extracted_field_value} (使用选择器 '{current_field_sel}')")
                        
                        if extracted_field_value is not None:
                            detail_data[field_key] = extracted_field_value
                            break # Found and processed, exit selector loop
                        
                    except (TimeoutException, NoSuchElementException):
                        self.logger.warning(f"详情页 {url}: 查找元素失败，选择器: '{current_field_sel}' for field '{field_key}'")
                        if i == len(unique_selectors) - 1: # If it's the last selector and it failed
                            self.logger.error(f"FAILURE: All selectors for field '{field_key}' ({unique_selectors}) failed for URL {url}.") # LOG FAILURE
                            detail_data[field_key] = None # Set to None as all attempts failed
                            self.logger.error(f"字段 '{field_key}' 的所有选择器 '{selector_sources['custom']}' 均失效 (URL: {url})。")
                            if field_key == 'pub_date' or field_key == 'author': # Emit signal if all time or author selectors fail
                                self.selector_failed.emit(source_name) 
                 
                 # Ensure field is in detail_data even if all selectors failed or it wasn't configured
                 if field_key not in detail_data:
                      detail_data[field_key] = None

            other_fields_duration = time.perf_counter() - other_fields_start_time # TIMING
            self.logger.debug(f"TIMING: Other fields (date/author) extraction took {other_fields_duration:.4f} seconds.") # TIMING - CHANGED TO DEBUG

            # --- 日志记录最终提取到的数据 ---
            self.logger.info(f"_fetch_detail 结果 for {url}: Date='{detail_data.get('pub_date')}', Author='{detail_data.get('author')}', Content Length={len(detail_data.get('content', '')) if detail_data.get('content') else 'None or Error'}")

        except JavascriptException as js_e: # Catch JavaScript errors during page interaction
            self.logger.error(f"详情页 {url}: 执行 JavaScript 时出错 (可能在移除元素或获取属性时): {js_e}", exc_info=True)
            # 根据错误严重性，可能需要设置 content 为错误信息
            if not detail_data.get('content'): # 如果还没有内容，则记录此错误
                 detail_data['content'] = f"错误：页面JavaScript执行失败 - {js_e}"

        except Exception as e_main_fetch:
            self.logger.error(f"详情页 {url}: 获取详细信息时发生主错误: {e_main_fetch}", exc_info=True)
            # 确保即使发生意外错误，也会尝试返回一些信息，特别是内容（如果已提取）
            if not detail_data.get('content'): # 如果还没有内容，则记录此错误
                detail_data['content'] = f"错误：提取详情时发生未知错误 - {e_main_fetch}"
        
        # Ensure essential keys exist in the returned dict, even if None
        for key in ['pub_date', 'content', 'author']:
            if key not in detail_data:
                detail_data[key] = None

        # Ensure pub_date is a string if it was parsed to datetime, for AppService compatibility
        if isinstance(detail_data.get('pub_date'), datetime):
            self.logger.debug(f"Converting pub_date from datetime back to string for AppService: {detail_data['pub_date']}")
            try:
                detail_data['pub_date'] = detail_data['pub_date'].strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e_conv:
                self.logger.error(f"Error converting pub_date datetime to string: {e_conv}. Leaving as datetime.")

        overall_duration = time.perf_counter() - overall_start_time # TIMING
        self.logger.debug(f"TIMING: _fetch_detail for {url} took {overall_duration:.4f} seconds overall.") # TIMING - CHANGED TO DEBUG
        self.logger.info(f"DEBUG - PengpaiCollector: _fetch_detail 方法返回: {detail_data}") # DEBUG LOG
        return detail_data

    def _parse_relative_or_absolute_time(self, time_str: str) -> Optional[datetime]:
        """尝试解析相对时间（如"X小时前"）或绝对时间字符串。"""
        if not time_str:
            return None

        time_str = time_str.strip()

        # 尝试解析 "YYYY-MM-DD HH:MM" 格式 (例如 "2025-05-18 22:59")
        try:
            return datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        except ValueError:
            self.logger.debug(f"无法将 '{time_str}' 解析为 YYYY-MM-DD HH:MM 格式。")

        # 尝试解析 "YYYY-MM-DD HH:MM:SS" 格式
        try:
            return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            self.logger.debug(f"无法将 '{time_str}' 解析为 YYYY-MM-DD HH:MM:SS 格式。")
        
        # 尝试解析 "MM-DD HH:MM" 格式, 并添加当年年份
        try:
            dt_obj = datetime.strptime(time_str, '%m-%d %H:%M')
            current_year = datetime.now().year
            return dt_obj.replace(year=current_year)
        except ValueError:
            self.logger.debug(f"无法将 '{time_str}' 解析为 MM-DD HH:MM 格式。")

        # --- 保留您现有的其他相对时间解析逻辑 ---
        # 例如: "X小时前", "X分钟前", "昨天 HH:MM" 等
        # (以下是示例，请根据您的实际代码调整或保留)
        
        # 示例：处理 "X小时前"
        match_hour = re.match(r'(\d+)\s*小时前', time_str)
        if match_hour:
            hours_ago = int(match_hour.group(1))
            return datetime.now() - timedelta(hours=hours_ago)

        # 示例：处理 "X分钟前"
        match_minute = re.match(r'(\d+)\s*分钟前', time_str)
        if match_minute:
            minutes_ago = int(match_minute.group(1))
            return datetime.now() - timedelta(minutes=minutes_ago)
        
        # 示例：处理 "昨天 HH:MM"
        match_yesterday = re.match(r'昨天\s*(\d{1,2}):(\d{1,2})', time_str)
        if match_yesterday:
            hour = int(match_yesterday.group(1))
            minute = int(match_yesterday.group(2))
            yesterday_dt = datetime.now() - timedelta(days=1)
            return yesterday_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # 如果所有格式都解析失败
        self.logger.warning(f"无法识别的时间字符串格式: '{time_str}'")
        return None

    def _init_webdriver(self):
        self.logger.debug("PengpaiCollector._init_webdriver called.") # ADDED DEBUG LOG
        if self.driver or self._webdriver_init_failed: # 如果已初始化或上次失败，则不再尝试
            if self._webdriver_init_failed:
                self.logger.warning("WebDriver 初始化先前已失败，本次跳过。")
            else:
                self.logger.info("WebDriver 实例已存在，跳过初始化。")
            return

        self.logger.info("开始初始化 Selenium WebDriver (Edge)...")
        try:
            edge_options = webdriver.EdgeOptions()
            edge_options.add_argument("--headless")
            edge_options.add_argument("--disable-gpu")
            edge_options.add_argument("--no-sandbox") # 在某些环境下需要
            edge_options.add_argument("--disable-dev-shm-usage") # 克服 Docker/CI 环境中的限制
            edge_options.add_argument('--ignore-certificate-errors') # 忽略证书错误
            edge_options.add_argument('--allow-running-insecure-content') # 允许不安全内容
            edge_options.add_argument('--ignore-ssl-errors=true') # Added
            edge_options.add_argument('--enable-unsafe-swiftshader') # Added for WebGL warning
            edge_options.add_argument("--disable-blink-features=AutomationControlled") # 尝试减少被检测为机器人的几率
            edge_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            edge_options.add_experimental_option('useAutomationExtension', False)

            # SPEED OPTIMIZATIONS START
            edge_options.page_load_strategy = 'eager'
            edge_options.add_experimental_option("prefs", {
                "profile.managed_default_content_settings.images": 2, # 禁止加载图片
            })
            # SPEED OPTIMIZATIONS END

            # SSL and Insecure Content Handling
            edge_options.add_argument('--ignore-certificate-errors')
            edge_options.add_argument('--allow-running-insecure-content')
            edge_options.add_argument('--ignore-ssl-errors=true') # Added
            edge_options.add_argument('--enable-unsafe-swiftshader') # Added for WebGL warning

            # Unique profile for each instance to avoid conflicts
            # ... existing code ...
        except Exception as e:
            self.logger.error(f"初始化 WebDriver 时发生错误: {e}", exc_info=True)
            self._webdriver_init_failed = True # 设置失败标志
