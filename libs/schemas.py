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
            "display",
            "type",
            "arguments",
            "keywords"
        ],
        "properties": {
            "display": {"type": str},
            "type": {"type": str},
            "arguments": {"type": dict},
            "keywords": {"type": str}
        }
    },
    "default": [
        {
            "display": "重启程序",
            "type": "debug",
            "keywords": "sys:restart|restart",
            "arguments": {"function": "restart"}
        },
        {
            "display": "关闭程序",
            "type": "debug",
            "keywords": "sys:close|close",
            "arguments": {"function": "close"}
        },
        {
            "display": "操作管理与帮助",
            "type": "file",
            "keywords": "sys:manager|manager|sys:help|help",
            "arguments": {"path": "manager.pyw", "no_window": False}
        },
        {
            "display": "打开程序文件夹",
            "type": "dir",
            "keywords": "sys:folder|folder",
            "arguments": {"dir": "E:\\Play\\Utilities\\Fast Run"}
        },
        {
            "display": "打开启动文件夹",
            "type": "dir",
            "keywords": "sys:startup|startup",
            "arguments": {"dir": "C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\Startup"}
        },
        {
            "display": "调试：运行开机启动文件",
            "type": "file",
            "keywords": "debug:startup_file",
            "arguments": {"path": "C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\run.pyw",
                          "no_window": False}
        },
        {
            "display": "调试：关闭所有正在运行的 Python 程序并重启",
            "type": "file",
            "keywords": "debug:close_python",
            "arguments": {"path": "custom\\debug.bat", "no_window": True}
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
