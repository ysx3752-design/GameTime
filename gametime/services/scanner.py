"""按需扫描 Steam / Epic / 常见游戏目录，返回候选游戏供用户确认添加。

扫描不是“自动把硬盘上的 exe 全加进库”：
- 优先读取平台清单（Steam appmanifest、Epic manifest）；
- 只扫描常见 Games 目录与用户指定的文件夹；
- 每个游戏目录用启发式规则挑选最可能的主程序；
- 所有结果必须由用户在扫描对话框中勾选后才会入库。
"""

from __future__ import annotations

import json
import math
import os
import re
import string
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ..windows import file_display_name, normalize_windows_path

ProgressCallback = Callable[[str], None]
StopCallback = Callable[[], bool]

_SKIP_NAMES = {
    "uninstall.exe",
    "unins000.exe",
    "unins001.exe",
    "uninst.exe",
    "uninstaller.exe",
    "setup.exe",
    "install.exe",
    "installer.exe",
    "update.exe",
    "updater.exe",
    "crashhandler.exe",
    "crashreporter.exe",
    "unitycrashandler32.exe",
    "unitycrashandler64.exe",
    "unitycrashhandler32.exe",
    "unitycrashhandler64.exe",
    "ue4prereqsetup_x64.exe",
    "ue4prereqsetup.exe",
    "dxsetup.exe",
    "dxwebsetup.exe",
    "vcredist_x86.exe",
    "vcredist_x64.exe",
    "vc_redist.x86.exe",
    "vc_redist.x64.exe",
    "python.exe",
    "pythonw.exe",
    "python3.exe",
    "cmd.exe",
    "powershell.exe",
    "conhost.exe",
    "notepad.exe",
    "7z.exe",
    "7zfm.exe",
    "7zg.exe",
    "winrar.exe",
    "rar.exe",
}

_SKIP_SUBSTRINGS = (
    "uninstall",
    "redist",
    "prerequisite",
    "prereq",
    "crashhandler",
    "crashreporter",
    "dxsetup",
    "vcredist",
    "dotnet",
    "repair",
    "helper",
    "launcher_helper",
    "bugreport",
    "reporter",
    "cleanup",
    "installer",
    "setup",
    "微端",
)

_SKIP_PATTERNS = (
    re.compile(r"^vc_redist", re.IGNORECASE),
    re.compile(r"^vcredist", re.IGNORECASE),
    re.compile(r"unins\d{3}", re.IGNORECASE),
    re.compile(r"^UE\dPrereq", re.IGNORECASE),
)

_SKIP_DIRS = {
    "$recycle.bin",
    "system volume information",
    "__pycache__",
    "node_modules",
    ".git",
    "_commonredist",
    "redist",
    "redistributables",
    "directx",
    "dotnet",
    "docs",
    "documentation",
    "support",
    "tools",
}

# 全盘扫描时跳过的系统/缓存目录，避免遍历系统组件和开发缓存。
_FULL_SCAN_SKIP_DIRS = _SKIP_DIRS | {
    ".cache",
    ".venv",
    "cache",
    "cachedata",
    "config.msi",
    "driverstore",
    "installer",
    "msocache",
    "package cache",
    "packages",
    "perflogs",
    "recovery",
    "servicing",
    "site-packages",
    "softwaredistribution",
    "temp",
    "venv",
    "windows",
    "windows.old",
    "windowsapps",
    "winsxs",
    "workshop",
    "$windows.~bt",
    "$windows.~ws",
}

_INSTALLER_PATTERNS = (
    re.compile(r"(^|[-_. ])(setup|installer|install|update|updater|patch)([-_. ]|$)", re.IGNORECASE),
    re.compile(r"(download|webinstall|redist|unins)", re.IGNORECASE),
    re.compile(r"(x64|x86|win64|win32)?[-_.]?v?\d+(\.\d+){2,}", re.IGNORECASE),
)

_FULL_SCAN_ROOT_SKIP = {
    "$recycle.bin",
    "system volume information",
    "windows",
    "programdata",
    "recovery",
    "perflogs",
    "msocache",
    "config.msi",
}

