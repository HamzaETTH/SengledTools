:: setup_windows.bat
:: Prepare a local Python virtual environment for SengledTools on Windows.
:: Uses uv if available, otherwise python -m venv + pip.

@echo off
setlocal

cd /d "%~dp0"

:: Detect uv
where uv >nul 2>&1
if errorlevel 1 (
    set UV_AVAILABLE=0
) else (
    set UV_AVAILABLE=1
)

:: Check python
python --version >nul 2>&1
if errorlevel 1 goto :no_python

:: Create .venv if missing
if not exist ".venv" (
    if "%UV_AVAILABLE%"=="1" (
        echo Creating virtual environment using uv...
        uv venv --seed .venv
    ) else (
        echo Creating virtual environment using python -m venv...
        python -m venv --include-pip .venv
    )
    if errorlevel 1 goto :venv_fail
)

:: Install/refresh deps
echo Installing/refreshing dependencies...
set "VENV_PY=.venv\Scripts\python.exe"
"%VENV_PY%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo pip not found in venv. Bootstrapping with ensurepip...
    "%VENV_PY%" -m ensurepip --upgrade
    if errorlevel 1 goto :pip_bootstrap_fail
)

"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto :pip_upgrade_fail

"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :requirements_fail

echo.
echo Environment setup complete. You can now run run_wizard.bat to start the wizard.
exit /b 0

:no_python
echo ERROR: Python 3.10+ is required but not found in your PATH.
echo Please install it from https://www.python.org/downloads/
exit /b 1

:venv_fail
echo ERROR: Failed to create virtual environment.
exit /b 1

:pip_bootstrap_fail
echo ERROR: Failed to bootstrap pip (ensurepip).
exit /b 1

:pip_upgrade_fail
echo ERROR: Failed to upgrade pip.
exit /b 1

:requirements_fail
echo ERROR: Failed to install requirements.
exit /b 1
