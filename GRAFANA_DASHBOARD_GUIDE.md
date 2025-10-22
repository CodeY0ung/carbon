# CASPIAN Grafana 대시보드 설명

## 접속 정보
- URL: http://localhost:3000/d/caspian-hub
- 계정: admin / admin

---

## 대시보드 패널 설명

### 1. 탄소 집약도 모니터링 (Carbon Intensity)

#### Korea Carbon Intensity (게이지)
- **의미**: 한국 전력망의 현재 탄소 집약도
- **단위**: gCO2/kWh (킬로와트시당 이산화탄소 그램)
- **쿼리**: `grid_carbon_intensity_gco2_per_kwh{zone="KR"}`
- **해석**: 
  - 낮을수록 친환경 (재생에너지 비중 높음)
  - 높을수록 탄소 집약적 (화석연료 비중 높음)
- **예시**: 326 gCO2/kWh = 1kWh 전기 생산 시 326g의 CO2 배출

#### Japan Carbon Intensity (게이지)
- **의미**: 일본 전력망의 현재 탄소 집약도
- **쿼리**: `grid_carbon_intensity_gco2_per_kwh{zone="JP"}`
- **특징**: KR과 번갈아가며 최적이 되도록 설계됨

#### China Carbon Intensity (게이지)
- **의미**: 중국 전력망의 현재 탄소 집약도
- **쿼리**: `grid_carbon_intensity_gco2_per_kwh{zone="CN"}`
- **특징**: 석탄 중심으로 항상 가장 높음 (550-750 범위)

#### Carbon Intensity Over Time (시계열 그래프)
- **의미**: 3개 지역의 탄소 집약도 변화 추이
- **쿼리**: 
  - `grid_carbon_intensity_gco2_per_kwh{zone="KR"}`
  - `grid_carbon_intensity_gco2_per_kwh{zone="JP"}`
  - `grid_carbon_intensity_gco2_per_kwh{zone="CN"}`
- **해석**: 
  - 선이 교차하는 지점 = 최적 지역 변경 (마이그레이션 트리거!)
  - 급격한 하락 = 재생에너지 급증
  - 급격한 상승 = 수요 급증 또는 화석연료 발전 증가

---

### 2. 워크로드 상태 (AppWrapper Status)

#### Total AppWrappers (통계)
- **의미**: 시스템에 제출된 총 작업(워크로드) 수
- **쿼리**: `appwrappers_total`
- **예시**: 1 = 현재 1개의 작업이 시스템에 존재

#### Pending AppWrappers (통계)
- **의미**: 스케줄링 대기 중인 작업 수
- **쿼리**: `appwrappers_pending`
- **상태**: 아직 클러스터에 배치되지 않음
- **예시**: 0 = 대기 중인 작업 없음

#### Running AppWrappers (통계)
- **의미**: 현재 실행 중인 작업 수
- **쿼리**: `appwrappers_running`
- **상태**: 클러스터에 배치되어 실행 중
- **예시**: 1 = 1개의 작업이 실행 중

#### Completed AppWrappers (통계)
- **의미**: 완료된 작업 수
- **쿼리**: `appwrappers_completed`
- **상태**: 실행이 끝난 작업
- **예시**: 0 = 아직 완료된 작업 없음

---

### 3. 클러스터 상태 (Cluster Status)

#### Total Clusters (통계)
- **의미**: 시스템에 등록된 총 클러스터 수
- **쿼리**: `clusters_total`
- **예시**: 3 = KR, JP, CN 클러스터

#### Ready Clusters (통계)
- **의미**: 정상 작동 중인 클러스터 수
- **쿼리**: `clusters_ready`
- **해석**: Ready/Total이 100%가 아니면 일부 클러스터에 문제
- **예시**: 3/3 = 모든 클러스터 정상

---

### 4. 마이그레이션 추적 (Migration Tracking)

**참고**: 이 패널들은 최근에 추가되었으며, 시스템 재시작 후 표시됩니다.

#### Total Migrations (통계)
- **의미**: 발생한 총 마이그레이션 횟수
- **쿼리**: `sum(migrations_total)`
- **해석**: 탄소 집약도 변화로 인해 작업이 다른 클러스터로 이동한 횟수
- **예시**: 5 = 5번의 마이그레이션 발생

#### Data Transferred (GB) (통계)
- **의미**: 마이그레이션으로 전송된 총 데이터량
- **쿼리**: `sum(migration_data_transferred_gb)`
- **단위**: GB (기가바이트)
- **해석**: 작업을 옮기면서 함께 이동한 데이터
- **예시**: 500 GB = 총 500GB의 데이터가 클러스터 간 이동

#### Migration Carbon Cost (gCO2) (통계)
- **의미**: 마이그레이션으로 인한 탄소 비용
- **쿼리**: `sum(migration_cost_gco2)`
- **계산**: 100 gCO2 (기본) + (네트워크 비용 × 데이터량)
- **해석**: 마이그레이션 자체가 탄소를 배출함 (네트워크 전송 비용)
- **예시**: 500 gCO2 = 마이그레이션으로 500g의 CO2 추가 배출

