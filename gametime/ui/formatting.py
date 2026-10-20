"""界面文本格式化。"""

from __future__ import annotations

from datetime import datetime, timedelta

WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


def format_duration(seconds: int, *, zero: str = "0 分钟", compact: bool = False) -> str:
    seconds = max(0, int(seconds))
    if seconds <= 0:
        return zero
    minutes = seconds // 60
    hours, remaining_minutes = divmod(minutes, 60)
    if compact:
        if hours:
            return f"{hours}h {remaining_minutes:02d}m"
        if minutes:
            return f"{minutes}m"
        return f"{seconds}s"
    if hours:
        return f"{hours} 小时 {remaining_minutes:02d} 分"
    if minutes:
        return f"{minutes} 分钟"
    return "不足 1 分钟"


def format_big_duration(seconds: int) -> str:
    """用于概览大数字，拆分为数值和单位。"""
    seconds = max(0, int(seconds))
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} 分钟"
    hours, remaining = divmod(minutes, 60)
    if remaining == 0:
        return f"{hours} 小时"
    return f"{hours} 小时 {remaining:02d} 分"


def format_clock(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _local_datetime(timestamp: int) -> datetime | None:
    try:
        return datetime.fromtimestamp(timestamp).astimezone()
    except (OverflowError, OSError, ValueError):
        return None


def format_last_played(timestamp: int | None) -> str:
    if not timestamp:
        return "还没有游玩记录"
    moment = _local_datetime(timestamp)
    if moment is None:
        return "记录时间不可用"
    now = datetime.now().astimezone()
    today = now.date()
    if moment.date() == today:
        return f"今天 {moment:%H:%M}"
    if moment.date() == today - timedelta(days=1):
        return f"昨天 {moment:%H:%M}"
    if moment.year == now.year:
        return f"{moment.month}月{moment.day}日 {moment:%H:%M}"
    return f"{moment.year}年{moment.month}月{moment.day}日"


def format_date_heading(moment: datetime | None = None) -> str:
    current = (moment or datetime.now()).astimezone()
    return f"{current.year}年{current.month}月{current.day}日 · {WEEKDAYS[current.weekday()]}"


def greeting(moment: datetime | None = None) -> str:
    hour = (moment or datetime.now()).astimezone().hour
    if 5 <= hour < 11:
        return "早上好"
    if 11 <= hour < 13:
        return "中午好"
    if 13 <= hour < 18:
        return "下午好"
    if 18 <= hour < 23:
        return "晚上好"
    return "夜深了"


def format_session_time(timestamp: int) -> str:
    moment = _local_datetime(timestamp)
    if moment is None:
        return "时间不可用"
    now = datetime.now().astimezone()
    today = now.date()
    if moment.date() == today:
        prefix = "今天"
    elif moment.date() == today - timedelta(days=1):
        prefix = "昨天"
    else:
        prefix = f"{moment.month}月{moment.day}日"
    return f"{prefix} {moment:%H:%M}"


def format_session_range(start: int, end: int | None) -> str:
    start_dt = _local_datetime(start)
    if start_dt is None:
        return "时间记录不可用"
    if end:
        end_dt = _local_datetime(end)
        if end_dt is None:
            return f"{format_session_time(start)} – 时间不可用"
        if start_dt.date() == end_dt.date():
            return f"{format_session_time(start)} – {end_dt:%H:%M}"
        return f"{format_session_time(start)} – {format_session_time(end)}"
    return f"{format_session_time(start)} – 进行中"


def format_bytes(size: int) -> str:
    value = float(max(0, size))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"