_FULL_SCAN_NOISE_NAMES = {
    "eosbootstrapper.exe",
    "eosbootstrap.exe",
    "epicgameslauncher.exe",
    "epiconlineserviceshost.exe",
    "fcgamemanager.exe",
    "gamemanager.exe",
    "gameservice_x86.exe",
    "gametime.exe",
    "gameviewer.exe",
    "gameviewerlauncher.exe",
    "gameviewerserver.exe",
    "gameviewerservice.exe",
    "sogouplaylauncher.exe",
    "tinydl.exe",
    "wegamelauncher.exe",
    "wegameminiloader.exe",
    "wxgamedaemon.exe",
}

_FULL_SCAN_NOISE_PATH_TOKENS = (
    "\\epic games\\epic online services\\",
    "\\epic games\\launcher\\",
    "\\tencent\\androws\\",
    "\\wegame\\wegameminiloader",
    "\\xwechat\\xplugin\\plugins\\radiumwmpf",
    "\\gameviewer\\",
    "\\uu远控\\",
)

_STEAM_SKIP_NAMES = ("steamworks", "proton", "steam linux runtime", "steamvr")


@dataclass(slots=True)
class ScanResult:
    exe_path: str
    display_name: str
    folder_name: str
    source: str = "文件夹"
    already_added: bool = False
    size_bytes: int = 0


def _tokens(text: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9\u4e00-\u9fff]+", text.lower()) if len(token) > 1}


def _name_similarity(game_name: str, exe_stem: str) -> float:
    game_tokens = _tokens(game_name)
    exe_tokens = _tokens(exe_stem)
    if not game_tokens or not exe_tokens:
        return 0.0
    overlap = len(game_tokens & exe_tokens)
    if overlap:
        return min(1.0, overlap / max(1, len(game_tokens)) + 0.15)
    joined_game = "".join(game_tokens)
    joined_exe = "".join(exe_tokens)
    if joined_game and (joined_game in joined_exe or joined_exe in joined_game):
        return 0.7
    return 0.0


def _is_game_exe(path: Path) -> bool:
    """启发式过滤安装器、运行库和工具，保留可能是主程序的 exe。"""
    name_lower = path.name.lower()
    if name_lower in _SKIP_NAMES:
        return False
    stem_lower = path.stem.lower()
    if any(sub in stem_lower for sub in _SKIP_SUBSTRINGS):
        return False
    if any(pattern.search(path.name) for pattern in _SKIP_PATTERNS):
        return False
    try:
        if path.stat().st_size < 1_000_000:
            return False
    except OSError:
        return False
    return True


def _walk_exes(directory: Path, max_depth: int = 3, limit: int = 4000) -> list[tuple[Path, int]]:
    base_depth = len(directory.parts)
    found: list[tuple[Path, int]] = []
    for root, dirnames, filenames in os.walk(directory):
        current = Path(root)
        depth = len(current.parts) - base_depth
        dirnames[:] = [
            name
            for name in dirnames
            if depth < max_depth
            and not name.startswith(".")
            and name.lower() not in _SKIP_DIRS
        ]
        for filename in filenames:
            if len(found) >= limit:
                return found
            if not filename.lower().endswith(".exe"):
                continue
            path = current / filename
            if _is_game_exe(path):
                found.append((path, depth))
    return found


def _choose_exe(game_dir: Path, display_name: str) -> tuple[Path, int] | None:
    """从一个游戏目录中挑选最可能的启动程序。"""
    candidates = _walk_exes(game_dir)
    if not candidates:
        return None
    best: tuple[float, Path, int] | None = None
    for path, depth in candidates:
        try:
            size = path.stat().st_size
        except OSError:
            continue
        score = min(30.0, math.log2(max(1, size / 1_000_000)) * 4.0)
        score += max(0, 10 - depth * 3)
        score += _name_similarity(display_name, path.stem) * 55
        parent = path.parent.name.lower()
        if parent in {"bin", "binaries", "win64", "win32", "x64", "x86", "retail"}:
            score += 5
        stem_lower = path.stem.lower()
        if "launcher" in stem_lower:
            score -= 8
        if "config" in stem_lower or "settings" in stem_lower:
            score -= 20
        if best is None or score > best[0]:
            best = (score, path, size)
    if best is None:
        return None
    return best[1], best[2]


