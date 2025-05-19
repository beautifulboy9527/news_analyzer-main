# src/ui/browsing_history_panel.py
"""
浏览历史记录面板

显示用户查看过的单条新闻记录，并提供管理功能。
"""

import logging
from datetime import datetime
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListView,
                             QListWidgetItem, QLabel, QTextBrowser, QPushButton,
                             QSplitter, QMessageBox, QSizePolicy, QWidget, QAbstractItemView) # Use PySide6
from PySide6.QtCore import Qt, QSize, QUrl, QTimer # Use PySide6, add QUrl, QTimer
from PySide6.QtGui import QIcon, QDesktopServices, QPalette # Use PySide6
from PySide6.QtCore import Slot as pyqtSlot
from PySide6.QtCore import Signal as pyqtSignal # Ensure Signal is imported
from PySide6.QtCore import QModelIndex

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..viewmodels.browsing_history_viewmodel import BrowsingHistoryViewModel
    from ..storage.news_storage import NewsStorage # Keep for type hint if still used indirectly or for gradual refactor

# 假设 NewsStorage 在父级目录的 storage 中
try:
    from ..storage.news_storage import NewsStorage
except ImportError:
    # 处理可能的导入错误，例如在独立运行此文件进行测试时
    NewsStorage = None
    logging.getLogger(__name__).error("无法导入 NewsStorage！")

class BrowsingHistoryPanel(QDialog):
    """浏览历史记录对话框"""

    rejected_and_deleted = pyqtSignal() # Define signal at class level

    # Signal definition moved to __init__ to resolve potential NameError

