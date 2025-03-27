#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
新闻聚合与分析系统 - 主程序入口

该文件是应用程序的入口点，负责初始化和启动GUI应用程序。
"""

import sys
import os
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

# 确保项目根目录在Python路径中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入项目模块
from news_analyzer.ui.main_window import MainWindow
from news_analyzer.storage.news_storage import NewsStorage
from news_analyzer.collectors.rss_collector import RSSCollector
from news_analyzer.collectors.default_sources import initialize_sources


def setup_logging():
    """设置日志记录"""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'news_analyzer.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 创建根日志记录器
    logger = logging.getLogger('news_analyzer')
    logger.info('新闻聚合与分析系统启动')
    
    return logger


def main():
    """主函数，初始化和启动应用程序"""
    # 设置日志记录
    logger = setup_logging()
    
    try:
        # 初始化数据存储
        storage = NewsStorage()
        
        # 初始化RSS收集器
        rss_collector = RSSCollector()
        
        # 添加预设新闻源
        sources_count = initialize_sources(rss_collector)
        logger.info(f"已初始化 {sources_count} 个预设新闻源")
        
        # 创建Qt应用程序
        app = QApplication(sys.argv)
        app.setApplicationName("新闻聚合与分析系统")
        
        # 创建并显示主窗口
        main_window = MainWindow(storage, rss_collector)
        main_window.show()
        
        # 执行应用程序事件循环
        sys.exit(app.exec_())
        
    except Exception as e:
        logger.error(f"应用程序启动失败: {str(e)}", exc_info=True)
        print(f"错误: 应用程序启动失败 - {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()