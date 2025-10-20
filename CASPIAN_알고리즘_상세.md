# CASPIAN 알고리즘 상세 설명

## 🎯 CASPIAN이란?

**C**arbon-**A**ware **S**cheduling using Integer Linear **P**rogramming **A**nd **N**etwork optimization

탄소 배출을 최소화하는 Kubernetes 워크로드 스케줄링 알고리즘

---

## 📐 수학적 모델

### 목적 함수 (Objective Function)

```
minimize: Σ (탄소_비용 + 마이그레이션_비용)
```

**상세**:
```
minimize: Σ(j,r,t) x[j,r,t] × (CI[r,t] × E[j] + MigrationCost[j,r])

여기서:
- x[j,r,t]: 의사결정 변수 (0 또는 1)
- j: Job ID
- r: Region (클러스터)
- t: 시작 시간 슬롯
- CI[r,t]: Region r의 시간 t에서의 탄소 강도 (gCO2/kWh)
- E[j]: Job j의 에너지 소비 (kWh)
- MigrationCost: 마이그레이션 페널티
```

### 의사결정 변수

```python
x[job_id, region, start_time] ∈ {0, 1}

x[j,r,t] = {
    1  if Job j가 Region r에서 시간 t에 시작
    0  otherwise
}
```

**예시**:
```
x["test-job-1", "carbon-kr", 0] = 1  # KR에서 즉시 시작
x["test-job-1", "carbon-jp", 0] = 0  # JP에서는 시작 안 함
```

---

## 🔢 제약 조건 (Constraints)

### 1. 각 Job은 정확히 한 번만 스케줄링

```
Σ(r,t) x[j,r,t] = 1  for all j

즉, 각 Job은 하나의 (region, time)에만 배치
```

**코드** (`optimizer.py` 110-121줄):
```python
for j in jobs:
    starts = []
    for r in regions:
        for t in range(j.release_slot, j.deadline_slot - j.runtime_slots + 1):
            if (j.job_id, r, t) in x:
                starts.append(x[(j.job_id, r, t)])

    if starts:
        prob += pulp.lpSum(starts) == 1  # 정확히 1개만 선택
```

---

### 2. 리소스 용량 제한

```
Σ(j: running at time τ) ResourceUsage[j] ≤ Capacity[r,τ]

각 시간 슬롯에서:
- CPU 사용량 ≤ CPU 용량
- Memory 사용량 ≤ Memory 용량
- GPU 사용량 ≤ GPU 용량
```

**코드** (`optimizer.py` 123-152줄):
```python
for r in regions:
    for tau in range(H):  # 각 시간 슬롯
        # CPU 제약
        cpu_usage = []
        for j in jobs:
            for t in range(max(0, tau - j.runtime_slots + 1), tau + 1):
                # Job이 시간 tau에 실행 중이면
                if t <= tau < t + j.runtime_slots:
                    cpu_usage.append(x[(j.job_id, r, t)] * j.cpu)

        prob += pulp.lpSum(cpu_usage) <= capacity["cpu"]
```

---

### 3. 시간 윈도우 제약

```
release_slot ≤ start_time ≤ deadline_slot - runtime_slots

Job은 release 이후, deadline 전에 완료되어야 함
```

**코드** (`optimizer.py` 66줄):
```python
for t in range(j.release_slot, min(j.deadline_slot - j.runtime_slots + 1, H)):
    # 이 범위 내에서만 변수 생성
    x[(j.job_id, r, t)] = pulp.LpVariable(...)
```

---

### 4. Affinity 제약 (선호 클러스터)

```
if affinity_regions is not empty:
    x[j,r,t] = 0  for r not in affinity_regions
```

**코드** (`optimizer.py` 61-63줄):
```python
for r in regions:
    if j.affinity_regions and r not in j.affinity_regions:
        continue  # 변수 생성 안 함 (자동으로 0)
```

---

## ⚡ 에너지 및 탄소 계산

### 에너지 소비 계산

```
Energy[j,t] = CPU[j] × WattPerCPU × Duration × (1/1000)

여기서:
- CPU[j]: Job의 CPU 코어 수
- WattPerCPU: CPU 코어당 와트 (기본값: 30W)
- Duration: 실행 시간 (시간 단위)
- 1/1000: Wh → kWh 변환
```

