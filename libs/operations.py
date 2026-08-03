import os
import time
import pyperclip

from PySide6.QtCore import QThreadPool

from libs import explorer
from libs import log
from libs import runnable


def _norm(text):
    result = []
    for ch in text.lower():
        if 'a' <= ch <= 'z' or '0' <= ch <= '9':
            result.append(ch)
    return "".join(result)


class Operation:
    def __init__(self):
        self.display = ""
        self.is_internal = False
        self.is_external = False

    def execute(self, key_pressed):
        pass


class ExternalOperation(Operation):
    def __init__(self, data: dict):
        super().__init__()
        self.is_external = True
        self.display = data["display"]
        self.type = data["type"]
        self.arguments = data["arguments"]
        self.keywords = data["keywords"].split("|")

    def validate_search(self, search_text: str) -> bool:
        lower_text = search_text.lower()
        return any(kw.startswith(lower_text) for kw in self.keywords)

    def execute(self, key_pressed):
        if self.type == "debug":
            runnable_instance = runnable.DebugRunnable(self.arguments.get("function", ""))
            runnable_instance.run()
            return

        if self.type == "file":
            r = runnable.OpenFileRunnable(
                self.arguments.get("path", ""),
                self.arguments.get("no_window", False),
                key_pressed
            )
            QThreadPool.globalInstance().start(r)
            log.write(f"操作成功执行：{self.display}（file）", 3)
        elif self.type == "url":
            r = runnable.OpenUrlRunnable(self.arguments.get("url", ""))
            QThreadPool.globalInstance().start(r)
            log.write(f"操作成功执行：{self.display}（url）", 3)
        elif self.type == "cmd":
            r = runnable.RunCmdRunnable(self.arguments.get("command", ""))
            QThreadPool.globalInstance().start(r)
            log.write(f"操作成功执行：{self.display}（cmd）", 3)


class DirOperation(ExternalOperation):
    def __init__(self, data: dict):
        super().__init__(data)
        self.is_external = True
        self.allow_explore = data["arguments"].get("allow_explore", True)
        self.explore_depth = data["arguments"].get("explore_depth", 0)
        self._explore_root = None
        self.keywords = [_norm(kw) for kw in self.keywords]

    def validate_search(self, search_text: str) -> bool:
        lower_text = _norm(search_text)
        if not lower_text:
            return False
        return any(kw.startswith(lower_text) for kw in self.keywords)

    def execute(self, key_pressed):
        r = runnable.OpenDirRunnable(self.arguments.get("dir", ""))
        QThreadPool.globalInstance().start(r)
        log.write(f"操作成功执行：{self.display}（dir）", 3)

    def build_tree(self):
        if self.allow_explore:
            self._explore_root = explorer.scan_root(
                self.arguments.get("dir", ""), self.explore_depth
            )


class InternalOperation(Operation):
    def __init__(self, window):
        super().__init__()
        self.is_internal = True
        self.type = ""
        self._window = window

    def update_display(self, new_display: str, row: int):
        self.display = new_display
        window = self._window
        visible_row = row - window.visible_start
        if 0 <= visible_row < window.result_list_widget.count():
            window.result_list_widget.item(visible_row).setText(new_display)
        if 0 <= row < len(window.filtered_operations):
            window.filtered_operations[row].display = new_display

    def execute(self, key_pressed):
        pass


class SearchOperation(InternalOperation):
    def __init__(self, search_text, window):
        super().__init__(window)
        self.type = "search"
        self._search_text = search_text
        self.display = f"搜索：{search_text}"

    def execute(self, key_pressed):
        r = runnable.SearchRunnable(self._search_text)
        QThreadPool.globalInstance().start(r)
        log.write("操作成功执行：搜索", 3)


