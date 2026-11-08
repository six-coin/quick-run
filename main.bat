@echo off
chcp 65001 >nul
rem 启动 Quick Run 启动器：在虚拟环境里运行 main.pyw，不弹控制台窗口。
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo [Quick Run] 还没有安装运行环境。
    echo [Quick Run] 请先双击 setup.bat，或在命令行执行：uv sync
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "main.pyw"
