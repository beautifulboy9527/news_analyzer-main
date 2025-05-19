"""
新闻分析可视化组件

提供重要程度和立场识别的可视化展示功能，
支持进度条、颜色渐变和图表展示。
"""

import logging
from typing import Dict, Any, Optional, List, Tuple

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QProgressBar, QSizePolicy, QFrame)
from PySide6.QtCore import Qt, Signal, Property
from PySide6.QtGui import QColor, QPalette, QLinearGradient, QBrush

# 尝试导入matplotlib，如果失败则提供备用实现
try:
    from matplotlib.figure import Figure
    # 使用与PySide6兼容的后端
    from matplotlib.backends.backend_qt6agg import FigureCanvasQTAgg as FigureCanvas
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logging.getLogger('news_analyzer.ui.views.analysis_visualizer').warning(
        "Matplotlib未安装或导入失败，将使用简化版图表显示")


class ImportanceBar(QWidget):
    """重要程度可视化进度条"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.views.importance_bar') # Updated logger
        
        # 初始化UI
        self._init_ui()
        
        # 设置默认值
        self._importance = 0
        self.update_importance(0)
    
    def _init_ui(self):
        """初始化UI布局"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 标签
        self.label = QLabel("重要程度:")
        self.label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        layout.addWidget(self.label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 5)  # 0-5分
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v/5")
        layout.addWidget(self.progress_bar)
        
        # 文本描述
        self.description = QLabel("一般")
        self.description.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.description.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.description.setMinimumWidth(50)
        layout.addWidget(self.description)
    
    def update_importance(self, value: int):
        """更新重要程度值和显示
        
        Args:
            value: 重要程度值（0-5）
        """
        # 确保值在有效范围内
        value = max(0, min(5, value))
        self._importance = value
        
        # 更新进度条
        self.progress_bar.setValue(value)
        
        # 更新颜色（绿色渐变）
        self._update_color()
        
        # 更新描述文本
        self._update_description()
    
    def _update_color(self):
        """根据重要程度更新进度条颜色"""
        # 创建调色板
        palette = QPalette()
        
        # 根据重要程度设置颜色渐变
        if self._importance <= 1:  # 次要/一般
            color = QColor(144, 238, 144)  # 浅绿色
        elif self._importance <= 3:  # 重要
            color = QColor(50, 205, 50)  # 酸橙绿
        else:  # 头条
            color = QColor(0, 128, 0)  # 深绿色
        
        # 设置进度条颜色
        palette.setColor(QPalette.Highlight, color)
        self.progress_bar.setPalette(palette)
    
    def _update_description(self):
        """根据重要程度更新描述文本"""
        if self._importance == 0:
            self.description.setText("次要")
        elif self._importance <= 1:
            self.description.setText("一般")
        elif self._importance <= 3:
            self.description.setText("重要")
        else:
            self.description.setText("头条")


