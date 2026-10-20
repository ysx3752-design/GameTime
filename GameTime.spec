# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：Windows x64 便携目录版。"""

from pathlib import Path

ROOT = Path(SPECPATH)
APP_ICON = ROOT / "gametime" / "resources" / "app.ico"
VERSION_FILE = ROOT / "build" / "version_info.txt"

a = Analysis(
    [str(ROOT / "run_gametime.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "gametime" / "resources"), "gametime/resources"),
    ],
    hiddenimports=["psutil"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PIL",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "sqlalchemy",
        "IPython",
        "pytest",
        "PySide6.QtTest",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.Qt3DCore",
        "PySide6.QtMultimedia",
        "PySide6.QtCharts",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GameTime",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(APP_ICON),
    version=str(VERSION_FILE),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="GameTime",
)
