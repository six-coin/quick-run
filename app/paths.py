"""Single source of truth for every path the application touches.

Every path here is absolute and derived from this file's location. Nothing in
the project may depend on the process working directory, and nothing may call
``os.chdir`` -- see ``app/system/shell.py`` for the cwd-safe launcher helpers.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = PACKAGE_DIR.parent

CONFIG_DIR = PROGRAM_DIR / "config"
LOG_DIR = PROGRAM_DIR / "logs"

OPERATIONS_PATH = CONFIG_DIR / "operations.json"
TRANSLATE_PATH = CONFIG_DIR / "translate.json"
AI_PATH = CONFIG_DIR / "ai.json"

ENTRY_MAIN = PROGRAM_DIR / "main.pyw"
ENTRY_MANAGER = PROGRAM_DIR / "manager.pyw"

WEB_DIR = PACKAGE_DIR / "manager" / "web"


def resolve_user_path(raw: str) -> Path:
    """Resolve a path that came from the config file.

    Relative entries (``custom\\foo.py``) are anchored at the program directory
    instead of the process cwd, which is what made the old version create
    ``logs/`` folders all over the disk.
    """
    text = (raw or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1]
    if not text:
        return PROGRAM_DIR
    path = Path(text)
    if path.is_absolute():
        return path
    return (PROGRAM_DIR / path).resolve()


def split_paths(raw: str) -> list[Path]:
    """Split a ``|`` separated path list from the config into absolute paths."""
    return [resolve_user_path(part) for part in (raw or "").split("|") if part.strip()]
