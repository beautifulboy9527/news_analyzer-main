# news_analyzer/ui/refresh_dialog.py
import logging
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton
from PyQt5.QtCore import Qt, pyqtSlot

class RefreshProgressDialog(QDialog):
    """显示刷新进度的对话框"""

    def __init__(self, total_sources, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.refresh_dialog')
        self.setWindowTitle("刷新新闻源")
        self.setMinimumWidth(350)
        self.setModal(True) # 设置为模态对话框

        layout = QVBoxLayout(self)

        self.status_label = QLabel(f"准备刷新 {total_sources} 个新闻源...")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(total_sources)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.cancel_button = QPushButton("取消")
        # 取消按钮的信号连接将在 MainWindow 中完成，连接到 AppService 的取消方法
        layout.addWidget(self.cancel_button, alignment=Qt.AlignRight)

        self._is_cancelled = False # 用于跟踪是否是用户主动取消

    @pyqtSlot(int, int)
    def update_progress(self, current, total):
        """更新进度条和状态标签"""
        # 可能在刷新过程中源的总数发生变化（虽然不太可能），确保最大值正确
        if self.progress_bar.maximum() != total:
            self.progress_bar.setMaximum(total)
            self.status_label.setText(f"正在刷新 (总数更新): {current}/{total}")
        else:
             self.status_label.setText(f"正在刷新: {current}/{total}")
        self.logger.info(f"对话框收到 update_progress 信号: {current}/{total}") # 添加日志
        self.progress_bar.setValue(current)
        self.logger.debug(f"对话框更新进度: {current}/{total}")

    @pyqtSlot(list) # 接收完成信号传递的新闻列表 (虽然对话框本身不用)
    def mark_as_complete(self, news_articles):
        """标记为完成并准备关闭"""
        self.status_label.setText(f"刷新完成！获取 {len(news_articles)} 条新闻。")
        self.cancel_button.setEnabled(False)
        self.logger.info("标记为完成，立即调用 accept()")
        self.accept() # 移除延迟，立即关闭

    @pyqtSlot()
    def mark_as_cancelled(self):
        """标记为已取消并准备关闭"""
        self.status_label.setText("刷新已取消。")
        self.cancel_button.setEnabled(False)
        self._is_cancelled = True
        self.logger.info("标记为取消，立即调用 reject()")
        self.reject() # 移除延迟，立即关闭

    def closeEvent(self, event):
        """处理对话框关闭事件（例如点击X）"""
        if not self._is_cancelled and self.cancel_button.isEnabled():
            # 如果用户尝试关闭但未完成也未取消，触发取消逻辑
            self.logger.info("用户尝试关闭刷新对话框，触发取消操作")
            self.cancel_button.click() # 模拟点击取消按钮
            event.ignore() # 阻止立即关闭，等待取消完成信号
        else:
            self.logger.debug("接受对话框关闭事件")
            event.accept()