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
# 移除了 tempfile, uuid, shutil, base64, BytesIO, PIL.Image

import json # 导入 json 模块
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, JavascriptException # 导入 JavascriptException
import time
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from urllib.parse import urljoin
from PyQt5.QtCore import QObject, pyqtSignal # 导入 QObject 和 pyqtSignal

from src.models import NewsSource

class PengpaiCollector(QObject): # 继承 QObject 以使用信号
    """
    负责从澎湃新闻网站抓取新闻的收集器。
    """
    # 定义选择器失效信号，传递源名称
    selector_failed = pyqtSignal(str)
    # 澎湃新闻手机版首页 URL
    MOBILE_URL = "https://m.thepaper.cn"

    def __init__(self):
        super().__init__() # 调用父类构造函数
        self.logger = logging.getLogger('news_analyzer.collectors.pengpai')
        self.session = requests.Session() # 使用 Session 保持连接和 cookies
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' # 使用桌面 User-Agent，Selenium 通常工作更好
        })

        # WebDriver 将在首次需要时延迟初始化
        self.driver = None
        self._webdriver_init_failed = False # 添加初始化失败标志
        self.logger.info("PengpaiCollector 初始化完成，WebDriver 将延迟加载。")

    def close(self):
        """关闭 WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Selenium WebDriver 已关闭")
            except Exception as e:
                self.logger.error(f"关闭 WebDriver 时出错: {e}")
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

    def collect(self, source_config: NewsSource, cancel_checker: callable = lambda: False) -> List[Dict]:
        """
        执行澎湃新闻手机版的抓取。

        Args:
            source_config: 澎湃新闻源的配置对象
            cancel_checker: 一个 callable 对象，调用它返回 True 时应中断抓取。

        Returns:
            一个包含新闻信息的字典列表，每个字典应包含 'title', 'link' 等键。
            注意：这里返回的是原始字典列表，AppService 会负责将其转换为 NewsArticle 对象。
        """
        self.logger.info(f"PengpaiCollector.collect 方法开始执行，来源: {source_config.name}") # 更明确的入口日志
        self.logger.info(f"开始抓取澎湃新闻 (手机版): {source_config.name}")
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
            selectors = source_config.selector_config or {}
            # 提供默认值，以防配置不完整
            default_selectors = {
                'news_list_selector': 'div.index_wrapper__9rz3z a[href*="/newsDetail_forward_"]',
                'title_selector': 'h3, h4, div.news_title, span.content_title, p.title', # 列表页标题选择器可能不同
                'link_selector': None, # 链接通常是 <a> 标签的 href
                'summary_selector': None, # 列表页通常没有摘要
                'time_selector': None, # 列表页通常没有时间
            }
            # 合并用户配置和默认值，用户配置优先
            final_selectors = {**default_selectors, **selectors}

            list_link_selector = final_selectors.get('news_list_selector')
            title_selector = final_selectors.get('title_selector') # 获取标题选择器

            if not list_link_selector:
                self.logger.error(f"澎湃新闻源 '{source_config.name}' 未配置 'news_list_selector'，无法抓取。")
                self.selector_failed.emit(source_config.name) # 发出信号
                return []

            # --- 查找新闻列表项 ---
            self.logger.info(f"尝试使用选择器 '{list_link_selector}' 查找新闻列表链接...")
            news_links = soup.select(list_link_selector)
            self.logger.info(f"使用选择器 '{list_link_selector}' 找到 {len(news_links)} 个链接元素")

            # --- 选择器失效检查 ---
            if not news_links:
                self.logger.error(f"澎湃新闻源 '{source_config.name}' 的新闻列表选择器 '{list_link_selector}' 失效，在 {target_url} 未找到任何匹配项。")
                self.selector_failed.emit(source_config.name) # 发出信号
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
                    detail_data = self._fetch_detail(absolute_link, source_config.selector_config or {}, source_config.name)
                    self.logger.info(f"_fetch_detail 调用返回，内容长度: {len(detail_data.get('content', '')) if detail_data.get('content') else 'None'}") # 添加调用后日志

                    # 如果获取详情失败（例如内容为空或出错），则跳过此条新闻
                    if not detail_data.get('content') or "失败" in detail_data.get('content', "") or "无效" in detail_data.get('content', ""):
                         self.logger.warning(f"获取详情页 {absolute_link} 失败或内容无效，跳过此新闻。错误信息: {detail_data.get('content')}")
                         continue

                    news_item = {
                        'title': title,
                        'link': absolute_link,
                        'summary': None, # 摘要可以考虑从正文生成，或在详情页提取
                        'pub_date': detail_data.get('pub_date'), # 使用详情页获取的日期
                        'content': detail_data.get('content') # 使用详情页获取的内容
                        # 'author': detail_data.get('author') # 可以考虑添加作者
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
        # --- 延迟初始化 WebDriver ---
        # --- 延迟初始化 WebDriver ---
        if self.driver is None:
            self.logger.info("WebDriver 实例为 None，进入初始化代码块...") # 添加日志
            self.logger.info("WebDriver 实例为 None，尝试进行初始化...") # 更明确的日志
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
                options.add_argument('--headless')
                options.add_argument('--disable-gpu')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                # 添加唯一的 user-data-dir 参数
                options.add_argument(f"--user-data-dir={self.user_data_dir}")
                # 添加额外参数尝试解决 session not created 问题
                options.add_argument('--disable-extensions')
                options.add_argument('--remote-debugging-port=0')
                options.add_argument('--disable-background-networking')

                from PyQt5.QtCore import QSettings
                settings = QSettings("NewsAnalyzer", "NewsAggregator")
                edgedriver_path = settings.value("msedgedriver_path", "")
                service = None
                if edgedriver_path and os.path.exists(edgedriver_path):
                    self.logger.info(f"使用配置文件中指定的 EdgeDriver 路径: {edgedriver_path}")
                    service = webdriver.EdgeService(executable_path=edgedriver_path)
                else:
                    if edgedriver_path:
                         self.logger.warning(f"配置文件中指定的 EdgeDriver 路径无效或文件不存在: {edgedriver_path}")
                    else:
                        self.logger.info("配置文件中未指定有效路径，将尝试使用系统 PATH 中的 EdgeDriver (msedgedriver.exe)") # 修改日志
                self.driver = webdriver.Edge(service=service, options=options)
                self.logger.info(f"webdriver.Edge(...) 执行完毕，WebDriver 实例: {'成功创建' if self.driver else '创建失败'}") # 添加初始化后日志
            except Exception as e:
                # 使用 CRITICAL 级别记录致命错误，并包含堆栈跟踪
                self.logger.critical(f"WebDriver 初始化过程中发生致命异常: {e}", exc_info=True)
                error_msg = f"Edge WebDriver 初始化失败: {e}\n请确保已正确安装 Microsoft Edge 浏览器和对应版本的 EdgeDriver (msedgedriver.exe)，并将其路径添加到系统 PATH 或在设置中指定路径。"
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
            self.driver.get(url)
            self.logger.info(f"WebDriver 已请求 URL: {url}") # 提升日志级别
            # --- 添加日志：记录页面源代码 ---
            # 等待页面某个基础元素加载完成
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
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
            # 提供默认值（如果需要，但最好依赖用户配置）
            default_detail_selectors = {
                'title_selector': "#__next > div > main > div > div.index_wrapbox__VFyXe > div.index_wrapper__L_zqV > h1",
                'time_selector': "#__next > div > main > div > div.index_wrapbox__VFyXe > div.index_wrapper__L_zqV > div.index_headerContent__sASF4 > div > div.ant-space.ant-space-horizontal.ant-space-align-center > div:nth-child(1) > span", # 对应之前的 date
                'author_selector': "#__next > div > main > div > div.index_wrapbox__VFyXe > div.index_wrapper__L_zqV > div.index_headerContent__sASF4 > div > div:nth-child(1)",
                'content_selector': "div.index_cententWrap__Jv8jK", # 尝试使用日志中观察到的更通用的类名
            }
            # 合并用户配置和默认值，用户配置优先
            final_detail_selectors = {**default_detail_selectors, **selector_config}

            # 检查关键选择器是否存在
            content_selector = final_detail_selectors.get('content_selector')
            if not content_selector:
                self.logger.error(f"澎湃新闻源 '{source_name}' 未配置详情页 'content_selector'，无法提取正文。")
                self.selector_failed.emit(source_name) # 发出信号
                detail_data['content'] = "错误：未配置内容选择器"
                return detail_data

            # --- 尝试提取各个字段 ---
            # 分开处理 content 和其他字段
            content_html = None
            other_fields = {}

            # 1. 优先提取 Content HTML
            # 1. 优先提取 Content HTML
            try:
                self.logger.info(f"尝试使用选择器 '{content_selector}' 定位内容容器...")
                content_container = WebDriverWait(self.driver, 5).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, content_selector))
                )
                self.logger.info(f"成功定位到内容容器: {content_container.tag_name}")
                self.logger.info(f"DEBUG - PengpaiCollector: 使用选择器 '{content_selector}' 定位内容容器结果: {'成功' if content_container else '失败'}") # DEBUG LOG

                # 清理广告等 (保留之前的逻辑)
                selectors_to_remove = [
                    '.ad', '.ad-container', '.video-container', '.recommend', '.related-reads', 'script',
                    'style', '.content_open_app', '.go_app', '.news_open_app_fixed', '.toutiao', '.sponsor',
                    '.adsbygoogle', '[id*="ad"]', '[class*="video"]'
                ]
                for sel_remove in selectors_to_remove:
                    try:
                        script = f"arguments[0].querySelectorAll('{sel_remove}').forEach(el => el.parentNode.removeChild(el));"
                        self.driver.execute_script(script, content_container)
                    except Exception: pass

                # 获取容器的 innerHTML
                # 获取容器的 innerHTML
                content_html = content_container.get_attribute('innerHTML').strip()
                self.logger.info(f"详情页 {url}: 获取到原始 innerHTML (前100字符): {content_html[:100]}")

                # --- 图片处理逻辑已移除 ---
                # content_html 现在包含原始的 innerHTML，包括原始的 <img> 标签和 src
                self.logger.info(f"详情页 {url}: 保留原始 innerHTML (前100字符): {content_html[:100]}")

            except (TimeoutException, NoSuchElementException) as e_content_find:
                 self.logger.error(f"澎湃新闻源 '{source_name}' 的内容选择器 '{content_selector}' 失效，在 {url} 未找到匹配项: {e_content_find}")
                 self.selector_failed.emit(source_name) # 发出信号
                 detail_data['content'] = f"错误：内容选择器 '{content_selector}' 失效"
                 return detail_data # 无法获取内容，直接返回
            except Exception as e_content:
                 self.logger.error(f"详情页 {url}: 获取或处理内容容器 HTML 时出错: {e_content}", exc_info=True)
                 # 即使出错，也尝试提取其他字段

            # 2. 提取其他字段 (Title, Date, Author) - 仍然使用 .text
            # 2. 提取其他字段 (Title, Date/Time, Author) - 使用配置的选择器
            field_mapping = {
                'title': final_detail_selectors.get('title_selector'),
                'date': final_detail_selectors.get('time_selector'), # 映射 time_selector 到 date
                'author': final_detail_selectors.get('author_selector'),
            }

            for field, selector in field_mapping.items():
                 if not selector: # 如果未配置该选择器，跳过
                     self.logger.debug(f"详情页 {url}: 未配置 '{field}' 的选择器，跳过提取。")
                     continue

                 extracted_value = None
                 try:
                     element = WebDriverWait(self.driver, 3).until(
                         EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                     )
                     extracted_value = element.text.strip()
                     if extracted_value:
                         self.logger.info(f"详情页 {url}: 通过 CSS '{selector}' 提取到 {field}: '{extracted_value[:50]}...'")
                         other_fields[field] = extracted_value # 存储到字典
                     else:
                         # 找到了元素但文本为空，也可能意味着选择器部分失效
                         self.logger.warning(f"详情页 {url}: 使用 CSS '{selector}' 找到了 {field} 元素，但其文本为空。")
                 except (TimeoutException, NoSuchElementException):
                     # 如果非必须字段（如 author）提取失败，仅记录日志
                     log_level = logging.WARNING if field in ['author'] else logging.ERROR
                     self.logger.log(log_level, f"详情页 {url}: 使用 CSS '{selector}' 未找到 {field} 元素 (3秒超时)。")
                     # 对于关键字段（如 date/time），可以考虑发出信号，但目前仅记录错误
                     # if field == 'date':
                     #     self.selector_failed.emit(source_name)
                 except Exception as e_extract:
                     self.logger.warning(f"详情页 {url}: 使用 CSS '{selector}' 提取 {field} 时出错: {e_extract}")
            # 3. 组合结果
            detail_data['pub_date'] = other_fields.get('date')
            detail_data['author'] = other_fields.get('author')
            detail_data['content'] = content_html # 使用获取到的 HTML 内容

            # --- 内容后处理和检查 ---
            content = detail_data.get('content')
            if content:
                content = re.sub(r'\n{3,}', '\n\n', content) # 合并多余空行
                if len(content) > 15000: # 稍微放宽截断长度
                    content = content[:15000] + "...(内容过长，已截断)"
                detail_data['content'] = content
                self.logger.info(f"详情页 {url}: 最终提取内容长度: {len(content)}")
            else:
                self.logger.error(f"详情页 {url}: 尝试所有选择器后仍未找到有效内容或内容为空，放弃提取。") # 调整日志信息
                if not detail_data.get('content'): # 确保错误信息只在内容为空时设置
                    detail_data['content'] = "无法定位或提取新闻内容区域，请访问原始链接查看。"


        except TimeoutException:
             self.logger.error(f"加载详情页 {url} 超时")
             detail_data['content'] = f"加载页面超时"
        except Exception as e:
            self.logger.error(f"使用 Selenium 获取或解析详情页 {url} 时发生错误: {e}", exc_info=True)
            detail_data['content'] = f"Selenium 处理失败: {e}"

        return detail_data
