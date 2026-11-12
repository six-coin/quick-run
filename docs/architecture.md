# 架构设计

本文给维护者看：程序怎么分层、依赖朝哪个方向走、关键流程如何串起来，以及哪些约定由测试强制保证。

## 1. 目标与约束

Quick Run 有两个独立进程：

- **启动器**（`main.pyw`）：常驻后台，`Alt+Space` 唤出一个无边框搜索框，回车执行操作。
- **快捷运行操作管理器**（Quick Run Manager，`manager.pyw`）：按需打开的网页界面，维护操作清单。

两者共享同一份配置和同一套领域模型，但界面技术栈不同（Qt 与 WebView2），因此代码必须让「业务逻辑」与「界面」彻底分离，否则任何一处改动都要写两遍。

硬约束：

| 约束 | 原因 |
|---|---|
| 进程内不调用 `os.chdir` | 工作目录是进程级全局状态，被多线程共享。一旦切换，其他线程写相对路径就会落到别处 |
| 所有内部路径由 `__file__` 推导 | 程序从任何目录启动、被任何快捷方式拉起，行为一致 |
| `app/core` 不导入任何界面库 | 核心逻辑要能被纯 pytest 覆盖，也要能被两个界面共用 |
| 入口文件保持极薄 | 装配集中在 `app/launcher/app.py` 与 `app/manager/app.py` |

前三条由 `tests/test_source_hygiene.py` 静态扫描强制，第四条由 `test_entry_points_are_thin` 限制行数。

## 2. 目录结构

```
main.pyw / manager.pyw        入口薄壳
main.bat / manager.bat        用虚拟环境启动
setup.bat                     安装依赖

app/
├─ paths.py                  全部路径的唯一来源
├─ errors.py                 异常类型
├─ models.py                 领域模型：Operation / OperationGroup / 字段校验
├─ settings.py               配置读写与校验
├─ i18n.py                   文案查表
├─ logging_setup.py          loguru 初始化与致命错误处理
├─ locales/                  zh-CN.json / en-US.json（文件名即语言代码）
├─ core/                     纯逻辑，零界面依赖
│  ├─ matching.py            归一化、拼音、前缀匹配位置
│  ├─ catalog.py             操作索引与前缀匹配
│  ├─ navigation.py          文件夹浏览语法
│  ├─ resolver.py            查询 → 结果行
│  ├─ calculator.py          AST 白名单求值
│  ├─ actions.py             结果行 → 副作用
│  ├─ rows.py                ResultRow / RowKind / RowStatus
│  └─ services/              翻译、查词、朗读、搜索链接
├─ system/                   唯一直接接触 Windows 的地方
│  ├─ shell.py               启动文件 / 文件夹 / 网址 / 命令
│  ├─ hotkey.py              全局热键线程
│  ├─ taskbar.py             全屏时隐藏任务栏
│  ├─ clipboard.py           剪贴板
│  └─ theme.py               读取系统明暗偏好
├─ launcher/                 Qt 启动器
│  ├─ app.py                 组装根
│  ├─ controller.py          交互状态机
│  ├─ window.py              视图
│  ├─ tasks.py               后台任务、动作执行与代次
│  └─ theme.py               两套 Qt 样式表
└─ manager/                  pywebview 管理器
   ├─ app.py                 组装根与关闭拦截
   ├─ api.py                 暴露给网页的全部接口
   ├─ dialogs.py             原生兜底对话框
   └─ web/                   index.html / styles.css / app.js
```

## 3. 分层与依赖方向

```
        main.pyw              manager.pyw
            │                     │
     app/launcher           app/manager
       (Qt 视图)            (网页 + pywebview)
            │                     │
            └────────┬────────────┘
                     ▼
                app/core            纯逻辑：解析、匹配、求值、执行语义
                     │
                     ▼
        models / settings / errors / i18n / paths
                     ▲
                     │
                app/system          系统集成：进程、注册表、剪贴板
```

规则：

1. **依赖只朝下**。`core` 不知道 `launcher` 与 `manager` 的存在；`system` 不知道谁在调用它。
2. **`core` 只依赖纯模块**（`models`、`errors`、`i18n`、`paths`）和标准库。
3. **`system` 不依赖界面库**，可以被任意一侧复用。
4. **跨层通信靠参数与返回值**，不用全局状态。`ActionExecutor` 通过 `Opener` 协议拿到底层能力，测试时换成假实现即可。

`app/settings.py` 会调用 `app/system/theme.py` 读取一次系统外观——这是唯一一处配置层反向依赖系统层的地方，只发生在首次生成配置文件时。

