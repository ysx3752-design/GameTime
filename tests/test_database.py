from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gametime.database import Database, SCHEMA_VERSION
from gametime.services.library import DuplicateGameError, GameService, GameValidationError


def test_database_schema_and_foreign_keys(db: Database) -> None:
    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert db.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    tables = {
        row[0]
        for row in db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"games", "sessions", "settings"} <= tables


def test_game_crud_and_unique_path(library: GameService, exe_factory, db: Database) -> None:
    exe = exe_factory("EldenRing.exe")
    game = library.add_game("艾尔登法环", str(exe), "通关中")
    assert game.id > 0
    assert game.exe_name == "EldenRing.exe"
    assert game.notes == "通关中"
    assert game.icon_file
    assert library.icon_path(game) is not None
    assert library.summary(game.id).total_seconds == 0

    with pytest.raises(DuplicateGameError):
        library.add_game("另一个名字", str(exe).upper())

    updated = library.update_game(game.id, "艾尔登法环 · 黄金树", str(exe), "新备注")
    assert updated.name == "艾尔登法环 · 黄金树"
    assert updated.notes == "新备注"
    assert library.get_game(game.id).name == "艾尔登法环 · 黄金树"

    library.remove_game(game.id)
    assert db.get_game(game.id) is None


def test_game_validation(library: GameService, tmp_path: Path) -> None:
    with pytest.raises(GameValidationError):
        library.add_game("空路径", "")
    text_file = tmp_path / "readme.txt"
    text_file.write_text("not a game")
    with pytest.raises(GameValidationError):
        library.add_game("文本", str(text_file))
    with pytest.raises(GameValidationError):
        library.add_game("不存在", str(tmp_path / "nope.exe"))


def test_remove_game_cascades_sessions(db: Database, library: GameService, exe_factory) -> None:
    game = library.add_game("游戏", str(exe_factory()))
    session_id = db.start_session(game.id, "auto", 1000)
    db.finish_session(session_id, duration_seconds=60, ended_at=1060)
    assert db.game_summary(game.id)[0] == 60
    library.remove_game(game.id)
    assert db.list_sessions(game.id) == []
    assert db.total_seconds() == 0


def test_session_lifecycle_and_unique_active(db: Database, sample_game) -> None:
    session_id = db.start_session(sample_game.id, "auto", 1000)
    assert db.get_active_session(sample_game.id).id == session_id
    with pytest.raises(sqlite3.IntegrityError):
        db.start_session(sample_game.id, "manual", 1001)
    db.update_session(session_id, duration_seconds=30, heartbeat=1030)
    active = db.get_active_session(sample_game.id)
    assert active.duration_seconds == 30
    db.finish_session(session_id, duration_seconds=55, ended_at=1055)
    assert db.get_active_session(sample_game.id) is None
    sessions = db.list_sessions(sample_game.id)
    assert sessions[0].status == "completed"
    assert sessions[0].duration_seconds == 55
    assert sessions[0].ended_at == 1055


def test_close_open_sessions_uses_last_heartbeat(db: Database, sample_game) -> None:
    session_id = db.start_session(sample_game.id, "auto", 1000)
    db.update_session(session_id, duration_seconds=17, heartbeat=1020)
    recovered = db.close_open_sessions()
    assert recovered == 1
    session = db.list_sessions(sample_game.id)[0]
    assert session.status == "completed"
    assert session.ended_at == 1020
    assert session.duration_seconds == 17
    assert db.close_open_sessions() == 0


def test_settings_roundtrip(db: Database) -> None:
    assert db.get_setting("missing") is None
    assert db.get_setting("missing", "fallback") == "fallback"
    db.set_setting("close_to_tray", "0")
    assert db.get_setting("close_to_tray") == "0"
    db.set_setting("close_to_tray", "1")
    assert db.get_setting("close_to_tray") == "1"


def test_list_sort_and_search(db: Database, library: GameService, exe_factory) -> None:
    first = library.add_game("Alpha 冒险", str(exe_factory("alpha.exe")))
    second = library.add_game("Beta 世界", str(exe_factory("beta.exe")))
    s1 = db.start_session(first.id, "auto", 1000)
    db.finish_session(s1, duration_seconds=120, ended_at=1120)
    s2 = db.start_session(second.id, "auto", 2000)
    db.finish_session(s2, duration_seconds=600, ended_at=2600)
    assert [item.game.id for item in library.list_games(sort="name")] == [first.id, second.id]
    assert library.list_games(sort="playtime")[0].game.id == second.id
    assert [item.game.id for item in library.list_games(query="Alpha")] == [first.id]
    assert len(library.list_games(query="不存在")) == 0
    assert library.list_games(sort="recent")[0].game.id == second.id


def test_database_file_is_sqlite_and_has_version(paths, tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"
    database = Database(path)
    assert path.is_file()
    assert database.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    database.close()
