@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."
set "VENV_PY=%PROJECT_ROOT%\.venv\Scripts\python.exe"

echo [Photo2Print3D] Windows CPU bootstrap

if not exist "%VENV_PY%" (
  echo Creating virtual environment...
  python -m venv "%PROJECT_ROOT%\.venv"
  if errorlevel 1 (
    echo ERROR: Could not create the virtual environment. Make sure `python` works from this terminal.
    exit /b 1
  )
)

echo Installing Photo2Print3D into the virtual environment...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%VENV_PY%" -m pip install -e "%PROJECT_ROOT%"
if errorlevel 1 exit /b 1

echo Running CPU/low-memory setup with PowerShell execution-policy bypass...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_cpu_windows.ps1"
if errorlevel 1 exit /b 1

echo.
echo Setup complete.
echo Start the app with:
echo   "%VENV_PY%" "%PROJECT_ROOT%\app.py"

endlocal
