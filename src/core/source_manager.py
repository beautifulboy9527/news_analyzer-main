# src/core/source_manager.py
import logging
from typing import List, Dict, Optional
from PyQt5.QtCore import QObject, pyqtSignal, QSettings

# 导入 NewsSource 模型
from src.models import NewsSource
# 导入预设源获取函数
from src.collectors.default_sources import get_default_rss_sources

logger = logging.getLogger('news_analyzer.core.source_manager')

class SourceManager(QObject):
    """负责管理新闻源配置的加载、保存和修改。"""

    sources_updated = pyqtSignal() # 新闻源列表发生变化

    # QSettings keys
    USER_RSS_SOURCES_KEY = "user_rss_sources"
    PENGPAI_ENABLED_KEY = "source/pengpai_enabled"

    # 特殊源的固定名称和类型
    PENGPAI_NAME = "澎湃新闻"
    PENGPAI_TYPE = "pengpai"
    PENGPAI_CATEGORY_ID = "general" # 固定分类

    def __init__(self):
        super().__init__()
        self.settings = QSettings("NewsAnalyzer", "NewsAggregator")
        self.news_sources: List[NewsSource] = []
        self._load_sources_config() # 初始化时加载

    def _load_sources_config(self):
        """从 QSettings 加载新闻源列表，并合并预设源"""
        logger.info("SourceManager: 加载新闻源配置...")
        loaded_sources_dict: Dict[str, NewsSource] = {} # 使用字典去重，以名称为键
        user_source_urls = set()

        # 1. 加载用户添加的RSS源 (来自 QSettings)
        user_rss_sources_data = self.settings.value(self.USER_RSS_SOURCES_KEY, [])
        if isinstance(user_rss_sources_data, list):
            user_added_count = 0
            for data in user_rss_sources_data:
                if isinstance(data, dict) and 'url' in data and 'name' in data:
                    # 确保用户源名称不重复
                    if data['name'] not in loaded_sources_dict:
                        source = NewsSource(
                            name=data['name'],
                            type='rss',
                            url=data['url'],
                            category=data.get('category', '未分类'),
                            enabled=data.get('enabled', True),
                            is_user_added=True,
                            notes=data.get('notes')
                        )
                        loaded_sources_dict[source.name] = source
                        user_source_urls.add(source.url)
                        user_added_count += 1
                    else:
                         logger.warning(f"SourceManager: 加载用户源时发现重复名称 '{data['name']}'，已忽略。")
                else:
                     logger.warning(f"SourceManager: 无效的用户 RSS 源数据格式: {data}")
            logger.info(f"SourceManager: 从设置加载了 {user_added_count} 个有效的用户添加 RSS 源")

        # 2. 加载预设 RSS 源 (从 collectors.default_sources 获取)
        try:
            default_rss_sources_data = get_default_rss_sources()
            preset_rss_added_count = 0
            for data in default_rss_sources_data:
                # 检查是否与用户源冲突 (URL 或名称)
                url_exists = data['url'] in user_source_urls
                name_exists = data['name'] in loaded_sources_dict

                if not url_exists and not name_exists:
                    preset_source = NewsSource(
                        name=data['name'],
                        type='rss',
                        url=data['url'],
                        category=data.get('category', '未分类'),
                        enabled=True, # 预设默认启用
                        is_user_added=False
                    )
                    loaded_sources_dict[preset_source.name] = preset_source
                    preset_rss_added_count += 1
                else:
                    logger.debug(f"SourceManager: 跳过预设 RSS 源 '{data['name']}'，因为它与用户源冲突。")
            logger.info(f"SourceManager: 添加了 {preset_rss_added_count} 个预设 RSS 源")
        except Exception as e:
            logger.error(f"SourceManager: 加载或处理预设 RSS 源时出错: {e}", exc_info=True)

        # 3. 加载澎湃新闻源配置 (从 QSettings 读取启用状态)
        # 检查是否已存在同名用户源
        if self.PENGPAI_NAME not in loaded_sources_dict:
            pengpai_enabled = self.settings.value(self.PENGPAI_ENABLED_KEY, True, type=bool)
            pengpai_source = NewsSource(
                name=self.PENGPAI_NAME,
                type=self.PENGPAI_TYPE,
                enabled=pengpai_enabled,
                category=self.PENGPAI_CATEGORY_ID,
                is_user_added=False # 标记为非用户添加
            )
            loaded_sources_dict[pengpai_source.name] = pengpai_source
            logger.info(f"SourceManager: 添加了澎湃新闻源，启用状态: {pengpai_enabled}")
            logger.info(f"SourceManager: DEBUG - 澎湃新闻源 ('{pengpai_source.name}') 加载完成，启用状态: {pengpai_enabled}, 分类ID: {pengpai_source.category}") # DEBUG LOG
        else:
             logger.warning(f"SourceManager: 用户已添加同名源 '{self.PENGPAI_NAME}'，跳过添加内置澎湃源。")

        # 将字典值转换为列表并更新内部状态
        self.news_sources = list(loaded_sources_dict.values())
        # 可以选择排序，例如按类型再按名称
        self.news_sources.sort(key=lambda s: (s.type, s.name))

        logger.info(f"SourceManager: 加载完成，共 {len(self.news_sources)} 个新闻源")
        self.sources_updated.emit() # 加载完成后发射一次信号

    def _save_sources_config(self):
        """将新闻源配置保存到 QSettings"""
        logger.info("SourceManager: 保存新闻源配置...")

        user_rss_sources_data = []
        pengpai_enabled = True # 默认值

        for source in self.news_sources:
            # 只保存用户添加的 RSS 源到特定列表
            if source.type == 'rss' and source.is_user_added:
                user_rss_sources_data.append({
                    'name': source.name,
                    'url': source.url,
                    'category': source.category,
                    'enabled': source.enabled,
                    'is_user_added': True,
                    'notes': source.notes
                })
            # 保存澎湃新闻的启用状态（即使它是内置的）
            elif source.type == self.PENGPAI_TYPE and not source.is_user_added:
                 pengpai_enabled = source.enabled

        self.settings.setValue(self.USER_RSS_SOURCES_KEY, user_rss_sources_data)
        self.settings.setValue(self.PENGPAI_ENABLED_KEY, pengpai_enabled)

        logger.info(f"SourceManager: 保存了 {len(user_rss_sources_data)} 个用户 RSS 源和澎湃状态 ({pengpai_enabled})")
        logger.info("SourceManager: 新闻源配置已保存")

    def get_sources(self) -> List[NewsSource]:
        """获取所有新闻源配置的副本"""
        return list(self.news_sources) # 返回副本

    def add_source(self, source: NewsSource):
        """添加新的新闻源"""
        logger.info(f"SourceManager: 尝试添加新闻源: {source.name} ({source.type})")
        # 检查重复 (基于 URL 或 Name)
        if source.type == 'rss' and source.url and any(s.url == source.url for s in self.news_sources if s.type == 'rss' and s.url):
             logger.warning(f"SourceManager: 已存在相同 URL 的 RSS 源: {source.url}")
             raise ValueError(f"已存在相同 URL 的 RSS 源: {source.url}")
        if any(s.name == source.name for s in self.news_sources):
             logger.warning(f"SourceManager: 已存在相同名称的源: {source.name}")
             raise ValueError(f"已存在相同名称的源: {source.name}")

        # 确保新添加的源标记为用户添加
        source.is_user_added = True

        self.news_sources.append(source)
        self.news_sources.sort(key=lambda s: (s.type, s.name)) # 保持排序
        self._save_sources_config()
        self.sources_updated.emit()
        logger.info(f"SourceManager: 新闻源 '{source.name}' 已添加并发出信号")

    def remove_source(self, source_name: str):
        """移除指定名称的新闻源"""
        logger.info(f"SourceManager: 尝试移除新闻源: {source_name}")
        source_to_remove = next((s for s in self.news_sources if s.name == source_name), None)

        if source_to_remove:
            # 阻止删除内置的澎湃源（如果需要）
            if source_to_remove.type == self.PENGPAI_TYPE and not source_to_remove.is_user_added:
                 logger.warning(f"不允许直接删除内置的澎湃新闻源 '{source_name}'，请禁用它。")
                 raise ValueError("不能直接删除内置的澎湃新闻源，请禁用它。")

            self.news_sources.remove(source_to_remove)
            self._save_sources_config()
            self.sources_updated.emit()
            logger.info(f"SourceManager: 新闻源 '{source_name}' 已移除并发出信号")
        else:
            logger.warning(f"SourceManager: 未找到要移除的新闻源: {source_name}")

    def update_source(self, source_name: str, updated_data: dict):
        """更新指定新闻源的信息"""
        logger.info(f"SourceManager: 尝试更新新闻源 '{source_name}' 使用数据: {updated_data}")
        source = next((s for s in self.news_sources if s.name == source_name), None)
        if source:
            updated = False
            original_name = source.name # 保存原始名称以防名称被修改

            # 检查并应用更新
            is_builtin_pengpai = source.type == self.PENGPAI_TYPE and not source.is_user_added

            for key, value in updated_data.items():
                # 阻止修改内置澎湃源的类型或 URL
                if is_builtin_pengpai and key in ('type', 'url'):
                    logger.warning(f"SourceManager: 尝试修改内置澎湃源的受保护属性 '{key}'，已忽略。")
                    continue

                if not hasattr(source, key):
                    logger.warning(f"SourceManager: 尝试更新不存在的属性 '{key}' for source '{source_name}'")
                    continue

                current_value = getattr(source, key)

                # 特殊处理: 名称修改需要检查冲突
                if key == 'name' and value != current_value:
                    new_name = value.strip()
                    if not new_name:
                         logger.error("更新失败：新闻源名称不能为空。")
                         raise ValueError("新闻源名称不能为空。")
                    if any(s.name == new_name for s in self.news_sources if s.name != original_name):
                         logger.error(f"更新失败：名称 '{new_name}' 已被其他源使用。")
                         raise ValueError(f"名称 '{new_name}' 已被其他源使用。")
                    setattr(source, key, new_name)
                    updated = True
                    logger.info(f"SourceManager: 更新了 '{original_name}' 的属性 '{key}' 为 '{new_name}'")

                # 特殊处理: URL 修改需要检查冲突 (仅对 RSS)
                elif key == 'url' and source.type == 'rss' and value != current_value:
                    new_url = value.strip()
                    if not new_url:
                         logger.error("更新失败：RSS URL 不能为空。")
                         raise ValueError("RSS URL 不能为空。")
                    if any(s.url == new_url for s in self.news_sources if s.type == 'rss' and s.name != original_name):
                         logger.error(f"更新失败：URL '{new_url}' 已被其他 RSS 源使用。")
                         raise ValueError(f"URL '{new_url}' 已被其他 RSS 源使用。")
                    setattr(source, key, new_url)
                    updated = True
                    logger.info(f"SourceManager: 更新了 '{original_name}' 的属性 '{key}' 为 '{new_url}'")

                # 特殊处理: 分类不能为空
                elif key == 'category' and isinstance(value, str) and value.strip() == "":
                     if current_value != "未分类":
                          setattr(source, key, "未分类")
                          updated = True
                          logger.info(f"SourceManager: 更新了 '{original_name}' 的属性 '{key}' 为 '未分类'")
                # 其他属性直接比较和设置
                elif getattr(source, key) != value:
                    setattr(source, key, value)
                    updated = True
                    logger.info(f"SourceManager: 更新了 '{original_name}' 的属性 '{key}' 为 '{value}'")

            if updated:
                self.news_sources.sort(key=lambda s: (s.type, s.name)) # 如果名称或类型改变，重新排序
                self._save_sources_config()
                self.sources_updated.emit()
                logger.info(f"SourceManager: 新闻源 '{original_name}' (可能已重命名为 '{source.name}') 已更新并发出信号")
            else:
                logger.info(f"SourceManager: 新闻源 '{source_name}' 无需更新 (数据未改变)")
        else:
            logger.warning(f"SourceManager: 未找到要更新的新闻源: {source_name}")