# Removed incorrectly placed import and signal definition

    def __init__(self, view_model: 'BrowsingHistoryViewModel', parent=None):
        super().__init__(parent)
        self.setWindowTitle("浏览历史记录")
        # Removed signal definition from __init__

        self.setMinimumSize(700, 500)
        # 设置窗口标志，移除问号按钮，添加最大化按钮
        flags = self.windowFlags()
        flags &= ~Qt.WindowContextHelpButtonHint  # 移除问号按钮
        flags |= Qt.WindowMaximizeButtonHint     # 尝试启用最大化
        flags |= Qt.WindowMinimizeButtonHint     # 尝试启用最小化
        flags |= Qt.WindowCloseButtonHint        # 确保关闭按钮启用
        self.setWindowFlags(flags)

        self.logger = logging.getLogger('news_analyzer.ui.browsing_history')
        self.view_model = view_model # MODIFIED: Store ViewModel

        self._init_ui()

        # Connect ViewModel signals to Panel slots
        if self.view_model:
            self.view_model.history_changed.connect(self._on_history_vm_updated)
            self.view_model.error_occurred.connect(self._on_vm_error) # Optional: handle VM errors
            self.view_model.load_history() # Initial load
            self.logger.info("BrowsingHistoryPanel initialized with ViewModel and signals connected.")
        else:
            self.logger.error("BrowsingHistoryViewModel not provided to BrowsingHistoryPanel!")
            # Optionally disable UI elements or show an error message
            QMessageBox.critical(self, "错误", "历史记录视图模型不可用，无法加载浏览历史。")
            # Disable buttons if VM is missing
            self.refresh_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.clear_all_button.setEnabled(False)
            self.history_list.setEnabled(False)

    def _init_ui(self):
        """初始化UI布局和控件"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # --- 控制按钮 ---
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)

        self.refresh_button = QPushButton(QIcon.fromTheme("view-refresh", QIcon("")), " 刷新")
        self.refresh_button.setToolTip("重新加载历史记录列表")
        self.refresh_button.clicked.connect(self._refresh_history)
        control_layout.addWidget(self.refresh_button)

        control_layout.addStretch()

        self.delete_button = QPushButton(QIcon.fromTheme("edit-delete", QIcon("")), " 删除选中")
        self.delete_button.setToolTip("删除选中的历史记录")
        self.delete_button.clicked.connect(self._delete_selected)
        self.delete_button.setEnabled(False) # 初始禁用
        control_layout.addWidget(self.delete_button)

        self.clear_all_button = QPushButton(QIcon.fromTheme("edit-clear", QIcon("")), " 清空全部")
        self.clear_all_button.setToolTip("清空所有浏览历史记录（不可恢复）")
        self.clear_all_button.clicked.connect(self._clear_all)
        control_layout.addWidget(self.clear_all_button)

        layout.addLayout(control_layout)

        # --- 列表和预览 ---
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1) # 让分割器占据主要空间

        # 左侧历史列表
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.history_list = QListView()
        self.logger.debug(f"history_list instance: {self.history_list}") # DEBUG
        selection_model = self.history_list.selectionModel()
        self.logger.debug(f"history_list selectionModel: {selection_model}") # DEBUG

        self.history_list.setAlternatingRowColors(True)
        # Updated stylesheet for selection and hover colors
        self.history_list.setStyleSheet(""" 
            QListView::item:selected {
                background-color: #ADD8E6; /* lightskyblue */
                color: black; 
            }
            QListView::item:selected:active {
                background-color: #87CEEB; /* SkyBlue */
                color: black;
            }
            QListView::item:selected:!active {
                background-color: #B0C4DE; /* LightSteelBlue */
                color: black;
            }
            QListView::item:hover {
                background-color: #E0F2F7; /* Very light blue for hover */
                color: black; 
            }
        """)
        self.history_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.history_list.doubleClicked.connect(self._on_history_item_double_clicked)
        
        if selection_model: # Check if selection_model is not None
            selection_model.currentChanged.connect(self._on_history_selection_changed)
            selection_model.selectionChanged.connect(self._update_delete_button_state)
        else:
            self.logger.warning("history_list.selectionModel() is None initially. Attempting to connect signals via QTimer.singleShot.")
            QTimer.singleShot(0, self._connect_history_list_signals)

        left_layout.addWidget(self.history_list)
        splitter.addWidget(left_panel)

        # 右侧预览面板 (使用 QTextBrowser 以支持链接点击)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 0, 0, 0) # 左边距5，其他为0

        self.preview_browser = QTextBrowser() # 改为 QTextBrowser
        self.preview_browser.setOpenExternalLinks(True) # 允许打开外部链接
        self.preview_browser.setPlaceholderText("请在左侧选择一条历史记录查看详情") # 设置占位符文本
        # 移除硬编码的背景色，让其适应主题
        self.preview_browser.setStyleSheet("QTextBrowser { border: 1px solid #ccc; padding: 5px; }")
        right_layout.addWidget(self.preview_browser, 1) # 让浏览器占据可用空间
        splitter.addWidget(right_panel)

        splitter.setSizes([400, 300]) # 调整初始比例

        # --- 关闭按钮 ---
        close_button = QPushButton("关闭")
        close_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        close_button.clicked.connect(self.reject) # Connect directly to reject

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        # 禁用控件（如果 storage 无效）
        # MODIFIED: This check will now be based on self.view_model in __init__
        # if not self.storage: 
        #     self.refresh_button.setEnabled(False)
        #     self.delete_button.setEnabled(False)
        #     self.clear_all_button.setEnabled(False)
        #     self.history_list.setEnabled(False)

    # ADDED: Slot to handle history updates from ViewModel
    @pyqtSlot()
    def _on_history_vm_updated(self):
        """Slot to handle ViewModel updates (e.g., history loaded or changed)."""
        self.logger.info("_on_history_vm_updated called. Updating list view.")
        # The model is now directly accessible via self._view_model.get_model()
        # We just need to tell the view to use the potentially updated model
        # The view model handles updating the model data internally.
        # We don't need the history_entries argument here anymore.
        model = self.view_model.get_model() 
        if model:
            # Ensure the view is using the correct model instance
            # (Should already be set in __init__, but doesn't hurt to re-affirm)
            self.history_list.setModel(model) 
            # The view should automatically reflect changes when the model signals dataChanged
            # or layoutChanged (which _apply_filters should trigger via model.update_data)
            self.logger.info(f"History list view updated with model. Row count: {model.rowCount()}")
        else:
            self.logger.warning("ViewModel did not provide a valid model.")
            self.history_list.setModel(None) # Clear the view if model is invalid

    # ADDED: Slot to handle errors from ViewModel (optional)
    @pyqtSlot(str)
    def _on_vm_error(self, error_message: str):
        self.logger.error(f"Error from ViewModel: {error_message}")
        QMessageBox.warning(self, "历史记录错误", error_message)

    def _refresh_history(self):
        """从 ViewModel重新加载历史记录"""
        if self.view_model:
            self.logger.info("刷新按钮点击，调用 ViewModel.load_history()")
            self.view_model.load_history()
        else:
            self.logger.warning("ViewModel 无效，无法刷新历史记录")
            # self.history_list.clear() # Already handled by _on_history_vm_updated if it emits empty
            # self.preview_browser.setHtml("<p style='color: red;'>错误：历史记录视图模型不可用。</p>")
            self._on_vm_error("历史记录视图模型不可用。")

    @pyqtSlot(QModelIndex, QModelIndex)
    def _on_history_selection_changed(self, current: QModelIndex, previous: QModelIndex):
        """当列表选中项改变时，更新预览区域 (for QListView)"""
        if not current.isValid():
            self.preview_browser.setHtml("")
            self.preview_browser.setPlaceholderText("请在左侧选择一条历史记录查看详情")
            return

        entry_data = self.view_model.get_model().data(current, Qt.UserRole)
        if entry_data and isinstance(entry_data, dict):
            title = entry_data.get('article_title', 'N/A')
            link = entry_data.get('article_link', '#')
            source = entry_data.get('article_source_name', 'N/A')
            view_time_obj = entry_data.get('view_time', 'N/A')

            # Format view_time if it's a datetime object
            display_browsed_at = 'N/A' # 默认值
            if view_time_obj and view_time_obj != 'N/A':
                try:
                    if isinstance(view_time_obj, datetime):
                        browsed_dt = view_time_obj
                    elif isinstance(view_time_obj, str):
                        # Attempt to parse if it's a string (e.g., ISO format from DB before conversion)
                        browsed_dt = datetime.fromisoformat(view_time_obj.replace('Z', '+00:00'))
                    else:
                        # If it's neither datetime nor string we can parse, log and keep N/A
                        self.logger.warning(f"Unsupported type for view_time_obj: {type(view_time_obj)}")
                        browsed_dt = None # Ensure it falls into the N/A case

                    if browsed_dt:
                        display_browsed_at = browsed_dt.strftime('%Y-%m-%d %H:%M:%S')
                        # If browsed_dt is None (e.g. due to unsupported type), display_browsed_at remains 'N/A'

                except (ValueError, TypeError) as e: # Catch parsing errors for string or other issues
                    self.logger.warning(f"预览时无法解析或格式化日期时间: {view_time_obj}, Error: {e}")
                    # display_browsed_at 保持 'N/A'

            # 格式化显示 (使用 HTML)
            preview_html = f"""
            <p><b>标题:</b> {title}</p>
            <p><b>来源:</b> {source}</p>
            <p><b>链接:</b> <a href="{link}">{link}</a></p>
            <p><b>浏览时间:</b> {display_browsed_at}</p>
            """
            self.preview_browser.setHtml(preview_html)
            # 确保文本颜色适应主题
            palette = self.preview_browser.palette()
            palette.setColor(QPalette.ColorRole.Text, self.palette().color(QPalette.ColorRole.Text))
            self.preview_browser.setPalette(palette)
        else:
            self.preview_browser.setHtml("<p style='color: red;'>无法加载所选项的详细信息。</p>")
            # 确保文本颜色适应主题
            palette = self.preview_browser.palette()
            palette.setColor(QPalette.ColorRole.Text, self.palette().color(QPalette.ColorRole.Text))
            self.preview_browser.setPalette(palette)
            self.logger.warning(f"选中的列表项数据无效: {entry_data}")

    def _delete_selected(self):
        """删除选中的历史记录条目"""
        if not self.view_model: # MODIFIED
            self.logger.error("ViewModel 无效，无法删除历史记录")
            return

        selected_indexes = self.history_list.selectedIndexes()
        if not selected_indexes:
            QMessageBox.information(self, "提示", "请先选择要删除的历史记录。")
            return

        # MODIFIED: Adapt to call ViewModel method.
        # This requires `delete_history_entries` to be implemented in ViewModel
        # and further in HistoryService. For now, it might be a placeholder.
        # entries_to_delete = [item.data(Qt.UserRole) for item in selected_items if item.data(Qt.UserRole)]
        # links_to_delete = [entry.get('link') for entry in entries_to_delete if entry.get('link')]
        
        # Placeholder if ViewModel method not ready / to avoid error
        # if hasattr(self.view_model, 'delete_history_entries_by_link'):
        #    self.view_model.delete_history_entries_by_link(links_to_delete)
        # else:
        #    QMessageBox.warning(self, "功能暂未实现", "通过ViewModel删除历史记录的功能正在开发中。")
        #    self.logger.warning("Attempted to delete history, but ViewModel method is not fully implemented/connected.")

        # For now, let's assume a method that takes the full entry dicts or specific IDs
        # history_entries_data = [item.data(Qt.UserRole) for item in selected_items if item.data(Qt.UserRole)]
        # For QListView, we get data from the model using the selected indexes
        model = self.view_model.get_model()
        # We only need unique rows, as one item can have multiple columns selected if the view supports it (though our model is 1D)
        unique_rows = sorted(list(set(index.row() for index in selected_indexes)))
        history_entries_data = [model.data(model.index(row, 0), Qt.UserRole) for row in unique_rows]
        history_entries_data = [entry for entry in history_entries_data if entry is not None] # Filter out None if any index was invalid

        if not history_entries_data:
            return
            
        reply = QMessageBox.question(self, "确认删除",
                                     f"确定要删除选中的 {len(history_entries_data)} 条历史记录吗？此操作不可恢复。",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logger.info(f"请求 ViewModel 删除 {len(history_entries_data)} 条历史记录...")
            if hasattr(self.view_model, 'delete_history_entries'):
                 # Assuming delete_history_entries expects a list of dicts or IDs
                 # Let's assume it expects list of dicts as stored in UserRole
                # self.view_model.delete_history_entries(history_entries_data) # This method is not in the current VM
                # We need to call delete_history_item_at_index for each item, or implement a bulk delete in VM
                # For now, let's try deleting one by one by index (row)
                # This is inefficient for multiple selections and should be improved in ViewModel
                # The ViewModel's delete_history_item_at_index expects a single model index (row number)
                
                # We need to delete from highest index to lowest to avoid index shifting issues if list reorders immediately
                for row in sorted(unique_rows, reverse=True):
                    self.logger.info(f"Calling delete_history_item_at_index for row: {row}")
                    self.view_model.delete_history_item_at_index(row)
                # After deletion, the ViewModel should emit history_changed, which will call _on_history_vm_updated
                # which in turn calls setModel if the model is valid. A full refresh is handled by the VM's load_history.
                # If deletions are frequent, consider a more optimized ViewModel method.
            else:
                self.logger.warning("ViewModel does not have 'delete_history_entries' method.")
                QMessageBox.information(self, "提示", "删除功能暂不可用。")
            # self._refresh_history() # ViewModel should ideally handle refreshing the list after deletion via signal

    def _clear_all(self):
        """清空所有历史记录"""
        if not self.view_model: # MODIFIED
            self.logger.error("ViewModel 无效，无法清空历史记录")
            return

        reply = QMessageBox.question(self, "确认清空",
                                     "确定要清空所有浏览历史记录吗？此操作不可恢复。",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logger.info("请求 ViewModel 清空所有历史记录...")
            self.view_model.clear_history() # This exists in VM
            # ViewModel's clear_history should trigger a load_history or emit history_changed itself.
            # self._refresh_history() # ViewModel should handle refresh

    def reject(self):
        """Override reject to ensure proper closing and cleanup for non-modal dialog."""
        self.logger.debug("BrowsingHistoryPanel: reject() called. Calling super().reject(), deleteLater(), and emitting signal.")
        super().reject() # Try default reject behavior (hiding)
        self.deleteLater() # Schedule deletion
        self.rejected_and_deleted.emit() # Notify manager

    def closeEvent(self, event):
        """Override close event to ensure proper closing."""
        self.logger.debug("BrowsingHistoryPanel: closeEvent triggered.")
        # 确保事件被接受
        event.accept() # 明确接受关闭事件
        # 发出信号并安排删除
        self.rejected_and_deleted.emit() # 通知管理器
        self.deleteLater() # 安排删除

    def _close_dialog(self):
        """Explicitly closes the dialog."""
        self.logger.debug("BrowsingHistoryPanel: _close_dialog called (likely from main window closing). Emitting rejected and scheduling deleteLater.")
        self.rejected_and_deleted.emit() # Emit standard rejected signal
        # self.rejected_and_deleted.emit() # Custom signal not standard for QDialog, consider if needed
        self.deleteLater() # Ensure it gets cleaned up

    # Helper function for updating button state, to be connected to selectionChanged
    def _update_delete_button_state(self):
        """Enables or disables the delete button based on current selection."""
        has_selection = bool(self.history_list.selectedIndexes())
        self.delete_button.setEnabled(has_selection)

    def _connect_history_list_signals(self):
        """Connects signals for history_list, typically called via QTimer if selectionModel was initially None."""
        self.logger.debug("Attempting to connect history_list signals via _connect_history_list_signals.")
        if self.history_list:
            selection_model = self.history_list.selectionModel()
            if selection_model:
                self.logger.info("Successfully obtained selectionModel. Connecting signals.")
                selection_model.currentChanged.connect(self._on_history_selection_changed)
                selection_model.selectionChanged.connect(self._update_delete_button_state)
            else:
                self.logger.error("Critical: history_list.selectionModel() is STILL None even after QTimer delay. Signals not connected.")
        else:
            self.logger.error("Critical: self.history_list is None in _connect_history_list_signals. Cannot connect signals.")

    # ADDED: Slot for double click
    @pyqtSlot(QModelIndex)
    def _on_history_item_double_clicked(self, index: QModelIndex):
        """Handles double-click on a history item (for QListView)."""
        if not index.isValid():
            return

        self.logger.info(f"PANEL: _on_history_item_double_clicked: self.view_model instance: {self.view_model} (ID: {id(self.view_model)})")
        if hasattr(self.view_model, 'request_news_detail_display'):
            self.logger.info(f"PANEL: self.view_model has attribute 'request_news_detail_display': {getattr(self.view_model, 'request_news_detail_display')}")
        else:
            self.logger.error(f"PANEL: self.view_model DOES NOT HAVE attribute 'request_news_detail_display'")

        entry_data = self.view_model.get_model().data(index, Qt.UserRole)
        if entry_data and isinstance(entry_data, dict):
            article_id = entry_data.get('article_id')
            if article_id is not None:
                self.logger.info(f"PANEL: 历史记录项被双击: Article ID={article_id}, Data: {entry_data}")
                self.logger.info(f"PANEL: Attempting to call self.view_model.request_news_detail_display({article_id})")
                self.view_model.request_news_detail_display(article_id)
                self.logger.info(f"PANEL: Call to self.view_model.request_news_detail_display({article_id}) has completed.")
            else:
                self.logger.warning(f"双击的历史记录项缺少 article_id: {entry_data}")
        else:
            self.logger.warning(f"双击的历史记录项数据无效或不是字典: {entry_data}")

# --- 用于独立测试 ---
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication

    logging.basicConfig(level=logging.DEBUG)

    # 创建一个模拟的 Storage 对象
    class MockStorage:
        def __init__(self):
            self.history = [
                {"link": "http://example.com/1", "title": "示例新闻标题1", "source_name": "来源A", "browsed_at": datetime.now().isoformat()},
                {"link": "http://example.com/2", "title": "这是一个非常非常非常非常非常非常非常非常长的示例新闻标题2", "source_name": "来源B", "browsed_at": "2025-04-01T10:00:00"},
                {"link": "http://example.com/3", "title": "示例新闻标题3", "source_name": "来源C", "browsed_at": "2025-03-31T15:30:00"},
            ]
            self.logger = logging.getLogger('MockStorage')

        def load_history(self):
            self.logger.info("MockStorage: load_history called")
            return self.history[:]

        def delete_history_entry(self, link):
            self.logger.info(f"MockStorage: delete_history_entry called for {link}")
            original_len = len(self.history)
            self.history = [item for item in self.history if item.get('link') != link]
            return len(self.history) < original_len

        def clear_all_history(self):
            self.logger.info("MockStorage: clear_all_history called")
            self.history = []
            return True

    app = QApplication(sys.argv)
    mock_storage = MockStorage()
    dialog = BrowsingHistoryPanel(mock_storage)
    dialog.show()
    sys.exit(app.exec_())