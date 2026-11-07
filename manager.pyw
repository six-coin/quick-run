"""Fast Run operation manager entry point (pywebview)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.manager.app import main  # noqa: E402  (path bootstrap must run first)

if __name__ == "__main__":
    main()
