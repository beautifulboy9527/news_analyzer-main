"""
UI 工具函数和辅助类
"""
from PySide6.QtWidgets import QPushButton, QSizePolicy, QFrame, QComboBox, QListWidget, QTextBrowser, QLabel, QFormLayout, QWidget, QAbstractItemView # Use PySide6
from PySide6.QtGui import QIcon, QPalette, QColor # Use PySide6
from PySide6.QtCore import Qt, QSize # Use PySide6

def create_standard_button(text: str, icon_path: str = None, tooltip: str = None, fixed_size: QSize = None, object_name: str = None) -> QPushButton:
    """
    创建一个标准化的 QPushButton。

    Args:
        text: 按钮显示的文本。
        icon_path: (可选) 按钮图标的路径 (例如 ":/icons/add.png")。
        tooltip: (可选) 按钮的鼠标悬停提示。
        fixed_size: (可选) 按钮的固定尺寸 (QSize)。
        object_name: (可选) 设置按钮的 objectName 以便应用 QSS。

    Returns:
        配置好的 QPushButton 实例。
    """
    button = QPushButton(text)

    if icon_path:
        icon = QIcon(icon_path)
        if not icon.isNull():
            button.setIcon(icon)
            # 可以根据需要设置图标大小
            # button.setIconSize(QSize(16, 16))

    if tooltip:
        button.setToolTip(tooltip)

    if fixed_size:
        button.setFixedSize(fixed_size)
    else:
        # 提供一个默认的大小策略，允许按钮根据内容调整，但也可以限制
        button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed) # 高度固定，宽度随内容
        button.setFixedHeight(32) # 设置一个默认的舒适高度

    if object_name:
        button.setObjectName(object_name)

    # 可以在这里添加默认的 QSS 类选择器，例如 button.setProperty("class", "standard-button")
    # button.setProperty("class", "standard-button")

    return button

# 可以继续添加其他辅助函数，例如：
# def create_form_row(...)
# def setup_list_widget(...)
# def create_title_label(...)

# Imports moved to the top

def create_title_label(text: str, object_name: str = None) -> QLabel:
    """
    创建一个标准化的标题 QLabel。

    Args:
        text: 标签显示的文本。
        object_name: (可选) 设置标签的 objectName 以便应用 QSS。

    Returns:
        配置好的 QLabel 实例。
    """
    label = QLabel(text)
    # 应用常见的标题样式 (可以通过 QSS 覆盖)
    label.setStyleSheet("font-size: 16pt; font-weight: bold;")
    label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    if object_name:
        label.setObjectName(object_name)
    # 可以添加 QSS 类选择器
    # label.setProperty("class", "title-label")
    return label


# Imports moved to the top
from typing import Union

def add_form_row(layout: QFormLayout, label_text: str, widget: Union[QWidget, QFormLayout]):
    """
    向 QFormLayout 添加一个标签和控件行。

    Args:
        layout: 目标 QFormLayout。
        label_text: 行的标签文本。
        widget: 要添加到行的控件或子布局。
    """
    # 可以添加一些默认的标签样式或控件设置
    label = QLabel(label_text)
    layout.addRow(label, widget)


# Imports moved to the top

def setup_list_widget(list_widget: QListWidget, object_name: str = None, selection_mode: QAbstractItemView.SelectionMode = QAbstractItemView.SingleSelection, item_padding: int = 5):
    """
    配置 QListWidget 的通用属性。

    Args:
        list_widget: 要配置的 QListWidget 实例。
        object_name: (可选) 设置列表的 objectName 以便应用 QSS。
        selection_mode: (可选) 设置列表的选择模式。
        item_padding: (可选) 设置列表项的内边距 (通过样式表)。
    """
    if object_name:
        list_widget.setObjectName(object_name)

    list_widget.setSelectionMode(selection_mode)

    # 应用基础样式，特别是 item padding
    # 注意：这可能会覆盖 QSS 文件中的部分样式，如果 QSS 中也定义了 item padding
    # 更好的做法可能是在 QSS 中统一定义
    list_widget.setStyleSheet(f"QListWidget::item {{ padding: {item_padding}px; }}")

    # 可以添加其他通用设置，例如:
    # list_widget.setAlternatingRowColors(True)
    # list_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)