class TranslateOperation(InternalOperation):
    def __init__(self, text, translate_config, window, is_live=True):
        super().__init__(window)
        self.type = "translate"
        self._text = text
        self._translate_config = translate_config
        self.translate_id = int(time.time() * 1000) if is_live else None
        if is_live:
            self.display = "翻译：等待中..."
        else:
            self.display = f"翻译：{text}"

    def start_fetch(self, row: int):
        self.update_display("翻译：加载中...", row)
        r = runnable.TranslateRunnable(
            text=self._text,
            appid=self._translate_config["appid"],
            secret_key=self._translate_config["secret_key"],
            translate_id=self.translate_id
        )
        window = self._window
        r.signals.success.connect(lambda rlist, r=row: window._on_translate_success(rlist, r))
        r.signals.error.connect(lambda rlist, r=row: window._on_translate_error(rlist, r))
        QThreadPool.globalInstance().start(r)

    def execute(self, key_pressed):
        r = runnable.TranslateExecuteRunnable(self._text, key_pressed)
        QThreadPool.globalInstance().start(r)
        log.write("操作成功执行：翻译", 3)


class CalculateOperation(InternalOperation):
    def __init__(self, text, window):
        super().__init__(window)
        self.type = "calculate"
        self._equation = text
        self.calculate_id = int(time.time() * 1000)
        self.calculate_status = 0
        self._result = text

    def try_simple_calc(self) -> bool:
        if not all(c in set("0123456789 .+-*/()") for c in self._equation):
            return False
        if "**" in self._equation or len(self._equation) >= 20:
            return False
        try:
            result = str(eval(self._equation))
            self._result = result
            self.calculate_status = 2
            self.display = f"计算：{result}"
            return True
        except Exception as e:
            self._result = str(e)
            self.calculate_status = 3
            self.display = f"计算：{str(e)}"
            return True

    def start_fetch(self, row: int):
        r = runnable.CalculateRunnable(
            calculate_equation=self._equation,
            calculate_id=self.calculate_id
        )
        window = self._window
        r.signals.success.connect(lambda rlist, r=row: window._on_calculate_success(rlist, r))
        r.signals.error.connect(lambda rlist, r=row: window._on_calculate_error(rlist, r))
        QThreadPool.globalInstance().start(r)

    def execute(self, key_pressed):
        if self.calculate_status == 2:
            pyperclip.copy(self._result)


class DefinitionOperation(InternalOperation):
    def __init__(self, text, api_key, window):
        super().__init__(window)
        self.type = "definition"
        self._text = text
        self._api_key = api_key
        self._definition_id = None
        self.definition_status = 0  # 0: 未开始, 1: 进行中, 2: 成功, 3: 错误
        self.display = f"查词：{text}（回车或双击开始查词）"

    def start_fetch(self, row: int):
        self.definition_status = 1
        self._definition_id = int(time.time() * 1000)
        self.update_display("查词：加载中...", row)
        r = runnable.DefinitionRunnable(
            text=self._text,
            api_key=self._api_key,
            definition_id=self._definition_id
        )
        window = self._window
        r.signals.success.connect(lambda rlist, r=row: window._on_definition_success(rlist, r))
        r.signals.error.connect(lambda rlist, r=row: window._on_definition_error(rlist, r))
        QThreadPool.globalInstance().start(r)

    def execute(self, key_pressed):
        if self.definition_status in (0, 3):
            row = self._window._find_operation_row(self)
            if row >= 0:
                self.start_fetch(row)
            log.write("操作成功执行：查词", 3)
        elif self.definition_status == 2:
            pyperclip.copy(self._result)
            self._window._hide_and_reset()

    def set_result(self, result_text: str):
        self._result = result_text


class ExploreOperation(InternalOperation):
    def __init__(self, entry, window):
        super().__init__(window)
        self.type = "explore"
        self.entry = entry
        prefix = "文件夹：" if entry.is_dir else "文件："
        self.display = f"{prefix}{entry.name}"

    def execute(self, key_pressed):
        if self.entry.is_dir:
            os.startfile(self.entry.full_path)
        else:
            r = runnable.OpenFileRunnable(self.entry.full_path, False, key_pressed)
            QThreadPool.globalInstance().start(r)
        self._window.hide_window()
        self._window._reset_internal_state()


class ErrorOperation(InternalOperation):
    def __init__(self, message, window):
        super().__init__(window)
        self.type = "error"
        self.display = f"错误：{message}"

    def execute(self, key_pressed):
        self._window.hide_window()
        self._window._reset_internal_state()
