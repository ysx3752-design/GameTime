"""启动游戏 / 打开目录。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QProcess, QUrl
from PySide6.QtGui import QDesktopServices

from ..models import Game


@dataclass(slots=True)
class LaunchResult:
    ok: bool
    pid: int = 0
    error: str = ""


class GameLauncher:
    def launch(self, game: Game) -> LaunchResult:
        path = Path(game.exe_path)
        if not path.is_file():
            return LaunchResult(False, error="游戏程序已被移动或卸载，请重新定位。")
        try:
            ok, pid = QProcess.startDetached(
                str(path), [], str(path.parent)
            )
        except Exception as exc:
            return LaunchResult(False, error=f"启动失败：{exc}")
        if not ok:
            return LaunchResult(False, error="游戏启动失败，可能被系统权限拦截。")
        return LaunchResult(True, pid=int(pid))

    @staticmethod
    def open_folder(game: Game) -> bool:
        path = Path(game.exe_path)
        directory = path.parent if path.parent.is_dir() else Path.home()
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    @staticmethod
    def open_path(path: str | os.PathLike[str]) -> bool:
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
