"""设置存储与开机自启。"""

from __future__ import annotations

import logging
import sys
import winreg
from pathlib import Path

from ..database import Database
from ..paths import is_frozen

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "GameTime"


class SettingsStore:
    DEFAULTS = {
        "close_to_tray": "1",
        "notify_game_started": "0",
        "launch_minimized": "0",
        "theme_mode": "dark",
        "last_seen_version": "",
    }

    def __init__(self, db: Database) -> None:
        self.db = db

    def get_bool(self, key: str, default: bool = False) -> bool:
        fallback = self.DEFAULTS.get(key, "1" if default else "0")
        raw = self.db.get_setting(key, fallback)
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    def set_bool(self, key: str, value: bool) -> None:
        self.db.set_setting(key, "1" if value else "0")

    def get(self, key: str, default: str = "") -> str:
        value = self.db.get_setting(key, self.DEFAULTS.get(key, default))
        return str(value) if value is not None else default

    def set(self, key: str, value: str) -> None:
        self.db.set_setting(key, str(value))


def _autostart_command() -> str:
    if is_frozen():
        return f'"{sys.executable}" --minimized'
    project_root = Path(__file__).resolve().parent.parent.parent
    launcher = project_root / "run_gametime.py"
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{interpreter}" "{launcher}" --minimized'


class AutostartManager:
    """通过 HKCU\\...\\Run 管理当前用户的开机自启，无需管理员权限。"""

    @staticmethod
    def is_enabled() -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, VALUE_NAME)
                return True
        except FileNotFoundError:
            return False
        except OSError:
            return False

    @staticmethod
    def set_enabled(enabled: bool) -> None:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _autostart_command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass

    @staticmethod
    def command() -> str:
        return _autostart_command()
