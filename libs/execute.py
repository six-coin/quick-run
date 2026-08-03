import os
import subprocess
import webbrowser
import winreg

from libs import log
from libs import text_to_speech


def custom_execute(execute_args):
    def check_proxy():
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        return proxy_enable

    def any_special_key_pressed():
        return "alt_pressed" in key_pressed or "shift_pressed" in key_pressed or "ctrl_pressed" in key_pressed

    def open_dir(target_dirs):
        """打开路径文件夹"""
        target_dirs = target_dirs.split("|")
        for target_dir in target_dirs:
            target_dir = os.path.abspath(target_dir)  # 自动将相对路径转化为绝对路径
            if os.path.exists(target_dir) and os.path.isdir(target_dir):
                os.startfile(target_dir)
            else:
                log.write(f"打开路径 {target_dir} 时出错：路径不存在或不是路径", 2)

    def open_file(file_paths):
        """用系统默认方式打开文件"""
        file_paths = file_paths.split("|")
        for file_path in file_paths:
            file_path = os.path.abspath(file_path)  # 自动将相对路径转化为绝对路径
            if any_special_key_pressed():
                open_dir(os.path.dirname(file_path))
                continue
            if os.path.exists(file_path) and os.path.isfile(file_path):
                file_cwd = os.path.dirname(file_path)
                original_cwd = os.getcwd()  # 当前目录
                try:
                    os.chdir(file_cwd)  # 将文件目录作为其运行目录
                    if "no_window" in run_arguments:
                        subprocess.Popen([file_path], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    else:
                        os.startfile(file_path)
                except Exception as e:
                    log.write(f"打开文件{file_path}时出错：{e}", 2)
                finally:
                    os.chdir(original_cwd)  # 恢复原目录
            else:
                log.write(f"打开文件{file_path}时出错：文件不存在或不是文件", 2)

    def execute_search(search_text):
        """执行搜索：默认使用必应，如果按下 Shift 键则使用百度"""
        if check_proxy():
            url = f"https://www.baidu.com/s?wd={search_text}"
        else:
            url = f"https://cn.bing.com/search?q={search_text}"
        webbrowser.open(url)

    def execute_translate(translate_text):
        """执行翻译：如果纯 ascii 则英译中，否则中译英"""
        if any_special_key_pressed() and len(translate_text) < 1000:
            text_to_speech.text_to_speech(translate_text)
            return

        url = f"https://fanyi.baidu.com/mtpe-individual/transText?query={translate_text}&lang=auto2auto#/"
        webbrowser.open(url)

    display_name = execute_args[0]
    run_type = execute_args[1]
    run_content = execute_args[2]
    run_arguments = execute_args[3]
    key_pressed = execute_args[5]
    if run_type == "file":
        open_file(run_content)
        log.write(f"操作成功执行：{display_name}（file）", 3)
    elif run_type == "dir":
        open_dir(run_content)
        log.write(f"操作成功执行：{display_name}（dir）", 3)
    elif run_type == "url":
        webbrowser.open(run_content)
        log.write(f"操作成功执行：{display_name}（url）", 3)
    elif run_type == "cmd":
        os.system(run_content)
        log.write(f"操作成功执行：{display_name}（cmd）", 3)
    elif run_type == "special" and "search" in run_arguments:
        execute_search(run_content)
        log.write(f"操作成功执行：搜索", 3)
    elif run_type == "special" and "translate" in run_arguments:
        execute_translate(run_content)
        log.write(f"操作成功执行：翻译", 3)
    else:
        log.write(f"执行了未定义的操作，参数：{execute_args}", 1)
    return
