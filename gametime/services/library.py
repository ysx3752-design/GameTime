"""游戏库服务：手动添加、重定位、移除以及列表视图所需数据。"""

from __future__ import annotations

import time
from pathlib import Path

from ..database import Database
from ..models import Game, GameSummary
from ..windows import file_display_name, normalize_windows_path, same_path
from .icons import IconService, accent_for


class LibraryError(Exception):
    """游戏库业务错误。"""


class GameValidationError(LibraryError):
    pass


class DuplicateGameError(LibraryError):
    pass


class GameNotFoundError(LibraryError):
    pass


class GameService:
    def __init__(self, db: Database, icons: IconService) -> None:
        self.db = db
        self.icons = icons

    # ------------------------------------------------------------------- CRUD
    def add_game(
        self,
        name: str,
        exe_path: str,
        notes: str = "",
        *,
        now: int | None = None,
    ) -> Game:
        clean_name = name.strip()
        clean_notes = notes.strip()[:500]
        path = self._validate_exe(exe_path)
        if not clean_name:
            clean_name = file_display_name(path)
        if not clean_name:
            raise GameValidationError("请填写游戏名称。")

        normalized = normalize_windows_path(path)
        if self.db.find_game_by_path(normalized):
            raise DuplicateGameError("这个游戏程序已经在游戏库中了。")

        accent = accent_for(clean_name, normalized)
        icon_file = self.icons.create_cached_icon(str(path), clean_name, accent)
        timestamp = int(now if now is not None else time.time())
        try:
            game_id = self.db.add_game(
                name=clean_name,
                exe_path=str(path),
                exe_name=path.name,
                icon_file=icon_file,
                accent=accent,
                notes=clean_notes,
                now=timestamp,
            )
        except Exception:
            self.icons.delete_cached_icon(icon_file)
            raise
        game = self.db.get_game(game_id)
        if game is None:  # pragma: no cover - 数据库异常
            raise LibraryError("保存游戏失败，请重试。")
        return game

    def update_game(
        self,
        game_id: int,
        name: str,
        exe_path: str,
        notes: str = "",
        *,
        now: int | None = None,
    ) -> Game:
        existing = self.get_game(game_id)
        clean_name = name.strip()
        if not clean_name:
            raise GameValidationError("请填写游戏名称。")
        path = self._validate_exe(exe_path)
        normalized = normalize_windows_path(path)
        duplicate = self.db.find_game_by_path(normalized)
        if duplicate and duplicate.id != game_id:
            raise DuplicateGameError("这个游戏程序已经在游戏库中了。")

        path_changed = not same_path(existing.exe_path, str(path))
        icon_file = existing.icon_file
        if path_changed or not icon_file:
            icon_file = self.icons.create_cached_icon(str(path), clean_name, existing.accent)
            if path_changed:
                self.icons.delete_cached_icon(existing.icon_file)
        elif not self.icons.icons_dir.joinpath(icon_file).is_file():
            icon_file = self.icons.create_cached_icon(str(path), clean_name, existing.accent)

        timestamp = int(now if now is not None else time.time())
        self.db.update_game(
            game_id,
            name=clean_name,
            exe_path=str(path),
            exe_name=path.name,
            icon_file=icon_file,
            notes=notes.strip()[:500],
            now=timestamp,
        )
        return self.get_game(game_id)

    def remove_game(self, game_id: int) -> None:
        game = self.get_game(game_id)
        self.db.delete_game(game_id)
        self.icons.delete_cached_icon(game.icon_file)

    def relocate_game(self, game_id: int, new_exe_path: str) -> Game:
        game = self.get_game(game_id)
        return self.update_game(game_id, game.name, new_exe_path, game.notes)

    def repair_icons(self) -> int:
        """一次性修复旧缓存图标：去掉透明留白，并从 exe 重新提取真实图标。

        仅处理已有记录，不会改变游戏、会话或卸载后的历史。
        """
        repaired = 0
        now = int(time.time())
        for summary in self.list_games():
            game = summary.game
            if game.icon_file:
                self.icons.normalize_cached_icon(game.icon_file)
            if not Path(game.exe_path).is_file():
                continue
            new_icon = self.icons.create_cached_icon(game.exe_path, game.name, game.accent)
            if not new_icon:
                continue
            self.db.update_game(
                game.id,
                name=game.name,
                exe_path=game.exe_path,
                exe_name=game.exe_name,
                icon_file=new_icon,
                notes=game.notes,
                now=now,
            )
            if game.icon_file != new_icon:
                self.icons.delete_cached_icon(game.icon_file)
            repaired += 1
        return repaired

    # ------------------------------------------------------------------ reads
    def get_game(self, game_id: int) -> Game:
        game = self.db.get_game(game_id)
        if game is None:
            raise GameNotFoundError("游戏不存在或已被移除。")
        return game

    def list_games(self, query: str = "", sort: str = "recent") -> list[GameSummary]:
        rows = self.db.list_games(query, sort)
        return [
            GameSummary(
                game=game,
                total_seconds=total,
                last_played_at=last_played,
                session_count=count,
            )
            for game, total, last_played, count in rows
        ]

    def summary(self, game_id: int) -> GameSummary:
        game = self.get_game(game_id)
        values = self.db.game_summary(game_id)
        if values is None:  # pragma: no cover
            return GameSummary(game=game)
        total, last_played, count = values
        return GameSummary(game=game, total_seconds=total, last_played_at=last_played, session_count=count)

    def icon_path(self, game: Game) -> Path | None:
        if not game.icon_file:
            return None
        path = self.icons.icons_dir / game.icon_file
        return path if path.is_file() else None

    # --------------------------------------------------------------- validation
    @staticmethod
    def _validate_exe(exe_path: str) -> Path:
        raw = (exe_path or "").strip().strip('"')
        if not raw:
            raise GameValidationError("请选择游戏的可执行文件。")
        path = Path(raw).expanduser()
        try:
            path = path.resolve()
        except OSError:
            pass
        if path.suffix.lower() != ".exe":
            raise GameValidationError("请选择 .exe 游戏启动程序。")
        if not path.is_file():
            raise GameValidationError("找不到这个游戏程序，请确认文件仍然存在。")
        return path
