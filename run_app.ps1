# run_app.ps1
# 总是使用项目内 .venv 运行 app.py，不使用全局 Python。

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

$PythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (!(Test-Path $PythonExe)) {
    Write-Host ".venv not found. Creating and installing dependencies first..."
    powershell -ExecutionPolicy Bypass -File "$ProjectDir\setup_venv.ps1"
}

Write-Host "=== Running with project Python ==="
& $PythonExe -c "import sys; print(sys.executable)"

Write-Host "=== Package environment ==="
& $PythonExe -m pip -V

Write-Host "=== Starting app.py ==="
& $PythonExe app.py
