# src/ui/browsing_history_panel.py
"""
浏览历史记录面板

显示用户查看过的单条新闻记录，并提供管理功能。
"""

import logging
from datetime import datetime
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QLabel, QTextBrowser, QPushButton,
                             QSplitter, QMessageBox, QSizePolicy, QWidget) # <-- 添加了 QWidget
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QDesktopServices, QPalette # <-- 添加 QPalette 和 QDesktopServices

# 假设 NewsStorage 在父级目录的 storage 中
try:
    from ..storage.news_storage import NewsStorage
except ImportError:
    # 处理可能的导入错误，例如在独立运行此文件进行测试时
    NewsStorage = None
    logging.getLogger(__name__).error("无法导入 NewsStorage！")

class BrowsingHistoryPanel(QDialog):
    """浏览历史记录对话框"""

    def __init__(self, storage: NewsStorage, parent=None):
        super().__init__(parent)
        self.setWindowTitle("浏览历史记录")
        self.setMinimumSize(700, 500)
        # 设置窗口标志，移除问号按钮，添加最大化按钮
        flags = self.windowFlags()
        flags &= ~Qt.WindowContextHelpButtonHint
        flags |= Qt.WindowMaximizeButtonHint
        self.setWindowFlags(flags)

        self.logger = logging.getLogger('news_analyzer.ui.browsing_history')
        if not storage or not isinstance(storage, NewsStorage):
            self.logger.error("传入的 storage 无效！历史记录功能将无法使用。")
            # 可以选择禁用控件或显示错误消息
            QMessageBox.critical(self, "错误", "存储服务不可用，无法加载浏览历史。")
            # 延迟关闭对话框，以便用户看到消息
            # QTimer.singleShot(0, self.reject) # 需要导入 QTimer
            # return # 提前返回可能导致后续 _init_ui 访问 None 属性
            self.storage = None # 明确设为 None
        else:
            self.storage = storage

        self._init_ui()
        if self.storage: # 仅在 storage 有效时加载
            self._refresh_history()

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

        self.history_list = QListWidget()
        self.history_list.setAlternatingRowColors(True)
        self.history_list.setSelectionMode(QListWidget.ExtendedSelection) # 允许多选
        self.history_list.setStyleSheet("QListWidget::item { padding: 5px; }")
        self.history_list.currentItemChanged.connect(self._on_history_selected)
        self.history_list.itemSelectionChanged.connect(
            lambda: self.delete_button.setEnabled(len(self.history_list.selectedItems()) > 0)
        )
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
        close_button.clicked.connect(self.accept) # 点击关闭按钮接受对话框

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        # 禁用控件（如果 storage 无效）
        if not self.storage:
            self.refresh_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.clear_all_button.setEnabled(False)
            self.history_list.setEnabled(False)

    def _refresh_history(self):
        """从 storage 加载历史记录并填充列表"""
        if not self.storage:
            self.logger.warning("Storage 无效，无法刷新历史记录")
            self.history_list.clear()
            self.preview_browser.setHtml("<p style='color: red;'>错误：无法加载历史记录存储。</p>") # 更新预览
            # 确保文本颜色适应主题
            palette = self.preview_browser.palette()
            palette.setColor(palette.Text, self.palette().color(palette.Text))
            self.preview_browser.setPalette(palette)
            return

        self.logger.info("刷新浏览历史列表...")
        self.history_list.clear()
        self.preview_browser.setHtml("") # 清空预览
        self.preview_browser.setPlaceholderText("请在左侧选择一条历史记录查看详情") # 重置占位符
        self.delete_button.setEnabled(False) # 刷新后禁用删除按钮

        try:
            history_data = self.storage.load_history()
            self.logger.info(f"加载到的浏览历史数据: {history_data}") # <-- 添加日志记录加载的数据
            if not history_data:
                self.logger.info("没有找到浏览历史记录。")
                # 可以选择添加一个提示项
                item = QListWidgetItem("没有历史记录")
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable) # 不可选
                self.history_list.addItem(item)
                return

            self.logger.debug(f"加载了 {len(history_data)} 条历史记录，准备填充列表...")
            for entry in history_data:
                title = entry.get('title', '无标题')
                source = entry.get('source_name', '未知来源')
                browsed_at_str = entry.get('viewed_at', '') # 修正：使用 viewed_at
                try:
                    # 尝试将 ISO 格式字符串转为更友好的格式
                    browsed_dt = datetime.fromisoformat(browsed_at_str)
                    display_time = browsed_dt.strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    display_time = browsed_at_str # 如果解析失败，显示原始字符串

                display_text = f"{title}\n来源: {source} - 时间: {display_time}"
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, entry) # 将完整字典存入 UserRole
                self.history_list.addItem(item)

            self.logger.info(f"历史记录列表填充完成，共 {self.history_list.count()} 项。")

        except Exception as e:
            self.logger.error(f"刷新历史记录时出错: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"加载历史记录失败: {e}")

    def _on_history_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        """当列表选中项改变时，更新预览区域"""
        if not current or not current.flags() & Qt.ItemIsSelectable: # 检查是否可选
            self.preview_browser.setHtml("")
            self.preview_browser.setPlaceholderText("请在左侧选择一条历史记录查看详情")
            return

        entry_data = current.data(Qt.UserRole)
        if isinstance(entry_data, dict):
            title = entry_data.get('title', 'N/A')
            link = entry_data.get('link', '#') # 提供默认值以防链接不存在
            source = entry_data.get('source_name', 'N/A')
            browsed_at_str = entry_data.get('viewed_at', 'N/A') # 修正：使用 viewed_at 获取原始字符串

            # 解析和格式化浏览时间以供预览
            display_browsed_at = 'N/A' # 默认值
            if browsed_at_str and browsed_at_str != 'N/A':
                try:
                    browsed_dt = datetime.fromisoformat(browsed_at_str)
                    display_browsed_at = browsed_dt.strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    self.logger.warning(f"预览时无法解析日期时间字符串: {browsed_at_str}")
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
            palette.setColor(palette.Text, self.palette().color(palette.Text))
            self.preview_browser.setPalette(palette)
        else:
            self.preview_browser.setHtml("<p style='color: red;'>无法加载所选项的详细信息。</p>")
            # 确保文本颜色适应主题
            palette = self.preview_browser.palette()
            palette.setColor(palette.Text, self.palette().color(palette.Text))
            self.preview_browser.setPalette(palette)
            self.logger.warning(f"选中的列表项数据无效: {entry_data}")

    def _delete_selected(self):
        """删除选中的历史记录条目"""
        if not self.storage:
            self.logger.error("Storage 无效，无法删除历史记录")
            return

        selected_items = self.history_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择要删除的历史记录。")
            return

        reply = QMessageBox.question(self, "确认删除",
                                     f"确定要删除选定的 {len(selected_items)} 条历史记录吗？此操作不可恢复。",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.logger.info(f"开始删除 {len(selected_items)} 条选中的历史记录...")
            deleted_count = 0
            errors = []
            links_to_delete = []
            for item in selected_items:
                entry_data = item.data(Qt.UserRole)
                if isinstance(entry_data, dict) and 'link' in entry_data:
                    links_to_delete.append(entry_data['link'])
                else:
                    self.logger.warning(f"跳过无效的选中项数据进行删除: {entry_data}")

            # 批量删除（如果 storage 支持）或逐条删除
            for link in links_to_delete:
                 success = self.storage.delete_history_entry(link)
                 if success:
                     deleted_count += 1
                     self.logger.debug(f"成功删除历史记录: {link}")
                 else:
                     errors.append(link) # 记录删除失败的链接
                     self.logger.warning(f"删除历史记录失败: {link}")


            self.logger.info(f"删除操作完成，成功删除 {deleted_count} 条，失败 {len(errors)} 条。")
            if errors:
                QMessageBox.warning(self, "部分删除失败", f"以下链接对应的记录删除失败:\n- " + "\n- ".join(errors))

            self._refresh_history() # 刷新列表显示

    def _clear_all(self):
        """清空所有历史记录"""
        if not self.storage:
            self.logger.error("Storage 无效，无法清空历史记录")
            return

        reply = QMessageBox.question(self, "确认清空",
                                     "确定要清空所有浏览历史记录吗？此操作不可恢复！",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.logger.warning("开始清空所有浏览历史记录...")
            success = self.storage.clear_all_history()
            if success:
                self.logger.info("所有浏览历史记录已清空。")
                QMessageBox.information(self, "成功", "已清空所有浏览历史记录。")
                self._refresh_history() # 刷新列表
            else:
                self.logger.error("清空浏览历史记录失败。")
                QMessageBox.critical(self, "错误", "清空历史记录时发生错误。")

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