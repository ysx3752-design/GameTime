from __future__ import annotations


import pytest

from gametime.database import Database
from gametime.services.library import GameService
from gametime.services.tracking import SessionConflictError, TrackingEngine


def _engine(db: Database, library: GameService, scanner, clock, **kwargs) -> TrackingEngine:
    return TrackingEngine(
        db,
        library,
        scanner,
        clock=clock,
        tick_cap=kwargs.pop("tick_cap", 5),
        persist_interval=kwargs.pop("persist_interval", 10),
        **kwargs,
    )


def test_only_library_games_are_tracked(
    db: Database, library: GameService, scanner, clock, exe_factory, tmp_path
) -> None:
    added = library.add_game("已添加", str(exe_factory("added.exe")))
    unadded = exe_factory("not-added.exe")
    scanner.set_running([added.exe_path, str(unadded)])
    engine = _engine(db, library, scanner, clock)
    engine.poll()
    assert engine.active_runs.keys() == {added.id}
    assert engine.active_source(added.id) == "auto"
    engine.shutdown()
    assert db.list_sessions(added.id)[0].source == "auto"


def test_auto_session_accumulates_and_finishes(
    db: Database, library: GameService, scanner, clock, exe_factory
) -> None:
    game = library.add_game("自动游戏", str(exe_factory("auto.exe")))
    scanner.set_running([game.exe_path])
    events: list[tuple[str, str]] = []
    engine = _engine(db, library, scanner, clock)
    engine.add_listener(lambda event: events.append((event.kind, event.source)))
    engine.poll()
    assert engine.is_active(game.id)
    clock.advance(2)
    engine.poll()
    assert engine.live_elapsed(game.id) >= 2
    clock.advance(2)
    engine.poll()
    scanner.set_running([])
    clock.advance(2)
    engine.poll()
    assert not engine.is_active(game.id)
    sessions = db.list_sessions(game.id)
    assert len(sessions) == 1
    assert sessions[0].status == "completed"
    assert sessions[0].duration_seconds == 6
    assert sessions[0].source == "auto"
    assert events == [("started", "auto"), ("stopped", "auto")]


def test_sleep_gap_is_capped(
    db: Database, library: GameService, scanner, clock, exe_factory
) -> None:
    game = library.add_game("睡眠测试", str(exe_factory("sleep.exe")))
    scanner.set_running([game.exe_path])
    engine = _engine(db, library, scanner, clock, tick_cap=5)
    engine.poll()
    clock.advance(3600)  # 电脑睡眠一小时
    engine.poll()
    assert engine.live_elapsed(game.id) <= 5
    engine.shutdown()
    assert db.list_sessions(game.id)[0].duration_seconds == 5


def test_heartbeat_persists_duration(
    db: Database, library: GameService, scanner, clock, exe_factory
) -> None:
    game = library.add_game("心跳", str(exe_factory("heartbeat.exe")))
    scanner.set_running([game.exe_path])
    engine = _engine(db, library, scanner, clock, persist_interval=10)
    engine.poll()
    for _ in range(5):
        clock.advance(2)
        engine.poll()
    session = db.get_active_session(game.id)
    assert session is not None
    assert session.duration_seconds >= 10
    assert session.last_heartbeat == clock.now
    engine.shutdown()


def test_manual_session_ignores_process_scanner(
    db: Database, library: GameService, scanner, clock, exe_factory
) -> None:
    game = library.add_game("手动游戏", str(exe_factory("manual.exe")))
    engine = _engine(db, library, scanner, clock)
    engine.start_manual(game.id)
    clock.advance(2)
    engine.poll()
    clock.advance(3)
    engine.poll()
    assert engine.active_source(game.id) == "manual"
    elapsed = engine.live_elapsed(game.id)
    engine.stop_manual(game.id)
    assert not engine.is_active(game.id)
    session = db.list_sessions(game.id)[0]
    assert session.source == "manual"
    assert session.duration_seconds == elapsed
    with pytest.raises(SessionConflictError):
        engine.stop_manual(game.id)


def test_conflicting_sessions_rejected(
    db: Database, library: GameService, scanner, clock, exe_factory
) -> None:
    game = library.add_game("冲突", str(exe_factory("conflict.exe")))
    scanner.set_running([game.exe_path])
    engine = _engine(db, library, scanner, clock)
    engine.poll()
    with pytest.raises(SessionConflictError):
        engine.start_manual(game.id)
    engine.shutdown()


def test_shutdown_finalizes_all_active(
    db: Database, library: GameService, scanner, clock, exe_factory
) -> None:
    one = library.add_game("甲", str(exe_factory("one.exe")))
    two = library.add_game("乙", str(exe_factory("two.exe")))
    scanner.set_running([one.exe_path, two.exe_path])
    engine = _engine(db, library, scanner, clock)
    engine.poll()
    clock.advance(4)
    engine.shutdown()
    sessions_one = db.list_sessions(one.id)
    sessions_two = db.list_sessions(two.id)
    assert sessions_one[0].status == "completed"
    assert sessions_two[0].status == "completed"
    assert db.get_active_sessions() == []


def test_recovery_closes_stale_sessions(
    db: Database, library: GameService, scanner, clock, exe_factory
) -> None:
    game = library.add_game("恢复", str(exe_factory("recover.exe")))
    session_id = db.start_session(game.id, "auto", clock.now)
    db.update_session(session_id, duration_seconds=42, heartbeat=clock.now + 10)
    engine = _engine(db, library, scanner, clock)
    assert engine.recovered_sessions == 1
    session = db.list_sessions(game.id)[0]
    assert session.status == "completed"
    assert session.duration_seconds == 42
    assert session.ended_at == clock.now + 10
    engine.shutdown()


def test_deleted_game_is_removed_from_active_runs(
    db: Database, library: GameService, scanner, clock, exe_factory
) -> None:
    game = library.add_game("删除中", str(exe_factory("deleted.exe")))
    scanner.set_running([game.exe_path])
    engine = _engine(db, library, scanner, clock)
    engine.poll()
    assert engine.is_active(game.id)
    db.delete_game(game.id)
    clock.advance(2)
    engine.poll()
    assert not engine.is_active(game.id)
