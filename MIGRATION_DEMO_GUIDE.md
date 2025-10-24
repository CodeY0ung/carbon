# CASPIAN 자동 마이그레이션 데모 가이드

## 📌 핵심 개념

### 마이그레이션은 왜 자동으로 발생하지 않나요?

**마이그레이션 = 워크로드를 한 클러스터에서 다른 클러스터로 이동**

마이그레이션이 발생하려면:
1. ✅ 워크로드(AppWrapper)가 **존재**해야 함
2. ✅ 워크로드가 이미 **배치**되어 있어야 함
3. ✅ 탄소 강도 **변화**로 다른 클러스터가 더 유리해져야 함
4. ✅ Scheduler가 **재스케줄링**을 실행해야 함

**현재 시스템 상태:**
- ✅ 탄소 강도는 10초마다 자동 변경됨
- ✅ Scheduler는 30초마다 자동 실행됨
- ❌ **워크로드가 없음** ← 이것이 핵심 문제!

**결론: 워크로드를 생성해야 마이그레이션이 발생합니다.**

---

## 🚀 빠른 시작

### 방법 1: 자동 데모 스크립트 (권장)

```bash
# 기본 데모 (3개 워크로드, 10분 모니터링)
bash auto-migration-demo.sh

# 5개 워크로드, 20 사이클 (더 많은 마이그레이션)
bash auto-migration-demo.sh 5 20

# 10개 워크로드, 30 사이클 (장시간 테스트)
bash auto-migration-demo.sh 10 30
```

**이 스크립트가 하는 일:**
1. Hub API 상태 확인
2. 클러스터 자동 등록 (필요시)
3. 테스트 워크로드 생성
4. 초기 스케줄링 실행
5. 실시간 마이그레이션 모니터링
6. 최종 통계 출력

### 방법 2: 수동 워크로드 생성

```bash
# 1. 워크로드 생성
curl -X POST http://localhost:8080/hub/appwrappers \
  -H 'Content-Type: application/json' \
  -d '{
    "job_id": "my-workload-1",
    "cpu": 2.0,
    "mem_gb": 4.0,
    "data_gb": 30.0,
    "runtime_minutes": 120,
    "deadline_minutes": 480
  }'

# 2. 스케줄링 실행
curl -X POST http://localhost:8080/hub/schedule

# 3. 배치 확인
curl -s http://localhost:8080/hub/appwrappers | python -m json.tool

# 4. 30초 대기 후 재스케줄링
sleep 30
curl -X POST http://localhost:8080/hub/schedule

# 5. 마이그레이션 확인
curl -s http://localhost:8080/metrics | grep migration
```

---

## 📊 마이그레이션 시나리오 예시

### 시나리오 1: 단순 교차

```
시간 T0 (초기):
  탄소 강도: KR=300 ⭐, JP=400, CN=600
  워크로드 생성: workload-1
  스케줄링 → workload-1 배치: carbon-kr

시간 T1 (+30초):
  탄소 강도: KR=450, JP=280 ⭐, CN=620
  재스케줄링 → 마이그레이션 발생!
  workload-1: carbon-kr → carbon-jp

  메트릭 기록:
    migrations_total{from_cluster="carbon-kr",to_cluster="carbon-jp"} = 1
    migration_data_transferred_gb = 30
    migration_cost_gco2 = 100
```

### 시나리오 2: 여러 워크로드

```
시간 T0:
  탄소: KR=320 ⭐, JP=380, CN=650
  워크로드: w1, w2, w3 → 모두 carbon-kr

시간 T1:
  탄소: KR=480, JP=290 ⭐, CN=600
  재스케줄링 → 3개 모두 마이그레이션!
  w1, w2, w3: carbon-kr → carbon-jp

  메트릭:
    migrations_total = 3
    migration_data_transferred_gb = 90 (30×3)
```

### 시나리오 3: 부분 마이그레이션

```
시간 T0:
  탄소: KR=300 ⭐, JP=350, CN=650
  워크로드: w1(50GB), w2(20GB), w3(10GB) → 모두 carbon-kr

시간 T1:
  탄소: KR=380, JP=320 ⭐, CN=600
  재스케줄링 → CI 차이 60 vs 마이그레이션 비용

  결과:
    - w1 (50GB): 유지 (마이그레이션 비용이 너무 큼)
    - w2 (20GB): 마이그레이션 (carbon-kr → carbon-jp)
    - w3 (10GB): 마이그레이션 (carbon-kr → carbon-jp)
```

---

## 🔍 마이그레이션 모니터링

### 실시간 확인

```bash
# 1. 워크로드 배치 상태
curl -s http://localhost:8080/hub/appwrappers | python -c "
import sys, json
aws = json.load(sys.stdin).get('appwrappers', [])
for aw in aws:
    print(f\"{aw['spec']['job_id']}: {aw['spec'].get('target_cluster', 'N/A')}\")
"

# 2. 마이그레이션 메트릭
curl -s http://localhost:8080/metrics | grep migration

# 3. 탄소 강도 실시간 확인
watch -n 5 "curl -s http://localhost:8080/hub/stats | python -m json.tool"
```

### Grafana 대시보드

1. 브라우저에서 http://localhost:3000 접속
2. 로그인: admin / admin
3. "CASPIAN Hub - Carbon-Aware Scheduling" 대시보드 선택
4. **Migration 패널 확인**:
   - Total Migrations
   - Data Transferred (GB)
   - Migration Carbon Cost (gCO2)
   - Migrations In Progress
   - Migration Matrix
   - Migrations Over Time

