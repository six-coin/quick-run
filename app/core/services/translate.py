"""百度翻译接口客户端。"""

from __future__ import annotations

import hashlib
import time

import requests

from app import i18n
from app.errors import ServiceError

_ENDPOINT = "https://fanyi-api.baidu.com/api/trans/vip/translate"


class BaiduTranslator:
    def __init__(self, appid: str, secret_key: str, timeout: float = 5.0) -> None:
        self._appid = appid
        self._secret_key = secret_key
        self._timeout = timeout

    def translate(self, text: str) -> str:
        salt = str(int(time.time() * 1000))
        sign_source = f"{self._appid}{text}{salt}{self._secret_key}"
        sign = hashlib.md5(sign_source.encode("utf-8")).hexdigest()
        params = {
            "q": text,
            "from": "auto",
            "to": "auto",
            "appid": self._appid,
            "salt": salt,
            "sign": sign,
        }
        try:
            response = requests.get(_ENDPOINT, params=params, timeout=self._timeout)
            payload = response.json()
        except Exception as error:  # 网络异常、超时、返回的不是 JSON
            raise ServiceError(i18n.t("service.request_failed", error=error)) from error

        if "trans_result" in payload:
            try:
                return str(payload["trans_result"][0]["dst"])
            except (KeyError, IndexError, TypeError) as error:
                raise ServiceError(i18n.t("service.request_failed", error=error)) from error

        message = payload.get("error_msg", i18n.t("service.unknown_error"))
        raise ServiceError(i18n.t("service.translate_failed", message=message))