def _platform_game_name(exe_path: Path, fallback: str) -> str:
    """平台/目录名称通常比 exe 的 FileDescription 更可靠，优先使用。"""
    if fallback.strip():
        return fallback.strip()[:80]
    try:
        detected = file_display_name(exe_path)
    except Exception:
        return exe_path.stem[:80]
    return (detected or exe_path.stem)[:80]


def _common_game_roots() -> list[Path]:
    roots: list[Path] = []
    home = Path.home()
    local = os.environ.get("LOCALAPPDATA")
    roots.extend((home / "Games", home / "games"))
    if local:
        roots.append(Path(local) / "Games")
    for letter in string.ascii_uppercase:
        drive = Path(f"{letter}:\\")
        if not drive.is_dir():
            continue
        for relative in (
            "Games",
            "games",
            "SteamLibrary/steamapps/common",
            "Epic Games",
            "GOG Games",
            "Ubisoft/Ubisoft Game Launcher/games",
            "Origin Games",
            "EA Games",
            "XboxGames",
            "Program Files/Games",
            "Program Files (x86)/Games",
        ):
            candidate = drive / Path(relative)
            if candidate.is_dir():
                roots.append(candidate)
    return _unique_dirs(roots)


def _unique_dirs(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue
        if not resolved.is_dir():
            continue
        key = normalize_windows_path(str(resolved))
        if key not in seen:
            seen.add(key)
            result.append(resolved)
    return result


def _fixed_drives() -> list[Path]:
    """返回所有本地固定磁盘根目录（排除 U 盘、光驱、网络盘）。"""
    import ctypes

    drives: list[Path] = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if not os.path.isdir(root):
            continue
        try:
            if ctypes.windll.kernel32.GetDriveTypeW(root) != 3:  # DRIVE_FIXED
                continue
        except Exception:
            pass
        drives.append(Path(root))
    return drives


def _clean_game_folder(name: str) -> str:
    cleaned = re.sub(
        r"[_-](?:ob|zh|en|cn|win(?:32|64)|shipping|release|retail)(?:[_-].*)?$",
        "",
        name,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"[_-]v?\d+(?:\.\d+){1,}.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("_", " ").replace("-", " ").strip()
    return cleaned[:80] or name[:80]


def _is_full_scan_noise(exe_path: Path) -> bool:
    if exe_path.name.lower() in _FULL_SCAN_NOISE_NAMES:
        return True
    lowered = str(exe_path).lower()
    if any(token in lowered for token in _FULL_SCAN_NOISE_PATH_TOKENS):
        return True
    try:
        if os.path.exists(sys.executable) and os.path.samefile(exe_path, sys.executable):
            return True
    except OSError:
        pass
    return False


def _registry_display_hints() -> dict[str, str]:
    """从卸载项中提取“安装目录 -> 显示名”提示，只用于改进全盘扫描的命名。"""
    hints: dict[str, str] = {}
    try:
        import winreg
    except Exception:
        return hints
    keys = (
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ),
    )
    for hive, key_name in keys:
        try:
            root = winreg.OpenKey(hive, key_name)
        except OSError:
            continue
        with root:
            index = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(root, index)
                except OSError:
                    break
                index += 1
                try:
                    with winreg.OpenKey(root, subkey_name) as subkey:
                        display_name = str(winreg.QueryValueEx(subkey, "DisplayName")[0]).strip()
                        try:
                            icon_value = str(winreg.QueryValueEx(subkey, "DisplayIcon")[0]).strip()
                        except OSError:
                            icon_value = ""
                except OSError:
                    continue
                if not display_name or not icon_value:
                    continue
                icon_path = icon_value.strip('"').split(",")[0].strip()
                if not icon_path.lower().endswith(".exe"):
                    continue
                icon = Path(icon_path)
                if not icon.is_file():
                    continue
                hints[normalize_windows_path(str(icon))] = display_name
                icon_parent = icon.parent
                hints[normalize_windows_path(str(icon_parent))] = display_name
                install_root = icon_parent.parent
                try:
                    child_count = sum(1 for entry in install_root.iterdir() if entry.is_dir())
                except OSError:
                    child_count = 999
                if child_count <= 8 and install_root.name.lower() not in {
                    "program files",
                    "program files (x86)",
                    "appdata",
                    "local",
                    "roaming",
                    "programs",
                    "apps",
                    "users",
                    "steam",
                    "steamapps",
                    "epic games",
                    "gog games",
                    "origin games",
                }:
                    hints[normalize_windows_path(str(install_root))] = display_name
    return hints


def _hinted_name(exe_path: Path, hints: dict[str, str] | None) -> str | None:
    if not hints:
        return None
    exact = hints.get(normalize_windows_path(str(exe_path)))
    if exact:
        return exact
    current = exe_path.parent
    for _ in range(5):
        matched = hints.get(normalize_windows_path(str(current)))
        if matched:
            return matched
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _meaningful_game_name(exe_path: Path) -> str:
    """从 exe 所在目录向上寻找最有意义的游戏目录名。"""
    generic = {
        "app",
        "application",
        "bin",
        "binaries",
        "client",
        "data",
        "engine",
        "game",
        "games",
        "paks",
        "retail",
        "win32",
        "win64",
        "x64",
        "x86",
    }
    ancestors = [exe_path.parent]
    parent = exe_path.parent
    for _ in range(5):
        parent = parent.parent
        if parent == parent.parent:
            break
        ancestors.append(parent)
    for ancestor in ancestors:
        lowered = ancestor.name.lower()
        if lowered not in generic and any(
            token in lowered for token in ("game", "launcher", "client", "online")
        ):
            return _clean_game_folder(ancestor.name)
    for ancestor in ancestors:
        if ancestor.name.lower() not in generic and len(ancestor.name) > 2:
            return _clean_game_folder(ancestor.name)
    return _clean_game_folder(exe_path.stem)


def _full_scan_score(exe_path: Path, size_bytes: int) -> float:
    lowered = str(exe_path).lower()
    name = exe_path.name.lower()
    stem = exe_path.stem.lower()
    score = min(30.0, math.log2(max(1, size_bytes / 1_000_000)) * 4.0)
    if "game" in lowered:
        score += 35
    if any(token in lowered for token in ("steamapps", "epic games", "gog games", "origin games")):
        score += 20
    if "binaries" in lowered:
        score += 12
    if "win64" in lowered or "win32" in lowered:
        score += 6
    if "shipping" in stem:
        score += 12
    if "launcher" in stem:
        score += 8
    if "engine" in lowered:
        score -= 25
    if "download" in lowered:
        score -= 40
    if any(pattern.search(name) for pattern in _INSTALLER_PATTERNS):
        score -= 70
    if any(token in stem for token in ("cef", "crash", "tqm", "helper", "config", "setup")):
        score -= 50
    return score


def scan_all_drives(
    existing: set[str],
    *,
    roots: Iterable[Path] | None = None,
    name_hints: dict[str, str] | None = None,
    on_progress: ProgressCallback | None = None,
    should_stop: StopCallback | None = None,
) -> list[ScanResult]:
    """全盘扫描所有本地磁盘，按目录挑选游戏候选。

    会跳过 Windows、WinSxS、WindowsApps、包缓存、开发缓存等系统目录，
    只保留得分较高的游戏候选；结果仍需用户确认。
    """
    drive_roots = _unique_dirs(list(roots)) if roots is not None else _fixed_drives()
    hints = _registry_display_hints() if name_hints is None else name_hints
    best_by_dir: dict[str, tuple[float, Path, int]] = {}
    scanned_dirs = 0
    for drive in drive_roots:
        if should_stop and should_stop():
            break
        if on_progress:
            on_progress(str(drive))
        for current, dirnames, filenames in os.walk(drive, topdown=True, onerror=lambda _: None):
            if should_stop and should_stop():
                break
            scanned_dirs += 1
            if on_progress and scanned_dirs % 120 == 0:
                on_progress(current)
            current_path = Path(current)
            depth = len(current_path.parts) - len(drive.parts)
            kept_dirs = []
            for name in dirnames:
                lower = name.lower()
                if lower in _FULL_SCAN_SKIP_DIRS or lower.startswith("."):
                    continue
                if depth == 0 and lower in _FULL_SCAN_ROOT_SKIP:
                    continue
                # 过深的缓存/嵌套目录通常不是游戏安装目录。
                if depth >= 13:
                    continue
                kept_dirs.append(name)
            dirnames[:] = kept_dirs
            if not filenames:
                continue
            best_in_dir: tuple[float, Path, int] | None = None
            for filename in filenames:
                if should_stop and should_stop():
                    break
                if not filename.lower().endswith(".exe"):
                    continue
                exe_path = current_path / filename
                if _is_full_scan_noise(exe_path):
                    continue
                if not _is_game_exe(exe_path):
                    continue
                try:
                    size_bytes = exe_path.stat().st_size
                except OSError:
                    continue
                score = _full_scan_score(exe_path, size_bytes)
                threshold = 35 if "game" in str(exe_path).lower() else 50
                if score < threshold:
                    continue
                if best_in_dir is None or score > best_in_dir[0]:
                    best_in_dir = (score, exe_path, size_bytes)
            if best_in_dir is not None:
                key = normalize_windows_path(str(best_in_dir[1].parent))
                previous = best_by_dir.get(key)
                if previous is None or best_in_dir[0] > previous[0]:
                    best_by_dir[key] = best_in_dir

    results: list[ScanResult] = []
    seen: set[str] = set()
    ranked = sorted(best_by_dir.values(), key=lambda item: item[0], reverse=True)
    for score, exe_path, size_bytes in ranked:
        key = normalize_windows_path(str(exe_path))
        if key in seen:
            continue
        seen.add(key)
        display_name = _hinted_name(exe_path, hints) or _meaningful_game_name(exe_path)
        results.append(
            ScanResult(
                exe_path=str(exe_path),
                display_name=display_name[:80],
                folder_name=display_name[:80],
                source="全盘扫描",
                already_added=key in existing,
                size_bytes=size_bytes,
            )
        )
        if len(results) >= 200:
            break
    return results


def _scan_game_folders(
    roots: Iterable[Path],
    *,
    source: str,
    existing: set[str],
    on_progress: ProgressCallback | None,
    should_stop: StopCallback | None,
    results: list[ScanResult],
    seen: set[str],
) -> None:
    for root in _unique_dirs(roots):
        if should_stop and should_stop():
            return
        if on_progress:
            on_progress(str(root))
        try:
            children = [entry for entry in root.iterdir() if entry.is_dir()]
        except OSError:
            continue
        try:
            has_root_exe = any(
                entry.is_file()
                and entry.suffix.lower() == ".exe"
                and _is_game_exe(entry)
                for entry in root.iterdir()
            )
        except OSError:
            has_root_exe = False
        if has_root_exe:
            # 用户选择的目录本身就是一个游戏目录时，不再把子目录当作独立游戏。
            children = [root]
        elif not children:
            children = [root]
        for game_dir in children:
            if should_stop and should_stop():
                return
            if game_dir.name.lower() in _SKIP_DIRS or game_dir.name.startswith("."):
                continue
            chosen = _choose_exe(game_dir, game_dir.name)
            if chosen is None:
                continue
            exe_path, size_bytes = chosen
            key = normalize_windows_path(str(exe_path))
            if key in seen:
                continue
            seen.add(key)
            display = _platform_game_name(exe_path, game_dir.name)
            results.append(
                ScanResult(
                    exe_path=str(exe_path),
                    display_name=display,
                    folder_name=game_dir.name,
                    source=source,
                    already_added=key in existing,
                    size_bytes=size_bytes,
                )
            )
            if len(results) >= 200:
                return


def _vdf_value(text: str, key: str) -> str:
    match = re.search(rf'"{re.escape(key)}"\s+"([^"]*)"', text, re.IGNORECASE)
    return match.group(1).replace("\\\\", "\\") if match else ""


def _steam_libraries(steam_root: Path) -> list[Path]:
    libraries: list[Path] = [steam_root]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    try:
        text = vdf.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        text = ""
    for match in re.finditer(r'"path"\s+"([^"]+)"', text, re.IGNORECASE):
        path = Path(match.group(1).replace("\\\\", "\\"))
        if path.is_dir():
            libraries.append(path)
    return _unique_dirs(libraries)


def _discover_steam_roots() -> list[Path]:
    roots: list[Path] = []
    try:
        import winreg

        for hive, key_name, value_name in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        ):
            try:
                with winreg.OpenKey(hive, key_name) as key:
                    value, _ = winreg.QueryValueEx(key, value_name)
                    roots.append(Path(value))
            except OSError:
                continue
    except Exception:
        pass
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base:
            roots.append(Path(base) / "Steam")
    return _unique_dirs(roots)


