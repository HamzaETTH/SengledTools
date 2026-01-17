:: setup_windows.bat
:: Prepare a local Python virtual environment for SengledTools on Windows.
:: Uses uv if available, otherwise python -m venv + pip.

@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

:: Detect uv
where uv >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set UV_AVAILABLE=1
) else (
    set UV_AVAILABLE=0
)

:: Check python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python 3.10+ is required but not found in your PATH.
    echo Please install it from https://www.python.org/downloads/
    exit /b 1
)

:: Create .venv if missing
if not exist ".venv" (
    if "!UV_AVAILABLE!"=="1" (
        echo Creating virtual environment using uv...
        uv venv .venv
    ) else (
        echo Creating virtual environment using python -m venv...
        python -m venv .venv
    )
)

if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to create virtual environment.
    exit /b 1
)

:: Install/refresh deps
echo Installing/refreshing dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip
if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to upgrade pip.
    exit /b 1
)

.venv\Scripts\python.exe -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to install requirements.
    exit /b 1
)

echo.
echo Environment setup complete. You can now run run_wizard.bat to start the wizard.
exit /b 0
