"""用 python-vlc 播放百度语音合成。

``vlc`` 是延迟导入的：用户没装 python-vlc 或 VLC 播放器时程序要照常可用，
只是少了朗读功能。
"""

from __future__ import annotations

from typing import Any, Callable

from loguru import logger

from app.core.services.search import tts_url


class BaiduSpeech:
    def __init__(self, player_factory: Callable[[str], Any] | None = None) -> None:
        self._player_factory = player_factory

    def speak(self, text: str) -> bool:
        """播放发音；失败时返回 False 而不是抛异常。"""
        try:
            player = self._create_player(tts_url(text))
            player.play()
            try:
                player.set_time(0)
            except Exception:
                pass
            logger.info("播放发音：{}", text)
            return True
        except ImportError:
            logger.warning("无法播放发音：未安装 python-vlc 或 VLC Media Player")
        except Exception as error:
            logger.warning("播放发音 {} 失败：{}", text, error)
        return False

    def _create_player(self, url: str) -> Any:
        if self._player_factory is not None:
            return self._player_factory(url)
        import vlc  # noqa: PLC0415 - 有意延迟导入

        return vlc.MediaPlayer(url)
