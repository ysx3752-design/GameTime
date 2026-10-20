import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gametime.database import Database
from gametime.paths import AppPaths
from gametime.services.icons import IconService
from gametime.services.library import GameService
from gametime.services.processes import FakeProcessScanner
from gametime.services.settings import AutostartManager, SettingsStore
from gametime.services.stats import StatsService
from gametime.services.tracking import TrackingEngine
from gametime.ui.pages import DashboardPage, LibraryPage, SettingsPage, StatsPage

app = QApplication(sys.argv)
paths = AppPaths().ensure()
db = Database(paths.database)
icons = IconService(paths.icons)
library = GameService(db, icons)
stats = StatsService(db)
tracker = TrackingEngine(db, library, FakeProcessScanner())
for cls, args in [
    (DashboardPage, (library, stats, tracker)),
    (LibraryPage, (library, tracker)),
    (StatsPage, (library, stats)),
    (SettingsPage, (SettingsStore(db), paths, AutostartManager)),
]:
    page = cls(*args)
    page.resize(900, 700)
    page.show()
    app.processEvents()
    page.refresh()
    app.processEvents()
    print(cls.__name__, "OK", page.sizeHint().width(), page.sizeHint().height())
print("all ok")
