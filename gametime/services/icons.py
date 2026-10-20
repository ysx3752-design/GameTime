"""游戏图标：从 exe 提取并永久缓存，卸载后仍保留，绝不用“未知游戏”占位。"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from PySide6.QtCore import QFileInfo, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QFileIconProvider

ICON_SIZE = 256
ACCENTS = (
    "#7C5CFF",
    "#20C997",
    "#FF8A3D",
    "#4DABF7",
    "#F06595",
    "#FCC419",
    "#38D9A9",
    "#9775FA",
)


def accent_for(name: str, path: str = "") -> str:
    digest = hashlib.sha1(f"{name}|{path}".encode("utf-8", "ignore")).digest()
    return ACCENTS[digest[0] % len(ACCENTS)]


def _load_font(size: int, weight: QFont.Weight = QFont.Weight.Bold) -> QFont:
    font = QFont("Microsoft YaHei UI")
    font.setPixelSize(size)
    font.setWeight(weight)
    return font


def letter_pixmap(name: str, accent: str, size: int = ICON_SIZE) -> QPixmap:
    """生成品牌色字母/汉字图标，用作无图标游戏的稳定封面。"""
    scale = 2
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    rect = QRectF(0, 0, size, size)
    base = QColor(accent)
    gradient = QLinearGradient(QPointF(0, 0), QPointF(size, size))
    gradient.setColorAt(0.0, base.lighter(132))
    gradient.setColorAt(1.0, base.darker(158))
    path = QPainterPath()
    path.addRoundedRect(rect.adjusted(6, 6, -6, -6), 54, 54)
    painter.fillPath(path, gradient)

    glow = QRadialGradient(QPointF(size * 0.78, size * 0.18), size * 0.58)
    glow.setColorAt(0.0, QColor(255, 255, 255, 72))
    glow.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.fillPath(path, glow)

    painter.setPen(QPen(QColor(255, 255, 255, 38), 2))
    painter.drawPath(path)

    text = (name.strip()[:1] or "游").upper()
    painter.setFont(_load_font(112))
    painter.setPen(QColor(255, 255, 255, 238))
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    painter.end()
    return pixmap


class IconService:
    def __init__(self, icons_dir: str | Path) -> None:
        self.icons_dir = Path(icons_dir)
        self.icons_dir.mkdir(parents=True, exist_ok=True)
        self._provider = QFileIconProvider()
        self._cache: dict[tuple[str, int, str], QIcon] = {}

    # ------------------------------------------------------------------ public
    def create_cached_icon(self, exe_path: str, name: str, accent: str) -> str | None:
        """提取 exe 图标并保存为 PNG；提取失败时保存字母封面。返回相对文件名。"""
        filename = f"game_{uuid.uuid4().hex}.png"
        destination = self.icons_dir / filename
        try:
            pixmap = self._extract_pixmap(exe_path, 256)
            if pixmap is None or pixmap.isNull():
                pixmap = letter_pixmap(name, accent)
            # 保存原尺寸（最多 256），显示端再平滑缩放。
            if pixmap.width() > ICON_SIZE or pixmap.height() > ICON_SIZE:
                pixmap = pixmap.scaled(
                    QSize(ICON_SIZE, ICON_SIZE),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            if not pixmap.save(str(destination), "PNG"):
                return None
            return filename
        except Exception:
            return None

    def delete_cached_icon(self, relative_name: str | None) -> None:
        if not relative_name:
            return
        candidate = (self.icons_dir / relative_name).resolve()
        try:
            candidate.relative_to(self.icons_dir.resolve())
        except ValueError:
            return
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass

    def icon_for_file(self, exe_path: str, fallback_name: str, accent: str) -> QIcon:
        key = (exe_path.lower(), 256, fallback_name)
        if key in self._cache:
            return self._cache[key]
        pixmap = self._extract_pixmap(exe_path, 256)
        if pixmap is None or pixmap.isNull():
            pixmap = letter_pixmap(fallback_name, accent)
        icon = QIcon(pixmap)
        self._cache[key] = icon
        return icon

    def icon_path(self, game) -> Path | None:  # noqa: ANN001
        """返回游戏缓存图标的绝对路径；缓存缺失时返回 None，由 UI 生成字母封面。"""
        if not game.icon_file:
            return None
        candidate = (self.icons_dir / game.icon_file).resolve()
        try:
            candidate.relative_to(self.icons_dir.resolve())
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    def pixmap_from_file(self, icon_file: str | Path | None, size: int = 64) -> QPixmap | None:
        if not icon_file:
            return None
        path = Path(icon_file)
        if not path.is_file():
            return None
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
        return pixmap.scaled(
            QSize(size, size),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    # ----------------------------------------------------------------- private
    def _extract_pixmap(self, exe_path: str, size: int) -> QPixmap | None:
        path = Path(exe_path)
        if not path.is_file():
            return None
        try:
            icon = self._provider.icon(QFileInfo(str(path)))
            if icon.isNull():
                return None
            for candidate in (256, 128, 64, 48, 32):
                pixmap = icon.pixmap(QSize(candidate, candidate))
                if not pixmap.isNull():
                    return pixmap
        except Exception:
            return None
        return None
