@echo off
setlocal EnableExtensions

cd /d "%~dp0\.."
set "ROOT=%CD%"
set "SF3D_DIR=%ROOT%\vendor\stable-fast-3d"
set "SF3D_COMMIT=ff21fc491b4dc5314bf6734c7c0dabd86b5f5bb2"
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"

where git >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Git nao foi encontrado no PATH.
  exit /b 1
)

if not exist "%VSWHERE%" (
  echo [ERRO] Stable Fast 3D no Windows exige Visual Studio 2022 / Build Tools com C++.
  echo Instale o workload "Desktop development with C++" e rode este arquivo novamente.
  exit /b 2
)

if not exist "%SF3D_DIR%\run.py" (
  echo [1/7] Clonando Stable Fast 3D oficial...
  if not exist "%ROOT%\vendor" mkdir "%ROOT%\vendor"
  git clone https://github.com/Stability-AI/stable-fast-3d.git "%SF3D_DIR%"
  if errorlevel 1 exit /b 1
) else (
  echo [1/7] Checkout do Stable Fast 3D ja existe.
)

echo [2/7] Fixando checkout oficial conhecido...
git -C "%SF3D_DIR%" fetch origin
if errorlevel 1 exit /b 1
git -C "%SF3D_DIR%" checkout "%SF3D_COMMIT%"
if errorlevel 1 exit /b 1

if not exist "%SF3D_DIR%\.venv\Scripts\python.exe" (
  echo [3/7] Criando ambiente Python isolado do SF3D...
  py -3.11 -m venv "%SF3D_DIR%\.venv"
  if errorlevel 1 (
    echo [ERRO] Nao foi possivel criar o venv com Python 3.11.
    exit /b 1
  )
) else (
  echo [3/7] Ambiente isolado ja existe.
)

set "PY=%SF3D_DIR%\.venv\Scripts\python.exe"

echo [4/7] Preparando pip e ferramentas de build...
"%PY%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%PY%" -m pip install "setuptools==69.5.1" wheel
if errorlevel 1 exit /b 1

echo [5/7] Instalando PyTorch CPU no ambiente isolado...
"%PY%" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 exit /b 1

echo [6/7] Preparando requirements CPU do SF3D...
"%ROOT%\.venv\Scripts\python.exe" "%ROOT%\scripts\prepare_sf3d_cpu_requirements.py" "%SF3D_DIR%"
if errorlevel 1 exit /b 1

pushd "%SF3D_DIR%"
echo [7/7] Instalando dependencias oficiais do SF3D. Esta etapa pode demorar e compilar extensoes C++...
"%PY%" -m pip install -r requirements-photo2print3d-cpu.txt
if errorlevel 1 (
  popd
  echo [ERRO] A instalacao do SF3D falhou. Veja as ultimas linhas acima.
  exit /b 1
)
popd

echo.
echo ================================================
echo Stable Fast 3D instalado em ambiente isolado.
echo ================================================
echo.
echo O modelo e gated no Hugging Face. Antes do primeiro uso:
echo 1. Solicite acesso a stabilityai/stable-fast-3d no Hugging Face.
echo 2. Crie um token de leitura.
echo 3. Execute:
echo.
echo   "%SF3D_DIR%\.venv\Scripts\huggingface-cli.exe" login
echo.
echo Depois reinicie o Photo2Print3D e selecione Stable Fast 3D.
exit /b 0