# Imports moved to the top

def setup_list_widget(list_widget: QListWidget, object_name: str = None, selection_mode: QAbstractItemView.SelectionMode = QAbstractItemView.SingleSelection, item_padding: int = 5):
    """
    配置 QListWidget 的通用属性。

    Args:
        list_widget: 要配置的 QListWidget 实例。
        object_name: (可选) 设置列表的 objectName 以便应用 QSS。
        selection_mode: (可选) 设置列表的选择模式。
        item_padding: (可选) 设置列表项的内边距 (通过样式表)。
    """
    if object_name:
        list_widget.setObjectName(object_name)

    list_widget.setSelectionMode(selection_mode)

    # 应用基础样式，特别是 item padding
    # 注意：这可能会覆盖 QSS 文件中的部分样式，如果 QSS 中也定义了 item padding
    # 更好的做法可能是在 QSS 中统一定义
    list_widget.setStyleSheet(f"QListWidget::item {{ padding: {item_padding}px; }}")

    # 可以添加其他通用设置，例如:
    # list_widget.setAlternatingRowColors(True)
    # list_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)


def setup_news_list_widget(list_widget: QListWidget):
    """
    配置新闻列表 QListWidget 的特定样式和行为。

    Args:
        list_widget: 要配置的 QListWidget 实例。
    """
    list_widget.setObjectName("newsListWidget")
    list_widget.setAlternatingRowColors(False)
    # 移除焦点虚线框 (Temporarily commented out)
    # list_widget.setStyleSheet("QListWidget { outline: none; } QListWidget::item:selected { border: none; }")

    # 通过 Palette 设置深色背景 (Temporarily commented out for light theme testing)
    # palette = list_widget.palette()
    # Use PySide6 signature: setColor(ColorGroup, ColorRole, QColor)
    # palette.setColor(QPalette.ColorGroup.All, QPalette.Base, QColor("#1a1a1a")) # 列表背景
    # palette.setColor(QPalette.ColorGroup.All, QPalette.Text, QColor("#e8e8e8")) # 列表文字
    # palette.setColor(QPalette.ColorGroup.All, QPalette.Highlight, QColor("#4a4a4a")) # 选中背景 (增加对比度)
    # palette.setColor(QPalette.ColorGroup.All, QPalette.HighlightedText, QColor("#f5f5f5")) # 选中文字
    # list_widget.setPalette(palette)

def create_separator(orientation=Qt.Horizontal, margin_top=15, margin_bottom=15) -> QFrame:
    """
    创建一个标准化的分隔线 QFrame。

    Args:
        orientation: 分隔线的方向 (Qt.Horizontal 或 Qt.Vertical)。
        margin_top: (可选) 顶边距。
        margin_bottom: (可选) 底边距。

    Returns:
        配置好的 QFrame 实例。
    """
    separator = QFrame()
    shape = QFrame.HLine if orientation == Qt.Horizontal else QFrame.VLine
    separator.setFrameShape(shape)
    separator.setFrameShadow(QFrame.Sunken)
    separator.setStyleSheet(f"margin-top: {margin_top}px; margin-bottom: {margin_bottom}px;")
    return separator

def setup_combobox(combobox: QComboBox, object_name: str = None):
    """
    配置 QComboBox 的通用样式。

    Args:
        combobox: 要配置的 QComboBox 实例。
        object_name: (可选) 设置下拉框的 objectName 以便应用 QSS。
    """
    if object_name:
        combobox.setObjectName(object_name)
    # 应用基础样式 (可以被 QSS 覆盖)
    combobox.setStyleSheet("""
        QComboBox {
            border: 1px solid #BDBDBD;
            border-radius: 4px;
            padding: 8px;
            background-color: white;
            margin-top: 5px;
        }
    """)

    combobox.view().viewport().setAutoFillBackground(True) # 修正：使用 combobox.view() 获取下拉列表视图

def setup_preview_browser(browser: QTextBrowser):
    """
    配置新闻预览 QTextBrowser 的通用属性。

    Args:
        browser: 要配置的 QTextBrowser 实例。
    """
    browser.setOpenExternalLinks(True)
