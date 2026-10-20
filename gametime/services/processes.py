"""进程检测：只检测“已手动加入游戏库”的 exe 是否正在运行。"""

from __future__ import annotations

import logging
from collections.abc import Iterable

import psutil

from ..windows import normalize_windows_path

log = logging.getLogger(__name__)


class ProcessScanner:
    """返回当前运行进程的规范化 exe 路径集合。

    不做任何游戏目录扫描，也不维护游戏名单；是否属于游戏完全由游戏库决定。
    """

    def running_paths(self) -> set[str]:
        paths: set[str] = set()
        try:
            iterator: Iterable[psutil.Process] = psutil.process_iter(["exe"])
        except Exception:
            log.exception("无法枚举进程")
            return paths
        for process in iterator:
            try:
                exe = process.info.get("exe")
                if exe:
                    paths.add(normalize_windows_path(exe))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
                continue
            except Exception:
                log.debug("读取进程路径失败", exc_info=True)
        return paths


class FakeProcessScanner:
    """测试辅助：由测试代码显式设置正在运行的路径。"""

    def __init__(self, paths: Iterable[str] = ()) -> None:
        self.paths = {normalize_windows_path(path) for path in paths}

    def set_running(self, paths: Iterable[str]) -> None:
        self.paths = {normalize_windows_path(path) for path in paths}

    def running_paths(self) -> set[str]:
        return set(self.paths)
