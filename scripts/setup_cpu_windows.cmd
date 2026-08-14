@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."
set "VENV_PY=%PROJECT_ROOT%\.venv\Scripts\python.exe"

echo [Photo2Print3D] Windows CPU bootstrap

if not exist "%VENV_PY%" (
  echo Creating Python 3.11 virtual environment...
  py -3.11 -m venv "%PROJECT_ROOT%\.venv" >nul 2>&1
  if errorlevel 1 (
    echo ERROR: Python 3.11 was not found through the Windows py launcher.
    echo Install Python 3.11, reopen PowerShell, and run this command again.
    exit /b 1
  )
)

"%VENV_PY%" -c "import sys; print('Using Python', sys.version.split()[0]); raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)"
if errorlevel 1 (
  echo ERROR: The existing .venv is not Python 3.11.
  echo Delete .venv and run this setup again.
  exit /b 1
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
