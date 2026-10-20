 HEAD
# 游时 GameTime

一款 Windows 桌面游戏助手：**手动添加游戏、自动记录时长、卸载后不丢记录**。

游时不扫描硬盘、不读取 Steam / Epic 游戏库，也不会出现“未知游戏”占位。你添加哪款游戏，它就只记录哪款游戏。

![游时概览](docs/images/01-dashboard.png)

## 直接使用

1. 解压 `dist/GameTime-1.0.0-win64-portable.zip`
2. 运行 `GameTime.exe`
3. 点击「添加游戏」，选择游戏的启动程序 `.exe`
4. 启动游戏，游时会在后台自动计时；关闭主窗口会留在托盘继续记录

无需安装，无需管理员权限。数据保存在 `%LOCALAPPDATA%\GameTime`，只存储在本机。

 这是未签名的个人软件，Windows SmartScreen 可能提示“未知发布者”。点击「更多信息 → 仍要运行」即可。

## 功能

- 手动添加桌面游戏，绝不自动扫描或识别未添加的游戏
- 自动检测已添加游戏的 exe 进程并计时，退出后自动保存
- 手动计时兜底，适合启动器与进程识别困难的游戏
- 游戏库、搜索、排序、总时长、上次游玩
- 今日 / 近 7 天 / 累计统计，14 天趋势与游戏排行
- 卸载或移动游戏后保留名称、缓存图标和完整历史，显示「文件缺失」，可重新定位
- 系统托盘、关闭到托盘、开机自启、计时通知
- CSV 导出、本地 SQLite 数据、单实例运行
- 深色简洁界面，支持高 DPI

## 文档

- [产品说明文档（含框架、架构、测试报告）](docs/游时-说明文档.md)
- [Word 版说明文档](docs/游时-说明文档.docx)
- [PDF 版说明文档](docs/游时-说明文档.pdf)
- [测试报告](docs/测试报告.md)

## 开发

```powershell
python -m pip install -r requirements-dev.txt
python -m gametime
python -m pytest -q
```

构建便携版：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

## 技术栈

Python 3.14 · PySide6 / Qt 6.12 · SQLite · psutil · PyInstaller 6.20

## 说明

- 支持 Windows 10 / 11 x64。
- 自动计时按“添加时选择的 exe 完整路径”匹配进程，不猜测、不模糊匹配。
- 需要手动计时的场景：游戏由启动器拉起另一个 exe、游戏以管理员权限运行导致进程路径不可读等。
- 所有演示用游戏图标均为项目内生成的抽象图，不代表官方素材。

# GameTime
记录游戏时长。
 fa133e27831fd1a4fbc1ecfebbc225463e1d6538
