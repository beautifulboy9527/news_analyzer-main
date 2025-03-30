"""
历史新闻面板

提供浏览和加载已保存的历史新闻功能。
"""

import os
import json
import logging
from datetime import datetime
# REMOVED incorrect insertion on line 11

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QLabel, QTextBrowser,
                             QPushButton, QSplitter, QComboBox, QFrame,
                             QMessageBox, QFileDialog, QProgressBar, QDialog, # Added QDialog here
                             QTabWidget, QGridLayout)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer # 移除 QEvent

# 1.1 修改基类为 QDialog
class HistoryPanel(QDialog):
    """历史记录管理对话框""" # 更新文档字符串

    # 1.1 移除不再需要的信号
    # history_loaded = pyqtSignal(list)

    def __init__(self, storage, parent=None):
        super().__init__(parent) # 调用 QDialog 的构造函数
        self.setWindowTitle("历史记录管理") # 设置对话框标题
        self.setMinimumSize(700, 500) # 设置对话框最小尺寸
        # 移除问号按钮并添加最大化按钮
        flags = self.windowFlags()
        flags &= ~Qt.WindowContextHelpButtonHint # 移除问号
        flags |= Qt.WindowMaximizeButtonHint    # 添加最大化
        self.setWindowFlags(flags)

        self.logger = logging.getLogger('news_analyzer.ui.history_panel')
        self.storage = storage

        self.read_news_ids = set() # 用于存储已读新闻的ID

        # 从 storage 对象获取 news 目录路径，确保一致性
        self.news_dir = os.path.join(self.storage.data_dir, "news")
        # 确保目录存在 (虽然 storage 可能已创建，但再次检查无害)
        if not os.path.exists(self.news_dir):
             try:
                 os.makedirs(self.news_dir, exist_ok=True)
                 self.logger.info(f"创建缺失的新闻目录: {self.news_dir}")
             except Exception as e:
                 self.logger.error(f"创建新闻目录失败: {str(e)}")
                 # 如果创建失败，后续扫描会出错，但至少日志记录了问题

        self.logger.info(f"使用的历史新闻目录: {self.news_dir}") # 更新日志信息

        self._init_ui()

    def set_read_ids(self, read_ids):
        """设置已读新闻ID集合

        Args:
            read_ids (set): 包含已读新闻链接的集合
        """
        self.read_news_ids = read_ids
        # 当已读ID更新时，如果当前正显示历史新闻列表，可以考虑刷新显示
        # 但更简单的方式是在加载列表时 (_on_history_selected) 直接使用最新的集合

    def _init_ui(self):
        """初始化UI"""
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(10) # 减小主布局间距
        layout.setContentsMargins(10, 10, 10, 10) # 设置边距

        # # 标题标签 (REMOVED)
        # title_label = QLabel("历史记录")
        # title_label.setStyleSheet("""...""")
        # layout.addWidget(title_label)

        # 创建标签页控件 (REMOVED)
        # tab_widget = QTabWidget()
        # tab_widget.setStyleSheet("""...""")

        # 创建浏览标签页 (REMOVED - Logic will be integrated directly)
        # browse_tab = QWidget()
        # self._setup_browse_tab(browse_tab)
        # tab_widget.addTab(browse_tab, "浏览历史")

        # # 创建导入/导出标签页 (REMOVED)
        # ...

        # layout.addWidget(tab_widget, 1)  # REMOVED

        # --- Browse History UI Integrated ---
        # 控制面板 (精简按钮和优化样式)
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10) # 增加按钮间距

        # 统一的按钮样式
        button_style = """
            QPushButton {
                background-color: #f8f9fa; /* 更亮的背景 */
                border: 1px solid #dee2e6; /* 更浅的边框 */
                border-radius: 4px;
                padding: 6px 14px; /* 调整内边距 */
                color: #495057; /* 深灰色文字 */
                font-size: 9pt; /* 稍小字体 */
            }
            QPushButton:hover {
                background-color: #e9ecef; /* 悬停效果 */
                border-color: #ced4da;
            }
            QPushButton:pressed {
                background-color: #dee2e6; /* 按下效果 */
            }
            QPushButton:disabled {
                background-color: #f8f9fa;
                color: #adb5bd;
                border-color: #e9ecef;
            }
        """
        delete_button_style = button_style + """
            QPushButton { color: #dc3545; } /* 删除按钮红色文字 */
            QPushButton:hover { background-color: #f8d7da; border-color: #f5c6cb; } /* 悬停淡红色 */
            QPushButton:pressed { background-color: #f1b0b7; }
        """


        # 刷新按钮 (放左侧)
        self.refresh_button = QPushButton("刷新列表")
        self.refresh_button.setStyleSheet(button_style)
        self.refresh_button.setToolTip("重新加载浏览历史列表")
        self.refresh_button.clicked.connect(self._refresh_history_list)
        control_layout.addWidget(self.refresh_button)

        control_layout.addStretch() # 将删除按钮推到右侧

        # 删除选中按钮 (放右侧)
        self.delete_button = QPushButton("删除选中")
        self.delete_button.setStyleSheet(delete_button_style) # 应用删除样式
        self.delete_button.setToolTip("删除选中的浏览记录")
        self.delete_button.clicked.connect(self._delete_history_record)
        self.delete_button.setEnabled(False)
        control_layout.addWidget(self.delete_button)

        # 清除全部按钮 (放右侧)
        self.clear_all_button = QPushButton("清除全部")
        self.clear_all_button.setStyleSheet(delete_button_style) # 应用删除样式
        self.clear_all_button.setToolTip("清除所有浏览历史记录（不可恢复）")
        self.clear_all_button.clicked.connect(self.clear_all_history_records)
        control_layout.addWidget(self.clear_all_button)

        layout.addLayout(control_layout) # Correctly add to _init_ui's layout

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1) # Correctly add to _init_ui's layout

        # 左侧浏览历史列表
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.history_list = QListWidget()
        self.history_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.history_list.setAlternatingRowColors(True)
        self.history_list.currentItemChanged.connect(self._on_history_selected)
        self.history_list.setStyleSheet("""
            QListWidget { border: 1px solid #E0E0E0; border-radius: 4px; background-color: white; }
            QListWidget::item { padding: 5px; border-bottom: 1px solid #F5F5F5; }
            QListWidget::item:selected { background-color: #E3F2FD; color: #1976D2; }
        """)
        left_layout.addWidget(self.history_list)

        self.history_list.itemSelectionChanged.connect(
            lambda: self.delete_button.setEnabled(len(self.history_list.selectedItems()) > 0)
        )
        splitter.addWidget(left_panel)

        # 右侧预览面板
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.info_label = QLabel("请选择浏览历史条目")
        self.info_label.setStyleSheet("color: #757575; font-style: italic; padding: 5px;")
        right_layout.addWidget(self.info_label)

        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)
        self.preview.setStyleSheet("""
            QTextBrowser { border: 1px solid #E0E0E0; border-radius: 4px; background-color: white; padding: 10px; }
        """)
        right_layout.addWidget(self.preview)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 400]) # 调整初始比例
        # --- Browse History UI End ---

        # 使用 QTimer 延迟初始刷新，避免 RuntimeError (Keep this for now)
        QTimer.singleShot(0, self._perform_initial_refresh)

    def _perform_initial_refresh(self):
        """执行初始的列表刷新"""
        self.logger.debug("执行延迟的初始列表刷新")
        try:
            # 确保相关控件已创建
            if hasattr(self, 'history_list'):
                 self._refresh_history_list()
            else:
                 self.logger.warning("_perform_initial_refresh: history_list 不存在")

            # 移除 export_combo 检查，因为它不再属于这个面板
            # if hasattr(self, 'export_combo'):
            #      self._refresh_export_combo()
            # else:
            #      self.logger.warning("_perform_initial_refresh: export_combo 不存在")

        except RuntimeError as e:
             # 捕获可能的 RuntimeError，以防万一
             self.logger.error(f"延迟刷新时仍然发生 RuntimeError: {e}")
        except Exception as e:
            self.logger.error(f"延迟刷新时发生未知错误: {e}", exc_info=True)

    # def _setup_browse_tab(self, tab): # REMOVED Method Definition
    #     """设置浏览历史标签页""" # REMOVED
    #     layout = QVBoxLayout(tab) # REMOVED
    #     layout.setContentsMargins(0, 10, 0, 0) # REMOVED
    #
    #     # 控制面板 # REMOVED
    #     control_layout = QHBoxLayout() # REMOVED
    #
    #     # 刷新按钮 (用于刷新浏览历史) # REMOVED
    #     self.refresh_button = QPushButton("刷新列表") # REMOVED
    #     self.refresh_button.setFixedSize(100, 30) # REMOVED
    #     self.refresh_button.setStyleSheet("""...""") # REMOVED
    #     self.refresh_button.clicked.connect(self._refresh_history_list) # REMOVED
    #     control_layout.addWidget(self.refresh_button) # REMOVED
    #
    #
    #     # 全选按钮 # REMOVED
    #     self.select_all_button = QPushButton("全选") # REMOVED
    #     self.select_all_button.setFixedSize(80, 30) # REMOVED
    #     self.select_all_button.setStyleSheet("""...""") # REMOVED
    #     self.select_all_button.clicked.connect(self._select_all_history) # REMOVED
    #     control_layout.addWidget(self.select_all_button) # REMOVED
    #
    #     # 取消全选按钮 # REMOVED
    #     self.deselect_all_button = QPushButton("取消全选") # REMOVED
    #     self.deselect_all_button.setFixedSize(100, 30) # REMOVED
    #     self.deselect_all_button.setStyleSheet("""...""") # REMOVED
    #     self.deselect_all_button.clicked.connect(self._deselect_all_history) # REMOVED
    #     control_layout.addWidget(self.deselect_all_button) # REMOVED
    #
    #     # 删除按钮 # REMOVED
    #     self.delete_button = QPushButton("删除记录") # REMOVED
    #     self.delete_button.setFixedSize(100, 30) # REMOVED
    #     self.delete_button.setStyleSheet("""...""") # REMOVED
    #     self.delete_button.clicked.connect(self._delete_history_record) # REMOVED
    #     self.delete_button.setEnabled(False) # REMOVED
    #     control_layout.addWidget(self.delete_button) # REMOVED
    #
    #     # 清除全部按钮 (NEW) # REMOVED
    #     self.clear_all_button = QPushButton("清除全部") # REMOVED
    #     self.clear_all_button.setFixedSize(100, 30) # REMOVED
    #     # 使用与删除按钮类似的警告样式 # REMOVED
    #     self.clear_all_button.setStyleSheet("""...""") # REMOVED
    #     self.clear_all_button.setToolTip("清除所有浏览历史记录（不可恢复）") # REMOVED
    #     self.clear_all_button.clicked.connect(self.clear_all_history_records) # Connect to the method # REMOVED
    #     control_layout.addWidget(self.clear_all_button) # REMOVED
    #
    #     control_layout.addStretch() # REMOVED
    #     layout.addLayout(control_layout) # REMOVED
    #
    #     # 创建分割器 - 左侧是浏览历史列表，右侧是预览 # REMOVED
    #     splitter = QSplitter(Qt.Horizontal) # REMOVED
    #
    #     # 左侧浏览历史列表 # REMOVED
    #     left_panel = QWidget() # REMOVED
    #     left_layout = QVBoxLayout(left_panel) # REMOVED
    #     left_layout.setContentsMargins(0, 0, 0, 0) # REMOVED
    #
    #     self.history_list = QListWidget() # REMOVED
    #     self.history_list.setSelectionMode(QListWidget.ExtendedSelection) # 启用多选 # REMOVED
    #     self.history_list.setAlternatingRowColors(True) # REMOVED
    #     self.history_list.currentItemChanged.connect(self._on_history_selected) # 更改为 currentItemChanged 信号 # REMOVED
    #     self.history_list.setStyleSheet("""...""") # REMOVED
    #     left_layout.addWidget(self.history_list) # REMOVED
    #
    #
    #     # 当选择变化时更新删除按钮状态 (移动到 history_list 创建之后) # REMOVED
    #     self.history_list.itemSelectionChanged.connect( # REMOVED
    #         lambda: self.delete_button.setEnabled(len(self.history_list.selectedItems()) > 0) # 根据是否有选中项来启用 # REMOVED
    #     ) # REMOVED
    #     # 右侧预览面板 # REMOVED
    #     right_panel = QWidget() # REMOVED
    #     right_layout = QVBoxLayout(right_panel) # REMOVED
    #     right_layout.setContentsMargins(0, 0, 0, 0) # REMOVED
    #
    #     # 信息标签 # REMOVED
    #     self.info_label = QLabel("请选择浏览历史条目") # REMOVED
    #     self.info_label.setStyleSheet("color: #757575; font-style: italic; padding: 5px;") # REMOVED
    #     right_layout.addWidget(self.info_label) # REMOVED
    #
    #     # 新闻详情预览 (保留) # REMOVED
    #     self.preview = QTextBrowser() # REMOVED
    #     self.preview.setOpenExternalLinks(True) # REMOVED
    #     self.preview.setStyleSheet("""...""") # REMOVED
    #     right_layout.addWidget(self.preview) # 让预览占据剩余空间 # REMOVED
    #
    #     # 设置面板到分割器 # REMOVED
    #     splitter.addWidget(left_panel) # REMOVED
    #     splitter.addWidget(right_panel) # REMOVED
    #
    #     # 设置初始宽度比例（例如，左:右 = 1:1 或根据需要调整） # REMOVED
    #     splitter.setSizes([1, 1]) # REMOVED
    #     layout.addWidget(splitter) # 将 splitter 添加到 browse_tab 的布局中 # REMOVED

    # def _setup_import_tab(self, tab): # REMOVED Method
    #     """设置导入/导出标签页""" # REMOVED
    #     layout = QVBoxLayout(tab) # REMOVED
    #     layout.setContentsMargins(10, 15, 10, 10) # 调整边距 # REMOVED
    #
    #     # 添加说明文字 # REMOVED
    #     instr_label = QLabel("在此页面中，您可以导入外部JSON新闻文件或导出现有的历史新闻批次文件。") # REMOVED
    #     instr_label.setWordWrap(True) # REMOVED
    #     instr_label.setStyleSheet("font-size: 14px; margin-bottom: 15px;") # REMOVED
    #     layout.addWidget(instr_label) # REMOVED
    #
    #     # --- 简化布局：移除 QFrame 容器 --- # REMOVED
    #
    #     # 导入部分 (直接添加到主 layout) # REMOVED
    #     import_title = QLabel("导入JSON新闻文件") # REMOVED
    #     import_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #1976D2; margin-top: 10px;") # 加点上边距 # REMOVED
    #     layout.addWidget(import_title) # REMOVED
    #
    #     import_desc = QLabel("选择一个JSON文件导入到系统。文件应包含新闻条目列表，将作为新的历史批次保存。") # REMOVED
    #     import_desc.setWordWrap(True) # REMOVED
    #     layout.addWidget(import_desc) # REMOVED
    #
    #     import_button = QPushButton("选择并导入JSON文件") # 保持局部变量，因为只用一次 # REMOVED
    #     import_button.setStyleSheet(""" # REMOVED
    #         QPushButton { # REMOVED
    #             background-color: #2196F3; # REMOVED
    #             color: white; # REMOVED
    #             border-radius: 4px; # REMOVED
    #             padding: 10px; # REMOVED
    #             font-weight: bold; # REMOVED
    #             margin-top: 10px; # REMOVED
    #         } # REMOVED
    #         QPushButton:hover { # REMOVED
    #             background-color: #1E88E5; # REMOVED
    #         } # REMOVED
    #     """) # REMOVED
    #     import_button.clicked.connect(self._import_news_file) # REMOVED
    #     layout.addWidget(import_button) # REMOVED
    #
    #     # 添加分隔线 # REMOVED
    #     separator = QFrame() # REMOVED
    #     separator.setFrameShape(QFrame.HLine) # REMOVED
    #     separator.setFrameShadow(QFrame.Sunken) # REMOVED
    #     separator.setStyleSheet("margin-top: 15px; margin-bottom: 15px;") # REMOVED
    #     layout.addWidget(separator) # REMOVED
    #
    #     # 导出部分 (直接添加到主 layout) # REMOVED
    #     export_title = QLabel("导出历史新闻批次") # REMOVED
    #     export_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #1976D2;") # REMOVED
    #     layout.addWidget(export_title) # REMOVED
    #
    #     export_desc = QLabel("选择并导出系统中的一个历史新闻批次文件。") # REMOVED
    #     export_desc.setWordWrap(True) # REMOVED
    #     layout.addWidget(export_desc) # REMOVED
    #
    #     # 创建历史文件下拉选择框 # REMOVED
    #     self.export_combo = QComboBox() # REMOVED
    #     self.export_combo.setStyleSheet(""" # REMOVED
    #         QComboBox { # REMOVED
    #             border: 1px solid #BDBDBD; # REMOVED
    #             border-radius: 4px; # REMOVED
    #             padding: 8px; # REMOVED
    #             background-color: white; # REMOVED
    #             margin-top: 5px; /* 加点上边距 */ # REMOVED
    #         } # REMOVED
    #     """) # REMOVED
    #     layout.addWidget(self.export_combo) # REMOVED
    #
    #     # 刷新和导出按钮 (使用 QHBoxLayout) # REMOVED
    #     button_layout = QHBoxLayout() # REMOVED
    #     button_layout.setContentsMargins(0, 5, 0, 0) # 调整按钮布局边距 # REMOVED
    #
    #     self.refresh_export_button = QPushButton("刷新列表") # 保持实例变量 # REMOVED
    #     # self.refresh_export_button.installEventFilter(self) # 移除事件过滤器 # REMOVED
    #     self.refresh_export_button.setStyleSheet(""" # REMOVED
    #         QPushButton { # REMOVED
    #             background-color: #ECEFF1; # REMOVED
    #             border: 1px solid #CFD8DC; # REMOVED
    #             border-radius: 4px; # REMOVED
    #             padding: 8px; # REMOVED
    #             color: #455A64; # REMOVED
    #         } # REMOVED
    #          QPushButton:hover { # REMOVED
    #             background-color: #CFD8DC; # REMOVED
    #         } # REMOVED
    #     """) # REMOVED
    #     # 恢复原始连接 # REMOVED
    #     self.refresh_export_button.clicked.connect(self._refresh_export_combo) # REMOVED
    #     button_layout.addWidget(self.refresh_export_button) # REMOVED
    #
    #     self.export_button = QPushButton("导出所选文件") # 保持实例变量 # REMOVED
    #     self.export_button.setStyleSheet(""" # REMOVED
    #         QPushButton { # REMOVED
    #             background-color: #2196F3; # REMOVED
    #             color: white; # REMOVED
    #             border-radius: 4px; # REMOVED
    #             padding: 8px; # REMOVED
    #             font-weight: bold; # REMOVED
    #         } # REMOVED
    #         QPushButton:hover { # REMOVED
    #             background-color: #1E88E5; # REMOVED
    #         } # REMOVED
    #     """) # REMOVED
    #     self.export_button.clicked.connect(self._export_selected_file) # REMOVED
    #     button_layout.addWidget(self.export_button) # REMOVED
    #
    #     layout.addLayout(button_layout) # 将按钮布局添加到主布局 # REMOVED
    #
    #     layout.addStretch() # 将所有内容推到顶部 # REMOVED

    def _refresh_export_combo(self):
        """刷新导出文件下拉框"""
        self.logger.debug("_refresh_export_combo 方法被调用") # 添加日志
        # 检查 self.export_combo 是否存在
        if not hasattr(self, 'export_combo'):
            self.logger.warning("尝试刷新不存在的 export_combo")
            return

        self.logger.debug("清空 export_combo")
        self.export_combo.clear()

        try:
            self.logger.debug(f"扫描目录: {self.news_dir}")
            # 确保目录存在
            if not os.path.exists(self.news_dir):
                self.logger.warning(f"导出目录不存在: {self.news_dir}")
                return

            # 获取所有JSON文件
            files = [f for f in os.listdir(self.news_dir) if f.endswith('.json')]
            self.logger.debug(f"找到 {len(files)} 个 .json 文件")
            files.sort(reverse=True)  # 最新的文件排在前面

            for filename in files:
                self.logger.debug(f"处理文件: {filename}")
                try:
                    # 从文件名提取日期时间
                    if filename.startswith("news_") and filename.endswith(".json"):
                        date_str = filename.replace("news_", "").replace(".json", "")
                        date_time = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                        display_text = f"{date_time.strftime('%Y-%m-%d %H:%M:%S')} ({filename})"
                    else:
                        display_text = filename

                    self.export_combo.addItem(display_text, filename)
                    self.logger.debug(f"添加项目到 export_combo: {display_text}")
                except ValueError: # 更具体的异常捕获
                    self.logger.warning(f"无法解析文件名中的日期: {filename}")
                    self.export_combo.addItem(filename, filename) # 仍然添加，但使用原始文件名
                    self.logger.debug(f"添加原始文件名到 export_combo: {filename}")

            item_count = self.export_combo.count() # 获取最终数量
            self.logger.debug(f"export_combo 刷新完成，共 {item_count} 个项目")
            # 移除状态标签更新
            # if item_count > 0:
            #     pass # 原更新状态标签代码移除
            # else:
            #     pass # 原更新状态标签代码移除

        except Exception as e:
            self.logger.error(f"加载导出文件列表失败: {str(e)}")
            # 移除状态标签更新

    def _load_to_main(self):
        """将选中的历史新闻批次文件加载到主界面"""
        # 检查是否有选中的历史文件 (这里指浏览历史列表，但数据是旧格式文件名)
        # 这个逻辑需要调整，因为现在 history_list 显示的是浏览历史，不是文件列表
        # 暂时保留，但可能需要进一步修改或移除此按钮的功能

        # --- 临时注释掉，因为 history_list 不再存储文件名 ---
        # if self.history_list.currentItem() is None:
        #     QMessageBox.warning(self, "提示", "请先选择一个历史文件")
        #     return
        #
        # # 获取文件名
        # filename = self.history_list.currentItem().data(Qt.UserRole)
        # file_path = os.path.join(self.news_dir, filename)
        # --- 临时注释结束 ---

        # --- 临时添加警告，说明此功能可能不再适用 ---
        QMessageBox.warning(self, "功能调整", "“加载到主界面”按钮目前与浏览历史不兼容。\n请使用导入/导出标签页管理历史批次文件。")
        return
        # --- 临时添加结束 ---


        # --- 以下是旧的加载逻辑，暂时保留但可能无法正常工作 ---
        # try:
        #     # 显示进度条 (检查是否存在)
        #     if hasattr(self, 'progress_bar'):
        #         self.progress_bar.setVisible(True)
        #         self.progress_bar.setValue(0)
        #
        #     # 直接从文件读取
        #     with open(file_path, 'r', encoding='utf-8') as f:
        #         news_items = json.load(f)
        #
        #     # 更新进度
        #     if hasattr(self, 'progress_bar'):
        #         self.progress_bar.setValue(50)
        #
        #     if not news_items:
        #         if hasattr(self, 'progress_bar'):
        #             self.progress_bar.setVisible(False)
        #         QMessageBox.information(self, "提示", "所选文件不包含新闻数据")
        #         return
        #
        #     # 发送加载完成信号
        #     self.history_loaded.emit(news_items)
        #
        #     # 完成进度
        #     if hasattr(self, 'progress_bar'):
        #         self.progress_bar.setValue(100)
        #
        #     if hasattr(self, 'status_label'):
        #         self.status_label.setText(f"已将 {len(news_items)} 条新闻加载到主界面")
        #     self.logger.info(f"将历史文件 {filename} 中的 {len(news_items)} 条新闻加载到主界面")
        #
        #     # 显示成功消息
        #     QMessageBox.information(self, "加载成功", f"已成功加载 {len(news_items)} 条历史新闻到主界面")
        #
        #     # 隐藏进度条
        #     if hasattr(self, 'progress_bar'):
        #         self.progress_bar.setVisible(False)
        #
        # except Exception as e:
        #     if hasattr(self, 'progress_bar'):
        #         self.progress_bar.setVisible(False)
        #     QMessageBox.critical(self, "加载失败", f"加载历史新闻失败: {str(e)}")
        #     if hasattr(self, 'status_label'):
        #         self.status_label.setText("加载失败")
        #     self.logger.error(f"加载历史新闻到主界面失败: {str(e)}")
        # --- 旧逻辑结束 ---


    def _import_news_file(self):
        """导入外部新闻文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入新闻文件", "", "JSON Files (*.json)"
        )

        if not file_path:
            return

        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                news_items = json.load(f)

            if not isinstance(news_items, list):
                QMessageBox.warning(self, "格式错误", "文件格式不正确，应为新闻条目列表")
                return

            # 生成新的文件名 (使用 news_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"news_{timestamp}.json"
            new_path = os.path.join(self.news_dir, new_filename)

            # 确保目录存在
            os.makedirs(os.path.dirname(new_path), exist_ok=True)

            # 保存到数据目录
            with open(new_path, 'w', encoding='utf-8') as f:
                json.dump(news_items, f, ensure_ascii=False, indent=2)

            # 刷新列表 (包括导出下拉框)
            self._refresh_history_list() # 刷新浏览历史列表
            self._refresh_export_combo() # 刷新导出文件下拉框

            # 显示成功消息
            QMessageBox.information(
                self, "导入成功",
                f"成功导入 {len(news_items)} 条新闻\n保存为历史批次 {new_filename}"
            )
            # 移除状态标签更新
            self.logger.info(f"已导入 {len(news_items)} 条新闻到 {new_filename}")

        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"导入新闻文件失败: {str(e)}")
            self.logger.error(f"导入新闻文件失败: {str(e)}")

    def _export_selected_file(self):
        """导出当前选中的文件"""
        # 检查是否有选中的文件
        if not hasattr(self, 'export_combo') or self.export_combo.count() == 0:
            QMessageBox.warning(self, "提示", "没有可导出的文件")
            return

        # 获取文件名
        selected_index = self.export_combo.currentIndex()
        if selected_index < 0:
            QMessageBox.warning(self, "提示", "请选择要导出的文件")
            return

        filename = self.export_combo.itemData(selected_index)
        # display_name = self.export_combo.currentText() # display_name 未使用

        # 构建完整文件路径 (使用 news_dir)
        file_path = os.path.join(self.news_dir, filename)

        # 检查源文件是否存在
        if not os.path.exists(file_path):
            QMessageBox.critical(self, "错误", f"源文件不存在: {filename}")
            self.logger.error(f"尝试导出不存在的文件: {file_path}")
            return

        # 选择保存路径
        export_path, _ = QFileDialog.getSaveFileName(
            self, "导出新闻批次", filename, "JSON Files (*.json)"
        )

        if not export_path:
            return

        try:
            # 直接复制文件
            with open(file_path, 'r', encoding='utf-8') as src_file:
                news_items = json.load(src_file) # 读取以获取数量

            with open(file_path, 'rb') as src_file, open(export_path, 'wb') as dst_file:
                 dst_file.write(src_file.read()) # 使用二进制复制确保一致性

            QMessageBox.information(
                self, "导出成功",
                f"成功导出包含 {len(news_items)} 条新闻的批次文件到:\n{export_path}"
            )
            # 移除状态标签更新
            self.logger.info(f"已将历史批次 {filename} ({len(news_items)} 条新闻) 导出到 {export_path}")

        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出新闻失败: {str(e)}")
            # 移除状态标签更新
            self.logger.error(f"导出新闻失败: {str(e)}")

    # --- Methods for Menu Actions ---
    # def load_all_history(self): # REMOVED - Logic moved to _show_history_dialog or handled internally
    #     """加载所有浏览历史并发送信号""" # REMOVED
    #     history_file = os.path.join('data', 'browsing_history.json') # REMOVED
    #     self.logger.info("请求加载所有浏览历史") # REMOVED
    #     try: # REMOVED
    #         if not os.path.exists(history_file): # REMOVED
    #             self.logger.warning("浏览历史文件不存在，无法加载") # REMOVED
    #             # self.history_loaded.emit([]) # REMOVED Signal emit
    #             QMessageBox.information(self, "提示", "没有找到浏览历史记录文件。") # REMOVED
    #             return # REMOVED
    #
    #         with open(history_file, 'r', encoding='utf-8') as f: # REMOVED
    #             history_items = json.load(f) # REMOVED
    #
    #         if not history_items: # REMOVED
    #             self.logger.info("浏览历史文件为空") # REMOVED
    #             # self.history_loaded.emit([]) # REMOVED Signal emit
    #             QMessageBox.information(self, "提示", "浏览历史记录为空。") # REMOVED
    #             return # REMOVED
    #
    #         # self.history_loaded.emit(history_items) # REMOVED Signal emit
    #         self.logger.info(f"已发送 {len(history_items)} 条浏览历史记录到主窗口") # REMOVED
    #         # 可以在这里加一个提示，或者让主窗口处理 # REMOVED
    #         # QMessageBox.information(self, "加载成功", f"已加载 {len(history_items)} 条浏览历史到主新闻列表。") # REMOVED
    #
    #     except (json.JSONDecodeError, IOError) as e: # REMOVED
    #         self.logger.error(f"加载浏览历史失败: {str(e)}") # REMOVED
    #         QMessageBox.critical(self, "加载失败", f"加载浏览历史文件失败: {str(e)}") # REMOVED
    #         # self.history_loaded.emit([]) # REMOVED Signal emit
    #     except Exception as e: # REMOVED
    #         self.logger.error(f"加载浏览历史时发生未知错误: {str(e)}", exc_info=True) # REMOVED
    #         QMessageBox.critical(self, "加载失败", f"加载浏览历史时发生未知错误: {str(e)}") # REMOVED
    #         # self.history_loaded.emit([]) # REMOVED Signal emit

    def clear_all_history_records(self):
        """清除所有浏览历史记录"""
        reply = QMessageBox.question(
            self, '确认清除',
            '确定要清除所有浏览历史记录吗？此操作不可恢复。',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        history_file = os.path.join('data', 'browsing_history.json')
        try:
            # 清空文件内容（写入空列表）
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump([], f)

            # 刷新UI (如果面板还可见的话，虽然现在不可见，但保留逻辑无害)
            self._refresh_history_list() # 清空列表显示
            if hasattr(self, 'preview'): self.preview.clear()
            if hasattr(self, 'info_label'): self.info_label.setText("浏览历史已清除")

            self.logger.info("已清除所有浏览历史记录")
            QMessageBox.information(self, "清除成功", "所有浏览历史记录已被清除。")

        except Exception as e:
            self.logger.error(f"清除浏览历史失败: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "清除失败", f"清除浏览历史失败: {str(e)}")


    def _refresh_history_list(self):
        """刷新浏览历史列表"""
        # 检查 self.history_list 是否存在
        if not hasattr(self, 'history_list'):
             self.logger.warning("_refresh_history_list: history_list 不存在")
             return

        self.history_list.clear()
        # 检查 self.news_list 是否存在 (虽然已移除，但防御性检查)
        # if hasattr(self, 'news_list'):
        #     self.news_list.clear()
        if hasattr(self, 'preview'):
            self.preview.clear()
        if hasattr(self, 'info_label'):
            self.info_label.setText("请选择浏览历史条目")

        history_file = os.path.join('data', 'browsing_history.json')

        try:
            if not os.path.exists(history_file):
                # 移除状态标签更新
                self.logger.info("浏览历史文件不存在")
                return

            with open(history_file, 'r', encoding='utf-8') as f:
                history_items = json.load(f)

            if not history_items:
                # 移除状态标签更新
                return

            # 添加到列表
            for item_data in history_items:
                title = item_data.get('title', '无标题')
                viewed_at_str = item_data.get('viewed_at', '')
                display_time = "未知时间"
                try:
                    # 解析 ISO 格式时间并格式化
                    viewed_dt = datetime.fromisoformat(viewed_at_str)
                    display_time = viewed_dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    self.logger.warning(f"无法解析浏览时间: {viewed_at_str}")

                display_text = f"{title}\n(浏览于: {display_time})"
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, item_data)  # 存储完整的历史条目数据
                self.history_list.addItem(item)

            # 移除状态标签更新
            self.logger.info(f"刷新浏览历史列表，找到 {len(history_items)} 条记录")

        except (json.JSONDecodeError, IOError) as e:
            # 移除状态标签更新
            self.logger.error(f"加载浏览历史失败: {str(e)}")

        except Exception as e:
            # 移除状态标签更新
            self.logger.error(f"加载浏览历史时发生未知错误: {str(e)}", exc_info=True)

    def _delete_history_record(self):
        """删除选中的历史记录 (支持多选)"""
        selected_items = self.history_list.selectedItems()
        if not selected_items:
            return

        count = len(selected_items)
        # 确认对话框
        reply = QMessageBox.question(
            self, '确认删除',
            f'确定要删除选中的 {count} 条历史记录吗？此操作不可恢复。',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            # 获取所有选中项的数据标识 (link 和 viewed_at)
            items_to_delete = set()
            deleted_titles = [] # 用于日志记录
            for item in selected_items:
                history_data = item.data(Qt.UserRole)
                if history_data:
                    link = history_data.get('link')
                    viewed_at = history_data.get('viewed_at')
                    if link and viewed_at:
                        items_to_delete.add((link, viewed_at))
                        deleted_titles.append(history_data.get('title', '无标题'))

            if not items_to_delete:
                QMessageBox.warning(self, "错误", "无法获取选中项的有效信息进行删除。")
                return

            # 读取现有历史文件
            history_file = os.path.join('data', 'browsing_history.json')
            if not os.path.exists(history_file):
                QMessageBox.warning(self, "错误", "历史记录文件不存在")
                return

            with open(history_file, 'r', encoding='utf-8') as f:
                history_items = json.load(f)

            # 过滤掉要删除的记录
            new_history = [
                item for item in history_items
                if (item.get('link'), item.get('viewed_at')) not in items_to_delete
            ]

            # 保存更新后的历史记录
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(new_history, f, ensure_ascii=False, indent=2)

            # 刷新列表
            self._refresh_history_list()
            self.logger.info(f"已删除 {len(items_to_delete)} 条历史记录: {', '.join(deleted_titles)}")
            QMessageBox.information(self, "删除成功", f"已成功删除 {len(items_to_delete)} 条历史记录。")
        except Exception as e:
            QMessageBox.critical(self, "删除失败", f"删除历史记录失败: {str(e)}")
            self.logger.error(f"删除历史记录失败: {str(e)}", exc_info=True)

    def _on_history_selected(self, item):
        """处理浏览历史条目选择事件"""
        # 获取存储的历史条目数据
        history_data = item.data(Qt.UserRole)
        if not history_data:
            return

        # 更新预览区域
        title = history_data.get('title', '无标题')
        source = history_data.get('source_name', '未知来源')
        pub_date = history_data.get('pub_date', '未知发布日期') # 原始发布日期
        description = history_data.get('description', '无内容')
        link = history_data.get('link', '')
        viewed_at_str = history_data.get('viewed_at', '')


    def _select_all_history(self):
        """选中所有历史记录项"""
        if hasattr(self, 'history_list'):
            for i in range(self.history_list.count()):
                self.history_list.item(i).setSelected(True)

    def _deselect_all_history(self):
        """取消选中所有历史记录项"""
        if hasattr(self, 'history_list'):
            for i in range(self.history_list.count()):
                self.history_list.item(i).setSelected(False)

    def _on_history_selected(self, current, previous):
        """处理浏览历史条目选择事件 (使用 currentItemChanged 信号)"""
        # 检查当前项是否存在
        if not current:
            # 如果没有当前项被选中 (例如列表清空时)，清除预览
            if hasattr(self, 'preview'):
                self.preview.clear()
            if hasattr(self, 'info_label'):
                self.info_label.setText("请选择浏览历史条目")
            return

        # 获取存储的历史条目数据
        history_data = current.data(Qt.UserRole)
        if not history_data:
            return

        # 更新预览区域
        title = history_data.get('title', '无标题')
        source = history_data.get('source_name', '未知来源')
        pub_date = history_data.get('pub_date', '未知发布日期') # 原始发布日期
        description = history_data.get('description', '无内容')
        link = history_data.get('link', '')
        viewed_at_str = history_data.get('viewed_at', '')

        # 格式化浏览时间
        display_viewed_time = "未知时间"
        try:
            viewed_dt = datetime.fromisoformat(viewed_at_str)
            display_viewed_time = viewed_dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            pass # 保持 "未知时间"

        # 创建HTML内容
        html = f"""
        <div style='font-family: "Segoe UI", "Microsoft YaHei", sans-serif;'>
            <h2 style='color: #1976D2;'>{title}</h2>
            <p><strong>来源:</strong> {source} | <strong>发布日期:</strong> {pub_date}</p>
            <p><strong>浏览时间:</strong> {display_viewed_time}</p>
            <hr style='border: 1px solid #E0E0E0;'>
            <p>{description}</p>
        """

        if link:
            html += f'<p><a href="{link}" style="color: #1976D2; text-decoration: none;" target="_blank">阅读原文</a></p>'

        html += "</div>"

        # 设置HTML内容
        if hasattr(self, 'preview'):
            self.preview.setHtml(html)
        if hasattr(self, 'info_label'):
            self.info_label.setText(f"预览: {title[:50]}...") # 更新信息标签
        self.logger.debug(f"预览浏览历史条目: {title[:30]}...")


        # 创建HTML内容
        html = f"""
        <div style='font-family: "Segoe UI", "Microsoft YaHei", sans-serif;'>
            <h2 style='color: #1976D2;'>{title}</h2>
            <p><strong>来源:</strong> {source} | <strong>发布日期:</strong> {pub_date}</p>
            <p><strong>浏览时间:</strong> {display_viewed_time}</p>
            <hr style='border: 1px solid #E0E0E0;'>
            <p>{description}</p>
        """

        if link:
            html += f'<p><a href="{link}" style="color: #1976D2; text-decoration: none;" target="_blank">阅读原文</a></p>'

        html += "</div>"

        # 设置HTML内容
        if hasattr(self, 'preview'):
            self.preview.setHtml(html)
        if hasattr(self, 'info_label'):
            self.info_label.setText(f"预览: {title[:50]}...") # 更新信息标签
        self.logger.debug(f"预览浏览历史条目: {title[:30]}...")

# 移除 eventFilter 方法 (原 686-703 行)

# 移除多余的日志行 (原 705 行)

# _on_news_selected 方法已移除 (Lines 329-356)

# _load_to_main 方法已移除 (Lines 514-562)

# _import_news_file 方法已移除 (Lines 564-608)

# _export_selected_file 方法已移除 (Lines 610-656)