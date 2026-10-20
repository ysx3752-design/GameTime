"""添加 / 编辑 / 详情 / 确认对话框。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..models import Game
from ..services.icons import accent_for, letter_pixmap
from ..services.launcher import GameLauncher
from ..services.library import (
    DuplicateGameError,
    GameNotFoundError,
    GameService,
    GameValidationError,
)
from ..services.stats import StatsService
from ..services.tracking import SessionConflictError, TrackingEngine
from ..windows import apply_dark_title_bar, file_display_name
from .formatting import (
    format_duration,
    format_last_played,
)
from .icons import icon, pixmap
from .theme import COLORS
from .widgets import BarChart, CardFrame, GameIcon, Separator, SessionRow, SmallButton, pill


class _PreviewIcon(QWidget):
    def __init__(self, size: int = 76) -> None:
        super().__init__()
        self._size = size
        self._pixmap: QPixmap | None = None
        self.setFixedSize(size, size)

    def set_pixmap(self, value: QPixmap | None) -> None:
        self._pixmap = value
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._pixmap is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self._size, self._size, 20, 20)
        painter.setClipPath(path)
        scaled = self._pixmap.scaled(
            self._size,
            self._size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(0, 0, scaled)
        painter.end()


def _dialog_title(parent: QDialog, title: str, subtitle: str = "") -> QWidget:
    layout = QVBoxLayout()
    layout.setSpacing(4)
    heading = QLabel(title)
    heading.setProperty("role", "h1")
    layout.addWidget(heading)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setProperty("role", "muted")
        sub.setWordWrap(True)
        layout.addWidget(sub)
    holder = QWidget()
    holder.setLayout(layout)
    return holder


class AddGameDialog(QDialog):
    """添加或编辑游戏。"""

    def __init__(
        self,
        library: GameService,
        icons,
        *,
        game: Game | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.library = library
        self.icons = icons
        self.game = game
        self.saved_game: Game | None = None
        self._last_suggestion = ""
        self._loading = True
        self.setObjectName("ContentDialog")
        self.setWindowTitle("编辑游戏 · 游时" if game else "添加游戏 · 游时")
        self.setModal(True)
        self.setMinimumWidth(590)
        self.setFixedHeight(515 if game else 500)
        self._build()
        if game:
            self._load_game(game)
        self._loading = False

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(16)
        self.preview = _PreviewIcon(76)
        self.preview.set_pixmap(letter_pixmap("游", COLORS["accent"]))
        header.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(4)
        title = QLabel("编辑游戏" if self.game else "添加一款桌面游戏")
        title.setProperty("role", "h1")
        desc = QLabel(
            "游时不会自动扫描硬盘里的游戏；只有你在这里手动添加的程序才会被统计。"
        )
        desc.setProperty("role", "muted")
        desc.setWordWrap(True)
        text.addWidget(title)
        text.addWidget(desc)
        header.addLayout(text, 1)
        root.addLayout(header)

        form = QVBoxLayout()
        form.setSpacing(7)
        form.addWidget(self._field_label("游戏名称"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：艾尔登法环")
        self.name_edit.setClearButtonEnabled(True)
        self.name_edit.setMaxLength(80)
        form.addWidget(self.name_edit)
        form.addSpacing(4)
        form.addWidget(self._field_label("游戏程序"))
        path_row = QHBoxLayout()
        path_row.setSpacing(10)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(r"选择游戏的启动程序，例如 D:\Games\...\game.exe")
        self.path_edit.setClearButtonEnabled(True)
        self.browse_button = SmallButton("浏览…", "folder", variant="soft")
        self.browse_button.setMinimumWidth(92)
        self.browse_button.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(self.browse_button)
        form.addLayout(path_row)
        form.addSpacing(4)
        form.addWidget(self._field_label("备注（可选）"))
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("例如：通关目标、平台、版本")
        self.notes_edit.setMaxLength(500)
        form.addWidget(self.notes_edit)
        root.addLayout(form)

        self.hint = QLabel("提示：自动计时会在该 exe 进程运行时开始，退出时结束；也可在详情中手动计时。")
        self.hint.setProperty("role", "faint")
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        self.error_label = QLabel("")
        self.error_label.setProperty("role", "danger")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root.addWidget(self.error_label)
        root.addStretch(1)
        root.addWidget(Separator())

        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addStretch(1)
        cancel = SmallButton("取消", variant="ghost")
        cancel.clicked.connect(self.reject)
        self.save_button = QPushButton("保存游戏" if self.game else "添加到游戏库")
        self.save_button.setProperty("variant", "primary")
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.setMinimumHeight(36)
        self.save_button.setIcon(icon("check", "#FFFFFF", 15))
        self.save_button.clicked.connect(self._save)
        footer.addWidget(cancel)
        footer.addWidget(self.save_button)
        root.addLayout(footer)

        self.path_edit.editingFinished.connect(self._path_finished)
        self.name_edit.returnPressed.connect(self._save)
        self.notes_edit.returnPressed.connect(self._save)
        QTimer.singleShot(0, self.name_edit.setFocus)

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "muted")
        return label

    def _load_game(self, game: Game) -> None:
        self.name_edit.setText(game.name)
        self.path_edit.setText(game.exe_path)
        self.notes_edit.setText(game.notes)
        cached = self.library.icon_path(game)
        if cached:
            pixmap_value = QPixmap(str(cached))
            if not pixmap_value.isNull():
                self.preview.set_pixmap(pixmap_value)
        self._path_finished()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        apply_dark_title_bar(int(self.winId()))

    def _browse(self) -> None:
        start = self.path_edit.text().strip()
        directory = str(Path(start).parent) if start and Path(start).parent.is_dir() else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择游戏启动程序", directory, "Windows 程序 (*.exe)"
        )
        if path:
            self.path_edit.setText(path)
            self._path_finished()

    def _path_finished(self) -> None:
        raw = self.path_edit.text().strip().strip('"')
        if not raw:
            return
        path = Path(raw)
        if not path.is_file():
            self.error_label.setText("找不到这个文件，请重新选择游戏程序。")
            self.error_label.show()
            self.path_edit.setProperty("error", "true")
            self._repolish(self.path_edit)
            return
        self.error_label.hide()
        self.path_edit.setProperty("error", "false")
        self._repolish(self.path_edit)
        if not self.path_edit.hasFocus():
            self.path_edit.setCursorPosition(0)
        suggestion = file_display_name(path)
        current = self.name_edit.text().strip()
        if not current or current == self._last_suggestion:
            self.name_edit.setText(suggestion)
            self._last_suggestion = suggestion
        accent = accent_for(suggestion or path.stem, str(path))
        qicon = self.icons.icon_for_file(str(path), suggestion or path.stem, accent)
        preview = qicon.pixmap(QSize(256, 256))
        if preview.isNull():
            preview = letter_pixmap(suggestion or path.stem, accent)
        self.preview.set_pixmap(preview)

    def _save(self) -> None:
        if self._loading:
            return
        name = self.name_edit.text().strip()
        path = self.path_edit.text().strip()
        self.error_label.hide()
        try:
            if self.game is None:
                game = self.library.add_game(name, path, self.notes_edit.text())
            else:
                game = self.library.update_game(
                    self.game.id, name, path, self.notes_edit.text()
                )
        except (GameValidationError, DuplicateGameError, GameNotFoundError) as exc:
            self._show_error(str(exc))
            return
        except Exception as exc:  # pragma: no cover - 防御性
            self._show_error(f"保存失败：{exc}")
            return
        self.saved_game = game
        self.accept()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()
        self.path_edit.setProperty("error", "true")
        self._repolish(self.path_edit)
        self.error_label.setFocus()

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()


class GameDetailDialog(QDialog):
    dataChanged = Signal()
    deleted = Signal(int)

    def __init__(
        self,
        game_id: int,
        library: GameService,
        stats: StatsService,
        tracker: TrackingEngine,
        launcher: GameLauncher,
        icons,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.game_id = game_id
        self.library = library
        self.stats = stats
        self.tracker = tracker
        self.launcher = launcher
        self.icons = icons
        self._game: Game | None = None
        self.setObjectName("ContentDialog")
        self.setWindowTitle("游戏详情 · 游时")
        self.setMinimumSize(720, 620)
        self.resize(760, 660)
        self.setModal(False)
        self._build()
        self.refresh()

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("Page")
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(28, 24, 28, 24)
        self.body.setSpacing(18)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # 头部
        header = QHBoxLayout()
        header.setSpacing(16)
        self.icon_holder = QWidget()
        self.icon_layout = QVBoxLayout(self.icon_holder)
        self.icon_layout.setContentsMargins(0, 0, 0, 0)
        self.game_icon = GameIcon(82)
        self.icon_layout.addWidget(self.game_icon)
        header.addWidget(self.icon_holder, 0, Qt.AlignmentFlag.AlignTop)
        info = QVBoxLayout()
        info.setSpacing(5)
        title_row = QHBoxLayout()
        title_row.setSpacing(9)
        self.name_label = QLabel("")
        self.name_label.setProperty("role", "h1")
        title_row.addWidget(self.name_label)
        self.live_badge = pill("计时中", "green")
        self.missing_badge = pill("文件缺失", "amber")
        title_row.addWidget(self.live_badge)
        title_row.addWidget(self.missing_badge)
        title_row.addStretch(1)
        info.addLayout(title_row)
        self.path_label = QLabel("")
        self.path_label.setProperty("role", "muted")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info.addWidget(self.path_label)
        self.notes_label = QLabel("")
        self.notes_label.setProperty("role", "body")
        self.notes_label.setWordWrap(True)
        info.addWidget(self.notes_label)
        header.addLayout(info, 1)
        close_button = QPushButton()
        close_button.setObjectName("WindowButton")
        close_button.setFixedSize(30, 30)
        close_button.setIcon(icon("close", COLORS["muted"], 16))
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setToolTip("关闭")
        close_button.clicked.connect(self.close)
        header.addWidget(close_button, 0, Qt.AlignmentFlag.AlignTop)
        self.body.addLayout(header)

        # 缺失提示
        self.missing_banner = QFrame()
        self.missing_banner.setStyleSheet(
            "background: #2E2517; border: 1px solid #4A3A21; border-radius: 12px;"
        )
        banner_layout = QHBoxLayout(self.missing_banner)
        banner_layout.setContentsMargins(14, 11, 14, 11)
        banner_layout.setSpacing(10)
        alert = QLabel()
        alert.setPixmap(pixmap("alert", COLORS["amber"], 17))
        banner_layout.addWidget(alert)
        text = QLabel(
            "游戏程序已被移动或卸载。游时仍保留名称、图标和全部时长记录，不会用问号占位，也不会丢失历史。"
        )
        text.setStyleSheet("color: #E9C37E; font-size: 12px; border: none; background: transparent;")
        text.setWordWrap(True)
        banner_layout.addWidget(text, 1)
        relocate = QPushButton("重新定位")
        relocate.setStyleSheet(
            "QPushButton { background: #3C2F1C; border: 1px solid #5D4723; color: #F3C66D; "
            "border-radius: 8px; padding: 6px 11px; font-size: 11px; }"
            "QPushButton:hover { background: #4A3A22; }"
        )
        relocate.setCursor(Qt.CursorShape.PointingHandCursor)
        relocate.clicked.connect(self._relocate)
        banner_layout.addWidget(relocate)
        self.missing_banner.hide()
        self.body.addWidget(self.missing_banner)

        # 操作
        actions = QHBoxLayout()
        actions.setSpacing(9)
        self.launch_button = QPushButton("启动游戏")
        self.launch_button.setProperty("variant", "primary")
        self.launch_button.setIcon(icon("play", "#FFFFFF", 15))
        self.launch_button.setMinimumHeight(37)
        self.launch_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launch_button.clicked.connect(self._launch)
        self.manual_button = QPushButton("开始手动计时")
        self.manual_button.setProperty("variant", "soft")
        self.manual_button.setIcon(icon("clock", COLORS["text_soft"], 15))
        self.manual_button.setMinimumHeight(37)
        self.manual_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.manual_button.clicked.connect(self._toggle_manual)
        actions.addWidget(self.launch_button)
        actions.addWidget(self.manual_button)
        actions.addStretch(1)
        edit_button = SmallButton("编辑", "edit", variant="ghost")
        edit_button.clicked.connect(self._edit)
        delete_button = SmallButton("移除", "trash", variant="ghost")
        delete_button.setStyleSheet(
            f"QPushButton {{ color: {COLORS['red']}; background: transparent; border: none; "
            f"padding: 7px 10px; }} QPushButton:hover {{ background: {COLORS['red_soft']}; }}"
        )
        delete_button.clicked.connect(self._delete)
        actions.addWidget(edit_button)
        actions.addWidget(delete_button)
        self.body.addLayout(actions)

        # 统计
        stats_row = QHBoxLayout()
        stats_row.setSpacing(11)
        self.total_stat = self._mini_stat("总时长", "0 分钟", "clock")
        self.sessions_stat = self._mini_stat("对局", "0 局", "gamepad")
        self.week_stat = self._mini_stat("近 7 天", "0 分钟", "chart")
        self.last_stat = self._mini_stat("上次游玩", "从未", "calendar")
        for card in (self.total_stat, self.sessions_stat, self.week_stat, self.last_stat):
            stats_row.addWidget(card, 1)
        self.body.addLayout(stats_row)

        # 图表
        chart_card = CardFrame()
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(18, 15, 18, 12)
        chart_layout.setSpacing(4)
        chart_header = QHBoxLayout()
        chart_title = QLabel("近 7 天")
        chart_title.setProperty("role", "h3")
        chart_header.addWidget(chart_title)
        chart_header.addStretch(1)
        chart_note = QLabel("按本次游戏统计")
        chart_note.setProperty("role", "faint")
        chart_header.addWidget(chart_note)
        chart_layout.addLayout(chart_header)
        self.chart = BarChart()
        self.chart.setMinimumHeight(154)
        chart_layout.addWidget(self.chart)
        self.body.addWidget(chart_card)

        # 最近记录
        sessions_card = CardFrame()
        sessions_layout = QVBoxLayout(sessions_card)
        sessions_layout.setContentsMargins(18, 14, 18, 12)
        sessions_layout.setSpacing(0)
        heading = QHBoxLayout()
        label = QLabel("最近记录")
        label.setProperty("role", "h3")
        heading.addWidget(label)
        heading.addStretch(1)
        self.session_count_label = QLabel("")
        self.session_count_label.setProperty("role", "faint")
        heading.addWidget(self.session_count_label)
        sessions_layout.addLayout(heading)
        sessions_layout.addSpacing(4)
        self.sessions_holder = QVBoxLayout()
        self.sessions_holder.setSpacing(0)
        sessions_layout.addLayout(self.sessions_holder)
        self.body.addWidget(sessions_card)
        self.body.addStretch(1)

        footer = QHBoxLayout()
        footer.setContentsMargins(28, 12, 28, 16)
        hint = QLabel("关闭此窗口不会停止计时，游时会在托盘继续记录。")
        hint.setProperty("role", "faint")
        footer.addWidget(hint)
        footer.addStretch(1)
        done = SmallButton("完成", variant="primary")
        done.clicked.connect(self.accept)
        footer.addWidget(done)
        root.addLayout(footer)

    @staticmethod
    def _mini_stat(title: str, value: str, icon_name: str) -> QFrame:
        card = CardFrame(soft=True)
        card.setMinimumHeight(76)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(13, 10, 13, 10)
        layout.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(6)
        badge = QLabel()
        badge.setPixmap(pixmap(icon_name, COLORS["muted"], 13))
        top.addWidget(badge)
        label = QLabel(title)
        label.setProperty("role", "faint")
        top.addWidget(label)
        top.addStretch(1)
        layout.addLayout(top)
        value_label = QLabel(value)
        value_label.setProperty("role", "number-sm")
        value_label.setObjectName("Value")
        layout.addWidget(value_label)
        return card

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        apply_dark_title_bar(int(self.winId()))

    # ------------------------------------------------------------------- state
    def refresh(self) -> None:
        try:
            self._game = self.library.get_game(self.game_id)
        except GameNotFoundError:
            self.close()
            return
        game = self._game
        summary = self.library.summary(self.game_id)
        self.setWindowTitle(f"{game.name} · 游时")
        self.name_label.setText(game.name)
        self.path_label.setText(game.exe_path)
        self.notes_label.setText(game.notes)
        self.notes_label.setVisible(bool(game.notes))
        self.game_icon.set_game(game, self.library.icon_path(game))
        self.missing_badge.setVisible(summary.missing)
        self.missing_banner.setVisible(summary.missing)
        self.launch_button.setText("重新定位游戏" if summary.missing else "启动游戏")
        self.launch_button.setIcon(icon("folder" if summary.missing else "play", "#FFFFFF", 15))

        active = self.tracker.is_active(self.game_id)
        source = self.tracker.active_source(self.game_id)
        self.live_badge.setVisible(active)
        if active:
            elapsed = self.tracker.live_elapsed(self.game_id)
            self.live_badge.setText(
                f"{'自动' if source == 'auto' else '手动'} · {format_duration(elapsed, zero='刚刚')}"
            )
        self.manual_button.setEnabled(not summary.missing or active)
        if source == "manual":
            self.manual_button.setText("结束手动计时")
            self.manual_button.setIcon(icon("stop", COLORS["red"], 14))
        elif source == "auto":
            self.manual_button.setText("自动计时中")
            self.manual_button.setIcon(icon("clock", COLORS["green"], 14))
            self.manual_button.setEnabled(False)
        else:
            self.manual_button.setText("开始手动计时")
            self.manual_button.setIcon(icon("clock", COLORS["text_soft"], 15))

        self.total_stat.findChild(QLabel, "Value").setText(
            format_duration(summary.total_seconds, zero="尚未计时")
        )
        self.sessions_stat.findChild(QLabel, "Value").setText(f"{summary.session_count} 局")
        daily = self.stats.daily_seconds(7, game_id=self.game_id)
        self.week_stat.findChild(QLabel, "Value").setText(
            format_duration(sum(duration for _, duration in daily), zero="0 分钟")
        )
        self.last_stat.findChild(QLabel, "Value").setText(format_last_played(summary.last_played_at))
        self._fill_chart()
        self._fill_sessions()

    def refresh_live(self) -> None:
        if not self.isVisible() or not self._game:
            return
        source = self.tracker.active_source(self.game_id)
        active = source is not None
        if self.live_badge.isVisible() != active:
            self.refresh()
            return
        if active:
            elapsed = self.tracker.live_elapsed(self.game_id)
            self.live_badge.setText(
                f"{'自动' if source == 'auto' else '手动'} · {format_duration(elapsed, zero='刚刚')}"
            )

    def _fill_chart(self) -> None:
        if not self._game:
            return
        daily = self.stats.daily_seconds(7, game_id=self.game_id)
        from .formatting import WEEKDAYS
        from datetime import date

        values = []
        for day_string, seconds in daily:
            day = date.fromisoformat(day_string)
            values.append((WEEKDAYS[day.weekday()], seconds))
        self.chart.set_accent(self._game.accent)
        self.chart.set_data(values)

    def _fill_sessions(self) -> None:
        while self.sessions_holder.count():
            item = self.sessions_holder.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        sessions = self.stats.sessions_for_game(self.game_id, 9)
        self.session_count_label.setText(f"共 {len(sessions)} 条（最近）")
        if not sessions:
            empty = QLabel("还没有记录，启动游戏后会自动开始计时。")
            empty.setProperty("role", "muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumHeight(60)
            self.sessions_holder.addWidget(empty)
            return
        for index, session in enumerate(sessions):
            if index:
                self.sessions_holder.addWidget(Separator())
            self.sessions_holder.addWidget(
                SessionRow(
                    session.started_at,
                    session.ended_at if not session.is_active else None,
                    self.tracker.live_elapsed(self.game_id)
                    if session.is_active
                    else session.duration_seconds,
                    session.source,
                )
            )

    # ----------------------------------------------------------------- actions
    def _launch(self) -> None:
        if not self._game:
            return
        if not self._game.path_exists:
            self._relocate()
            return
        result = self.launcher.launch(self._game)
        if not result.ok:
            self._notify_error(result.error)
            return
        self.launch_button.setText("等待进程启动…")
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._launch_settled)
        timer.timeout.connect(self.dataChanged.emit)
        timer.start(1500)

    def _launch_settled(self) -> None:
        if self._game:
            self.launch_button.setText("启动游戏")
            self.refresh()

    def _toggle_manual(self) -> None:
        try:
            if self.tracker.active_source(self.game_id) == "manual":
                self.tracker.stop_manual(self.game_id)
            else:
                self.tracker.start_manual(self.game_id)
        except SessionConflictError as exc:
            self._notify_error(str(exc))
            return
        self.refresh()
        self.dataChanged.emit()

    def _edit(self) -> None:
        if not self._game:
            return
        dialog = AddGameDialog(self.library, self.icons, game=self._game, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_game:
            self.refresh()
            self.dataChanged.emit()

    def _relocate(self) -> None:
        if not self._game:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "重新定位游戏程序",
            str(Path(self._game.exe_path).parent) if Path(self._game.exe_path).parent.is_dir() else "",
            "Windows 程序 (*.exe)",
        )
        if not path:
            return
        try:
            self.library.relocate_game(self.game_id, path)
        except (GameValidationError, DuplicateGameError, GameNotFoundError) as exc:
            self._notify_error(str(exc))
            return
        self.refresh()
        self.dataChanged.emit()

    def _delete(self) -> None:
        if not self._game:
            return
        from .dialogs_confirm import ask_confirm

        if not ask_confirm(
            self,
            "移除游戏？",
            f"将从游戏库移除《{self._game.name}》，并删除它的全部计时记录。此操作不可撤销。",
            "移除游戏",
            danger=True,
        ):
            return
        if self.tracker.is_active(self.game_id):
            self.tracker.stop_game(self.game_id)
        game_id = self.game_id
        self.library.remove_game(game_id)
        self.deleted.emit(game_id)
        self.dataChanged.emit()
        self.accept()

    def _notify_error(self, message: str) -> None:
        from .dialogs_confirm import show_message

        show_message(self, "无法完成操作", message, danger=True)


class ConfirmDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        confirm_text: str = "确定",
        *,
        danger: bool = False,
        cancel_text: str = "取消",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ContentDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedWidth(430)
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 20)
        root.setSpacing(14)
        title_label = QLabel(title)
        title_label.setProperty("role", "h2")
        root.addWidget(title_label)
        body = QLabel(message)
        body.setProperty("role", "body")
        body.setWordWrap(True)
        body.setMinimumHeight(48)
        root.addWidget(body)
        root.addWidget(Separator())
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = SmallButton(cancel_text, variant="ghost")
        cancel.clicked.connect(self.reject)
        confirm = QPushButton(confirm_text)
        confirm.setProperty("variant", "dangerSolid" if danger else "primary")
        confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm.setMinimumHeight(35)
        confirm.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)
        root.addLayout(buttons)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        apply_dark_title_bar(int(self.winId()))
