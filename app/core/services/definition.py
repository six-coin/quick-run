"""智谱 GLM 查词。"""

from __future__ import annotations

import requests

from app import i18n
from app.errors import ServiceError

_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
_MODEL = "GLM-4-Flash-250414"
_SYSTEM_PROMPT = """你是一个词典助手，功能如下：
用户输入的是中文词语、成语或俗语，请输出其不超过25个字的简短释义：
 (1) 例如用户输入“暗度陈仓”，你输出“正面迷惑对手，暗地里迂回突袭要害，最终达成目的。”；
 (2) 例如用户输入“申诉”，你输出“指当事人对处理不服，向有关部门请求重新处理。”。
如果用户问了一个问句，那你就简短回答。"""


class GlmDefinition:
    def __init__(self, api_key: str, timeout: float = 15.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    def lookup(self, text: str) -> str:
        body = {
            "model": _MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
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
