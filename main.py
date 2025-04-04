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

from dotenv import load_dotenv # 导入 load_dotenv

from PyQt5.QtWidgets import QApplication, QWidget
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
from ui.main_window import MainWindow           # 从 src/ui 导入
from ui.theme_manager import ThemeManager         # 导入 ThemeManager
from ui.ui_settings_manager import UISettingsManager # 导入 UI 设置管理器
# 导入 AppService 类以供手动实例化
from src.core.app_service import AppService


# 注意：确保所有被导入的模块路径相对于 src 目录是正确的
# 例如, 如果 MainWindow 在 src/ui/main_window.py, 导入应为 from ui.main_window import MainWindow


def main() -> NoReturn:
    """
    应用程序主函数。

    初始化日志、核心服务和UI，然后启动Qt事件循环。
    在退出时确保资源被正确关闭。
    """
    # 1. 设置日志记录 (使用新的日志模块)
    # 必须先设置日志，才能记录后续信息
    setup_logging(log_level=logging.INFO)  #恢复 INFO 级别
    logger = get_logger("main_entry") # 获取名为 'main_entry' 的 logger
    # logging.getLogger('news_analyzer.ui.chat_panel').setLevel(logging.DEBUG) # Removed explicit DEBUG
    # logging.getLogger('news_analyzer.ui.viewmodels.news_list_viewmodel').setLevel(logging.DEBUG) # Removed explicit DEBUG
    # logging.getLogger('ui.theme_manager').setLevel(logging.DEBUG) # Removed explicit DEBUG
    # logger.info("Explicitly set DEBUG level for ... logger.") # Removed log message

    # 加载 .env 文件中的环境变量 (移动到 logger 初始化之后)
    load_dotenv()
    logger.info(".env 文件已加载 (如果存在)") # 现在可以安全地使用 logger

    logger.info("应用程序启动...")
    logger.info(f"Python 版本: {sys.version}")
    logger.info(f"项目根目录: {project_root}")
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
    try:
        # 2. 初始化核心组件
        logger.debug("初始化应用服务...")
        try:
            # --- 手动实例化 AppService ---
            # a. 从容器获取依赖项实例
            logger.debug("从容器获取 AppService 的依赖项...")
            llm_config_manager = container.llm_config_manager()
            storage = container.news_storage()
            source_manager = container.source_manager()
            api_client = container.api_client() # 获取 ApiClient
            llm_service = container.llm_service(
                config_manager=llm_config_manager, # 显式传递依赖
                prompt_manager=container.prompt_manager(),
                api_client=api_client
            )
            logger.debug("AppService 依赖项获取完成。")

            # b. 创建 AppService 实例，传入依赖
            logger.debug("手动创建 AppService 实例...")
            app_service = AppService(
                llm_config_manager=llm_config_manager,
                storage=storage,
                source_manager=source_manager,
                llm_service=llm_service
            )

            # --- 调用依赖初始化 ---
            app_service._initialize_dependencies()
            logger.info(f"应用服务初始化成功: {app_service}")
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
        except Exception as e:
            logger.error(f"创建QApplication失败: {str(e)}", exc_info=True)
            raise # Re-raise the exception

        # --- 初始化并应用主题 ---
        theme_manager = ThemeManager()
        theme_manager.apply_saved_theme() # 应用保存的主题或默认主题
        logger.info(f"已应用启动主题: {theme_manager.get_current_theme()}") # Log the actually applied theme

        # --- 初始化并应用 UI 设置 (字体大小) ---
        ui_settings_manager = UISettingsManager()
        ui_settings_manager.apply_saved_font_size()
        logger.info(f"已应用字体大小: {ui_settings_manager.get_current_font_size()}pt")



        logger.debug("创建主窗口 MainWindow...")
        try:
            # --- 手动实例化 MainWindow ---
            main_window = MainWindow(app_service=app_service) # 传入 AppService
            logger.info("主窗口创建完成，准备显示。")

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

        # 4. 启动 Qt 事件循环
        logger.info("启动 Qt 事件循环...")
        try:
            exit_code = app.exec_()
            logger.info(f"Qt事件循环退出，代码: {exit_code}")
        except Exception as e:
            logger.error(f"Qt事件循环异常: {str(e)}", exc_info=True)
            raise # Re-raise the exception
        logger.info(f"Qt 事件循环结束，退出代码: {exit_code}")

        # 5. 应用程序退出前的清理工作
        logger.info("应用程序准备退出，关闭资源...")
        if app_service: # Check if app_service was successfully created
            app_service.close_resources() # 调用 AppService 的清理方法
            logger.info("资源已关闭。")
        else:
            logger.warning("AppService 未成功初始化，无法关闭资源。")

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