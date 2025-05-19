"""
简单取消标志类，用于线程间的取消信号传递。
"""

import threading

class CancellationFlag:
    """一个简单的线程安全的取消标志。"""
    def __init__(self):
        self._is_set = False
        self._lock = threading.Lock()

    def set(self):
        """设置取消标志。"""
        with self._lock:
            self._is_set = True

    def clear(self):
        """清除取消标志。"""
        with self._lock:
            self._is_set = False

    def is_set(self) -> bool:
        """检查取消标志是否已设置。"""
        with self._lock:
            return self._is_set 