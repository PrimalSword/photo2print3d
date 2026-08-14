$ErrorActionPreference = "Stop"

Write-Host "[Photo2Print3D] CPU/low-memory setup for Windows" -ForegroundColor Cyan
Write-Host "Installing the CPU build of PyTorch..." -ForegroundColor Cyan

python -m pip install --upgrade pip
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

$env:TRIPOSR_DEVICE = "cpu"
Write-Host "TRIPOSR_DEVICE=cpu set for this PowerShell session." -ForegroundColor Yellow

& (Join-Path $PSScriptRoot "setup_triposr.ps1")

Write-Host ""
Write-Host "CPU profile ready." -ForegroundColor Green
Write-Host "Keep this PowerShell window open and run: python app.py" -ForegroundColor Green
Write-Host "For a first test, use marching-cubes resolution 128." -ForegroundColor Green
