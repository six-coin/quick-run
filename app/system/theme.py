"""读取 Windows 的浅色 / 深色偏好。

只在第一次启动、还没有 ``config/app.json`` 时用一次：把系统当前的外观
写成初始值。之后一律以配置文件里保存的值为准，用户手动切换过就不再跟随系统。
"""

from __future__ import annotations

try:  # 项目只在 Windows 上运行，这里仍保留导入兜底，方便在别的平台跑测试
    import winreg
except ImportError:  # pragma: no cover
    winreg = None  # type: ignore[assignment]

_PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
_LIGHT_KEY = "AppsUseLightTheme"

#: 允许写入配置的外观取值。
THEMES: tuple[str, ...] = ("light", "dark")


def normalize_theme(value: object) -> str:
    """把任意输入收敛成受支持的外观取值。"""
    text = str(value or "").strip().lower()
    return text if text in THEMES else "light"


def system_theme() -> str:
    """返回 ``"dark"`` 或 ``"light"``，读取失败时按浅色处理。"""
    if winreg is None:
        return "light"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _PERSONALIZE) as key:
            value, _ = winreg.QueryValueEx(key, _LIGHT_KEY)
        return "light" if int(value) else "dark"
    except Exception:
        return "light"
