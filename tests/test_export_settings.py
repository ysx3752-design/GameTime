from __future__ import annotations

import csv
from pathlib import Path

from gametime.database import Database
from gametime.services.export import export_sessions_csv
from gametime.services.settings import AutostartManager, SettingsStore


def test_settings_store(db: Database) -> None:
    settings = SettingsStore(db)
    assert settings.get_bool("close_to_tray", True) is True
    settings.set_bool("close_to_tray", False)
    assert settings.get_bool("close_to_tray", True) is False
    settings.set_bool("notify_game_started", True)
    assert settings.get_bool("notify_game_started") is True
    settings.set("window_geometry", "abc")
    assert settings.get("window_geometry") == "abc"


def test_autostart_command_contains_minimized() -> None:
    command = AutostartManager.command()
    assert "--minimized" in command
    assert "python" in command.lower() or "gametime" in command.lower()


def test_export_csv(db: Database, library, exe_factory, tmp_path: Path) -> None:
    game = library.add_game("导出游戏", str(exe_factory("export.exe")))
    session_id = db.start_session(game.id, "auto", 1_790_000_000)
    db.finish_session(session_id, duration_seconds=125, ended_at=1_790_000_125)
    target = tmp_path / "export.csv"
    result = export_sessions_csv(db, target)
    assert result == target
    assert target.exists()
    raw = target.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM，便于 Excel 打开
    with target.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0][0] == "游戏"
    assert rows[1][0] == "导出游戏"
    assert rows[1][4] == "125"
    assert rows[1][6] == "自动"


def test_export_empty(db: Database, tmp_path: Path) -> None:
    target = tmp_path / "empty.csv"
    export_sessions_csv(db, target)
    lines = target.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 1
