# src/ui/managers/panel_manager.py
import logging
from PySide6.QtWidgets import (QWidget, QSplitter, QVBoxLayout, QDockWidget, QPushButton, QTabWidget,
                             QGridLayout) # Use PySide6 - Added QGridLayout
from PySide6.QtCore import Qt, QSettings # Use PySide6

# Import panel classes (ensure these exist and paths are correct)
try:
    # from src.ui.sidebar import CategorySidebar # Old path
    from src.ui.views.sidebar import CategorySidebar # Corrected path
except ImportError: CategorySidebar = None; logging.getLogger(__name__).warning("CategorySidebar not found.")
try:
    # from src.ui.news_list import NewsListPanel # Old path
    from src.ui.news_list import NewsListPanel # Corrected path
except ImportError: NewsListPanel = None; logging.getLogger(__name__).warning("NewsListPanel not found.")
try:
    # from src.ui.chat_panel import ChatPanel # Old path
    from src.ui.views.chat_panel import ChatPanel # Corrected path
except ImportError: ChatPanel = None; logging.getLogger(__name__).warning("ChatPanel not found.")
try:
    # from src.ui.llm_panel import LLMPanel # Old path
    from src.ui.llm_panel import LLMPanel # Corrected path
except ImportError: LLMPanel = None; logging.getLogger(__name__).warning("LLMPanel not found.")
try:
    # from src.ui.search_panel import SearchPanel # Old path
    from src.ui.search_panel import SearchPanel # Corrected path
except ImportError: SearchPanel = None; logging.getLogger(__name__).warning("SearchPanel not found.")


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow # Avoid circular import
    from src.core.app_service import AppService
    from src.ui.viewmodels.news_list_viewmodel import NewsListViewModel
    from src.ui.viewmodels.llm_panel_viewmodel import LLMPanelViewModel
    from src.ui.viewmodels.chat_panel_viewmodel import ChatPanelViewModel

