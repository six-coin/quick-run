# 扩展指南

本文说明几类常见改动该动哪些文件，以及改完之后必须满足的约定。

## 1. 新增一种操作类型

以新增 `shell`（在终端里执行 PowerShell 片段）为例。

### 1.1 领域模型

`app/models.py`：

```python
class OperationType:
    ...
    SHELL = "shell"

TYPE_ORDER = (..., OperationType.SHELL)

TYPE_DEFAULTS = {
    ...
    OperationType.SHELL: {"script": ""},
}

REQUIRED_ARGUMENT = {
    ...
    OperationType.SHELL: "script",
}
```

`TYPE_ORDER` 决定管理器里胶囊按钮的顺序，`TYPE_DEFAULTS` 决定新建时的初始参数，`REQUIRED_ARGUMENT` 决定保存时的必填校验。`normalize()` 里按需补一段路径 / 文本清理。

### 1.2 执行语义

`app/core/actions.py::ActionExecutor._external` 增加一个分支：

```python
elif operation.type == OperationType.SHELL:
    self._opener.run_command(
        f'powershell -NoProfile -Command "{operation.arguments.get("script", "")}"',
        cwd=paths.PROGRAM_DIR,
    )
```

如果新类型需要新的系统能力，先在 `Opener` 协议上加方法，再在 `app/system/shell.py::WindowsOpener` 里实现。测试时用假实现，不需要真的起进程。

### 1.3 管理器界面

`app/manager/web/index.html` 增加参数面板，`data-type` 必须与类型常量一致：

```html
<div class="arg-panel" data-type="shell">
  <div class="field">
    <label data-i18n="field.script">脚本</label>
    <input id="f-script" type="text" data-arg="script">
  </div>
</div>
```

`app/manager/web/app.js` 的 `FIELD_INPUTS` 里补上字段到输入框 id 的映射（用于把校验错误标到正确的控件上）。

### 1.4 文案

`app/locales/zh-CN.json` 与 `en-US.json` 都要加：

```json
"type.shell": "执行脚本",
"field.script": "脚本"
```

缺任何一条，其他语言界面会回退 `zh-CN`；两条都缺，界面会显示裸露的键名。

### 1.5 检查清单

- [ ] `TYPE_ORDER`、`TYPE_DEFAULTS`、`REQUIRED_ARGUMENT` 三处都改了
- [ ] 执行分支有对应的 `Opener` 方法
- [ ] 管理器参数面板的 `data-type` 与常量一致
- [ ] `FIELD_INPUTS` 有映射
- [ ] 中英文案都有 `type.*` 与 `field.*`
- [ ] `tests/test_manager_api.py` 里补一条新建 / 校验用例
- [ ] 跑 `pytest`

## 2. 新增一种语言

不需要改代码。`app/i18n.py` 启动时扫描 `app/locales/*.json`，文件名就是语言代码。

1. 复制 `app/locales/en-US.json`，重命名为目标代码，例如 `ja-JP.json`；
2. 逐条翻译值，键名与 `{name}` 占位符保持不变；
3. 重启管理器，设置弹窗的语言列表会自动多出一项。

想让它显示成「日本語」而不是 `ja-JP`，在 `app/i18n.py` 的 `_KNOWN_NAMES` 里登记：

```python
_KNOWN_NAMES = {"zh-CN": "中文", "en-US": "English", "ja-JP": "日本語"}
```

约定：

- 键名只增不改。删键要同步删所有语言文件，否则其他语言会留下孤儿条目。
- 占位符必须保持一致，`{name}` 不能写成 `{名称}`。
- 缺键会回退 `zh-CN`，所以可以先把文件放进去再补翻译。
- 新增语言后跑一遍 `pytest`，`tests/test_i18n.py` 会检查每份语言文件的键是否与默认语言一致。
- 英文缺键会回退中文，所以新增键时可以先只写中文，但要记着补。

## 3. 接入新的外部服务

以新增一个「天气」服务为例。

### 3.1 服务实现

放在 `app/core/services/weather.py`，只依赖 `requests` 与 `app.errors.ServiceError`：

```python
class WeatherService:
    def __init__(self, api_key: str, timeout: float = 5.0) -> None:
        ...

    def current(self, city: str) -> str:
        """失败时抛 ServiceError，由上层转成结果行文案。"""
```

不要在服务里弹窗、不要写日志文件、不要碰界面。

### 3.2 配置

`app/settings.py::AppConfig` 增加字段，并在 `from_dict` / `to_dict` 里读写。若需要夹取范围，参照 `clamp_depth` 的写法。

### 3.3 装配与调用

- `app/launcher/app.py` 里按配置决定是否创建实例，注入 `LauncherController`。
- 需要异步的，参照 `_start_translate` 的写法：先塞一行 `LOADING`，再 `self._tasks.submit(...)`，回包时用代次过滤。
- 需要新 `RowKind` 的，在 `app/core/rows.py` 里加枚举值，并在 `ActionExecutor.execute` 的分派表里加处理函数。

### 3.4 管理器设置项

- `app/manager/api.py::get_settings` 返回新字段。
- `update_settings` 里接收并写盘。
- `app/manager/web/index.html` 的 `#modal-settings` 增加输入框，`app.js` 的 `bindSettingInput` 里绑定。

## 4. 修改管理器界面

前端是三个静态文件，没有构建步骤，改完刷新窗口即可看到效果。

| 文件 | 内容 |
|---|---|
| `index.html` | 结构与静态文案（用 `data-i18n*` 标记） |
| `styles.css` | 全部样式，颜色走 CSS 变量，深色模式在 `[data-theme="dark"]` 里覆盖 |
| `app.js` | 渲染与事件，所有文案走 `T("键")` |

约定：

- 不要在前端维护业务数据。状态只来自 `get_state()` 的返回值，前端只保留折叠状态这类纯视图状态。
- 新增静态文案时用 `data-i18n` 系列属性，不要写死中文。
- 新增颜色时先加 CSS 变量，再在深色主题里给出对应值，否则深色模式下会看不清。
- 列表的键盘导航依赖 `[data-node]` 与 roving tabindex，新增可聚焦元素时要考虑是否会破坏「整张列表一个 Tab 停靠点」的约定。

## 5. 代码约定

| 约定 | 说明 |
|---|---|
| 注释与文档字符串用中文 | 包括标点。变量名、函数名保持英文 |
| 注释只写「现在为什么这样」 | 记录设计原因，不记录改动过程 |
| 不调用 `os.chdir` | 需要工作目录就传参数 |
| 内部路径从 `app/paths.py` 取 | 不要在模块里自己拼 `Path("config")` |
| 面向用户的文本走 `i18n.t()` | 异常信息也一样 |
| 捕获异常要有具体理由 | 说明为什么这里能吞掉，以及吞掉之后用户看到什么 |

提交前跑：

```bat
.venv\Scripts\python -m pytest
```

`tests/test_source_hygiene.py` 会顺带检查所有文件能否解析、有没有 `chdir`、核心层有没有混进界面依赖。
