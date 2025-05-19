# src/ui/managers/window_state_manager.py
from PyQt5.QtCore import QSettings, QByteArray, QSize, QPoint
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow # Avoid circular import

class WindowStateManager:
    """
    Manages saving and restoring the main window's geometry state using QSettings.
    """
    WINDOW_GEOMETRY_KEY = "geometry/mainWindowGeometry"
    WINDOW_STATE_KEY = "geometry/mainWindowState"

    def __init__(self, parent_window: 'MainWindow', settings: QSettings):
        """
        Initializes the WindowStateManager.

        Args:
            parent_window: The main window instance (MainWindow).
            settings: The QSettings instance to use for persistence.
        """
        self.window = parent_window
        self.settings = settings

    def save_state(self):
        """Saves the main window's geometry and state to settings."""
        print("WindowStateManager: Saving window state...")
        self.settings.setValue(self.WINDOW_GEOMETRY_KEY, self.window.saveGeometry())
        self.settings.setValue(self.WINDOW_STATE_KEY, self.window.saveState()) # Saves dock/toolbar state too
        # Note: Splitter states are saved by PanelManager

    def restore_state(self):
        """Restores the main window's geometry and state from settings."""
        print("WindowStateManager: Restoring window state...")
        geometry = self.settings.value(self.WINDOW_GEOMETRY_KEY)
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            if self.window.restoreGeometry(geometry):
                print("WindowStateManager: Window geometry restored.")
            else:
                print("WindowStateManager: Failed to restore window geometry.")
        else:
            print("WindowStateManager: No saved geometry found, using default.")
            # Optional: Set a default size if no geometry is saved
            # self.window.resize(QSize(1200, 800))
            # self.window.move(QPoint(100, 100)) # Optional default position

        state = self.settings.value(self.WINDOW_STATE_KEY)
        if isinstance(state, QByteArray) and not state.isEmpty():
             if self.window.restoreState(state):
                 print("WindowStateManager: Window state (docks/toolbars) restored.")
             else:
                 print("WindowStateManager: Failed to restore window state.")
        else:
            print("WindowStateManager: No saved window state found.")

        # Note: Splitter states are restored by PanelManager after panels are created