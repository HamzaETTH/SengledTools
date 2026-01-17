:: update_windows.bat
:: Update the SengledTools repo via git pull and refresh Python dependencies in .venv on Windows.

@echo off
cd /d "%~dp0"

:: Check for Git
git rev-parse --is-inside-work-tree >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: This directory is not a Git repository. Cannot update.
    pause
    exit /b 1
)

:: Check for local changes
for /f "tokens=*" %%i in ('git status --porcelain') do set LOCAL_CHANGES=%%i
if defined LOCAL_CHANGES (
    echo WARNING: You have local changes. git pull may fail or cause conflicts.
    echo.
)

:: Pull changes
echo Pulling latest changes from Git...
git pull --ff-only
if %ERRORLEVEL% neq 0 (
    echo ERROR: git pull failed. Please resolve manually.
    pause
    exit /b 1
)

:: Refresh dependencies
echo.
echo Refreshing dependencies...
call setup_windows.bat

if %ERRORLEVEL% equ 0 (
    echo.
    echo Update complete.
) else (
    echo.
    echo WARNING: Git update succeeded, but dependency refresh failed.
)

pause
exit /b 0
