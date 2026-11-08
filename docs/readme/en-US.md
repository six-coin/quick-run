# Quick Run

A keyboard launcher for Windows: press `Alt+Space`, type a few letters, and open a file, a folder, a web page or run a command. The bundled **operation manager** maintains that list through a web UI.

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

## 2. Starting

| File | Purpose |
|---|---|
| `main.bat` | Starts the background launcher; summon it with `Alt+Space` |
| `manager.bat` | Opens the operation manager window |
| `setup.bat` | Installs / updates the virtual environment |

Both launch scripts use `pythonw.exe` from `.venv`, so no console window is left behind.

To start the launcher at login, put a shortcut to `main.bat` in
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`.

> The launcher is a background process. Double-clicking `main.bat` shows nothing on screen — that is expected. Press `Alt+Space` to bring it up.

## 3. Launcher

### 3.1 Basics

Type a few letters and the list shows operations by **prefix match**; press Enter to run one.

| Key | Action |
|---|---|
| `Alt+Space` | Show / hide the launcher |
| `↑` `↓` | Move the selection |
| `Enter` | Run the selected item |
| `Esc` | Hide |
| `Shift+↑` `Shift+↓` | Browse input history |
| `Ctrl` / `Shift` / `Alt` + `Enter` | For files, open the containing folder instead; for the translation row, read the text aloud |

The input is single-line, and the right-click menu is disabled.

### 3.2 Selecting by index

Append `#n` to a keyword to take the n-th match directly, then press Enter:

```
leidian#1      → the first operation matching leidian
play#2         → the second operation matching play
```

Indexes start at 1. Out-of-range values report “unknown index”; a bare `#`, or `#` without digits, is treated as plain text.

### 3.3 Browsing folders

Tick **allow browsing subfolders** on an “open folder” operation, then type `keyword` plus a space. In the table below `␣` stands for one space:

| Input | Result |
|---|---|
| `play␣` | List the folder contents |
| `play␣a` | List entries whose name contains a |
| `play␣a␣` | Enter the first match and list its contents |
| `play␣a␣␣` | Enter the second match |
| `play␣a#2` | Show only the second match |

In short:

- the first space after the keyword enters browse mode and lists the root folder;
- each following token selects one level;
- the **number of spaces** after a token decides which match to take (one space = the first), and `#n` overrides it;
- if the last token has no trailing space, matches are listed without entering.

Matching also accepts pinyin, so `biji` finds 「笔记」. How deep you can go is limited by the exploration depth: the smaller of the operation's own depth and the global cap in `app.json`, at most 5.

### 3.4 Built-in rows

When nothing matches, these rows appear:

| Row | Enter does |
|---|---|
| **Search** | Opens Bing results in the default browser |
| **Calculate** | Copies the result to the clipboard (supports `+ - * / // % **` and parentheses) |
| **Translate** | Opens the Baidu Translate page; with `Ctrl`/`Shift`/`Alt` held, reads the text aloud |
| **Define** | Looks the word up with an LLM (requires an API key) |

