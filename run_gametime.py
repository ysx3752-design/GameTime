"""开发环境与开机自启使用的启动脚本。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gametime.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
