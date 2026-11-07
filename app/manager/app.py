"""Entry point for the pywebview operation manager."""

from __future__ import annotations

import ctypes

import webview
from loguru import logger

from app import logging_setup, paths
from app.errors import ConfigError
from app.manager.api import ManagerApi
from app.manager.dialogs import confirm_unsaved


def main() -> None:
    logging_setup.setup("manage")

    try:
        api = ManagerApi()
    except ConfigError as error:
        logging_setup.fatal(f"程序无法继续运行，因为无法读取操作列表：\n{error}")
        return

    width, height = _window_size()
    min_width, min_height = _min_size()

    window = webview.create_window(
        "Fast Run 操作管理器",
        str(paths.WEB_DIR / "index.html"),
        js_api=api,
        width=width,
        height=height,
        min_size=(min_width, min_height),
        background_color="#f0f2f5",
    )
    api.attach(window)
    window.events.closing += _make_closing_handler(api)

    logger.info("管理器已就绪")
    webview.start()


def _make_closing_handler(api: ManagerApi):
    def on_closing():
        if not api.dirty:
            return True

        choice = confirm_unsaved()
        if choice == "discard":
            return True
        if choice == "save":
            return bool(api.save().get("ok"))
        return False

    return on_closing


def _screen_size() -> tuple[int, int]:
    try:
        screen = webview.screens[0]
        return int(screen.width), int(screen.height)
    except Exception:
        user32 = ctypes.windll.user32
        return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))


def _window_size() -> tuple[int, int]:
    width, height = _screen_size()
    return int(width * 0.85), int(height * 0.85)


def _min_size() -> tuple[int, int]:
    width, height = _screen_size()
    return int(width * 0.5), int(height * 0.5)


if __name__ == "__main__":
    main()
