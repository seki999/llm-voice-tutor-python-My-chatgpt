# setup_venv.ps1
# 在项目目录内创建 .venv，并把依赖安装到这个项目自己的 Python 环境里。

$ErrorActionPreference = "Stop"

Write-Host "=== My Local Voice ChatGPT: setup project venv ==="

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

Write-Host "Project directory: $ProjectDir"

if (!(Test-Path ".venv")) {
    Write-Host "Creating .venv ..."
    python -m venv .venv
} else {
    Write-Host ".venv already exists."
}

$PythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (!(Test-Path $PythonExe)) {
    Write-Host "ERROR: .venv python.exe not found: $PythonExe"
    exit 1
}

Write-Host "Using Python:"
& $PythonExe -c "import sys; print(sys.executable)"

Write-Host "Upgrading pip ..."
& $PythonExe -m pip install --upgrade pip

Write-Host "Installing requirements into project .venv ..."
& $PythonExe -m pip install -r requirements.txt

Write-Host ""
Write-Host "Setup completed."
Write-Host "Next time run:"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\run_app.ps1"
