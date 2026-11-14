"""智谱 GLM 查词。"""

from __future__ import annotations

import requests

from app import i18n
from app.errors import ServiceError
from app.prompts import DEFAULT_SYSTEM_PROMPT

_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
_MODEL = "GLM-4-Flash-250414"


class GlmDefinition:
    def __init__(
        self,
        api_key: str,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        timeout: float = 15.0,
    ) -> None:
        self._api_key = api_key
        # 设置里清空提示词时回到内置的那一份，别真发一条空 system 消息出去。
        self._system_prompt = (system_prompt or "").strip() or DEFAULT_SYSTEM_PROMPT
        self._timeout = timeout

    def lookup(self, text: str) -> str:
        body = {
            "model": _MODEL,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.5,
            "max_tokens": 1000,
        }
        headers = {"Authorization": self._api_key, "Content-Type": "application/json"}

        try:
            response = requests.post(_ENDPOINT, headers=headers, json=body, timeout=self._timeout)
            payload = response.json()
        except Exception as error:
            raise ServiceError(str(error)) from error

        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError):
            message = i18n.t("service.definition_failed")
            if isinstance(payload, dict):
                message = str(payload.get("error", {}).get("message", message))
            raise ServiceError(message) from None
