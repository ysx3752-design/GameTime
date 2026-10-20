# ruff: noqa: E402
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("GAMETIME_DISABLE_TRAY", "1")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from gametime.app import _apply_app_style
from gametime.database import Database
from gametime.paths import AppPaths
from gametime.services.icons import IconService
from gametime.services.library import GameService
from gametime.ui.dialogs_scan import ScanGamesDialog

app = QApplication(sys.argv)
_apply_app_style(app, "light")
paths = AppPaths(ROOT / "build" / "scan-runtime").ensure()
db = Database(paths.database)
library = GameService(db, IconService(paths.icons))
dialog = ScanGamesDialog(library, auto_start=True)
dialog.show()
deadline = time.time() + 90
while time.time() < deadline and not dialog._scan_done:
    app.processEvents()
    time.sleep(0.05)
print("scan_done", dialog._scan_done, "rows", len(dialog._rows), "label", dialog.progress_label.text())
dialog.close()
QTest.qWait(300)
print("thread", dialog._thread)
db.close()
print("done")
