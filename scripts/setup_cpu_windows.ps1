$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

Write-Host "[Photo2Print3D] CPU/low-memory setup for Windows" -ForegroundColor Cyan
Write-Host "Using Python: $Python" -ForegroundColor DarkGray
Write-Host "Installing the CPU build of PyTorch..." -ForegroundColor Cyan

& $Python -m pip install --upgrade pip
& $Python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

$env:TRIPOSR_DEVICE = "cpu"
Write-Host "TRIPOSR_DEVICE=cpu set for this PowerShell process." -ForegroundColor Yellow

& (Join-Path $PSScriptRoot "setup_triposr.ps1")

Write-Host ""
Write-Host "CPU profile ready." -ForegroundColor Green
Write-Host "Run the app with: .\.venv\Scripts\python.exe app.py" -ForegroundColor Green
Write-Host "For a first test, use marching-cubes resolution 128." -ForegroundColor Green
