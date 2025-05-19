# src/ui/managers/status_bar_manager.py
import logging # Import logging
from PySide6.QtWidgets import QStatusBar, QProgressBar # Use PySide6
from PySide6.QtCore import Qt # Use PySide6
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow # Avoid circular import
    from src.core.app_service import AppService # If connecting signals

class StatusBarManager:
    """
    Manages the creation and updates of the application's status bar,
    including messages and a progress bar.
    """
    def __init__(self, parent_window: 'MainWindow'):
        """
        Initializes the StatusBarManager.

        Args:
            parent_window: The main window instance (MainWindow).
        """
        self.window = parent_window
        self.logger = logging.getLogger(__name__) # Add logger
        self.status_bar: QStatusBar = None
        self.progress_bar: QProgressBar = None # Add progress bar attribute
        self._setup_status_bar()

    def _setup_status_bar(self):
        """Creates and sets up the status bar and progress bar."""
        self.status_bar = QStatusBar(self.window)
        self.window.setStatusBar(self.status_bar)

        # Create Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumSize(150, 15) # Set a reasonable max size
        self.progress_bar.setTextVisible(False) # Hide percentage text
        self.progress_bar.setVisible(False) # Initially hidden

        # Add progress bar as a permanent widget on the right
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.logger.info("Status bar and progress bar initialized.")

        self.show_message("Ready", 5000) # Initial message, disappears after 5s

    def show_message(self, message: str, timeout: int = 0):
        """
        Displays a message on the status bar.

        Args:
            message: The message to display.
            timeout: The time in milliseconds to display the message (0 = permanent).
        """
        if self.status_bar:
            self.status_bar.showMessage(message, timeout)
            self.logger.debug(f"Status bar message set: '{message}' (Timeout: {timeout}ms)")
        else:
            self.logger.error(f"Status bar not initialized. Cannot show message: {message}")


    def clear_message(self):
        """Clears the current message from the status bar."""
        if self.status_bar:
            self.status_bar.clearMessage()
            self.logger.debug("Status bar message cleared.")

    # --- Progress Bar Methods ---
    def show_progress(self):
        """Shows the progress bar."""
        if self.progress_bar:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0) # Reset value when shown
            self.logger.debug("Progress bar shown.")
        else:
             self.logger.error("Progress bar not initialized. Cannot show.")

    def hide_progress(self):
        """Hides the progress bar."""
        if self.progress_bar:
            self.progress_bar.setVisible(False)
            self.progress_bar.setValue(0) # Reset value when hidden
            self.logger.debug("Progress bar hidden.")
        else:
             self.logger.error("Progress bar not initialized. Cannot hide.")

    def update_progress(self, current: int, total: int):
        """Updates the progress bar value."""
        if self.progress_bar:
            if total > 0:
                # Calculate percentage or set range
                self.progress_bar.setRange(0, total)
                self.progress_bar.setValue(current)
                self.logger.debug(f"Progress bar updated: {current}/{total}")
            else:
                # Handle indeterminate case or reset if total is zero
                self.progress_bar.setRange(0, 0) # Indeterminate state
                self.logger.debug("Progress bar set to indeterminate (total=0).")
        else:
             self.logger.error("Progress bar not initialized. Cannot update.")

    # --- End Progress Bar Methods ---

    def connect_signals(self, app_service: 'AppService'):
        """Connects signals for automatic status updates."""
        self.logger.info("Connecting status bar signals to AppService...")
        try:
            # Connect status message signal
            if hasattr(app_service, 'status_message_updated'):
                app_service.status_message_updated.connect(self.show_message)
                self.logger.debug("Connected app_service.status_message_updated to show_message.")

            # Connect progress signals
            if hasattr(app_service, 'refresh_started'):
                app_service.refresh_started.connect(self.show_progress)
                self.logger.debug("Connected app_service.refresh_started to show_progress.")
            if hasattr(app_service, 'refresh_progress'):
                app_service.refresh_progress.connect(self.update_progress)
                self.logger.debug("Connected app_service.refresh_progress to update_progress.")
            if hasattr(app_service, 'refresh_complete'):
                # Connect finished signal (success or fail) to hide progress
                app_service.refresh_complete.connect(lambda success, msg: self.hide_progress())
                self.logger.debug("Connected app_service.refresh_complete to hide_progress.")
            # No need to connect refresh_cancelled separately if refresh_complete handles it

        except Exception as e:
            self.logger.error(f"Error connecting status bar signals: {e}", exc_info=True)