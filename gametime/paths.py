"""应用数据、资源与日志路径。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

DATA_DIR_ENV = "GAMETIME_DATA_DIR"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_path(*parts: str) -> Path:
    """返回随程序分发的只读资源路径（兼容 PyInstaller）。"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base.joinpath(*parts)


def default_data_dir() -> Path:
    """默认使用 %LOCALAPPDATA%\\GameTime，测试时可用环境变量覆盖。"""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "GameTime"
    return Path.home() / "AppData" / "Local" / "GameTime"


class AppPaths:
    """集中管理一个数据目录下的所有路径。"""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self.root = Path(data_dir).expanduser().resolve() if data_dir else default_data_dir()
        self.icons = self.root / "icons"
        self.logs = self.root / "logs"
        self.exports = self.root / "exports"
        self.database = self.root / "gametime.db"
        self.settings = self.root / "settings.json"

    def ensure(self) -> "AppPaths":
        for directory in (self.root, self.icons, self.logs, self.exports):
            directory.mkdir(parents=True, exist_ok=True)
        return self

    def icon_file(self, relative_name: str | None) -> Path | None:
        if not relative_name:
            return None
        candidate = (self.icons / relative_name).resolve()
        # 只允许读取 icons 目录内的图标，避免异常数据指向任意文件。
        try:
            candidate.relative_to(self.icons.resolve())
        except ValueError:
            return None
        return candidate
