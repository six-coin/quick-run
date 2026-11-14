# Quick Run User Manual

A keyboard launcher for Windows: press Alt+Space, type a few letters, and open a file, a folder, a web page or run a command. The bundled Quick Run Manager maintains that list through a web UI.

[简体中文](zh-CN.md)

---

## 1. Installation

Windows 10 or later (the manager relies on the built-in WebView2 runtime), plus [uv](https://docs.astral.sh/uv/).

```bat
git clone <repository> "Quick Run"
cd "Quick Run"
setup.bat
```

`setup.bat` creates the `.venv` virtual environment and installs dependencies. You can also do it manually:

```bat
uv sync
```

Re-run `setup.bat` after upgrading or on a new machine; dependency versions are pinned by `uv.lock`.

The package index is pinned in `uv.toml` at the project root and points at official PyPI, so `uv.lock` records official URLs and a fresh clone installs without relying on the machine-wide uv config.

On a slow network, swap the `url` in `uv.toml` for a mirror (e.g. `https://mirrors.aliyun.com/pypi/simple/`) and run `uv lock`. The lockfile will switch to the mirror URLs too — don't commit that change.

## 2. Starting

| File          | Purpose                                                    |
|---------------|------------------------------------------------------------|
| `main.bat`    | Starts the background launcher; summon it with `Alt+Space` |
| `manager.bat` | Opens the operation manager window                         |
| `setup.bat`   | Installs / updates the virtual environment                 |

Both launch scripts use `pythonw.exe` from `.venv`, so no console window is left behind.

To start the launcher at login, put a shortcut to `main.bat` in
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`.

> The launcher is a background process. Double-clicking `main.bat` shows nothing on screen — that is expected. Press `Alt+Space` to bring it up.

On the **first run**, whichever entry point you double-click opens the manager instead: pick the interface language (the Windows UI language by default, English when there is no matching locale; the whole dialog switches the moment you change it), then read the manual. If you started `main.bat`, one extra note explains that the manager is what just opened. Close it and start your original entry point again when you are done.

Both entry points are single-instance: starting `main.bat` twice shows "already running"; opening the manager again brings the existing window to the front.

## 3. Launcher

### 3.1 Basics

Type a few letters and the list shows operations by **prefix match**; press Enter to run one.

| Key                                | Action                                                                                      |
|------------------------------------|---------------------------------------------------------------------------------------------|
| `Alt+Space`                        | Show / hide the launcher                                                                    |
| `↑` `↓`                            | Move the selection                                                                          |
| `Enter`                            | Run the selected item                                                                       |
| `Esc`                              | Hide                                                                                        |
| `Shift+↑` `Shift+↓`                | Browse input history                                                                        |
| `Ctrl` / `Shift` / `Alt` + `Enter` | For files, open the containing folder instead; for the translation row, read the text aloud |

The input is single-line, and the right-click menu is disabled. Click a row to select it; double-click to run it.

### 3.2 Selecting by index

Append `#n` to a keyword to take the n-th match directly, then press Enter:

```
leidian#1      → the first operation matching leidian
play#2         → the second operation matching play
```

Indexes start at 1. Out-of-range values report “unknown index”; a bare `#`, or `#` without digits, is treated as plain text.

### 3.3 Browsing folders

Tick **allow browsing subfolders** on an “open folder” operation, then type `keyword` plus a space. In the table below `␣` stands for one space:

| Input      | Result                                      |
|------------|---------------------------------------------|
| `play␣`    | List the folder contents                    |
| `play␣a`   | List entries whose name contains a          |
| `play␣a␣`  | Enter the first match and list its contents |
| `play␣a␣␣` | Enter the second match                      |
| `play␣a#2` | Show only the second match                  |

In short:

- the first space after the keyword enters browse mode and lists the root folder;
- each following token selects one level;
- the **number of spaces** after a token decides which match to take (one space = the first), and `#n` overrides it;
- if the last token has no trailing space, matches are listed without entering.

Matching also accepts pinyin, so `biji` finds 「笔记」. How deep you can go is limited by the exploration depth: the smaller of the operation's own depth and the global cap in `app.json`, at most 5.

### 3.4 Built-in rows

When nothing matches, these rows appear:

| Row           | Enter does                                                                           |
|---------------|--------------------------------------------------------------------------------------|
| **Search**    | Opens Bing results in the default browser                                            |
| **Calculate** | Copies the result to the clipboard (supports `+ - * / // % **` and parentheses)      |
| **Translate** | Opens the Baidu Translate page; with `Ctrl`/`Shift`/`Alt` held, reads the text aloud |
| **Define**    | Looks the word up with an LLM (requires an API key)                                  |

Appending a backtick `` ` `` to the query skips operation matching and keeps only these rows.

Translation and definition need credentials configured in the manager, see [4.4 Settings](#44-settings).

## 4. Quick Run Manager

Open it with `manager.bat`. The group tree is on the left, the editor on the right. Edits go to memory immediately; press `Ctrl+S` or click “Save file” to write them to disk. The search box has focus as soon as the window opens, so you can start typing straight away.

### 4.1 Groups

- Operations are organised in groups, and **the group order is the order of results in the launcher**;
- drag a group header to reorder groups;
- the switch on the right of a group header enables or disables the whole group; disabled groups are skipped by search but keep their configuration;
- drag an operation to reorder it within its group, or drop it on another group header to move it to the end of that group;
- the `+` on a group header creates an operation in that group; “New group” in the footer adds a group at the end of the list.

### 4.2 Operation types

| Type        | Required argument | Notes                                                                    |
|-------------|-------------------|--------------------------------------------------------------------------|
| Open file   | `path`            | Opens with the default program. `no_window` hides the console window     |
| Open folder | `dir`             | Opens in Explorer. Subfolder browsing and exploration depth are optional |
| Open URL    | `url`             | Opens in the default browser                                             |
| Run command | `command`         | Runs in the program folder and keeps the console window                  |
| Debug       | `function`        | Restarts or closes Quick Run itself                                      |

File and folder operations each have a **path base** dropdown that decides how the path is completed:

| Option                         | Where a relative path starts                                                                      |
|--------------------------------|---------------------------------------------------------------------------------------------------|
| Relative to the data folder    | The data folder (default `%PROGRAMDATA%\six-coin\quick-run`, configurable); `custom\` lives there |
| Relative to the program folder | The folder holding `main.bat`                                                                     |
| Absolute path                  | No completion; the path is used exactly as typed                                                  |

All three only matter when the path is **not** absolute: a full path such as `D:\Tools\x.exe` points at the same file whichever base you pick. A file path may contain several entries separated by `|`; all of them open at once.

Switching the base also changes the grey example text inside the path box, so you can copy the shape of the example:

| Base           | File path example      | Folder path example |
|----------------|------------------------|---------------------|
| Absolute path  | `E:\data\example.json` | `E:\data\`          |
| Data folder    | `custom\example.bat`   | `custom\`           |
| Program folder | `manager.bat`          | `docs\`             |

Folder paths get a trailing `\` when saved (`E:\data` is stored as `E:\data\`).

Whenever the launcher runs an operation, the working directory is the program folder — never the folder of the target file.

### 4.3 Match keywords

Decides what input hits the operation. Only **lowercase `a-z`** and the separator `|` are allowed:

- on save, text is lowercased, other characters dropped, consecutive `|` collapsed, leading/trailing `|` trimmed, and duplicates removed;
- if nothing remains, saving is blocked with “match keywords cannot be empty”;
- keywords are alternatives: matching any one of them is enough.

For example `leidian|ld` means either `leidian` or `ld` hits it.

### 4.4 Settings

Click the gear at the right of the title bar:

| Item                   | Description                                                                                                                       |
|------------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| Language               | Simplified Chinese (China) / English (US) built in; switching applies immediately; the list is sorted by language code            |
| Appearance             | Light or dark only; the system preference is read once on the first run, then the setting wins                                    |
| Fade in                | Milliseconds for the launcher's fade-in, 0–1000; 0 disables the animation. Restart the launcher to apply                          |
| Fade out               | Milliseconds for the fade-out, same rules                                                                                         |
| Max scan depth         | Global depth limit for folder browsing, 0–5                                                                                       |
| Max entries per folder | Folders with more entries are not expanded, keeping the UI responsive                                                             |
| Baidu Translate        | Translation is enabled only when both `appid` and secret key are set                                                              |
| AI definition          | Enabled once an API key is filled in                                                                                              |
| AI prompt              | System prompt sent to the model; shapes the answer style. Clear it or press “Restore default prompt” to get the built-in one back |

Below the fields there are three blocks, with no dividers between them:

- **Data folder**: the first row holds the input box plus "Change" and "Reset"; the next row explains the setting. A change appends `quick-run` automatically and applies after a restart, moving the old contents over.
- **User manual**: the "Open" button on the right shows the manual in the current language.
- **Version**: the version of the program you are running.

Secret fields are masked by default; click the eye icon to reveal them temporarily. The bottom of the panel has "Reset all settings" on the left (language and appearance go back to defaults; the operation list is untouched) and "Done" on the right.

If a Baidu Translate or AI dictionary credential is filled in, the confirmation adds one warning and a "Keep credentials" button: that resets everything else and keeps the APP ID, key and API key.

The settings panel only closes through "Done", the × in the corner, or `Esc`; clicking outside it does nothing. Every other dialog (manual, confirmations) closes on `Esc` or a click outside.

### 4.5 Keyboard

The sidebar as a whole is a **single** `Tab` stop:

| Key             | Action                                                         |
|-----------------|----------------------------------------------------------------|
| `Tab`           | Enter the list once; the next `Tab` leaves it                  |
| `↑` `↓`         | Move between groups and operations                             |
| `Home` `End`    | Jump to the first / last item                                  |
| `Enter` `Space` | Select the focused item; a collapsed group is expanded as well |
| `←`             | Collapse a group, or jump from an operation back to its group  |
| `→`             | Expand a group                                                 |
| `Ctrl+S`        | Save                                                           |
| `Ctrl+F`        | Focus the search box                                           |

While a dialog is open, `Tab` cycles inside it and `Esc` closes the topmost layer. The `+` and the switch on group rows are mouse-only; select the group and use the panel on the right instead.

## 5. Configuration and data

The program folder holds code and `setup.bat` only; runtime files live in system folders.

```
%PROGRAMDATA%\six-coin\quick-run\       data folder (configurable)
├─ app.json                             application settings
├─ operations.json                      operations and groups
└─ custom\                              your own scripts and assets (pick the data folder as the path base)

%LOCALAPPDATA%\six-coin\quick-run\
├─ logs\                                runtime logs
├─ locks\                               locks
└─ data-dir.txt                         data folder pointer

%TEMP%\six-coin\quick-run\              temp folder, safe to delete
```

The data folder always ends with the project code: picking `D://Data` gives `D://Data//quick-run`. On a change the old contents move there on the next start; existing files in the target are never overwritten. Delete `<data>\app.json` and the next launch asks for a language again and regenerates the defaults.

### 5.1 app.json

```json
{
    "language": "zh-CN",
    "theme": "light",
    "navigation": {
        "max_depth": 5,
        "max_entries": 100
    },
    "translate": {
        "appid": "",
        "secret_key": ""
    },
    "ai": {
        "api_key": "",
        "prompt": "你是一个词典助手，功能如下：…"
    }
}
```

`ai.prompt` is the default system prompt for the AI dictionary; it is the same in every interface language, and an empty string means the built-in one.

`language` must be a code that exists in `app/locales`; anything else falls back to `en-US`. `theme` is `light` or `dark` only; it is seeded from the system preference when the file does not exist, afterwards the file wins.

### 5.2 operations.json

The root is the group array:

```json
[
    {
        "name": "Default",
        "enabled": true,
        "operations": [
            {
                "display": "Operations & help",
                "type": "file",
                "keywords": "manager",
                "arguments": {
                    "path": "manager.bat",
                    "base": "program",
                    "no_window": true
                }
            }
        ]
    }
]
```

`base` is the path base: `data` (data folder), `program` (program folder) or `absolute`. The key is **required**: a missing value, an empty string or anything else is reported as a config error naming the offending operation.

See [4.2](#42-operation-types) and [4.3](#43-match-keywords) for the fields. After editing by hand, restart the launcher; the manager re-reads the file every time it opens.

### 5.3 Logs

Each launch creates one log file, `%LOCALAPPDATA%\six-coin\quick-run\logs\main_*.log` or `manage_*.log`. A file rotates after 5 MB and is kept for 14 days. If the program dies unexpectedly, a dialog shows the time, the error and the log path.

## 6. Languages

Two are built in: `zh-CN` (Simplified Chinese) and `en-US` (English). Language files live in `app/locales`, and **the file name is the language code**:

```
app/locales/zh-CN.json
app/locales/en-US.json
```

The directory is scanned at startup, so whatever languages are present are supported — no code changes needed.

### Adding a language

1. Copy `app/locales/en-US.json` and rename it to the target code, e.g. `ja-JP.json`;
2. Translate the values, **keeping the keys and `{name}` placeholders unchanged**;
3. Set `language.name` to the language's own name (for example `"日本語"`); that is what the language list shows;
4. Restart the manager; the language list in settings now includes it.

If `language.name` is missing, the language list falls back to the code itself (`ja-JP`).

Other rules:

- missing keys fall back to `zh-CN`, so a partially translated file still works and never shows raw key names;
- deleting a JSON file removes that language; a stored value that no longer exists falls back to `zh-CN`.

## 7. FAQ

**`Alt+Space` does nothing**

Another program owns the hotkey. The log records “registration failed (error 1409)” and a dialog appears at startup. Close the program holding the hotkey (often another launcher or a screen recorder) and run `main.bat` again.

**The manager window is blank**

Check that the WebView2 runtime is installed. Windows 11 ships with it; Windows 10 may need the [Evergreen Runtime](https://developer.microsoft.com/microsoft-edge/webview2/).

**Translation does not work**

Both `appid` and `secret_key` must be filled in. Only one of them counts as not configured.

**Ctrl+Enter does not read the text aloud**

Speech requires python-vlc and the VLC desktop player. Without them the program still works, just silently.

**I changed the appearance in `app.json` but the launcher did not change**

The launcher reads configuration once at startup; restart `main.bat`. Switching inside the manager is immediate.

**I want the default configuration back**

Close the program, delete `%PROGRAMDATA%\six-coin\quick-run\app.json` and `operations.json`, then start again.

## 8. Development

Architecture, layering rules, data model and testing are documented in [`docs/architecture.md`](../architecture.md).

```bat
uv sync
.venv\Scripts\python -m pytest
```
