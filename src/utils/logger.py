# src/utils/logger.py
import logging
import os
import sys
# from logging.handlers import RotatingFileHandler # 移除旧的导入
from logging.handlers import TimedRotatingFileHandler # 导入新的 Handler

# 确定日志目录
# 假设此文件位于 src/utils/logger.py
# 项目根目录是 src 的上一级
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
log_dir = os.path.join(project_root, 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'news_analyzer.log')

# 全局日志记录器名称
LOGGER_NAME = "news_analyzer"

def setup_logging(log_level: int = logging.INFO, backup_count: int = 7, when: str = 'D', interval: int = 1) -> logging.Logger:
    """
    配置全局日志记录器。

    Args:
        log_level: 日志记录级别 (例如 logging.DEBUG, logging.INFO).
        backup_count: 保留的备份日志文件数量.
        when: 轮转间隔类型 ('S', 'M', 'H', 'D', 'W0'-'W6', 'midnight'). 默认为 'D' (天).
        interval: 轮转间隔数量. 默认为 1.

    Returns:
        配置好的 Logger 对象.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(log_level)

    # 防止重复添加 handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 文件处理器 (按时间滚动日志)
    file_handler = TimedRotatingFileHandler(
        log_file,
        when=when,         # 按天轮转
        interval=interval, # 每天轮转一次
        backupCount=backup_count, # 保留 7 个备份文件 (7 天)
        encoding='utf-8',
        utc=False          # 使用本地时间
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 控制台处理器
    stream_handler = logging.StreamHandler(sys.stdout) # 输出到标准输出
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # 更新日志消息以反映时间轮转
    logger.info(f"日志系统已初始化。日志级别: {logging.getLevelName(log_level)}, 日志文件: {log_file}, 按时间轮转 (when='{when}', interval={interval}, backupCount={backup_count})")
    return logger

def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    """
    获取指定名称的日志记录器。如果未设置，则返回根日志记录器。

    Args:
        name: 日志记录器的名称。

    Returns:
        logging.Logger 对象。
    """
    return logging.getLogger(name)

# 使用示例 (通常在模块内部不直接调用 setup_logging，而是在应用入口处调用)
if __name__ == "__main__":
    # 示例：在 DEBUG 级别设置日志
    logger_instance = setup_logging(log_level=logging.DEBUG)
    logger_instance.debug("这是一个 DEBUG 级别的日志消息。")
    logger_instance.info("这是一个 INFO 级别的日志消息。")
    logger_instance.warning("这是一个 WARNING 级别的日志消息。")
    logger_instance.error("这是一个 ERROR 级别的日志消息。")

    # 获取同一个 logger
    another_logger = get_logger()
    another_logger.info("通过 get_logger 获取的实例。")

    # 获取子 logger (继承根 logger 的设置)
    child_logger = get_logger("news_analyzer.module")
    child_logger.info("这是子模块的日志消息。")