#### Migrations In Progress (통계)
- **의미**: 현재 진행 중인 마이그레이션 수
- **쿼리**: `migrations_in_progress`
- **해석**: 실시간으로 이동 중인 작업
- **예시**: 0 = 현재 이동 중인 작업 없음

#### Migration Matrix (테이블)
- **의미**: 클러스터 간 마이그레이션 경로별 횟수
- **쿼리**: `migrations_total`
- **형식**: From Cluster → To Cluster: Count
- **해석**: 어느 클러스터에서 어디로 주로 이동하는지 분석
- **예시**:
  ```
  carbon-kr → carbon-jp: 3
  carbon-jp → carbon-kr: 2
  carbon-kr → carbon-cn: 0
  ```
  KR↔JP 간 마이그레이션이 주로 발생

#### Migrations Over Time (시계열 그래프)
- **의미**: 시간에 따른 마이그레이션 발생률
- **쿼리**: `rate(migrations_total[5m])`
- **단위**: 마이그레이션/초
- **해석**: 
  - 스파이크 = 그 시점에 마이그레이션 발생
  - 평평한 선 = 마이그레이션 없음
- **활용**: 마이그레이션 패턴 및 빈도 분석

---

## 실전 시나리오 해석

### 시나리오 1: 정상 운영 중

**보이는 것:**
- KR: 350, JP: 380, CN: 650
- Total AppWrappers: 5
- Running: 5, Pending: 0, Completed: 0
- Total Migrations: 0

**의미:**
- KR이 최적이므로 모든 작업이 KR에 배치됨
- 아직 마이그레이션 발생 안 함
- 시스템 정상 작동 중

---

### 시나리오 2: 마이그레이션 발생!

**Before (T0):**
- KR: 350 ← BEST
- JP: 380
- CN: 650
- Job on: carbon-kr
- Total Migrations: 0

**Event (T1):**
- Carbon Intensity Over Time 그래프에서 KR 선 급등, JP 선 하락
- 두 선이 교차!

**After (T2):**
- KR: 450
- JP: 320 ← NEW BEST
- CN: 640
- Job on: carbon-jp ← MIGRATED!
- Total Migrations: 1 ↑
- Data Transferred: 100 GB ↑
- Migration Cost: 100 gCO2 ↑

**Migration Matrix:**
```
carbon-kr → carbon-jp: 1  (new!)
```

**의미:**
- JP의 탄소 집약도가 급락 (재생에너지 급증?)
- 시스템이 자동으로 작업을 KR에서 JP로 이동
- 100GB 데이터와 함께 전송
- 마이그레이션 비용: 100 gCO2

---

### 시나리오 3: 불규칙한 패턴

**Carbon Intensity Over Time 그래프:**
```
Time    KR    JP    CN    
0:00   380   420   650   
0:30   340   390   630   (KR 하락)
1:00   250   410   660   (KR 급락! 재생에너지 급증)
1:30   320   380   640   
2:00   370   330   620   (JP 급락! 역전!)
2:30   410   480   630   (JP 급등! 수요 증가)
```

**마이그레이션:**
- 1:00 → 작업 이미 KR에 있음, 유지
- 2:00 → JP가 최적이 되어 KR → JP 마이그레이션
- 2:30 → JP 급등하지만 여전히 최적, 유지

---

## 주요 인사이트

### 1. 탄소 집약도와 마이그레이션의 관계
- **교차 지점** = 마이그레이션 트리거
- **큰 격차** = 안정적 (마이그레이션 없음)
- **지그재그 패턴** = 빈번한 마이그레이션 (비효율적일 수 있음)

### 2. 마이그레이션 비용 vs 절감 효과
- **마이그레이션 비용**: 고정 100 gCO2 + 네트워크 전송
- **절감 효과**: (이전 CI - 새 CI) × 전력 사용량 × 실행 시간
- **최적화 목표**: 절감 효과 > 마이그레이션 비용

### 3. 패턴 분석
- **Migration Matrix**: 주로 이동하는 경로 파악
- **Over Time 그래프**: 마이그레이션 주기 분석
- **Carbon Intensity**: 각 지역의 전력망 특성 이해

---

## 대시보드 활용 팁

### 실시간 모니터링
1. **Carbon Intensity Over Time** 그래프를 주시
2. 선이 교차하는 순간 = 마이그레이션 가능성
3. **Running AppWrappers** 확인 (실행 중인 작업이 있어야 마이그레이션 가능)

### 마이그레이션 확인
1. **Total Migrations** 숫자 증가 확인
2. **Migration Matrix** 테이블에서 경로 확인
3. Hub API 로그 확인:
   ```bash
   kubectl logs -l app=hub-api | grep MIGRATION
   ```

### 최적화 분석
1. **Total Migrations** vs **Migration Cost** 비율
2. 너무 빈번한 마이그레이션 = 비효율적
3. 마이그레이션 없음 = 탄소 최적화 기회 놓침

---

**작성일**: 2025-10-22  
**대시보드 버전**: 1.0 (16 panels)
