@echo off
echo ==========================================
echo CASPIAN Hub-Spoke System 시작
echo ==========================================
echo.

echo [1/4] Prometheus와 Grafana 시작...
docker-compose up -d prometheus grafana
echo.

echo [2/4] Hub API 시작 (포트 8080)...
echo.
echo 다음 명령어로 Hub를 시작하세요:
echo.
echo   cd c:\Users\USER\Desktop\carbon
echo   set ELECTRICITYMAP_API_KEY=your_api_key_here
echo   set CARBON_ZONES=KR,JP,CN
echo   set USE_MOCK_DATA=true
echo   python -m uvicorn hub.app:app --host 0.0.0.0 --port 8080
echo.
echo [3/4] Spoke 클러스터 확인...
kubectl config get-contexts | findstr carbon
echo.

echo ==========================================
echo 시스템 엔드포인트:
echo ==========================================
echo.
echo Hub API:        http://localhost:8080
echo Hub Stats:      http://localhost:8080/hub/stats
echo Prometheus:     http://localhost:9090
echo Grafana:        http://localhost:3000 (admin/admin)
echo.

echo ==========================================
echo AppWrapper 제출 예시:
echo ==========================================
echo.
echo curl -X POST http://localhost:8080/hub/appwrappers \
echo   -H "Content-Type: application/json" \
echo   -d "{\"job_id\": \"test-job-1\", \"cpu\": 2.0, \"mem_gb\": 4.0, \"runtime_minutes\": 30, \"deadline_minutes\": 120}"
echo.

echo 스케줄링 트리거:
echo curl -X POST http://localhost:8080/hub/schedule
echo.

echo 디스패치 트리거:
echo curl -X POST http://localhost:8080/hub/dispatch
echo.