**코드** (`optimizer.py` 88-92줄):
```python
SLOT_HOURS = inp.slot_seconds / 3600.0  # 슬롯을 시간으로
watt_cpu = 30.0  # CPU 코어당 30W

# 모든 실행 슬롯의 탄소 비용 합산
ci_sum = sum(
    ci[(r, tau)] * (j.cpu * watt_cpu * SLOT_HOURS / 1000.0)
    for tau in range(t, t + j.runtime_slots)
)
```

**예시**:
```
Job:
- CPU: 2 코어
- Runtime: 30분 (6 슬롯, 각 5분)
- WattPerCPU: 30W

Energy per slot = 2 × 30W × (5/60)시간 = 5 Wh = 0.005 kWh
Total Energy = 0.005 kWh × 6 슬롯 = 0.03 kWh
```

### 탄소 배출 계산

```
Carbon[j,r,t] = Σ(τ=t to t+runtime) CI[r,τ] × Energy[j]

여기서:
- CI[r,τ]: Region r의 시간 τ 탄소 강도 (gCO2/kWh)
- Energy[j]: Job의 에너지 소비 (kWh)
```

**예시**:
```
Region: carbon-kr
CI: [350, 340, 330, 320, 310, 300] gCO2/kWh (6 슬롯)
Energy: 0.005 kWh per slot

Carbon = (350×0.005 + 340×0.005 + ... + 300×0.005)
       = (350 + 340 + 330 + 320 + 310 + 300) × 0.005
       = 1950 × 0.005
       = 9.75 gCO2
```

---

## 🔄 마이그레이션 비용

### 마이그레이션이란?

이전에 다른 클러스터에서 실행되던 Job을 새 클러스터로 이동

### 마이그레이션 비용 계산

```
MigrationCost[j,r] = {
    0                           if r == prev_region
    λ + NetCost × DataSize      if migration allowed
    ∞ (1e6)                     if migration not allowed
}

여기서:
- λ: 마이그레이션 페널티 (기본값: 100)
- NetCost: 네트워크 비용 (region 간)
- DataSize: 데이터 크기 (GB)
```

**코드** (`optimizer.py` 96-104줄):
```python
if prev_r:  # 이전 배치가 있으면
    if not allow_mig and r != prev_r:
        # 마이그레이션 금지
        cost += 1e6
    elif allow_mig and r != prev_r:
        # 마이그레이션 페널티 + 네트워크 비용
        net_cost = network_matrix[prev_r][r]
        cost += lambda_dev + (net_cost * j.data_gb)
```

---

## 🔄 3단계 스케줄링 프로세스

### 전체 흐름

```
User → POST /hub/appwrappers → HubStore
                                   ↓
                    [5분마다 자동 실행]
                                   ↓
                           HubScheduler
                                   ↓
        ┌──────────────────────────┼──────────────────────────┐
        ↓                          ↓                          ↓
    Step 1                     Step 2                     Step 3
 Collect Info              Optimize                   Update
        ↓                          ↓                          ↓
   ClusterInfo          CASPIAN Algorithm          targetCluster
   (carbon, CPU)        (MILP Solver)              gate=OPEN
```

---

### Step 1: Collect (정보 수집)

**위치**: `hub/scheduler.py` (133-145줄)

**수집 정보**:
```python
ClusterInfo {
    name: "carbon-kr"
    carbon_intensity: 350  # gCO2/kWh
    resources: {
        cpu_available: 14.0
        cpu_total: 16.0
        mem_available_gb: 28.0
        mem_total_gb: 32.0
    }
    status: "ready"
}
```

**프로세스**:
1. HubStore에서 Ready 상태 클러스터 조회
2. 각 클러스터의 탄소 강도 확인
3. 리소스 가용량 확인

**코드**:
```python
async def _collect_cluster_info(self) -> List[ClusterInfo]:
    cluster_infos = await hub_store.get_ready_clusters()

    logger.info(f"Collected info from {len(cluster_infos)} clusters")
    for ci in cluster_infos:
        logger.info(
            f"  - {ci.name}: CI={ci.carbon_intensity} gCO2/kWh, "
            f"CPU={ci.resources.cpu_available}/{ci.resources.cpu_total}"
        )

    return cluster_infos
```

---

### Step 2: Optimize (CASPIAN 최적화)

**위치**: `hub/scheduler.py` (147-244줄), `app/optimizer.py`

