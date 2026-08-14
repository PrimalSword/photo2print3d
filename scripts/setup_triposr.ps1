$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VendorDir = Join-Path $ProjectRoot "vendor"
$TripoDir = Join-Path $VendorDir "TripoSR"

Write-Host "[Photo2Print3D] Preparing TripoSR..." -ForegroundColor Cyan

New-Item -ItemType Directory -Force -Path $VendorDir | Out-Null

if (-not (Test-Path (Join-Path $TripoDir ".git"))) {
    git clone https://github.com/VAST-AI-Research/TripoSR.git $TripoDir
} else {
    Write-Host "TripoSR already exists. Updating checkout..."
    git -C $TripoDir pull --ff-only
}

python -c "import torch; print('PyTorch', torch.__version__, '| CUDA available:', torch.cuda.is_available())"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "PyTorch is not installed in the active Python environment." -ForegroundColor Yellow
    Write-Host "Install PyTorch for your CPU/CUDA configuration from the official PyTorch installer, then run this script again."
    exit 1
}

python -m pip install --upgrade setuptools
python -m pip install -r (Join-Path $TripoDir "requirements.txt")

Write-Host ""
Write-Host "TripoSR ready at: $TripoDir" -ForegroundColor Green
Write-Host "Now run: python app.py" -ForegroundColor Green
