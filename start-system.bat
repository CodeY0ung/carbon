@echo off
REM CASPIAN System Startup Script for Windows

echo ==========================================
echo   CASPIAN 시스템 시작
echo ==========================================
echo.

REM Git Bash 경로 찾기
set "GIT_BASH=C:\Program Files\Git\bin\bash.exe"

if not exist "%GIT_BASH%" (
    echo [ERROR] Git Bash를 찾을 수 없습니다.
    echo Git Bash 설치 경로를 확인하세요: %GIT_BASH%
    echo.
    echo 또는 직접 Git Bash를 열고 다음 명령어를 실행하세요:
    echo   cd /c/Users/USER/Desktop/carbon
    echo   bash start-complete-system.sh
    pause
    exit /b 1
)

echo Git Bash를 사용하여 시스템을 시작합니다...
echo.

"%GIT_BASH%" --login -i -c "cd /c/Users/USER/Desktop/carbon && bash start-complete-system.sh"

echo.
echo 시스템 시작 스크립트가 완료되었습니다.
pause
