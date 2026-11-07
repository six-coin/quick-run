"""Entry point for the Alt+Space launcher (composition root).

Everything is wired here and nowhere else: settings -> catalog -> resolver ->
controller -> window -> hotkey. The rest of the package only receives what it
needs through constructors, which is what keeps the modules decoupled.
"""

from __future__ import annotations

import sys

from loguru import logger
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from app import logging_setup
from app.core.actions import ActionExecutor
from app.core.catalog import Catalog
from app.core.navigation import DirectoryNavigator
from app.core.resolver import QueryResolver
from app.core.services.definition import GlmDefinition
from app.core.services.speech import BaiduSpeech
from app.core.services.translate import BaiduTranslator
from app.errors import ConfigError
from app.launcher.controller import LauncherController
from app.launcher.window import SearchWindow
from app.settings import load_settings
from app.system.clipboard import PyperclipClipboard
from app.system.hotkey import HotkeyListener
from app.system.shell import WindowsOpener


class _HotkeyBridge(QObject):
    """Marshals the hotkey callback from the Win32 thread onto the Qt thread."""

    triggered = Signal()


def main() -> None:
    logging_setup.setup("main")
    try:
        _run()
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001 - last resort, show a dialog
        logger.exception("程序启动失败")
        logging_setup.fatal(f"程序启动失败：\n{error}")


def _run() -> None:
    try:
        settings = load_settings()
    except ConfigError as error:
        logging_setup.fatal(f"程序无法启动，因为无法读取操作列表：\n{error}")
        return

    for warning in settings.warnings:
        logger.warning(warning)

    catalog = Catalog(settings.operations)
    resolver = QueryResolver(
        catalog,
        DirectoryNavigator(),
        ai_api_key=settings.ai_api_key,
        translate_enabled=settings.translate is not None,
    )
    translator = (
        BaiduTranslator(settings.translate.appid, settings.translate.secret_key)
        if settings.translate is not None
        else None
    )
    definition = GlmDefinition(settings.ai_api_key) if settings.ai_api_key else None

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Windows")

    executor = ActionExecutor(WindowsOpener(), BaiduSpeech())
    controller = LauncherController(
        resolver=resolver,
        executor=executor,
        clipboard=PyperclipClipboard(),
        translator=translator,
        definition=definition,
    )
    window = SearchWindow(controller)

    bridge = _HotkeyBridge()
    bridge.triggered.connect(window.show_window)

    listener = HotkeyListener(bridge.triggered.emit)
    listener.start()
    ready = listener.wait_ready(3.0)
    if listener.error or not ready:
        logging_setup.fatal(listener.error or "全局快捷键注册超时，程序无法启动")
        return

    logger.info("启动器已就绪，按 Alt+Space 唤出")
    try:
        sys.exit(app.exec())
    finally:
        listener.stop()


if __name__ == "__main__":
    main()
