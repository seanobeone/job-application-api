$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
$py=(Get-Command python -ErrorAction Stop).Source
if (-not (Test-Path '.\.venv\Scripts\python.exe')) { & $py -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m py_compile app\*.py control_center.py
Write-Host ''
Write-Host 'v1.4.8 installed successfully.' -ForegroundColor Green
Write-Host 'Browser extension folder:' (Join-Path $PSScriptRoot 'browser_extension')
Write-Host 'Load it unpacked in Chrome chrome://extensions or Edge edge://extensions (Developer mode).'
