$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VendorDir = Join-Path $ProjectRoot "vendor"
$TripoDir = Join-Path $VendorDir "TripoSR"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }
$CompatSource = Join-Path $PSScriptRoot "torchmcubes_compat.py"
$CompatTarget = Join-Path $TripoDir "torchmcubes.py"
$FilteredRequirements = Join-Path $env:TEMP "photo2print3d-triposr-cpu-requirements.txt"

function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

Write-Host "[Photo2Print3D] Preparing TripoSR..." -ForegroundColor Cyan
Write-Host "Using Python: $Python" -ForegroundColor DarkGray

New-Item -ItemType Directory -Force -Path $VendorDir | Out-Null

if (-not (Test-Path (Join-Path $TripoDir ".git"))) {
    git clone https://github.com/VAST-AI-Research/TripoSR.git $TripoDir
    Assert-NativeSuccess "Cloning TripoSR"
} else {
    Write-Host "TripoSR already exists. Updating checkout..."
    git -C $TripoDir pull --ff-only
    Assert-NativeSuccess "Updating TripoSR"
}

& $Python -c "import sys; print('Python', sys.version.split()[0]); assert sys.version_info < (3, 12), 'TripoSR CPU profile requires Python 3.11 or earlier on Windows'"
Assert-NativeSuccess "Python compatibility check"

& $Python -c "import torch; print('PyTorch', torch.__version__, '| CUDA available:', torch.cuda.is_available())"
Assert-NativeSuccess "PyTorch check"

& $Python -m pip install --upgrade setuptools
Assert-NativeSuccess "Updating setuptools"

# torchmcubes is a compiled C++/CUDA extension. On the Windows CPU profile it
# would require Visual C++ Build Tools just to extract the final isosurface.
# Install every other official TripoSR dependency and provide a small
# scikit-image compatibility module instead.
Get-Content (Join-Path $TripoDir "requirements.txt") |
    Where-Object { $_ -notmatch "torchmcubes" } |
    Set-Content -Encoding UTF8 $FilteredRequirements

Write-Host "Installing TripoSR dependencies (compiler-free CPU profile)..." -ForegroundColor Cyan
& $Python -m pip install -r $FilteredRequirements
Assert-NativeSuccess "Installing TripoSR dependencies"

& $Python -m pip install "scikit-image>=0.24,<0.27"
Assert-NativeSuccess "Installing scikit-image marching-cubes backend"

Copy-Item -Force $CompatSource $CompatTarget

Push-Location $TripoDir
try {
    & $Python -c "import torch; from torchmcubes import marching_cubes; v=torch.ones((8,8,8), dtype=torch.float32); v[2:6,2:6,2:6]=-1; verts,faces=marching_cubes(v,0.0); print('CPU marching cubes OK:', len(verts), 'verts,', len(faces), 'faces')"
    Assert-NativeSuccess "Testing CPU marching-cubes compatibility layer"

    & $Python -c "from tsr.system import TSR; print('TripoSR import OK')"
    Assert-NativeSuccess "Importing TripoSR"
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "TripoSR ready at: $TripoDir" -ForegroundColor Green
Write-Host "Run: .\.venv\Scripts\python.exe app.py" -ForegroundColor Green
