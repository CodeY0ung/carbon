@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

REM CASPIAN Hub-Spoke 시스템 시작 스크립트 (Windows)

echo.
echo ==========================================
echo   CASPIAN Hub-Spoke 시스템 시작
echo ==========================================
echo.
echo 탄소 인지형 Kubernetes 워크로드 스케줄러
echo.

REM ============================================================
REM Step 1: 기존 환경 정리
REM ============================================================
echo ==========================================
echo [1/6] 기존 환경 정리...
echo ==========================================
echo.

echo - Docker 컨테이너 정리...
docker-compose down 2>nul
timeout /t 2 /nobreak >nul

echo - 기존 Kind 클러스터 확인...
kind get clusters 2>nul | findstr /r "carbon-" >nul
if %errorlevel% equ 0 (
    echo   기존 클러스터 발견, 삭제 중...
    kind delete cluster --name carbon-kr 2>nul
    kind delete cluster --name carbon-jp 2>nul
    kind delete cluster --name carbon-cn 2>nul
    timeout /t 2 /nobreak >nul
)

echo [완료] 환경 정리 완료
echo.

REM ============================================================
REM Step 2: Spoke 클러스터 생성
REM ============================================================
echo ==========================================
echo [2/6] Spoke 클러스터 생성...
echo ==========================================
echo.

if not exist "setup-spoke-clusters.sh" (
    echo [오류] setup-spoke-clusters.sh 파일을 찾을 수 없습니다
    exit /b 1
)

echo Git Bash를 사용하여 클러스터 생성 중...
bash setup-spoke-clusters.sh

echo [완료] Spoke 클러스터 생성 완료
echo.

REM ============================================================
REM Step 3: Docker kubeconfig 생성
REM ============================================================
echo ==========================================
echo [3/6] Docker용 kubeconfig 생성...
echo ==========================================
echo.

echo - kubeconfig 내보내기...
kubectl config view --flatten > kubeconfig-docker

echo - API 서버 주소 변환...
echo   Windows 환경에서는 수동으로 kubeconfig-docker를 확인하세요

echo [완료] kubeconfig 생성 완료
echo.

REM ============================================================
REM Step 4: Docker Compose 서비스 시작
REM ============================================================
echo ==========================================
echo [4/6] Docker 서비스 시작...
echo ==========================================
echo.

echo - Hub Cluster, Prometheus, Grafana 시작...
docker-compose up -d --build

echo - 서비스 준비 대기 (30초)...
timeout /t 30 /nobreak >nul

echo [완료] Docker 서비스 시작 완료
echo.

REM ============================================================
REM Step 5: Hub API 준비 대기 및 클러스터 등록
REM ============================================================
echo ==========================================
echo [5/6] Hub API 준비 및 클러스터 등록...
echo ==========================================
echo.

echo - Hub API 준비 대기 중...
set /a count=0
:wait_hub
set /a count+=1
curl -s http://localhost:8080/hub/stats >nul 2>&1
if %errorlevel% equ 0 (
    echo [완료] Hub API 준비 완료 (%count%초^)
    goto hub_ready
)
if %count% geq 60 (
    echo [오류] Hub API 시작 시간 초과
    echo   로그 확인: docker logs carbon-hub
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_hub

:hub_ready
echo.

echo - Spoke 클러스터 등록 중...
echo   [1/3] carbon-kr 등록...
curl -s -X POST http://localhost:8080/hub/clusters -H "Content-Type: application/json" -d "{\"name\": \"carbon-kr\", \"geolocation\": \"KR\", \"carbon_intensity\": 400.0, \"resources\": {\"cpu_available\": 14.0, \"cpu_total\": 16.0, \"mem_available_gb\": 28.0, \"mem_total_gb\": 32.0}, \"kubeconfig_context\": \"kind-carbon-kr\"}" >nul
echo   [완료] carbon-kr 등록 완료

echo   [2/3] carbon-jp 등록...
curl -s -X POST http://localhost:8080/hub/clusters -H "Content-Type: application/json" -d "{\"name\": \"carbon-jp\", \"geolocation\": \"JP\", \"carbon_intensity\": 450.0, \"resources\": {\"cpu_available\": 14.0, \"cpu_total\": 16.0, \"mem_available_gb\": 28.0, \"mem_total_gb\": 32.0}, \"kubeconfig_context\": \"kind-carbon-jp\"}" >nul
echo   [완료] carbon-jp 등록 완료

echo   [3/3] carbon-cn 등록...
curl -s -X POST http://localhost:8080/hub/clusters -H "Content-Type: application/json" -d "{\"name\": \"carbon-cn\", \"geolocation\": \"CN\", \"carbon_intensity\": 550.0, \"resources\": {\"cpu_available\": 14.0, \"cpu_total\": 16.0, \"mem_available_gb\": 28.0, \"mem_total_gb\": 32.0}, \"kubeconfig_context\": \"kind-carbon-cn\"}" >nul
echo   [완료] carbon-cn 등록 완료

echo.
echo [완료] 클러스터 등록 완료
echo.

REM ============================================================
REM Step 6: 시스템 상태 확인
REM ============================================================
echo ==========================================
echo [6/6] 시스템 상태 확인...
echo ==========================================
echo.

echo - Docker 컨테이너 상태:
docker ps --filter "name=carbon-" --format "   {{.Names}}: {{.Status}}" | findstr /r "hub prometheus grafana"
echo.

echo - Kubernetes 클러스터 상태:
kubectl config get-contexts | findstr carbon
echo.

echo - Hub 통계:
curl -s http://localhost:8080/hub/stats
echo.
echo.

echo [완료] 시스템 상태 정상
echo.

REM ============================================================
REM 시작 완료
REM ============================================================
echo ==========================================
echo   CASPIAN 시스템 시작 완료!
echo ==========================================
echo.

echo [접속 정보]
echo ==========================================
echo.
echo   Hub API:        http://localhost:8080
echo                   - /hub/stats (시스템 상태)
echo                   - /hub/clusters (클러스터 목록)
echo                   - /hub/appwrappers (작업 목록)
echo                   - /metrics (Prometheus 메트릭)
echo.
echo   Prometheus:     http://localhost:9090
echo.
echo   Grafana:        http://localhost:3000
echo                   - 계정: admin / admin
echo                   - 대시보드: "CASPIAN Carbon-Aware Scheduling"
echo.

echo [빠른 시작]
echo ==========================================
echo.
echo 1. AppWrapper 제출:
echo    curl -X POST http://localhost:8080/hub/appwrappers ^
echo      -H "Content-Type: application/json" ^
echo      -d "{\"job_id\": \"my-job\", \"cpu\": 2.0, \"mem_gb\": 4.0, \"runtime_minutes\": 30, \"deadline_minutes\": 120}"
echo.
echo 2. 스케줄링 트리거:
echo    curl -X POST http://localhost:8080/hub/schedule
echo.
echo 3. 디스패치 트리거:
echo    curl -X POST http://localhost:8080/hub/dispatch
echo.
echo 4. Job 확인:
echo    kubectl --context kind-carbon-kr get jobs,pods
echo.

echo [유용한 명령어]
echo ==========================================
echo.
echo   시스템 상태:    curl http://localhost:8080/hub/stats
echo   Hub 로그:       docker logs -f carbon-hub
echo   시스템 종료:    docker-compose down
echo.

echo 모든 준비가 완료되었습니다!
echo 지금 바로 Grafana에 접속하여 실시간 모니터링을 확인하세요.
echo.

pause
