# CASPIAN 워크로드 마이그레이션 추적 가이드

## 개요

CASPIAN은 탄소 집약도 변화에 따라 워크로드를 최적의 클러스터로 재배치합니다.  
이 문서는 마이그레이션이 발생하는 시점과 방법을 추적하고 모니터링하는 방법을 설명합니다.

## 마이그레이션이 발생하는 경우

### 시나리오: 탄소 집약도 변화

시간에 따라 각 지역의 탄소 집약도가 변경됩니다:

**시간 T1:**
- carbon-kr: 400 gCO2/kWh (최적 - 낮음)
- carbon-jp: 450 gCO2/kWh (중간)
- carbon-cn: 550 gCO2/kWh (높음)

→ 워크로드가 KR에 배치됨

**시간 T2 (5분 후):**
- carbon-kr: 700 gCO2/kWh (높음)
- carbon-jp: 300 gCO2/kWh (최적 - 낮음)
- carbon-cn: 600 gCO2/kWh (중간)

→ **마이그레이션 발생**: KR → JP

## 새롭게 추가된 기능

### 1. Prometheus 메트릭

다음 메트릭이 app/metrics.py에 추가되었습니다:

#### migrations_total
- **타입**: Counter (누적 카운터)
- **레이블**: from_cluster, to_cluster
- **설명**: 클러스터 간 총 마이그레이션 횟수
- **Prometheus 쿼리 예시**:
  - `migrations_total{from_cluster="carbon-kr", to_cluster="carbon-jp"}` - KR에서 JP로의 총 마이그레이션 횟수
  - `sum(migrations_total)` - 모든 마이그레이션 합계

#### migration_data_transferred_gb
- **타입**: Counter
- **레이블**: from_cluster, to_cluster
- **설명**: 마이그레이션 시 전송된 총 데이터량 (GB)
- **Prometheus 쿼리 예시**:
  - `sum(migration_data_transferred_gb{from_cluster="carbon-cn"})` - CN에서 전출된 총 데이터량
  - `sum by (from_cluster, to_cluster) (migration_data_transferred_gb)` - 클러스터별 전송 데이터량

#### migrations_in_progress
- **타입**: Gauge (현재 상태)
- **설명**: 현재 진행 중인 마이그레이션 수
- **Prometheus 쿼리 예시**:
  - `migrations_in_progress` - 현재 진행 중인 마이그레이션

#### migration_cost_gco2
- **타입**: Counter
- **레이블**: from_cluster, to_cluster
- **설명**: 마이그레이션으로 인한 총 탄소 비용 (gCO2)
- **Prometheus 쿼리 예시**:
  - `sum(migration_cost_gco2)` - 총 마이그레이션 탄소 비용
  - `migration_cost_gco2` - 마이그레이션 경로별 비용

### 2. 스케줄러 로그

hub/scheduler.py가 마이그레이션 감지 시 다음과 같이 로그를 남깁니다:

```
MIGRATION detected for job-123: carbon-kr -> carbon-jp, data=50.00GB, cost=100.00gCO2
```

### 3. AppWrapper 메타데이터

마이그레이션된 AppWrapper는 다음 메타데이터를 포함합니다:

```json
{
  "metadata": {
    "migrated_from": "carbon-kr",
    "migration_time": "1729584732.456"
  }
}
```

## 마이그레이션 확인 방법

### 방법 1: Hub API 로그 확인

가장 직접적인 방법입니다. MIGRATION 키워드를 검색하면 모든 마이그레이션 이벤트를 볼 수 있습니다.

```bash
kubectl --context kind-carbon-hub logs -n caspian-hub -l app=hub-api --tail=100 | grep MIGRATION
```

출력 예시:
```
INFO:hub.scheduler:  MIGRATION detected for migration-test: carbon-kr -> carbon-jp, data=50.00GB, cost=100.00gCO2
```

### 방법 2: AppWrapper 상태 추적

AppWrapper를 제출하고 시간에 따른 클러스터 할당 변화를 모니터링합니다.