class PanelManager:
    """
    Manages the creation, layout, and visibility of the main UI panels.
    Handles splitter state persistence.
    """
    # Settings keys for splitter states
    MAIN_SPLITTER_STATE_KEY = "geometry/mainSplitterState"
    # RIGHT_SPLITTER_STATE_KEY = "geometry/rightSplitterState" # Removed: No longer using right splitter (Confirming removal)
    # BOTTOM_SPLITTER_STATE_KEY = "geometry/bottomSplitterState" # Removed: No longer using bottom splitter

    def __init__(self, parent_window: 'MainWindow', app_service: 'AppService'):
        """
        Initializes the PanelManager.

        Args:
            parent_window: The main window instance (MainWindow).
            app_service: The application service instance.
        """
        self.window = parent_window
        self.app_service = app_service
        self.logger = logging.getLogger(__name__)

        # Panel instances
        self.sidebar: CategorySidebar = None
        self.news_list_panel: NewsListPanel = None
        self.chat_panel: ChatPanel = None
        self.llm_panel: LLMPanel = None
        self.search_panel: SearchPanel = None

        # Layout widgets
        self.main_splitter: QSplitter = None
        # self.right_splitter: QSplitter = None # Removed: No longer using right splitter (Confirming removal)
        # self.bottom_splitter: QSplitter = None # Removed: No longer using bottom splitter
        self.llm_chat_tabs: QTabWidget = None # Added: Tab widget for LLM/Chat
        self.central_widget: QWidget = None
        # self.sidebar_dock: QDockWidget = None # No longer using DockWidget for sidebar

    def setup_panels(self,
                     news_list_vm: 'NewsListViewModel',
                     llm_panel_vm: 'LLMPanelViewModel',
                     chat_panel_vm: 'ChatPanelViewModel'):
        """
        Creates, initializes, and lays out the main UI panels.

        Args:
            news_list_vm: The ViewModel for the news list panel.
            llm_panel_vm: The ViewModel for the LLM panel.
            chat_panel_vm: The ViewModel for the chat panel.
        """
        self.logger.info("Setting up UI panels...")
        # --- Instantiate Panels ---
        # Check if classes were imported successfully before instantiating
        if CategorySidebar: self.sidebar = CategorySidebar(self.app_service.source_manager)
        if NewsListPanel: self.news_list_panel = NewsListPanel(view_model=news_list_vm)
        if LLMPanel: self.llm_panel = LLMPanel(view_model=llm_panel_vm)
        if ChatPanel: self.chat_panel = ChatPanel(view_model=chat_panel_vm)
        if SearchPanel: self.search_panel = SearchPanel()

        # --- Setup Layout ---
        self._setup_layout()

        # --- Connect Panel Signals ---
        # Connections are now handled in MainWindow._connect_manager_signals
        # We might connect internal panel signals here if needed in the future.
        # self._connect_internal_panel_signals()
        self.logger.info("Panel setup complete.")


    def _setup_layout(self):
        """Sets up the main layout using splitters.""" # Removed docks from description
        self.logger.debug("Setting up panel layout...")
        # Create central widget and main layout for it
        self.central_widget = QWidget()
        self.central_widget.setObjectName("centralWidget")
        self.window.setCentralWidget(self.central_widget) # Set it on the main window
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5) # Use margins from original code
        main_layout.setSpacing(5)

        # Add Search Panel at the top (if it exists)
        if self.search_panel:
            main_layout.addWidget(self.search_panel)
            self.logger.debug("Added SearchPanel to main layout.") # Added log
        else:
            self.logger.warning("SearchPanel not available for layout.")

        # Main content area using a horizontal splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.main_splitter, 1) # Give splitter stretch factor
        self.logger.debug("Added main_splitter to main layout.") # Added log

        # --- Left Side: Container with Sidebar --- (Button removed from here)
        if self.sidebar:
            # The sidebar itself is now the direct widget in the splitter
            self.main_splitter.addWidget(self.sidebar)
            # Optionally set a minimum width directly on the sidebar if needed
            self.sidebar.setMinimumWidth(200) # Adjust if necessary
            self.logger.debug(f"Added sidebar directly to main splitter.")
        else:
            self.logger.warning("CategorySidebar not available for layout.")


        # --- Middle Section: News List Panel ---
        if self.news_list_panel:
            self.main_splitter.addWidget(self.news_list_panel)
            self.news_list_panel.setMinimumWidth(400) # Set minimum width for the middle panel
            self.logger.debug(f"Added news_list_panel to main_splitter. main_splitter count: {self.main_splitter.count()}")
        else:
            self.logger.warning("NewsListPanel not available for layout.")

        # --- Right Section: Tab Widget for LLM and Chat ---
        self.llm_chat_tabs = QTabWidget() # Ensure it's created here
        self.llm_chat_tabs.setObjectName("llmChatTabWidget")
        self.logger.debug("Created llm_chat_tabs (QTabWidget).")

        # Add LLM Panel (if it exists)
        if self.llm_panel:
            self.llm_chat_tabs.addTab(self.llm_panel, "LLM 分析")
            # self.llm_panel.setMinimumHeight(400) # Removed: Let size policy handle height
            self.logger.debug("Added llm_panel to llm_chat_tabs and set minimum height.")
        else:
            self.logger.warning("LLMPanel not available for layout.")

        # Add Chat Panel (if it exists)
        if self.chat_panel:
            self.llm_chat_tabs.addTab(self.chat_panel, "智能聊天")
            # self.chat_panel.setMinimumHeight(400) # Removed: Let size policy handle height
            self.logger.debug("Added chat_panel to llm_chat_tabs and set minimum height.")
        else:
            self.logger.warning("ChatPanel not available for layout.")

        # Add the tab widget to the main splitter if it has tabs
        if self.llm_chat_tabs.count() > 0:
             self.llm_chat_tabs.setMinimumWidth(300) # Set minimum width for the right panel
             self.main_splitter.addWidget(self.llm_chat_tabs)
             self.logger.debug(f"Added llm_chat_tabs to main_splitter. main_splitter count: {self.main_splitter.count()}")
        else:
             self.logger.warning("LLM/Chat TabWidget is empty, not adding to main_splitter.")
        # Set initial sizes for the three sections (can be overridden by restore_state)
        # Ensure splitter has 3 widgets before setting sizes
        if self.main_splitter.count() == 3:
            # Give middle panel (news list) more initial space
            self.main_splitter.setSizes([200, 700, 300]) # Adjusted ratio
            self.logger.debug(f"Set initial sizes for main_splitter: {self.main_splitter.sizes()}")
        else:
            self.logger.warning(f"main_splitter has {self.main_splitter.count()} widgets, expected 3. Skipping initial size setting.")
        self.logger.debug("Panel layout structure created.")


    # def _connect_internal_panel_signals(self):
    #     """Connect signals internal to panels if needed."""
        # Example: If chat panel needed direct access to LLM panel's state
        # if self.llm_panel and self.chat_panel:
        #     self.llm_panel.some_signal.connect(self.chat_panel.some_slot)
        # pass

    def toggle_sidebar(self, visible: bool):
        """Shows or hides the left sidebar container.""" # Updated description
        # Find the left container widget in the splitter
        if self.main_splitter and self.main_splitter.count() > 0:
             left_widget = self.main_splitter.widget(0) # Assuming it's the first widget
             if left_widget:
                 left_widget.setVisible(visible)
                 self.logger.info(f"Left sidebar container visibility set to: {visible}")
             else:
                 self.logger.warning("Could not find left widget in main splitter to toggle visibility.")
        else:
            self.logger.warning("Attempted to toggle sidebar, but main splitter not found or empty.")


    def get_sidebar_visibility(self) -> bool:
        """Returns the current visibility state of the left sidebar container.""" # Updated description
        if self.main_splitter and self.main_splitter.count() > 0:
             left_widget = self.main_splitter.widget(0)
             return left_widget.isVisible() if left_widget else False
        return False

    # --- Methods to access panels ---
    def get_sidebar(self) -> CategorySidebar | None: return self.sidebar
    def get_news_list_panel(self) -> NewsListPanel | None: return self.news_list_panel
    def get_chat_panel(self) -> ChatPanel | None: return self.chat_panel
    def get_llm_panel(self) -> LLMPanel | None: return self.llm_panel
    def get_search_panel(self) -> SearchPanel | None: return self.search_panel


    # --- State Saving/Restoring ---
    def save_state(self, settings: QSettings):
        """Saves the state of the splitters."""
        self.logger.debug("Saving splitter states...")
        if self.main_splitter:
            settings.setValue(self.MAIN_SPLITTER_STATE_KEY, self.main_splitter.saveState())
            self.logger.debug(f"Main splitter state saved.")
        # Removed right_splitter state saving logic
        # if self.bottom_splitter: # Removed
        #     settings.setValue(self.BOTTOM_SPLITTER_STATE_KEY, self.bottom_splitter.saveState())
        #     self.logger.debug(f"Bottom splitter state saved.")
        # Dock widget state is handled by MainWindow.saveState() via WindowStateManager

    def restore_state(self, settings: QSettings):
        """Restores the state of the splitters, forcing default sizes for debugging.""" # Updated docstring

        # --- Force Default Sizes for Debugging Splitter --- 
        self.logger.debug("Forcing default splitter sizes for debugging...")
        if self.main_splitter:
            self.logger.debug("Applying default sizes to main splitter...")
            # Adjust default sizes for three sections
            default_width_left = 200
            default_width_right = max(300, self.window.width() // 4) # Min 300px or 1/4 width
            default_width_middle = max(400, self.window.width() - default_width_left - default_width_right - 20) # Remaining space, min 400px
            # Ensure main_splitter has 3 widgets before setting sizes
            if self.main_splitter.count() == 3:
                self.main_splitter.setSizes([default_width_left, default_width_middle, default_width_right])
                self.logger.debug(f"Applied default sizes to main splitter: {[default_width_left, default_width_middle, default_width_right]}")
            else:
                self.logger.warning(f"main_splitter has {self.main_splitter.count()} widgets, expected 3. Skipping default size setting.")

        # --- Log final splitter sizes after restore/default ---
        if self.main_splitter:
             self.logger.info(f"Final main_splitter sizes after restore/default: {self.main_splitter.sizes()}")
        # Removed logging for non-existent splitters
        # --- End log ---

        # Dock widget state is handled by MainWindow.restoreState() via WindowStateManager