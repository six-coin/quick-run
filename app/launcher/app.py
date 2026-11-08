"""Alt+Space 启动器的入口，也是唯一负责装配的地方。

所有依赖都在这里串起来：配置 → 操作目录 → 解析器 → 控制器 → 窗口 → 热键。
其余模块只通过构造函数拿到自己需要的东西，这正是它们能保持低耦合的原因。
"""

from __future__ import annotations

import sys

from loguru import logger
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from app import i18n, logging_setup
from app.core.actions import ActionExecutor
from app.core.catalog import Catalog
from app.core.navigation import DirectoryNavigator
from app.core.resolver import QueryResolver
from app.core.services.definition import GlmDefinition
from app.core.services.speech import BaiduSpeech
from app.core.services.translate import BaiduTranslator
from app.errors import ConfigError
from app.launcher import theme
from app.launcher.controller import LauncherController
from app.launcher.window import SearchWindow
from app.settings import load_settings
from app.system.clipboard import PyperclipClipboard
from app.system.hotkey import HotkeyListener
from app.system.shell import WindowsOpener


class _HotkeyBridge(QObject):
    """把热键回调从 Win32 线程搬到 Qt 线程上执行。"""

    triggered = Signal()


def main() -> None:
    logging_setup.setup("main")
    try:
        _run()
    except SystemExit:
        raise
    except Exception as error:  # 最后一道防线，直接弹窗
        logger.exception("程序启动失败")
        logging_setup.fatal(i18n.t("fatal.startup", error=error))


def _run() -> None:
    try:
        settings = load_settings()
    except ConfigError as error:
        logging_setup.fatal(i18n.t("fatal.operations", error=error))
        return

    for warning in settings.warnings:
        logger.warning(warning)

    catalog = Catalog(settings.operations)
    resolver = QueryResolver(
        catalog,
        DirectoryNavigator(
            max_items=settings.config.max_entries,
            max_depth=settings.config.max_depth,
        ),
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
    window = SearchWindow(controller, theme.for_theme(settings.config.theme))

    bridge = _HotkeyBridge()
    bridge.triggered.connect(window.show_window)

    listener = HotkeyListener(bridge.triggered.emit)
    listener.start()
    ready = listener.wait_ready(3.0)
    if listener.error or not ready:
        logging_setup.fatal(listener.error or i18n.t("fatal.hotkey_timeout"))
        return

    logger.info("启动器已就绪，按 Alt+Space 唤出")
    try:
        sys.exit(app.exec())
    finally:
        listener.stop()


if __name__ == "__main__":
    main()
