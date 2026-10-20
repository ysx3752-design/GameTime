# 游时 GameTime · 第三方组件声明

游时 1.0.0 以 Python / PySide6 构建，并以 PyInstaller 打包为 Windows 便携版。
以下声明随软件分发。完整 LGPL/GPL 文本位于本目录的 `LICENSES` 文件夹。

## PySide6 / Qt 6

- 项目：https://www.qt.io/qt-for-python
- 许可：GNU Lesser General Public License v3（LGPLv3），或 Qt 商业许可
- 本项目使用方式：通过 PySide6 动态链接 Qt 6 共享库，未修改 Qt 源码。
- 使用的 Qt 模块：Core、Gui、Widgets、Network、Svg。
- LGPLv3 文本：`LICENSES/LGPL-3.0.txt`
- GPLv3 文本：`LICENSES/GPL-3.0.txt`
- Qt 源代码获取：https://download.qt.io/official_releases/qt/

根据 LGPLv3，接收者可以替换 Qt 共享库（本软件以独立 DLL 方式分发），并可在需要时获取 Qt 源代码。若要以闭源商业方式分发，请自行评估 LGPL 义务或购买 Qt 商业许可。

## psutil

- 项目：https://github.com/giampaolo/psutil
- 许可：BSD 3-Clause
- 文本：`LICENSES/psutil-BSD-3-Clause.txt`

## Python

- 项目：https://www.python.org/
- 许可：Python Software Foundation License
- 文本：https://docs.python.org/3/license.html

## SQLite

- 项目：https://www.sqlite.org/
- 许可：Public Domain

## PyInstaller

- 项目：https://pyinstaller.org/
- 许可：GNU GPL v2，附有允许打包专有应用程序的 bootloader 例外条款。
- 文本：https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt

## 图标与演示素材

应用图标、界面图标、演示游戏封面均由本项目脚本生成（`scripts/generate_assets.py` 与 `scripts/seed_demo.py`），不包含任何游戏官方美术资源。演示中的游戏名称仅用于说明功能。
