"""内联 SVG 图标，避免外部图标库依赖并保证高分屏清晰。"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_PATHS: dict[str, str] = {
    "home": '<path d="M3.5 10.8 12 3.5l8.5 7.3"/><path d="M5.5 9.2V20h13V9.2"/><path d="M9.7 20v-5.8h4.6V20"/>',
    "library": '<rect x="3.5" y="4" width="7" height="7" rx="1.6"/><rect x="13.5" y="4" width="7" height="7" rx="1.6"/><rect x="3.5" y="14" width="7" height="6" rx="1.6"/><rect x="13.5" y="14" width="7" height="6" rx="1.6"/>',
    "chart": '<path d="M4 20V11"/><path d="M10 20V4"/><path d="M16 20v-6"/><path d="M22 20H2"/>',
    "settings": '<circle cx="12" cy="12" r="3.2"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.1 2.1-.06-.06A1.7 1.7 0 0 0 15.76 18a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.38 1.1V20h-3v-.3a1.7 1.7 0 0 0-1.1-1.58 1.7 1.7 0 0 0-1.88.34l-.06.06-2.1-2.1.06-.06A1.7 1.7 0 0 0 6 15.76a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.38H4v-3h.3A1.7 1.7 0 0 0 5.88 10.3a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.1-2.1.06.06A1.7 1.7 0 0 0 9.5 6.7a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .38-1.1V5h3v.3a1.7 1.7 0 0 0 1 1.58 1.7 1.7 0 0 0 1.88-.34l.06-.06 2.1 2.1-.06.06a1.7 1.7 0 0 0-.34 1.88v.1a1.7 1.7 0 0 0 1.7 1.7H20v3h-.3a1.7 1.7 0 0 0-1.58 1"/>',
    "plus": '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "play": '<path d="M8 5.2v13.6L19 12 8 5.2Z" fill="{color}" stroke="none"/>',
    "stop": '<rect x="7" y="7" width="10" height="10" rx="1.5" fill="{color}" stroke="none"/>',
    "pause": '<path d="M9 5v14"/><path d="M15 5v14"/>',
    "edit": '<path d="m4 20 4.5-1 10.2-10.2a2.1 2.1 0 0 0-3-3L5.5 16 4 20Z"/><path d="m14.5 6.7 2.8 2.8"/>',
    "trash": '<path d="M4 7h16"/><path d="M9 7V5h6v2"/><path d="m6 7 .9 13h10.2L18 7"/><path d="M10 11v5M14 11v5"/>',
    "folder": '<path d="M3.5 7.5h6l2-2h9v13h-17Z"/>',
    "search": '<circle cx="10.7" cy="10.7" r="6.2"/><path d="m15.5 15.5 4.4 4.4"/>',
    "chevron-right": '<path d="m9 5 7 7-7 7"/>',
    "chevron-left": '<path d="m15 5-7 7 7 7"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "clock": '<circle cx="12" cy="12" r="8.3"/><path d="M12 7.5V12l3 2"/>',
    "gamepad": '<path d="M7.5 8h9a5 5 0 0 1 4.8 6.4l-.6 2.3a2.5 2.5 0 0 1-4.2 1.1L14.6 16H9.4l-1.9 1.8a2.5 2.5 0 0 1-4.2-1.1l-.6-2.3A5 5 0 0 1 7.5 8Z"/><path d="M7 11.5v3M5.5 13h3M16 12h.01M18 14h.01"/>',
    "close": '<path d="m6 6 12 12M18 6 6 18"/>',
    "more": '<circle cx="5" cy="12" r="1" fill="{color}" stroke="none"/><circle cx="12" cy="12" r="1" fill="{color}" stroke="none"/><circle cx="19" cy="12" r="1" fill="{color}" stroke="none"/>',
    "refresh": '<path d="M20 11a8 8 0 1 0-2.3 6.7"/><path d="M20 4v7h-7"/>',
    "external": '<path d="M14 4h6v6"/><path d="M20 4 10 14"/><path d="M19 14v5H5V5h5"/>',
    "download": '<path d="M12 4v11"/><path d="m7.5 11 4.5 4.5 4.5-4.5"/><path d="M4 19.5h16"/>',
    "check": '<path d="m5 12.5 4.3 4.3L19 7"/>',
    "alert": '<path d="M12 3.5 21 20H3Z"/><path d="M12 9v5"/><path d="M12 17h.01"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/>',
    "spark": '<path d="m12 3 1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4Z"/><path d="m19 16 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8Z"/>',
}


@lru_cache(maxsize=256)
def pixmap(name: str, color: str = "#E8ECF5", size: int = 20, width: float = 1.8) -> QPixmap:
    body = _PATHS.get(name, _PATHS["gamepad"]).replace("{color}", color)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    scale = 2
    image = QPixmap(size * scale, size * scale)
    image.setDevicePixelRatio(scale)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return image


def icon(name: str, color: str = "#E8ECF5", size: int = 20) -> QIcon:
    return QIcon(pixmap(name, color, size))


class IconWidget:
    """供需要直接绘制的场景使用的小工具，不属于 QWidget。"""

    @staticmethod
    def size() -> QSize:
        return QSize(20, 20)
