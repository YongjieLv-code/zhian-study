param([int]$Port = 8765, [switch]$SkipBuild)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$studyPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $studyPython)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Unable to create the Python environment. Install Python 3.11 or newer.' }
}

& $studyPython -c "import importlib.util,sys; sys.exit(0 if all(importlib.util.find_spec(name) for name in ['fastapi','uvicorn','sqlalchemy','tzdata']) else 1)"
if ($LASTEXITCODE -ne 0) {
    & $studyPython -m pip install -r requirements-lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
}

if (-not $SkipBuild -or -not (Test-Path -LiteralPath '.\dist\index.html')) {
    if (-not (Test-Path -LiteralPath '.\node_modules')) {
        npm install --no-fund --no-audit
        if ($LASTEXITCODE -ne 0) { throw 'Node dependency installation failed.' }
    }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
}

Write-Host ""
Write-Host "Zhi An is starting at http://127.0.0.1:$Port" -ForegroundColor Green
Write-Host 'Keep this window open. Press Ctrl+C to stop.'
Write-Host ""
& $studyPython -m uvicorn server.main:app --host 127.0.0.1 --port $Port
