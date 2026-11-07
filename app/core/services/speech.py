"""Baidu TTS playback through python-vlc.

``vlc`` is imported lazily: the app must keep working when the user has not
installed python-vlc or the VLC desktop player, it just loses pronunciation.
"""

from __future__ import annotations

from typing import Any, Callable

from loguru import logger

from app.core.services.search import tts_url


class BaiduSpeech:
    def __init__(self, player_factory: Callable[[str], Any] | None = None) -> None:
        self._player_factory = player_factory

    def speak(self, text: str) -> bool:
        """Play the pronunciation; returns False instead of raising."""
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
        import vlc  # noqa: PLC0415 - deliberately lazy

        return vlc.MediaPlayer(url)