class StanceIndicator(QWidget):
    """立场可视化指示器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.views.stance_indicator') # Updated logger
        
        # 初始化UI
        self._init_ui()
        
        # 设置默认值
        self._stance = 0.0
        self.update_stance(0.0)
    
    def _init_ui(self):
        """初始化UI布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 顶部标签和描述
        top_layout = QHBoxLayout()
        
        # 标签
        self.label = QLabel("立场:")
        self.label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        top_layout.addWidget(self.label)
        
        # 文本描述
        self.description = QLabel("中立")
        self.description.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        top_layout.addWidget(self.description)
        
        top_layout.addStretch()
        layout.addLayout(top_layout)
        
        # 立场指示条
        indicator_layout = QHBoxLayout()
        
        # 左侧标签（亲美）
        self.left_label = QLabel("亲美")
        self.left_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        indicator_layout.addWidget(self.left_label)
        
        # 立场指示框
        self.indicator_frame = QFrame()
        self.indicator_frame.setFrameShape(QFrame.StyledPanel)
        self.indicator_frame.setFrameShadow(QFrame.Sunken)
        self.indicator_frame.setMinimumHeight(20)
        self.indicator_frame.setMinimumWidth(200)
        indicator_layout.addWidget(self.indicator_frame)
        
        # 右侧标签（亲中）
        self.right_label = QLabel("亲中")
        self.right_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        indicator_layout.addWidget(self.right_label)
        
        layout.addLayout(indicator_layout)
    
    def update_stance(self, value: float):
        """更新立场值和显示
        
        Args:
            value: 立场值（-1到1）
        """
        # 确保值在有效范围内
        value = max(-1.0, min(1.0, value))
        self._stance = value
        
        # 更新颜色渐变
        self._update_color()
        
        # 更新描述文本
        self._update_description()
    
    def _update_color(self):
        """根据立场更新颜色渐变"""
        # 创建线性渐变
        gradient = QLinearGradient(0, 0, self.indicator_frame.width(), 0)
        
        # 设置渐变颜色（红-白-蓝）
        gradient.setColorAt(0, QColor(255, 0, 0))  # 左侧红色（亲美）
        gradient.setColorAt(0.5, QColor(255, 255, 255))  # 中间白色（中立）
        gradient.setColorAt(1, QColor(0, 0, 255))  # 右侧蓝色（亲中）
        
        # 创建画刷
        brush = QBrush(gradient)
        
        # 设置样式表
        palette = self.indicator_frame.palette()
        palette.setBrush(QPalette.Window, brush)
        self.indicator_frame.setPalette(palette)
        self.indicator_frame.setAutoFillBackground(True)
        
        # 添加指示器
        # 将-1到1的值映射到0到1的范围（用于定位指示器）
        position = (self._stance + 1) / 2
        
        # 使用样式表设置指示器
        # 这里使用边框作为指示器，在适当位置显示
        border_position = int(position * 100)
        self.indicator_frame.setStyleSheet(f"""
            QFrame {{
                border: 2px solid black;
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                              stop:0 #ff0000, 
                                              stop:0.5 #ffffff, 
                                              stop:1 #0000ff);
                border-radius: 3px;
            }}
            QFrame::after {{
                content: "";
                position: absolute;
                left: {border_position}%;
                top: 0;
                width: 2px;
                height: 100%;
                background-color: black;
            }}
        """)
    
    def _update_description(self):
        """根据立场更新描述文本"""
        if self._stance <= -0.8:
            self.description.setText("亲美")
        elif self._stance <= -0.3:
            self.description.setText("偏美")
        elif self._stance <= 0.3:
            self.description.setText("中立")
        elif self._stance <= 0.8:
            self.description.setText("偏中")
        else:
            self.description.setText("亲中")