def scan_steam(
    existing: set[str],
    *,
    steam_roots: Iterable[Path] | None = None,
    on_progress: ProgressCallback | None = None,
    should_stop: StopCallback | None = None,
) -> list[ScanResult]:
    roots = list(steam_roots) if steam_roots is not None else _discover_steam_roots()
    results: list[ScanResult] = []
    seen: set[str] = set()
    for root in _unique_dirs(roots):
        for library in _steam_libraries(root):
            steamapps = library / "steamapps"
            if not steamapps.is_dir():
                continue
            for manifest in steamapps.glob("appmanifest_*.acf"):
                if should_stop and should_stop():
                    return results
                if on_progress:
                    on_progress(str(manifest.parent))
                try:
                    text = manifest.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                name = _vdf_value(text, "name")
                install_dir = _vdf_value(text, "installdir")
                if not name or not install_dir:
                    continue
                if any(token in name.lower() for token in _STEAM_SKIP_NAMES):
                    continue
                game_dir = steamapps / "common" / install_dir
                if not game_dir.is_dir():
                    continue
                chosen = _choose_exe(game_dir, name)
                if chosen is None:
                    continue
                exe_path, size_bytes = chosen
                key = normalize_windows_path(str(exe_path))
                if key in seen:
                    continue
                seen.add(key)
                results.append(
                    ScanResult(
                        exe_path=str(exe_path),
                        display_name=_platform_game_name(exe_path, name),
                        folder_name=name,
                        source="Steam",
                        already_added=key in existing,
                        size_bytes=size_bytes,
                    )
                )
                if len(results) >= 200:
                    return results
    return results


