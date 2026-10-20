from __future__ import annotations

import json
from pathlib import Path

from gametime.services.scanner import (
    _is_game_exe,
    scan_all_drives,
    scan_epic,
    scan_games,
    scan_steam,
)
from gametime.windows import normalize_windows_path


def _make_exe(path: Path, size: int = 1_200_000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"MZ" + b"\0" * max(0, size - 2))
    return path


def _make_steam_library(root: Path, name: str = "Test Game", folder: str = "TestGame") -> Path:
    steamapps = root / "steamapps"
    game_dir = steamapps / "common" / folder
    exe = _make_exe(game_dir / f"{folder}.exe")
    (steamapps / "appmanifest_123.acf").write_text(
        '"AppState"\n{\n'
        '\t"appid"\t\t"123"\n'
        f'\t"name"\t\t"{name}"\n'
        f'\t"installdir"\t\t"{folder}"\n'
        "}\n",
        encoding="utf-8",
    )
    return exe


def _make_epic_manifest(root: Path, name: str = "Epic Game") -> Path:
    game_dir = root / "EpicGame"
    exe = _make_exe(game_dir / "EpicGame.exe")
    manifest = root / "manifest.item"
    manifest.write_text(
        json.dumps(
            {
                "DisplayName": name,
                "InstallLocation": str(game_dir),
                "LaunchExecutable": "EpicGame.exe",
                "AppCategories": ["games", "public"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return exe


def test_scan_steam_manifest(tmp_path: Path) -> None:
    steam_root = tmp_path / "Steam"
    exe = _make_steam_library(steam_root, "Portal Test", "PortalTest")
    results = scan_steam(set(), steam_roots=[steam_root])
    assert len(results) == 1
    assert results[0].source == "Steam"
    assert Path(results[0].exe_path) == exe
    assert results[0].already_added is False
    assert results[0].size_bytes >= 1_000_000


def test_scan_steam_marks_existing(tmp_path: Path) -> None:
    steam_root = tmp_path / "Steam"
    exe = _make_steam_library(steam_root)
    results = scan_steam({normalize_windows_path(str(exe))}, steam_roots=[steam_root])
    assert results[0].already_added is True


def test_scan_epic_manifest(tmp_path: Path) -> None:
    exe = _make_epic_manifest(tmp_path, "Epic Test Game")
    results = scan_epic(set(), manifest_dirs=[tmp_path])
    assert len(results) == 1
    assert results[0].source == "Epic"
    assert results[0].display_name
    assert Path(results[0].exe_path) == exe


def test_scan_custom_folder_and_root_game(tmp_path: Path) -> None:
    parent = tmp_path / "MyGames"
    game_dir = parent / "Alpha"
    exe = _make_exe(game_dir / "Alpha.exe")
    results = scan_games(
        set(),
        include_steam=False,
        include_epic=False,
        include_common=False,
        custom_dirs=[parent],
    )
    assert len(results) == 1
    assert results[0].source == "自定义文件夹"
    assert Path(results[0].exe_path) == exe

    single_game_dir = tmp_path / "SingleGame"
    single_exe = _make_exe(single_game_dir / "SingleGame.exe")
    _make_exe(single_game_dir / "extras" / "nested.exe")
    results = scan_games(
        set(),
        include_steam=False,
        include_epic=False,
        include_common=False,
        custom_dirs=[single_game_dir],
    )
    assert any(Path(item.exe_path) == single_exe for item in results)


def test_scan_deduplicates_and_sorts(tmp_path: Path) -> None:
    steam_root = tmp_path / "Steam"
    steam_exe = _make_steam_library(steam_root, "Same Game", "SameGame")
    results = scan_games(
        set(),
        include_epic=False,
        include_common=False,
        steam_roots=[steam_root],
        custom_dirs=[steam_root / "steamapps" / "common"],
    )
    same = [item for item in results if Path(item.exe_path) == steam_exe]
    assert len(same) == 1
    assert same[0].source == "Steam"


def test_scan_skips_installers_and_tiny_exes(tmp_path: Path) -> None:
    game_dir = tmp_path / "Game"
    _make_exe(game_dir / "uninstall.exe")
    _make_exe(game_dir / "tiny.exe", 20_000)
    _make_exe(game_dir / "小花仙微端.exe", 5_000_000)
    assert _is_game_exe(game_dir / "uninstall.exe") is False
    assert _is_game_exe(game_dir / "tiny.exe") is False
    assert _is_game_exe(game_dir / "小花仙微端.exe") is False
    results = scan_games(
        set(),
        include_steam=False,
        include_epic=False,
        include_common=False,
        custom_dirs=[tmp_path],
    )
    assert results == []


def test_full_disk_scan_finds_custom_install_and_uses_registry_name(tmp_path: Path) -> None:
    install_root = tmp_path / "APP2" / "Yslzm"
    exe = _make_exe(
        install_root
        / "LifeMakeoverGame_ob_zh_944"
        / "Azure"
        / "Binaries"
        / "Win64"
        / "Azure-Win64-Shipping.exe"
    )
    hints = {normalize_windows_path(str(install_root)): "以闪亮之名"}
    results = scan_all_drives(set(), roots=[tmp_path], name_hints=hints)
    assert len(results) == 1
    assert Path(results[0].exe_path) == exe
    assert results[0].display_name == "以闪亮之名"
    assert results[0].source == "全盘扫描"


def test_full_disk_scan_filters_self_and_installers(tmp_path: Path) -> None:
    _make_exe(tmp_path / "tools" / "GameTime.exe")
    _make_exe(tmp_path / "setup-big.exe", 2_000_000)
    results = scan_all_drives(set(), roots=[tmp_path], name_hints={})
    assert all(item.display_name.lower() not in {"gametime", "setup big"} for item in results)
