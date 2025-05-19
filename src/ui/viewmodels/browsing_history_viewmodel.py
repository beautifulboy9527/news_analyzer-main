# src/ui/viewmodels/browsing_history_viewmodel.py
import logging
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from PySide6.QtCore import QObject, Signal, Slot, QAbstractListModel, Qt, QModelIndex
from datetime import datetime, timedelta

# Assuming a model for history entries exists, e.g., BrowsingHistoryEntry
# from src.models import BrowsingHistoryEntry # Adjust import as needed

if TYPE_CHECKING:
    from src.core.app_service import AppService
    from src.core.history_service import HistoryService

class BrowsingHistoryListModel(QAbstractListModel):
    def __init__(self, data: Optional[List[Dict[str, Any]]] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._data: List[Dict[str, Any]] = data if data is not None else []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._data)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None

        entry = self._data[index.row()]

        if role == Qt.DisplayRole:
            return entry.get('article_title', 'N/A')
        elif role == Qt.UserRole:
            return entry  # Return the whole dictionary
        return None

    def set_data_source(self, new_data: List[Dict[str, Any]]):
        """Updates the model's data and notifies views."""
        self.beginResetModel()
        self._data = new_data if new_data is not None else []
        self.endResetModel()

    def get_all_items(self) -> List[Dict[str, Any]]:
        """Returns all items currently in the model."""
        return self._data

    def get_item_id(self, row: int) -> Optional[Any]:
        """Returns the ID of the item at the given row."""
        if 0 <= row < len(self._data):
            # Assuming 'id' or 'link' can be used as an identifier.
            # Prefer 'id' if available, otherwise fall back to 'link'.
            # This needs to match what HistoryService.remove_history_item expects.
            item = self._data[row]
            if 'id' in item:
                return item.get('id')
            # Fallback, ensure this is a suitable ID for deletion if 'id' is not present.
            # The original log for delete_history_item_at_index in ViewModel
            # was trying to get 'history_item_id', implying a specific ID field.
            # If this is 'link', it should be fine, but clarity on ID field is best.
            return item.get('link') 
        return None

