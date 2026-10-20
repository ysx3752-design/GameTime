"""扫描游戏对话框：按需扫描平台与目录，用户确认后再加入游戏库。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..services.icons import accent_for, letter_pixmap
from ..services.library import DuplicateGameError, GameService
from ..services.scanner import ScanResult, ScanThread
from ..windows import apply_dark_title_bar, normalize_windows_path
from .icons import pixmap
from .theme import COLORS, is_dark_active, rgba
from .widgets import ElidedLabel, Separator, SmallButton, pill

_ORPHAN_SCAN_THREADS: set[ScanThread] = set()


class _ScanCheckBox(QCheckBox):
    """带清晰勾选标记的复选框，避免纯色方块难以辨认。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(1, 1, 18, 18)
        if not self.isEnabled():
            fill = QColor(COLORS["surface_3"])
            border = QColor(COLORS["border"])
        elif self.isChecked():
            fill = QColor(COLORS["accent"])
            border = QColor(COLORS["accent"])
        else:
            fill = QColor(COLORS["surface"])
            border = QColor(COLORS["border"])
        painter.setPen(QPen(border, 1.4))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 5, 5)
        if self.isChecked():
            pen = QPen(QColor("#FFFFFF"), 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(5.5, 10.2)
            path.lineTo(8.7, 13.2)
            path.lineTo(14.8, 6.7)
            painter.drawPath(path)
        painter.end()


class _ScanPreviewIcon(QWidget):
    def __init__(self, size: int = 40) -> None:
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
        path.addRoundedRect(0, 0, self._size, self._size, 10, 10)
        painter.setClipPath(path)
        scaled = self._pixmap.scaled(
            self._size,
            self._size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(1.0)
        painter.drawPixmap(0, 0, scaled)
        painter.end()


class _ScanResultRow(QFrame):
    def __init__(self, result: ScanResult, library: GameService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.result = result
        self.setProperty("card", "soft")
        self.setMinimumHeight(64)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(10)

        self.checkbox = _ScanCheckBox()
        self.checkbox.setChecked(not result.already_added)
        self.checkbox.setEnabled(not result.already_added)
        layout.addWidget(self.checkbox)

        preview = _ScanPreviewIcon(40)
        accent = accent_for(result.display_name, result.exe_path)
        cached = None
        existing_game = library.db.find_game_by_path(result.exe_path)
        if existing_game is not None:
            cached = library.icon_path(existing_game)
        if cached is not None:
            pixmap_value = QPixmap(str(cached))
        else:
            qicon = library.icons.icon_for_file(result.exe_path, result.display_name, accent)
            pixmap_value = qicon.pixmap(QSize(128, 128))
        if pixmap_value.isNull():
            pixmap_value = letter_pixmap(result.display_name, accent, 128)
        preview.set_pixmap(pixmap_value)
        layout.addWidget(preview)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)
        self.name_label = ElidedLabel(result.display_name, Qt.TextElideMode.ElideRight)
        self.name_label.setProperty("role", "h3")
        text_col.addWidget(self.name_label)
        self.path_label = ElidedLabel(result.exe_path, Qt.TextElideMode.ElideMiddle)
        self.path_label.setProperty("role", "faint")
        text_col.addWidget(self.path_label)
        layout.addLayout(text_col, 1)

        source = pill(result.source, "purple" if result.source in {"Steam", "Epic"} else "neutral")
        layout.addWidget(source)
        if result.already_added:
            layout.addWidget(pill("已添加", "neutral"))
            self.checkbox.setChecked(False)
            self.name_label.setStyleSheet(f"color: {COLORS['faint']};")


class ScanGamesDialog(QDialog):
    """扫描 Steam / Epic / 常见 Games 目录，勾选后批量加入。"""

    scanFinished = Signal(int)

    def __init__(
        self,
        library: GameService,
        *,
        parent: QWidget | None = None,
        auto_start: bool = True,
        initial_results: list[ScanResult] | None = None,
        custom_dirs: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.library = library
        self._rows: list[_ScanResultRow] = []
        self._thread: ScanThread | None = None
        self._custom_dirs = list(custom_dirs or [])
        self._scan_done = False
        self.added_count = 0

        self.setObjectName("ContentDialog")
        self.setWindowTitle("扫描游戏 · 游时")
        self.setModal(True)
        self.setMinimumSize(780, 620)
        self.resize(800, 640)
        self._build()
        self._update_custom_label()
        if initial_results is not None:
            self._on_results(initial_results)
        elif auto_start:
            self._start_scan()
        else:
            self._on_results([])

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(26, 22, 26, 14)
        header_layout.setSpacing(10)
        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        badge = QLabel()
        badge.setFixedSize(40, 40)
        badge.setPixmap(pixmap("scan", COLORS["accent"], 21))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {COLORS['accent_soft']}; border: 1px solid {rgba(COLORS['accent'], 60)}; "
            "border-radius: 12px;"
        )
        title_row.addWidget(badge)
        title_text = QVBoxLayout()
        title_text.setSpacing(3)
        heading = QLabel("扫描游戏")
        heading.setProperty("role", "h1")
        desc = QLabel(
            "扫描 Steam、Epic、常见 Games 文件夹以及所有本地磁盘，找到可能的游戏。"
            "扫描结果不会自动加入，需要你勾选确认。"
        )
        desc.setProperty("role", "muted")
        desc.setWordWrap(True)
        title_text.addWidget(heading)
        title_text.addWidget(desc)
        title_row.addLayout(title_text, 1)
        header_layout.addLayout(title_row)

        sources = QHBoxLayout()
        sources.setSpacing(6)
        sources.addWidget(pill("Steam", "purple"))
        sources.addWidget(pill("Epic", "purple"))
        sources.addWidget(pill("Games 文件夹", "neutral"))
        sources.addWidget(pill("自定义目录", "neutral"))
        sources.addStretch(1)
        header_layout.addLayout(sources)

        scope_row = QHBoxLayout()
        scope_row.setSpacing(9)
        self.full_scan_button = QPushButton("全盘扫描所有本地磁盘")
        self.full_scan_button.setCheckable(True)
        self.full_scan_button.setChecked(True)
        self.full_scan_button.setProperty("scope", "true")
        self.full_scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.full_scan_button.setToolTip("遍历所有本地固定磁盘；可发现自定义安装目录，耗时可能较长")
        scope_row.addWidget(self.full_scan_button)
        scope_hint = QLabel("默认开启，可发现自定义安装目录；取消勾选后仅扫描平台与常见目录，速度更快。")
        scope_hint.setProperty("role", "faint")
        scope_hint.setWordWrap(True)
        scope_row.addWidget(scope_hint, 1)
        header_layout.addLayout(scope_row)

        self.progress_frame = QFrame()
        self.progress_frame.setStyleSheet(
            f"QFrame {{ background: {COLORS['surface_2']}; border: 1px solid {COLORS['border_soft']}; "
            "border-radius: 10px; }"
        )
        progress_layout = QHBoxLayout(self.progress_frame)
        progress_layout.setContentsMargins(12, 8, 12, 8)
        progress_layout.setSpacing(8)
        self.progress_dot = QLabel()
        self.progress_dot.setFixedSize(7, 7)
        self.progress_dot.setStyleSheet(f"background: {COLORS['accent']}; border-radius: 3px;")
        progress_layout.addWidget(self.progress_dot)
        self.progress_label = QLabel("准备扫描…")
        self.progress_label.setProperty("role", "muted")
        self.progress_label.setStyleSheet(
            "font-size: 11px; border: none; background: transparent;"
        )
        progress_layout.addWidget(self.progress_label, 1)
        self.found_count_label = QLabel("已找到 0 个")
        self.found_count_label.setProperty("role", "faint")
        self.found_count_label.setStyleSheet(
            "font-size: 11px; border: none; background: transparent;"
        )
        progress_layout.addWidget(self.found_count_label)
        header_layout.addWidget(self.progress_frame)
        root.addWidget(header)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(26, 4, 26, 6)
        toolbar.setSpacing(8)
        custom_button = SmallButton("添加文件夹…", "folder", variant="ghost")
        custom_button.clicked.connect(self._choose_folder)
        toolbar.addWidget(custom_button)
        self.custom_label = QLabel("")
        self.custom_label.setProperty("role", "faint")
        toolbar.addWidget(self.custom_label)
        toolbar.addStretch(1)
        self.rescan_button = SmallButton("重新扫描", "refresh", variant="ghost")
        self.rescan_button.clicked.connect(self._start_scan)
        toolbar.addWidget(self.rescan_button)
        root.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_widget = QWidget()
        self._list_widget.setObjectName("ScrollContent")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(20, 2, 20, 6)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch(1)
        scroll.setWidget(self._list_widget)
        self._scroll = scroll
        root.addWidget(scroll, 1)

        self.empty_label = QLabel("正在准备扫描…")
        self.empty_label.setProperty("role", "muted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setMinimumHeight(160)
        self._list_layout.insertWidget(0, self.empty_label)

        root.addWidget(Separator())
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(26, 12, 26, 16)
        footer_layout.setSpacing(10)
        self.select_all_button = SmallButton("全选", variant="ghost")
        self.select_all_button.clicked.connect(self._toggle_select_all)
        footer_layout.addWidget(self.select_all_button)
        self.status_label = QLabel("")
        self.status_label.setProperty("role", "muted")
        footer_layout.addWidget(self.status_label)
        footer_layout.addStretch(1)
        cancel = SmallButton("关闭", variant="ghost")
        cancel.clicked.connect(self.reject)
        footer_layout.addWidget(cancel)
        self.add_button = SmallButton("添加选中游戏", "plus", variant="primary")
        self.add_button.setMinimumHeight(37)
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self._add_selected)
        footer_layout.addWidget(self.add_button)
        root.addWidget(footer)
        self._update_status()

    # ------------------------------------------------------------------- scan
    def _start_scan(self) -> None:
        self._stop_thread()
        self._clear_rows()
        self._scan_done = False
        self.empty_label.setText("正在扫描 Steam、Epic 与常见游戏目录…")
        self.empty_label.show()
        self.progress_dot.setStyleSheet(f"background: {COLORS['accent']}; border-radius: 3px;")
        self.progress_label.setText(
            "正在全盘扫描所有本地磁盘…" if self.full_scan_button.isChecked() else "正在扫描…"
        )
        self.found_count_label.setText("已找到 0 个")
        self.rescan_button.setEnabled(False)
        self.add_button.setEnabled(False)

        existing = {normalize_windows_path(item.game.exe_path) for item in self.library.list_games()}
        self._thread = ScanThread(
            existing,
            custom_dirs=self._custom_dirs,
            full_scan=self.full_scan_button.isChecked(),
            parent=self,
        )
        self._thread.progress.connect(self._on_progress)
        self._thread.results_ready.connect(self._on_results)
        self._thread.failed.connect(self._on_failed)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def _stop_thread(self) -> None:
        thread = self._thread
        self._thread = None
        if thread is None:
            return
        for signal, slot in (
            (thread.progress, self._on_progress),
            (thread.results_ready, self._on_results),
            (thread.failed, self._on_failed),
            (thread.finished, self._on_thread_finished),
        ):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        if thread.isRunning():
            thread.stop()
        if thread.isRunning():
            # 极端情况下扫描目录过大，保留线程对象直到它自然结束，避免销毁运行中的 QThread。
            thread.setParent(None)
            _ORPHAN_SCAN_THREADS.add(thread)
            thread.finished.connect(lambda t=thread: _ORPHAN_SCAN_THREADS.discard(t))
            thread.finished.connect(thread.deleteLater)
        else:
            thread.deleteLater()

    def _on_thread_finished(self) -> None:
        thread = self.sender()
        if self._thread is thread:
            self._thread = None
        if isinstance(thread, ScanThread):
            thread.deleteLater()

    def _on_progress(self, directory: str) -> None:
        display = directory
        if len(display) > 62:
            display = display[:18] + "…" + display[-41:]
        self.progress_label.setText(f"正在扫描：{display}")

    def _on_failed(self, message: str) -> None:
        self._scan_done = True
        self.progress_dot.setStyleSheet(f"background: {COLORS['red']}; border-radius: 3px;")
        self.progress_label.setText(f"扫描失败：{message}")
        self.empty_label.setText("扫描未完成，可以点击“重新扫描”重试。")
        self.empty_label.show()
        self.rescan_button.setEnabled(True)

    def _on_results(self, results: list[ScanResult]) -> None:
        self._scan_done = True
        self.rescan_button.setEnabled(True)
        self._clear_rows()
        if not results:
            self.progress_dot.setStyleSheet(f"background: {COLORS['amber']}; border-radius: 3px;")
            self.progress_label.setText("扫描完成，未找到可添加的游戏")
            self.empty_label.setText(
                "没有找到新的游戏。\n可以点击“添加文件夹…”选择自定义游戏目录后重新扫描。"
            )
            self.empty_label.show()
        else:
            self.progress_dot.setStyleSheet(f"background: {COLORS['green']}; border-radius: 3px;")
            self.progress_label.setText("扫描完成")
            self.empty_label.hide()
            for result in results:
                row = _ScanResultRow(result, self.library, self._list_widget)
                row.checkbox.stateChanged.connect(lambda _: self._update_status())
                insert_index = self._list_layout.count() - 1
                self._list_layout.insertWidget(insert_index, row)
                self._rows.append(row)
            self.found_count_label.setText(f"已找到 {len(self._rows)} 个")
        self._update_status()

    def _clear_rows(self) -> None:
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()
        self.found_count_label.setText("已找到 0 个")

    def _choose_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择游戏文件夹", str(Path.home()))
        if not directory:
            return
        if normalize_windows_path(directory) not in {
            normalize_windows_path(value) for value in self._custom_dirs
        }:
            self._custom_dirs.append(directory)
        self._update_custom_label()
        self._start_scan()

    def _update_custom_label(self) -> None:
        if not self._custom_dirs:
            self.custom_label.setText("")
        else:
            self.custom_label.setText(f"已添加 {len(self._custom_dirs)} 个自定义目录")

    # --------------------------------------------------------------- selection
    def _toggle_select_all(self) -> None:
        checkable = [row for row in self._rows if not row.result.already_added]
        if not checkable:
            return
        all_checked = all(row.checkbox.isChecked() for row in checkable)
        for row in checkable:
            row.checkbox.setChecked(not all_checked)
        self._update_status()

    def _update_status(self) -> None:
        selected = sum(
            1 for row in self._rows if row.checkbox.isChecked() and not row.result.already_added
        )
        total = sum(1 for row in self._rows if not row.result.already_added)
        self.status_label.setText(f"已选 {selected}/{total} 个候选")
        self.add_button.setEnabled(selected > 0 and self._scan_done)
        checkable = [row for row in self._rows if not row.result.already_added]
        if checkable and all(row.checkbox.isChecked() for row in checkable):
            self.select_all_button.setText("取消全选")
        else:
            self.select_all_button.setText("全选")
        self.select_all_button.setEnabled(bool(checkable))

    def _add_selected(self) -> None:
        added = 0
        errors: list[str] = []
        for row in self._rows:
            if not row.checkbox.isChecked() or row.result.already_added:
                continue
            try:
                self.library.add_game(row.result.display_name, row.result.exe_path)
                added += 1
                row.result.already_added = True
                row.checkbox.setChecked(False)
                row.checkbox.setEnabled(False)
            except DuplicateGameError:
                row.result.already_added = True
                row.checkbox.setChecked(False)
                row.checkbox.setEnabled(False)
            except Exception as exc:
                errors.append(f"{row.result.display_name}: {exc}")
        self.added_count += added
        self._update_status()
        if errors:
            from .dialogs_confirm import show_message

            show_message(
                self,
                "部分游戏未添加",
                "以下游戏无法加入：\n" + "\n".join(errors[:6]),
                danger=True,
            )
        if added > 0:
            self.scanFinished.emit(added)
            self.accept()

    # ------------------------------------------------------------------ window
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        apply_dark_title_bar(int(self.winId()), dark=is_dark_active())

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stop_thread()
        super().closeEvent(event)

    def reject(self) -> None:
        self._stop_thread()
        super().reject()
