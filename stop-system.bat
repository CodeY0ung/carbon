@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo   CASPIAN - Stopping All Services (Windows)
echo ============================================================
echo.

REM Check if Git Bash is available
set "GIT_BASH=C:\Program Files\Git\bin\bash.exe"

if not exist "%GIT_BASH%" (
    echo [ERROR] Git Bash not found at: %GIT_BASH%
    echo.
    echo Please install Git for Windows or update the GIT_BASH path in this script.
    pause
    exit /b 1
)

echo Using Git Bash to execute stop script...
echo.

REM Execute the stop script
"%GIT_BASH%" --login -i -c "cd /c/Users/USER/Desktop/carbon && bash stop-all-services.sh"

echo.
echo Press any key to exit...
pause >nul
