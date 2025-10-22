# 현실적인 Mock 탄소 데이터

## 개요

Mock 데이터가 실제 전력망의 불규칙한 패턴을 시뮬레이션하도록 업데이트되었습니다.

## 이전 방식 vs 새로운 방식

### 이전 (단순 Sine Wave)
```
- 고정된 2분 주기
- 예측 가능한 패턴
- KR과 JP가 정확히 180° 위상차
- 매번 같은 시간에 역전
```

### 새로운 방식 (불규칙 현실적 패턴)
```
- 3개의 주파수 혼합 (10분, 3분, 1분)
- 무작위 이벤트 (재생에너지 급증, 수요 급증)
- 예측 불가능한 변화
- 실제 전력망 행동 모방
```

## 기술적 세부사항

### 1. Multi-Frequency Mixing

서로 다른 주기의 sine wave를 혼합하여 복잡한 패턴 생성:

```python
# Long cycle: ~10 minutes (일일 수요 패턴)
long_wave = sin(time / 600 * 2π)

# Medium cycle: ~3 minutes (날씨/구름 변화)
med_wave = sin(time / 180 * 2π)

# Short cycle: ~1 minute (빠른 수요 변동)
short_wave = sin(time / 60 * 2π)
```

### 2. Zone-Specific Behaviors

각 지역마다 고유한 특성:

#### Korea (KR)
```
Base: 350 gCO2/kWh
Pattern: (long * 80) + (med * 50) + (short * 30)
Special: 15% 확률로 재생에너지 급증 (-50 ~ -120)
```

**특징**: 높은 산업 변동성, 태양광/풍력 통합

#### Japan (JP)
```
Base: 380 gCO2/kWh
Pattern: (long * 70) + (med * 60) + (short * 20)
Special: 10% 확률로 수요 급증 (+40 ~ +100)
```

**특징**: 비교적 안정적이지만 가끔 피크

#### China (CN)
```
Base: 650 gCO2/kWh
Pattern: (long * 40) + (med * 30) + (short * 20)
Special: 없음 (일관되게 높음)
```

**특징**: 석탄 중심, 변동성 낮음, 항상 최악

#### Canada (CA)
```
Base: 120 gCO2/kWh
Pattern: (long * 30) + (med * 20) + (short * 15)
Special: 20% 확률로 수력 조정 (-10 ~ -30)
```

**특징**: 수력 발전, 매우 안정적, 낮은 탄소

#### Brazil (BR)
```
Base: 180 gCO2/kWh
Pattern: (long * 60) + (med * 40) + (short * 25)
Special: 12% 확률로 강우/가뭄 효과 (-40 ~ +60)
```

**특징**: 수력 의존, 날씨에 민감

### 3. Random Noise & Events

#### 연속 노이즈
- 모든 읽기마다 ±25 gCO2/kWh
- 측정 불확실성, 작은 그리드 변동 시뮬레이션

#### 드문 그리드 이벤트
- 5% 확률
- ±80 gCO2/kWh 변화
- 예: 주요 발전소 가동/중단, 대규모 재생에너지 출력 변화

### 4. Bounds

모든 값은 현실적인 범위 내로 제한:
- 최소: 50 gCO2/kWh
- 최대: 800 gCO2/kWh

## 마이그레이션 발생 시나리오

### 시나리오 1: 재생에너지 급증
```
Time T0: KR=400, JP=350, CN=650
         → Job on JP (최적)

Time T1 (30초 후):
  KR gets renewable surge: 400 - 100 = 300
  JP stable: 350
  CN stable: 650
  → MIGRATION: JP → KR
```

### 시나리오 2: 수요 급증
```
Time T0: KR=300, JP=320, CN=650
         → Job on KR (최적)

Time T1 (1분 후):
  KR stable: 310
  JP gets demand spike: 320 + 80 = 400
  CN stable: 640
  → No migration (KR still best)
```

### 시나리오 3: 복합 변화
```
Time T0: KR=350, JP=340, CN=620
         → Job on JP (최적)

Time T1 (2분 후):
  KR renewable surge: 350 - 90 = 260
  JP demand spike: 340 + 60 = 400
  CN drops slightly: 610
  → MIGRATION: JP → KR (대폭 개선!)
```

## 예상 동작

### 탄소 집약도 변화 패턴

불규칙하고 예측 불가능:

```
Time    KR    JP    CN    Best
0:00   380   420   650    KR
0:30   340   390   630    KR
1:00   250*  410   660    KR  ← 재생에너지 급증
1:30   320   380   640    KR
2:00   370   330   620    JP  ← 역전!
2:30   410   480*  630    KR  ← JP 급증
3:00   350   380   640    KR
3:30   290*  360   610    KR  ← 재생에너지 급증

* = 특별 이벤트 발생
```

### 마이그레이션 트리거

마이그레이션은 다음 경우 발생:
1. **재생에너지 급증**: 한 지역이 갑자기 -100 gCO2/kWh 하락
2. **수요 급증**: 현재 최적 지역이 갑자기 +80 gCO2/kWh 상승
3. **복합 변화**: 여러 지역이 동시에 다른 방향으로 변화
4. **점진적 교차**: 느린 주기들이 겹쳐서 순위 역전

## 테스트 방법

### 1. 시스템 시작
```bash
bash start-complete-system.sh
```

### 2. 워크로드 제출
```bash
curl -X POST http://localhost:8080/hub/appwrappers \
  -H 'Content-Type: application/json' \
  -d '{
    "job_id": "realistic-test",
    "cpu": 4.0,
    "mem_gb": 8.0,
    "data_gb": 100.0,
    "runtime_minutes": 120,
    "deadline_minutes": 480
  }'
```

### 3. 실시간 모니터링

**Grafana 대시보드:**
```
http://localhost:3000/d/caspian-hub
```

**탄소 집약도 변화 관찰:**
```bash
watch -n 2 'curl -s http://localhost:8080/hub/stats | python -m json.tool'
```

### 4. 마이그레이션 확인

**로그:**
```bash
kubectl --context kind-carbon-hub logs -n caspian-hub -l app=hub-api --tail=100 | grep MIGRATION
```

**메트릭:**
```bash
curl -s http://localhost:8080/metrics | grep migration_
```

## 장점

### 현실성
- 실제 전력망 행동 모방
- 예측 불가능한 변화
- 다양한 이벤트 유형

### 테스트 품질
- 더 많은 마이그레이션 시나리오
- 엣지 케이스 노출
- 실제 운영 환경과 유사

### 시각화
- Grafana에서 흥미로운 패턴
- 명확한 이벤트 표시
- 실제 같은 데이터 흐름

## 로깅

특별 이벤트 발생 시 로그:

```
INFO - Mock KR: Significant grid event! Δ-75 gCO2/kWh
INFO - Mock JP: Significant grid event! Δ+82 gCO2/kWh
```

디버그 모드 (5% 확률):
```
DEBUG - Mock KR: base=350, pattern=-45, noise=12, event=-75, final=242
```

---

**작성일**: 2025-10-22  
**버전**: 2.0.0 - Realistic Irregular Patterns