class BrowsingHistoryViewModel(QObject):
    """
    ViewModel for the Browsing History Panel.
    Handles loading, filtering, and potentially deleting browsing history entries.
    """
    history_changed = Signal() # Signal emitted when the history list changes
    error_occurred = Signal(str)
    history_loaded = Signal()
    news_detail_requested = Signal(int) # ADDED: Signal to request opening news detail by article_id

    def __init__(self, history_service: 'HistoryService', app_service: Optional['AppService'] = None, parent: Optional[QObject] = None):
        """Inject HistoryService"""
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self._history_service = history_service
        self._all_history: List[Dict] = [] # History items are likely dicts from storage
        self._filtered_history: List[Dict] = []
        self._filter_text: str = ""
        self._filter_days: int = 7 # Default filter: last 7 days
        self._model = BrowsingHistoryListModel(parent=self) # Pass parent if appropriate, or None

        # --- ADDED: Connect to HistoryService signal ---
        if self._history_service:
            try:
                self._history_service.browsing_history_updated.connect(self.load_history)
                self.logger.info("Successfully connected to HistoryService.browsing_history_updated signal.")
            except AttributeError:
                self.logger.error("Failed to connect to HistoryService.browsing_history_updated: signal not found. History might not auto-update.")
            except Exception as e:
                self.logger.error(f"Error connecting to HistoryService.browsing_history_updated: {e}", exc_info=True)
        else:
            self.logger.warning("HistoryService not provided, history will not auto-update.")
        # --- END ADDED ---

        # Initial load
        self.load_history()

    @Slot(result=QAbstractListModel)
    def get_model(self) -> QAbstractListModel:
        return self._model

    def load_history(self):
        """Loads browsing history from the HistoryService."""
        self.logger.info(f"Loading browsing history with filter_days: {self._filter_days}...") # Log filter_days
        try:
            if self._history_service:
                # MODIFIED: Call get_browsing_history on HistoryService instance and pass days_limit
                history_items_from_storage = self._history_service.get_browsing_history(days_limit=self._filter_days if self._filter_days > 0 else None)
            else:
                self.logger.warning("HistoryService is not available.")
                history_items_from_storage = []
            
            self._all_history = history_items_from_storage
            
            self.logger.info(f"Loaded {len(self._all_history)} history items from service based on days_limit.")
            self._apply_filters() # Apply further text filters if any, and update the model
            self.history_loaded.emit()

        except Exception as e:
            error_msg = f"加载浏览历史时发生错误: {e}"
            self.logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)

    def set_filter_text(self, text: str):
        """Sets the text filter."""
        self.logger.debug(f"Filter text set to: '{text}'")
        self._filter_text = text.lower().strip()
        self._apply_filters()

    def set_filter_days(self, days: int):
        """Sets the time range filter (in days). 0 means all time."""
        self.logger.debug(f"Filter days set to: {days}")
        self._filter_days = days
        self._apply_filters()

    def _apply_filters(self):
        """Filters the history based on current text and date filters."""
        # Start with all history loaded according to _filter_days from service
        temp_list = self._all_history 

        # Date filter is now primarily handled by the service call in load_history.
        # If _filter_days was 0 (all time), then _all_history contains all items.
        # If _filter_days > 0, _all_history is already pre-filtered by date.
        # However, if we want to be absolutely sure or allow dynamic changes without re-calling service,
        # we could re-apply date filter here. For now, assume service call is sufficient for date filter.
        
        # If _filter_days > 0 and we still want to refine (e.g. if service returned more than asked due to its own logic)
        # This part can be re-enabled if _all_history might contain items older than _filter_days
        # For now, assuming get_browsing_history respects days_limit strictly.
        # if self._filter_days > 0:
        #     try:
        #         cutoff_dt_aware = datetime.now() - timedelta(days=self._filter_days)
        #         def parse_history_time(ts_str_or_dt_obj):
        #             if isinstance(ts_str_or_dt_obj, datetime):
        #                 return ts_str_or_dt_obj.replace(tzinfo=None) if ts_str_or_dt_obj.tzinfo else ts_str_or_dt_obj
        #             if isinstance(ts_str_or_dt_obj, str):
        #                 try: 
        #                     dt_obj = datetime.fromisoformat(ts_str_or_dt_obj)
        #                     return dt_obj.replace(tzinfo=None) if dt_obj.tzinfo else dt_obj
        #                 except: return datetime.min
        #             return datetime.min
        #         temp_list = [entry for entry in temp_list
        #                      # MODIFIED: Use 'view_time' for date filtering
        #                      if parse_history_time(entry.get('view_time', datetime.min)) >= cutoff_dt_aware.replace(tzinfo=None)]
        #     except Exception as e:
        #         self.logger.warning(f"Error applying date filter in _apply_filters: {e}. Skipping date filter.", exc_info=True)

        # Apply text filter
        if self._filter_text:
            temp_list = [
                entry for entry in temp_list
                # MODIFIED: Use 'article_title' and 'article_link' for text filtering, matching NewsStorage.get_browsing_history
                if self._filter_text in entry.get('article_title', '').lower() or \
                   self._filter_text in entry.get('article_link', '').lower()
            ]

        self._filtered_history = temp_list
        self.logger.debug(f"Filtering applied. Displaying {len(self._filtered_history)} history entries.")
        self._model.set_data_source(self._filtered_history)
        self.history_changed.emit()

    # Note: Deletion methods are commented out as HistoryService doesn't support them yet.
    # If deletion is needed, it should be added to HistoryService first.

    # @pyqtSlot(list) # Expecting a list of IDs or entry objects to delete
    # def delete_history_entries(self, entries_to_delete: list):
    #     """Requests deletion of specific history entries."""
    #     pass # Requires HistoryService.delete_history_entries

    def clear_history(self):
        """Requests deletion of all browsing history."""
        self.logger.info("ViewModel: Requesting to clear all browsing history...")
        try:
            if self._history_service:
                # MODIFIED: Call clear_all_history_items as per HistoryService
                self._history_service.clear_all_history_items() 
                self.logger.info("ViewModel: Clear all browsing history successful (call made). Reloading...")
                self.load_history() # Reload data to update the view
            else:
                self.logger.warning("HistoryService is not initialized. Cannot clear browsing history.")
                self.error_occurred.emit("历史服务未初始化。无法清空浏览历史。")
        except AttributeError:
             self.logger.error("HistoryService does not have the 'clear_all_history_items' method. Feature not implemented in service layer.")
             self.error_occurred.emit("清空浏览历史功能尚未在服务层实现。")
        except Exception as e:
            self.logger.error(f"Error calling clear_history: {e}", exc_info=True)
            self.error_occurred.emit(f"清空浏览历史时发生意外错误: {e}")

    @Slot()
    def refresh_history(self):
        """Reloads history data from the service and updates the model."""
        self.logger.debug(f"BrowsingHistoryViewModel: Refreshing history with filter_days: {self._filter_days}...")
        if not self._history_service:
             self.logger.warning("Cannot refresh history: HistoryService not available.")
             return
        try:
            # MODIFIED: Pass days_limit to service call
            history_data = self._history_service.get_browsing_history(days_limit=self._filter_days if self._filter_days > 0 else None)
            self.logger.debug(f"Fetched {len(history_data)} history items from service for refresh.")
            
            self._all_history = history_data # Update the base list
            self._apply_filters() # Apply text filters and update model

            # self._model.set_data_source(history_data) # This was directly setting, now use _apply_filters
            self.logger.debug("History model updated after refresh and applying filters.")
        except Exception as e:
            self.logger.error(f"Error refreshing browsing history: {e}", exc_info=True)

    @Slot()
    def clear_all_history(self):
        """Requests the HistoryService to clear all history."""
        self.logger.debug("BrowsingHistoryViewModel: Clearing all history...")
        if not self._history_service:
             self.logger.warning("Cannot clear history: HistoryService not available.")
             return
        try:
            self._history_service.clear_browsing_history()
            # The history_updated signal connection will trigger refresh_history
        except Exception as e:
            self.logger.error(f"Error clearing browsing history: {e}", exc_info=True)

    @Slot(int) # Assuming index is passed from the view
    def delete_history_item_at_index(self, index: int):
        """Deletes the history item corresponding to the given model index."""
        self.logger.debug(f"BrowsingHistoryViewModel: Deleting history item at index {index}...")
        if not self._history_service:
            self.logger.warning("Cannot delete history item: HistoryService not available.")
            return
        
        history_item_id = self._model.get_item_id(index) # This should be the DB primary key of the history entry
        if history_item_id is None:
             self.logger.warning(f"Could not get valid history item DB ID for index {index}.")
             return

        self.logger.debug(f"Attempting to delete history item with DB ID: {history_item_id}")
        try:
            self._history_service.remove_history_item(str(history_item_id)) # remove_history_item expects string ID
            # history_updated signal from HistoryService should trigger load_history via connection
        except AttributeError:
             self.logger.error(f"HistoryService does not have the 'remove_history_item' method.")
        except Exception as e:
            self.logger.error(f"Error deleting history item (DB ID: {history_item_id}): {e}", exc_info=True)

    # ADDED: Slot to be called by the Panel when an item is double-clicked
    @Slot(int) # article_id from the history entry
    def request_news_detail_display(self, article_id: int):
        """Emits a signal to request the main application to display news detail."""
        self.logger.info(f"ViewModel: Received request to display news detail for article_id: {article_id}")
        self.news_detail_requested.emit(article_id)

    # Helper to potentially get the underlying data (might not be needed)
    def get_history_items(self) -> List[Dict[str, Any]]:
        return self._model.get_all_items() # Delegate to model