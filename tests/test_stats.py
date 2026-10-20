from __future__ import annotations

from datetime import datetime

from gametime.database import Database
from gametime.services.library import GameService
from gametime.services.stats import StatsService


def _ts(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
    return int(datetime(year, month, day, hour, minute).astimezone().timestamp())


def _add_session(db: Database, game_id: int, start: int, duration: int, source: str = "auto") -> None:
    session_id = db.start_session(game_id, source, start)
    db.finish_session(session_id, duration_seconds=duration, ended_at=start + duration)


def test_today_week_total_and_ranking(
    db: Database, library: GameService, exe_factory
) -> None:
    game_a = library.add_game("A", str(exe_factory("a.exe")))
    game_b = library.add_game("B", str(exe_factory("b.exe")))
    now = _ts(2026, 10, 20, 18, 0)
    _add_session(db, game_a.id, _ts(2026, 10, 20, 9), 3600)
    _add_session(db, game_a.id, _ts(2026, 10, 20, 14), 1800)
    _add_session(db, game_b.id, _ts(2026, 10, 19, 20), 2400)
    _add_session(db, game_b.id, _ts(2026, 10, 10, 20), 900)
    stats = StatsService(db, clock=lambda: now)
    overview = stats.overview()
    assert overview.today_seconds == 5400
    assert overview.last7_seconds == 7800
    assert overview.total_seconds == 8700
    assert overview.game_count == 2
    assert overview.sessions_today == 2
    assert len(overview.daily) == 7
    ranking = stats.ranking(5)
    assert ranking[0][0].id == game_a.id
    assert ranking[0][1] == 5400


def test_cross_midnight_is_split(
    db: Database, library: GameService, exe_factory
) -> None:
    game = library.add_game("午夜", str(exe_factory("midnight.exe")))
    now = _ts(2026, 10, 21, 12)
    _add_session(db, game.id, _ts(2026, 10, 20, 23, 30), 3600)
    stats = StatsService(db, clock=lambda: now)
    daily = dict(stats.daily_seconds(2, now=now))
    assert sum(daily.values()) == 3600
    assert daily["2026-10-20"] == 1800
    assert daily["2026-10-21"] == 1800


def test_active_session_contributes(
    db: Database, library: GameService, exe_factory
) -> None:
    game = library.add_game("进行中", str(exe_factory("active.exe")))
    now = _ts(2026, 10, 20, 18)
    session_id = db.start_session(game.id, "manual", now - 600)
    db.update_session(session_id, duration_seconds=300, heartbeat=now)
    stats = StatsService(db, clock=lambda: now)
    assert stats.overview().today_seconds == 300


def test_empty_stats(db: Database) -> None:
    stats = StatsService(db)
    overview = stats.overview()
    assert overview.game_count == 0
    assert overview.today_seconds == 0
    assert overview.daily
    assert stats.ranking() == []


def test_session_filter_by_game(db: Database, library: GameService, exe_factory) -> None:
    one = library.add_game("一", str(exe_factory("one.exe")))
    two = library.add_game("二", str(exe_factory("two.exe")))
    now = _ts(2026, 10, 20, 18)
    _add_session(db, one.id, _ts(2026, 10, 20, 10), 600)
    _add_session(db, two.id, _ts(2026, 10, 20, 11), 1200)
    stats = StatsService(db, clock=lambda: now)
    daily_one = stats.daily_seconds(1, now=now, game_id=one.id)
    assert daily_one[0][1] == 600
    sessions = stats.sessions_for_game(one.id)
    assert len(sessions) == 1
