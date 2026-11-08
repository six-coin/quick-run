@echo off
chcp 65001 >nul
rem 打开 Quick Run 操作管理器：在虚拟环境里运行 manager.pyw。
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo [Quick Run] 还没有安装运行环境。
    echo [Quick Run] 请先双击 setup.bat，或在命令行执行：uv sync
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "manager.pyw"
