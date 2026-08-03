import hashlib
import multiprocessing
import time

import requests
from PySide6.QtCore import (QRunnable)
from PySide6.QtCore import (Signal, QObject)

from libs import ai
from libs import execute
from libs import log


class Signals(QObject):
    """用于在线程与主线程之间传递结果的信号类"""
    success = Signal(list)  # 成功时发出结果
    error = Signal(list)  # 失败时发出错误信息


class TranslateRunnable(QRunnable):
    """用于执行百度翻译的 Runnable"""

    def __init__(self, text, appid, secret_key, translate_id):
        super().__init__()
        self.text = text
        self.appid = appid
        self.secret_key = secret_key
        self.translate_id = translate_id
        self.signals = Signals()

    # 在线程池的线程中执行，不会卡主线程
    def run(self):
        try:
            salt = str(int(time.time() * 1000))
            sign_str = self.appid + self.text + salt + self.secret_key
            sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
            from_lang, to_lang = "auto", "auto"

            # 向百度翻译发送请求
            params = {"q": self.text, "from": from_lang, "to": to_lang, "appid": self.appid, "salt": salt, "sign": sign}
            response = requests.get("https://fanyi-api.baidu.com/api/trans/vip/translate", params=params, timeout=5)
            data = response.json()

            if "trans_result" in data:
                dst = data["trans_result"][0]["dst"]
                self.signals.success.emit([dst, self.translate_id])
            else:
                err_msg = data.get("error_msg", "未知错误")
                self.signals.error.emit([f"翻译失败：{err_msg}", self.translate_id])

        except Exception as e:
            self.signals.error.emit([f"请求异常：{e}", self.translate_id])


class DefinitionRunnable(QRunnable):
    """用于执行查词的 Runnable"""

    def __init__(self, text, api_key, definition_id):
        super().__init__()
        self.text = text
        self.api_key = api_key
        self.definition_id = definition_id
        self.signals = Signals()

    # 在线程池的线程中执行，不会卡主线程
    def run(self):
        try:
            definition_result = ai.find_definition(self.text, self.api_key)
            self.signals.success.emit([definition_result, self.definition_id])
        except Exception as e:
            self.signals.error.emit([str(e), self.definition_id])


class CalculateRunnable(QRunnable):
    """用于执行计算的 Runnable"""

    def __init__(self, calculate_equation, calculate_id):
        super().__init__()
        self.calculate_equation = calculate_equation
        self.calculate_id = calculate_id
        self.signals = Signals()
        self.calculate_timeout = 2

    def run(self):
        try:
            # 使用进程池执行计算，原因：若使用 PyQt 自带的多线程，仍会收到 GIL 的限制，导致主线程被卡死，只能新建进程
            with multiprocessing.Pool(processes=1) as pool:
                # 异步执行计算
                async_result = pool.apply_async(self._calculate, (self.calculate_equation,))
                try:
                    # 等待结果，设置超时
                    calculate_result = async_result.get(timeout=self.calculate_timeout)
                    if len(calculate_result) > 5000:
                        raise Exception("结果过长")
                    self.signals.success.emit([calculate_result, self.calculate_id])
                except multiprocessing.TimeoutError:
                    # 超时处理
                    pool.terminate()  # 终止进程
                    pool.join()  # 等待进程结束
                    self.signals.error.emit(["计算超时", self.calculate_id])
                except Exception as e:
                    # 其他错误
                    self.signals.error.emit([f"发生错误：{e}", self.calculate_id])
        except Exception as e:
            # 进程池创建等错误
            self.signals.error.emit([f"进程创建错误：{e}", self.calculate_id])

    @staticmethod
    def _calculate(calculate_equation):
        """实际的计算函数在子进程中运行"""
        try:
            return str(eval(calculate_equation))
        except Exception as e:
            return str(e)


class CustomExecute(QRunnable):
    """用于执行自定义操作的 Runnable"""

    def __init__(self, execute_args):
        super().__init__()
        self.execute_args = execute_args

    def run(self):
        try:
            execute.custom_execute(self.execute_args)
        except Exception as e:
            log.write(f"执行操作时发生错误：{e}，操作：{self.execute_args}", 3)
