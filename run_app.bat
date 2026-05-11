@echo off
REM run_app.bat
REM 双击也可以启动。总是使用项目内 .venv。

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo .venv not found. Creating and installing dependencies first...
    powershell -ExecutionPolicy Bypass -File "%~dp0setup_venv.ps1"
)

echo === Running with project Python ===
".venv\Scripts\python.exe" -c "import sys; print(sys.executable)"

echo === Starting app.py ===
".venv\Scripts\python.exe" app.py

pause
