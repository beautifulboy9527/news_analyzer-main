# src/ui/views/advanced_analysis_visualizer.py
"""
高级新闻分析可视化组件

提供多维度新闻热点分析的可视化展示功能，
支持雷达图、热力图和多维度立场分析，
确保客观性和全面性。
"""

import logging
from typing import Dict, Any, Optional, List, Tuple

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QProgressBar, QSizePolicy, QFrame, QTabWidget,
                             QComboBox, QScrollArea, QGridLayout, QGroupBox)
from PySide6.QtCore import Qt, Signal, Property
from PySide6.QtGui import QColor, QPalette, QLinearGradient, QBrush, QFont

# 尝试导入matplotlib，如果失败则提供备用实现
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qt6agg import FigureCanvasQTAgg as FigureCanvas
    import matplotlib.pyplot as plt
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logging.getLogger('news_analyzer.ui.views.advanced_analysis_visualizer').warning(
        "Matplotlib未安装或导入失败，将使用简化版图表显示")


class ImportanceIndicator(QWidget):
    """重要程度可视化组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.views.importance_indicator') # Updated logger
        
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
        # self.description.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred) # Remove fixed size policy
        # self.description.setMinimumWidth(50) # Remove minimum width constraint
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


class MultiDimensionalStanceIndicator(QWidget):
    """多维度立场可视化指示器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.views.multi_dimensional_stance_indicator') # Updated logger
        
        # 设置默认维度和值
        self._dimensions = {
            "政治立场": 0.0,
            "经济立场": 0.0,
            "社会议题": 0.0,
            "国际关系": 0.0
        }
        
        # 维度描述映射
        self._dimension_descriptions = {
            "政治立场": {"left": "左翼", "center": "中立", "right": "右翼"},
            "经济立场": {"left": "国家干预", "center": "混合经济", "right": "自由市场"},
            "社会议题": {"left": "进步", "center": "中立", "right": "保守"},
            "国际关系": {"left": "多边主义", "center": "中立", "right": "单边主义"}
        }

        # 初始化UI
        self._init_ui()
        
        # 初始化所有维度
        self.update_all_dimensions(self._dimensions)
    
    def _init_ui(self):
        """初始化UI布局"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5) # Reduced margins
        main_layout.setSpacing(8) # Reduced spacing
        
        # 标题标签
        title_label = QLabel("多维度立场分析")
        title_label.setAlignment(Qt.AlignCenter)
        font = title_label.font()
        font.setPointSize(font.pointSize() + 1) # Slightly larger title
        font.setBold(True)
        title_label.setFont(font)
        title_label.setStyleSheet("margin-bottom: 5px;") # Add some space below title
        main_layout.addWidget(title_label)
        
        # 创建网格布局来放置所有维度指示器
        grid_layout = QGridLayout()
        grid_layout.setSpacing(8) # Reduced spacing within grid
        grid_layout.setVerticalSpacing(10) # Reduced vertical spacing
        main_layout.addLayout(grid_layout)
        
        # 创建维度指示器
        self.dimension_indicators = {}
        row = 0
        col = 0
        
        for dimension in self._dimensions.keys():
            # 创建维度容器 (Use QGroupBox for better visual separation)
            dimension_group = QGroupBox(dimension)
            dimension_group.setAlignment(Qt.AlignCenter)
            dimension_layout = QVBoxLayout(dimension_group)
            dimension_layout.setContentsMargins(6, 12, 6, 6) # Adjusted margins inside group
            dimension_layout.setSpacing(4) # Reduced spacing inside group
        
            # 指示器布局
            indicator_layout = QHBoxLayout()
            indicator_layout.setSpacing(4) # Reduced spacing
        
            # 左侧标签
            left_label = QLabel(self._dimension_descriptions[dimension]["left"])
            left_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            left_label.setStyleSheet("font-size: 9pt; color: #444;") # Increase font size slightly
            left_label.setWordWrap(True) # Allow word wrap if needed
            indicator_layout.addWidget(left_label, 2) # Adjust stretch factor
        
            # 进度条
            progress_bar = QProgressBar()
            progress_bar.setRange(-100, 100)  # -1到1映射到-100到100
            progress_bar.setValue(0)
            progress_bar.setTextVisible(False)
            progress_bar.setFixedHeight(10) # Make progress bar slimmer
            progress_bar.setStyleSheet(
                """QProgressBar {
                    background-color: #e8e8e8; 
                    border: 1px solid #c0c0c0; 
                    border-radius: 3px; 
                    height: 8px; /* Ensure height consistency */
                }
                QProgressBar::chunk {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                                    stop:0 #6666ff, 
                                                    stop:0.5 #f0f0f0, 
                                                    stop:1 #ff6666);
                    border-radius: 2px;
                }
                """
            )
            indicator_layout.addWidget(progress_bar, 4) # Increase stretch factor for progress bar
        
            # 右侧标签
            right_label = QLabel(self._dimension_descriptions[dimension]["right"])
            right_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            right_label.setStyleSheet("font-size: 9pt; color: #444;") # Increase font size slightly
            right_label.setWordWrap(True) # Allow word wrap if needed
            indicator_layout.addWidget(right_label, 2) # Adjust stretch factor
        
            dimension_layout.addLayout(indicator_layout)
        
            # 描述标签 (Current stance)
            description_label = QLabel(self._dimension_descriptions[dimension]["center"])
            description_label.setAlignment(Qt.AlignCenter)
            description_label.setStyleSheet("font-size: 9pt; font-weight: bold; margin-top: 2px;") # Slightly smaller description
            description_label.setWordWrap(True) # Allow word wrap
            dimension_layout.addWidget(description_label)
        
            # 存储引用
            self.dimension_indicators[dimension] = {
                "progress_bar": progress_bar,
                "description": description_label
            }
        
            # 添加到网格
            grid_layout.addWidget(dimension_group, row, col)
        
            # 更新行列位置
            col += 1
            if col > 1:  # 每行两个维度
                col = 0
                row += 1
    
    def update_dimension(self, dimension: str, value: float):
        """更新单个维度的立场值
        
        Args:
            dimension: 维度名称
            value: 立场值 (-1.0 到 1.0)
        """
        if dimension not in self.dimension_indicators:
            self.logger.warning(f"尝试更新未知维度: {dimension}")
            return
            
        # 确保值在有效范围内
        value = max(-1.0, min(1.0, value))
        self._dimensions[dimension] = value
        
        # 更新进度条和描述
        indicator = self.dimension_indicators[dimension]
        progress_bar = indicator["progress_bar"]
        description_label = indicator["description"]
        
        progress_bar.setValue(int(value * 100))
        
        # 更新描述文本
        desc_map = self._dimension_descriptions[dimension]
        if value < -0.3:
            description_label.setText(desc_map["left"])
        elif value > 0.3:
            description_label.setText(desc_map["right"])
        else:
            description_label.setText(desc_map["center"])
            
    def update_all_dimensions(self, dimensions: Dict[str, float]):
        """更新所有维度的立场值
        
        Args:
            dimensions: 包含维度和对应值的字典
        """
        for dimension, value in dimensions.items():
            self.update_dimension(dimension, value)


class TopicHeatmapWidget(QWidget):
    """话题热力图显示组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.views.topic_heatmap_widget') # Updated logger
        self._topics: List[str] = []
        self._values: List[float] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.canvas_widget = QWidget() # Placeholder or actual canvas
        layout.addWidget(self.canvas_widget)
        
        if MATPLOTLIB_AVAILABLE:
            self.fig = Figure(figsize=(5, 3), dpi=100) # Reduced figure size
            self.ax = self.fig.add_subplot(111)
            self.canvas = FigureCanvas(self.fig)
            layout.replaceWidget(self.canvas_widget, self.canvas) # Replace placeholder
            self.canvas_widget.deleteLater()
            self.canvas_widget = self.canvas
        else:
            # Use a QLabel for text-based fallback
            fallback_label = QLabel("Matplotlib不可用，无法显示热力图。")
            fallback_label.setAlignment(Qt.AlignCenter)
            fallback_label.setWordWrap(True)
            layout.replaceWidget(self.canvas_widget, fallback_label)
            self.canvas_widget.deleteLater()
            self.canvas_widget = fallback_label
            
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred) # Allow expansion

    def update_data(self, topics: List[str], values: List[float]):
        if not topics or not values or len(topics) != len(values):
            self.logger.warning("无效的热力图数据，无法更新。")
            return
            
        self._topics = topics
        self._values = values
        
        if MATPLOTLIB_AVAILABLE:
            self._update_chart()
        else:
            self._update_text_display()

    def _update_chart(self):
        if not MATPLOTLIB_AVAILABLE:
            return
            
        self.ax.clear()
        
        if not self._topics or not self._values:
            self.ax.text(0.5, 0.5, '无热力图数据', horizontalalignment='center', verticalalignment='center')
            self.canvas.draw()
            return
            
        # 准备数据: 将一维数据视为Nx1的热力图
        data = np.array(self._values).reshape(-1, 1)
        
        # 使用 imshow 创建热力图
        # cmap: 使用从冷到热的颜色映射 (例如 'coolwarm', 'RdYlBu_r', 'viridis')
        # aspect='auto' 让单元格根据图形大小调整
        # vmin/vmax: 可以设置颜色的范围，例如0到1
        im = self.ax.imshow(data, cmap='viridis', aspect='auto', vmin=0, vmax=1)
        
        # 设置Y轴标签 (话题)
        self.ax.set_yticks(np.arange(len(self._topics)))
        self.ax.set_yticklabels(self._topics)
        
        # 隐藏X轴标签，因为只有一列
        self.ax.set_xticks([])
        
        # 添加颜色条
        # self.fig.colorbar(im, ax=self.ax, label='热度') # 可选
        
        # 添加标题
        self.ax.set_title("话题热度分布", fontsize=10) # Smaller title
        
        # 调整布局以防止标签重叠
        self.fig.tight_layout()
        
        self.canvas.draw()

    def _update_text_display(self):
        if MATPLOTLIB_AVAILABLE or not isinstance(self.canvas_widget, QLabel):
            return
            
        if not self._topics or not self._values:
            self.canvas_widget.setText("无热力图数据")
            return
            
        # 创建基于文本的热力图表示
        text_output = "话题热度分布:\n\n"
        max_len = max(len(t) for t in self._topics) if self._topics else 0
        
        for topic, value in zip(self._topics, self._values):
            # 简单的字符表示热度
            heat_chars = int(value * 10) # 0-10个字符
            heat_str = '*' * heat_chars + '-' * (10 - heat_chars)
            # 保留两位小数
            value_str = f"{value:.2f}"
            text_output += f"{topic:<{max_len}} : [{heat_str}] ({value_str})\n"
            
        self.canvas_widget.setText(text_output)
        self.canvas_widget.setAlignment(Qt.AlignLeft | Qt.AlignTop)


