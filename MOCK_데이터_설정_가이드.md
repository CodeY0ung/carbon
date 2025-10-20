# Mock 데이터 설정 가이드

## 🎯 Mock 데이터란?

실제 ElectricityMap API를 호출하지 않고, 시뮬레이션된 탄소 강도 데이터를 사용합니다.

**장점**:
- ✅ API 키 불필요
- ✅ 무료 (API 호출 제한 없음)
- ✅ 시간대별 패턴 시뮬레이션
- ✅ 테스트 및 데모에 적합

---

## 🔧 Mock 모드 활성화/비활성화

### 방법 1: 환경변수 (권장)

**Mock 모드 활성화** (기본값):
```bash
export USE_MOCK_DATA=true
```

**실제 API 사용**:
```bash
export USE_MOCK_DATA=false
export ELECTRICITYMAP_API_KEY=your_actual_api_key
```

### 방법 2: docker-compose.yml 수정

**파일**: `docker-compose.yml`

```yaml
services:
  hub:
    environment:
      - USE_MOCK_DATA=true    # Mock 모드
      # 또는
      - USE_MOCK_DATA=false   # 실제 API
```

변경 후:
```bash
docker-compose up -d --build hub
```

---

## 📊 Mock 데이터 값 조절

### 위치: `app/carbon_client.py`

#### 1. 기본 탄소 강도 설정

**25-32줄**: `MOCK_DATA` 딕셔너리

```python
MOCK_DATA = {
    "CA": {"carbonIntensity": 120, "fossilFreePercentage": 75},
    "BR": {"carbonIntensity": 180, "fossilFreePercentage": 65},
    "BO": {"carbonIntensity": 450, "fossilFreePercentage": 35},
    "CN": {"carbonIntensity": 650, "fossilFreePercentage": 20},  # 항상 최악
    "KR": {"carbonIntensity": 350, "fossilFreePercentage": 45},  # 중간, 변동
    "JP": {"carbonIntensity": 380, "fossilFreePercentage": 40},  # 중간, 변동
}
```

**설정 항목**:
- `carbonIntensity`: 기본 탄소 강도 (gCO2/kWh)
- `fossilFreePercentage`: 재생에너지 비율 (%)

**예시 - 한국을 더 낮게**:
```python
"KR": {"carbonIntensity": 250, "fossilFreePercentage": 60},  # 더 친환경
```

---

#### 2. 변동 폭 조절

**197-224줄**: 각 지역별 변동 패턴

```python
if zone == "KR":
    # Korea: 변동 폭 조절
    wave = math.sin(phase * 2 * math.pi)
    carbon_offset = int(wave * 30)  # ±30 gCO2/kWh 변동
```

**변동 폭 값**:
- `wave * 30`: ±30 범위로 변동
- `wave * 50`: ±50 범위로 변동 (더 큰 변동)
- `wave * 10`: ±10 범위로 변동 (작은 변동)

**예시 - KR 변동 크게**:
```python
if zone == "KR":
    wave = math.sin(phase * 2 * math.pi)
    carbon_offset = int(wave * 80)  # ±80 gCO2/kWh (큰 변동)
```

---

#### 3. 변동 주기 조절

**192줄**: `cycle_seconds` 값

```python
cycle_seconds = 300  # 5분 = 300초
```

**변경 예시**:
```python
cycle_seconds = 600   # 10분 주기
cycle_seconds = 60    # 1분 주기 (빠른 변동)
cycle_seconds = 1800  # 30분 주기 (느린 변동)
```

---

#### 4. 랜덤 노이즈 조절

**227줄**: 작은 랜덤 노이즈

```python
noise = random.randint(-15, 15)  # ±15 gCO2/kWh 랜덤
```

**변경 예시**:
```python
noise = random.randint(-5, 5)    # 작은 노이즈
noise = random.randint(-30, 30)  # 큰 노이즈
noise = 0                        # 노이즈 없음 (부드러운 곡선)
```

---

## 🎨 시나리오별 설정 예시

### 시나리오 1: KR이 항상 최선

```python
# MOCK_DATA 수정
"KR": {"carbonIntensity": 100, "fossilFreePercentage": 90},  # 매우 낮음
"JP": {"carbonIntensity": 400, "fossilFreePercentage": 40},
"CN": {"carbonIntensity": 700, "fossilFreePercentage": 20},

# 변동 폭 수정
if zone == "KR":
    carbon_offset = int(wave * 10)  # 작은 변동, 항상 낮게 유지
```

**결과**: KR이 거의 항상 선택됨

---

### 시나리오 2: 세 지역이 경쟁

```python
# MOCK_DATA 수정 - 비슷한 기본값
"KR": {"carbonIntensity": 350, "fossilFreePercentage": 50},
"JP": {"carbonIntensity": 360, "fossilFreePercentage": 48},
"CN": {"carbonIntensity": 370, "fossilFreePercentage": 45},

# 변동 폭 크게 - 서로 역전됨
if zone == "KR":
    carbon_offset = int(wave * 100)  # 큰 변동
elif zone == "JP":
    wave = math.sin((phase + 0.33) * 2 * math.pi)  # 위상차
    carbon_offset = int(wave * 100)
elif zone == "CN":
    wave = math.sin((phase + 0.67) * 2 * math.pi)  # 위상차
    carbon_offset = int(wave * 100)
```

**결과**: 시간에 따라 최선 지역이 계속 바뀜

---

### 시나리오 3: 극적인 변화 (데모용)

```python
# 빠른 주기
cycle_seconds = 60  # 1분마다 변화

# 큰 변동
if zone == "KR":
    carbon_offset = int(wave * 200)  # ±200 (극적 변화)

# 큰 노이즈
noise = random.randint(-50, 50)
```

**결과**: 매우 빠르고 극적인 탄소 강도 변화

