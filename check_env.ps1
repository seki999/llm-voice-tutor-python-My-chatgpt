# check_env.ps1
# 确认当前项目使用的是不是项目内 .venv。

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

$PythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (!(Test-Path $PythonExe)) {
    Write-Host ".venv does not exist yet. Run setup first:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\setup_venv.ps1"
    exit 1
}

Write-Host "Project Python:"
& $PythonExe -c "import sys; print(sys.executable)"

Write-Host ""
Write-Host "Pip location:"
& $PythonExe -m pip -V

Write-Host ""
Write-Host "Important packages:"
& $PythonExe -c "import gradio, openai, requests, edge_tts, pyttsx3; import faster_whisper; print('gradio:', gradio.__version__); print('openai:', openai.__version__); print('OK')"
