"""Fast Run launcher entry point.

Kept as ``.pyw`` (and at the same path as before) so existing shortcuts and the
``operations.json`` entry that points at ``manager.pyw`` keep working.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.launcher.app import main  # noqa: E402  (path bootstrap must run first)

if __name__ == "__main__":
    main()
