"""
服务模块 - 负责后台任务调度，如定时刷新新闻源。
"""

import logging
from typing import Optional
from PySide6.QtCore import QObject, QSettings, QTimer # QTimer might be useful for delayed start
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# 假设 AppService 的导入路径，需要根据实际情况调整
# from src.core.app_service import AppService # Avoid direct import if using dependency injection

class SchedulerService(QObject):
    """管理后台任务调度，特别是定时刷新新闻源。"""

    # Default interval in minutes
    DEFAULT_REFRESH_INTERVAL_MINUTES = 60
    SETTINGS_KEY_ENABLED = "scheduler/enabled"
    SETTINGS_KEY_INTERVAL = "scheduler/interval_minutes"

    def __init__(self, settings: QSettings, parent: Optional[QObject] = None):
        """
        初始化 SchedulerService。

        Args:
            settings (QSettings): 应用设置对象，用于读取调度配置。
            parent (Optional[QObject]): 父 QObject。
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.settings = settings
        self.scheduler = BackgroundScheduler(daemon=True) # daemon=True so it exits when main thread exits
        self._app_service = None # Placeholder for injected AppService
        self._refresh_job_id = "refresh_all_sources_job"

        self.logger.info("SchedulerService initialized.")

    def set_app_service(self, app_service):
        """
        注入 AppService 依赖。
        必须在调用 start 之前设置。
        """
        self.logger.debug("Setting AppService dependency.")
        self._app_service = app_service

    def start(self):
        """根据配置启动调度器并添加刷新任务。"""
        if not self._app_service:
            self.logger.error("AppService is not set. Cannot start scheduler.")
            # Consider raising an error or handling this more gracefully
            return

        is_enabled = self.settings.value(self.SETTINGS_KEY_ENABLED, False, type=bool)
        interval_minutes = self.settings.value(self.SETTINGS_KEY_INTERVAL, self.DEFAULT_REFRESH_INTERVAL_MINUTES, type=int)

        if is_enabled:
            self.logger.info(f"Scheduler enabled. Starting scheduler and adding refresh job with interval: {interval_minutes} minutes.")
            try:
                self.scheduler.add_job(
                    self._run_refresh_job,
                    trigger=IntervalTrigger(minutes=interval_minutes),
                    id=self._refresh_job_id,
                    replace_existing=True # Replace if job already exists (e.g., after config change)
                )
                self.scheduler.start()
                self.logger.info("Scheduler started successfully.")
            except Exception as e:
                self.logger.error(f"Failed to start scheduler or add job: {e}", exc_info=True)
        else:
            self.logger.info("Scheduler is disabled in settings. Not starting.")

    def stop(self):
        """安全地停止调度器。"""
        if self.scheduler.running:
            self.logger.info("Stopping scheduler...")
            try:
                # wait=False means shutdown doesn't wait for running jobs to complete
                self.scheduler.shutdown(wait=False)
                self.logger.info("Scheduler stopped.")
            except Exception as e:
                self.logger.error(f"Error stopping scheduler: {e}", exc_info=True)
        else:
            self.logger.info("Scheduler was not running.")

    def _run_refresh_job(self):
        """执行实际的新闻刷新任务。"""
        if not self._app_service:
            self.logger.warning("Cannot run refresh job: AppService is not available.")
            return

        self.logger.info("Scheduler triggered: Running refresh_all_sources...")
        try:
            # Ensure refresh_all_sources is thread-safe or called appropriately
            # If refresh_all_sources is blocking, it will block the scheduler thread.
            # If it uses its own threads (like AppService seems to do), this is fine.
            self._app_service.refresh_all_sources()
            self.logger.info("refresh_all_sources called successfully by scheduler.")
        except Exception as e:
            self.logger.error(f"Error calling refresh_all_sources from scheduler: {e}", exc_info=True)

    def update_schedule(self, enabled: bool, interval_minutes: int):
        """
        更新调度配置并重新应用。

        Args:
            enabled (bool): 是否启用调度。
            interval_minutes (int): 刷新间隔（分钟）。
        """
        self.logger.info(f"Updating schedule: enabled={enabled}, interval={interval_minutes} minutes.")
        # Save new settings
        self.settings.setValue(self.SETTINGS_KEY_ENABLED, enabled)
        self.settings.setValue(self.SETTINGS_KEY_INTERVAL, interval_minutes)
        self.settings.sync() # Ensure settings are saved

        # Remove existing job if scheduler is running
        if self.scheduler.running:
            try:
                existing_job = self.scheduler.get_job(self._refresh_job_id)
                if existing_job:
                    self.scheduler.remove_job(self._refresh_job_id)
                    self.logger.debug(f"Removed existing job '{self._refresh_job_id}'.")
            except Exception as e:
                 self.logger.error(f"Error removing job during update: {e}", exc_info=True)

        # Add new job or stop scheduler based on new 'enabled' status
        if enabled:
            if interval_minutes <= 0:
                 self.logger.warning(f"Invalid interval ({interval_minutes}), using default: {self.DEFAULT_REFRESH_INTERVAL_MINUTES}")
                 interval_minutes = self.DEFAULT_REFRESH_INTERVAL_MINUTES
            
            try:
                self.scheduler.add_job(
                    self._run_refresh_job,
                    trigger=IntervalTrigger(minutes=interval_minutes),
                    id=self._refresh_job_id,
                    replace_existing=True
                )
                self.logger.info(f"Added new refresh job with interval: {interval_minutes} minutes.")
                # Start scheduler if it wasn't running
                if not self.scheduler.running:
                    self.scheduler.start()
                    self.logger.info("Scheduler started due to schedule update.")
            except Exception as e:
                self.logger.error(f"Failed to add job during update: {e}", exc_info=True)
        else:
            # If disabled, ensure scheduler is stopped
            self.logger.info("Scheduler disabled by update. Stopping if running.")
            self.stop() # stop() handles the case where it's already stopped

    def get_schedule_config(self) -> tuple[bool, int]:
        """获取当前的调度配置。"""
        is_enabled = self.settings.value(self.SETTINGS_KEY_ENABLED, False, type=bool)
        interval_minutes = self.settings.value(self.SETTINGS_KEY_INTERVAL, self.DEFAULT_REFRESH_INTERVAL_MINUTES, type=int)
        return is_enabled, interval_minutes

# Example of how it might be used (conceptual, actual integration in main.py/MainWindow)
# if __name__ == '__main__':
#     from PySide6.QtCore import QCoreApplication
#     import sys
#     import time

#     # --- Mock AppService for testing ---
#     class MockAppService:
#         def refresh_all_sources(self):
#             print(f"{datetime.now()}: MockAppService.refresh_all_sources() called")
#     # --- End Mock AppService ---

#     logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

#     app = QCoreApplication(sys.argv) # Need event loop for QSettings/QObject if used more deeply
#     settings = QSettings("MyOrg", "MyApp") # Example QSettings

#     # --- Clear previous settings for clean test ---
#     settings.remove("scheduler")
#     # --- End clear settings ---

#     # --- Set initial settings (e.g., enable with 1 minute interval for testing) ---
#     settings.setValue(SchedulerService.SETTINGS_KEY_ENABLED, True)
#     settings.setValue(SchedulerService.SETTINGS_KEY_INTERVAL, 1) # 1 minute
#     settings.sync()
#     # --- End set initial settings ---


#     scheduler_service = SchedulerService(settings)
#     mock_app_service = MockAppService()
#     scheduler_service.set_app_service(mock_app_service)

#     print("Starting scheduler service...")
#     scheduler_service.start()

#     print("Scheduler running. Waiting for triggers... (Press Ctrl+C to stop)")
#     try:
#         # Keep the main thread alive to let the scheduler run
#         while True:
#             time.sleep(1)
#             # Example: Simulate changing settings after some time
#             # if int(time.time()) % 150 == 0: # ~ every 2.5 minutes
#             #    print("\n--- Simulating schedule update (disable) ---")
#             #    scheduler_service.update_schedule(enabled=False, interval_minutes=5)
#             # elif int(time.time()) % 90 == 0: # ~ every 1.5 minutes
#             #     print("\n--- Simulating schedule update (enable, 2 min) ---")
#             #     scheduler_service.update_schedule(enabled=True, interval_minutes=2)

#     except KeyboardInterrupt:
#         print("\nCtrl+C received. Stopping scheduler service...")
#     finally:
#         scheduler_service.stop()
#         print("Scheduler service stopped. Exiting.")
#         # sys.exit(app.exec()) # Not needed if QCoreApplication is simple 