def _epic_manifest_dirs() -> list[Path]:
    program_data = os.environ.get("ProgramData", r"C:\ProgramData")
    return [Path(program_data) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"]


def scan_epic(
    existing: set[str],
    *,
    manifest_dirs: Iterable[Path] | None = None,
    on_progress: ProgressCallback | None = None,
    should_stop: StopCallback | None = None,
) -> list[ScanResult]:
    dirs = list(manifest_dirs) if manifest_dirs is not None else _epic_manifest_dirs()
    results: list[ScanResult] = []
    seen: set[str] = set()
    for manifest_dir in _unique_dirs(dirs):
        if on_progress:
            on_progress(str(manifest_dir))
        for manifest in manifest_dir.glob("*.item"):
            if should_stop and should_stop():
                return results
            try:
                data = json.loads(manifest.read_text(encoding="utf-8", errors="ignore"))
            except (OSError, json.JSONDecodeError):
                continue
            categories = data.get("AppCategories") or []
            if categories and not any("game" in str(category).lower() for category in categories):
                continue
            name = str(data.get("DisplayName") or "").strip()
            install = str(data.get("InstallLocation") or "").strip()
            if not name or not install:
                continue
            game_dir = Path(install)
            if not game_dir.is_dir():
                continue
            launch = str(data.get("LaunchExecutable") or "").strip()
            chosen_path: Path | None = None
            size_bytes = 0
            if launch:
                candidate = (game_dir / launch).resolve()
                if candidate.is_file():
                    chosen_path = candidate
                    try:
                        size_bytes = candidate.stat().st_size
                    except OSError:
                        size_bytes = 0
            if chosen_path is None:
                chosen = _choose_exe(game_dir, name)
                if chosen is None:
                    continue
                chosen_path, size_bytes = chosen
            key = normalize_windows_path(str(chosen_path))
            if key in seen:
                continue
            seen.add(key)
            results.append(
                ScanResult(
                    exe_path=str(chosen_path),
                    display_name=_platform_game_name(chosen_path, name),
                    folder_name=name,
                    source="Epic",
                    already_added=key in existing,
                    size_bytes=size_bytes,
                )
            )
    return results


def scan_games(
    existing_paths: Iterable[str] = (),
    *,
    include_steam: bool = True,
    include_epic: bool = True,
    include_common: bool = True,
    full_scan: bool = False,
    custom_dirs: Iterable[str | Path] = (),
    steam_roots: Iterable[Path] | None = None,
    epic_manifest_dirs: Iterable[Path] | None = None,
    common_roots: Iterable[Path] | None = None,
    full_scan_roots: Iterable[Path] | None = None,
    full_scan_name_hints: dict[str, str] | None = None,
    on_progress: ProgressCallback | None = None,
    should_stop: StopCallback | None = None,
) -> list[ScanResult]:
    existing = {normalize_windows_path(path) for path in existing_paths if path}
    results: list[ScanResult] = []
    seen: set[str] = set()
    if include_steam:
        for result in scan_steam(
            existing,
            steam_roots=steam_roots,
            on_progress=on_progress,
            should_stop=should_stop,
        ):
            key = normalize_windows_path(result.exe_path)
            if key not in seen:
                seen.add(key)
                results.append(result)
    if include_epic:
        for result in scan_epic(
            existing,
            manifest_dirs=epic_manifest_dirs,
            on_progress=on_progress,
            should_stop=should_stop,
        ):
            key = normalize_windows_path(result.exe_path)
            if key not in seen:
                seen.add(key)
                results.append(result)
    if include_common:
        roots = list(common_roots) if common_roots is not None else _common_game_roots()
        _scan_game_folders(
            roots,
            source="Games 文件夹",
            existing=existing,
            on_progress=on_progress,
            should_stop=should_stop,
            results=results,
            seen=seen,
        )
    if full_scan:
        for result in scan_all_drives(
            existing,
            roots=full_scan_roots,
            name_hints=full_scan_name_hints,
            on_progress=on_progress,
            should_stop=should_stop,
        ):
            key = normalize_windows_path(result.exe_path)
            if key not in seen:
                seen.add(key)
                results.append(result)
    if custom_dirs:
        _scan_game_folders(
            [Path(path) for path in custom_dirs],
            source="自定义文件夹",
            existing=existing,
            on_progress=on_progress,
            should_stop=should_stop,
            results=results,
            seen=seen,
        )
    results.sort(key=lambda item: (item.already_added, item.display_name.lower()))
    return results


class ScanThread(QThread):
    """后台扫描线程；通过 Qt 信号把进度和结果送回 UI 线程。"""

    progress = Signal(str)
    results_ready = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        existing_paths: set[str],
        *,
        custom_dirs: list[str] | None = None,
        full_scan: bool = False,
        steam_roots: list[Path] | None = None,
        epic_manifest_dirs: list[Path] | None = None,
        common_roots: list[Path] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._existing = set(existing_paths)
        self._custom_dirs = list(custom_dirs or [])
        self._full_scan = full_scan
        self._steam_roots = steam_roots
        self._epic_manifest_dirs = epic_manifest_dirs
        self._common_roots = common_roots

    def run(self) -> None:  # noqa: D401
        try:
            results = scan_games(
                self._existing,
                custom_dirs=self._custom_dirs,
                full_scan=self._full_scan,
                steam_roots=self._steam_roots,
                epic_manifest_dirs=self._epic_manifest_dirs,
                common_roots=self._common_roots,
                on_progress=self.progress.emit,
                should_stop=self.isInterruptionRequested,
            )
            if not self.isInterruptionRequested():
                self.results_ready.emit(results)
        except Exception as exc:  # pragma: no cover - 防御性
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def stop(self) -> None:
        self.requestInterruption()
        self.wait(1500)
