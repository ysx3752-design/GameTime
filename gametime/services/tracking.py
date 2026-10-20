"""计时引擎：轮询已添加游戏的进程，自动开启/结束会话，并支持手动计时。

时间计算要点：
- 只在进程存在时累计时长；
- 每次轮询最多累计 tick_cap 秒，电脑睡眠/休眠造成的大间隔不会被计入；
- 每 persist_interval 秒写一次心跳，异常退出后最多损失一个心跳周期；
- 所有游戏都必须先在游戏库中，引擎从不主动发现未知游戏。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable

from ..database import Database
from ..models import ActiveRun, Game, TrackingEvent
from ..windows import normalize_windows_path
from .library import GameService
from .processes import ProcessScanner

log = logging.getLogger(__name__)


class SessionConflictError(RuntimeError):
    pass


class TrackingEngine:
    def __init__(
        self,
        db: Database,
        library: GameService,
        scanner: ProcessScanner | None = None,
        *,
        clock: Callable[[], float] = time.time,
        tick_cap: int = 5,
        persist_interval: int = 10,
        auto_detect: bool = True,
    ) -> None:
        self.db = db
        self.library = library
        self.scanner = scanner or ProcessScanner()
        self.clock = clock
        self.tick_cap = max(1, int(tick_cap))
        self.persist_interval = max(1, int(persist_interval))
        self.auto_detect = auto_detect
        self._active: dict[int, ActiveRun] = {}
        self._listeners: list[Callable[[TrackingEvent], None]] = []
        self._closed = False
        # 上次异常退出遗留的 active 会话：用最后心跳时间收尾，避免时长膨胀。
        self.recovered_sessions = self.db.close_open_sessions()

    # --------------------------------------------------------------- listeners
    def add_listener(self, callback: Callable[[TrackingEvent], None]) -> None:
        self._listeners.append(callback)

    def _emit(self, run: ActiveRun, game: Game, kind: str) -> None:
        event = TrackingEvent(
            kind=kind,
            game_id=game.id,
            game_name=game.name,
            session_id=run.session_id,
            source=run.source,
        )
        for callback in list(self._listeners):
            try:
                callback(event)
            except Exception:
                log.exception("计时事件回调失败")

    # ------------------------------------------------------------------ public
    @property
    def active_runs(self) -> dict[int, ActiveRun]:
        return dict(self._active)

    def is_active(self, game_id: int) -> bool:
        return game_id in self._active

    def active_source(self, game_id: int) -> str | None:
        run = self._active.get(game_id)
        return run.source if run else None

    def live_elapsed(self, game_id: int, now: float | None = None) -> int:
        run = self._active.get(game_id)
        if run is None:
            return 0
        current = int(now if now is not None else self.clock())
        pending = max(0, min(current - run.last_tick, self.tick_cap))
        return int(run.duration + pending)

    def start_manual(self, game_id: int) -> int:
        game = self.library.get_game(game_id)
        if not game.path_exists:
            raise SessionConflictError("游戏程序已不存在，无法开始计时。")
        if game_id in self._active:
            raise SessionConflictError("这个游戏已经在计时中。")
        now = int(self.clock())
        session_id = self.db.start_session(game_id, "manual", now)
        run = ActiveRun(
            game_id=game_id,
            session_id=session_id,
            source="manual",
            started_at=now,
            last_tick=now,
            duration=0,
            last_persist=now,
        )
        self._active[game_id] = run
        self._emit(run, game, "started")
        return session_id

    def stop_manual(self, game_id: int) -> None:
        run = self._active.get(game_id)
        if run is None or run.source != "manual":
            raise SessionConflictError("这个游戏没有正在进行的手动计时。")
        now = int(self.clock())
        self._advance(run, now)
        self._finalize(run, now)
        game = self.library.get_game(game_id)
        self._emit(run, game, "stopped")

    def stop_game(self, game_id: int) -> None:
        """结束某个游戏的当前会话（不判断来源），供删除游戏等场景使用。"""
        run = self._active.get(game_id)
        if run is None:
            return
        game = self.library.get_game(game_id)
        now = int(self.clock())
        self._advance(run, now)
        self._finalize(run, now)
        self._emit(run, game, "stopped")

    def poll(self) -> None:
        if self._closed:
            return
        now = int(self.clock())
        for run in list(self._active.values()):
            self._advance(run, now)

        games = {summary.game.id: summary.game for summary in self.library.list_games(sort="name")}

        # 已删除的游戏，立刻结束其计时。
        for game_id, run in list(self._active.items()):
            if game_id not in games:
                self._finalize(run, now)

        running: set[str] | None
        if self.auto_detect:
            try:
                running = self.scanner.running_paths()
            except Exception:
                log.exception("进程检测失败，本轮跳过自动计时")
                running = None
        else:
            running = set()

        if running is not None:
            # 先结束已经退出的自动会话。
            for game_id, run in list(self._active.items()):
                if run.source != "auto":
                    continue
                game = games.get(game_id)
                if game is None or normalize_windows_path(game.exe_path) not in running:
                    self._finalize(run, now)

            # 再为刚启动的、且确实在游戏库里的游戏开启会话。
            for game in games.values():
                if game.id in self._active:
                    continue
                if not game.path_exists:
                    continue
                if normalize_windows_path(game.exe_path) in running:
                    self._start_auto(game, now)

        # 心跳持久化，保证崩溃/断电后的时长尽可能准确。
        for run in list(self._active.values()):
            if now - run.last_persist >= self.persist_interval:
                try:
                    self.db.update_session(
                        run.session_id, duration_seconds=run.duration, heartbeat=now
                    )
                    run.last_persist = now
                except Exception:
                    log.exception("写入计时心跳失败")

    def shutdown(self) -> None:
        if self._closed:
            return
        now = int(self.clock())
        for run in list(self._active.values()):
            self._advance(run, now)
            self._finalize(run, now, emit=False)
        self._closed = True

    # ----------------------------------------------------------------- private
    def _start_auto(self, game: Game, now: int) -> None:
        try:
            session_id = self.db.start_session(game.id, "auto", now)
        except Exception:
            log.exception("无法为 %s 开启自动计时", game.name)
            return
        run = ActiveRun(
            game_id=game.id,
            session_id=session_id,
            source="auto",
            started_at=now,
            last_tick=now,
            duration=0,
            last_persist=now,
        )
        self._active[game.id] = run
        self._emit(run, game, "started")

    def _advance(self, run: ActiveRun, now: int) -> None:
        if now < run.last_tick:
            run.last_tick = now
            return
        delta = min(now - run.last_tick, self.tick_cap)
        if delta > 0:
            run.duration += delta
        run.last_tick = now

    def _finalize(self, run: ActiveRun, now: int, *, emit: bool = True) -> None:
        self._active.pop(run.game_id, None)
        try:
            self.db.finish_session(
                run.session_id, duration_seconds=run.duration, ended_at=now
            )
        except Exception:
            log.exception("结束计时会话失败")
        if emit:
            try:
                game = self.library.get_game(run.game_id)
            except Exception:
                return
            self._emit(run, game, "stopped")

    def flush(self) -> None:
        """立即持久化当前所有会话的时长（用于退出前/测试）。"""
        now = int(self.clock())
        for run in list(self._active.values()):
            self._advance(run, now)
            try:
                self.db.update_session(
                    run.session_id, duration_seconds=run.duration, heartbeat=now
                )
                run.last_persist = now
            except Exception:
                log.exception("刷新计时失败")

    def __enter__(self) -> "TrackingEngine":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self.shutdown()


def active_game_ids(runs: Iterable[ActiveRun]) -> set[int]:
    return {run.game_id for run in runs}
