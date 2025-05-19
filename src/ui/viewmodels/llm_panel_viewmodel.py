import logging
from PySide6.QtCore import QObject, Signal as pyqtSignal, Slot as pyqtSlot, QThread # Use PySide6, alias Signal/Slot

from src.core.app_service import AppService
from src.llm.llm_service import LLMService
from src.models import NewsArticle


class LLMPanelViewModel(QObject):
    """
    ViewModel for the LLMPanel, handling LLM analysis logic and state.
    """
    # Signals to notify the View about state changes
    analysis_started = pyqtSignal()
    analysis_finished = pyqtSignal(object)  # 修改为object类型以支持字典
    analysis_error = pyqtSignal(str)    # Emits error message
    busy_changed = pyqtSignal(bool)     # Indicates if an analysis is in progress
    current_article_changed = pyqtSignal(object) # NEW: Emits the new article (or None)

    def __init__(self, app_service: AppService, llm_service: LLMService, parent=None):
        super().__init__(parent)
        self._app_service = app_service
        self._llm_service = llm_service
        self._current_article = None
        self._is_busy = False
        self._analysis_worker = None
        self.logger = logging.getLogger(__name__) # Add logger

        # Connect to relevant signals from services if needed
        # e.g., self._app_service.selected_news_changed.connect(self.set_current_article)

    @property
    def is_busy(self) -> bool:
        return self._is_busy

    def _set_busy(self, busy: bool):
        if self._is_busy != busy:
            self._is_busy = busy
            self.busy_changed.emit(busy)

    @pyqtSlot(NewsArticle)
    def set_current_article(self, article: NewsArticle | None):
        """Sets the currently selected article for analysis."""
        self._current_article = article
        self.logger.debug(f"Current article set in ViewModel: {article.title if article else 'None'}")
        # Potentially clear previous results or update UI state via signals
        # Also, update button enablement based on new article and busy state
        self.busy_changed.emit(self._is_busy) # Re-emit busy to trigger UI update
        self.current_article_changed.emit(self._current_article) # NEW: Emit article change

    @pyqtSlot(str)
    def perform_analysis(self, analysis_type: str):
        """Initiates an analysis task (e.g., 'summarize', 'deep_analyze')."""
        if self._is_busy or not self._current_article:
            # Maybe emit an error signal or log a warning
            self.logger.warning(f"Analysis requested for '{analysis_type}' but VM is busy ({self._is_busy}) or no article selected ({not self._current_article}).")
            return

        self._set_busy(True)
        self.analysis_started.emit()

        self.logger.info(f"Starting async analysis '{analysis_type}' for article: {self._current_article.title}")

        # Create and start the worker thread
        self._analysis_worker = LLMAnalysisWorker(
            self._llm_service,
            self._current_article,
            analysis_type
        )
        self._analysis_worker.analysis_complete.connect(self._handle_analysis_result)
        self._analysis_worker.analysis_error.connect(self._handle_analysis_error)
        # Connect finished signal to clean up the thread reference and reset busy state
        self._analysis_worker.finished.connect(self._handle_analysis_thread_finished)
        self._analysis_worker.start()

    @pyqtSlot(object)
    def _handle_analysis_result(self, result):
        """Handles the successful completion of the analysis thread."""
        self.logger.info("Analysis thread completed successfully.")
        self.analysis_finished.emit(result)
        self._set_busy(False)

    @pyqtSlot(str)
    def _handle_analysis_error(self, error_msg: str):
        """Handles errors from the analysis thread."""
        self.logger.error(f"Analysis thread failed: {error_msg}")
        self.analysis_error.emit(error_msg)
        self._set_busy(False)

    @pyqtSlot()
    def _handle_analysis_thread_finished(self):
        """Cleans up after the analysis thread finishes (success or error)."""
        self.logger.debug("Analysis thread finished signal received.")
        if self._analysis_worker:
            self._analysis_worker.deleteLater()
            self._analysis_worker = None
        self._set_busy(False)

# --- Add LLMAnalysisWorker class ---
class LLMAnalysisWorker(QThread):
    """Worker thread for performing LLM analysis."""
    analysis_complete = pyqtSignal(object)  # 修改为object类型以支持字典
    analysis_error = pyqtSignal(str)

    def __init__(self, llm_service: LLMService, article: NewsArticle, analysis_type: str, parent=None):
        super().__init__(parent)
        self._llm_service = llm_service
        self._article = article
        self._analysis_type = analysis_type
        self.logger = logging.getLogger(__name__) # Ensure logger is properly initialized for the class instance

    def run(self):
        self.logger.critical("--- LLMAnalysisWorker.run: METHOD ENTERED ---") 
        if not self._article:
            self.logger.error("--- LLMAnalysisWorker.run: No article, emitting error and exiting. ---")
            self.analysis_error.emit("No article provided to analysis worker.")
            self.logger.critical("--- LLMAnalysisWorker.run: METHOD EXITED (due to no article) ---")
            return

        self.logger.info(f"--- LLMAnalysisWorker.run: Worker thread started for '{self._analysis_type}' on article: {self._article.title[:100]} ---")
        result = None # Initialize result
        try:
            self.logger.debug("--- LLMAnalysisWorker.run: TRY BLOCK ENTERED, about to call LLMService.analyze_news --- ")
            result = self._llm_service.analyze_news(self._article, self._analysis_type)
            self.logger.critical(f"--- LLMAnalysisWorker.run: Result from LLMService.analyze_news (type: {type(result)}). First 700 chars: {str(result)[:700]} ---") # Increased length
            self.logger.info(f"--- LLMAnalysisWorker.run: Worker thread completed analysis for: {self._article.title[:100]} ---")
            if result is not None:
                self.analysis_complete.emit(result)
                self.logger.debug("--- LLMAnalysisWorker.run: analysis_complete emitted with result. ---")
            else:
                self.logger.error("--- LLMAnalysisWorker.run: Result from LLMService was None. Emitting error. ---")
                self.analysis_error.emit("LLMService returned None result.")
        except Exception as e:
            error_message = f"Error during analysis in worker thread: {e}"
            self.logger.error(f"--- LLMAnalysisWorker.run: EXCEPTION OCCURRED in try block: {error_message} ---", exc_info=True)
            self.analysis_error.emit(error_message)
        
        self.logger.critical("--- LLMAnalysisWorker.run: METHOD EXITED (normally or after exception) ---")