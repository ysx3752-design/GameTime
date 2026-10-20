"""Windows 平台相关的小工具；在非 Windows 环境下均安全降级。"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"


def normalize_windows_path(path: str | os.PathLike[str]) -> str:
    """规范化为可比较的绝对路径。Windows 下大小写不敏感。"""
    raw = os.fspath(path)
    try:
        if raw.startswith("\\\\?\\"):
            raw = raw[4:]
        absolute = os.path.abspath(raw)
        normalized = os.path.normpath(absolute)
        return os.path.normcase(normalized) if IS_WINDOWS else normalized
    except (OSError, ValueError):
        return os.path.normcase(os.path.normpath(raw)) if IS_WINDOWS else raw


def same_path(left: str, right: str) -> bool:
    return normalize_windows_path(left) == normalize_windows_path(right)


def _query_file_version_string(exe_path: str, field: str) -> str:
    """通过 version.dll 读取资源中的 ProductName / FileDescription。"""
    if not IS_WINDOWS:
        return ""
    try:
        from ctypes import wintypes

        version = ctypes.WinDLL("version", use_last_error=True)
        size = version.GetFileVersionInfoSizeW(str(exe_path), None)
        if not size:
            return ""
        buffer = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(str(exe_path), 0, size, buffer):
            return ""
        value = ctypes.c_void_p()
        length = wintypes.UINT()
        if not version.VerQueryValueW(
            buffer, f"\\StringFileInfo\\040904B0\\{field}", ctypes.byref(value), ctypes.byref(length)
        ):
            # 很多游戏使用 080404B0（简体中文）等语言表，退而使用 VarFileInfo 翻译表。
            translations = ctypes.c_void_p()
            trans_len = wintypes.UINT()
            if not version.VerQueryValueW(
                buffer,
                "\\VarFileInfo\\Translation",
                ctypes.byref(translations),
                ctypes.byref(trans_len),
            ) or not trans_len.value:
                return ""
            count = trans_len.value // 4
            for index in range(count):
                lang, codepage = ctypes.cast(
                    translations, ctypes.POINTER(ctypes.c_uint16 * 2)
                )[index]
                sub_block = f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\{field}"
                if version.VerQueryValueW(
                    buffer, sub_block, ctypes.byref(value), ctypes.byref(length)
                ) and value.value:
                    return ctypes.wstring_at(value.value, length.value).strip("\x00").strip()
            return ""
        if not value.value:
            return ""
        return ctypes.wstring_at(value.value, length.value).strip("\x00").strip()
    except Exception:
        return ""


def file_display_name(exe_path: str | os.PathLike[str]) -> str:
    """优先使用文件版本信息里的产品名，其次使用文件名。"""
    path = Path(exe_path)
    for field in ("ProductName", "FileDescription"):
        name = _query_file_version_string(str(path), field)
        if name and name.lower() not in {"python", "python launcher"}:
            return name[:80]
    stem = path.stem
    cleaned = stem.replace("_", " ").replace("-", " ").strip()
    return (cleaned or stem or "未命名游戏")[:80]


def pretty_exe_name(exe_path: str | os.PathLike[str]) -> str:
    return Path(exe_path).name


def set_app_user_model_id(app_id: str) -> None:
    """让任务栏与通知正确归组。"""
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


def apply_dark_title_bar(hwnd: int, dark: bool = True) -> None:
    """设置原生标题栏明暗（Windows 10 1809+）。"""
    if not IS_WINDOWS or not hwnd:
        return
    try:
        value = ctypes.c_int(1 if dark else 0)
        # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE (新版)，19 = 旧版编号
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), 20, ctypes.byref(value), ctypes.sizeof(value)
        )
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), 19, ctypes.byref(value), ctypes.sizeof(value)
        )
    except Exception:
        pass


def flash_window(hwnd: int) -> None:
    """当第二实例请求显示窗口时，将窗口带到前台。"""
    if not IS_WINDOWS or not hwnd:
        return
    try:
        ctypes.windll.user32.ShowWindow(ctypes.c_void_p(hwnd), 9)  # SW_RESTORE
        ctypes.windll.user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
    except Exception:
        pass