class SimpleAnalysisChart(QWidget):
    """简化的分析图表，用于Matplotlib不可用时显示基本信息"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.views.simple_analysis_chart') # Updated logger
        self._init_ui()
        self._data = [] # Store data as list of tuples (label, importance, stance)

    def _init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.text_label = QLabel("无分析数据")
        self.text_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.text_label.setWordWrap(True)
        self.layout.addWidget(self.text_label)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def update_data(self, importance_data: List[int], stance_data: List[float], labels: List[str]):
        if not labels or len(importance_data) != len(labels) or len(stance_data) != len(labels):
            self._data = []
        else:
            self._data = list(zip(labels, importance_data, stance_data))
        
        self._update_text_display()

    def _update_text_display(self):
        if not self._data:
            self.text_label.setText("无分析数据")
            return

        # 创建富文本显示
        html_content = "<h4>分析结果:</h4><table border=\"0\" cellspacing=\"5\">"
        html_content += "<tr><th>新闻</th><th>重要性</th><th>立场</th></tr>"
        
        for label, importance, stance in self._data:
            # 将stance值转换为文本描述
            stance_desc = "中立"
            if stance <= -0.8: stance_desc = "亲美"
            elif stance <= -0.3: stance_desc = "偏美"
            elif stance <= 0.3: stance_desc = "中立"
            elif stance <= 0.8: stance_desc = "偏中"
            else: stance_desc = "亲中"
            
            # 截断长标签
            short_label = (label[:30] + '...') if len(label) > 30 else label
            
            html_content += f"<tr><td>{short_label}</td><td>{importance}/5</td><td>{stance_desc} ({stance:.2f})</td></tr>"
            
        html_content += "</table>"
        self.text_label.setText(html_content)

# 仅当Matplotlib可用时定义AnalysisChart
if MATPLOTLIB_AVAILABLE:
    class AnalysisChart(QWidget):
        """使用Matplotlib绘制分析图表"""
        
        def __init__(self, parent=None):
            super().__init__(parent)
            self.logger = logging.getLogger('news_analyzer.ui.views.analysis_chart') # Updated logger
            
            # 初始化数据
            self._importance_data: List[int] = []
            self._stance_data: List[float] = []
            self._labels: List[str] = []
            
            # 初始化UI
            self._init_ui()
            
        def _init_ui(self):
            """初始化UI布局和图表"""
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0) # No external margins
            
            # 创建Matplotlib画布
            self.fig = Figure(figsize=(5, 4), dpi=100)
            self.canvas = FigureCanvas(self.fig)
            layout.addWidget(self.canvas)
            
            # 添加两个子图 (一个显示重要性，一个显示立场)
            self.ax_importance = self.fig.add_subplot(2, 1, 1) # Top plot for importance
            self.ax_stance = self.fig.add_subplot(2, 1, 2) # Bottom plot for stance
            
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            
        def update_data(self, importance_data: List[int], stance_data: List[float], labels: List[str]):
            """更新图表数据"""
            if not labels or len(importance_data) != len(labels) or len(stance_data) != len(labels):
                self.logger.warning("无效的分析数据，无法更新图表。")
                # 清空数据以防旧数据显示
                self._importance_data = []
                self._stance_data = []
                self._labels = []
            else:
                self._importance_data = importance_data
                self._stance_data = stance_data
                self._labels = labels
                
            self._update_chart()
            
        def _update_chart(self):
            """重新绘制图表"""
            # 清除旧图
            self.ax_importance.clear()
            self.ax_stance.clear()
            
            if not self._labels: # 如果没有数据，显示提示信息
                self.ax_importance.text(0.5, 0.5, '无重要性数据', ha='center', va='center')
                self.ax_stance.text(0.5, 0.5, '无立场数据', ha='center', va='center')
                self.canvas.draw()
                return
            
            x = range(len(self._labels))
            
            # 绘制重要性条形图
            self.ax_importance.bar(x, self._importance_data, color='skyblue')
            self.ax_importance.set_ylabel('重要程度 (0-5)')
            self.ax_importance.set_ylim(0, 5.5)
            self.ax_importance.set_xticks([]) # 隐藏上图X轴标签，避免重叠
            self.ax_importance.set_title('新闻分析结果')
            self.ax_importance.grid(axis='y', linestyle='--', alpha=0.7)
            
            # 绘制立场散点图或条形图
            # 使用水平条形图可能更清晰
            # self.ax_stance.scatter(x, self._stance_data, color='salmon')
            colors = ['#ff6666' if s <= -0.3 else ('#6666ff' if s >= 0.3 else '#cccccc') for s in self._stance_data]
            self.ax_stance.barh(x, self._stance_data, color=colors, height=0.6)
            self.ax_stance.set_xlabel('立场 (-1:亲美, 1:亲中)')
            self.ax_stance.set_xlim(-1.1, 1.1)
            self.ax_stance.set_yticks(x)
            self.ax_stance.set_yticklabels(self._labels, fontsize=8) # 设置Y轴标签为新闻标题
            self.ax_stance.invert_yaxis() # 让第一个标签在顶部
            self.ax_stance.axvline(0, color='grey', linestyle='--') # 中立线
            self.ax_stance.grid(axis='x', linestyle='--', alpha=0.7)
            
            # 调整布局以防止标签重叠
            self.fig.tight_layout(rect=[0, 0.03, 1, 0.95]) # Add padding for title
            
            # 重新绘制画布
            self.canvas.draw()


class AnalysisVisualizer(QWidget):
    """分析可视化主组件，包含重要性和立场指示器/图表"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.views.analysis_visualizer') # Updated logger
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10) # Add margins
        main_layout.setSpacing(15) # Add spacing
        
        # 重要程度指示器
        self.importance_bar = ImportanceBar()
        main_layout.addWidget(self.importance_bar)
        
        # 立场指示器
        self.stance_indicator = StanceIndicator()
        main_layout.addWidget(self.stance_indicator)
        
        # 分析图表 (根据Matplotlib可用性选择)
        if MATPLOTLIB_AVAILABLE:
            self.analysis_chart = AnalysisChart()
            self.analysis_chart.setMinimumHeight(250) # Give chart enough space
        else:
            self.analysis_chart = SimpleAnalysisChart()
            self.analysis_chart.setMinimumHeight(150)
        
        main_layout.addWidget(self.analysis_chart)
        main_layout.addStretch() # Push elements to the top
        
        self.reset() # Initialize with empty state

    def update_importance(self, importance: int):
        """仅更新重要程度指示器"""
        self.importance_bar.update_importance(importance)
        # 如果是多条分析模式，图表可能需要保持
        # self.analysis_chart.update_data([], [], []) # Reset chart if only importance is updated?

    def update_stance(self, stance: float):
        """仅更新立场指示器"""
        self.stance_indicator.update_stance(stance)
        # self.analysis_chart.update_data([], [], []) # Reset chart if only stance is updated?

    def update_single_analysis(self, importance: int, stance: float):
        """
        更新显示单条新闻的分析结果
        
        Args:
            importance: 重要程度 (0-5)
            stance: 立场 (-1.0 到 1.0)
        """
        self.logger.info(f"更新单条分析: 重要性={importance}, 立场={stance:.2f}")
        self.importance_bar.update_importance(importance)
        self.stance_indicator.update_stance(stance)
        
        # 重置或隐藏多条分析图表
        if MATPLOTLIB_AVAILABLE:
            self.analysis_chart.update_data([], [], [])
        else:
            self.analysis_chart.update_data([], [], [])
        self.analysis_chart.setVisible(False) # Hide chart in single mode

    def update_multiple_analysis(self, importance_data: List[int], stance_data: List[float], labels: List[str]):
        """
        更新显示多条新闻的分析结果
        
        Args:
            importance_data: 重要程度列表
            stance_data: 立场列表
            labels: 新闻标题或标识符列表
        """
        self.logger.info(f"更新多条分析: {len(labels)} 条新闻")
        # 对于多条新闻，重要性和立场指示器可以显示平均值或禁用
        # 这里选择禁用/重置它们
        self.importance_bar.update_importance(0) # Reset importance bar
        self.stance_indicator.update_stance(0.0) # Reset stance indicator
        self.importance_bar.setEnabled(False)
        self.stance_indicator.setEnabled(False)
        
        # 更新并显示图表
        self.analysis_chart.update_data(importance_data, stance_data, labels)
        self.analysis_chart.setVisible(True)

    def reset(self):
        """重置所有可视化组件到默认状态"""
        self.logger.debug("重置分析可视化组件")
        self.importance_bar.update_importance(0)
        self.stance_indicator.update_stance(0.0)
        self.importance_bar.setEnabled(True) # Enable for single analysis
        self.stance_indicator.setEnabled(True)
        
        if MATPLOTLIB_AVAILABLE:
            self.analysis_chart.update_data([], [], [])
        else:
            self.analysis_chart.update_data([], [], [])
        self.analysis_chart.setVisible(False) # Hide chart initially

