"""Fast Run 操作管理器入口（pywebview）。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.manager.app import main  # noqa: E402  （必须先完成路径引导）

if __name__ == "__main__":
    main()
