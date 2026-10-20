"""统计服务：按本地自然日汇总，跨午夜的对局按时长比例拆分。"""

from __future__ import annotations

import time
from datetime import date, datetime, time as dtime, timedelta

from ..database import Database
from ..models import Game, Overview, Session


def _day_start(day: date) -> int:
    """本地某日 00:00 的 Unix 时间戳。"""
    return int(datetime.combine(day, dtime.min).astimezone().timestamp())


def day_key(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp).astimezone().date().isoformat()


class StatsService:
    def __init__(self, db: Database, clock=time.time) -> None:
        self.db = db
        self.clock = clock

    # ------------------------------------------------------------------ public
    def overview(self, now: float | None = None) -> Overview:
        current = int(now if now is not None else self.clock())
        daily = self.daily_seconds(7, now=current)
        today = datetime.fromtimestamp(current).astimezone().date()
        today_start = _day_start(today)
        sessions_today = [
            session
            for session in self.db.list_sessions_since(today_start)
            if session.started_at >= today_start
        ]
        return Overview(
            today_seconds=daily[-1][1] if daily else 0,
            last7_seconds=sum(value for _, value in daily),
            total_seconds=self.db.total_seconds(),
            game_count=self.db.count_games(),
            sessions_today=len(sessions_today),
            daily=daily,
        )

    def daily_seconds(
        self, days: int = 7, now: float | None = None, game_id: int | None = None
    ) -> list[tuple[str, int]]:
        current = int(now if now is not None else self.clock())
        today = datetime.fromtimestamp(current).astimezone().date()
        dates = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
        starts = [_day_start(day) for day in dates]
        boundaries = starts + [_day_start(today + timedelta(days=1))]
        buckets = {day.isoformat(): 0.0 for day in dates}
        window_start = boundaries[0]

        sessions = self.db.list_sessions_since(window_start)
        if game_id is not None:
            sessions = [session for session in sessions if session.game_id == game_id]
        for session in sessions:
            self._allocate_session(session, boundaries, dates, buckets, current)
        return [(day.isoformat(), int(round(buckets[day.isoformat()]))) for day in dates]

    def ranking(self, limit: int = 5) -> list[tuple[Game, int]]:
        return self.db.top_games(limit)

    def sessions_for_game(self, game_id: int, limit: int = 30) -> list[Session]:
        return self.db.list_sessions(game_id, limit)

    # ----------------------------------------------------------------- private
    @staticmethod
    def _allocate_session(
        session: Session,
        boundaries: list[int],
        dates: list[date],
        buckets: dict[str, float],
        now: int,
    ) -> None:
        duration = max(0, session.duration_seconds)
        if duration == 0:
            return
        start = session.started_at
        end = session.ended_at if session.ended_at is not None else max(now, start)
        wall = end - start
        if wall <= 0:
            return
        allocated = 0.0
        last_index = -1
        for index, day in enumerate(dates):
            bucket_start = boundaries[index]
            bucket_end = boundaries[index + 1]
            overlap = max(0, min(end, bucket_end) - max(start, bucket_start))
            if overlap:
                share = duration * overlap / wall
                buckets[day.isoformat()] += share
                allocated += share
                last_index = index
        # 浮点误差修补到最后一天，避免图表合计相差 1 秒。
        if last_index >= 0:
            deficit = duration - allocated
            if abs(deficit) < 0.01:
                buckets[dates[last_index].isoformat()] += deficit
