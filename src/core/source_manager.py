# src/core/source_manager.py
import logging
import json # 导入 json 模块
from typing import List, Dict, Optional, Any # Added Any
from datetime import datetime # 添加 datetime 导入
# from PySide6.QtCore import QObject, Signal as pyqtSignal, QSettings, Qt # QSettings and Qt might be removable if not used elsewhere
from PySide6.QtCore import QObject, Signal as pyqtSignal, Qt # QSettings removed

# 导入 NewsSource 模型
from src.models import NewsSource
# 导入预设源获取函数
from src.collectors.default_sources import get_default_rss_sources
from src.storage.news_storage import NewsStorage # Import NewsStorage

logger = logging.getLogger('news_analyzer.core.source_manager')

class SourceManager(QObject):
    """负责管理新闻源配置的加载、保存和修改。"""

    sources_updated = pyqtSignal() # 新闻源列表发生变化

    # QSettings keys are no longer needed for main source config
    # ALL_SOURCES_CONFIG_KEY = "all_sources_config_v2" 
    # DELETED_SOURCES_KEY = "deleted_sources_list"

    # 特殊源的固定名称和类型 (Still relevant for identifying/creating defaults if needed)
    PENGPAI_NAME = "澎湃新闻"
    PENGPAI_TYPE = "pengpai"
    PENGPAI_CATEGORY_ID = "general" # 固定分类

    def __init__(self, storage: NewsStorage): # Inject NewsStorage
        super().__init__()
        self.logger = logging.getLogger(__name__) # +++ ADDED THIS LINE +++
        # self.settings = QSettings("NewsAnalyzer", "NewsAggregator") # QSettings might be removed
        self.storage = storage # Store NewsStorage instance
        self.news_sources: List[NewsSource] = []
        
        self._load_sources_from_db() # Load sources first
        
        # If, after loading from DB, the list of sources is empty,
        # it means the DB was empty or didn't exist in a way that sources could be loaded.
        # In this case, populate with default sources.
        if not self.news_sources:
            logger.debug("SourceManager: No news sources found after loading from DB. Populating with default sources.")
            self._ensure_default_sources_exist() # This method handles adding to DB and internal list, and should emit sources_updated if changes occur.
        else:
            # If sources were loaded from DB, we still need to emit to notify listeners.
            logger.debug(f"SourceManager: Successfully loaded {len(self.news_sources)} sources from existing database. Emitting sources_updated.")
            self.sources_updated.emit()

    # 辅助方法用于解析 ISO 时间字符串
    def _parse_iso_datetime(self, datetime_str: Optional[str], source_name_for_log: str) -> Optional[datetime]:
        """安全地将 ISO 格式字符串解析为 datetime 对象"""
        if not datetime_str:
            return None
        try:
            # Handle both string datetimes and already converted datetimes from DB (sqlite3.Row might auto-convert some)
            if isinstance(datetime_str, datetime):
                return datetime_str
            return datetime.fromisoformat(str(datetime_str).replace('Z', '+00:00'))
        except (ValueError, TypeError) as e: # Added TypeError
            logger.warning(f"SourceManager: 无法解析源 '{source_name_for_log}' 的 datetime: {datetime_str} ({type(datetime_str)}). Error: {e}")
            return None

    def _create_news_source_from_dict(self, source_dict: Dict[str, Any]) -> Optional[NewsSource]:
        """Helper to create NewsSource object from a dictionary (typically from DB)."""
        if not source_dict or not source_dict.get('name') or not source_dict.get('type'):
            logger.warning(f"SourceManager: Invalid source data for object creation: {source_dict}")
            return None
        
        custom_config_str = source_dict.get('custom_config')
        deserialized_custom_config = {}
        if custom_config_str and isinstance(custom_config_str, str):
            try:
                deserialized_custom_config = json.loads(custom_config_str)
            except json.JSONDecodeError:
                logger.error(f"Failed to deserialize custom_config for source '{source_dict.get('name')}': {custom_config_str}")
        elif isinstance(custom_config_str, dict): # If it's already a dict (e.g. from tests)
            deserialized_custom_config = custom_config_str
            
        # Fields like status, last_error, error_count, consecutive_error_count, notes, is_user_added
        # are not in the news_sources table in the DB.
        # They will be initialized to defaults in NewsSource dataclass or managed in memory.
        # For loading, we primarily care about what's in the DB.
        return NewsSource(
            id=source_dict.get('id'),
            name=source_dict['name'],
            type=source_dict['type'],
            url=source_dict.get('url'),
            category=source_dict.get('category_name', '未分类'), # DB stores as category_name
            enabled=bool(source_dict.get('is_enabled', True)),
            custom_config=deserialized_custom_config,
            last_checked_time=self._parse_iso_datetime(source_dict.get('last_checked_time'), source_dict.get('name', 'UnknownSource')),
            # Fields not in DB will get dataclass defaults:
            # is_user_added, last_update, error_count, last_error, status, notes, consecutive_error_count
            # --- CORRECTED: Load fields previously missed from DB dict ---
            status=source_dict.get('status', 'unchecked'),  # Load status, default to 'unchecked' if missing
            last_error=source_dict.get('last_error'),      # Load last_error
            consecutive_error_count=int(source_dict.get('consecutive_error_count', 0)), # Load consecutive_error_count, default 0
            # notes=source_dict.get('notes'), # Load notes if/when added to DB schema
            # is_user_added needs separate logic later based on defaults
            # error_count might be redundant if consecutive_error_count exists? Or maybe total? Keep default for now.
            # last_update seems related to fetching articles, not source status check. Keep default.
        )

    def _load_sources_from_db(self):
        """从数据库加载所有新闻源的配置。"""
        logger.debug("SourceManager: Loading news sources from database...")
        try:
            source_dicts_from_db = self.storage.get_all_news_sources()
            
            temp_sources_list: List[NewsSource] = []
            for s_dict in source_dicts_from_db:
                source_obj = self._create_news_source_from_dict(s_dict)
                if source_obj:
                    # For now, is_user_added can be inferred. If it's not a known default, it's user-added.
                    # This might need refinement if default sources can be modified and re-identified.
                    # A more robust way would be a dedicated column in DB or a clear naming convention.
                    # Simple check for now:
                    is_default_pengpai = source_obj.name == self.PENGPAI_NAME and source_obj.type == self.PENGPAI_TYPE
                    is_default_rss = any(
                        ds['name'] == source_obj.name and ds['url'] == source_obj.url 
                        for ds in get_default_rss_sources()
                    )
                    source_obj.is_user_added = not (is_default_pengpai or is_default_rss)
                    temp_sources_list.append(source_obj)
            
            self.news_sources = temp_sources_list
            self.news_sources.sort(key=lambda s: (s.type, s.name)) # Keep sorting

            logger.debug(f"SourceManager: Loaded {len(self.news_sources)} news sources from database.")

            # REMOVED: Optional: Ensure default sources exist if DB was empty or they were deleted
            # self._ensure_default_sources_exist() # This is now handled in __init__ based on DB creation state

            # self.sources_updated.emit() # Emit is now handled in __init__ after this method and potential default source addition
        except Exception as e:
            logger.error(f"SourceManager: Error loading news sources from database: {e}", exc_info=True)
            self.news_sources = [] # Ensure consistent state on error
            self.sources_updated.emit() # Emit even on error so UI can react

    def _ensure_default_sources_exist(self):
        """Checks if default sources are in the loaded list and adds them to DB if missing."""
        logger.debug("Ensuring default sources exist...")
        loaded_source_names = {s.name for s in self.news_sources}
        
        # Check Pengpai
        pengpai_exists_in_loaded = self.PENGPAI_NAME in loaded_source_names

        if not pengpai_exists_in_loaded: # Use the specific check
            logger.debug(f"Default source '{self.PENGPAI_NAME}' not found in DB. Adding it.")
            default_pengpai = NewsSource(
                name=self.PENGPAI_NAME,
                type=self.PENGPAI_TYPE,
                url="internal://pengpai", # Placeholder URL for Pengpai type
                category=self.PENGPAI_CATEGORY_ID,
                enabled=True,
                is_user_added=False
            )
            self.add_source(default_pengpai, _is_default_addition=True) # Internal flag to avoid double emit/sort

        # Check default RSS
        default_rss_sources_data = get_default_rss_sources()
        for default_data in default_rss_sources_data:
            if default_data['name'] not in loaded_source_names:
                logger.debug(f"Default RSS source '{default_data['name']}' not found in DB. Adding it.")
                rss_default = NewsSource(
                    name=default_data['name'],
                    type='rss',
                    url=default_data['url'],
                    category=default_data.get('category', '未分类'),
                    enabled=True,
                    is_user_added=False
                )
                self.add_source(rss_default, _is_default_addition=True)
        
        # If defaults were added, re-sort and emit
        if hasattr(self, '_defaults_added_flag') and self._defaults_added_flag:
            self.news_sources.sort(key=lambda s: (s.type, s.name))
            self.sources_updated.emit() # Emit once after all potential additions
            del self._defaults_added_flag

    def update_source_status_in_cache(self, source_id: int, status: str, 
                                      last_error: Optional[str], 
                                      last_checked_time: datetime):
        """Updates the status of a specific source in the memory cache and emits sources_updated."""
        found_source = None
        for src in self.news_sources:
            if src.id == source_id:
                found_source = src
                break
        
        if found_source:
            self.logger.debug(f"SourceManager: update_source_status_in_cache for ID {source_id} ('{found_source.name}'). Incoming status: '{status}', last_error: '{last_error}', last_checked: {last_checked_time}")
            found_source.status = status
            found_source.last_error = last_error
            found_source.last_checked_time = last_checked_time
            self.logger.debug(f"SourceManager: Updated status for source ID {source_id} ('{found_source.name}') in cache to '{found_source.status}'.")
        else:
            self.logger.warning(f"SourceManager: Source ID {source_id} not found in cache for status update.")

    # save_sources_config method is REMOVED. Persistence is handled by NewsStorage.

    def get_sources(self) -> List[NewsSource]:
        """获取所有新闻源的列表。"""
        return self.news_sources

    def add_source(self, source: NewsSource, _is_default_addition: bool = False): # Added internal flag
        """添加一个新的新闻源到数据库和内存列表。"""
        logger.debug(f"SourceManager: Attempting to add source '{source.name}'")
        if not source.name or not source.type:
            logger.error("SourceManager: Cannot add source, name or type is missing.")
            return None

        # Check for duplicates by name before adding to DB
        if any(s.name == source.name for s in self.news_sources):
            logger.warning(f"SourceManager: Source with name '{source.name}' already exists. Add operation cancelled.")
            # Optionally, could update if it's an attempt to re-add a default.
            # For user-added, this prevents duplicates.
            return None

        try:
            source_dict_for_db = source.to_storage_dict()
            # Remove 'id' if it's None, DB will autoincrement
            if source_dict_for_db.get('id') is None:
                del source_dict_for_db['id']
            
            new_id = self.storage.add_news_source(source_dict_for_db)
            
            # --- CORRECTED LOGIC: Only add to memory list IF DB add was successful --- 
            if new_id is not None:
                source.id = new_id # Update the model with the ID from DB
                self.news_sources.append(source) # Add to memory list only on success
                
                if not _is_default_addition: # Avoid multiple sorts/emits if called from _ensure_defaults
                    self.news_sources.sort(key=lambda s: (s.type, s.name))
                    self.sources_updated.emit()
                    logger.info(f"SourceManager: Successfully added source '{source.name}' with ID {new_id}.")
                else:
                    self._defaults_added_flag = True # Mark that a default was added
                    logger.debug(f"SourceManager: Successfully added default source '{source.name}' with ID {new_id} (no immediate emit/sort).")
                return source # Return the source object only on success
            else:
                logger.error(f"SourceManager: Failed to add source '{source.name}' to database (storage returned None ID).")
                return None # Return None if DB add failed
            # --- END CORRECTION --- 
        except Exception as e:
            logger.error(f"SourceManager: Error adding source '{source.name}': {e}", exc_info=True)
            return None # Return None on exception

    def remove_source(self, source_name: str):
        """从数据库和内存列表中移除指定名称的新闻源。"""
        logger.debug(f"SourceManager: Attempting to remove source '{source_name}'")
        source_to_remove = self.get_source_by_name(source_name)

        if source_to_remove and source_to_remove.id is not None:
            try:
                success = self.storage.delete_news_source(source_to_remove.id)
                if success:
                    self.news_sources.remove(source_to_remove)
                    self.sources_updated.emit()
                    logger.info(f"SourceManager: Successfully removed source '{source_name}' (ID: {source_to_remove.id}).")
                else:
                    logger.error(f"SourceManager: Failed to remove source '{source_name}' from database (storage returned False).")
            except Exception as e:
                logger.error(f"SourceManager: Error removing source '{source_name}': {e}", exc_info=True)
        elif source_to_remove:
            logger.warning(f"SourceManager: Source '{source_name}' found in memory but has no ID. Cannot remove from DB. Removing from memory only.")
            self.news_sources.remove(source_to_remove) # Remove from memory if it has no ID (should not happen with DB backend)
            self.sources_updated.emit()
        else:
            logger.warning(f"SourceManager: Source with name '{source_name}' not found for removal.")
            
    def update_source(self, source_name: str, updated_data: dict, emit_signal: bool = True):
        """更新指定名称的新闻源的配置。"""
        source_to_update = self.get_source_by_name(source_name)

        if source_to_update and source_to_update.id is not None:
            try:
                processed_data = updated_data.copy()

                if 'name' in processed_data:
                    new_name_candidate = str(processed_data['name']).strip()
                    if not new_name_candidate:
                        raise ValueError("新闻源名称不能为空")

                    is_different_name = new_name_candidate != source_to_update.name

                    # Check for conflict
                    conflict_exists = False
                    if is_different_name:
                        for s_iter in self.news_sources:
                            if s_iter is not source_to_update and s_iter.name == new_name_candidate:
                                conflict_exists = True
                                break
                    
                    if is_different_name and conflict_exists:
                        # 使用 f-string 构造更详细的错误信息
                        error_message = f"名称 '{new_name_candidate}' 已被其他源使用"
                        raise ValueError(error_message)
                    processed_data['name'] = new_name_candidate

                original_type = source_to_update.type
                original_url = source_to_update.url
                
                current_type = processed_data.get('type', original_type) # Use new type if provided, else original
                new_url_candidate = processed_data.get('url', None) # Get new URL if provided
                if new_url_candidate is not None:
                    new_url_candidate = str(new_url_candidate).strip()

                # Pengpai specific validation
                if source_to_update.name == self.PENGPAI_NAME:
                    attempted_type_change = 'type' in processed_data and processed_data['type'] != self.PENGPAI_TYPE
                    # URL change is attempted if new_url_candidate is not None (meaning 'url' was in processed_data), 
                    # and it's different from original_url, and it's not an attempt to set to empty.
                    attempted_url_change = new_url_candidate is not None and new_url_candidate != original_url and new_url_candidate != ""

                    if attempted_type_change and attempted_url_change:
                        # 同时尝试修改类型和URL，可以合并为一个错误，或者优先类型错误
                        raise ValueError("不能修改澎湃新闻的类型和URL") 
                    elif attempted_type_change:
                        raise ValueError("不能修改澎湃新闻源的类型。")
                    elif attempted_url_change:
                        raise ValueError("不能修改澎湃新闻源的URL。")

                # General RSS URL validation (if not Pengpai)
                # current_type here is the type that will be applied (either new or original if not changed)
                if current_type == 'rss' and source_to_update.name != self.PENGPAI_NAME:
                    if new_url_candidate is not None: # URL is being explicitly set or updated (was in processed_data)
                        if not new_url_candidate: # Explicitly set to empty
                            raise ValueError("RSS 源的 URL 不能为空") # Target
                        # Check for URL conflict only if URL is actually changing to a new, non-empty value        
                        if new_url_candidate != original_url and any(s.url == new_url_candidate and s is not source_to_update for s in self.news_sources if hasattr(s, 'url') and s.url):
                            error_message = f"URL '{new_url_candidate}' 已被其他 RSS 源使用"
                            raise ValueError(error_message) # Target
                    elif not original_url: # URL was not in processed_data, and original URL is empty for this RSS source
                        raise ValueError("RSS 源的 URL 不能为空") # Target
                
                # Ensure type and url are correctly in processed_data if they were part of input and validated
                if 'type' in processed_data:
                     processed_data['type'] = str(processed_data['type']).strip()
                if 'url' in processed_data and new_url_candidate is not None: # only if url was provided and processed
                     processed_data['url'] = new_url_candidate
                elif 'url' in processed_data and new_url_candidate is None: # url was key but value was None, strip to empty string
                     processed_data['url'] = ""

                # Process custom_config (ensure it's a dict or None)
                if 'custom_config' in processed_data:
                    custom_config_candidate = processed_data['custom_config']
                    if custom_config_candidate is not None and not isinstance(custom_config_candidate, dict):
                        try:
                            processed_data['custom_config'] = json.loads(custom_config_candidate)
                        except json.JSONDecodeError:
                            logger.error(f"SourceManager: Invalid JSON for custom_config for source '{source_name}': {custom_config_candidate}")
                            del processed_data['custom_config']

                # Apply updates to the NewsSource object in memory only if they cause a change
                has_changed = False
                for key, value in processed_data.items():
                    if hasattr(source_to_update, key):
                        old_value = getattr(source_to_update, key)
                        
                        value_to_set = None # Initialize to ensure it's assigned
                        if key == 'enabled' and isinstance(value, str):
                            value_to_set = value.lower() == 'true'
                        elif key == 'custom_config' and isinstance(value, str):
                            try:
                                value_to_set = json.loads(value)
                            except json.JSONDecodeError:
                                logger.error(f"Invalid JSON for custom_config for source '{source_name}': {value}")
                                continue # Skip update of this field if JSON is bad
                        elif key == 'category': # Specific handling for category
                            value_to_set = str(value).strip()
                            if not value_to_set:  # If empty after strip, default it
                                value_to_set = '未分类'
                        else:
                            value_to_set = value
                        
                        if old_value != value_to_set:
                            setattr(source_to_update, key, value_to_set)
                            has_changed = True
                    else:
                        logger.warning(f"SourceManager: Attempted to update non-existent attribute '{key}' on source '{source_name}'")
                
                if not has_changed:
                    logger.debug(f"SourceManager: No actual changes for source '{source_name}'. Update skipped.")
                    return

                # Now prepare the dictionary for storage
                storage_dict = source_to_update.to_storage_dict()
                # NewsStorage.update_news_source expects only the fields to be updated.
                # However, our current NewsStorage.update_news_source takes source_id and a full dict.
                # Let's adapt NewsStorage.update_news_source to take a partial dict, or send all fields from storage_dict.
                # For now, assume NewsStorage.update_news_source can handle a full dict of new values.
                
                # Filter storage_dict to only include fields present in the news_sources table schema
                # This is essentially what to_storage_dict() already does.
                # So, storage_dict from source_to_update.to_storage_dict() is what we pass.

                success = self.storage.update_news_source(source_to_update.id, storage_dict)
                
                if success:
                    if emit_signal:
                        self.sources_updated.emit()
                    logger.info(f"SourceManager: Successfully updated source '{source_name}' (ID: {source_to_update.id}).")
                else:
                    logger.error(f"SourceManager: Failed to update source '{source_name}' in database (storage returned False).")
            except ValueError as ve:  # Catch validation errors specifically
                # Log the validation error
                logger.error(f"SourceManager: Validation error updating source '{source_name}': {ve}")
                raise  # Re-raise the ValueError so it propagates
            except Exception as e:  # Catch other unexpected errors
                logger.error(f"SourceManager: Error updating source '{source_name}': {e}", exc_info=True)
        else:
            logger.warning(f"SourceManager: Source with name '{source_name}' not found for update or has no ID.")

    def get_source_by_name(self, name: str) -> Optional[NewsSource]:
        """按名称获取新闻源。"""
        for source in self.news_sources:
            if source.name == name:
                return source
        return None

    def get_source_by_id(self, source_id: int) -> Optional[NewsSource]:
        """按 ID 获取新闻源。"""
        if source_id is None: # 防御性检查
            self.logger.warning("SourceManager.get_source_by_id called with None ID.")
            return None
        for source in self.news_sources:
            if source.id == source_id:
                return source
        self.logger.warning(f"SourceManager.get_source_by_id: Source with ID {source_id} not found in cache.")
        return None

    def _load_sources_from_storage(self):
        self.news_sources.clear()
        try:
            sources_data = self.storage.get_all_news_sources()
            for data in sources_data:
                try:
                    source = NewsSource.from_dict(data)
                    self.news_sources.append(source)
                except Exception as e:
                    self.logger.error(f"Error converting DB data to NewsSource: {data}. Error: {e}")
        except Exception as e:
            self.logger.error(f"Failed to load sources from storage: {e}")

    # --- 添加数据库更新方法 ---
    def update_source_in_db(self, source_name: str, update_data: Dict) -> bool:
        """
        直接更新数据库中指定名称的新闻源记录。

        Args:
            source_name: 要更新的源名称。
            update_data: 包含要更新字段及其新值的字典。
                       例如: {'status': 'ok', 'last_checked_time': '...', 'last_error': None}

        Returns:
            bool: 更新是否成功。
        """
        self.logger.debug(f"SM_DEBUG: Attempting to update source '{source_name}' in DB with data: {update_data}")
        try:
            success = self.storage.update_news_source(source_name, update_data)
            if success:
                self.logger.debug(f"Source '{source_name}' updated successfully in DB.")
                # Optionally, update the in-memory object as well, though a full reload might be safer
                # or rely on the caller to update the in-memory object passed to it.
            else:
                self.logger.warning(f"Source '{source_name}' update in DB failed (storage returned False).")
            return success
        except Exception as e:
            self.logger.error(f"Error updating source '{source_name}' in DB: {e}", exc_info=True)
            return False
    # --- 数据库更新方法结束 ---