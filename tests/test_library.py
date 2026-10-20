from __future__ import annotations

from pathlib import Path

from gametime.database import Database
from gametime.services.library import GameService, GameService as _GameService  # noqa: F401
from gametime.windows import file_display_name, normalize_windows_path, same_path


def test_icon_is_cached_and_uninstall_keeps_metadata(library: GameService, exe_factory) -> None:
    exe = exe_factory("UninstalledGame.exe")
    game = library.add_game("将被卸载的游戏", str(exe))
    icon_path = library.icon_path(game)
    assert icon_path is not None and icon_path.is_file()
    exe.unlink()
    summary = library.summary(game.id)
    assert summary.missing is True
    assert summary.game.name == "将被卸载的游戏"
    assert summary.game.icon_file
    assert library.icon_path(summary.game) is not None
    assert "未知" not in summary.game.name
    # 历史记录不因文件消失而丢失
    assert summary.total_seconds == 0


def test_relocate_game(db: Database, library: GameService, exe_factory, tmp_path: Path) -> None:
    old = exe_factory("old.exe")
    game = library.add_game("搬家的游戏", str(old))
    session_id = db.start_session(game.id, "manual", 1000)
    db.finish_session(session_id, duration_seconds=300, ended_at=1300)
    new = exe_factory("new.exe")
    moved = library.relocate_game(game.id, str(new))
    assert moved.exe_name == "new.exe"
    assert moved.name == "搬家的游戏"
    assert library.summary(game.id).total_seconds == 300
    # 图标在重定位后仍可用
    assert library.icon_path(moved) is not None


def test_path_normalization() -> None:
    left = r"C:\Games\Demo\Game.EXE"
    right = r"c:/games/demo/game.exe"
    assert same_path(left, right)
    assert normalize_windows_path(left) == normalize_windows_path(right)


def test_display_name_fallback(exe_factory) -> None:
    path = exe_factory("my_cool_game.exe")
    name = file_display_name(path)
    assert name
    assert "my cool game" in name.lower() or "my_cool_game" in name.lower()


def test_update_missing_icon_cache(library: GameService, exe_factory) -> None:
    exe = exe_factory("iconless.exe")
    game = library.add_game("Iconless", str(exe))
    icon = library.icon_path(game)
    assert icon and icon.exists()
    icon.unlink()
    refreshed = library.update_game(game.id, game.name, game.exe_path)
    assert library.icon_path(refreshed) is not None
