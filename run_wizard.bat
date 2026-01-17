:: run_wizard.bat
:: Run the Sengled WiFi Bulb setup wizard using the local .venv environment on Windows.

@echo off
cd /d "%~dp0"

:: Check for .venv
if not exist ".venv\Scripts\python.exe" (
    echo .venv not found. Running setup_windows.bat first...
    call setup_windows.bat
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Setup failed. Cannot launch wizard.
        pause
        exit /b 1
    )
)

:: Run the wizard
echo Starting Sengled WiFi Bulb setup wizard...
.venv\Scripts\python.exe sengled_tool.py

echo.
pause
exit /b 0
