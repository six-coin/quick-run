"""领域异常。

集中放在一个模块里，界面层只需要捕获一个基类，核心层则完全不用关心
“怎么把错误显示给用户”。
"""

from __future__ import annotations


class AppError(Exception):
    """本程序抛出的所有异常的基类。"""


class ConfigError(AppError):
    """配置文件缺失、读不出来，或者结构不合法。"""


class CalcError(AppError):
    """表达式算不出来（语法错误、溢出、超时）。"""


class ServiceError(AppError):
    """远程服务（翻译 / 查词 / 朗读）调用失败。"""


class ActionError(AppError):
    """动作执行失败（文件不存在、进程启动失败）。"""
