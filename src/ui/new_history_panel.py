import sys
from typing import List, TYPE_CHECKING
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMenu, QMessageBox, QApplication
)
from PyQt5.QtCore import Qt, pyqtSlot

if TYPE_CHECKING:
    from src.ui.viewmodels.browsing_history_viewmodel import BrowsingHistoryViewModel, BrowsingHistory

class NewHistoryPanel(QWidget):
    """
    新的浏览历史记录面板 UI。
    使用 QTableWidget 显示历史记录，并提供刷新、清空和删除单条记录的功能。
    """
    def __init__(self, view_model: 'BrowsingHistoryViewModel', parent=None):
        super().__init__(parent)
        self.view_model = view_model
        self._init_ui()
        self._connect_signals()
        # 初始加载历史记录
        self.view_model.load_history()

    def _init_ui(self):
        """初始化 UI 元素和布局。"""
        layout = QVBoxLayout(self)

        # 按钮区域
        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton("刷新")
        self.clear_button = QPushButton("清空所有记录")
        button_layout.addWidget(self.refresh_button)
        button_layout.addStretch()
        button_layout.addWidget(self.clear_button)
        layout.addLayout(button_layout)

        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4) # 增加 Link 列用于内部处理
        self.history_table.setHorizontalHeaderLabels(["标题", "来源", "查看时间", "Link"])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch) # 标题列拉伸
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.history_table.setColumnHidden(3, True) # 隐藏 Link 列
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers) # 禁止编辑
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows) # 整行选择
        self.history_table.setSelectionMode(QTableWidget.SingleSelection) # 单选
        self.history_table.setContextMenuPolicy(Qt.CustomContextMenu)
        layout.addWidget(self.history_table)

        self.setLayout(layout)

    def _connect_signals(self):
        """连接 ViewModel 的信号和 UI 控件的事件。"""
        self.view_model.history_updated.connect(self._update_history_list)
        self.view_model.error_occurred.connect(self._show_error_message)

        self.refresh_button.clicked.connect(self.view_model.load_history)
        self.clear_button.clicked.connect(self._confirm_clear_all_history)
        self.history_table.customContextMenuRequested.connect(self._show_context_menu)

    @pyqtSlot(list)
    def _update_history_list(self, history_items: List['BrowsingHistory']):
        """更新表格中的历史记录数据。"""
        self.history_table.setRowCount(0) # 清空表格
        self.history_table.setRowCount(len(history_items))

        for row, item in enumerate(history_items):
            title_item = QTableWidgetItem(item.title)
            source_item = QTableWidgetItem(item.source_name)
            # 格式化时间
            viewed_at_str = item.viewed_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(item.viewed_at, datetime) else str(item.viewed_at)
            viewed_at_item = QTableWidgetItem(viewed_at_str)
            link_item = QTableWidgetItem(item.link) # 存储 link 用于删除

            self.history_table.setItem(row, 0, title_item)
            self.history_table.setItem(row, 1, source_item)
            self.history_table.setItem(row, 2, viewed_at_item)
            self.history_table.setItem(row, 3, link_item) # 存储 link

        # 如果需要，可以在这里调整列宽
        # self.history_table.resizeColumnsToContents()

    @pyqtSlot(str)
    def _show_error_message(self, error_msg: str):
        """显示错误消息对话框。"""
        QMessageBox.warning(self, "错误", f"发生错误：\n{error_msg}")

    def _confirm_clear_all_history(self):
        """显示确认对话框，确认后清空所有历史记录。"""
        reply = QMessageBox.question(self, '确认清空', '确定要清空所有浏览历史记录吗？此操作不可恢复。',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.view_model.clear_all_history()

    def _show_context_menu(self, position):
        """在表格上显示右键菜单。"""
        selected_items = self.history_table.selectedItems()
        if not selected_items:
            return

        menu = QMenu()
        delete_action = menu.addAction("删除此条记录")
        action = menu.exec_(self.history_table.mapToGlobal(position))

        if action == delete_action:
            selected_row = self.history_table.currentRow()
            link_item = self.history_table.item(selected_row, 3) # 获取隐藏的 Link 列
            if link_item:
                link_to_delete = link_item.text()
                self._confirm_delete_item(link_to_delete)

    def _confirm_delete_item(self, link: str):
        """显示确认对话框，确认后删除单条历史记录。"""
        # 可以选择性地加入确认步骤
        # reply = QMessageBox.question(self, '确认删除', '确定要删除这条历史记录吗？',
        #                              QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        # if reply == QMessageBox.Yes:
        #     self.view_model.delete_history_item(link)
        # 或者直接删除
        self.view_model.delete_history_item(link)

# 用于独立测试 UI (可选)
if __name__ == '__main__':
    # 创建一个 Mock ViewModel 用于测试
    class MockBrowsingHistoryViewModel:
        from PyQt5.QtCore import QObject, pyqtSignal
        history_updated = pyqtSignal(list)
        error_occurred = pyqtSignal(str)

        def __init__(self):
            self._history = [
                BrowsingHistory(title="测试新闻1", link="http://example.com/1", source_name="来源A", viewed_at=datetime.now()),
                BrowsingHistory(title="测试新闻2-这是一个非常长的标题用于测试自动拉伸的效果", link="http://example.com/2", source_name="来源B", viewed_at=datetime(2024, 1, 1, 10, 30, 0)),
            ]

        def load_history(self):
            print("Mock: load_history called")
            self.history_updated.emit(self._history)

        def delete_history_item(self, link: str):
            print(f"Mock: delete_history_item called with link: {link}")
            self._history = [item for item in self._history if item.link != link]
            self.history_updated.emit(self._history)
            # self.error_occurred.emit("测试错误消息") # 测试错误显示

        def clear_all_history(self):
            print("Mock: clear_all_history called")
            self._history = []
            self.history_updated.emit(self._history)

    # 需要定义 BrowsingHistory 数据类才能运行测试
    from dataclasses import dataclass
    @dataclass
    class BrowsingHistory:
        title: str
        link: str
        source_name: str
        viewed_at: datetime


    app = QApplication(sys.argv)
    mock_vm = MockBrowsingHistoryViewModel()
    main_window = NewHistoryPanel(mock_vm)
    main_window.setWindowTitle("New History Panel Test")
    main_window.setGeometry(100, 100, 600, 400)
    main_window.show()
    sys.exit(app.exec_())