class RadarChartWidget(QWidget):
    """雷达图显示组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.views.radar_chart_widget') # Updated logger
        self._categories: List[str] = []
        self._values: List[float] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.canvas_widget = QWidget()
        layout.addWidget(self.canvas_widget)
        
        if MATPLOTLIB_AVAILABLE:
            self.fig = Figure(figsize=(4, 4), dpi=100) # Square figure
            # 使用极坐标
            self.ax = self.fig.add_subplot(111, polar=True)
            self.canvas = FigureCanvas(self.fig)
            layout.replaceWidget(self.canvas_widget, self.canvas)
            self.canvas_widget.deleteLater()
            self.canvas_widget = self.canvas
        else:
            fallback_label = QLabel("Matplotlib不可用，无法显示雷达图。")
            fallback_label.setAlignment(Qt.AlignCenter)
            fallback_label.setWordWrap(True)
            layout.replaceWidget(self.canvas_widget, fallback_label)
            self.canvas_widget.deleteLater()
            self.canvas_widget = fallback_label
            
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # Allow expansion

    def update_data(self, categories: List[str], values: List[float]):
        if not categories or not values or len(categories) != len(values):
            self.logger.warning("无效的雷达图数据，无法更新。")
            self._categories = []
            self._values = []
        else:
            self._categories = categories
            self._values = values
        
        if MATPLOTLIB_AVAILABLE:
            self._update_chart()
        else:
            self._update_text_display()

    def _update_chart(self):
        if not MATPLOTLIB_AVAILABLE:
            return

        self.ax.clear()
        
        if not self._categories or not self._values:
            self.ax.text(0, 0, '无雷达图数据', ha='center', va='center')
            self.ax.set_xticks([])
            self.ax.set_yticks([])
            self.canvas.draw()
            return
            
        num_vars = len(self._categories)
        
        # 计算角度
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        
        # 使图形闭合
        values = self._values + self._values[:1]
        angles += angles[:1]
        
        # 绘制数据
        self.ax.plot(angles, values, linewidth=1, linestyle='solid', label="特征分布")
        self.ax.fill(angles, values, 'b', alpha=0.4) # 填充颜色
        
        # 设置角度标签
        self.ax.set_xticks(angles[:-1])
        self.ax.set_xticklabels(self._categories, fontsize=8) # Smaller font size
        
        # 设置Y轴范围和标签 (可以根据数据范围调整)
        max_val = max(self._values) if self._values else 1
        self.ax.set_yticks(np.linspace(0, max_val, 4)) # 4个刻度
        self.ax.set_yticklabels([f"{i:.1f}" for i in np.linspace(0, max_val, 4)], fontsize=7)
        self.ax.set_ylim(0, max_val * 1.1) # 留一点空间
        
        # 设置标题
        self.ax.set_title("多维度分析雷达图", size=10, y=1.1) # Adjust title position
        
        # 确保标签不重叠 (tight_layout可能对polar图效果不佳，手动调整)
        # self.fig.tight_layout() # May not work well with polar
        
        self.canvas.draw()

    def _update_text_display(self):
        if MATPLOTLIB_AVAILABLE or not isinstance(self.canvas_widget, QLabel):
            return

        if not self._categories or not self._values:
            self.canvas_widget.setText("无雷达图数据")
            return

        text_output = "多维度分析雷达图:\n\n"
        max_len = max(len(c) for c in self._categories) if self._categories else 0
        for category, value in zip(self._categories, self._values):
            # 保留两位小数
            value_str = f"{value:.2f}"
            text_output += f"{category:<{max_len}} : {value_str}\n"

        self.canvas_widget.setText(text_output)
        self.canvas_widget.setAlignment(Qt.AlignLeft | Qt.AlignTop)


class AdvancedAnalysisVisualizer(QWidget):
    """高级分析可视化面板，整合多种图表"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('news_analyzer.ui.views.advanced_analysis_visualizer') # Updated logger
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 1. 重要程度和立场分析区域 (左右布局)
        top_section_layout = QHBoxLayout()
        top_section_layout.setSpacing(15)

        # 1.1 重要程度指示器
        importance_group = QGroupBox("重要性")
        importance_layout = QVBoxLayout(importance_group)
        self.importance_indicator = ImportanceIndicator()
        importance_layout.addWidget(self.importance_indicator)
        top_section_layout.addWidget(importance_group, 1) # Stretch factor 1

        # 1.2 多维度立场指示器
        stance_group = QGroupBox("立场分析")
        stance_layout = QVBoxLayout(stance_group)
        self.stance_indicator = MultiDimensionalStanceIndicator()
        stance_layout.addWidget(self.stance_indicator)
        top_section_layout.addWidget(stance_group, 2) # Stretch factor 2 (wider)

        main_layout.addLayout(top_section_layout)

        # 2. 图表区域 (Tab Widget)
        chart_tabs = QTabWidget()
        chart_tabs.setObjectName("AnalysisChartTabs")

        # 2.1 雷达图 Tab
        radar_tab = QWidget()
        radar_layout = QVBoxLayout(radar_tab)
        radar_layout.setContentsMargins(5, 5, 5, 5)
        self.radar_chart = RadarChartWidget()
        radar_layout.addWidget(self.radar_chart)
        chart_tabs.addTab(radar_tab, "雷达图分析")

        # 2.2 热力图 Tab
        heatmap_tab = QWidget()
        heatmap_layout = QVBoxLayout(heatmap_tab)
        heatmap_layout.setContentsMargins(5, 5, 5, 5)
        self.topic_heatmap = TopicHeatmapWidget()
        heatmap_layout.addWidget(self.topic_heatmap)
        chart_tabs.addTab(heatmap_tab, "话题热力图")

        main_layout.addWidget(chart_tabs, 1) # Give tabs vertical stretch factor
        
        # 初始化时显示占位信息
        self.reset()

    def update_analysis_data(self, analysis_data: Dict[str, Any]):
        """
        根据提供的分析数据更新所有可视化组件。
        
        Args:
            analysis_data: 包含所有分析结果的字典，期望的键包括：
                'importance' (int): 0-5
                'stance_dimensions' (Dict[str, float]): 如 {"政治立场": 0.5, ...}
                'radar_categories' (List[str]): 雷达图的轴标签
                'radar_values' (List[float]): 雷达图的值
                'heatmap_topics' (List[str]): 热力图的主题标签
                'heatmap_values' (List[float]): 热力图的值 (0-1)
        """
        self.logger.debug(f"Received analysis data: {analysis_data}")
        
        # 更新重要程度
        importance = analysis_data.get('importance', 0)
        self.update_importance(importance)
        
        # 更新立场维度
        stance_dimensions = analysis_data.get('stance_dimensions', {})
        self.update_stance_dimensions(stance_dimensions)
        
        # 更新雷达图
        radar_categories = analysis_data.get('radar_categories', [])
        radar_values = analysis_data.get('radar_values', [])
        self.update_radar_chart(radar_categories, radar_values)
        
        # 更新热力图
        heatmap_topics = analysis_data.get('heatmap_topics', [])
        heatmap_values = analysis_data.get('heatmap_values', [])
        self.update_topic_heatmap(heatmap_topics, heatmap_values)
        
        self.logger.info("高级分析可视化组件已更新。")

    def update_importance(self, importance: int):
        """单独更新重要程度指示器"""
        self.importance_indicator.update_importance(importance)

    def update_stance_dimensions(self, dimensions: Dict[str, float]):
        """单独更新多维度立场指示器"""
        self.stance_indicator.update_all_dimensions(dimensions)

    def update_radar_chart(self, categories: List[str], values: List[float]):
        """单独更新雷达图"""
        self.radar_chart.update_data(categories, values)

    def update_topic_heatmap(self, topics: List[str], values: List[float]):
        """单独更新话题热力图"""
        self.topic_heatmap.update_data(topics, values)

    def reset(self):
        """重置所有可视化组件到默认或空状态"""
        self.logger.debug("重置高级分析可视化组件")
        self.update_importance(0)
        self.update_stance_dimensions({
            "政治立场": 0.0,
            "经济立场": 0.0,
            "社会议题": 0.0,
            "国际关系": 0.0
        }) 
        self.update_radar_chart([], [])
        self.update_topic_heatmap([], [])

