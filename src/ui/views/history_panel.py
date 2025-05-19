# -*- coding: utf-8 -*-
# src/ui/views/history_panel.py
import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, 
                               QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView, 
                               QHeaderView, QMessageBox)
from PySide6.QtCore import Qt

class HistoryPanel(QWidget):
    """Panel for displaying and managing various history records (browse, analysis, chat)."""
    def __init__(self, viewmodel, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.viewmodel = viewmodel
        self._setup_ui()
        self._connect_signals()
        self.logger.info("HistoryPanel initialized.")

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()

        # --- Create Tabs ---
        self.browse_tab = QWidget()
        self.analysis_tab = QWidget()
        self.chat_tab = QWidget()

        self.tab_widget.addTab(self.browse_tab, "浏览历史")
        self.tab_widget.addTab(self.analysis_tab, "分析历史")
        self.tab_widget.addTab(self.chat_tab, "聊天历史")

        self._setup_browse_tab()
        self._setup_analysis_tab()
        self._setup_chat_tab()

        main_layout.addWidget(self.tab_widget)
        self.setLayout(main_layout)

    def _setup_browse_tab(self):
        layout = QVBoxLayout(self.browse_tab)

        # --- Action Buttons ---
        button_layout = QHBoxLayout()
        self.btn_refresh_browse = QPushButton("刷新")
        self.btn_delete_selected_browse = QPushButton("删除选中")
        self.btn_clear_all_browse = QPushButton("清空所有")
        
        button_layout.addWidget(self.btn_refresh_browse)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_delete_selected_browse)
        button_layout.addWidget(self.btn_clear_all_browse)
        layout.addLayout(button_layout)

        # --- History Table ---
        self.browse_history_table = QTableWidget()
        self.browse_history_table.setColumnCount(3)
        self.browse_history_table.setHorizontalHeaderLabels(["标题", "来源", "访问时间"])
        self.browse_history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.browse_history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.browse_history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch) # Title column stretches
        self.browse_history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.browse_history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.browse_history_table.verticalHeader().setVisible(False) # Hide row numbers

        layout.addWidget(self.browse_history_table)
        self.browse_tab.setLayout(layout)
        self.logger.debug("Browse History tab UI setup completed.")

    def _setup_analysis_tab(self):
        layout = QVBoxLayout(self.analysis_tab)

        # --- Action Buttons for Analysis History ---
        button_layout = QHBoxLayout()
        self.btn_refresh_analysis = QPushButton("刷新")
        self.btn_delete_selected_analysis = QPushButton("删除选中")
        self.btn_clear_all_analysis = QPushButton("清空所有")
        
        button_layout.addWidget(self.btn_refresh_analysis)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_delete_selected_analysis)
        button_layout.addWidget(self.btn_clear_all_analysis)
        layout.addLayout(button_layout)

        # --- Analysis History Table ---
        self.analysis_history_table = QTableWidget()
        self.analysis_history_table.setColumnCount(6) # Timestamp, Title, Type, Model, Preview, Status
        self.analysis_history_table.setHorizontalHeaderLabels(["时间戳", "新闻标题", "分析类型", "使用模型", "结果预览", "状态"])
        self.analysis_history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.analysis_history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.analysis_history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # Timestamp
        self.analysis_history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)          # Title
        self.analysis_history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents) # Type
        self.analysis_history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents) # Model
        self.analysis_history_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)          # Preview
        self.analysis_history_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents) # Status
        self.analysis_history_table.verticalHeader().setVisible(False)

        layout.addWidget(self.analysis_history_table)
        self.analysis_tab.setLayout(layout)
        self.logger.debug("Analysis History tab UI setup completed.")

    def _setup_chat_tab(self):
        layout = QVBoxLayout(self.chat_tab)
        label = QLabel("AI 聊天历史将在此处显示 (功能待开发)。")
        layout.addWidget(label)
        self.chat_tab.setLayout(layout)
        self.logger.debug("Chat History tab UI setup (placeholder).")

    def _connect_signals(self):
        self.logger.debug("Connecting HistoryPanel signals...")
        # ViewModel -> View
        self.viewmodel.browse_history_changed.connect(self._update_browse_table)
        self.viewmodel.analysis_history_changed.connect(self._update_analysis_table)
        self.viewmodel.error_occurred.connect(self._show_error_message) # Assuming a generic error display

        # View -> ViewModel (via panel methods)
        self.btn_refresh_browse.clicked.connect(self._on_refresh_browse_clicked)
        self.btn_delete_selected_browse.clicked.connect(self._on_delete_selected_browse_clicked)
        self.btn_clear_all_browse.clicked.connect(self._on_clear_all_browse_clicked)
        self.browse_history_table.itemDoubleClicked.connect(self._on_browse_item_double_clicked)
        self.btn_refresh_analysis.clicked.connect(self._on_refresh_analysis_clicked)
        self.btn_delete_selected_analysis.clicked.connect(self._on_delete_selected_analysis_clicked)
        self.btn_clear_all_analysis.clicked.connect(self._on_clear_all_analysis_clicked)
        self.analysis_history_table.itemDoubleClicked.connect(self._on_analysis_item_double_clicked)
        self.logger.debug("HistoryPanel signals connected.")

    # --- UI Update Slots ---
    def _update_browse_table(self, history_items: list):
        self.logger.info(f"Updating browse_history_table with {len(history_items)} items.")
            
        self.browse_history_table.setRowCount(0) 

        for row, item_data in enumerate(history_items):
            self.browse_history_table.insertRow(row)
            
            title = item_data.get('title', 'N/A')
            source = item_data.get('source_name', 'N/A') 
            accessed_at_str = item_data.get('viewed_at', 'N/A')
            
            title_item = QTableWidgetItem(title)
            source_item = QTableWidgetItem(source)
            accessed_item = QTableWidgetItem(accessed_at_str)

            title_item.setData(Qt.UserRole, item_data.get('link')) 
            
            self.browse_history_table.setItem(row, 0, title_item)
            self.browse_history_table.setItem(row, 1, source_item)
            self.browse_history_table.setItem(row, 2, accessed_item)
        
        self.logger.debug("Browse history table updated.")

    def _update_analysis_table(self, analysis_items: list):
        self.logger.info(f"Updating analysis_history_table with {len(analysis_items)} items.")
        self.analysis_history_table.setRowCount(0)

        for row, item_data in enumerate(analysis_items):
            self.analysis_history_table.insertRow(row)

            ts = item_data.get('timestamp', 'N/A')
            title = item_data.get('news_article_title', 'N/A')
            analysis_type = item_data.get('analysis_type', 'N/A')
            model = item_data.get('llm_model_used', 'N/A')
            
            result_preview = str(item_data.get('result', '')) # Ensure it's a string
            if len(result_preview) > 100: # Simple preview truncation
                result_preview = result_preview[:100] + "..."
            
            status = item_data.get('status', 'N/A')
            if status == "error" and item_data.get('error_message'):
                status = f"失败: {item_data.get('error_message')[:50]}..." # Preview error
            elif status == "success":
                status = "成功"

            ts_item = QTableWidgetItem(ts)
            title_item = QTableWidgetItem(title)
            type_item = QTableWidgetItem(analysis_type)
            model_item = QTableWidgetItem(model)
            preview_item = QTableWidgetItem(result_preview)
            status_item = QTableWidgetItem(status)

            # Store the analysis ID for later actions (e.g., delete, view detail)
            analysis_id = item_data.get('id')
            title_item.setData(Qt.UserRole, analysis_id) # Store ID in title item for convenience
            # Store related news link as well if needed for double-click action
            title_item.setData(Qt.UserRole + 1, item_data.get('news_article_link'))

            self.analysis_history_table.setItem(row, 0, ts_item)
            self.analysis_history_table.setItem(row, 1, title_item)
            self.analysis_history_table.setItem(row, 2, type_item)
            self.analysis_history_table.setItem(row, 3, model_item)
            self.analysis_history_table.setItem(row, 4, preview_item)
            self.analysis_history_table.setItem(row, 5, status_item)
        self.logger.debug("Analysis history table updated.")

    # --- Button Click Handlers ---
    def _on_refresh_browse_clicked(self):
        self.logger.debug("Refresh browse history button clicked.")
        self.viewmodel.load_browse_history()

    def _on_delete_selected_browse_clicked(self):
        self.logger.debug("Delete selected browse history button clicked.")
        selected_items = self.browse_history_table.selectedItems()
        if not selected_items:
            self.logger.debug("No items selected for deletion.")
            return
        
        selected_row = self.browse_history_table.currentRow()
        if selected_row < 0: return

        link_item = self.browse_history_table.item(selected_row, 0) 
        if link_item:
            link_to_delete = link_item.data(Qt.UserRole)
            if link_to_delete:
                self.logger.info(f"Requesting deletion of browse item: {link_to_delete}")
                self.viewmodel.delete_browse_history_item(link_to_delete)
            else:
                self.logger.warning("Selected item for deletion has no link data.")
        else:
            self.logger.warning("Could not retrieve link from selected item for deletion.")

    def _on_clear_all_browse_clicked(self):
        self.logger.debug("Clear all browse history button clicked.")
        reply = QMessageBox.question(self, "确认操作", 
                                     "您确定要清空所有浏览历史吗？此操作不可恢复。",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.viewmodel.clear_browse_history()
        else:
            self.logger.debug("Clear all browse history cancelled by user.")

    def _on_browse_item_double_clicked(self, item: QTableWidgetItem):
        link = item.data(Qt.UserRole) 
        if item.column() == 0 and link: 
             self.logger.info(f"Browse history item double-clicked. Link: {link}")
             self.viewmodel.reopen_browse_item(link)
        else: 
            link_item = self.browse_history_table.item(item.row(), 0)
            if link_item:
                link = link_item.data(Qt.UserRole)
                if link:
                    self.logger.info(f"Browse history item (any column) double-clicked. Link from row: {link}")
                    self.viewmodel.reopen_browse_item(link)
                else:
                    self.logger.warning(f"Double-clicked item's row has no link data in title column. Row: {item.row()}")
            else:
                self.logger.warning(f"Could not get title item for double-clicked row to retrieve link. Row: {item.row()}")

    def _on_refresh_analysis_clicked(self):
        self.logger.debug("Refresh analysis history button clicked.")
        self.viewmodel.load_analysis_history()

    def _on_delete_selected_analysis_clicked(self):
        self.logger.debug("Delete selected analysis history button clicked.")
        selected_items = self.analysis_history_table.selectedItems()
        if not selected_items:
            self.logger.debug("No analysis items selected for deletion.")
            return

        selected_row = self.analysis_history_table.currentRow()
        if selected_row < 0: return

        # Assuming ID is stored in the title item (column 1) for now
        id_item = self.analysis_history_table.item(selected_row, 1) 
        if id_item:
            analysis_id_to_delete = id_item.data(Qt.UserRole)
            if analysis_id_to_delete:
                self.logger.info(f"Requesting deletion of analysis item ID: {analysis_id_to_delete}")
                self.viewmodel.delete_analysis_history_item(analysis_id_to_delete)
            else:
                self.logger.warning("Selected analysis item for deletion has no ID data.")
        else:
            self.logger.warning("Could not retrieve ID from selected analysis item for deletion.")

    def _on_clear_all_analysis_clicked(self):
        self.logger.debug("Clear all analysis history button clicked.")
        reply = QMessageBox.question(self, "确认操作", 
                                     "您确定要清空所有分析历史吗？此操作不可恢复。",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.viewmodel.clear_analysis_history()
        else:
            self.logger.debug("Clear all analysis history cancelled by user.")

    def _on_analysis_item_double_clicked(self, item: QTableWidgetItem):
        analysis_id = None
        news_link = None

        # Try to get analysis_id from the item itself or the title column (column 1)
        if item.column() == 1: # Title column where ID is stored
            analysis_id = item.data(Qt.UserRole)
            news_link = item.data(Qt.UserRole + 1)
        else:
            title_column_item = self.analysis_history_table.item(item.row(), 1)
            if title_column_item:
                analysis_id = title_column_item.data(Qt.UserRole)
                news_link = title_column_item.data(Qt.UserRole + 1)

        if analysis_id:
            self.logger.info(f"Analysis history item double-clicked. ID: {analysis_id}, News Link: {news_link}")
            # Option 1: Show analysis detail (e.g., in a dialog)
            analysis_detail = self.viewmodel.get_analysis_detail(analysis_id)
            if analysis_detail:
                # For simplicity, show in a QMessageBox for now. Later, a custom dialog.
                detail_text = f"ID: {analysis_detail.get('id')}\n"
                detail_text += f"时间: {analysis_detail.get('timestamp')}\n"
                detail_text += f"新闻: {analysis_detail.get('news_article_title')}\n"
                detail_text += f"类型: {analysis_detail.get('analysis_type')}\n"
                detail_text += f"模型: {analysis_detail.get('llm_model_used', 'N/A')}\n"
                detail_text += f"状态: {analysis_detail.get('status')}\n"
                detail_text += f"结果:\n{str(analysis_detail.get('result', ''))}"
                if analysis_detail.get('status') == 'error':
                    detail_text += f"\n错误信息: {analysis_detail.get('error_message', '')}"
                
                QMessageBox.information(self, "分析详情", detail_text)
            else:
                self._show_error_message(f"无法加载分析详情 (ID: {analysis_id}).")

            # Option 2: If news_link exists, also consider reopening the news
            # if news_link:
            # self.viewmodel.reopen_browse_item(news_link)
        else:
            self.logger.warning(f"Double-clicked analysis item's row has no ID data. Row: {item.row()}")

    def refresh_data(self):
        """Request ViewModel to refresh all history data. Currently only browse history."""
        self.logger.info("Requesting ViewModel to refresh history data.")
        self.viewmodel.load_browse_history()
        # TODO: Call load methods for other tabs when implemented
        # self.viewmodel.load_analysis_history()
        # self.viewmodel.load_chat_history()

    def _show_error_message(self, message: str):
        # This panel might not have direct access to DialogManager to show a global error.
        # For now, log it. Consider emitting a signal if global error popups are needed.
        self.logger.error(f"Error from ViewModel: {message}")
        QMessageBox.warning(self, "错误", message) 