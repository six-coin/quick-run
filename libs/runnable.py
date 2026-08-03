import hashlib
import multiprocessing
import os
import subprocess
import time
import webbrowser
import winreg

import requests
from PySide6.QtCore import QRunnable, Signal, QObject

from libs import ai
from libs import log
from libs import text_to_speech


class Signals(QObject):
    success = Signal(list)
    error = Signal(list)


class TranslateRunnable(QRunnable):
    def __init__(self, text, appid, secret_key, translate_id):
        super().__init__()
        self.text = text
        self.appid = appid
        self.secret_key = secret_key
        self.translate_id = translate_id
        self.signals = Signals()

    def run(self):
        try:
            salt = str(int(time.time() * 1000))
            sign_str = self.appid + self.text + salt + self.secret_key
            sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
            params = {"q": self.text, "from": "auto", "to": "auto", "appid": self.appid, "salt": salt, "sign": sign}
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
    def __init__(self, text, api_key, definition_id):
        super().__init__()
        self.text = text
        self.api_key = api_key
        self.definition_id = definition_id
        self.signals = Signals()

    def run(self):
        try:
            definition_result = ai.find_definition(self.text, self.api_key)
            self.signals.success.emit([definition_result, self.definition_id])
        except Exception as e:
            self.signals.error.emit([str(e), self.definition_id])


class CalculateRunnable(QRunnable):
    def __init__(self, calculate_equation, calculate_id):
        super().__init__()
        self.calculate_equation = calculate_equation
        self.calculate_id = calculate_id
        self.signals = Signals()
        self.calculate_timeout = 2

    def run(self):
        try:
            with multiprocessing.Pool(processes=1) as pool:
                async_result = pool.apply_async(self._calculate, (self.calculate_equation,))
                try:
                    calculate_result = async_result.get(timeout=self.calculate_timeout)
                    if len(calculate_result) > 5000:
                        raise Exception("结果过长")
                    self.signals.success.emit([calculate_result, self.calculate_id])
                except multiprocessing.TimeoutError:
                    pool.terminate()
                    pool.join()
                    self.signals.error.emit(["计算超时", self.calculate_id])
                except Exception as e:
                    self.signals.error.emit([f"发生错误：{e}", self.calculate_id])
        except Exception as e:
            self.signals.error.emit([f"进程创建错误：{e}", self.calculate_id])

    @staticmethod
    def _calculate(calculate_equation):
        try:
            return str(eval(calculate_equation))
        except Exception as e:
            return str(e)


class OpenFileRunnable(QRunnable):
    def __init__(self, path, no_window, key_pressed):
        super().__init__()
        self.path = path
        self.no_window = no_window
        self.key_pressed = key_pressed

    def run(self):
        file_paths = self.path.split("|")
        for file_path in file_paths:
            file_path = os.path.abspath(file_path)
            if any(k in self.key_pressed for k in ("alt_pressed", "shift_pressed", "ctrl_pressed")):
                target_dir = os.path.dirname(file_path)
                if os.path.exists(target_dir) and os.path.isdir(target_dir):
                    os.startfile(target_dir)
                continue
            if os.path.exists(file_path) and os.path.isfile(file_path):
                file_cwd = os.path.dirname(file_path)
                original_cwd = os.getcwd()
                try:
                    os.chdir(file_cwd)
                    if self.no_window:
                        subprocess.Popen([file_path], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    else:
                        os.startfile(file_path)
                except Exception as e:
                    log.write(f"打开文件{file_path}时出错：{e}", 2)
                finally:
                    os.chdir(original_cwd)
            else:
                log.write(f"打开文件{file_path}时出错：文件不存在或不是文件", 2)


class OpenDirRunnable(QRunnable):
    def __init__(self, dir_path):
        super().__init__()
        self.dir_path = dir_path

    def run(self):
        target_dirs = self.dir_path.split("|")
        for target_dir in target_dirs:
            target_dir = os.path.abspath(target_dir)
            if os.path.exists(target_dir) and os.path.isdir(target_dir):
                os.startfile(target_dir)
            else:
                log.write(f"打开路径 {target_dir} 时出错：路径不存在或不是路径", 2)


class OpenUrlRunnable(QRunnable):
    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        webbrowser.open(self.url)


class RunCmdRunnable(QRunnable):
    def __init__(self, command):
        super().__init__()
        self.command = command

    def run(self):
        os.system(self.command)


class SearchRunnable(QRunnable):
    def __init__(self, search_text):
        super().__init__()
        self.search_text = search_text

    def run(self):
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        except Exception:
            proxy_enable = False
        if proxy_enable:
            url = f"https://www.baidu.com/s?wd={self.search_text}"
        else:
            url = f"https://cn.bing.com/search?q={self.search_text}"
        webbrowser.open(url)


class TranslateExecuteRunnable(QRunnable):
    def __init__(self, translate_text, key_pressed):
        super().__init__()
        self.translate_text = translate_text
        self.key_pressed = key_pressed

    def run(self):
        if any(k in self.key_pressed for k in ("alt_pressed", "shift_pressed", "ctrl_pressed")) \
                and len(self.translate_text) < 1000:
            text_to_speech.text_to_speech(self.translate_text)
            return
        url = f"https://fanyi.baidu.com/mtpe-individual/transText?query={self.translate_text}&lang=auto2auto#/"
        webbrowser.open(url)


class DebugRunnable(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function

    def run(self):
        if self.function == "restart":
            os.startfile("main.pyw")
            log.write("操作成功执行：重启程序", 3)
            os._exit(0)
        elif self.function == "close":
            log.write("操作成功执行：关闭程序", 3)
            os._exit(0)
