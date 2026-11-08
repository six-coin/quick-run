"""Quick Run 启动器入口。

双击 ``main.bat`` 时由虚拟环境里的 ``pythonw.exe`` 执行本文件。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _run() -> None:
    from app.launcher.app import main

    main()


if __name__ == "__main__":
    _run()