```bash
# 1. 데이터가 있는 워크로드 제출
curl -X POST http://localhost:8080/hub/appwrappers -H 'Content-Type: application/json' -d '{"job_id":"track-migration-1","cpu":2.0,"mem_gb":4.0,"data_gb":10.0,"runtime_minutes":60,"deadline_minutes":240}'

# 2. 첫 스케줄링 및 배포
curl -X POST http://localhost:8080/hub/schedule
curl -X POST http://localhost:8080/hub/dispatch

# 3. 현재 할당 클러스터 확인
curl -s http://localhost:8080/hub/appwrappers | python -m json.tool

# 4. 5분 후 재스케줄링 (탄소 집약도 변화 대기)
sleep 300
curl -X POST http://localhost:8080/hub/schedule

# 5. 마이그레이션 발생 확인
curl -s http://localhost:8080/hub/appwrappers | python -m json.tool
```

### 방법 3: Prometheus 메트릭 쿼리

Prometheus에서 직접 메트릭을 쿼리합니다.

```bash
# 총 마이그레이션 횟수
curl -s 'http://localhost:9090/api/v1/query?query=sum(migrations_total)' | python -m json.tool

# 총 전송된 데이터량
curl -s 'http://localhost:9090/api/v1/query?query=sum(migration_data_transferred_gb)' | python -m json.tool
```

### 방법 4: Kubernetes Job 추적

실제 Job이 어느 클러스터에서 실행 중인지 확인합니다.

```bash
# 모든 클러스터의 Job 확인
kubectl --context kind-carbon-kr get jobs,pods -A
kubectl --context kind-carbon-jp get jobs,pods -A
kubectl --context kind-carbon-cn get jobs,pods -A
```

## 마이그레이션 비용 계산

마이그레이션 비용은 app/optimizer.py (lines 103-104)에서 계산됩니다:

```python
net_cost = net_matrix.get(prev_r, {}).get(r, 0.0)
cost += lam_dev + (net_cost * j.data_gb)
```

**변수 설명:**
- `lam_dev`: 기본 마이그레이션 페널티 = **100.0 gCO2**
- `net_cost`: 클러스터 간 네트워크 비용 (현재 0)
- `j.data_gb`: 전송할 데이터 크기 (GB)

**현재 구현에서의 비용:**
```
migration_cost = 100.0 gCO2 (고정)
```

향후 네트워크 비용 매트릭스가 추가되면:
```
migration_cost = 100.0 + (net_cost_per_gb * data_gb)
```

## 구현 세부사항

### 파일 변경 사항

#### 1. app/metrics.py
- 4개의 새로운 메트릭 추가 (lines 95-121)
- setup_metrics() 함수 업데이트 (lines 80-93)

#### 2. hub/scheduler.py
- 마이그레이션 메트릭 import 추가 (lines 20-25)
- _update_appwrappers() 메서드 업데이트 (lines 270-344)
  - 이전 클러스터 확인 로직 (lines 286-288)
  - 마이그레이션 감지 및 메트릭 기록 (lines 291-319)
  - 메타데이터에 마이그레이션 정보 추가 (lines 333-335)

### 마이그레이션 감지 로직

```python
# 이전 클러스터 할당 확인
previous_cluster = appwrapper.spec.target_cluster
new_cluster = decision.target_cluster

# 마이그레이션 조건:
# 1. 이전 할당이 존재함 (previous_cluster is not None)
# 2. 새 할당이 이전과 다름 (previous_cluster != new_cluster)
is_migration = previous_cluster and previous_cluster != new_cluster
```

이 로직은 다음을 구분합니다:
- **최초 배치**: previous_cluster = None → 마이그레이션 아님
- **재할당 (동일 클러스터)**: previous_cluster == new_cluster → 마이그레이션 아님
- **마이그레이션**: previous_cluster != new_cluster → **마이그레이션!**

---

**작성일**: 2025-10-22  
**버전**: 1.0.0
