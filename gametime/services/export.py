"""CSV 导出。"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from ..database import Database

HEADERS = ["游戏", "程序路径", "开始时间", "结束时间", "时长（秒）", "时长（分钟）", "计时方式", "状态"]


def _local_time(timestamp: int | None) -> str:
    if timestamp is None:
        return ""
    return datetime.fromtimestamp(timestamp).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def export_sessions_csv(db: Database, destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = db.export_rows()
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS)
        for row in rows:
            writer.writerow(
                [
                    row["game_name"],
                    row["exe_path"],
                    _local_time(row["started_at"]),
                    _local_time(row["ended_at"]),
                    int(row["duration_seconds"]),
                    round(int(row["duration_seconds"]) / 60, 1),
                    "自动" if row["source"] == "auto" else "手动",
                    "进行中" if row["status"] == "active" else "已完成",
                ]
            )
    return path
