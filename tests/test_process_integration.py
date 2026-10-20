from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from gametime.database import Database
from gametime.services.library import GameService
from gametime.services.processes import ProcessScanner
from gametime.services.tracking import TrackingEngine

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows 进程集成测试")


def test_real_process_is_detected_and_recorded(
    db: Database, library: GameService, system_root: Path, tmp_path: Path
) -> None:
    source = system_root / "System32" / "ping.exe"
    if not source.is_file():
        pytest.skip("ping.exe not available")
    game_exe = tmp_path / "GameTimeIntegrationTest.exe"
    shutil.copy2(source, game_exe)
    game = library.add_game("进程集成测试", str(game_exe))

    process = subprocess.Popen(
        [str(game_exe), "-n", "30", "127.0.0.1"],
        cwd=str(tmp_path),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    tracker = TrackingEngine(db, library, ProcessScanner(), tick_cap=10, persist_interval=2)
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and not tracker.is_active(game.id):
            time.sleep(0.4)
            tracker.poll()
        assert tracker.is_active(game.id), "未检测到真实进程"
        time.sleep(2.2)
        tracker.poll()
        assert tracker.live_elapsed(game.id) >= 2

        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)

        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            tracker.poll()
            if not tracker.is_active(game.id):
                break
            time.sleep(0.3)
        assert not tracker.is_active(game.id)
        sessions = db.list_sessions(game.id)
        assert len(sessions) == 1
        assert sessions[0].status == "completed"
        assert sessions[0].duration_seconds >= 2
        assert sessions[0].source == "auto"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        tracker.shutdown()