# --- Example Usage ---
if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication

    logging.basicConfig(level=logging.DEBUG)
    
    app = QApplication(sys.argv)
    
    window = QWidget()
    main_layout = QVBoxLayout(window)
    
    visualizer = AdvancedAnalysisVisualizer()
    main_layout.addWidget(visualizer)
    
    # 示例数据
    sample_data = {
        'importance': 4,
        'stance_dimensions': {
            "政治立场": -0.7,  # 偏左
            "经济立场": 0.2,   # 略偏自由市场
            "社会议题": -0.5,  # 进步
            "国际关系": 0.8   # 偏单边
        },
        'radar_categories': ['客观性', '深度', '时效性', '影响力', '创新性'],
        'radar_values': [0.8, 0.6, 0.9, 0.7, 0.5],
        'heatmap_topics': ['经济政策', '国际贸易', '科技发展', '社会福利', '环境保护'],
        'heatmap_values': [0.9, 0.7, 0.8, 0.5, 0.6]
    }
    
    # 更新可视化
    visualizer.update_analysis_data(sample_data)
    
    window.setWindowTitle("高级分析可视化测试")
    window.resize(800, 600)
    window.show()
    
    # # 模拟重置
    # QTimer.singleShot(5000, visualizer.reset)
    
    sys.exit(app.exec()) 