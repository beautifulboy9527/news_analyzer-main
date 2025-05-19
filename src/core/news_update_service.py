"""
核心服务 - 新闻更新服务

负责处理新闻源的后台刷新、数据获取、解析和存储。
"""

import logging
import threading
import time
import os # +++ ADDED IMPORT +++
from typing import List, Dict, Optional, Callable, Any, Union
from datetime import datetime, timedelta, timezone # Added datetime imports AND timezone
from dateutil import parser as dateutil_parser # Added dateutil import
from PySide6.QtCore import QObject, Signal as pyqtSignal, Qt, Slot as pyqtSlot, QThreadPool, QRunnable, QMutex, QWaitCondition, QMutexLocker, QTimer, QEventLoop
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
import traceback # Import traceback

# 假设的导入路径，需要根据实际迁移调整
from src.models import NewsSource, NewsArticle
from src.storage.news_storage import NewsStorage
from src.core.source_manager import SourceManager
# 导入具体的 Collector 类型
from src.collectors import RSSCollector, PengpaiCollector # 确保导入
from src.collectors import CollectorFactory # +++ 添加此导入 +++
from src.collectors.categories import get_category_name # Import category helper
from src.core.cancellation_flag import CancellationFlag # Import CancellationFlag

# --- Custom Exception for Cancellation ---
class RefreshCancelledError(Exception):
    """Custom exception for explicitly cancelled refresh operations."""
    pass

# --- Worker Classes for QThreadPool ---