## 4. 模块职责

| 模块 | 职责 | 不做什么 |
|---|---|---|
| `paths` | 计算所有路径；把配置里的相对路径按程序目录解析 | 不判断文件是否存在 |
| `settings` | 读写两个 JSON、校验结构、夹取数值范围 | 不缓存，不持有界面状态 |
| `models` | 数据结构、类型常量、字段校验、写盘前归一化 | 不读写文件 |
| `i18n` | 扫描语言目录、按语言查表、填充占位符 | 不关心调用者是谁 |
| `core.matching` | 字符串归一化与拼音 | 不做 I/O |
| `core.catalog` | 前缀匹配、找可浏览的文件夹操作 | 不执行操作 |
| `core.navigation` | 解析浏览语法、逐层列目录 | 不打开任何东西 |
| `core.resolver` | 决定显示哪些行、哪些要异步发起 | 不发起请求 |
| `core.calculator` | 安全求值 | 不弹窗 |
| `core.actions` | 把结果行变成副作用，返回「是否收起」「要复制什么」 | 不碰窗口 |
| `system.shell` | 启动进程，工作目录用参数传递 | 不改进程状态 |
| `launcher.controller` | 查询、选中、历史、防抖、代次 | 不碰控件 |
| `launcher.window` | 渲染信号、键盘映射、窗口动画 | 不做业务判断 |
| `manager.api` | 每个用户意图一个方法，返回完整状态快照 | 不拼 HTML |
| `manager.web` | 纯渲染器，状态从 `get_state()` 来 | 不自己维护业务数据 |

## 5. 关键流程

### 5.1 启动器启动

`app/launcher/app.py::main` 是唯一的装配点：

```
setup 日志
  → load_settings()              读 app.json + operations.json，切换语言
  → Catalog(operations)          按分组顺序展平、跳过关闭的分组
  → QueryResolver(catalog, navigator, ai_key, translate_enabled)
  → QApplication
  → LauncherController(resolver, executor, clipboard, translator, definition)
  → SearchWindow(controller, theme.for_theme(config.theme),
                 fade_in_ms=config.animation_in_ms, fade_out_ms=config.animation_out_ms)
  → HotkeyListener(bridge.triggered.emit)   独立线程注册 Alt+Space
  → app.exec()
```

热键回调发生在 Win32 线程，不能直接操作 Qt 控件，因此经过一个 `_HotkeyBridge(QObject)` 把调用转成 Qt 信号，由 Qt 线程执行 `window.show_window()`。

### 5.2 一次查询的解析

`QueryResolver.resolve` 是一条严格的优先级链：

| 顺序 | 条件 | 结果 |
|---|---|---|
| 1 | 全是空白 | 空列表 |
| 2 | 以 `` ` `` 结尾 | 只给内置行（搜索 / 计算 / 查词 / 翻译） |
| 3 | 以 `#` 结尾且长度 > 1 | 去掉 `#` 重新解析（避免输入 `a#2` 途中列表跳变） |
| 4 | 含空格且前半段是可浏览的文件夹操作 | 目录浏览 |
| 5 | 含空格且整串命中操作 | 操作行 |
| 6 | 不含空格且形如 `关键词#n` | 只显示第 n 个匹配项 |
| 7 | 命中操作 | 操作行 |
| 8 | 其他 | 内置行 |

内置行最多四条：搜索（总是有）、计算（输入像算式时）、查词（配了 AI Key 时）、翻译（配了百度凭据且文本不超过 30 字时）。计算与翻译会额外返回 `PendingRequest`，由控制器延迟发起。

### 5.3 结果执行

`ActionExecutor.execute(row, modifiers)` 按 `RowKind` 分派：

| 行类型 | 行为 |
|---|---|
| `EXTERNAL` | 按操作类型打开文件 / 文件夹 / 网址，或执行命令 |
| `EXPLORE` | 打开浏览列表里的条目 |
| `SEARCH` | 打开必应搜索结果 |
| `CALCULATE` / `DEFINITION` | 算完了就返回要复制的文本并收起 |
| `TRANSLATE` | 带修饰键则朗读，否则打开百度翻译页面 |
| `ERROR` | 直接收起 |

返回值 `ActionOutcome(hide, clipboard_text)` 让「要不要收起窗口」和「复制什么」变成纯数据，窗口只负责执行这两个动作。

