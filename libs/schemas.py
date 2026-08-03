from pathlib import Path

config_dir = Path("config")
operations_path = config_dir / "operations.json"
translate_path = config_dir / "translate.json"
ai_path = config_dir / "ai.json"

operations_schema = {
    "type": list,
    "min_length": 1,
    "items": {
        "type": dict,
        "required": [
            "run_type",
            "run_content",
            "display_name",
            "run_arguments",
            "search_keywords"
        ],
        "properties": {
            "run_type": {"type": str},
            "run_content": {"type": str},
            "display_name": {"type": str},
            "run_arguments": {"type": str},
            "search_keywords": {"type": str}
        }
    },
    "default": [
        {
            "display_name": "重启程序",
            "run_type": "debug",
            "run_content": "-",
            "run_arguments": "restart",
            "search_keywords": "sys:restart|restart"
        },
        {
            "display_name": "关闭程序",
            "run_type": "debug",
            "run_content": "-",
            "run_arguments": "close",
            "search_keywords": "sys:close|close"
        },
        {
            "display_name": "操作管理与帮助",
            "run_type": "file",
            "run_content": "manager.py",
            "run_arguments": "",
            "search_keywords": "sys:manager|manager|sys:help|help"
        },
        {
            "display_name": "打开程序文件夹",
            "run_type": "dir",
            "run_content": "E:\\Play\\Utilities\\Fast Run",
            "run_arguments": "",
            "search_keywords": "sys:folder|folder"
        },
        {
            "display_name": "打开启动文件夹",
            "run_type": "dir",
            "run_content": "C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\Startup",
            "run_arguments": "",
            "search_keywords": "sys:startup|startup"
        },
        {
            "display_name": "调试：运行开机启动文件",
            "run_type": "file",
            "run_content": "C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\run.pyw",
            "run_arguments": "",
            "search_keywords": "debug:startup_file"
        },
        {
            "display_name": "调试：关闭所有正在运行的 Python 程序并重启",
            "run_type": "file",
            "run_content": "custom\\debug.bat",
            "run_arguments": "no_window",
            "search_keywords": "debug:close_python"
        }
    ]
}
translate_schema = {
    "type": dict,
    "required": ["appid", "secret_key"],
    "properties": {
        "appid": {"type": str, "default": ""},
        "secret_key": {"type": str, "default": ""}
    }
}
ai_schema = {
    "type": dict,
    "required": ["api_key"],
    "properties": {
        "api_key": {"type": str, "default": ""}
    }
}
