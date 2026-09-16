$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv\Scripts\python.exe")) { throw "Run install_v1_4_8.ps1 first." }
& .\.venv\Scripts\python.exe .\control_center.py