Appending a backtick `` ` `` to the query skips operation matching and keeps only these rows.

Translation and definition need credentials configured in the manager, see [4.4 Settings](#44-settings).

## 4. Operation manager

Open it with `manager.bat`. The group tree is on the left, the editor on the right. Edits go to memory immediately; press `Ctrl+S` or click “Save file” to write them to disk.

### 4.1 Groups

- Operations are organised in groups, and **the group order is the order of results in the launcher**;
- drag a group header to reorder groups;
- the switch on the right of a group header enables or disables the whole group; disabled groups are skipped by search but keep their configuration;
- drag an operation to reorder it within its group, or drop it on another group header to move it to the end of that group;
- the `+` on a group header creates an operation in that group; “New group” in the footer adds a group at the end of the list.

### 4.2 Operation types

| Type | Required argument | Notes |
|---|---|---|
| Open file | `path` | Opens with the default program. `no_window` hides the console window |
| Open folder | `dir` | Opens in Explorer. Subfolder browsing and exploration depth are optional |
| Open URL | `url` | Opens in the default browser |
| Run command | `command` | Runs in the program directory and keeps the console window |
| Debug | `function` | Restarts or closes Quick Run itself |

A file path may contain several entries separated by `|`; all of them open at once.

### 4.3 Match keywords

Decides what input hits the operation. Only **lowercase `a-z`** and the separator `|` are allowed:

- on save, text is lowercased, other characters dropped, consecutive `|` collapsed, leading/trailing `|` trimmed, and duplicates removed;
- if nothing remains, saving is blocked with “match keywords cannot be empty”;
- keywords are alternatives: matching any one of them is enough.

For example `leidian|ld` means either `leidian` or `ld` hits it.

### 4.4 Settings

Click the gear at the right of the title bar:

| Item | Description |
|---|---|
| Language | Chinese / English built in; switching applies immediately |
| Appearance | Light / dark. The first launch follows the system, afterwards this value wins |
| Max scan depth | Global depth limit for folder browsing, 0–5 |
| Max entries per folder | Folders with more entries are not expanded, keeping the UI responsive |
| Baidu Translate | Translation is enabled only when both `appid` and secret key are set |
| AI definition | Enabled once an API key is filled in |

Secret fields are masked by default; click the eye icon to reveal them temporarily.

### 4.5 Keyboard

The sidebar as a whole is a **single** `Tab` stop:

| Key | Action |
|---|---|
| `Tab` | Enter the list once; the next `Tab` leaves it |
| `↑` `↓` | Move between groups and operations |
| `Home` `End` | Jump to the first / last item |
| `Enter` `Space` | Select the focused item; a collapsed group is expanded as well |
| `←` | Collapse a group, or jump from an operation back to its group |
| `→` | Expand a group |
| `Ctrl+S` | Save |
| `Ctrl+F` | Focus the search box |

While a dialog is open, `Tab` cycles inside it and `Esc` closes it. The `+` and the switch on group rows are mouse-only; select the group and use the panel on the right instead.

## 5. Configuration and data

```
config/app.json          application settings
config/operations.json   operations and groups
logs/                    runtime logs
custom/                  your own scripts and assets (relative paths resolve against the program directory)
```

`config/`, `logs/` and `custom/` are local data and are excluded in `.gitignore`. Delete `config/` and the next launch regenerates a sample configuration.

### 5.1 app.json

```json
{
  "language": "zh-CN",
  "theme": "light",
  "navigation": { "max_depth": 5, "max_entries": 100 },
  "translate": { "appid": "", "secret_key": "" },
  "ai": { "api_key": "" }
}
```

`language` must be a code that exists in `app/locales`. `theme` is seeded from the system preference only when the file does not exist; afterwards the file wins.

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
        "arguments": { "path": "manager.bat", "no_window": true }
      }
    ]
  }
]
```

See [4.2](#42-operation-types) and [4.3](#43-match-keywords) for the fields. After editing by hand, restart the launcher; the manager re-reads the file every time it opens.

### 5.3 Logs

Each launch creates one log file, `logs/main_*.log` or `logs/manage_*.log`. A file rotates after 5 MB and is kept for 14 days. If the program dies unexpectedly, a dialog points at the log file.

## 6. Languages

Two are built in: `zh-CN` (Chinese) and `en-US` (English). Language files live in `app/locales`, and **the file name is the language code**:

```
app/locales/zh-CN.json
app/locales/en-US.json
```

The directory is scanned at startup, so whatever languages are present are supported — no code changes needed.

### Adding a language

1. Copy `app/locales/en-US.json` and rename it to the target code, e.g. `ja-JP.json`;
2. Translate the values, **keeping the keys and `{name}` placeholders unchanged**;
3. Restart the manager; the language list in settings now includes it.

The display name defaults to the code itself (`ja-JP`). To show 「日本語」 instead, add one line to `_KNOWN_NAMES` in `app/i18n.py`:

```python
_KNOWN_NAMES = {"zh-CN": "中文", "en-US": "English", "ja-JP": "日本語"}
```

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
Close the program, delete the `config/` directory, and start again.

## 8. Development

Architecture, layering rules, data model and testing are documented in [`docs/architecture.md`](../architecture.md).

```bat
uv sync
.venv\Scripts\python -m pytest
```
