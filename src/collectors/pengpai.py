import logging
import os
import shutil
import time
import uuid
from typing import List, Dict, Optional, Tuple, Callable

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .base_collector import BaseCollector
from ..models import NewsSource
from ..utils.date_utils import clean_date_string
from ..config.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_PENGPAI_CONFIG = {
    "base_url": "https://m.thepaper.cn/",
    "content_selector": "div.index_cententWrap__Jv8jK",
    "date_selector": "div.index_left__LfzyH > div.ant-space > div.ant-space-item:nth-child(1) > span",
    "author_selector": "div.index_left__LfzyH > div:nth-child(1)",
    "wait_timeout": 15,
    "webdriver_profile_base_path": "data/webdriver_profiles",
    "headless": True,
    "article_limit": None,
    "max_retries": 2,
    "retry_delay": 3,
    "accept_insecure_certs": True,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62",
    "proxy_server": None,
    "disable_gpu": True,
    "no_sandbox": True,
    "disable_dev_shm_usage": True,
    "page_load_strategy": "normal"
}

class PengpaiCollector(BaseCollector):
    """
    澎湃新闻采集器
    """
    def __init__(self, config: Optional[Dict] = None, data_dir: Optional[str] = None):
        merged_config = {**DEFAULT_PENGPAI_CONFIG, **(config if config else {})}
        super().__init__(merged_config)
        self.driver: Optional[webdriver.Edge] = None
        self.source_name = merged_config.get("source_name", "澎湃新闻")
        current_data_dir = data_dir if data_dir else self.config.get("webdriver_profile_base_path", DEFAULT_PENGPAI_CONFIG["webdriver_profile_base_path"])
        self._cleanup_old_profiles(current_data_dir)
        profile_dir_name = f"edge_profile_{uuid.uuid4()}"
        self.profile_path = os.path.join(current_data_dir, profile_dir_name)
        logger.info(f"PengpaiCollector 初始化完成，WebDriver 将延迟加载。Profile将创建于: {self.profile_path}")

    def _cleanup_old_profiles(self, base_profile_path: str):
        logger.info(f"开始清理旧的 WebDriver 配置文件目录: {base_profile_path}")
        if os.path.exists(base_profile_path):
            for item_name in os.listdir(base_profile_path):
                item_path = os.path.join(base_profile_path, item_name)
                if os.path.isdir(item_path) and item_name.startswith("edge_profile_"):
                    try:
                        shutil.rmtree(item_path)
                        logger.info(f"删除旧的配置文件目录: {item_path}")
                    except Exception as e:
                        logger.warning(f"删除旧配置文件目录 {item_path} 失败: {e}")
        logger.info("旧配置文件清理完成。")

    def _lazy_init_driver(self):
        logger.error("PENGPAI_LAZY_INIT_DRIVER_ENTERED")
        if self.driver:
            try:
                _ = self.driver.current_url
                logger.debug("WebDriver 实例已存在且活动。")
                return
            except WebDriverException:
                logger.warning("WebDriver 实例已存在但不再活动，将尝试重新初始化。")
                self.close()
                self.driver = None

        logger.info("WebDriver 实例为 None，开始初始化...")
        edge_options = EdgeOptions()
        if self.config.get("headless", DEFAULT_PENGPAI_CONFIG["headless"]):
            edge_options.add_argument("--headless")
        
        if self.config.get("disable_gpu", DEFAULT_PENGPAI_CONFIG["disable_gpu"]):
            edge_options.add_argument("--disable-gpu")
        if self.config.get("no_sandbox", DEFAULT_PENGPAI_CONFIG["no_sandbox"]):
            edge_options.add_argument("--no-sandbox")
        if self.config.get("disable_dev_shm_usage", DEFAULT_PENGPAI_CONFIG["disable_dev_shm_usage"]):
            edge_options.add_argument("--disable-dev-shm-usage")
        if self.config.get("accept_insecure_certs", DEFAULT_PENGPAI_CONFIG["accept_insecure_certs"]):
            edge_options.add_argument('--ignore-certificate-errors')
        
        user_agent = self.config.get("user_agent", DEFAULT_PENGPAI_CONFIG["user_agent"])
        if user_agent:
            edge_options.add_argument(f"user-agent={user_agent}")

        proxy_server = self.config.get("proxy_server", DEFAULT_PENGPAI_CONFIG["proxy_server"])
        if proxy_server:
            edge_options.add_argument(f"--proxy-server={proxy_server}")
            
        edge_options.page_load_strategy = self.config.get("page_load_strategy", DEFAULT_PENGPAI_CONFIG["page_load_strategy"])

        os.makedirs(self.profile_path, exist_ok=True)
        logger.info(f"为 WebDriver 创建用户数据目录: {self.profile_path}")
        edge_options.add_argument(f"user-data-dir={self.profile_path}")
        
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)

        driver_path_project = os.path.join(os.getcwd(), "drivers", "msedgedriver.exe")
        driver_path_to_use = None

        if os.path.exists(driver_path_project):
            logger.info(f"尝试使用项目内置的EdgeDriver路径: {driver_path_project}")
            driver_path_to_use = driver_path_project
        else:
            logger.info(f"未在 {driver_path_project} 找到内置EdgeDriver，将尝试使用系统PATH中的msedgedriver.exe")

        service = None
        if driver_path_to_use:
            service = EdgeService(executable_path=driver_path_to_use)
            service.creationflags = 0x08000000 # CREATE_NO_WINDOW
            logger.info(f"使用 EdgeService，路径: {driver_path_to_use}")

        try:
            logger.info(f"正在尝试使用以下配置初始化 WebDriver: Options={edge_options.arguments}, Service Path (if any)='{driver_path_to_use}'")
            if service:
                self.driver = webdriver.Edge(service=service, options=edge_options)
            else:
                self.driver = webdriver.Edge(options=edge_options)
            logger.info(f"webdriver.Edge(...) 执行完毕，WebDriver 实例: {'成功创建' if self.driver else '创建失败'}")
            
            if self.driver:
                self.driver.set_page_load_timeout(self.config.get("wait_timeout", DEFAULT_PENGPAI_CONFIG["wait_timeout"]) * 2)
                self.driver.implicitly_wait(5)
        except WebDriverException as e:
            logger.error(f"初始化 WebDriver 失败: {e}", exc_info=True)
            if "cannot find Microsoft Edge binary" in str(e).lower():
                 logger.error("严重错误: 未找到 Microsoft Edge 浏览器。请确保已正确安装。")
            elif "Timed out receiving message from renderer" in str(e) or "unable to discover open pages" in str(e):
                logger.error("WebDriver 启动时超时或无法连接到页面，可能与无头模式或环境有关。尝试检查配置。")
            self.driver = None
        except Exception as e:
            logger.error(f"初始化 WebDriver 时发生未知错误: {e}", exc_info=True)
            self.driver = None
        logger.info("WebDriver 初始化代码块执行完毕。")
        logger.error(f"PENGPAI_LAZY_INIT_DRIVER_RESULT: Driver is {'SET' if self.driver else 'NONE'}")

    def collect(self, source: NewsSource, progress_callback: Optional[Callable[[int, int], None]] = None) -> List[Dict]:
        logger.error("PENGPAI_COLLECT_METHOD_ENTERED")
        logger.info(f"PengpaiCollector.collect 方法开始执行，来源: {source.name}")
        final_articles: List[Dict] = []
        processed_links = set()

        try:
            self._lazy_init_driver()
            logger.error(f"PENGPAI_COLLECT_AFTER_LAZY_INIT: Driver is {'SET' if self.driver else 'NONE'}")
            if not self.driver:
                logger.error("WebDriver 初始化失败，无法采集澎湃新闻。")
                return final_articles
            
            logger.info(f"开始抓取澎湃新闻 (手机版): {source.name}")
            logger.error(f"PENGPAI_COLLECT_BEFORE_DRIVER_GET: URL={self.config.get("base_url", DEFAULT_PENGPAI_CONFIG["base_url"])}")
            self.driver.get(self.config.get("base_url", DEFAULT_PENGPAI_CONFIG["base_url"]))
            logger.error("PENGPAI_COLLECT_AFTER_DRIVER_GET")
            WebDriverWait(self.driver, self.config.get("wait_timeout", DEFAULT_PENGPAI_CONFIG["wait_timeout"])).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href^="/newsDetail_forward_"]'))
            )
            logger.info("尝试使用选择器 'a[href^=\"/newsDetail_forward_\"]' 查找新闻列表链接...")
            
            link_elements = self.driver.find_elements(By.CSS_SELECTOR, 'a[href^="/newsDetail_forward_"]')
            logger.info(f"使用选择器 'a[href^=\"/newsDetail_forward_\"]' 找到 {len(link_elements)} 个链接元素")

            article_links_with_titles: List[Tuple[str, str]] = []
            for el in link_elements:
                try:
                    href = el.get_attribute('href')
                    title_text = el.text.strip()
                    if href and href.startswith("http") and href not in processed_links:
                        article_links_with_titles.append((href, title_text))
                        processed_links.add(href)
                except Exception as e:
                    logger.warning(f"提取链接或标题时出错: {e}", exc_info=True)
            
            limit = self.config.get("article_limit")
            if limit is not None and isinstance(limit, int):
                article_links_with_titles = article_links_with_titles[:limit]
                logger.info(f"应用文章数量限制，最多处理 {limit} 篇新闻。")

            logger.info(f"最终准备处理的新闻链接数量: {len(article_links_with_titles)}")
            total_links_to_process = len(article_links_with_titles)

            for i, (link_url, initial_title) in enumerate(article_links_with_titles):
                logger.info(f"处理链接: {link_url}, 提取到初步标题: '{initial_title}'")
                
                if not initial_title or len(initial_title) < 5 or initial_title.isdigit() or initial_title.startswith("00:"):
                    logger.warning(f"标题 '{initial_title}' 被判断为无效，跳过链接 {link_url}")
                    if progress_callback:
                        logger.debug(f"PengpaiCollector: Calling progress_callback({i + 1}, {total_links_to_process}) for source '{source.name}'")
                        progress_callback(i + 1, total_links_to_process)
                    continue
                
                logger.info(f"标题 '{initial_title}' 有效，准备获取详情。")
                
                article_detail = self._fetch_detail(link_url, source.name)
                if article_detail and article_detail.get("content"):
                    detail_title = article_detail.get("title", initial_title)
                    if not detail_title or len(detail_title) < 5:
                        final_title = initial_title
                    else:
                        final_title = detail_title
                    
                    article_data = {
                        "title": final_title,
                        "link": link_url,
                        "summary": article_detail.get("summary"),
                        "pub_date": article_detail.get("pub_date"),
                        "content": article_detail.get("content"),
                        "author": article_detail.get("author"),
                        "source_name": source.name,
                        "category": source.category
                    }
                    final_articles.append(article_data)
                else:
                    logger.warning(f"未能从 {link_url} 获取到有效的文章详情或内容为空，已跳过。")
                
                if progress_callback:
                    logger.debug(f"PengpaiCollector: Calling progress_callback({i + 1}, {total_links_to_process}) for source '{source.name}'")
                    progress_callback(i + 1, total_links_to_process)

        except TimeoutException:
            logger.error(f"打开或查找澎湃新闻页面元素超时: {self.config.get('base_url', DEFAULT_PENGPAI_CONFIG['base_url'])}", exc_info=True)
        except WebDriverException as e:
            logger.error(f"WebDriver操作失败: {e}", exc_info=True)
            logger.error(f"PENGPAI_COLLECT_METHOD_EXITING_DUE_TO_WEBDRIVER_EXCEPTION: {e}")
            self.close()
            self.driver = None 
        except Exception as e:
            logger.error(f"采集澎湃新闻 '{source.name}' 时发生未预期错误: {e}", exc_info=True)
            logger.error(f"PENGPAI_COLLECT_METHOD_EXITING_DUE_TO_EXCEPTION: {e}")
        finally:
            pass 

        logger.info(f"澎湃新闻抓取完成，初步获取 {len(final_articles)} 条")
        logger.error(f"PENGPAI_COLLECT_METHOD_EXITING_NORMALLY with {len(final_articles)} items")
        logger.debug(f"DEBUG - PengpaiCollector: collect 方法完成，最终返回 {len(final_articles)} 条新闻。前 3 条: {final_articles[:3]}")
        return final_articles

    def _fetch_detail(self, url: str, source_name_for_log: str) -> Optional[Dict[str, str]]:
        logger.info(f"进入 _fetch_detail 方法，URL: {url}")
        if not self.driver:
            logger.error(f"_fetch_detail: WebDriver 实例为 None，无法获取详情: {url}")
            self._lazy_init_driver()
            if not self.driver:
                logger.error(f"_fetch_detail: 再次尝试初始化 WebDriver 失败，放弃获取 {url}")
                return None
        
        detail_data = {
            "title": "",
            "content": "",
            "pub_date": None,
            "author": None,
            "summary": None
        }
        max_retries = self.config.get("max_retries", DEFAULT_PENGPAI_CONFIG["max_retries"])
        retry_delay = self.config.get("retry_delay", DEFAULT_PENGPAI_CONFIG["retry_delay"])

        for attempt in range(max_retries + 1):
            try:
                logger.info(f"尝试使用 WebDriver 获取详情页: {url} (尝试 {attempt + 1}/{max_retries + 1})")
                self.driver.get(url)
                logger.info(f"WebDriver 已请求 URL: {url}")

                WebDriverWait(self.driver, self.config.get("wait_timeout", DEFAULT_PENGPAI_CONFIG["wait_timeout"])).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                logger.info(f"详情页 {url}: Body 元素已加载")

                try:
                    title_selectors = ["h1", "div.newsDetail_title__xS_uB", "div.videoHeader_title__r3Lar"]
                    for ts_idx, title_selector in enumerate(title_selectors):
                        try:
                            title_element = self.driver.find_element(By.CSS_SELECTOR, title_selector)
                            page_title = title_element.text.strip()
                            if page_title and len(page_title) > 5:
                                detail_data["title"] = page_title
                                logger.info(f"详情页 {url}: 通过 CSS '{title_selector}' 提取到标题: '{page_title[:50]}...'")
                                break
                        except NoSuchElementException:
                            if ts_idx == len(title_selectors) -1:
                                logger.warning(f"详情页 {url}: 未能通过任何预设选择器找到标题元素。")
                except Exception as e_title:
                    logger.warning(f"详情页 {url}: 提取标题时发生错误: {e_title}")

                content_selector = self.config.get("content_selector", DEFAULT_PENGPAI_CONFIG["content_selector"])
                logger.info(f"尝试使用选择器 '{content_selector}' 定位内容容器...")
                
                content_container = WebDriverWait(self.driver, self.config.get("wait_timeout", DEFAULT_PENGPAI_CONFIG["wait_timeout"])).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, content_selector))
                )
                logger.info(f"成功定位到内容容器: {content_container.tag_name if content_container else 'None'}")
                logger.debug(f"DEBUG - PengpaiCollector: 使用选择器 '{content_selector}' 定位内容容器结果: {'成功' if content_container else '失败'}")

                if content_container:
                    raw_html_content = content_container.get_attribute('innerHTML')
                    logger.info(f"详情页 {url}: 获取到原始 innerHTML (前100字符): {raw_html_content[:100].replace('\n', ' ')}")
                    detail_data["content"] = raw_html_content
                    logger.info(f"详情页 {url}: 保留原始 innerHTML (前100字符): {detail_data['content'][:100].replace('\n', ' ')}")

                    # 更新日期提取逻辑
                    date_selectors = [
                        self.config.get("date_selector", DEFAULT_PENGPAI_CONFIG["date_selector"]), # 原始选择器
                        "#__next > div > main > div > div.index_wrapper__mHU4q > div.index_headerContent__mOJJb > span.index_nowrap__rmdw_", # 用户提供1
                        "#__next > div > main > div > div.index_wrapbox__VFyXe > div.index_wrapper__L_zqV > div.index_headerContent__sASF4 > div > div.ant-space.ant-space-horizontal.ant-space-align-center > div:nth-child(1) > span" # 用户提供2
                    ]
                    date_text = None
                    for selector in date_selectors:
                        if not selector: continue # 跳过空选择器
                        date_text = self._safe_get_text(self.driver, selector)
                        if date_text:
                            logger.info(f"详情页 {url}: 通过 CSS '{selector}' 提取到 date: '{date_text[:30]}...'")
                            cleaned_date_str = clean_date_string(date_text)
                            detail_data["pub_date"] = cleaned_date_str
                            break 
                    if not date_text: 
                        logger.warning(f"详情页 {url}: 未能通过任何预设CSS选择器提取到日期。")
                        detail_data["pub_date"] = None

                    # 更新作者提取逻辑 (如果需要也可以定义多个选择器)
                    author_selector = self.config.get("author_selector", DEFAULT_PENGPAI_CONFIG["author_selector"])
                    # 可以仿照日期提取方式，为作者也设置一个选择器列表
                    # author_selectors = [author_selector, "selector2", "selector3"]
                    # for selector in author_selectors: ...
                    author_text = self._safe_get_text(self.driver, author_selector)
                    if author_text:
                        cleaned_author_str = clean_date_string(author_text) # 注意：作者字段通常不需要 clean_date_string
                        logger.info(f"详情页 {url}: 通过 CSS '{author_selector}' 提取到 author: '{cleaned_author_str[:30]}...'")
                        detail_data["author"] = cleaned_author_str.replace("来源：", "").strip() # 简单清理作者
                    else:
                        logger.warning(f"详情页 {url}: 未能通过 CSS '{author_selector}' 提取到作者。")
                        detail_data["author"] = None
                        
                else:
                    logger.error(f"澎湃新闻源 '{source_name_for_log}' 的内容选择器 '{content_selector}' 失效，在 {url} 未找到匹配项")
                    detail_data["content"] = f"错误：无法使用选择器 {content_selector} 在页面 {url} 获取内容。"

                logger.info(f"详情页 {url}: 最终提取内容长度: {len(detail_data['content'] if detail_data['content'] else '')}")
                return detail_data

            except TimeoutException:
                logger.warning(f"获取详情页 {url} 超时 (尝试 {attempt + 1}/{max_retries + 1})。")
                if attempt < max_retries:
                    logger.info(f"将在 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"获取详情页 {url} 达到最大重试次数，放弃。")
                    detail_data["content"] = f"错误：获取页面 {url} 超时。"
                    return detail_data
            except NoSuchElementException as e_nse:
                logger.error(f"在详情页 {url} 中未找到关键元素 (尝试 {attempt + 1}/{max_retries + 1}): {e_nse.msg}", exc_info=False)
                if attempt < max_retries:
                    logger.info(f"将在 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"获取详情页 {url} 因元素未找到达到最大重试次数，放弃。")
                    detail_data["content"] = f"错误：页面 {url} 结构已更改或元素不存在。"
                    return detail_data
            except Exception as e_detail:
                logger.error(f"获取详情页 {url} 时发生未知错误 (尝试 {attempt + 1}/{max_retries + 1}): {e_detail}", exc_info=True)
                if attempt < max_retries:
                    logger.info(f"将在 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                else:
                    detail_data["content"] = f"错误：处理页面 {url} 时发生未知错误。"
                    return detail_data
        
        logger.error(f"_fetch_detail: 所有尝试均失败，未能获取 {url} 的详情。")
        return None

    def _safe_get_text(self, driver_instance, selector: str, timeout: int = 5) -> Optional[str]:
        """安全地获取元素的文本内容，带有超时和异常处理。"""
        try:
            element = WebDriverWait(driver_instance, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return element.text.strip() if element else None
        except TimeoutException:
            logger.debug(f"安全获取文本：选择器 '{selector}' 超时 ({timeout}s)。")
            return None
        except NoSuchElementException:
            logger.debug(f"安全获取文本：选择器 '{selector}' 未找到元素。")
            return None
        except Exception as e:
            logger.warning(f"安全获取文本：选择器 '{selector}' 时发生未知错误: {e}")
            return None

    def close(self):
        """
        关闭WebDriver实例并尝试清理用户数据目录。
        """
        if self.driver:
            try:
                logger.info("尝试关闭 WebDriver 实例...")
                self.driver.quit()
                logger.info("WebDriver 实例已关闭。")
            except Exception as e:
                logger.error(f"关闭 WebDriver 时发生错误: {e}", exc_info=True)
            finally:
                self.driver = None # 确保driver被设置为None
        
        # 尝试清理profile目录，即使driver关闭失败
        if self.profile_path and os.path.exists(self.profile_path):
            try:
                logger.info(f"尝试删除 WebDriver profile 目录: {self.profile_path}")
                # 在Windows上，有时即使driver.quit()了，目录也可能被占用，加一点延迟和重试
                time.sleep(1) # 短暂等待
                shutil.rmtree(self.profile_path, ignore_errors=False) # ignore_errors=False 以便记录可能的错误
                logger.info(f"WebDriver profile 目录已删除: {self.profile_path}")
            except PermissionError as e_perm:
                 logger.warning(f"删除 profile 目录 {self.profile_path} 失败：权限错误。可能仍被占用。 {e_perm}")
            except OSError as e_os:
                logger.warning(f"删除 profile 目录 {self.profile_path} 失败：OS错误。 {e_os}")
            except Exception as e:
                logger.error(f"清理 WebDriver profile 目录 {self.profile_path} 时发生未知错误: {e}", exc_info=True)
        else:
            logger.debug(f"Profile 目录 {self.profile_path} 未找到或未指定，无需清理。")

    def check_status(self, source: NewsSource, data_dir: str, db_path: str) -> Dict:
        """
        检查澎湃新闻源的状态。尝试初始化WebDriver并访问基础URL。
        """
        logger.info(f"开始检查澎湃新闻源 '{source.name}' ({source.url}) 的状态...")
        status_info = {
            "source_name": source.name,
            "success": False,
            "message": "检查未完成",
            "article_count": None, 
            "last_updated": None,
            "error_details": None
        }
        try:
            self._lazy_init_driver() # 使用配置的 data_dir 初始化
            if self.driver:
                self.driver.get(self.config.get("base_url", DEFAULT_PENGPAI_CONFIG["base_url"])) # 访问基础URL
                # 简单检查页面标题是否包含"澎湃"
                if "澎湃" in self.driver.title:
                    status_info["success"] = True
                    status_info["message"] = "状态良好，成功访问基础URL。"
                    logger.info(f"澎湃新闻源 '{source.name}' 状态良好。页面标题: {self.driver.title}")
                else:
                    status_info["message"] = f"可以访问基础URL，但页面标题 '{self.driver.title}' 未包含预期内容。"
                    logger.warning(f"澎湃新闻源 '{source.name}' 状态警告: {status_info['message']}")
            else:
                status_info["message"] = "WebDriver 初始化失败，无法检查状态。"
                status_info["error_details"] = "WebDriver instance is None after _lazy_init_driver."
                logger.error(f"澎湃新闻源 '{source.name}' 状态检查失败: {status_info['message']}")

        except TimeoutException:
            status_info["message"] = "访问澎湃新闻基础URL超时。"
            status_info["error_details"] = "TimeoutException occurred."
            logger.error(f"澎湃新闻源 '{source.name}' 状态检查失败: 超时。", exc_info=True)
        except WebDriverException as e_wd:
            status_info["message"] = f"WebDriver操作失败: {str(e_wd)[:100]}..."
            status_info["error_details"] = str(e_wd)
            logger.error(f"澎湃新闻源 '{source.name}' 状态检查失败: WebDriver错误。", exc_info=True)
        except Exception as e:
            status_info["message"] = f"检查状态时发生未知错误: {str(e)[:100]}..."
            status_info["error_details"] = str(e)
            logger.error(f"澎湃新闻源 '{source.name}' 状态检查失败: 未知错误。", exc_info=True)
        finally:
            # 状态检查后通常也保持 WebDriver 打开，以便后续采集复用
            # self.close() # 如果希望每次检查都独立，则取消注释
            logger.info(f"澎湃新闻源 '{source.name}' 状态检查完成。Success: {status_info['success']}, Message: {status_info['message']}")
        
        return status_info