from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GAMETIME_DISABLE_TRAY", "1")
os.environ.setdefault("GAMETIME_DISABLE_SINGLE_INSTANCE", "1")
os.environ.setdefault("GAMETIME_DATA_DIR", str(Path(__file__).resolve().parent.parent / "build" / "pytest-data"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from gametime.app import _apply_app_style  # noqa: E402
from gametime.database import Database  # noqa: E402
from gametime.paths import AppPaths  # noqa: E402
from gametime.services.icons import IconService  # noqa: E402
from gametime.services.library import GameService  # noqa: E402
from gametime.services.processes import FakeProcessScanner  # noqa: E402


class FakeClock:
    def __init__(self, start: int = 1_790_000_000) -> None:
        self.now = int(start)

    def __call__(self) -> float:
        return float(self.now)

    def advance(self, seconds: int) -> int:
        self.now += int(seconds)
        return self.now


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    _apply_app_style(app)
    yield app
    for widget in QApplication.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    app.processEvents()


@pytest.fixture
def paths(tmp_path: Path) -> AppPaths:
    return AppPaths(tmp_path / "data").ensure()


@pytest.fixture
def db(paths: AppPaths) -> Database:
    database = Database(paths.database)
    yield database
    database.close()


@pytest.fixture
def icons(paths: AppPaths) -> IconService:
    return IconService(paths.icons)


@pytest.fixture
def library(db: Database, icons: IconService) -> GameService:
    return GameService(db, icons)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def scanner() -> FakeProcessScanner:
    return FakeProcessScanner()


def make_exe(directory: Path, name: str = "game.exe", content: bytes = b"MZ" + b"\0" * 256) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(content)
    return path


@pytest.fixture
def exe_factory(tmp_path: Path):
    def factory(name: str = "game.exe") -> Path:
        return make_exe(tmp_path / "games", name)

    return factory


@pytest.fixture
def sample_game(library: GameService, exe_factory):
    return library.add_game("测试游戏", str(exe_factory("sample.exe")), "备注")


@pytest.fixture(scope="session")
def system_root() -> Path:
    return Path(os.environ.get("SystemRoot", r"C:\Windows"))


@pytest.fixture
def cleanup_widgets(qapp):
    created = []
    yield created
    for widget in created:
        try:
            widget.close()
            widget.deleteLater()
        except RuntimeError:
            pass
    qapp.processEvents()


def wait_until(predicate, timeout: float = 6.0, interval: float = 0.1) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())
