$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (!(Test-Path .venv/Scripts/python.exe)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Install Python 3.12 x64 first" }
}
$python = ".venv/Scripts/python.exe"
& $python -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
& $python tools/prepare_model.py
if ($LASTEXITCODE -ne 0) { throw "Official Whisper model download failed" }
$env:QT_QPA_PLATFORM = "offscreen"
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name StreamForgeStudio --add-data "assets;assets" --collect-all faster_whisper --collect-all ctranslate2 --collect-all tokenizers --collect-all av --collect-all onnxruntime --collect-all imageio_ffmpeg --collect-all yt_dlp --copy-metadata imageio-ffmpeg --copy-metadata yt-dlp --copy-metadata faster-whisper main.py
if ($LASTEXITCODE -ne 0) { throw "EXE build failed" }
$checksum = (Get-FileHash dist/StreamForgeStudio.exe -Algorithm SHA256).Hash.ToLower()
"$checksum  StreamForgeStudio.exe" | Set-Content dist/StreamForgeStudio.exe.sha256 -Encoding ascii
Write-Host "Ready: dist/StreamForgeStudio.exe"