# --- Property Implementation (Optional) ---
# 可以添加Qt属性以便于从外部访问或绑定
# class AnalysisVisualizer(QWidget):
#     ... (previous code) ...

#     def _get_importance(self):
#         return self.importance_bar._importance
    
#     def update_importance(self, value):
#         self.importance_bar.update_importance(value)
    
#     # 定义importance属性
#     # 注意：setter需要与updater方法分开，或者在setter中调用updater
#     qt_importance = Property(int, _get_importance, update_importance) 

#     def _get_stance(self):
#         return self.stance_indicator._stance
    
#     def update_stance(self, value):
#         self.stance_indicator.update_stance(value)
        
#     qt_stance = Property(float, _get_stance, update_stance)
    
# --- Helper Functions (Example) ---
# def _parse_llm_output(output: str) -> Dict[str, Any]:
#     """示例：解析LLM输出以提取重要性和立场"""
#     try:
#         # 简单的基于关键词的解析
#         importance = 0
#         stance = 0.0
        
#         # 查找重要性 (假设格式如 "重要性： 3")
#         match = re.search(r"重要性[：:]\s*(\d)", output)
#         if match:
#             importance = int(match.group(1))
        
#         # 查找立场 (假设格式如 "立场： 偏中 (0.6)")
#         stance_match = re.search(r"立场[：:]\s*.*?\(?([-+]?\d*\.?\d+)\)?", output)
#         if stance_match:
#             stance = float(stance_match.group(1))
#         else:
#             # 尝试关键词匹配
#             if "亲美" in output: stance = -1.0
#             elif "偏美" in output: stance = -0.5
#             elif "亲中" in output: stance = 1.0
#             elif "偏中" in output: stance = 0.5
#             elif "中立" in output: stance = 0.0
            