#### 2.1 데이터 변환

**AppWrapper → JobSpec**:
```python
AppWrapper {
    job_id: "test-job-1"
    cpu: 2.0
    mem_gb: 4.0
    runtime_minutes: 30
    deadline_minutes: 120
}
↓
JobSpec {
    job_id: "test-job-1"
    cpu: 2.0
    mem_gb: 4.0
    runtime_slots: 6     # 30분 ÷ 5분 슬롯
    deadline_slot: 24    # 120분 ÷ 5분 슬롯
    release_slot: 0
}
```

**ClusterInfo → ClusterCapacity + CarbonPoint**:
```python
ClusterInfo {
    name: "carbon-kr"
    carbon_intensity: 350
    cpu_available: 14.0
}
↓
ClusterCapacity {
    region: "carbon-kr"
    slot: 0
    cpu_cap: 14.0
    mem_gb_cap: 28.0
}
+
CarbonPoint {
    region: "carbon-kr"
    slot: 0
    ci_gco2_per_kwh: 350
}
```

#### 2.2 MILP 문제 구성

**변수 생성**:
```python
# 각 (Job, Region, Time) 조합에 대해 0/1 변수 생성
x["test-job-1", "carbon-kr", 0] = LpVariable(...)
x["test-job-1", "carbon-jp", 0] = LpVariable(...)
x["test-job-1", "carbon-cn", 0] = LpVariable(...)
```

**목적 함수**:
```python
minimize:
    x["test-job-1","carbon-kr",0] × (CI_kr × Energy)
  + x["test-job-1","carbon-jp",0] × (CI_jp × Energy)
  + x["test-job-1","carbon-cn",0] × (CI_cn × Energy)
```

**제약 조건 추가**:
```python
# 1. 정확히 한 번만
x["test-job-1","carbon-kr",0]
+ x["test-job-1","carbon-jp",0]
+ x["test-job-1","carbon-cn",0] == 1

# 2. CPU 용량
Σ(running jobs) cpu_usage ≤ 14.0  # for carbon-kr
```

#### 2.3 솔버 실행

**사용 솔버**: CBC (COIN-OR Branch and Cut)

```python
solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=10)
status = prob.solve(solver)
```

**솔버 선택 이유**:
- ✅ 무료 오픈소스
- ✅ MILP (Mixed Integer Linear Programming) 지원
- ✅ 빠른 성능 (10초 타임아웃)
- ✅ Python PuLP와 통합

#### 2.4 결과 추출

```python
# x 변수 값 확인
for (j, r, t), var in x.items():
    if pulp.value(var) > 0.5:  # 1로 선택됨
        chosen = (r, t)
        break

# 결과
SchedulingDecision {
    job_id: "test-job-1"
    target_cluster: "carbon-kr"  # 최소 탄소 배출
    estimated_co2_g: 9.75
}
```

---

### Step 3: Update (AppWrapper 업데이트)

**위치**: `hub/scheduler.py` (246-280줄)

**업데이트 내용**:
```python
Before:
AppWrapper {
    spec: {
        job_id: "test-job-1"
        target_cluster: null          # 미배정
        dispatching_gates: [
            {status: "closed"}        # 닫힘
        ]
    }
    status: {
        phase: "Pending"
    }
}

After (Step 3):
AppWrapper {
    spec: {
        job_id: "test-job-1"
        target_cluster: "carbon-kr"   # ← 최적 클러스터 설정
        dispatching_gates: [
            {
                status: "open"        # ← 게이트 열림
                reason: "Optimal placement for minimum carbon footprint"
            }
        ]
    }
    status: {
        phase: "Pending"              # 아직 Pending
    }
    metadata: {
        scheduled_at: 1760899503.3
        estimated_co2_g: 9.75
    }
}
```

**코드**:
```python
async def _update_appwrappers(self, decisions: List[SchedulingDecision]):
    for decision in decisions:
        appwrapper = await hub_store.get_appwrapper(decision.job_id)

        # targetCluster 설정
        appwrapper.spec.target_cluster = decision.target_cluster

        # Gate OPEN
        appwrapper.spec.dispatching_gates[0].status = GateStatus.OPEN
        appwrapper.spec.dispatching_gates[0].reason = \
            "Optimal placement for minimum carbon footprint"

        # 메타데이터 업데이트
        appwrapper.metadata.scheduled_at = time.time()
        appwrapper.metadata.estimated_co2_g = str(decision.estimated_co2_g)

        await hub_store.update_appwrapper(decision.job_id, appwrapper)
```

