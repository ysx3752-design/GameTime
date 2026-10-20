"""游戏图标：从 exe 提取并永久缓存，卸载后仍保留，绝不用“未知游戏”占位。"""

from __future__ import annotations

import hashlib
import os
import sys
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QFileInfo, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QImage,
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


def _content_rect(image: QImage) -> QRect:
    """返回非透明内容的包围盒，去掉 exe 图标常见的透明留白。"""
    width, height = image.width(), image.height()
    left, top = width, height
    right = bottom = -1
    for y in range(height):
        for x in range(width):
            if (image.pixel(x, y) >> 24) & 0xFF > 8:
                left = min(left, x)
                top = min(top, y)
                right = max(right, x)
                bottom = max(bottom, y)
    if right < left:
        return QRect()
    return QRect(left, top, right - left + 1, bottom - top + 1)


def normalize_pixmap(pixmap: QPixmap | None, size: int = ICON_SIZE) -> QPixmap | None:
    """去掉透明留白、统一 DPR，并把图标放进正方形画布。"""
    if pixmap is None or pixmap.isNull():
        return None
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    image.setDevicePixelRatio(1.0)
    content = _content_rect(image)
    if content.isValid() and (content.width() < image.width() or content.height() < image.height()):
        image = image.copy(content)
    scaled = image.scaled(
        QSize(size, size),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    canvas = QImage(size, size, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.drawImage(
        (size - scaled.width()) // 2,
        (size - scaled.height()) // 2,
        scaled,
    )
    painter.end()
    result = QPixmap.fromImage(canvas)
    result.setDevicePixelRatio(1.0)
    return result


def _extract_shell_pixmap(exe_path: str) -> QPixmap | None:
    """通过 Windows Shell 读取真实 exe 图标。

    QFileIconProvider 对部分 Unreal/自解压 exe 只返回通用文件图标，
    这里用 SHGetFileInfoW 取得系统实际图标（通常是 32×32）。
    """
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    exe_path = os.path.normpath(exe_path)

    class SHFILEINFOW(ctypes.Structure):
        _fields_ = [
            ("hIcon", wintypes.HICON),
            ("iIcon", ctypes.c_int),
            ("dwAttributes", wintypes.DWORD),
            ("szDisplayName", wintypes.WCHAR * 260),
            ("szTypeName", wintypes.WCHAR * 80),
        ]

    class ICONINFO(ctypes.Structure):
        _fields_ = [
            ("fIcon", wintypes.BOOL),
            ("xHotspot", wintypes.DWORD),
            ("yHotspot", wintypes.DWORD),
            ("hbmMask", wintypes.HBITMAP),
            ("hbmColor", wintypes.HBITMAP),
        ]

    class BITMAP(ctypes.Structure):
        _fields_ = [
            ("bmType", wintypes.LONG),
            ("bmWidth", wintypes.LONG),
            ("bmHeight", wintypes.LONG),
            ("bmWidthBytes", wintypes.LONG),
            ("bmPlanes", wintypes.WORD),
            ("bmBitsPixel", wintypes.WORD),
            ("bmBits", wintypes.LPVOID),
        ]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    shell_info = SHFILEINFOW()
    flags = 0x00000100  # SHGFI_ICON | SHGFI_LARGEICON
    result = 0
    # Windows Shell 在应用刚启动/资源管理器繁忙时偶尔返回 0，短暂重试。
    for attempt in range(4):
        if attempt:
            time.sleep(0.06)
        result = ctypes.windll.shell32.SHGetFileInfoW(
            exe_path, 0, ctypes.byref(shell_info), ctypes.sizeof(shell_info), flags
        )
        if result and shell_info.hIcon:
            break
    if not result or not shell_info.hIcon:
        return None
    hicon = shell_info.hIcon
    icon_info = ICONINFO()
    hdc = 0
    try:
        if not ctypes.windll.user32.GetIconInfo(hicon, ctypes.byref(icon_info)):
            return None
        if not icon_info.hbmColor:
            return None
        bitmap = BITMAP()
        if not ctypes.windll.gdi32.GetObjectW(
            icon_info.hbmColor, ctypes.sizeof(bitmap), ctypes.byref(bitmap)
        ):
            return None
        width, height = bitmap.bmWidth, bitmap.bmHeight
        if width <= 0 or height <= 0:
            return None
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0
        buffer = ctypes.create_string_buffer(width * height * 4)
        hdc = ctypes.windll.user32.GetDC(0)
        copied = ctypes.windll.gdi32.GetDIBits(
            hdc, icon_info.hbmColor, 0, height, buffer, ctypes.byref(info), 0
        )
        if not copied:
            return None
        image = QImage(buffer, width, height, width * 4, QImage.Format.Format_ARGB32).copy()
        return QPixmap.fromImage(image)
    except Exception:
        return None
    finally:
        try:
            if hdc:
                ctypes.windll.user32.ReleaseDC(0, hdc)
            if icon_info.hbmColor:
                ctypes.windll.gdi32.DeleteObject(ctypes.c_void_p(icon_info.hbmColor))
            if icon_info.hbmMask:
                ctypes.windll.gdi32.DeleteObject(ctypes.c_void_p(icon_info.hbmMask))
            ctypes.windll.user32.DestroyIcon(ctypes.c_void_p(hicon))
        except Exception:
            pass


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
            pixmap = normalize_pixmap(pixmap)
            if pixmap is None or pixmap.isNull():
                pixmap = normalize_pixmap(letter_pixmap(name, accent)) or letter_pixmap(name, accent)
            if not pixmap.save(str(destination), "PNG"):
                return None
            return filename
        except Exception:
            return None

    def normalize_cached_icon(self, relative_name: str | None) -> bool:
        """修复旧版本留下的“小图标 + 大量透明留白”缓存。"""
        if not relative_name:
            return False
        source = self.icons_dir / relative_name
        if not source.is_file():
            return False
        pixmap = QPixmap(str(source))
        normalized = normalize_pixmap(pixmap)
        if normalized is None:
            return False
        temporary = source.with_name(f"{source.stem}.normalized.png")
        try:
            if not normalized.save(str(temporary), "PNG"):
                return False
            temporary.replace(source)
            return True
        except OSError:
            return False
        finally:
            temporary.unlink(missing_ok=True)

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
        pixmap = normalize_pixmap(self._extract_pixmap(exe_path, 256))
        if pixmap is None or pixmap.isNull():
            pixmap = normalize_pixmap(letter_pixmap(fallback_name, accent)) or letter_pixmap(
                fallback_name, accent
            )
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
        normalized = normalize_pixmap(pixmap)
        if normalized is None:
            return None
        return normalized.scaled(
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
            shell_pixmap = _extract_shell_pixmap(str(path))
            if shell_pixmap is not None and not shell_pixmap.isNull():
                return shell_pixmap
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
