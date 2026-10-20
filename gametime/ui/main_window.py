"""主窗口：侧边导航、四个页面、托盘与后台计时协调器。"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from PySide6.QtCore import QByteArray, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..database import Database
from ..models import TrackingEvent
from ..paths import AppPaths, resource_path
from ..services.export import export_sessions_csv
from ..services.launcher import GameLauncher
from ..services.library import GameService
from ..services.settings import AutostartManager, SettingsStore
from ..services.stats import StatsService
from ..services.tracking import SessionConflictError, TrackingEngine
from ..windows import apply_dark_title_bar
from .dialogs import AddGameDialog, GameDetailDialog
from .dialogs_confirm import show_message
from .formatting import format_duration
from .icons import pixmap
from .pages import DashboardPage, LibraryPage, SettingsPage, StatsPage
from .theme import COLORS
from .widgets import NavButton

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        paths: AppPaths,
        db: Database,
        library: GameService,
        stats: StatsService,
        tracker: TrackingEngine,
        settings: SettingsStore,
        autostart: AutostartManager,
        launcher: GameLauncher,
        start_timers: bool = True,
    ) -> None:
        super().__init__()
        self.paths = paths
        self.db = db
        self.library = library
        self.stats = stats
        self.tracker = tracker
        self.settings = settings
        self.autostart = autostart
        self.launcher = launcher
        self._force_quit = False
        self._cleaned = False
        self._tray_hint_shown = False
        self._detail: GameDetailDialog | None = None
        self._detail_id: int | None = None
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._hide_toast)

        self.setWindowTitle(f"{APP_NAME} · 桌面游戏助手")
        self.setMinimumSize(1000, 660)
        self.resize(1180, 780)
        app_icon = self._app_icon()
        self.setWindowIcon(app_icon)
        self.tracker.add_listener(self._on_tracking_event)
        self._build_ui()
        self._setup_tray()
        self._restore_geometry()
        self._center_if_needed()

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(2000)
        self.poll_timer.timeout.connect(self._poll)
        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(1000)
        self.ui_timer.timeout.connect(self._tick_ui)
        self.stats_timer = QTimer(self)
        self.stats_timer.setInterval(15000)
        self.stats_timer.timeout.connect(self._periodic_refresh)
        if start_timers:
            self.start_timers()

        self._update_sidebar_live()
        self._update_tray_tooltip()

    # ------------------------------------------------------------------ build
    def _app_icon(self) -> QIcon:
        for candidate in (
            resource_path("gametime", "resources", "app_icon.png"),
            resource_path("gametime", "resources", "app.ico"),
        ):
            if candidate.is_file():
                return QIcon(str(candidate))
        return QIcon(pixmap("gamepad", COLORS["accent"], 64))

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("AppRoot")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(224)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(17, 22, 17, 18)
        side.setSpacing(6)

        logo_row = QHBoxLayout()
        logo_row.setSpacing(11)
        logo = QLabel()
        logo.setFixedSize(40, 40)
        logo_image = self._app_icon().pixmap(40, 40)
        logo.setPixmap(logo_image)
        logo.setScaledContents(True)
        logo.setStyleSheet("border-radius: 10px;")
        logo_row.addWidget(logo)
        logo_text = QVBoxLayout()
        logo_text.setSpacing(0)
        title = QLabel(APP_NAME)
        title.setObjectName("LogoTitle")
        sub = QLabel("GAMETIME")
        sub.setObjectName("LogoSub")
        logo_text.addWidget(title)
        logo_text.addWidget(sub)
        logo_row.addLayout(logo_text, 1)
        side.addLayout(logo_row)
        side.addSpacing(24)
        section = QLabel("工作台")
        section.setProperty("role", "section")
        side.addWidget(section)
        side.addSpacing(4)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[NavButton] = []
        for index, (label, icon_name) in enumerate(
            (("概览", "home"), ("游戏库", "library"), ("统计", "chart"), ("设置", "settings"))
        ):
            button = NavButton(label, icon_name)
            self.nav_group.addButton(button, index)
            self.nav_buttons.append(button)
            side.addWidget(button)
        self.nav_group.idClicked.connect(self._navigate)
        self.nav_buttons[0].setChecked(True)

        side.addStretch(1)
        self.sidebar_live = QFrame()
        self.sidebar_live.setProperty("card", "soft")
        sidebar_live_layout = QVBoxLayout(self.sidebar_live)
        sidebar_live_layout.setContentsMargins(13, 12, 13, 12)
        sidebar_live_layout.setSpacing(6)
        live_header = QHBoxLayout()
        live_header.setSpacing(6)
        self.sidebar_dot = QLabel()
        self.sidebar_dot.setFixedSize(7, 7)
        self.sidebar_dot.setStyleSheet("background: #55627A; border-radius: 3px;")
        live_header.addWidget(self.sidebar_dot)
        live_title = QLabel("计时状态")
        live_title.setProperty("role", "faint")
        live_header.addWidget(live_title)
        live_header.addStretch(1)
        sidebar_live_layout.addLayout(live_header)
        self.sidebar_game = QLabel("待机中")
        self.sidebar_game.setStyleSheet("font-size: 12px; font-weight: 600; color: #C8D1E2;")
        self.sidebar_game.setWordWrap(True)
        sidebar_live_layout.addWidget(self.sidebar_game)
        self.sidebar_time = QLabel("游戏启动后自动计时")
        self.sidebar_time.setProperty("role", "faint")
        sidebar_live_layout.addWidget(self.sidebar_time)
        side.addWidget(self.sidebar_live)
        side.addSpacing(8)
        version = QLabel(f"v{__version__} · 本地数据")
        version.setProperty("role", "faint")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(version)
        root.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.dashboard = DashboardPage(self.library, self.stats, self.tracker)
        self.library_page = LibraryPage(self.library, self.tracker)
        self.stats_page = StatsPage(self.library, self.stats)
        self.settings_page = SettingsPage(self.settings, self.paths, self.autostart)
        for page in (self.dashboard, self.library_page, self.stats_page, self.settings_page):
            self.stack.addWidget(page)
        root.addWidget(self.stack, 1)

        self.dashboard.addRequested.connect(self._add_game)
        self.dashboard.openGame.connect(self.open_detail)
        self.dashboard.quickAction.connect(self._quick_action)
        self.dashboard.showLibrary.connect(lambda: self._navigate(1))
        self.library_page.addRequested.connect(self._add_game)
        self.library_page.openGame.connect(self.open_detail)
        self.library_page.quickAction.connect(self._quick_action)
        self.stats_page.exportRequested.connect(self._export_csv)
        self.stats_page.openGame.connect(self.open_detail)
        self.settings_page.exportRequested.connect(self._export_csv)
        self.settings_page.openDataRequested.connect(self._open_data_dir)

        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._add_game)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_search)
        QShortcut(QKeySequence("Escape"), self, activated=self._hide_detail)

        self._build_toast(central)
        self.dashboard.refresh()

    def _build_toast(self, parent: QWidget) -> None:
        self.toast = QFrame(parent)
        self.toast.setObjectName("Toast")
        self.toast.setStyleSheet(
            "QFrame#Toast { background: #1B2434; border: 1px solid #33425C; border-radius: 10px; }"
            "QLabel { background: transparent; border: none; color: #E8EDF5; font-size: 12px; }"
        )
        layout = QHBoxLayout(self.toast)
        layout.setContentsMargins(13, 8, 14, 8)
        layout.setSpacing(8)
        self.toast_icon = QLabel()
        self.toast_icon.setPixmap(pixmap("check", COLORS["green"], 14))
        layout.addWidget(self.toast_icon)
        self.toast_label = QLabel("")
        layout.addWidget(self.toast_label)
        self.toast.hide()

    # ------------------------------------------------------------------- tray
    def _setup_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if os.environ.get("GAMETIME_DISABLE_TRAY") or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(self._app_icon(), self)
        tray.setToolTip(f"{APP_NAME} · 桌面游戏助手")
        menu = QMenu()
        self.tray_menu = menu
        open_action = QAction("打开主界面", self)
        open_action.triggered.connect(self.show_main)
        menu.addAction(open_action)
        self.tray_status_action = QAction("当前没有计时", self)
        self.tray_status_action.setEnabled(False)
        menu.addAction(self.tray_status_action)
        menu.addSeparator()
        quit_action = QAction("退出游时", self)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(self._tray_activated)
        tray.show()
        self.tray = tray

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            if self.isVisible() and not self.isMinimized():
                self.hide()
            else:
                self.show_main()

    def _update_tray_tooltip(self) -> None:
        if not self.tray:
            return
        runs = self.tracker.active_runs
        if runs:
            names = []
            for game_id in runs:
                try:
                    names.append(self.library.get_game(game_id).name)
                except Exception:
                    continue
            text = "、".join(names[:2])
            suffix = f" 等 {len(names)} 款" if len(names) > 2 else ""
            self.tray.setToolTip(f"{APP_NAME} · 正在计时：{text}{suffix}")
            if hasattr(self, "tray_status_action"):
                self.tray_status_action.setText(f"正在计时：{text}{suffix}")
        else:
            self.tray.setToolTip(f"{APP_NAME} · 待机中")
            if hasattr(self, "tray_status_action"):
                self.tray_status_action.setText("当前没有计时")

    # ----------------------------------------------------------------- timing
    def start_timers(self) -> None:
        self.poll_timer.start()
        self.ui_timer.start()
        self.stats_timer.start()
        QTimer.singleShot(350, self._poll)

    def _poll(self) -> None:
        try:
            self.tracker.poll()
        except Exception:
            log.exception("轮询计时失败")
        self._update_live()

    def _tick_ui(self) -> None:
        self._update_live()

    def _periodic_refresh(self) -> None:
        self._refresh_current_page()
        self._update_live()

    def _update_live(self) -> None:
        if self.stack.currentIndex() == 0:
            self.dashboard.refresh_live()
        elif self.stack.currentIndex() == 1:
            self.library_page.refresh_live()
        self._update_sidebar_live()
        self._update_tray_tooltip()
        if self._detail and self._detail.isVisible():
            self._detail.refresh_live()

    def _update_sidebar_live(self) -> None:
        runs = self.tracker.active_runs
        if not runs:
            self.sidebar_dot.setStyleSheet("background: #55627A; border-radius: 3px;")
            self.sidebar_game.setText("待机中")
            self.sidebar_time.setText("游戏启动后自动计时")
            return
        self.sidebar_dot.setStyleSheet(f"background: {COLORS['green']}; border-radius: 3px;")
        game_id = next(iter(runs))
        try:
            game = self.library.get_game(game_id)
            self.sidebar_game.setText(game.name)
        except Exception:
            self.sidebar_game.setText("正在计时")
        source = self.tracker.active_source(game_id)
        extra = f" · 另有 {len(runs) - 1} 款" if len(runs) > 1 else ""
        self.sidebar_time.setText(
            f"{'自动' if source == 'auto' else '手动'} {format_duration(self.tracker.live_elapsed(game_id), zero='00:00')}{extra}"
        )

    def _on_tracking_event(self, event: TrackingEvent) -> None:
        log.info("游戏事件 %s: %s (%s)", event.kind, event.game_name, event.source)
        if event.kind == "started":
            self._show_toast(f"开始记录《{event.game_name}》")
            if self.settings.get_bool("notify_game_started", False) and self.tray:
                self.tray.showMessage(
                    f"{APP_NAME} · 开始计时",
                    f"《{event.game_name}》正在游玩，游时会在退出后自动保存。",
                    QSystemTrayIcon.MessageIcon.Information,
                    3500,
                )
        QTimer.singleShot(0, self._after_tracking_event)

    def _after_tracking_event(self) -> None:
        self._refresh_current_page()
        self._update_sidebar_live()
        self._update_tray_tooltip()
        if self._detail and self._detail.isVisible():
            self._detail.refresh()

    # --------------------------------------------------------------- navigation
    def _navigate(self, index: int) -> None:
        if not 0 <= index < self.stack.count():
            return
        self.stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)
        self._refresh_current_page()

    def _refresh_current_page(self) -> None:
        index = self.stack.currentIndex()
        if index == 0:
            self.dashboard.refresh()
        elif index == 1:
            self.library_page.refresh()
        elif index == 2:
            self.stats_page.refresh()
        elif index == 3:
            self.settings_page.refresh()

    def _focus_search(self) -> None:
        self._navigate(1)
        self.library_page.focus_search()

    # ----------------------------------------------------------------- actions
    def _add_game(self) -> None:
        dialog = AddGameDialog(self.library, self.library.icons, parent=self)
        if dialog.exec() == AddGameDialog.DialogCode.Accepted and dialog.saved_game:
            self.library_page.refresh()
            self.dashboard.refresh()
            self._show_toast(f"已添加《{dialog.saved_game.name}》")
            self._navigate(1)

    def _quick_action(self, game_id: int) -> None:
        source = self.tracker.active_source(game_id)
        if source == "manual":
            try:
                self.tracker.stop_manual(game_id)
            except SessionConflictError as exc:
                self._show_toast(str(exc), error=True)
            self._after_tracking_event()
            return
        if source == "auto":
            self.open_detail(game_id)
            return
        self._launch_game(game_id)

    def _launch_game(self, game_id: int) -> None:
        try:
            game = self.library.get_game(game_id)
        except Exception:
            self._show_toast("游戏不存在或已被移除", error=True)
            return
        if not game.path_exists:
            self.open_detail(game_id)
            return
        result = self.launcher.launch(game)
        if not result.ok:
            self._show_toast(result.error, error=True)
            return
        self._show_toast(f"正在启动《{game.name}》…")
        QTimer.singleShot(1200, self._poll)

    def open_detail(self, game_id: int) -> None:
        if self._detail is not None:
            if self._detail_id == game_id and self._detail.isVisible():
                self._detail.raise_()
                self._detail.activateWindow()
                return
            old_detail = self._detail
            self._detail = None
            self._detail_id = None
            old_detail.close()
            old_detail.deleteLater()
        try:
            detail = GameDetailDialog(
                game_id,
                self.library,
                self.stats,
                self.tracker,
                self.launcher,
                self.library.icons,
                self,
            )
        except Exception:
            log.exception("打开游戏详情失败")
            self._show_toast("无法打开游戏详情", error=True)
            return
        detail.dataChanged.connect(self._detail_changed)
        detail.deleted.connect(self._detail_deleted)
        detail.finished.connect(self._detail_closed)
        self._detail = detail
        self._detail_id = game_id
        detail.show()
        detail.raise_()
        detail.activateWindow()

    def _hide_detail(self) -> None:
        if self._detail and self._detail.isVisible():
            self._detail.close()

    def _detail_closed(self) -> None:
        if self._detail is not None:
            self._detail.deleteLater()
        self._detail = None
        self._detail_id = None
        self._refresh_current_page()

    def _detail_changed(self) -> None:
        self._refresh_current_page()

    def _detail_deleted(self, game_id: int) -> None:
        self._show_toast("游戏已从库中移除")
        self._refresh_current_page()

    # -------------------------------------------------------------------- data
    def _export_csv(self) -> None:
        default = self.paths.exports / f"游时计时记录_{datetime.now():%Y%m%d}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出计时记录", str(default), "CSV 文件 (*.csv)"
        )
        if not path:
            return
        try:
            export_sessions_csv(self.db, path)
        except Exception as exc:
            log.exception("导出失败")
            show_message(self, "导出失败", f"无法写入文件：{exc}", danger=True)
            return
        show_message(self, "导出完成", f"计时记录已保存到：\n{path}")

    def _open_data_dir(self) -> None:
        if not self.launcher.open_path(self.paths.root):
            self._show_toast("无法打开数据目录", error=True)

    # ------------------------------------------------------------------- toast
    def _show_toast(self, message: str, *, error: bool = False) -> None:
        self.toast_label.setText(message)
        self.toast_icon.setPixmap(
            pixmap("alert" if error else "check", COLORS["red"] if error else COLORS["green"], 14)
        )
        self.toast.adjustSize()
        self._position_toast()
        self.toast.show()
        self.toast.raise_()
        self._toast_timer.start(3200)

    def _hide_toast(self) -> None:
        self.toast.hide()

    def _position_toast(self) -> None:
        parent = self.centralWidget()
        if not parent:
            return
        width = min(self.toast.sizeHint().width(), parent.width() - 40)
        self.toast.setMinimumWidth(0)
        self.toast.resize(max(220, width), self.toast.sizeHint().height())
        x = (parent.width() - self.toast.width()) // 2
        y = parent.height() - self.toast.height() - 22
        self.toast.move(x, y)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "toast") and self.toast.isVisible():
            self._position_toast()

    # ----------------------------------------------------------------- geometry
    def _restore_geometry(self) -> None:
        raw = self.settings.get("window_geometry", "")
        if raw:
            try:
                encoded = QByteArray.fromBase64(raw.encode("ascii"))
                if self.restoreGeometry(encoded):
                    return
            except Exception:
                pass
        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.resize(min(1180, area.width() - 80), min(780, area.height() - 80))
            self.move(
                area.x() + (area.width() - self.width()) // 2,
                area.y() + (area.height() - self.height()) // 2,
            )

    def _center_if_needed(self) -> None:
        screen = QApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        if not area.intersects(self.frameGeometry()):
            self.move(
                area.x() + (area.width() - self.width()) // 2,
                area.y() + (area.height() - self.height()) // 2,
            )

    def _save_geometry(self) -> None:
        try:
            data = bytes(self.saveGeometry().toBase64()).decode("ascii")
            self.settings.set("window_geometry", data)
        except Exception:
            pass

    # ------------------------------------------------------------------- window
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        apply_dark_title_bar(int(self.winId()))

    def show_main(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        apply_dark_title_bar(int(self.winId()))

    def hide_to_tray(self) -> None:
        if not self.tray:
            return
        self._hide_detail()
        self._save_geometry()
        self.hide()
        if not self._tray_hint_shown:
            self.tray.showMessage(
                f"{APP_NAME} 仍在运行",
                "窗口已隐藏到托盘，游戏计时不会中断。右键托盘图标可以退出。",
                QSystemTrayIcon.MessageIcon.Information,
                3500,
            )
            self._tray_hint_shown = True

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        should_hide = (
            not self._force_quit
            and self.tray is not None
            and self.settings.get_bool("close_to_tray", True)
        )
        if should_hide:
            event.ignore()
            self.hide_to_tray()
            return
        self._save_geometry()
        self.shutdown()
        event.accept()
        QTimer.singleShot(0, QApplication.quit)

    def quit_app(self) -> None:
        self._force_quit = True
        self.close()

    def shutdown(self) -> None:
        if self._cleaned:
            return
        self._cleaned = True
        for timer in (getattr(self, "poll_timer", None), getattr(self, "ui_timer", None), getattr(self, "stats_timer", None)):
            if timer is not None:
                timer.stop()
        try:
            self.tracker.shutdown()
        except Exception:
            log.exception("退出时保存计时失败")
        if self._detail is not None:
            self._detail.close()
            self._detail = None
        self._save_geometry()
        if self.tray:
            self.tray.hide()
        try:
            self.db.close()
        except Exception:
            log.exception("关闭数据库失败")
