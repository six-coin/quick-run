"""快捷运行操作管理器（Quick Run Manager）入口。

双击 ``manager.bat`` 时由虚拟环境里的 ``pythonw.exe`` 执行本文件。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _run() -> None:
    from app.manager.app import main

    main()


if __name__ == "__main__":
    _run()
