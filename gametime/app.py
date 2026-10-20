"""应用入口与基础设施（日志、单实例）。"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QIODevice, QTimer
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from . import APP_ID, APP_NAME, __version__
from .database import Database
from .paths import AppPaths
from .services.icons import IconService
from .services.launcher import GameLauncher
from .services.library import GameService
from .services.settings import AutostartManager, SettingsStore
from .services.stats import StatsService
from .services.tracking import TrackingEngine
from .ui.main_window import MainWindow
from .ui.theme import build_stylesheet
from .windows import set_app_user_model_id

log = logging.getLogger(__name__)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="GameTime", description="游时 · 桌面游戏时长记录器")
    parser.add_argument("--data-dir", type=str, default=None, help="覆盖数据目录（便于测试）")
    parser.add_argument("--minimized", action="store_true", help="启动时隐藏到系统托盘")
    parser.add_argument("--smoke-test", action="store_true", help="无界面快速自检后退出")
    parser.add_argument("--smoke-output", type=str, default=None, help="自检结果 JSON 输出路径")
    parser.add_argument("--version", action="version", version=f"游时 GameTime {__version__}")
    return parser.parse_args(argv)


def setup_logging(paths: AppPaths) -> None:
    paths.ensure()
    level = logging.DEBUG if os.environ.get("GAMETIME_DEBUG") else logging.INFO
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    file_handler = RotatingFileHandler(
        paths.logs / "gametime.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    if not getattr(sys, "frozen", False):
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)


def _single_instance_name(paths: AppPaths) -> str:
    user = "".join(ch for ch in getpass.getuser() if ch.isalnum()) or "user"
    digest = hashlib.sha1(str(paths.root).lower().encode("utf-8")).hexdigest()[:10]
    return f"GameTime-{user}-{digest}"


def _activate_existing(name: str) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(name, QIODevice.OpenModeFlag.WriteOnly)
    if not socket.waitForConnected(250):
        return False
    socket.write(b"show")
    socket.flush()
    socket.waitForBytesWritten(250)
    socket.disconnectFromServer()
    return True


def _create_single_instance_server(name: str, window: MainWindow) -> QLocalServer | None:
    QLocalServer.removeServer(name)
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(name):
        log.warning("单实例服务监听失败：%s", server.errorString())
        return None

    def accept() -> None:
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            if connection is None:
                continue
            connection.readyRead.connect(window.show_main)
            connection.disconnected.connect(connection.deleteLater)
            QTimer.singleShot(0, window.show_main)

    server.newConnection.connect(accept)
    return server


def _install_exception_hook(smoke_test: bool, paths: AppPaths) -> None:
    def handle(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        log.critical("未捕获异常", exc_info=(exc_type, exc_value, exc_tb))
        if not smoke_test:
            try:
                box = QMessageBox()
                box.setIcon(QMessageBox.Icon.Critical)
                box.setWindowTitle("游时遇到问题")
                box.setText("程序遇到未处理的错误。")
                box.setInformativeText(
                    "计时数据已尽量保存。详细信息已写入日志：\n"
                    f"{paths.logs / 'gametime.log'}"
                )
                box.setDetailedText("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
                box.exec()
            except Exception:
                pass

    sys.excepthook = handle


def _apply_app_style(app: QApplication) -> None:
    from PySide6.QtGui import QFontDatabase

    families = set(QFontDatabase.families())
    family = "Microsoft YaHei UI" if "Microsoft YaHei UI" in families else "Segoe UI"
    font = QFont(family, 10)
    app.setFont(font)
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())


def _write_smoke_output(path: str | None, payload: dict) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.smoke_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    paths = AppPaths(args.data_dir).ensure()
    setup_logging(paths)
    log.info("启动游时 %s，数据目录 %s", __version__, paths.root)

    from PySide6.QtCore import Qt

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv[:1])
    app.setApplicationName("GameTime")
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("GameTime")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    set_app_user_model_id(APP_ID)
    icon_path = Path(__file__).resolve().parent / "resources" / "app_icon.png"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    _apply_app_style(app)
    _install_exception_hook(args.smoke_test, paths)

    if not args.smoke_test and not os.environ.get("GAMETIME_DISABLE_SINGLE_INSTANCE"):
        name = _single_instance_name(paths)
        if _activate_existing(name):
            log.info("检测到已运行的实例，已请求其显示主窗口")
            return 0

    db: Database | None = None
    server: QLocalServer | None = None
    try:
        db = Database(paths.database)
        icons = IconService(paths.icons)
        library = GameService(db, icons)
        stats = StatsService(db)
        settings = SettingsStore(db)
        if not args.smoke_test:
            try:
                # 移动过便携目录后，自动修正开机自启的命令路径。
                if AutostartManager.is_enabled():
                    AutostartManager.set_enabled(True)
            except Exception:
                log.warning("刷新开机自启路径失败", exc_info=True)
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
            start_timers=True,
        )
        app.aboutToQuit.connect(window.shutdown)
        if not args.smoke_test:
            server = _create_single_instance_server(_single_instance_name(paths), window)

        should_minimize = (args.minimized or settings.get_bool("launch_minimized", False)) and not args.smoke_test
        if should_minimize and window.tray is not None:
            window.hide()
        else:
            window.show()
        window.dashboard.refresh()

        if args.smoke_test:
            _write_smoke_output(
                args.smoke_output,
                {
                    "ok": True,
                    "version": __version__,
                    "data_dir": str(paths.root),
                    "game_count": library.db.count_games(),
                    "window_visible": window.isVisible(),
                    "theme_loaded": bool(app.styleSheet()),
                },
            )
            log.info("SMOKE_TEST_OK")
            QTimer.singleShot(700, app.quit)
        else:
            log.info("主窗口已就绪；单实例=%s，托盘=%s", server is not None, window.tray is not None)

        return app.exec()
    except Exception:
        log.exception("应用启动失败")
        if args.smoke_test:
            _write_smoke_output(
                args.smoke_output,
                {"ok": False, "error": traceback.format_exc()},
            )
        else:
            try:
                QMessageBox.critical(
                    None,
                    "游时启动失败",
                    f"应用无法启动。\n\n{paths.logs / 'gametime.log'}",
                )
            except Exception:
                pass
        return 1
    finally:
        if server is not None:
            server.close()
        if db is not None:
            db.close()


if __name__ == "__main__":
    raise SystemExit(main())
