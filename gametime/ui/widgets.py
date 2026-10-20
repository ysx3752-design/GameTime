"""自绘与组合控件。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..models import Game, GameSummary
from .formatting import format_duration, format_last_played
from .icons import icon, pixmap
from .theme import COLORS, rgba
from ..services.icons import letter_pixmap


# --------------------------------------------------------------------------- base
class CardFrame(QFrame):
    def __init__(self, parent: QWidget | None = None, *, soft: bool = False) -> None:
        super().__init__(parent)
        self.setProperty("card", "soft" if soft else "true")


class ElidedLabel(QLabel):
    """根据当前宽度省略中间路径或长文本。"""

    def __init__(self, text: str = "", mode: Qt.TextElideMode = Qt.TextElideMode.ElideMiddle) -> None:
        super().__init__(text)
        self._full_text = text
        self._mode = mode
        self.setToolTip(text)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def setText(self, text: str) -> None:  # noqa: N802
        self._full_text = text
        self.setToolTip(text)
        super().setText(text)
        self._update_elide()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_elide()

    def _update_elide(self) -> None:
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(self._full_text, self._mode, max(10, self.width() - 2))
        super().setText(elided)


class Separator(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Divider")
        self.setFixedHeight(1)


def pill(text: str, kind: str = "neutral") -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "pill")
    label.setProperty("pill", kind)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return label


class SmallButton(QPushButton):
    def __init__(self, text: str, icon_name: str | None = None, *, variant: str = "soft") -> None:
        super().__init__(text)
        self.setProperty("variant", variant)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(34)
        if icon_name:
            icon_color = "#FFFFFF" if variant in {"primary", "dangerSolid"} else COLORS["text_soft"]
            self.setIcon(icon(icon_name, icon_color, 16))
            self.setIconSize(QSize(16, 16))


class IconButton(QPushButton):
    def __init__(
        self,
        icon_name: str,
        *,
        color: str = COLORS["text_soft"],
        diameter: int = 36,
        tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._color = color
        self.setObjectName("IconButton")
        self.setFixedSize(diameter, diameter)
        self.setIcon(icon(icon_name, color, max(14, diameter // 2)))
        self.setIconSize(QSize(max(14, diameter // 2), max(14, diameter // 2)))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)

    def set_icon(self, name: str, color: str | None = None) -> None:
        self._icon_name = name
        if color:
            self._color = color
        self.setIcon(icon(name, self._color, max(14, self.width() // 2)))
        self.update()

    def set_color(self, color: str) -> None:
        self.set_icon(self._icon_name, color)


class NavButton(QPushButton):
    def __init__(self, text: str, icon_name: str) -> None:
        super().__init__(text)
        self._icon_name = icon_name
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(43)
        self.setIconSize(QSize(19, 19))
        self.toggled.connect(self._sync_icon)
        self._sync_icon(False)

    def _sync_icon(self, checked: bool) -> None:
        color = COLORS["accent"] if checked else COLORS["muted"]
        self.setIcon(icon(self._icon_name, color, 19))


class ToggleSwitch(QAbstractButton):
    """无文字的开关，避免系统原生 checkbox 破坏视觉。"""

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(42, 24)
        self._offset = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        track = QRectF(0, 2, 42, 20)
        if self.isChecked():
            gradient = QLinearGradient(track.topLeft(), track.topRight())
            base = QColor(COLORS["accent"])
            gradient.setColorAt(0, base.darker(112))
            gradient.setColorAt(1, base.lighter(108))
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
        else:
            painter.setBrush(QColor(COLORS["surface_3"]))
            painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawRoundedRect(track, 10, 10)
        knob_x = 4 + self._offset * 20
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(
            QColor("#FFFFFF") if self.isChecked() else QColor(COLORS["muted"])
        )
        painter.drawEllipse(QRectF(knob_x, 4, 16, 16))
        painter.end()


class ToggleRow(QWidget):
    changed = Signal(bool)

    def __init__(
        self,
        title: str,
        description: str,
        checked: bool,
        *,
        icon_name: str | None = None,
    ) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        if icon_name:
            badge = QLabel()
            badge.setFixedSize(34, 34)
            badge.setPixmap(pixmap(icon_name, COLORS["muted"], 17))
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(f"background: {COLORS['surface_3']}; border-radius: 9px;")
            layout.addWidget(badge)
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)
        title_label = QLabel(title)
        title_label.setProperty("role", "h3")
        desc = QLabel(description)
        desc.setProperty("role", "muted")
        desc.setWordWrap(True)
        text_layout.addWidget(title_label)
        text_layout.addWidget(desc)
        layout.addLayout(text_layout, 1)
        self.switch = ToggleSwitch(checked)
        self.switch.toggled.connect(self.changed.emit)
        layout.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)


class SoftComboBox(QComboBox):
    """QComboBox 的深色版本，自绘下拉箭头，避免平台样式缺失。"""

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        arrow = pixmap("chevron-down", COLORS["muted"], 12)
        painter.drawPixmap(
            self.width() - 24,
            (self.height() - 12) // 2,
            arrow,
        )
        painter.end()


class ThemeSelector(QWidget):
    """深色 / 浅色 / 跟随系统 三选一。"""

    changed = Signal(str)
    OPTIONS = (
        ("dark", "深色", "低光环境", "moon"),
        ("light", "浅色", "明亮清晰", "sun"),
        ("system", "跟随系统", "随 Windows 切换", "monitor"),
    )

    def __init__(self, current: str = "dark") -> None:
        super().__init__()
        self._current = current
        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        for index, (mode, title, description, icon_name) in enumerate(self.OPTIONS):
            button = QPushButton(f"{title}\n{description}")
            button.setCheckable(True)
            button.setProperty("themeChoice", "true")
            button.setProperty("themeMode", mode)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(64)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setIconSize(QSize(19, 19))
            self._group.addButton(button, index)
            self._buttons[mode] = button
            button.toggled.connect(lambda checked, m=mode: self._sync_icon(m, checked))
            layout.addWidget(button, 1)
        self._group.idClicked.connect(self._on_clicked)
        self.set_current(current)

    def _on_clicked(self, index: int) -> None:
        mode = self.OPTIONS[index][0]
        self._current = mode
        self._sync_all_icons()
        self.changed.emit(mode)

    def _sync_icon(self, mode: str, checked: bool) -> None:
        button = self._buttons.get(mode)
        if button is None:
            return
        icon_name = next(option[3] for option in self.OPTIONS if option[0] == mode)
        button.setIcon(icon(icon_name, COLORS["accent"] if checked else COLORS["muted"], 19))

    def _sync_all_icons(self) -> None:
        for mode, button in self._buttons.items():
            self._sync_icon(mode, button.isChecked())

    def set_current(self, mode: str) -> None:
        if mode not in self._buttons:
            mode = "dark"
        self._current = mode
        for button_mode, button in self._buttons.items():
            button.blockSignals(True)
            button.setChecked(button_mode == mode)
            button.blockSignals(False)
        self._sync_all_icons()

    def current_mode(self) -> str:
        return self._current


# --------------------------------------------------------------------------- icons
class GameIcon(QWidget):
    def __init__(self, size: int = 58, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = size
        self._pixmap: QPixmap | None = None
        self._game: Game | None = None
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_game(self, game: Game, icon_file: str | Path | None) -> None:
        self._game = game
        self._pixmap = None
        if icon_file:
            path = Path(icon_file)
            if path.is_file():
                loaded = QPixmap(str(path))
                if not loaded.isNull():
                    self._pixmap = loaded
        if self._pixmap is None:
            self._pixmap = letter_pixmap(game.name, game.accent, 256)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._pixmap is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        path = QPainterPath()
        radius = self._size * 0.27
        path.addRoundedRect(QRectF(0, 0, self._size, self._size), radius, radius)
        painter.setClipPath(path)
        scaled = self._pixmap.scaled(
            self._size,
            self._size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(1.0)
        x = (self._size - scaled.width()) / 2
        y = (self._size - scaled.height()) / 2
        painter.drawPixmap(QPointF(x, y), scaled)
        painter.end()


# --------------------------------------------------------------------------- layout
class FlowLayout(QLayout):
    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = 14) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self) -> None:
        while self.count():
            self.takeAt(0)

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientations:  # noqa: N802
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0
        for item in self._items:
            widget = item.widget()
            if widget is not None and widget.isHidden():
                continue
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


# --------------------------------------------------------------------------- charts
class BarChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._values: list[tuple[str, int]] = []
        self._accent = COLORS["accent"]
        self._hover = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(184)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, values: Sequence[tuple[str, int]]) -> None:
        self._values = list(values)
        self.update()

    def set_accent(self, color: str) -> None:
        self._accent = color
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(4, 8, -4, -2)
        labels_height = 26
        chart = QRectF(rect.left(), rect.top() + 16, rect.width(), rect.height() - labels_height - 16)
        max_value = max((value for _, value in self._values), default=0)
        if not self._values or max_value <= 0:
            painter.setPen(QColor(COLORS["faint"]))
            font = QFont("Microsoft YaHei UI")
            font.setPixelSize(12)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "还没有计时记录")
            painter.end()
            return

        # 横线
        painter.setPen(QPen(QColor(COLORS["border_soft"]), 1, Qt.PenStyle.DashLine))
        for step in range(1, 4):
            y = chart.bottom() - chart.height() * step / 4
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))

        count = len(self._values)
        slot = chart.width() / max(1, count)
        bar_width = min(30.0, slot * 0.46)
        painter.setFont(QFont("Microsoft YaHei UI", 9))
        for index, (label, value) in enumerate(self._values):
            cx = chart.left() + slot * (index + 0.5)
            ratio = value / max_value if max_value else 0
            height = max(3.0, (chart.height() - 8) * ratio) if value else 2.5
            bar = QRectF(cx - bar_width / 2, chart.bottom() - height, bar_width, height)
            if index == self._hover:
                top_color = QColor(self._accent).lighter(138)
                bottom_color = QColor(self._accent)
            elif index == count - 1:
                top_color = QColor(self._accent).lighter(124)
                bottom_color = QColor(self._accent).darker(102)
            else:
                top_color = QColor(self._accent).lighter(108)
                bottom_color = QColor(self._accent).darker(145)
            gradient = QLinearGradient(bar.topLeft(), bar.bottomLeft())
            gradient.setColorAt(0, top_color)
            gradient.setColorAt(1, bottom_color)
            path = QPainterPath()
            path.addRoundedRect(bar, min(6.0, bar_width / 2), min(6.0, bar_width / 2))
            painter.fillPath(path, gradient)
            painter.setPen(
                QColor(COLORS["muted"]) if index != count - 1 else QColor(COLORS["accent"])
            )
            painter.drawText(
                QRectF(cx - slot / 2, chart.bottom() + 7, slot, 18),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                label,
            )
        painter.end()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self._values:
            return
        rect = self.rect().adjusted(4, 8, -4, -2)
        chart_left = rect.left()
        slot = max(1.0, rect.width() / len(self._values))
        index = int((event.position().x() - chart_left) / slot)
        if 0 <= index < len(self._values):
            if index != self._hover:
                self._hover = index
                self.update()
            label, value = self._values[index]
            self.setToolTip(f"{label} · {format_duration(value, zero='0 分钟')}")
        else:
            self._hover = -1
            self.setToolTip("")
            self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = -1
        self.setToolTip("")
        self.update()


class RankBar(QWidget):
    def __init__(self, fraction: float, accent: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fraction = max(0.0, min(1.0, fraction))
        self._accent = accent
        self.setFixedHeight(6)
        self.setMinimumWidth(80)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS["surface_3"]))
        painter.drawRoundedRect(QRectF(0, 1, self.width(), 4), 2, 2)
        if self._fraction > 0:
            gradient = QLinearGradient(0, 0, self.width(), 0)
            gradient.setColorAt(0, QColor(self._accent).darker(125))
            gradient.setColorAt(1, QColor(self._accent))
            painter.setBrush(gradient)
            painter.drawRoundedRect(QRectF(0, 1, max(4.0, self.width() * self._fraction), 4), 2, 2)
        painter.end()


# --------------------------------------------------------------------------- cards
class StatCard(CardFrame):
    def __init__(
        self,
        title: str,
        value: str = "0 分钟",
        footnote: str = "",
        *,
        icon_name: str = "clock",
        accent: str = COLORS["accent"],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumHeight(116)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(8)
        badge = QLabel()
        badge.setFixedSize(28, 28)
        badge.setPixmap(pixmap(icon_name, accent, 15))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {rgba(accent, 32)}; border-radius: 8px;"
        )
        title_label = QLabel(title)
        title_label.setProperty("role", "muted")
        top.addWidget(badge)
        top.addWidget(title_label)
        top.addStretch(1)
        layout.addLayout(top)
        self.value_label = QLabel(value)
        self.value_label.setProperty("role", "number")
        layout.addWidget(self.value_label)
        self.footnote = QLabel(footnote)
        self.footnote.setProperty("role", "faint")
        layout.addWidget(self.footnote)

    def set_value(self, value: str, footnote: str | None = None) -> None:
        self.value_label.setText(value)
        if footnote is not None:
            self.footnote.setText(footnote)


class GameCard(QFrame):
    clicked = Signal(int)
    action_requested = Signal(int)

    def __init__(
        self,
        summary: GameSummary,
        icon_service,
        *,
        width: int = 330,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.summary = summary
        self._game = summary.game
        self._icon_service = icon_service
        self._active = False
        self._source: str | None = None
        self._elapsed = 0
        self.setObjectName("GameCard")
        self.setFixedSize(width, 162)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        if summary.missing:
            self.setProperty("missing", "true")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 15, 16, 13)
        layout.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(11)
        self.icon_widget = GameIcon(56)
        self.icon_widget.set_game(self._game, icon_service.icon_path(self._game))
        top.addWidget(self.icon_widget)
        info = QVBoxLayout()
        info.setSpacing(4)
        info.setContentsMargins(0, 1, 0, 0)
        name = ElidedLabel(self._game.name, Qt.TextElideMode.ElideRight)
        name.setProperty("role", "h3")
        name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.name_label = name
        self.sub_label = QLabel()
        self.sub_label.setProperty("role", "muted")
        self.sub_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        info.addWidget(name)
        info.addWidget(self.sub_label)
        info.addStretch(1)
        top.addLayout(info, 1)
        self.status = pill("", "neutral")
        self.status.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        top.addWidget(self.status, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        time_box = QVBoxLayout()
        time_box.setSpacing(0)
        self.total_label = QLabel(format_duration(summary.total_seconds, zero="尚未计时"))
        self.total_label.setProperty("role", "number-sm")
        self.total_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.count_label = QLabel(f"共 {summary.session_count} 局")
        self.count_label.setProperty("role", "faint")
        self.count_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        time_box.addWidget(self.total_label)
        time_box.addWidget(self.count_label)
        bottom.addLayout(time_box)
        bottom.addStretch(1)
        self.action_button = QPushButton()
        self.action_button.setObjectName("QuickButton")
        self.action_button.setFixedSize(36, 36)
        self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_button.setIcon(icon("play", "#FFFFFF", 17))
        self.action_button.setIconSize(QSize(17, 17))
        self.action_button.setToolTip("启动游戏并计时")
        self.action_button.clicked.connect(lambda: self.action_requested.emit(self._game.id))
        bottom.addWidget(self.action_button)
        layout.addLayout(bottom)
        self._refresh_static()

    def _refresh_static(self) -> None:
        if self.summary.missing:
            self.status.setText("文件缺失")
            self.status.setProperty("pill", "amber")
            self.status.show()
            self.sub_label.setText("历史记录已保留")
            self.action_button.setEnabled(False)
            self.action_button.setIcon(icon("alert", COLORS["amber"], 16))
            self.action_button.setToolTip("游戏文件已被移动或卸载。打开详情可重新定位。")
        elif self._active:
            self.status.setText("计时中")
            self.status.setProperty("pill", "green")
            self.status.show()
            self.sub_label.setText("正在自动计时" if self._source == "auto" else "手动计时")
        else:
            self.status.hide()
            self.sub_label.setText(format_last_played(self.summary.last_played_at))
        self._repolish(self.status)

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

    def set_live(self, active: bool, source: str | None, elapsed: int) -> None:
        self._active = active
        self._source = source
        self._elapsed = elapsed
        if self.summary.missing:
            return
        self.setProperty("active", "true" if active else "false")
        self._repolish(self)
        if active:
            self.status.setText("计时中")
            self.status.setProperty("pill", "green")
            self.status.show()
            self.sub_label.setText(
                f"{'自动识别' if source == 'auto' else '手动计时'} · {format_duration(elapsed, zero='刚刚')}"
            )
            if source == "manual":
                self.action_button.setProperty("active", "true")
                self.action_button.setIcon(icon("stop", COLORS["red"], 15))
                self.action_button.setToolTip("结束本次手动计时")
            else:
                self.action_button.setProperty("active", "false")
                self.action_button.setIcon(icon("clock", COLORS["green"], 17))
                self.action_button.setToolTip("正在自动计时；打开详情查看记录")
            self._repolish(self.action_button)
        else:
            self.status.hide()
            self.sub_label.setText(format_last_played(self.summary.last_played_at))
            self.action_button.setProperty("active", "false")
            self.action_button.setIcon(icon("play", "#FFFFFF", 17))
            self.action_button.setToolTip("启动游戏并计时")
            self._repolish(self.action_button)
        self._repolish(self.status)

    def refresh_summary(self, summary: GameSummary) -> None:
        self.summary = summary
        self.total_label.setText(format_duration(summary.total_seconds, zero="尚未计时"))
        self.count_label.setText(f"共 {summary.session_count} 局")

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self._game.id)
        super().mouseReleaseEvent(event)


class SessionRow(QWidget):
    def __init__(self, start: int, end: int | None, duration: int, source: str) -> None:
        super().__init__()
        from .formatting import format_session_range

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 9, 0, 9)
        layout.setSpacing(10)
        dot = QLabel()
        dot.setFixedSize(7, 7)
        color = COLORS["green"] if end is None else COLORS["faint"]
        dot.setStyleSheet(f"background: {color}; border-radius: 3px;")
        layout.addWidget(dot)
        when = QLabel(format_session_range(start, end))
        when.setProperty("role", "body")
        layout.addWidget(when, 1)
        badge = pill("进行中" if end is None else ("手动" if source == "manual" else "自动"), "green" if end is None else "neutral")
        layout.addWidget(badge)
        length = QLabel(format_duration(duration, zero="刚刚"))
        length.setProperty("role", "body")
        length.setMinimumWidth(78)
        length.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(length)


class EmptyState(QWidget):
    def __init__(
        self,
        title: str,
        description: str,
        button_text: str | None = None,
        icon_name: str = "gamepad",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 38, 24, 38)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        circle = QLabel()
        circle.setFixedSize(58, 58)
        circle.setPixmap(pixmap(icon_name, COLORS["accent"], 27))
        circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        circle.setStyleSheet(
            f"background: {COLORS['accent_soft']}; "
            f"border: 1px solid {rgba(COLORS['accent'], 55)}; border-radius: 18px;"
        )
        layout.addWidget(circle, 0, Qt.AlignmentFlag.AlignHCenter)
        title_label = QLabel(title)
        title_label.setProperty("role", "h2")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        desc = QLabel(description)
        desc.setProperty("role", "muted")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        self.button: QPushButton | None = None
        if button_text:
            self.button = QPushButton(button_text)
            self.button.setProperty("variant", "primary")
            self.button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.button.setMinimumHeight(35)
            layout.addSpacing(4)
            layout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignHCenter)
