"""Windows 集成项验证：真实托盘、关闭到托盘、通知入口、注册表开机自启。

该脚本会临时写入 HKCU\\...\\Run\\GameTime，并在结束时恢复原值。
"""

from __future__ import annotations

import os
import sys
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.pop("GAMETIME_DISABLE_TRAY", None)

from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QSystemTrayIcon  # noqa: E402

from gametime.app import _apply_app_style  # noqa: E402
from gametime.database import Database  # noqa: E402
from gametime.paths import AppPaths  # noqa: E402
from gametime.services.icons import IconService  # noqa: E402
from gametime.services.launcher import GameLauncher  # noqa: E402
from gametime.services.library import GameService  # noqa: E402
from gametime.services.settings import RUN_KEY, VALUE_NAME, AutostartManager, SettingsStore  # noqa: E402
from gametime.services.stats import StatsService  # noqa: E402
from gametime.services.tracking import TrackingEngine  # noqa: E402
from gametime.ui.main_window import MainWindow  # noqa: E402

DATA = ROOT / "build" / "manual-check-data"


def read_autostart_value():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, VALUE_NAME)[0]
    except FileNotFoundError:
        return None


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    _apply_app_style(app)
    paths = AppPaths(DATA).ensure()
    db = Database(paths.database)
    icons = IconService(paths.icons)
    library = GameService(db, icons)
    tracker = TrackingEngine(db, library)
    window = MainWindow(
        paths=paths,
        db=db,
        library=library,
        stats=StatsService(db),
        tracker=tracker,
        settings=SettingsStore(db),
        autostart=AutostartManager,
        launcher=GameLauncher(),
        start_timers=False,
    )
    window.show()
    QTest.qWait(500)
    assert window.tray is not None, "系统托盘不可用"
    assert window.tray.isVisible()
    assert len(window.tray_menu.actions()) >= 3
    print("PASS tray_created")

    # 托盘菜单“打开主界面”动作
    window.hide()
    window.tray_menu.actions()[0].trigger()
    QTest.qWait(200)
    assert window.isVisible()
    print("PASS tray_open_action")

    # 单击托盘图标：显示/隐藏切换
    window._tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
    QTest.qWait(100)
    assert window.isHidden()
    window._tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
    QTest.qWait(200)
    assert window.isVisible()
    print("PASS tray_toggle")

    # 关闭到托盘
    window.settings.set_bool("close_to_tray", True)
    window.close()
    QTest.qWait(200)
    assert window.isHidden()
    assert window.tray is not None
    print("PASS close_to_tray")
    window.show()

    # 通知入口可调用
    window.tray.showMessage(
        "游时 · 验证", "Windows 通知入口可用。", QSystemTrayIcon.MessageIcon.Information, 1000
    )
    print("PASS tray_notification_api")

    # 开机自启真实写入、读取、删除与恢复
    original = read_autostart_value()
    try:
        AutostartManager.set_enabled(True)
        assert AutostartManager.is_enabled()
        enabled_command = read_autostart_value()
        assert enabled_command and "--minimized" in enabled_command
        AutostartManager.set_enabled(False)
        assert not AutostartManager.is_enabled()
        print("PASS autostart_registry")
    finally:
        if original is None:
            try:
                AutostartManager.set_enabled(False)
            except Exception:
                pass
        else:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, str(original))

    window.hide()
    window.shutdown()
    if window.tray:
        window.tray.hide()
    window.deleteLater()
    app.processEvents()
    db.close()
    print("ALL_WINDOWS_FEATURE_CHECKS_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
