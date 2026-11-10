$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "Python 3.12 is required" }
& .venv/Scripts/python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
& .venv/Scripts/python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
& .venv/Scripts/python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name AIClipStudio --add-data "assets;assets" main.py
if ($LASTEXITCODE -ne 0) { throw "EXE build failed" }
Write-Host "Ready: dist/AIClipStudio.exe"
