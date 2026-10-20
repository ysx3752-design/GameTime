"""SQLite 持久层。

设计原则：
- 时间全部存 Unix 秒，避免时区歧义；
- 每局游戏一条 session，崩溃后最多丢失一个心跳周期（默认 10 秒）；
- games 与 sessions 级联删除，只有用户主动移除游戏时才删除历史；
- 主键、外键、唯一索引在数据库层兜底。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import Game, Session

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    exe_path    TEXT NOT NULL,
    exe_name    TEXT NOT NULL,
    icon_file   TEXT,
    accent      TEXT NOT NULL DEFAULT '#7C5CFF',
    notes       TEXT NOT NULL DEFAULT '',
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_games_exe_path
    ON games(exe_path COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id          INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    started_at       INTEGER NOT NULL,
    ended_at         INTEGER,
    duration_seconds INTEGER NOT NULL DEFAULT 0 CHECK(duration_seconds >= 0),
    last_heartbeat   INTEGER NOT NULL,
    source           TEXT NOT NULL CHECK(source IN ('auto', 'manual')),
    status           TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'completed'))
);
CREATE INDEX IF NOT EXISTS idx_sessions_game_started
    ON sessions(game_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_status
    ON sessions(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_one_active
    ON sessions(game_id) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), timeout=15, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self._migrate()

    def _migrate(self) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            with self.conn:
                self.conn.executescript(_SCHEMA)
                self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        elif version > SCHEMA_VERSION:
            raise RuntimeError(
                f"数据文件版本 {version} 高于程序支持的版本 {SCHEMA_VERSION}，请升级游时。"
            )
        # 预留给未来迁移：if version < 2: ...

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.conn:
            yield self.conn

    def close(self) -> None:
        try:
            self.conn.close()
        except sqlite3.Error:
            pass

    # ------------------------------------------------------------------ games
    def add_game(
        self,
        *,
        name: str,
        exe_path: str,
        exe_name: str,
        icon_file: str | None,
        accent: str,
        notes: str,
        now: int,
    ) -> int:
        with self.conn:
            cursor = self.conn.execute(
                """
                INSERT INTO games(name, exe_path, exe_name, icon_file, accent, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, exe_path, exe_name, icon_file, accent, notes, now, now),
            )
            return int(cursor.lastrowid)

    def update_game(
        self,
        game_id: int,
        *,
        name: str,
        exe_path: str,
        exe_name: str,
        icon_file: str | None,
        notes: str,
        now: int,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                UPDATE games
                   SET name = ?, exe_path = ?, exe_name = ?, icon_file = ?, notes = ?, updated_at = ?
                 WHERE id = ?
                """,
                (name, exe_path, exe_name, icon_file, notes, now, game_id),
            )

    def delete_game(self, game_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM games WHERE id = ?", (game_id,))

    def get_game(self, game_id: int) -> Game | None:
        row = self.conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        return self._row_to_game(row) if row else None

    def find_game_by_path(self, exe_path: str) -> Game | None:
        row = self.conn.execute(
            "SELECT * FROM games WHERE exe_path = ? COLLATE NOCASE", (exe_path,)
        ).fetchone()
        return self._row_to_game(row) if row else None

    def list_games(self, query: str = "", sort: str = "recent") -> list[tuple[Game, int, int | None, int]]:
        where = ""
        args: list[object] = []
        if query.strip():
            where = "WHERE g.name LIKE ? COLLATE NOCASE OR g.exe_name LIKE ? COLLATE NOCASE"
            pattern = f"%{query.strip()}%"
            args.extend((pattern, pattern))
        order = {
            "recent": "last_played_at IS NULL ASC, last_played_at DESC, g.name COLLATE NOCASE ASC",
            "playtime": "total_seconds DESC, g.name COLLATE NOCASE ASC",
            "name": "g.name COLLATE NOCASE ASC",
        }.get(sort, "last_played_at IS NULL ASC, last_played_at DESC")
        rows = self.conn.execute(
            f"""
            SELECT g.*,
                   COALESCE(SUM(s.duration_seconds), 0) AS total_seconds,
                   MAX(s.started_at) AS last_played_at,
                   COUNT(s.id) AS session_count
              FROM games g
              LEFT JOIN sessions s ON s.game_id = g.id
              {where}
             GROUP BY g.id
             ORDER BY {order}
            """,
            args,
        ).fetchall()
        result: list[tuple[Game, int, int | None, int]] = []
        for row in rows:
            result.append(
                (
                    self._row_to_game(row),
                    int(row["total_seconds"] or 0),
                    int(row["last_played_at"]) if row["last_played_at"] is not None else None,
                    int(row["session_count"] or 0),
                )
            )
        return result

    def game_summary(self, game_id: int) -> tuple[int, int | None, int] | None:
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(duration_seconds), 0) AS total_seconds,
                   MAX(started_at) AS last_played_at,
                   COUNT(id) AS session_count
              FROM sessions WHERE game_id = ?
            """,
            (game_id,),
        ).fetchone()
        if row is None:
            return None
        return (
            int(row["total_seconds"] or 0),
            int(row["last_played_at"]) if row["last_played_at"] is not None else None,
            int(row["session_count"] or 0),
        )

    def count_games(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM games").fetchone()[0])

    # --------------------------------------------------------------- sessions
    def start_session(self, game_id: int, source: str, now: int) -> int:
        if source not in {"auto", "manual"}:
            raise ValueError(f"未知计时来源: {source}")
        with self.conn:
            cursor = self.conn.execute(
                """
                INSERT INTO sessions(game_id, started_at, ended_at, duration_seconds,
                                     last_heartbeat, source, status)
                VALUES (?, ?, NULL, 0, ?, ?, 'active')
                """,
                (game_id, now, now, source),
            )
            return int(cursor.lastrowid)

    def update_session(
        self, session_id: int, *, duration_seconds: int, heartbeat: int
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                UPDATE sessions
                   SET duration_seconds = ?, last_heartbeat = ?
                 WHERE id = ? AND status = 'active'
                """,
                (max(0, int(duration_seconds)), int(heartbeat), session_id),
            )

    def finish_session(
        self, session_id: int, *, duration_seconds: int, ended_at: int
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                UPDATE sessions
                   SET duration_seconds = ?, ended_at = ?, last_heartbeat = ?, status = 'completed'
                 WHERE id = ?
                """,
                (max(0, int(duration_seconds)), int(ended_at), int(ended_at), session_id),
            )

    def close_open_sessions(self) -> int:
        """应用异常退出后，用最后一次心跳结束遗留的 active 会话。"""
        with self.conn:
            cursor = self.conn.execute(
                """
                UPDATE sessions
                   SET ended_at = COALESCE(last_heartbeat, started_at),
                       status = 'completed'
                 WHERE status = 'active'
                """
            )
            return int(cursor.rowcount)

    def get_active_sessions(self) -> list[Session]:
        rows = self.conn.execute(
            "SELECT * FROM sessions WHERE status = 'active' ORDER BY started_at"
        ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def get_active_session(self, game_id: int) -> Session | None:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE game_id = ? AND status = 'active'", (game_id,)
        ).fetchone()
        return self._row_to_session(row) if row else None

    def list_sessions(self, game_id: int, limit: int = 50) -> list[Session]:
        rows = self.conn.execute(
            """
            SELECT * FROM sessions WHERE game_id = ?
             ORDER BY started_at DESC, id DESC LIMIT ?
            """,
            (game_id, limit),
        ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def list_sessions_since(self, since: int) -> list[Session]:
        rows = self.conn.execute(
            """
            SELECT * FROM sessions
             WHERE COALESCE(ended_at, last_heartbeat) >= ? OR started_at >= ?
             ORDER BY started_at ASC
            """,
            (since, since),
        ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def total_seconds(self) -> int:
        value = self.conn.execute(
            "SELECT COALESCE(SUM(duration_seconds), 0) FROM sessions"
        ).fetchone()[0]
        return int(value or 0)

    def top_games(self, limit: int = 5) -> list[tuple[Game, int]]:
        rows = self.conn.execute(
            """
            SELECT g.*, COALESCE(SUM(s.duration_seconds), 0) AS total_seconds
              FROM games g JOIN sessions s ON s.game_id = g.id
             GROUP BY g.id
             HAVING total_seconds > 0
             ORDER BY total_seconds DESC, g.name COLLATE NOCASE ASC
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [(self._row_to_game(row), int(row["total_seconds"])) for row in rows]

    def export_rows(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT g.name AS game_name, g.exe_path, s.started_at, s.ended_at,
                   s.duration_seconds, s.source, s.status
              FROM sessions s JOIN games g ON g.id = s.game_id
             ORDER BY s.started_at ASC
            """
        ).fetchall()

    # --------------------------------------------------------------- settings
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO settings(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _row_to_game(row: sqlite3.Row) -> Game:
        return Game(
            id=int(row["id"]),
            name=str(row["name"]),
            exe_path=str(row["exe_path"]),
            exe_name=str(row["exe_name"]),
            icon_file=str(row["icon_file"]) if row["icon_file"] else None,
            accent=str(row["accent"]),
            notes=str(row["notes"] or ""),
            created_at=int(row["created_at"]),
            updated_at=int(row["updated_at"]),
        )

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> Session:
        return Session(
            id=int(row["id"]),
            game_id=int(row["game_id"]),
            started_at=int(row["started_at"]),
            ended_at=int(row["ended_at"]) if row["ended_at"] is not None else None,
            duration_seconds=int(row["duration_seconds"]),
            last_heartbeat=int(row["last_heartbeat"]),
            source=str(row["source"]),
            status=str(row["status"]),
        )