---

## ⚙️ 고급 설정

### 마이그레이션 빈도 조정

**Scheduler 간격 변경** ([hub/scheduler.py](c:\Users\USER\Desktop\carbon\hub\scheduler.py):348)
```python
# 기본값: 30초
hub_scheduler = HubScheduler(schedule_interval=30)

# 더 자주 체크 (10초)
hub_scheduler = HubScheduler(schedule_interval=10)

# 덜 자주 체크 (60초)
hub_scheduler = HubScheduler(schedule_interval=60)
```

### 마이그레이션 비용 조정

**Lambda 값 변경** ([app/optimizer.py](c:\Users\USER\Desktop\carbon\app\optimizer.py):222)
```python
# 기본값: 마이그레이션 페널티 100 gCO2
"lambda_plan_dev": 100.0

# 마이그레이션 장려 (낮은 비용)
"lambda_plan_dev": 50.0

# 마이그레이션 억제 (높은 비용)
"lambda_plan_dev": 200.0
```

### 탄소 강도 변동 조정

**변동폭 조정** ([app/carbon_client.py](c:\Users\USER\Desktop\carbon\app\carbon_client.py):214)
```python
# 기본값: 큰 변동
pattern = (long_wave * 100) + (med_wave * 80) + (short_wave * 60)

# 작은 변동 (마이그레이션 적음)
pattern = (long_wave * 30) + (med_wave * 20) + (short_wave * 10)

# 매우 큰 변동 (마이그레이션 많음)
pattern = (long_wave * 150) + (med_wave * 120) + (short_wave * 90)
```

---

## 🎯 데모 시나리오

### 시나리오 A: 빠른 확인 (2분)

```bash
# 1개 워크로드, 빠른 확인
bash auto-migration-demo.sh 1 6

# 또는 수동
curl -X POST http://localhost:8080/hub/appwrappers \
  -H 'Content-Type: application/json' \
  -d '{"job_id":"quick-test","cpu":2,"mem_gb":4,"data_gb":20,"runtime_minutes":60,"deadline_minutes":480}'

curl -X POST http://localhost:8080/hub/schedule

# 30초마다 확인
watch -n 30 "curl -s http://localhost:8080/hub/appwrappers"
```

### 시나리오 B: 표준 데모 (10분)

```bash
# 3개 워크로드, 20 사이클
bash auto-migration-demo.sh 3 20
```

### 시나리오 C: 프레젠테이션용 (20분)

```bash
# 5개 워크로드, 40 사이클
bash auto-migration-demo.sh 5 40

# Grafana 대시보드를 같이 띄워서 실시간 확인
# http://localhost:3000/d/caspian-hub
```

---

## 🐛 문제 해결

### "No migrations occurring"

**원인:**
- 탄소 강도 차이가 마이그레이션 비용보다 작음
- 워크로드가 없음
- Scheduler가 실행되지 않음

**해결:**
```bash
# 워크로드 확인
curl -s http://localhost:8080/hub/appwrappers

# 탄소 강도 확인
curl -s http://localhost:8080/hub/stats | python -m json.tool

# Scheduler 로그 확인
kubectl --context kind-carbon-hub logs -n caspian-hub -l app=hub-api --tail=50 | grep -i schedule
```

### "Migrations counted but not visible in Grafana"

**원인:**
- Prometheus가 메트릭 수집 전
- 대시보드 새로고침 필요

**해결:**
```bash
# 메트릭 직접 확인
curl -s http://localhost:8080/metrics | grep migration

# Prometheus에서 확인
# http://localhost:9090/graph
# Query: migrations_total

# Grafana 새로고침 (브라우저 F5)
```

### "Hub API not responding"

**해결:**
```bash
# Pod 상태 확인
kubectl --context kind-carbon-hub get pods -n caspian-hub

# 로그 확인
kubectl --context kind-carbon-hub logs -n caspian-hub -l app=hub-api --tail=100

# 재시작
kubectl --context kind-carbon-hub delete pod -n caspian-hub -l app=hub-api
```

---

## 📝 요약

### 핵심 포인트

1. **마이그레이션은 자동이 아닙니다** - 워크로드가 있어야 발생
2. **자동 데모 스크립트 사용** - `bash auto-migration-demo.sh`
3. **Grafana에서 확인** - http://localhost:3000/d/caspian-hub
4. **30초마다 재스케줄링** - 탄소 강도 변화 감지

### 명령어 요약

```bash
# 전체 시스템 시작
bash start-complete-system.sh

# 자동 마이그레이션 데모
bash auto-migration-demo.sh

# 수동 워크로드 생성
curl -X POST http://localhost:8080/hub/appwrappers -H 'Content-Type: application/json' -d '{"job_id":"test","cpu":2,"mem_gb":4,"data_gb":30,"runtime_minutes":60,"deadline_minutes":480}'

# 스케줄링 실행
curl -X POST http://localhost:8080/hub/schedule

# 마이그레이션 확인
curl -s http://localhost:8080/metrics | grep migration

# 전체 시스템 종료
bash stop-all-services.sh
```

---

**작성일**: 2025-10-23
**버전**: 1.0
**프로젝트**: CASPIAN - Carbon-Aware Scheduling Platform