class RefreshWorker(QRunnable):
    """Worker thread for executing the refresh task."""
    def __init__(self, fn: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.logger = logging.getLogger('news_analyzer.core.refresh_worker')

    @pyqtSlot()
    def run(self):
        self.logger.debug(f"RefreshWorker starting task: {self.fn.__name__}")
        try:
            result = self.fn(self._progress_callback, *self.args[:-2]) # Pass all args except callbacks
            success_callback = self.args[-2]
            success_callback(result) # Call success callback with result
        except Exception as e:
            error_callback = self.args[-1]
            self.logger.error(f"RefreshWorker caught exception in task {self.fn.__name__}: {e}", exc_info=True)
            error_callback(e) # Call error callback with exception
        self.logger.debug(f"RefreshWorker finished task: {self.fn.__name__}")

    def _progress_callback(self, current, total):
        # This worker itself doesn't emit progress, the function 'fn' does
        pass

# --- 新增：单源状态检查 Worker ---
class RSSSingleStatusCheckWorker(QRunnable):
    """为单个 RSS 源执行状态检查的 QRunnable。"""
    # 信号定义
    class WorkerSignals(QObject):
        # 发射结果字典: {'source_name': str, 'success': bool, 'message': str, 'check_time': str, 'error_count': int}
        check_complete = pyqtSignal(dict)
        finished = pyqtSignal() # +++ ADDED finished signal +++
        # 信号定义结束

    def __init__(self, source: NewsSource, data_dir: str, db_name: str, rss_collector: RSSCollector): # +++ CORRECTED SIGNATURE: data_dir, db_name +++
        super().__init__()
        self.source = source
        self.data_dir = data_dir   # +++ STORED data_dir +++
        self.db_name = db_name     # +++ STORED db_name +++
        self.rss_collector = rss_collector
        self.logger = logging.getLogger(f"{__name__}.Worker.{source.name}")
        self.signals = self.WorkerSignals()
        self.thread_local_storage: Optional[NewsStorage] = None

    @pyqtSlot()
    def run(self):
        self.logger.info(f"开始检查源: {self.source.name} (DataDir: {self.data_dir}, DBName: {self.db_name})") # +++ CORRECTED Log +++
        success = False
        message = ""
        check_time_str = datetime.now().isoformat()
        error_count = self.source.consecutive_error_count or 0
        
        result_for_signal = { # Prepare result dict early for finally block
            'source_name': self.source.name,
            'success': False, # Default to False
            'message': "Worker execution started but did not complete normally.",
            'check_time': check_time_str,
            'error_count': error_count
        }

        try:
            # +++ CREATE THREAD-LOCAL STORAGE AND SOURCEMANAGER +++
            self.logger.debug(f"Worker {self.source.name}: Creating thread-local NewsStorage.")
            # +++ CORRECTED NewsStorage initialization +++
            self.thread_local_storage = NewsStorage(data_dir=self.data_dir, db_name=self.db_name) 
            self.logger.debug(f"Worker {self.source.name}: Creating thread-local SourceManager.")
            thread_local_source_manager = SourceManager(storage=self.thread_local_storage)
            # +++ END THREAD-LOCAL CREATION +++

            if self.source.type == 'rss':
                # Use the rss_collector instance passed from NewsUpdateService
                status_result = self.rss_collector.check_status(self.source)
                success = status_result.get('status') == 'ok'
                message = status_result.get('error') or ("Check OK" if success else "Check Failed") # Use error message from result
                check_time_str = status_result.get('last_checked_time', datetime.now()).isoformat() # Update check_time from result
            elif self.source.type == 'pengpai':
                success, message = True, "澎湃新闻源无需检查 (状态检查)" # Pengpai status check is trivial
            else:
                success, message = False, f"不支持的源类型: {self.source.type}"

            if success:
                error_count = 0
                self.logger.info(f"源 '{self.source.name}' 检查成功: {message}")
            else:
                error_count += 1
                self.logger.warning(f"源 '{self.source.name}' 检查失败 (第 {error_count} 次): {message}")

            update_data = {
                'last_checked_time': check_time_str,
                'status': 'ok' if success else 'error', # Store 'ok' or 'error'
                'last_error': None if success else message,
                'consecutive_error_count': error_count
            }
            
            self.logger.debug(f"Worker {self.source.name}: Attempting to update DB with data: {update_data}")
            # Use thread-local source_manager to update DB
            if not thread_local_source_manager.update_source_in_db(self.source.name, update_data):
                self.logger.error(f"将源 '{self.source.name}' 的状态更新到数据库失败！ (Worker)")
                # Even if DB update fails, the check itself might have succeeded/failed, reflect that in message
                message += " (DB update failed)" if success else f"; {message} (DB update also failed)"
                success = False # Consider DB update failure as overall failure for this status
            else:
                self.logger.info(f"源 '{self.source.name}' 的状态成功更新到数据库。")


        except Exception as e:
            success = False
            error_count += 1
            # Use the message derived from the initial check if available, else the exception string
            exception_message = f"检查源 '{self.source.name}' 时发生内部错误: {str(e)}"
            message = message if message and not success else exception_message # Prefer original failure message if check failed before exception
            self.logger.error(exception_message, exc_info=True)
            # Attempt to persist error status to DB
            try:
                if hasattr(self, 'thread_local_storage') and self.thread_local_storage and thread_local_source_manager: # Ensure it was created
                    update_data_on_error = {
                        'last_checked_time': check_time_str,
                        'status': 'error',
                        'last_error': message,
                        'consecutive_error_count': error_count
                    }
                    thread_local_source_manager.update_source_in_db(self.source.name, update_data_on_error)
            except Exception as db_e_on_error:
                self.logger.error(f"尝试在主错误处理中更新源 '{self.source.name}' 错误状态到数据库失败: {db_e_on_error}")
        finally:
            result_for_signal.update({
                'success': success,
                'message': message,
                'error_count': error_count,
                'check_time': check_time_str
            })
            self.signals.check_complete.emit(result_for_signal)
            self.signals.finished.emit() # +++ EMIT finished signal +++
            self.logger.info(f"完成检查源: {self.source.name}. 结果: success={success}, emitted finished signal.")
            if self.thread_local_storage:
                self.logger.debug(f"Worker {self.source.name}: Closing thread-local NewsStorage.")
                self.thread_local_storage.close()
# --- Worker 结束 ---

class NewsUpdateService(QObject):
    """
    负责后台获取和更新新闻数据。
    通过信号与主线程通信。
    使用线程池并发处理多个新闻源。
    """

    # --- Signals ---
    refresh_started = pyqtSignal() # 开始刷新
    # MODIFIED: Include source_name in news_refreshed signal
    news_refreshed = pyqtSignal(str, list) # 单个源刷新完成，发送 (source_name, news_items list)
    refresh_complete = pyqtSignal(bool, str) # 所有源刷新完成 (success: bool, message: str)
    source_status_checked = pyqtSignal(dict) # 单个源状态检查完成（成功或失败），附带结果
    sources_status_checked = pyqtSignal(list) # 所有源状态检查完成，附带所有结果列表
    status_message_updated = pyqtSignal(str) # 更新状态栏消息
    error_occurred = pyqtSignal(str, str) # (source_name, error_message)
    source_refresh_progress = pyqtSignal(str, int, int, int) # Added new signal for progress
    source_status_persisted_in_db = pyqtSignal(int, str, str, object) # 新增信号: source_id, status, error_message, last_checked_time (datetime)

    # +++ New Signals for overall status check lifecycle +++
    status_check_started = pyqtSignal()
    status_check_finished = pyqtSignal()

    # --- Initialization ---
    def __init__(self, storage: NewsStorage, source_manager: SourceManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"--- NewsUpdateService.__init__: id(self)={id(self)}, id(self.news_refreshed)={id(self.news_refreshed)} ---") # +++ 新增日志 +++
        self.storage = storage
        self.source_manager = source_manager
        self.collector_factory = CollectorFactory()
        self.thread_pool = QThreadPool.globalInstance() # Use global Qt thread pool
        self.logger.info(f"NewsUpdateService 使用最大线程数: {self.thread_pool.maxThreadCount()}")

        # --- State Variables ---
        self._is_refreshing = False # Flag to prevent concurrent refreshes
        self._is_checking_status = False # Flag for status checks
        self._refresh_mutex = QMutex() # Mutex for protecting _is_refreshing flag
        self._check_status_mutex = QMutex() # Mutex for protecting _is_checking_status
        self._cancel_refresh = CancellationFlag() # Cancellation flag for refresh tasks
        self._cancel_check_status = CancellationFlag() # Cancellation flag for check status tasks

    # --- Cancellation Handling ---
    def _check_if_cancelled(self, flag: CancellationFlag, operation_name: str = "操作") -> bool:
        """Helper to check the cancellation flag and log if cancelled."""
        if flag.is_set():
            self.logger.info(f"{operation_name} 已被取消。")
            return True
        return False

    def cancel_refresh(self):
        """Sets the cancellation flag for the current refresh operation."""
        if self._is_refreshing:
            self.logger.info("请求取消当前新闻刷新操作...")
            self._cancel_refresh.set()
        else:
            self.logger.info("没有正在进行的新闻刷新操作可取消。")

    def cancel_check_status(self):
        """Sets the cancellation flag for the current status check operation."""
        if self._is_checking_status:
            self.logger.info("请求取消当前源状态检查操作...")
            self._cancel_check_status.set()
        else:
            self.logger.info("没有正在进行的源状态检查操作可取消。")

    # --- Status Checking --- #
    @pyqtSlot()
    def check_all_sources_status(self):
        """(Public Slot) 检查所有已启用新闻源的在线状态。"""
        self.logger.info("NewsUpdateService: 请求检查所有新闻源状态...")
        if self._check_status_mutex.tryLock():
            try:
                if self._is_checking_status:
                    self.logger.info("NewsUpdateService: 状态检查已在进行中，本次请求忽略。")
                    return

                self._set_checking_status_flag(True) # Set flag
                self._cancel_check_status.clear() # Clear previous cancellation
                self.status_check_started.emit() # Emit overall start signal
                all_sources = self.source_manager.get_sources() # Get all sources
                enabled_rss_sources = [s for s in all_sources if s.enabled and s.type == 'rss'] 

                if not enabled_rss_sources: 
                    self.logger.info("没有启用的RSS新闻源可供检查状态。") 
                    self.status_check_finished.emit() 
                    self._set_checking_status_flag(False) 
                    return

                self.logger.info(f"将为 {len(enabled_rss_sources)} 个启用的RSS新闻源检查状态。") 
                
                sources_to_check_runnable = enabled_rss_sources 

                # Correctly access data_dir and derive db_name from NewsStorage instance
                data_dir_for_worker = self.storage.data_dir 
                db_name_for_worker = os.path.basename(self.storage.db_path)

                self.logger.debug(f"Data dir for StatusCheckRunnable: {data_dir_for_worker}")
                self.logger.debug(f"DB name for StatusCheckRunnable: {db_name_for_worker}")

                runnable = StatusCheckRunnable(
                    collector_factory=self.collector_factory, 
                    sources_to_check=sources_to_check_runnable, 
                    cancel_flag=self._cancel_check_status, 
                    source_status_checked_signal=self.source_status_checked, 
                    source_status_persisted_in_db_signal=self.source_status_persisted_in_db,
                    sources_status_checked_signal=self.sources_status_checked,
                    status_message_updated_signal=self.status_message_updated,
                    set_checking_status_flag_callback=self._set_checking_status_flag,
                    data_dir=data_dir_for_worker, # Pass correct data_dir
                    db_name=db_name_for_worker    # Pass correct db_name
                )
                self.thread_pool.start(runnable)
                
            finally:
                self._check_status_mutex.unlock()
        else:
            self.logger.info("NewsUpdateService: 无法获取状态检查互斥锁，可能已有操作在进行。")

    # Method to be passed to runnable to reset the flag upon completion/error
    def _set_checking_status_flag(self, checking: bool):
        """(Private) 设置状态检查标志，并根据需要释放互斥锁。"""
        self.logger.debug(f"_set_checking_status_flag called with: {checking}")
        previous_status = self._is_checking_status
        self._is_checking_status = checking
        if not checking and previous_status: # Only emit/unlock if it was previously checking and now it's not
            self.status_message_updated.emit("所有新闻源状态检查完成。")
            self.logger.info("NewsUpdateService: 所有源状态检查任务完成。释放互斥锁。")
            self._check_status_mutex.unlock()
            self.status_check_finished.emit() # +++ EMIT FINISH SIGNAL +++
        elif checking and not previous_status:
            # This case is handled when check_all_sources_status starts
            pass

    # --- News Refreshing --- #
    @pyqtSlot(list)
    @pyqtSlot()
    def refresh_all_sources(self, sources: Optional[List[NewsSource]] = None):
        """
        启动后台任务刷新所有启用或指定的新闻源。

        Args:
            sources: 可选，要刷新的特定 NewsSource 对象列表。如果为 None，则刷新所有启用的源。
        """
        self._refresh_mutex.lock()
        if self._is_refreshing:
            self.logger.warning("刷新操作已在进行中，忽略新的请求。")
            self._refresh_mutex.unlock()
            self.status_message_updated.emit("刷新正在进行中...") # Inform user
            return
        self._is_refreshing = True
        self._refresh_mutex.unlock()

        self.refresh_started.emit()
        self.logger.info("开始刷新新闻源...")
        self.status_message_updated.emit("准备刷新新闻源...")
        self._cancel_refresh.clear() # Clear cancellation flag before starting

        if sources is None:
            sources_to_refresh = [s for s in self.source_manager.get_sources() if s.enabled]
            self.logger.info(f"刷新所有启用的新闻源 ({len(sources_to_refresh)} 个)")
        else:
            sources_to_refresh = sources
            self.logger.info(f"刷新指定的 {len(sources_to_refresh)} 个新闻源")

        if not sources_to_refresh:
            self.logger.info("没有要刷新的新闻源。")
            # Ensure the flag is reset and completion signal is emitted
            self._set_refreshing_flag(False)
            self.refresh_complete.emit(True, "没有启用的新闻源可刷新。")
            self.status_message_updated.emit("没有启用的新闻源。")
            return

        # Use QRunnable for the background refresh task
        runnable = RefreshRunnable(
            collector_factory=self.collector_factory,
            sources_to_refresh=sources_to_refresh,
            cancel_flag=self._cancel_refresh,
            news_refreshed_signal=self.news_refreshed, # Pass the modified signal
            refresh_complete_signal=self.refresh_complete,
            status_message_updated_signal=self.status_message_updated,
            source_refresh_progress_signal=self.source_refresh_progress, # +++ PASS THE PROGRESS SIGNAL +++
            error_occurred_signal=self.error_occurred,
            set_refreshing_flag_callback=self._set_refreshing_flag
        )
        self.thread_pool.start(runnable)

    # Method to be passed to runnable to reset the flag upon completion/error
    def _set_refreshing_flag(self, status: bool):
        self._refresh_mutex.lock()
        self._is_refreshing = status
        self._refresh_mutex.unlock()
        self.logger.debug(f"刷新标志已设置为: {status}")

# === QRunnables for Background Tasks ===

class RefreshRunnable(QRunnable):
    """QRunnable to handle the concurrent fetching of news sources."""
    def __init__(self, collector_factory, sources_to_refresh, cancel_flag,
                 news_refreshed_signal, refresh_complete_signal,
                 status_message_updated_signal, source_refresh_progress_signal, # +++ ADD progress_signal PARAM +++
                 error_occurred_signal,
                 set_refreshing_flag_callback):
        super().__init__()
        self.logger = logging.getLogger(__name__ + ".RefreshRunnable")
        self.logger.info(f"--- RefreshRunnable.__init__: id(news_refreshed_signal)={id(news_refreshed_signal)} ---") # +++ 新增日志 +++
        self.collector_factory = collector_factory
        self.sources_to_refresh = sources_to_refresh
        self.cancel_flag = cancel_flag
        self.news_refreshed = news_refreshed_signal
        self.source_refresh_progress = source_refresh_progress_signal # +++ STORE the progress signal +++
        self.logger.info(f"--- RefreshRunnable.__init__: id(self.news_refreshed) AFTER assignment={id(self.news_refreshed)} ---") # +++ 新增日志 +++
        self.refresh_complete = refresh_complete_signal
        self.status_message_updated = status_message_updated_signal
        self.error_occurred = error_occurred_signal
        self.set_refreshing_flag = set_refreshing_flag_callback
        self.setAutoDelete(True) # Auto delete when done

    def _check_if_cancelled(self, operation_name: str = "操作") -> bool:
        """Helper to check the cancellation flag and log if cancelled."""
        if self.cancel_flag.is_set():
            self.logger.info(f"{operation_name} 已被取消 (来自 RefreshRunnable)。")
            return True
        return False

    @pyqtSlot()
    def run(self):
        """Executes the refresh logic in a background thread."""
        self.logger.info(f"RefreshRunnable: 开始执行新闻刷新 for {len(self.sources_to_refresh)} sources...")
        self.status_message_updated.emit(f"正在刷新 {len(self.sources_to_refresh)} 个新闻源...")

        success = True
        all_errors: List[str] = []
        futures: Dict[Future, NewsSource] = {}
        total_collected = 0

        # Let's use a slightly simpler logic for now, or make it configurable
        # For IO bound tasks, more threads can be beneficial.
        # Max workers should not exceed number of sources for this specific task.
        num_sources = len(self.sources_to_refresh)
        # Max 8 workers, but no more than number of sources, and at least 1.
        max_workers = min(max(1, num_sources), 8) # Limit to 8, or fewer if not many sources.

        try:
            self.logger.info(f"RefreshRunnable: 使用 {max_workers} 个工作线程进行并发获取。")

            # Using ThreadPoolExecutor for managing futures and collecting results
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                self.logger.debug(f"RefreshRunnable: ThreadPoolExecutor created with {max_workers} workers.")
                for source_config in self.sources_to_refresh:
                    if self._check_if_cancelled(f"提交任务 for {source_config.name}"):
                        self.logger.info(f"RefreshRunnable: 取消提交任务 for source: {source_config.name}")
                        all_errors.append(f"{source_config.name}: Refresh cancelled before submission")
                        continue

                    collector = self.collector_factory.get_collector(source_config.type)
                    if collector:
                        self.logger.debug(f"RefreshRunnable: 提交任务 for source: {source_config.name}")
                        
                        # --- 定义 progress_callback ---
                        def _local_progress_callback(current_item: int, total_items: int):
                            if self.source_refresh_progress:
                                # 这里我们可能需要一个总体的进度，而不仅仅是单个源内部的进度。
                                # 这个回调是给单个collector用的，它报告 (当前条目, 此collector的总条目)
                                # 我们需要将其转换为相对于所有源的总进度，或者让MainWindow处理单个源的进度。
                                # 暂时，我们让MainWindow处理单个源的详细进度，如果它想的话。
                                # 我们先传递源名称，当前项，总项。 MainWindow可以决定如何显示。
                                # 主进度条的更新在 for future in as_completed(futures) 循环中处理。
                                # 这个回调主要是为了让collector内部可以报告其更细致的进度。
                                # self.logger.debug(f"RefreshRunnable: _local_progress_callback for '{source_config.name}': {current_item}/{total_items}")
                                # 我们在此处不直接发射 self.source_refresh_progress，因为那个是整体进度。
                                # collector 的 progress_callback 应该影响一个更细粒度的进度展示（如果UI支持）。
                                # 暂时，由于collector的progress_callback签名是 (int, int)，我们无法直接传递源名称。
                                # 除非我们修改BaseCollector的progress_callback签名。
                                # 为简单起见，暂时不从这里发射主进度信号，只将回调传递给collector。
                                pass

                        # Pass the cancel_checker function directly and the new progress_callback
                        future = executor.submit(
                            collector.collect, 
                            source_config, 
                            progress_callback=_local_progress_callback, # Pass the new callback
                            cancel_checker=lambda: self.cancel_flag.is_set()
                        )
                        futures[future] = source_config # Map future back to source
                    else:
                        error_msg = f"未找到适用于类型 '{source_config.type}' 的收集器 (源: {source_config.name})"
                        self.logger.error(error_msg)
                        all_errors.append(f"{source_config.name}: {error_msg}")
                        # MODIFIED: Emit empty list for sources with no collector
                        self.logger.info(f"--- RefreshRunnable.run (no collector): id(self.news_refreshed)={id(self.news_refreshed)} ---") # +++ 新增日志 +++
                        self.news_refreshed.emit(source_config.name, [])
                        self.error_occurred.emit(source_config.name, error_msg)


                self.logger.info(f"RefreshRunnable: 已提交 {len(futures)} 个任务，等待完成...")
                processed_sources_count = 0
                total_sources_to_process = len(futures) # Only count those successfully submitted

                for future in as_completed(futures):
                    source_config = futures[future]
                    source_name = source_config.name
                    processed_sources_count += 1
                    
                    # Emit progress to main UI or AppService
                    current_progress_percentage = int((processed_sources_count / total_sources_to_process) * 100) if total_sources_to_process > 0 else 0
                    if self.source_refresh_progress: # +++ CHECK IF SIGNAL EXISTS +++
                        self.logger.debug(f"RefreshRunnable: Emitting source_refresh_progress for \'{source_name}\': {current_progress_percentage}%, processed {processed_sources_count}/{total_sources_to_process}")
                        self.source_refresh_progress.emit(source_name, current_progress_percentage, total_sources_to_process, processed_sources_count)
                    
                    self.status_message_updated.emit(f"正在刷新: {source_name} ({processed_sources_count}/{total_sources_to_process})...")


                    if self._check_if_cancelled(f"处理结果 for {source_name}"):
                        self.logger.info(f"RefreshRunnable: 取消处理结果 for source: {source_name}")
                        all_errors.append(f"{source_name}: Refresh cancelled during processing")
                        # MODIFIED: Emit empty list for cancelled sources
                        self.logger.info(f"--- RefreshRunnable.run (cancelled during processing): id(self.news_refreshed)={id(self.news_refreshed)} ---") # +++ 新增日志 +++
                        self.news_refreshed.emit(source_name, [])
                        continue

                    try:
                        # Get the result (list of dicts) or raise exception if task failed
                        raw_news_items = future.result() 
                        
                        if raw_news_items is None: # Collector might return None on certain failures
                            self.logger.warning(f"RefreshRunnable: '{source_name}' 返回了 None，视为空列表。")
                            raw_news_items = [] # Treat as empty list

                        self.logger.info(f"RefreshRunnable: '{source_name}' 获取了 {len(raw_news_items)} 条新闻。")
                        total_collected += len(raw_news_items)
                        # MODIFIED: Emit signal with source_name and items
                        self.logger.info(f"--- RefreshRunnable.run (before emit): id(self.news_refreshed)={id(self.news_refreshed)} for source {source_name} ---") # +++ 新增日志 +++
                        self.news_refreshed.emit(source_name, raw_news_items)

                    except RefreshCancelledError: # Catch specific cancellation from collector
                        self.logger.info(f"RefreshRunnable: 源 '{source_name}' 的刷新被其收集器内部取消。")
                        all_errors.append(f"{source_name}: Collector internally cancelled")
                        self.logger.info(f"--- RefreshRunnable.run (collector cancelled): id(self.news_refreshed)={id(self.news_refreshed)} ---") # +++ 新增日志 +++
                        self.news_refreshed.emit(source_name, []) # Emit empty for cancelled
                    except Exception as exc:
                        error_message = f"RefreshRunnable: 获取源 '{source_name}' 新闻时出错: {exc}"
                        self.logger.error(error_message, exc_info=True) # Log with traceback
                        all_errors.append(f"{source_name}: {type(exc).__name__}: {exc}")
                        # MODIFIED: Emit empty list for failed sources to signal processing completion
                        self.logger.info(f"--- RefreshRunnable.run (exception during future.result): id(self.news_refreshed)={id(self.news_refreshed)} ---") # +++ 新增日志 +++
                        self.news_refreshed.emit(source_name, [])
                        self.error_occurred.emit(source_name, str(exc))


        except Exception as e: # Catch errors during executor setup/shutdown
            self.logger.error(f"RefreshRunnable: 线程池执行期间发生意外错误: {e}", exc_info=True)
            success = False
            all_errors.append(f"并发执行错误: {e}")

        finally:
            # --- Final Report --- #
            final_message = f"刷新完成 ({total_collected} 条新条目)。"
            if not success:
                 if self.cancel_flag.is_set():
                     final_message = "刷新操作被用户取消。"
                 else:
                     final_message = f"刷新完成，但出现错误: {'; '.join(all_errors)}"
                     self.logger.warning(f"RefreshRunnable: 刷新完成，但存在错误: {all_errors}")
            else:
                 self.logger.info(f"RefreshRunnable: 所有新闻源刷新成功，共获取 {total_collected} 条。")

            self.refresh_complete.emit(success, final_message)
            self.status_message_updated.emit(final_message) # Update status bar

            # --- Reset Flag --- #
            self.logger.info("RefreshRunnable: 刷新任务完成，重置刷新标志。")
            self.set_refreshing_flag(False) # Use the callback to reset the flag


class StatusCheckRunnable(QRunnable):
    """所有源状态检查的 QRunnable。"""

    def __init__(self, collector_factory, sources_to_check, cancel_flag,
                 source_status_checked_signal, # This is NewsUpdateService.source_status_checked
                 source_status_persisted_in_db_signal, # This is NewsUpdateService.source_status_persisted_in_db
                 sources_status_checked_signal, # This is NewsUpdateService.sources_status_checked
                 status_message_updated_signal, set_checking_status_flag_callback,
                 data_dir: str, db_name: str): # Added data_dir and db_name
        super().__init__()
        self.collector_factory = collector_factory
        self.sources_to_check: List[NewsSource] = sources_to_check
        self.cancel_flag = cancel_flag
        self.status_signal = source_status_checked_signal # Renaming for clarity within this class
        self.status_persisted_signal = source_status_persisted_in_db_signal # Store the new signal
        self.all_statuses_checked_signal = sources_status_checked_signal
        self.status_message_updated_signal = status_message_updated_signal
        self.set_checking_status_flag_callback = set_checking_status_flag_callback
        self.logger = logging.getLogger(f"{__name__}.StatusCheckRunnable")
        self.data_dir = data_dir # Store data_dir
        self.db_name = db_name   # Store db_name
        # 每个线程需要自己的 NewsStorage 实例，因为 SQLite 连接不能跨线程共享
        # 这里假设 NewsStorage 的初始化可以不依赖 QSettings (如果它依赖，则需要传递 config)
        # 也需要传递 data_dir 和 db_name
        # IMPORTANT: This worker does NOT create its own NewsStorage.
        # It relies on its caller (NewsUpdateService) to provide thread-safe DB access
        # or for the NewsStorage methods themselves to be thread-safe.
        # For now, we will assume NewsStorage methods are thread-safe or we pass a new instance.
        # Let's assume NewsUpdateService.storage can be used if methods are thread-safe.
        # For SQLite, it's better to create a new connection per thread.
        # We will pass the necessary info to create a new NewsStorage instance.
        # This will be handled if NewsStorage is called directly.
        # If SourceManager is used, it needs its own NewsStorage.
        # For now, direct NewsStorage calls for status update.

    @pyqtSlot()
    def run(self):
        self.logger.info(f"StatusCheckRunnable: 开始检查 {len(self.sources_to_check)} 个源的状态。")
        results = []
        processed_count = 0

        # Create a single NewsStorage instance for this thread using the passed data_dir and db_name
        thread_local_storage = NewsStorage(data_dir=self.data_dir, db_name=self.db_name)

        for source in self.sources_to_check:
            if self.cancel_flag.is_set():
                self.logger.info("StatusCheckRunnable: 检测到取消信号，停止提交任务。")
                break
            
            collector = self.collector_factory.get_collector(source.type)
            status_result: Dict[str, Any] = {} # Ensure status_result is always a dict

            current_error_count = source.consecutive_error_count or 0

            if not collector:
                self.logger.warning(f"源 '{source.name}' 的收集器类型 '{source.type}' 未找到，跳过状态检查。")
                status_result = {
                    'source_name': source.name,
                    'status': 'error',
                    'error': f'收集器类型 {source.type} 未找到',
                    'last_checked_time': datetime.now(timezone.utc) # Use datetime object directly
                }
                current_error_count += 1
            elif not hasattr(collector, 'check_status'):
                self.logger.warning(f"源 '{source.name}' 的收集器不支持状态检查，跳过。")
                status_result = {
                    'source_name': source.name,
                    'status': 'error',
                    'error': '收集器不支持状态检查',
                    'last_checked_time': datetime.now(timezone.utc) # Use datetime object directly
                }
                current_error_count += 1
            else:
                try:
                    self.logger.debug(f"StatusCheckRunnable: 检查源 '{source.name}'")
                    status_result = collector.check_status(source)
                    # Ensure last_checked_time from collector is datetime
                    lc_time = status_result.get('last_checked_time')
                    if isinstance(lc_time, str):
                        status_result['last_checked_time'] = dateutil_parser.isoparse(lc_time)
                    elif not isinstance(lc_time, datetime): # If None or other types, set to now
                        status_result['last_checked_time'] = datetime.now(timezone.utc)
                    
                    if status_result.get('status') == 'ok':
                        current_error_count = 0
                    else:
                        current_error_count += 1

                except Exception as e:
                    self.logger.error(f"检查源 '{source.name}' 状态时发生错误: {e}", exc_info=True)
                    status_result = {
                        'source_name': source.name,
                        'status': 'error',
                        'error': f'检查时发生内部错误: {str(e)}',
                        'last_checked_time': datetime.now(timezone.utc) # Use datetime object
                    }
                    current_error_count += 1
            
            results.append(status_result) # status_result is always defined
            
            # Persist to DB using the thread_local_storage
            source_id_to_update = source.id
            status_val = status_result.get('status', 'error') # Default to 'error'
            error_msg = status_result.get('error')
            last_checked_val = status_result.get('last_checked_time', datetime.now(timezone.utc))

            # Ensure last_checked_val is a datetime object
            if isinstance(last_checked_val, str):
                try:
                    last_checked_dt = dateutil_parser.isoparse(last_checked_val)
                except ValueError:
                    last_checked_dt = datetime.now(timezone.utc)
            elif isinstance(last_checked_val, datetime):
                last_checked_dt = last_checked_val
            else: # Fallback if it's neither string nor datetime
                last_checked_dt = datetime.now(timezone.utc)

            # Prepare data for DB update
            db_update_payload = {
                'status': status_val,
                'last_error': error_msg,
                'last_checked_time': last_checked_dt.isoformat(), # Store as ISO string
                'consecutive_error_count': current_error_count
            }

            if source_id_to_update is not None:
                try:
                    # MODIFIED: Call update_news_source instead of update_news_source_status
                    success_db_update = thread_local_storage.update_news_source(
                        source_id_or_name=source_id_to_update, # Pass ID
                        update_data=db_update_payload
                    )
                    if success_db_update:
                        self.logger.info(f"StatusCheckRunnable: 源 '{source.name}' (ID: {source_id_to_update}) 状态已更新到数据库: {db_update_payload}")
                        # Emit the new signal after successful DB update
                        # Pass the datetime object for the signal, not the ISO string
                        self.status_persisted_signal.emit(source_id_to_update, status_val, error_msg, last_checked_dt)
                    else:
                        self.logger.error(f"StatusCheckRunnable: 更新源 '{source.name}' (ID: {source_id_to_update}) 状态到数据库失败 (update_news_source returned False). Payload: {db_update_payload}")
                        status_result['error'] = (status_result.get('error') or "") + " (DB update failed: method returned False)"
                        status_result['status'] = 'error'


                except Exception as db_exc:
                    self.logger.error(f"StatusCheckRunnable: 更新源 '{source.name}' (ID: {source_id_to_update}) 状态到数据库时发生异常: {db_exc}", exc_info=True)
                    status_result['error'] = (status_result.get('error') or "") + f" (DB update exception: {db_exc})"
                    status_result['status'] = 'error' # Consider DB update failure as overall error

            # Emit signal for individual source check completion (for immediate UI update)
            # Ensure the emitted status_result reflects any DB update failures
            final_emit_result = {
                'source_name': source.name, # Ensure source_name is present
                'status': status_result.get('status', 'error'),
                'error': status_result.get('error'),
                'last_checked_time': last_checked_dt, # Emit datetime object
                'consecutive_error_count': current_error_count # Emit current error count
            }
            self.status_signal.emit(final_emit_result)

            processed_count += 1

        self.logger.info(f"StatusCheckRunnable: 所有源状态检查完成。共处理 {processed_count} 个源。")
        self.all_statuses_checked_signal.emit(results)
        self.set_checking_status_flag_callback(False)
        if thread_local_storage:
            thread_local_storage.close()

    # --- 新闻刷新相关方法 (保持不变) --- 
    @pyqtSlot()
    def refresh_all_news(self):
        """【入口】刷新所有启用的新闻源。"""
        # ... existing code ...

    def _do_refresh_news(self, sources_to_refresh: List[NewsSource], 
                         progress_callback: callable, 
                         completion_callback: callable, 
                         error_callback: callable):
        """在后台线程中执行新闻刷新。"""
        # ... existing code ...

    def _update_source_after_fetch(self, source: NewsSource, fetch_success: bool, article_count: int):
        """更新新闻源的最后更新时间和错误计数 (抓取后)。"""
        # ... existing code ...

    # --- LLM 相关方法 (保持不变) --- 
    def start_analyze_news_task(self, articles: List[NewsArticle], prompt_name: str, task_id: str):
        """启动后台 LLM 分析任务。"""
        # ... existing code ...

    def _do_llm_analysis(self, articles: List[NewsArticle], prompt_name: str, 
                         task_id: str, progress_callback: callable, 
                         completion_callback: callable):
        """在后台执行 LLM 分析。"""
        # ... existing code ...

    # --- 停止/取消操作 --- 
    def stop_all_tasks(self):
        """尝试停止所有后台任务 (刷新和检查)。"""
        # ... existing code ... 

    # +++ 新增简单测试方法 +++
    def simple_test_method(self) -> str:
        self.logger.info("--- simple_test_method was called ---")
        return "Test method executed successfully"
    # --- 测试方法结束 --- 

    def _refresh_source_async(self, source: NewsSource, progress_callback: callable, completion_callback: callable, error_callback: callable):
        """在后台线程中执行新闻刷新。"""
        try:
            self.logger.info(f"NewsUpdateService: _refresh_source_async for '{source.name}' started.")
            # ... existing code ...
            if not self._should_cancel_refresh_flag.is_set(): # MODIFIED: Use the instance flag
                total_processed += 1
                progress_percent = int((total_processed / total_sources_to_refresh) * 100)
                self.source_refresh_progress.emit(source.name, progress_percent, total_sources_to_refresh, total_processed)
                self.logger.info(f"NewsUpdateService: Emitted source_refresh_progress for '{source.name}': {progress_percent}%, processed {total_processed}/{total_sources_to_refresh}") # ADDED LOG

        except RefreshCancelledError:
            self.logger.info(f"NewsUpdateService: 刷新源 '{source.name}' 被取消 (async)。")
            # self.logger.debug(f"NewsUpdateService: _refresh_source_async for '{source.name}' completed. Items: {len(news_items)}, Error: {error_message}")

        except Exception as e:
            self.logger.error(f"NewsUpdateService: _refresh_source_async for '{source.name}' 失败: {e}", exc_info=True)