#         return {"importance": importance, "stance": stance}
#     except Exception as e:
#         logging.getLogger(__name__).error(f"解析LLM输出时出错: {e}")
#         return {"importance": 0, "stance": 0.0}


# --- Standalone Test --- 
if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer

    logging.basicConfig(level=logging.DEBUG)
    
    app = QApplication(sys.argv)
    
    window = QWidget()
    layout = QVBoxLayout(window)
    
    visualizer = AnalysisVisualizer()
    layout.addWidget(visualizer)
    
    # 测试按钮
    btn_layout = QHBoxLayout()
    test_btn_single = QPushButton("测试单条分析")
    test_btn_multi = QPushButton("测试多条分析")
    test_btn_reset = QPushButton("重置")
    btn_layout.addWidget(test_btn_single)
    btn_layout.addWidget(test_btn_multi)
    btn_layout.addWidget(test_btn_reset)
    layout.addLayout(btn_layout)
    
    # 连接按钮信号
    test_btn_single.clicked.connect(lambda: visualizer.update_single_analysis(importance=4, stance=-0.7))
    test_btn_multi.clicked.connect(lambda: visualizer.update_multiple_analysis(
        importance_data=[2, 5, 3, 1, 4],
        stance_data=[-0.8, 0.9, 0.1, -0.2, 0.5],
        labels=["新闻标题A - 这是一个很长很长的新闻标题需要被截断", "新闻B", "标题C", "新闻D", "新闻标题E"]
    ))
    test_btn_reset.clicked.connect(visualizer.reset)
    
    window.setWindowTitle("分析可视化测试")
    window.resize(600, 500)
    window.show()
    
    sys.exit(app.exec())


# Utility function (if needed elsewhere)
def _convert_stance_text_to_value(stance_text: str) -> float:
    """将文本立场描述转换为数值（-1到1）"""
    stance_text = stance_text.strip().lower()
    if "亲美" in stance_text: return -1.0
    if "偏美" in stance_text: return -0.5
    if "亲中" in stance_text: return 1.0
    if "偏中" in stance_text: return 0.5
    if "中立" in stance_text: return 0.0
    # Add more mappings if needed
    return 0.0 # Default to neutral 