$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VendorDir = Join-Path $ProjectRoot "vendor"
$TripoDir = Join-Path $VendorDir "TripoSR"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

Write-Host "[Photo2Print3D] Preparing TripoSR..." -ForegroundColor Cyan
Write-Host "Using Python: $Python" -ForegroundColor DarkGray

New-Item -ItemType Directory -Force -Path $VendorDir | Out-Null

if (-not (Test-Path (Join-Path $TripoDir ".git"))) {
    git clone https://github.com/VAST-AI-Research/TripoSR.git $TripoDir
} else {
    Write-Host "TripoSR already exists. Updating checkout..."
    git -C $TripoDir pull --ff-only
}

& $Python -c "import torch; print('PyTorch', torch.__version__, '| CUDA available:', torch.cuda.is_available())"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "PyTorch is not installed in the selected Python environment." -ForegroundColor Yellow
    Write-Host "Run the CPU or CUDA setup first, then run this script again."
    exit 1
}

& $Python -m pip install --upgrade setuptools
& $Python -m pip install -r (Join-Path $TripoDir "requirements.txt")

Write-Host ""
Write-Host "TripoSR ready at: $TripoDir" -ForegroundColor Green
Write-Host "Run: .\.venv\Scripts\python.exe app.py" -ForegroundColor Green
