"""Fast Run 启动器入口。

保持 ``.pyw`` 后缀和原来的路径，这样已有的快捷方式和
``operations.json`` 里指向 ``manager.pyw`` 的条目都还能用。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.launcher.app import main  # noqa: E402  （必须先完成路径引导）

if __name__ == "__main__":
    main()