打开文件、网址、朗读这几类动作**不在界面线程上跑**。它们最终都落到 `ShellExecuteW` 或网络请求上，而 `ShellExecuteW` 要等到关联程序回应才返回：浏览器走 DDE 要等握手，慢的 exe 还要先被安全软件扫一遍。这段时间如果占着界面线程，窗口就僵在满不透明的状态，用户看到的是「按了回车没反应」。所以顺序是：

```
控制器：先发 hide_requested（窗口开始淡出）
      → ActionRunner 把执行丢进线程池
      → 工作线程跑完，ActionOutcome 通过信号回到界面线程
      → 界面线程只做「复制到剪贴板」这类不能跨线程的动作
```

窗口动画没有被取消，只是**不再是卡顿的来源**。`hide_for_action`（执行动作）和 `hide_window`（`Esc`、失去焦点）走同一条淡出，时长取自配置里的 `animation.out_ms`，淡入则用 `animation.in_ms`——动画快慢是用户偏好，不是性能开关；真正决定手感的是界面线程有没有被占住。

收起之前会调用一次 `AllowSetForegroundWindow`：窗口一没，启动器就不再是前台进程，按 Windows 的规则它拉起来的程序没有资格抢前台，新窗口会开在别的窗口后面。把这份权利先让出去，目标程序才能正常出现在最前面。

### 5.4 异步任务与代次

`LauncherController` 每次查询变化都会把 `_generation` 加一。`TaskRunner` 把任务丢进 `QThreadPool`，回包时带上提交时的代次；控制器只接受与当前代次相同的回包，其余直接丢弃。

这样不需要取消正在跑的请求，也不会出现「上一次查询的结果覆盖当前列表」。`QRunnable` 在完成前保持引用，防止 Qt 还在执行时 Python 包装对象被回收。

### 5.5 管理器的状态快照

`ManagerApi` 的每个方法都返回 `_state()` 的完整快照：

```json
{
  "ok": true,
  "message": "",
  "groups": [{ "index": 0, "name": "常用", "enabled": true, "count": 3, "operations": [...] }],
  "selection": { "kind": "operation", "group": 0, "index": 1 },
  "total": 48,
  "enabled_total": 46,
  "dirty": false,
  "errors": [{ "group": 0, "index": 1, "field": "keywords", "label": "匹配字串" }],
  "types": [...],
  "debug_functions": [...],
  "language": "zh-CN",
  "theme": "light",
  "navigation": { "max_depth": 5, "max_entries": 100 }
}
```

前端拿到快照后整体重绘。它不维护业务数据，只保留「哪些分组被折叠」这类纯视图状态。这样后端不需要知道 DOM，前端也不需要知道规则。

坐标统一用 `(group, index)` 二元组，没有「当前组」这种隐含状态，任何方法都必须显式说明操作对象。

### 5.6 关闭确认

`window.events.closing` 在 UI 线程执行，此时调用 `evaluate_js` 会等待同一个正在执行回调的消息循环，形成死锁。因此拆成三步：

```
closing 回调（UI 线程）
  → api.request_close_prompt()      起一个工作线程
  → return False                    取消本次关闭

工作线程
  → evaluate_js("window.quickRun.askUnsaved()")
  → 页面弹出自己的三选一对话框

页面
  → answer_close("close" | "cancel")
  → force_close() 或什么都不做
```

页面不可用（渲染进程崩溃、脚本报错）时，`evaluate_js` 返回假值，自动退回原生 `MessageBoxW`，保证窗口永远关得掉。

## 6. 线程模型

| 线程 | 归属 | 做什么 |
|---|---|---|
| Qt 主线程 | 启动器 | 全部界面操作、窗口动画、结果渲染 |
| 热键线程 | `HotkeyListener` | `RegisterHotKey` + `GetMessage` 循环，只发信号 |
| 线程池 | `QThreadPool` | 计算、翻译、查词、执行动作，结果通过信号回到主线程 |
| pywebview UI 线程 | 管理器 | 窗口消息循环 |
| js_api 线程 | 管理器 | 每次网页调用一个线程，执行 `ManagerApi` 方法 |
| 关闭提示线程 | 管理器 | 只做一次 `evaluate_js`，随后退出 |

跨线程只传数据，不传控件。启动器用 Qt 信号，管理器用返回值。

## 7. 错误处理

