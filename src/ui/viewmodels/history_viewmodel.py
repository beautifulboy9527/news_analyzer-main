# -*- coding: utf-8 -*-
# src/ui/viewmodels/history_viewmodel.py
import logging
from typing import List, Dict, Optional
from PySide6.QtCore import QObject, Signal as pyqtSignal

from src.core.history_service import HistoryService # For browsing history
# Remove AnalysisStorageService import, AppService will be used
# from src.storage.analysis_storage_service import AnalysisStorageService
from src.core.app_service import AppService # Import AppService
# from src.storage.news_storage import NewsStorage # Or a dedicated analysis storage service

class HistoryViewModel(QObject):
    """ViewModel for the HistoryPanel.

    Handles fetching, filtering (optional), and managing deletion requests 
    for browsing history, analysis history, and chat history.
    """

    # --- Signals to update the View ---
    browse_history_changed = pyqtSignal(list)
    analysis_history_changed = pyqtSignal(list)
    chat_history_changed = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    request_reopen_news = pyqtSignal(str)

    def __init__(self, history_service: HistoryService,
                 app_service: AppService, # Replace analysis_storage_service with app_service
                 parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.history_service = history_service
        self.app_service = app_service # Store AppService instance

        self._browse_history: List[Dict] = []
        self._analysis_history: List[Dict] = []
        self._chat_history: List[Dict] = [] # Placeholder

        # +++ ADDED: Connect to HistoryService signal for automatic refresh +++
        if self.history_service and hasattr(self.history_service, 'browsing_history_updated'):
            self.history_service.browsing_history_updated.connect(self.load_browse_history)
            self.logger.debug("Connected to HistoryService.browsing_history_updated signal.")
        else:
            self.logger.warning("HistoryService not available or missing 'browsing_history_updated' signal during ViewModel init.")
        # +++ END ADDED +++

        # TODO: Connect signals from AppService if it emits them (e.g., on external changes)
        # For now, refresh will be manual or triggered by UI actions.

        self.logger.info("HistoryViewModel initialized.")

    # --- Load Methods ---
    def load_browse_history(self):
        self.logger.debug("Loading browsing history...")
        try:
            raw_from_service = self.history_service.get_all_history_items()
            current_history_items = raw_from_service
            self._browse_history = current_history_items 
            
            self.browse_history_changed.emit(current_history_items)
        except AttributeError as ae:
            self.logger.error(f"HistoryService might be missing or method not found: {ae}", exc_info=True)
            self.error_occurred.emit(f"加载浏览历史失败: {ae}")
        except Exception as e:
            self.logger.error(f"Error loading browse history: {e}", exc_info=True)
            self.error_occurred.emit(f"加载浏览历史时发生未知错误: {e}")

    def load_analysis_history(self):
        """Loads all LLM analysis history records via AppService."""
        self.logger.debug("Loading analysis history...")
        try:
            if not self.app_service:
                self.logger.error("AppService is not available.")
                self.error_occurred.emit("应用服务不可用 (分析历史)。")
                return
            # Assuming AppService will have a method like get_all_llm_analyses
            # For now, let's hardcode a limit/offset or get all
            # self._analysis_history = self.app_service.get_all_llm_analyses(limit=100, offset=0)
            self._analysis_history = self.app_service.get_all_llm_analyses() # Get all for now
            self.logger.info(f"Loaded {len(self._analysis_history)} analysis history items via AppService.")
            self.analysis_history_changed.emit(self._analysis_history)
        except Exception as e:
            self.logger.error(f"Error loading analysis history via AppService: {e}", exc_info=True)
            self.error_occurred.emit(f"加载分析历史时发生错误: {e}")

    def load_chat_history(self):
        self.logger.debug("Loading chat history (not implemented yet)...")
        # TODO: Implement chat history loading when feature is available
        self._chat_history = [] # Placeholder
        self.chat_history_changed.emit(self._chat_history)

    # --- Action Methods (Delete) ---
    def delete_browse_history_item(self, link: str):
        self.logger.debug(f"Request to delete browsing history for link: {link}")
        try:
            success = self.history_service.delete_history_entry(link)
            if success:
                self.logger.info(f"Successfully deleted browsing history for link: {link}")
                self.load_browse_history() # Refresh the list
            else:
                self.logger.warning(f"Failed to delete browsing history for link: {link}")
                self.error_occurred.emit("删除浏览记录失败。")
        except Exception as e:
            self.logger.error(f"Error deleting browse history item {link}: {e}", exc_info=True)
            self.error_occurred.emit(f"删除浏览记录时发生错误: {e}")

    def clear_browse_history(self):
        self.logger.debug("Request to clear all browsing history.")
        try:
            # Ideal: Call the method on HistoryService
            if hasattr(self.history_service, 'clear_browse_history'): # CORRECTED method name
                 if self.history_service.clear_browse_history():      # CORRECTED method call
                    self.logger.info("Successfully cleared all browsing history via HistoryService.")
                    self.load_browse_history() # Refresh the view
                 else:
                    self.logger.error("HistoryService.clear_browse_history reported failure.")
                    self.error_occurred.emit("清空浏览历史失败 (服务层报告失败)。") 
            # Fallback: Less ideal, direct to storage if HistoryService method is missing for some reason
            elif hasattr(self.history_service, 'storage') and hasattr(self.history_service.storage, 'clear_all_history'): 
                self.logger.warning("HistoryService missing 'clear_browse_history', attempting direct storage call 'clear_all_history'.")
                if self.history_service.storage.clear_all_history():
                    self.logger.info("Successfully cleared all browsing history via direct storage call.")
                    self.load_browse_history() # Refresh the list
                else:
                    self.logger.warning("Failed to clear all browsing history via direct storage call.")
                    self.error_occurred.emit("通过存储清空浏览历史失败。")
            else:
                self.logger.error("HistoryService and its storage lack a method to clear all browsing history.")
                self.error_occurred.emit("清空浏览历史功能所需的方法未在服务或存储层找到。")
        except Exception as e:
            self.logger.error(f"Error clearing browse history: {e}", exc_info=True)
            self.error_occurred.emit(f"清空浏览历史时发生意外错误: {e}")

    # TODO: Implement delete_analysis_item, clear_analysis_history
    # TODO: Implement delete_chat_item, clear_chat_history (when available)

    # +++ ADDED: Method to handle re-opening news +++
    def reopen_browse_item(self, link: str):
        """Emits a signal to request re-opening a news article."""
        if link:
            self.logger.debug(f"Request to reopen news item: {link}")
            self.request_reopen_news.emit(link)
        else:
            self.logger.warning("reopen_browse_item called with no link.")

    # --- Action/Deletion Methods for Analysis History --- ADDED
    def delete_analysis_history_item(self, analysis_id: str):
        """Deletes a specific analysis history item by its ID via AppService."""
        self.logger.debug(f"Request to delete analysis history for ID: {analysis_id}")
        try:
            if not self.app_service:
                self.logger.error("AppService is not available for analysis deletion.")
                self.error_occurred.emit("应用服务不可用。")
                return

            # Ensure analysis_id is int if it comes as string from UI/model
            try:
                analysis_id_int = int(analysis_id)
            except ValueError:
                self.logger.error(f"Invalid analysis_id format: {analysis_id}. Must be an integer.")
                self.error_occurred.emit(f"无效的分析记录ID格式: {analysis_id}")
                return

            success = self.app_service.delete_llm_analysis(analysis_id_int)
            if success:
                self.logger.info(f"Successfully requested deletion of analysis history for ID: {analysis_id_int}")
                self.load_analysis_history() # Refresh the list
            else:
                self.logger.warning(f"Failed to delete analysis history for ID: {analysis_id_int} (AppService returned False).")
                self.error_occurred.emit(f"删除分析记录 {analysis_id_int} 失败。")
        except Exception as e:
            self.logger.error(f"Error deleting analysis history item {analysis_id}: {e}", exc_info=True)
            self.error_occurred.emit(f"删除分析记录时发生错误: {e}")

    def clear_analysis_history(self):
        """Clears all analysis history records via AppService."""
        self.logger.debug("Request to clear all analysis history.")
        try:
            if not self.app_service:
                self.logger.error("AppService is not available for clearing analysis history.")
                self.error_occurred.emit("应用服务不可用。")
                return
            
            if self.app_service.delete_all_llm_analyses():
                self.logger.info("Successfully requested deletion of all analysis history via AppService.")
                self.load_analysis_history() # Refresh the list
            else:
                self.logger.warning("Failed to clear all analysis history (AppService returned False).")
                self.error_occurred.emit("清空分析历史失败。")
        except Exception as e:
            self.logger.error(f"Error clearing analysis history: {e}", exc_info=True)
            self.error_occurred.emit(f"清空分析历史时发生错误: {e}")
            
    def get_analysis_detail(self, analysis_id: str) -> Optional[Dict]:
        """Retrieves the full details of a specific analysis record via AppService."""
        self.logger.debug(f"Requesting details for analysis ID: {analysis_id}")
        try:
            if not self.app_service:
                self.logger.error("AppService is not available for getting analysis details.")
                self.error_occurred.emit("应用服务不可用。")
                return None

            try:
                analysis_id_int = int(analysis_id)
            except ValueError:
                self.logger.error(f"Invalid analysis_id format for detail view: {analysis_id}. Must be an integer.")
                self.error_occurred.emit(f"无效的分析记录ID格式: {analysis_id}")
                return None
                
            return self.app_service.get_llm_analysis_by_id(analysis_id_int)
        except Exception as e:
            self.logger.error(f"Error getting analysis detail for {analysis_id} via AppService: {e}", exc_info=True)
            self.error_occurred.emit(f"获取分析详情时发生错误: {e}")
            return None

    # --- Getters for View ---
    @property
    def browseHistory(self) -> List[Dict]:
        return self._browse_history

    @property
    def analysisHistory(self) -> List[Dict]:
        return self._analysis_history

    @property
    def chatHistory(self) -> List[Dict]:
        return self._chat_history 

    # --- General/Helper Methods ---
    def refresh_all_data(self):
        """Reloads data for all active history types."""
        self.logger.info("Refreshing all history data...")
        self.load_browse_history()
        self.load_analysis_history()
        self.load_chat_history() # Will emit empty for now 