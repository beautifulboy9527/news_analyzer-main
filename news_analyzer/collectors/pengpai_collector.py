#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
澎湃新闻收集器模块
"""

import logging
import requests
import re # 导入正则表达式模块
import os # 导入 os 模块
import json # 导入 json 模块
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, JavascriptException # 导入 JavascriptException
import time
from bs4 import BeautifulSoup
from typing import List, Dict, Optional # 导入 Optional
from urllib.parse import urljoin # 用于拼接相对 URL

from news_analyzer.models import NewsSource # 导入数据模型

class PengpaiCollector:
    """
    负责从澎湃新闻网站抓取新闻的收集器。
    """
    # 澎湃新闻手机版首页 URL
    MOBILE_URL = "https://m.thepaper.cn"

    def __init__(self):
        self.logger = logging.getLogger('news_analyzer.collectors.pengpai')
        self.session = requests.Session() # 使用 Session 保持连接和 cookies
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' # 使用桌面 User-Agent，Selenium 通常工作更好
        })

        # WebDriver 将在首次需要时延迟初始化
        self.driver = None
        self.logger.info("PengpaiCollector 初始化完成，WebDriver 将延迟加载。")

    def close(self):
        """关闭 WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Selenium WebDriver 已关闭")
            except Exception as e:
                self.logger.error(f"关闭 WebDriver 时出错: {e}")

    def collect(self, source_config: NewsSource, cancel_checker: callable = lambda: False) -> List[Dict]:
        """
        执行澎湃新闻手机版的抓取。

        Args:
            source_config: 澎湃新闻源的配置对象
            cancel_checker: 一个 callable 对象，调用它返回 True 时应中断抓取。

        Returns:
            一个包含新闻信息的字典列表，每个字典应包含 'title', 'link' 等键。
            注意：这里返回的是原始字典列表，AppService 会负责将其转换为 NewsArticle 对象。
            目前仅尝试抓取标题和链接，时间和摘要可能需要访问详情页。
        """
        self.logger.info(f"开始抓取澎湃新闻 (手机版): {source_config.name}")
        news_items = []
        target_url = self.MOBILE_URL

        try:
            response = self.session.get(target_url, timeout=20) # 增加超时时间
            response.raise_for_status()
            # 澎湃手机版通常是 UTF-8
            response.encoding = 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')

            # --- 查找新闻列表项 ---
            # 尝试的选择器 (基于对移动端结构的推测，非常可能需要调整!)
            # 查找包含新闻链接的 <a> 标签，可能在某个特定 ID 或 class 的容器内
            # 常见模式 1: 查找 ID 为 listContent 下的所有直接子 a 标签
            news_links = soup.select('#listContent > a')
            self.logger.debug(f"使用选择器 '#listContent > a' 找到 {len(news_links)} 个链接")

            # 常见模式 2: 如果模式1找不到，尝试查找 class 为 news_item 的 div 下的 a 标签
            if not news_links:
                news_links = soup.select('div.news_item a')
                self.logger.debug(f"使用选择器 'div.news_item a' 找到 {len(news_links)} 个链接")

            # 常见模式 3: 查找所有包含 href 指向 /newsDetail_forward_ 的 a 标签
            if not news_links:
                 news_links = soup.find_all('a', href=lambda href: href and 'newsDetail_forward_' in href)
                 self.logger.debug(f"查找 href 包含 'newsDetail_forward_' 的 <a> 标签，找到 {len(news_links)} 个")


            if not news_links:
                 self.logger.warning(f"在 {target_url} 未找到匹配的新闻链接元素")
                 return []

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

                    # --- 再次优化标题提取逻辑 ---
                    title = ""
                    # 尝试更具体的选择器组合
                    possible_title_tags = link_element.select('h3, h4, div.news_title, span.content_title, p.title') # 查找可能的标题容器
                    if possible_title_tags:
                        # 优先选择第一个找到的非空文本
                        for tag in possible_title_tags:
                            title = tag.get_text(strip=True)
                            if title:
                                self.logger.debug(f"通过选择器 '{tag.name}.{tag.get('class', '')}' 提取到标题: '{title[:30]}...'")
                                break

                    # 如果通过特定标签找不到，尝试获取 <a> 标签本身的直接文本（排除子标签）
                    if not title:
                         # 获取 a 标签下所有直接文本节点并合并
                         direct_text = ''.join(link_element.find_all(string=True, recursive=False)).strip()
                         if direct_text and len(direct_text) > 5: # 增加长度判断，过滤掉纯粹的图标或短标签
                             title = direct_text
                             self.logger.debug(f"通过 <a> 直接文本提取到标题: '{title[:30]}...'")
                         else: # 如果直接文本无效，最后尝试获取所有文本
                             title = link_element.get_text(strip=True)
                             self.logger.debug(f"通过 <a> get_text() 提取到标题: '{title[:30]}...'")


                    # 清理和验证标题
                    title = title.strip()
                    # 检查标题是否有效（例如，不是纯数字、时间戳或过短）
                    if (not title or len(title) < 5 or title.isdigit() or
                        re.match(r'^\d{2}:\d{2}(\.\.\.)?$', title) or
                        "广告" in title or "推广" in title or "视频" in title):
                        self.logger.warning(f"提取到的标题 '{title}' 无效或包含广告/视频，跳过链接 {absolute_link}")
                        continue
                    # --- 标题提取结束 ---

                    processed_links.add(link) # 添加到已处理集合

                    # 获取详情页信息
                    detail_data = self._fetch_detail(absolute_link)

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
        return news_items

    def _fetch_detail(self, url: str) -> Dict:
        """
        使用 Selenium 获取并解析新闻详情页，提取发布日期和正文。
        使用用户提供的精确 CSS 选择器进行尝试。

        Args:
            url: 新闻详情页的 URL。

        Returns:
            包含 'pub_date', 'content', 'author' 的字典，如果提取失败则值为 None 或错误信息。
        """
        self.logger.debug(f"开始获取详情页: {url}")
        detail_data = {'pub_date': None, 'content': None, 'author': None}

        # --- 延迟初始化 WebDriver ---
        if self.driver is None:
            # ... (WebDriver 初始化代码保持不变) ...
            self.logger.info("首次调用 _fetch_detail，尝试初始化 Selenium Edge WebDriver...")
            try:
                options = webdriver.EdgeOptions()
                options.add_argument('--headless')
                options.add_argument('--disable-gpu')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
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
                    self.logger.info("尝试使用系统 PATH 中的 EdgeDriver (msedgedriver.exe)")
                self.driver = webdriver.Edge(service=service, options=options)
                self.logger.info("Selenium WebDriver (Edge) 初始化成功 (无头模式)")
            except Exception as e:
                self.logger.error(f"延迟初始化 Selenium Edge WebDriver 失败: {e}. 详情页抓取将受限。", exc_info=True)
                error_msg = f"Edge WebDriver 初始化失败: {e}\n请确保已正确安装 Microsoft Edge 浏览器和对应版本的 EdgeDriver (msedgedriver.exe)，并将其路径添加到系统 PATH 或在设置中指定路径。"
                detail_data['content'] = error_msg
                self.driver = None
                return detail_data

        if not self.driver:
             self.logger.error("WebDriver 实例无效，无法获取详情页。")
             detail_data['content'] = "WebDriver 实例无效"
             return detail_data

        try:
            self.logger.debug(f"使用 WebDriver 加载 URL: {url}")
            self.driver.get(url)
            # 等待页面某个基础元素加载完成
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            self.logger.debug(f"详情页 {url}: Body 元素已加载")

            # --- 定义选择器 ---
            # 基于用户提供的例子
            selectors = {
                'title': [
                    "#__next > div > main > div > div.index_wrapbox__VFyXe > div.index_wrapper__L_zqV > h1", # URL1
                    "#__next > div > main > div > div.index_wrapbox__VFyXe > div.index_wrapper__L_zqV > div.index_cententWrapBox__bh0OY > div.index_cententWrap__Jv8jK > p:nth-child(1)" # URL2
                ],
                'date': [
                    "#__next > div > main > div > div.index_wrapbox__VFyXe > div.index_wrapper__L_zqV > div.index_headerContent__sASF4 > div > div.ant-space.ant-space-horizontal.ant-space-align-center > div > span"
                ],
                'author': [
                    "#__next > div > main > div > div.index_wrapbox__VFyXe > div.index_wrapper__L_zqV > div.index_headerContent__sASF4 > div > div:nth-child(1)"
                ],
                'content': [
                    "#__next > div > main > div > div.index_wrapbox__VFyXe > div.index_wrapper__L_zqV > div.index_cententWrapBox__bh0OY > div.index_cententWrap__Jv8jK", # URL1
                    "#__next > div > main > div > div.index_wrapbox__VFyXe > div.index_wrapper__L_zqV > div.index_cententWrapBox__bh0OY > div.index_cententWrap__Jv8jK > p:nth-child(3)" # URL2 (取第三段作为内容?) - 可能需要调整为取所有 p
                ]
            }

            # --- 尝试提取各个字段 ---
            for field, css_selectors in selectors.items():
                extracted_value = None
                for selector in css_selectors:
                    try:
                        # 使用较短超时查找元素
                        element = WebDriverWait(self.driver, 3).until(
                            EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        extracted_value = element.text.strip()
                        if extracted_value:
                            self.logger.info(f"详情页 {url}: 通过 CSS '{selector}' 提取到 {field}: '{extracted_value[:50]}...'")
                            break # 找到就停止尝试该字段的其他选择器
                    except (TimeoutException, NoSuchElementException):
                        self.logger.debug(f"详情页 {url}: 使用 CSS '{selector}' 未找到 {field} 元素 (3秒超时)")
                    except Exception as e_extract:
                        self.logger.warning(f"详情页 {url}: 使用 CSS '{selector}' 提取 {field} 时出错: {e_extract}")
                # 存储提取到的值 (即使是 None)
                if field == 'date':
                    detail_data['pub_date'] = extracted_value
                elif field == 'author':
                    detail_data['author'] = extracted_value # 存储作者信息
                elif field == 'content':
                    # 特殊处理内容：如果用 URL2 的选择器只取到第三段，可能不完整
                    # 尝试获取 URL1 选择器对应的整个容器文本
                    if extracted_value and selector == selectors['content'][1]: # 如果是 URL2 的选择器
                         try:
                             content_container = WebDriverWait(self.driver, 2).until(
                                 EC.visibility_of_element_located((By.CSS_SELECTOR, selectors['content'][0])) # 尝试 URL1 的容器
                             )
                             # 清理广告等
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
                             # 提取文本
                             paragraphs = content_container.find_elements(By.TAG_NAME, 'p')
                             if paragraphs:
                                 content = '\n'.join([p.text.strip() for p in paragraphs if p.text.strip()])
                             else:
                                 content = content_container.text.strip()
                                 content = '\n'.join([line for line in content.split('\n') if line])
                             extracted_value = content
                             self.logger.info(f"详情页 {url}: 使用 URL1 容器选择器重新提取到内容，长度: {len(extracted_value)}")
                         except Exception as e_refetch:
                             self.logger.warning(f"详情页 {url}: 尝试用 URL1 容器选择器重新获取内容失败: {e_refetch}")
                             # 保留之前提取到的第三段内容 (extracted_value)

                    detail_data['content'] = extracted_value
                # 标题不需要特殊处理，因为 collect 方法会提取列表页的标题

            # --- 内容后处理和检查 ---
            content = detail_data.get('content')
            if content:
                content = re.sub(r'\n{3,}', '\n\n', content) # 合并多余空行
                if len(content) > 15000: # 稍微放宽截断长度
                    content = content[:15000] + "...(内容过长，已截断)"
                detail_data['content'] = content
                self.logger.info(f"详情页 {url}: 最终提取内容长度: {len(content)}")
            else:
                self.logger.error(f"详情页 {url}: 尝试所有选择器后仍未找到有效内容，放弃提取。")
                detail_data['content'] = "无法定位或提取新闻内容区域，请访问原始链接查看。"


        except TimeoutException:
             self.logger.error(f"加载详情页 {url} 超时")
             detail_data['content'] = f"加载页面超时"
        except Exception as e:
            self.logger.error(f"使用 Selenium 获取或解析详情页 {url} 时发生错误: {e}", exc_info=True)
            detail_data['content'] = f"Selenium 处理失败: {e}"

        return detail_data