---

## 🚀 Dispatch (Job 배포)

**위치**: `hub/dispatcher.py`

**실행 주기**: 30초마다 자동

### 프로세스

```
[30초마다 실행]
    ↓
HubDispatcher
    ↓
gate=OPEN인 AppWrapper 찾기
    ↓
Kubernetes Job 매니페스트 생성
    ↓
kubectl apply (target_cluster context 사용)
    ↓
AppWrapper 상태 업데이트: Running
```

### Job 매니페스트 생성

**코드** (`hub/dispatcher.py` 150-180줄):
```python
def _create_job_manifest(appwrapper: AppWrapper) -> dict:
    spec = appwrapper.spec

    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": spec.job_id,
            "labels": {
                "app": "caspian",
                "job-id": spec.job_id,
                "carbon-aware": "true"
            }
        },
        "spec": {
            "template": {
                "spec": {
                    "containers": [{
                        "name": spec.job_id,
                        "image": spec.image,
                        "command": spec.command,
                        "resources": {
                            "requests": {
                                "cpu": str(spec.cpu),
                                "memory": f"{spec.mem_gb}Gi"
                            },
                            "limits": {
                                "cpu": str(spec.cpu),
                                "memory": f"{spec.mem_gb}Gi"
                            }
                        }
                    }],
                    "restartPolicy": "Never"
                }
            }
        }
    }
```

### Kubernetes 배포

```python
async def _dispatch_appwrapper(appwrapper: AppWrapper):
    target_cluster = appwrapper.spec.target_cluster
    cluster_info = await hub_store.get_cluster_info(target_cluster)

    # Kubernetes Client 생성 (context 전환)
    batch_api = self._get_k8s_client(cluster_info.kubeconfig_context)

    # Job 생성
    job_manifest = self._create_job_manifest(appwrapper)
    await asyncio.to_thread(
        batch_api.create_namespaced_job,
        namespace="default",
        body=job_manifest
    )

    # AppWrapper 상태 업데이트
    appwrapper.status.dispatched = True
    appwrapper.status.phase = "Running"
    appwrapper.status.cluster = target_cluster
    appwrapper.status.start_time = time.time()
```

---

## 📊 실제 예제

### 시나리오

**Job**:
```json
{
  "job_id": "ml-training-1",
  "cpu": 4.0,
  "mem_gb": 8.0,
  "runtime_minutes": 60,
  "deadline_minutes": 180
}
```

**Clusters**:
```
carbon-kr: CI = 320 gCO2/kWh, CPU = 14/16
carbon-jp: CI = 450 gCO2/kWh, CPU = 14/16
carbon-cn: CI = 620 gCO2/kWh, CPU = 14/16
```

---

### Step 1: Collect

```python
ClusterInfo [
    {name: "carbon-kr", carbon_intensity: 320, cpu_available: 14},
    {name: "carbon-jp", carbon_intensity: 450, cpu_available: 14},
    {name: "carbon-cn", carbon_intensity: 620, cpu_available: 14}
]
```

---

### Step 2: Optimize

**변환**:
```python
JobSpec {
    job_id: "ml-training-1"
    cpu: 4.0
    mem_gb: 8.0
    runtime_slots: 12  # 60분 ÷ 5분
    deadline_slot: 36  # 180분 ÷ 5분
}
```

**에너지 계산**:
```
Energy per slot = 4 CPU × 30W × (5/60)h = 10 Wh = 0.01 kWh
Total Energy = 0.01 kWh × 12 슬롯 = 0.12 kWh
```

**탄소 비용 계산**:
```
carbon-kr: 320 × 0.12 = 38.4 gCO2   ← 최소
carbon-jp: 450 × 0.12 = 54.0 gCO2
carbon-cn: 620 × 0.12 = 74.4 gCO2
```

**솔버 결과**:
```
x["ml-training-1", "carbon-kr", 0] = 1  ← 선택
x["ml-training-1", "carbon-jp", 0] = 0
x["ml-training-1", "carbon-cn", 0] = 0

Decision: carbon-kr, CO2 = 38.4 gCO2
```

