#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
新闻聚合与分析系统 - 主程序入口 (重构后)

该文件是应用程序的入口点，负责初始化核心服务、设置日志记录和启动GUI应用程序。
"""

import sys
import os
import logging
from typing import NoReturn
from logging.handlers import TimedRotatingFileHandler
from dependency_injector.wiring import inject, Provide
from PySide6.QtWidgets import QApplication, QWidget # Use PySide6 consistently
from PySide6.QtCore import QSettings, QTranslator, QLibraryInfo, QLocale # Import QSettings, QTranslator, QLibraryInfo, QLocale
# from PyQt5.QtGui import QIcon # QIcon 可以在 MainWindow 内部设置
# 导入依赖注入容器
from src.containers import Container
 # 修正导入路径

# 将项目根目录添加到 Python 路径，以便导入 src 包
# __file__ 指向 main.py 所在的目录 (项目根目录)
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src') # src 目录的路径
if src_path not in sys.path:
    sys.path.insert(0, src_path) # 将 src 目录添加到 sys.path

# 导入重构后的模块
from utils.logger import setup_logging, get_logger # 从 src/utils 导入
# from ui.main_window import MainWindow           # 从 src/ui 导入 - Old path
from ui.views.main_window import MainWindow         # 从 src/ui/views 导入 - Corrected path
from ui.theme_manager import ThemeManager         # 导入 ThemeManager
from ui.ui_settings_manager import UISettingsManager # 导入 UI 设置管理器
# 导入 AppService 类以供手动实例化
from src.core.app_service import AppService
# --- Import SchedulerService ---
from services.scheduler_service import SchedulerService
# --- End Import ---


# 注意：确保所有被导入的模块路径相对于 src 目录是正确的
# 例如, 如果 MainWindow 在 src/ui/main_window.py, 导入应为 from ui.main_window import MainWindow


def main() -> NoReturn:
    """
    应用程序主函数。

    初始化日志、核心服务和UI，然后启动Qt事件循环。
    在退出时确保资源被正确关闭。
    """
    # --- 1. 初始化日志 ---
    # 日志模块内部会确定日志路径
    setup_logging(log_level=logging.INFO)  # 使用正确的关键字参数名 log_level
    logger = get_logger("main_entry") # 获取 logger

    # --- 定义 project_root (移到使用它之前) ---
    # 假设 .env 在 main.py 的上一级目录 (项目根目录)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logger.info(f"项目根目录: {project_root}") # 可以记录一下

    # --- 加载 .env ---
    dotenv_path = os.path.join(project_root, '.env')
    if os.path.exists(dotenv_path):
        try:
            # 显式加载指定路径的 .env 文件
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=dotenv_path)
            logger.info(f"已加载 .env 文件: {dotenv_path}")
        except ImportError:
            logger.warning("未安装 python-dotenv 模块，无法加载 .env 文件。请运行 'pip install python-dotenv'")
        except Exception as e:
            logger.error(f"加载 .env 文件时出错: {e}", exc_info=True)
    else:
        logger.info(f".env 文件未找到于: {dotenv_path}，跳过加载环境变量。")

    logger.info("应用程序启动")
    logger.info(f"Python 版本: {sys.version}")
    logger.info(f"Src 目录已添加到 sys.path: {src_path}")


    # --- 初始化依赖注入容器 ---
    container = Container()

    # --- 加载配置并提供给容器 ---
    # TODO: 完善配置加载逻辑，确保路径等信息正确注入
    # 临时使用默认配置或空配置，以便程序运行
    container.config.from_dict({
        "paths": {
            "database": os.path.join(project_root, "data", "news_data.db"), # 示例数据库路径
            "data_dir": os.path.join(project_root, "data"), # 添加数据目录路径
            "config": os.path.join(project_root, "config", "settings.ini") # 示例配置文件路径
        },
        # 其他配置...
    })
    # logger.warning("使用了临时默认配置注入容器，请后续完善配置加载逻辑！") # Commented out warning

    # --- 容器接线 (Wiring) ---
    # 移除 Wiring，因为我们将手动实例化
    # container.wire(modules=[__name__, "src.ui.main_window", "src.core.app_service"])
    # logger.info("依赖注入容器已连接到模块: main, ui.main_window, core.app_service")

    app_service = None # Initialize app_service to None
    scheduler_service = None # Initialize scheduler_service to None
    try:
        # 2. 初始化核心组件
        logger.debug("从容器获取 AppService 实例...")
        try:
            # --- 直接从容器获取 AppService ---
            app_service = container.app_service() # <--- 修改点

            # --- 调用依赖初始化 ---
            # app_service._initialize_dependencies() # 确保 AppService 内部依赖连接 # Removed this line
            logger.info(f"应用服务初始化成功: {app_service}")

            # --- START: 一次性数据库清理 --- 
            if app_service and app_service.storage:
                logger.info("执行一次性数据库清理：删除 publish_time 为 NULL 的新闻条目...")
                try:
                    # news_storage_instance = app_service.storage # AppService 持有 NewsStorage 实例
                    # 直接使用 AppService 已经持有的 storage 实例
                    deleted_count = app_service.storage.delete_articles_with_null_publish_time()
                    if deleted_count >= 0:
                        logger.info(f"数据库清理完成。成功删除了 {deleted_count} 条 publish_time 为 NULL 的新闻。")
                    else:
                        logger.error("数据库清理过程中发生错误。")
                except AttributeError as ae:
                    logger.error(f"执行数据库清理失败: AppService 可能没有 storage 属性或 storage 没有 delete_articles_with_null_publish_time 方法: {ae}", exc_info=True)
                except Exception as e_clean:
                    logger.error(f"执行数据库清理时发生意外错误: {e_clean}", exc_info=True)
            else:
                logger.warning("AppService 或其 storage 未初始化，跳过数据库清理。")
            # --- END: 一次性数据库清理 ---

        except Exception as e:
            logger.error(f"初始化应用服务失败: {str(e)}", exc_info=True)
            raise # Re-raise the exception to be caught by the outer try-except

        # 3. 创建并运行 Qt 应用程序
        logger.debug("创建 QApplication...")
        try:
            app = QApplication(sys.argv)
            app.setApplicationName("讯析") # Updated App Name
            app.setOrganizationName("YourCompany") # Keep consistent with QSettings
            logger.info("QApplication创建成功")
            # app.setWindowIcon(QIcon("path/to/icon.png")) # 如果需要设置图标

            # --- 加载 Qt 标准中文翻译 --- 
            qt_translator = QTranslator()
            # 尝试从标准路径加载
            translations_path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
            loaded = False
            if translations_path:
                logger.info(f"尝试从 {translations_path} 加载 Qt 中文翻译...")
                # 尝试加载系统区域设置对应的翻译
                if qt_translator.load(QLocale.system(), "qtbase", "_", translations_path):
                    app.installTranslator(qt_translator)
                    logger.info(f"成功加载 Qt 翻译文件 (区域: {QLocale.system().name()})。")
                    loaded = True
                else:
                    # 如果系统区域设置加载失败，尝试显式加载中文
                    if qt_translator.load("qtbase_zh_CN", translations_path):
                        app.installTranslator(qt_translator)
                        logger.info("成功加载 Qt 翻译文件 (qtbase_zh_CN.qm)。")
                        loaded = True
                    else:
                        logger.warning(f"在 {translations_path} 中未找到 qtbase_zh_CN.qm 或系统区域设置对应的翻译文件。标准按钮可能显示英文。")
            else:
                logger.warning("无法获取 Qt 翻译文件路径。标准按钮可能显示英文。")
            # --- 翻译加载结束 ---
        except Exception as e:
            logger.error(f"创建QApplication失败: {str(e)}", exc_info=True)
            raise # Re-raise the exception

        # --- Initialize QSettings ---
        logger.debug("Initializing QSettings...")
        settings = QSettings(app.organizationName(), app.applicationName())
        logger.info(f"QSettings initialized for {app.organizationName()}/{app.applicationName()}")
        # --- End QSettings Initialization ---

        # --- Initialize SchedulerService ---
        logger.debug("Initializing SchedulerService...")
        try:
            scheduler_service = SchedulerService(settings=settings)
            if app_service:
                scheduler_service.set_app_service(app_service)
                logger.info("AppService injected into SchedulerService.")
                # Inject AnalysisService into SchedulerService if needed (unlikely for now)
                # scheduler_service.set_analysis_service(analysis_service)
            else:
                logger.error("AppService not initialized, cannot inject into SchedulerService!")
                # Handle this error? Maybe don't start the scheduler?
            logger.info("SchedulerService initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize SchedulerService: {e}", exc_info=True)
            # Decide how to handle this - maybe continue without scheduler?
        # --- End SchedulerService Initialization ---

        logger.debug("创建主窗口 MainWindow...")
        try:
            # --- 手动实例化 MainWindow ---
            main_window = MainWindow(app_service=app_service,
                                  # analysis_service=analysis_service, # REMOVED - Not expected by MainWindow
                                  scheduler_service=scheduler_service, # Pass scheduler_service
                                  container=container) # Pass container
            logger.info("主窗口创建完成，准备显示。")
            # Theme and font settings will be applied later

            # --- 连接 AppService shutdown 和 SchedulerService stop 到 aboutToQuit 信号 ---
            if app_service:
                app.aboutToQuit.connect(app_service.shutdown)
                logger.info("已连接 QApplication.aboutToQuit 信号到 AppService.shutdown")
            else:
                logger.error("AppService 未初始化，无法连接退出信号！")

            if scheduler_service:
                app.aboutToQuit.connect(scheduler_service.stop)
                logger.info("已连接 QApplication.aboutToQuit 信号到 SchedulerService.stop")
            else:
                logger.warning("SchedulerService 未初始化，无法连接退出信号。")
            # --- 信号连接结束 ---

            # 显示窗口并验证
            main_window.show()
            if not main_window.isVisible():
                logger.error("主窗口显示失败！")
                raise RuntimeError("无法显示主窗口")

            logger.info(f"主窗口已显示，尺寸: {main_window.size().width()}x{main_window.size().height()}")
            logger.info(f"主窗口标题: {main_window.windowTitle()}")

            # 强制设置窗口位置和状态 (可能不需要，取决于 restoreGeometry/State 的效果)
            # screen = QApplication.primaryScreen().geometry()
            # window_width = 1200
            # window_height = 800
            # x = (screen.width() - window_width) // 2
            # y = (screen.height() - window_height) // 2
            # main_window.setGeometry(x, y, window_width, window_height)
            # main_window.showNormal()  # 确保不是最小化状态

            # 确保窗口获得焦点并强制重绘
            main_window.raise_()
            main_window.activateWindow()
            main_window.repaint()
            QApplication.processEvents()

            # 验证窗口显示状态持续
            if not main_window.isVisible():
                logger.error("主窗口未能保持显示状态！")
                raise RuntimeError("窗口显示失败")

            logger.info("窗口显示验证完成，准备进入主事件循环")

        except Exception as e:
            logger.error(f"创建/显示主窗口失败: {str(e)}", exc_info=True)
            raise # Re-raise the exception

        # --- 初始化并应用主题和字体 (移到显示窗口之后, 事件循环之前) ---
        try:
            theme_manager = ThemeManager()
            theme_manager.apply_initial_theme() # 应用初始主题 (已重构)
            logger.info(f"已应用启动主题: {theme_manager.get_current_theme()}")
        except Exception as e:
            logger.error(f"应用主题时出错: {e}", exc_info=True)
        try:
            ui_settings_manager = UISettingsManager()
            ui_settings_manager.apply_saved_font_size()
            logger.info(f"已应用字体大小: {ui_settings_manager.get_current_font_size()}pt")
        except Exception as e:
            logger.error(f"应用字体大小时出错: {e}", exc_info=True)
        logger.info("主题和字体设置已应用。")
        # --- End Theme/Font Application ---

        # --- Start SchedulerService ---
        if scheduler_service:
            logger.info("Starting SchedulerService...")
            scheduler_service.start() # Start based on QSettings
        else:
            logger.warning("SchedulerService not initialized, cannot start.")
        # --- End SchedulerService Start ---

        # 4. 启动 Qt 事件循环
        logger.info("启动 Qt 事件循环...")
        try:
            exit_code = app.exec()
            logger.info(f"Qt事件循环退出，代码: {exit_code}")
        except Exception as e:
            logger.error(f"Qt事件循环异常: {str(e)}", exc_info=True)
            raise # Re-raise the exception
        logger.info(f"Qt 事件循环结束，退出代码: {exit_code}")

        # 5. 应用程序退出前的清理工作 (现在由 aboutToQuit 信号处理)
        logger.info("应用程序准备退出... (清理工作通过 aboutToQuit 信号处理)")
        # if app_service: # Check if app_service was successfully created
        #     app_service.close_resources() # 调用 AppService 的清理方法
        #     logger.info("资源已关闭。")
        # else:
        #     logger.warning("AppService 未成功初始化，无法关闭资源。")

        sys.exit(exit_code)

    except ImportError as e:
        # 特别处理导入错误，可能指示目录结构或 PYTHONPATH 问题
        logger.error(f"导入模块时出错: {e}", exc_info=True)
        print(f"错误: 无法导入必要的模块 '{e.name}'。请检查项目结构和 PYTHONPATH 设置。", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # 捕获其他所有未预料到的异常
        logger.error(f"应用程序运行时发生未处理的异常: {str(e)}", exc_info=True)
        print(f"严重错误: 应用程序意外终止 - {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # 确保脚本作为主程序运行时执行 main 函数
    main()