---

### 시나리오 4: 안정적 (실제 그리드 유사)

```python
# 긴 주기
cycle_seconds = 3600  # 1시간 주기

# 작은 변동
if zone == "KR":
    carbon_offset = int(wave * 20)  # ±20 (작은 변동)

# 작은 노이즈
noise = random.randint(-5, 5)
```

**결과**: 실제 전력망처럼 천천히 안정적으로 변화

---

## 🔄 변경 사항 적용

### 방법 1: Hub 재시작 (권장)

```bash
docker-compose restart hub
```

### 방법 2: 전체 재빌드

```bash
docker-compose up -d --build hub
```

### 방법 3: 전체 시스템 재시작

```bash
bash stop-caspian.sh
bash start-caspian.sh
```

---

## 📊 현재 Mock 데이터 확인

### Hub API로 확인

```bash
curl http://localhost:8080/hub/stats | python3 -m json.tool
```

**출력 예시**:
```json
{
  "carbon_intensity": {
    "KR": 335,
    "JP": 420,
    "CN": 715
  }
}
```

### Grafana로 확인

1. http://localhost:3000 접속
2. "CASPIAN Carbon-Aware Scheduling" 대시보드
3. 상단 3개 게이지와 시계열 그래프 확인

---

## 🎯 실전 팁

### 1. 테스트용 설정
```python
cycle_seconds = 60        # 1분 주기 (빠른 변화)
carbon_offset = wave * 100  # 큰 변동
```
→ 빠르게 동작 확인 가능

### 2. 데모용 설정
```python
cycle_seconds = 300       # 5분 주기 (현재 기본값)
carbon_offset = wave * 50   # 중간 변동
```
→ 데모 중 변화 확인 가능

### 3. 실전 시뮬레이션
```python
cycle_seconds = 1800      # 30분 주기
carbon_offset = wave * 20   # 작은 변동
```
→ 실제 전력망 패턴 유사

---

## 🔍 디버깅

### Mock 모드 확인

**Hub 로그**:
```bash
docker logs carbon-hub | grep MOCK
```

**출력 예시**:
```
⚠️  MOCK MODE ENABLED - Using simulated carbon intensity data
```

### Mock 데이터 패턴 확인

**코드 234줄**: 디버그 로그 활성화

```python
if random.random() < 0.1:  # 10% 확률
    logger.debug(
        f"Mock {zone}: base={base_intensity}, offset={carbon_offset}, "
        f"noise={noise}, final={final_intensity}, phase={phase:.2f}"
    )
```

**100% 활성화** (모든 업데이트마다 로그):
```python
if True:  # 항상 로그
    logger.info(  # debug → info로 변경
        f"Mock {zone}: base={base_intensity}, offset={carbon_offset}, "
        f"noise={noise}, final={final_intensity}, phase={phase:.2f}"
    )
```

---

## 📝 예제: 한국을 항상 최선으로 만들기

### 1. `app/carbon_client.py` 수정

```python
# 25-32줄
MOCK_DATA = {
    "CN": {"carbonIntensity": 650, "fossilFreePercentage": 20},
    "KR": {"carbonIntensity": 200, "fossilFreePercentage": 80},  # ← 매우 낮게
    "JP": {"carbonIntensity": 450, "fossilFreePercentage": 35},
}

# 213-216줄
elif zone == "KR":
    wave = math.sin(phase * 2 * math.pi)
    carbon_offset = int(wave * 10)  # ← 작은 변동 (±10)
```

### 2. Hub 재시작

```bash
docker-compose restart hub
```

### 3. 확인

```bash
# 통계 확인
curl http://localhost:8080/hub/stats

# Job 제출
curl -X POST http://localhost:8080/hub/appwrappers \
  -H "Content-Type: application/json" \
  -d '{"job_id":"test","cpu":2.0,"mem_gb":4.0,"runtime_minutes":30,"deadline_minutes":120}'

# 스케줄링
curl -X POST http://localhost:8080/hub/schedule

# AppWrapper 확인 - targetCluster가 "carbon-kr"이어야 함
curl http://localhost:8080/hub/appwrappers | grep targetCluster
```

---

## 🌍 실제 API로 전환

### 1. ElectricityMap API 키 발급

https://www.electricitymaps.com/ 에서 무료 계정 생성

### 2. 환경변수 설정

```bash
export ELECTRICITYMAP_API_KEY=your_real_api_key_here
export USE_MOCK_DATA=false
export CARBON_ZONES=KR,JP,CN
```

### 3. docker-compose.yml 수정

```yaml
hub:
  environment:
    - ELECTRICITYMAP_API_KEY=your_real_api_key_here
    - USE_MOCK_DATA=false
    - CARBON_ZONES=KR,JP,CN
```

### 4. 재시작

```bash
docker-compose restart hub
```

### 5. 로그 확인

```bash
docker logs -f carbon-hub
```

**성공 시**:
```
✅ Successfully fetched KR: 352 gCO2/kWh
```

**실패 시** (API 키 문제):
```
⚠️ HTTP error for KR: 403
```

---

## 🔑 정리

### Mock 모드 ON/OFF
- **파일**: `docker-compose.yml`
- **변수**: `USE_MOCK_DATA=true/false`

### 기본값 조절
- **파일**: `app/carbon_client.py`
- **위치**: 25-32줄 `MOCK_DATA`

### 변동 패턴
- **파일**: `app/carbon_client.py`
- **위치**: 197-224줄 (각 지역별)

### 변동 주기
- **파일**: `app/carbon_client.py`
- **위치**: 192줄 `cycle_seconds`

### 적용 방법
```bash
docker-compose restart hub
```

---

**Mock 데이터로 CASPIAN의 동작을 자유롭게 테스트하세요!** 🎯
