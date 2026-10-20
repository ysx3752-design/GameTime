"""领域模型。时间戳统一使用 Unix 秒（UTC），界面层负责转换成本地时间。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Game:
    id: int
    name: str
    exe_path: str
    exe_name: str
    icon_file: str | None
    accent: str
    notes: str
    created_at: int
    updated_at: int

    @property
    def path_obj(self) -> Path:
        return Path(self.exe_path)

    @property
    def path_exists(self) -> bool:
        return bool(self.exe_path) and self.path_obj.is_file()

    @property
    def initial(self) -> str:
        text = self.name.strip()
        return text[0].upper() if text else "游"


@dataclass(slots=True)
class GameSummary:
    game: Game
    total_seconds: int = 0
    last_played_at: int | None = None
    session_count: int = 0

    @property
    def missing(self) -> bool:
        return not self.game.path_exists


@dataclass(slots=True)
class Session:
    id: int
    game_id: int
    started_at: int
    ended_at: int | None
    duration_seconds: int
    last_heartbeat: int
    source: str
    status: str

    @property
    def is_active(self) -> bool:
        return self.status == "active"


@dataclass(slots=True)
class ActiveRun:
    game_id: int
    session_id: int
    source: str
    started_at: int
    last_tick: int
    duration: int = 0
    last_persist: int = 0


@dataclass(slots=True)
class Overview:
    today_seconds: int = 0
    last7_seconds: int = 0
    total_seconds: int = 0
    game_count: int = 0
    sessions_today: int = 0
    daily: list[tuple[str, int]] = field(default_factory=list)


@dataclass(slots=True)
class TrackingEvent:
    kind: str  # "started" | "stopped"
    game_id: int
    game_name: str
    session_id: int
    source: str