---

### Step 3: Update

```python
AppWrapper.spec.target_cluster = "carbon-kr"
AppWrapper.spec.dispatching_gates[0].status = "open"
AppWrapper.metadata.estimated_co2_g = "38.4"
```

---

### Dispatch

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: ml-training-1
spec:
  template:
    spec:
      containers:
      - name: ml-training-1
        image: busybox:latest
        resources:
          requests:
            cpu: "4.0"
            memory: "8Gi"
```

**배포**:
```bash
kubectl --context kind-carbon-kr apply -f job.yaml
```

---

## 🎯 알고리즘 특징

### 장점

1. **최적화 보장**: MILP 솔버 사용으로 수학적 최적해
2. **멀티 제약**: 리소스, 시간, affinity 모두 고려
3. **유연성**: 마이그레이션 허용/금지 선택 가능
4. **실시간**: 10초 타임아웃으로 빠른 결정
5. **확장성**: 여러 Job, 여러 클러스터 동시 처리

### 단점

1. **복잡도**: Job과 Region이 많으면 계산 시간 증가
2. **정적 예측**: 미래 탄소 강도 예측 없음 (현재 값 사용)
3. **메모리**: 모든 변수를 메모리에 저장

---

## 🔧 파라미터 조정

### 에너지 관련

**`watt_cpu`** (기본값: 30W):
```python
# app/optimizer.py 48줄
watt_cpu = float(inp.costs.get("watt_cpu", 30.0))
```

더 정확한 값:
- Intel Xeon: 35W/코어
- AMD EPYC: 25W/코어
- ARM: 10W/코어

---

### 마이그레이션 관련

**`lambda_plan_dev`** (기본값: 100):
```python
# app/optimizer.py 49줄
lam_dev = float(inp.costs.get("lambda_plan_dev", 100.0))
```

- 높은 값: 마이그레이션 회피
- 낮은 값: 탄소 절감 우선

---

### 시간 슬롯

**슬롯 크기** (기본값: 5분 = 300초):
```python
# hub/scheduler.py 167줄
runtime_slots = max(1, spec.runtime_minutes // 5)
```

변경:
```python
SLOT_MINUTES = 10  # 10분 슬롯
runtime_slots = max(1, spec.runtime_minutes // SLOT_MINUTES)
```

---

### 솔버 타임아웃

**타임아웃** (기본값: 10초):
```python
# app/optimizer.py 155줄
solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=10)
```

변경:
```python
solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=30)  # 30초
```

---

## 📈 성능 분석

### 변수 개수

```
총 변수 = Jobs × Regions × TimeSlots

예:
- 10 Jobs
- 3 Regions
- 24 TimeSlots (2시간, 5분 슬롯)

= 10 × 3 × 24 = 720 변수
```

### 제약 개수

```
제약 = Jobs (스케줄링) + Regions × TimeSlots × Resources (용량)

예:
- 10 Jobs
- 3 Regions
- 24 TimeSlots
- 2 Resources (CPU, Memory)

= 10 + (3 × 24 × 2) = 154 제약
```

### 솔버 시간

| Jobs | Regions | TimeSlots | 변수 | 시간 |
|------|---------|-----------|------|------|
| 5 | 3 | 12 | 180 | <1초 |
| 10 | 3 | 24 | 720 | 1-2초 |
| 20 | 5 | 48 | 4,800 | 3-5초 |
| 50 | 10 | 96 | 48,000 | 8-10초 |

---

## 📚 참고 자료

### 코드 위치

| 기능 | 파일 | 라인 |
|------|------|------|
| MILP 최적화 | `app/optimizer.py` | 14-194 |
| Step 1: Collect | `hub/scheduler.py` | 133-145 |
| Step 2: Optimize | `hub/scheduler.py` | 147-244 |
| Step 3: Update | `hub/scheduler.py` | 246-280 |
| Dispatch | `hub/dispatcher.py` | 85-140 |

### 관련 문서

- **[프로젝트_구조.md](프로젝트_구조.md)** - 파일 구조
- **[MOCK_데이터_설정_가이드.md](MOCK_데이터_설정_가이드.md)** - Mock 데이터
- **[README.md](README.md)** - 전체 개요

---

**CASPIAN: 탄소를 고려하는 스마트한 스케줄러** 🌱⚡
