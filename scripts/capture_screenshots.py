"""从演示数据渲染界面截图，输出到 docs/images。"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GAMETIME_DISABLE_TRAY", "1")

from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gametime.app import _apply_app_style  # noqa: E402
from gametime.database import Database  # noqa: E402
from gametime.paths import AppPaths  # noqa: E402
from gametime.services.icons import IconService  # noqa: E402
from gametime.services.launcher import GameLauncher  # noqa: E402
from gametime.services.library import GameService  # noqa: E402
from gametime.services.scanner import ScanResult  # noqa: E402
from gametime.services.settings import AutostartManager, SettingsStore  # noqa: E402
from gametime.services.stats import StatsService  # noqa: E402
from gametime.services.tracking import TrackingEngine  # noqa: E402
from gametime.ui.dialogs import AddGameDialog, GameDetailDialog  # noqa: E402
from gametime.ui.dialogs_scan import ScanGamesDialog  # noqa: E402
from gametime.ui.main_window import MainWindow  # noqa: E402

OUT = ROOT / "docs" / "images"
DEMO = ROOT / "build" / "demo-data"
GAME_ROOT = ROOT / "build" / "demo-games"


def settle(app: QApplication, ms: int = 300) -> None:
    app.processEvents()
    QTest.qWait(ms)
    app.processEvents()


def grab(widget, name: str) -> None:
    path = OUT / name
    pixmap = widget.grab()
    pixmap.save(str(path), "PNG")
    print(f"wrote {path} ({pixmap.width()}x{pixmap.height()})")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setApplicationName("GameTime")
    app.setQuitOnLastWindowClosed(False)
    _apply_app_style(app)
    paths = AppPaths(DEMO).ensure()
    db = Database(paths.database)
    icons = IconService(paths.icons)
    library = GameService(db, icons)
    stats = StatsService(db)
    settings = SettingsStore(db)
    tracker = TrackingEngine(db, library)
    launcher = GameLauncher()
    window = MainWindow(
        paths=paths,
        db=db,
        library=library,
        stats=stats,
        tracker=tracker,
        settings=settings,
        autostart=AutostartManager,
        launcher=launcher,
        start_timers=False,
    )
    window.resize(1200, 800)
    window.show()
    settle(app, 700)

    games = {summary.game.name: summary for summary in library.list_games()}
    active = games["黑神话：悟空"].game
    tracker.start_manual(active.id)
    run = tracker._active[active.id]
    run.duration = 22 * 60 + 37
    run.last_tick = int(time.time())
    window.dashboard.refresh()
    window._update_live()
    window._hide_toast()
    settle(app, 300)
    grab(window, "01-dashboard.png")

    window._navigate(1)
    window.library_page.refresh()
    window._hide_toast()
    settle(app, 300)
    grab(window, "02-library.png")

    window._navigate(2)
    window._hide_toast()
    settle(app, 300)
    grab(window, "03-stats.png")

    window._navigate(3)
    window._hide_toast()
    settle(app, 300)
    grab(window, "04-settings.png")

    detail = GameDetailDialog(
        active.id, library, stats, tracker, launcher, icons, window
    )
    detail.show()
    detail.raise_()
    window._hide_toast()
    settle(app, 500)
    grab(detail, "05-game-detail.png")

    add = AddGameDialog(library, icons, parent=window)
    add.path_edit.setText(str(GAME_ROOT / "game2" / "Cyberpunk2077.exe"))
    add._path_finished()
    add.preview.set_pixmap(QPixmap(str(paths.icons / "demo_2.png")))
    add.notes_edit.setText("夜之城，第二次通关")
    add.show()
    add.raise_()
    settle(app, 400)
    grab(add, "06-add-game.png")
    add.close()
    detail.close()

    missing = games["只狼：影逝二度"].game
    missing_detail = GameDetailDialog(
        missing.id, library, stats, tracker, launcher, icons, window
    )
    missing_detail.show()
    missing_detail.raise_()
    settle(app, 400)
    grab(missing_detail, "07-missing-game.png")
    missing_detail.close()

    window._apply_theme_mode("light", notify=False)
    window._navigate(0)
    window.dashboard.refresh()
    window._hide_toast()
    settle(app, 500)
    grab(window, "09-dashboard-light.png")

    window._navigate(3)
    window._hide_toast()
    settle(app, 300)
    grab(window, "10-settings-light.png")

    scan = ScanGamesDialog(
        library,
        parent=window,
        auto_start=False,
        initial_results=[
            ScanResult(
                exe_path=r"D:\APP2\Yslzm\LifeMakeoverGame_ob_zh_944\Azure\Binaries\Win64\Azure-Win64-Shipping.exe",
                display_name="以闪亮之名",
                folder_name="LifeMakeoverGame",
                source="全盘扫描",
                size_bytes=79_034_880,
            ),
            ScanResult(
                exe_path=games["赛博朋克 2077"].game.exe_path,
                display_name="赛博朋克 2077",
                folder_name="Cyberpunk 2077",
                source="Steam",
                already_added=True,
                size_bytes=72_000_000_000,
            ),
            ScanResult(
                exe_path=games["艾尔登法环"].game.exe_path,
                display_name="艾尔登法环",
                folder_name="ELDEN RING",
                source="Steam",
                already_added=True,
                size_bytes=49_000_000_000,
            ),
            ScanResult(
                exe_path=str(GAME_ROOT / "game-new1" / "AuroraVale.exe"),
                display_name="Aurora Vale",
                folder_name="Aurora Vale",
                source="Steam",
                size_bytes=18_600_000_000,
            ),
            ScanResult(
                exe_path=str(GAME_ROOT / "game-new2" / "NeonDrift.exe"),
                display_name="Neon Drift",
                folder_name="Neon Drift",
                source="Epic",
                size_bytes=31_200_000_000,
            ),
            ScanResult(
                exe_path=str(GAME_ROOT / "game-new3" / "PaperMoon.exe"),
                display_name="Paper Moon",
                folder_name="Paper Moon",
                source="自定义文件夹",
                size_bytes=4_800_000_000,
            ),
        ],
    )
    scan.show()
    scan.raise_()
    settle(app, 400)
    grab(scan, "11-scan-games.png")
    scan.close()
    window.hide()
    tracker.shutdown()
    if window.tray:
        window.tray.hide()
    db.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
