# src/utils/date_utils.py
from datetime import datetime, date, timedelta
from typing import Optional

def format_datetime_friendly(dt: Optional[datetime]) -> str:
    """
    将 datetime 对象格式化为用户友好的字符串。

    - 如果是今天，显示 "今天 HH:MM"。
    - 如果是昨天，显示 "昨天 HH:MM"。
    - 否则，显示 "YYYY-MM-DD HH:MM"。
    - 如果输入为 None，返回 "未知时间"。
    """
    if dt is None:
        return "未知时间"

    now = datetime.now()
    today = now.date()
    yesterday = today - timedelta(days=1)

    dt_date = dt.date()

    if dt_date == today:
        return f"今天 {dt.strftime('%H:%M')}"
    elif dt_date == yesterday:
        return f"昨天 {dt.strftime('%H:%M')}"
    else:
        # 对于更早的日期，可以只显示日期或完整日期时间
        # return dt.strftime('%Y-%m-%d')
        return dt.strftime('%Y-%m-%d %H:%M')