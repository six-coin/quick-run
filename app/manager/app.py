"""操作管理器的入口（pywebview）。"""

from __future__ import annotations

import ctypes

import webview
from loguru import logger

from app import i18n, logging_setup, paths
from app.errors import ConfigError
from app.manager.api import ManagerApi

#: 网页首帧渲染出来之前，窗口用这个底色，避免闪一下白。
_BACKGROUND = {"light": "#f0f2f5", "dark": "#14161a"}


def main() -> None:
    logging_setup.setup("manage")

    try:
        api = ManagerApi()
    except ConfigError as error:
        logging_setup.fatal(i18n.t("fatal.config", error=error))
        return

    width, height = _window_size()
    min_width, min_height = _min_size()
    theme = api.get_state()["theme"]

    window = webview.create_window(
        i18n.t("manager.title"),
        str(paths.WEB_DIR / "index.html"),
        js_api=api,
        width=width,
        height=height,
        min_size=(min_width, min_height),
        background_color=_BACKGROUND.get(theme, _BACKGROUND["light"]),
    )
    api.attach(window)
    window.events.closing += _make_closing_handler(api)

    logger.info("管理器已就绪")
    webview.start()


def _make_closing_handler(api: ManagerApi):
    """取消关闭，让网页在自己的界面里问用户。

    ``closing`` 在 UI 线程执行，所以提示由工作线程推过去
    （见 ``ManagerApi.request_close_prompt``）。页面实在弹不出来时，
    API 内部会退回系统对话框。
    """

    def on_closing():
        if not api.dirty or api.close_confirmed:
            return True
        api.request_close_prompt()
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
