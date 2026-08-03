import datetime
import os
import pathlib
import subprocess

log_file_path = pathlib.Path("")


def init(prefix=None):
    global log_file_path
    prefix = f"{prefix}_" if prefix else ""
    log_file_path = pathlib.Path("logs") / f"{prefix}{_get_time()}.log"
    log_file_path.resolve()
    _new_file(log_file_path)
    write(f"已初始化日志文件：{log_file_path}", 3)


def write(log_content, log_level):
    if log_file_path == pathlib.Path(""):
        return
    if not log_file_path.exists():
        _new_file(log_file_path)
        write(f"原日志文件被删除，重新创建：{log_file_path}", 2)
    log_level_name = {0: "FATAL", 1: "ERROR", 2: "WARN", 3: "INFO", 4: "DEBUG"}.get(log_level, "UNKNOWN")
    write_content = f"[{log_level_name}] [{_get_time()}] {log_content}\n"
    try:
        with open(log_file_path, "a", encoding="utf-8") as file_content:
            file_content.write(write_content)
    except Exception as e:
        error(f"写入日志时发生错误：{e}")


def error(error_message):
    crash_report = ("cmd /c echo ========崩溃报告======== &"
                    "echo 程序在运行中出现错误，无法继续执行 &"
                    f"echo 当前时间：{_get_time()} &"
                    f"echo 工作目录：{_safe_echo(str(pathlib.Path.cwd()))} &"
                    f"echo 日志文件：{log_file_path} &"
                    f"echo 错误信息：{_safe_echo(error_message)} &"
                    f"pause")
    subprocess.Popen(crash_report)
    os._exit(0)


def _safe_echo(text):
    special = set("^&|<>%!")
    result = []
    for ch in text:
        if ch in special:
            result.append("^" + ch)
        elif ch == "\n" or ch == "\r":
            result.append(" ")
        else:
            result.append(ch)
    return "".join(result)


def _get_time():
    return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _new_file(file_path):
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()
    except Exception as e:
        error(f"创建日志时发生错误：{e}")