| 场景 | 策略 |
|---|---|
| 配置损坏 | `ConfigError` → `logging_setup.fatal` → 弹窗给出日志路径 → 退出 |
| 网络请求失败 | `ServiceError` → 写进对应结果行的文本，程序继续运行 |
| 算式非法 / 超时 | `CalcError` → 结果行显示原因 |
| 打开文件失败 | 记一条 warning，不打断其他条目 |
| 写配置失败 | 管理器记日志并把原因显示在提示条里 |
| 未捕获异常 | `sys.excepthook` / `threading.excepthook` 记录后弹窗 |

原则：**能降级的降级，不能降级的要留下可读的原因**。任何静默失败都算缺陷。

## 8. 路径与工作目录

`app/paths.py` 是唯一允许推导路径的地方：

```python
PACKAGE_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = PACKAGE_DIR.parent
```

- 配置里的相对路径（如 `custom\clear_clipboard.py`）以 `PROGRAM_DIR` 为基准解析，与进程 cwd 无关。
- 启动子进程时，工作目录用参数传递：`subprocess.Popen(..., cwd=...)`、`os.startfile(path, cwd=...)`、`ShellExecuteW(..., lpDirectory=...)`。
- 日志与配置永远写绝对路径。

`test_no_chdir_anywhere` 会扫描 `app/` 下所有文件，出现任何 `chdir` 调用即失败。

## 9. 本地化

- 文案键放在 `app/locales/{语言代码}.json`，**文件名就是语言代码**（`zh-CN.json`、`en-US.json`）。
- `i18n.available_languages()` 扫描该目录，放进去什么语言就支持什么语言；`normalize()` 负责把配置里的值收敛到已发现的代码，认不出来时回退 `zh-CN`。
- `i18n.t("键", 占位符=值)` 查表并填充；其他语言缺键时回退 `zh-CN`，界面不会出现裸露的键名。
- 语言在界面上的显示名由 `i18n.language_names()` 从各语言包的 `language.name` 读取（用该语言自己的文字），程序里没有硬编码的名称表；该键缺失时直接用代码本身。
- 类型、字段、调试动作的显示名由函数生成（`type_label()` 等），不缓存成模块级字典——否则导入时就把语言固定了。
- 管理器的静态文案用 `data-i18n` / `data-i18n-placeholder` / `data-i18n-title` / `data-i18n-aria` 标记，启动时统一替换；动态文案用 `get_strings()` 拉到的表在 JS 里查。
- 列举多个字段时的分隔符由 `i18n.list_separator()` 给出，中文用 `、`，其他语言用 `, `。

新增语言的步骤见 [extending.md](extending.md)。

## 10. 前端与后端契约

网页通过 `window.pywebview.api.<方法>(...)` 调用 Python，参数与返回值都是 JSON 可序列化的值。方法分四类：

| 类别 | 方法 |
|---|---|
| 读取 | `get_state` `get_strings` `get_settings` |
| 选择 | `select_operation` `select_group` |
| 结构编辑 | `add_operation` `add_group` `delete_operation` `delete_group` `move_operation` `move_group` `move_operation_by` `move_group_by` |
| 字段编辑 | `set_field` `set_argument` `change_type` `set_group_name` `set_group_enabled` |
| 应用设置 | `set_language` `set_theme` `update_settings` |
| 持久化与窗口 | `save` `browse_file` `browse_dir` `answer_close` |

约定：

- 所有结构编辑方法都返回完整快照，前端直接 `apply()`。
- 越界或非法参数不抛异常，原样返回当前快照，避免网页拿到 Python traceback。
- `set_field` / `set_argument` 只返回 `{"ok": bool}`，因为它们由输入框逐字符触发，返回整份快照太重。

## 11. 测试策略

```
tests/
├─ conftest.py              把项目根加入 sys.path，统一中文语言
├─ test_paths.py            路径解析与相对路径基准
├─ test_settings.py         配置读写、夹取、匹配字串清理
├─ test_matching.py         归一化与拼音
├─ test_navigation.py       浏览语法与六种错误
├─ test_calculator.py       求值、边界、超时
├─ test_resolver.py         优先级链、#n、目录浏览
├─ test_actions_cwd.py      cwd 不变、目标目录显式传递
├─ test_manager_api.py      分组操作、校验、状态快照
├─ test_source_hygiene.py   静态守卫
└─ test_theme.py            系统外观读取
```

跑法：

```bat
uv sync
.venv\Scripts\python -m pytest
```

写测试的约定：

- 涉及文件系统的用例一律用 `tmp_path`，不碰真实配置。
- 涉及系统能力的用例注入假实现（`FakeOpener`、假剪贴板、假列举函数）。
- 断言文案时用中文，`conftest.py` 已经把语言固定为 `zh-CN`。
