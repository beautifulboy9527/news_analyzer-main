# tests/conftest.py
import sys
import os
import logging # 导入 logging

# 将项目根目录添加到 Python 路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- 设置测试期间的日志级别 ---
# 确保测试可以捕获到 INFO 级别的日志
logging.getLogger('news_analyzer.core.app_service').setLevel(logging.INFO)
# 也可以设置根 logger 级别，但这可能影响其他库的日志
# logging.getLogger().setLevel(logging.INFO)
# --- 日志级别设置结束 ---


print(f"conftest.py: Added project root to sys.path: {project_root}")
print(f"conftest.py: Current sys.path: {sys.path}")
print(f"conftest.py: Logger 'news_analyzer.core.app_service' level set to INFO")