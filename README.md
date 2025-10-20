# CASPIAN - Carbon-Aware Scheduling Platform

**C**arbon-**A**ware **S**cheduling using Integer Linear **P**rogramming **A**nd **N**etwork optimization

탄소 배출량을 최소화하는 Kubernetes 워크로드 스케줄러

---

## 🚀 빠른 시작 (60초 안에!)

### Linux/Mac
```bash
bash start-caspian.sh
```

### Windows
```bash
# Git Bash 사용 (권장)
bash start-caspian.sh

# 또는 CMD/PowerShell
start-caspian.bat
```

**끝!** 🎉 시스템이 자동으로 설정됩니다.

---

## 📋 시스템 개요

### Hub-Spoke 아키텍처

```
┌─────────────────────────────────────────┐
│           Hub Cluster (8080)            │
│  ┌──────────┐  ┌───────────┐           │
│  │Scheduler │→ │ Optimizer │           │
│  │  (5분)   │  │ (CASPIAN) │           │
│  └──────────┘  └───────────┘           │
│        ↓             ↓                  │
│  ┌────────────┐ ┌────────────┐         │
│  │Dispatcher  │ │ HubStore   │         │
│  │  (30초)    │ │            │         │
│  └────────────┘ └────────────┘         │
└─────────────────────────────────────────┘
            ↓  ↓  ↓
   ┌────────┼──┼──┼────────┐
   ↓        ↓  ↓  ↓        ↓
┌──────┐ ┌──────┐ ┌──────┐
│  KR  │ │  JP  │ │  CN  │
│ (3n) │ │ (3n) │ │ (3n) │
└──────┘ └──────┘ └──────┘
```

### 주요 기능

- ✅ **탄소 인지형 스케줄링**: MILP 기반 최적화
- ✅ **실시간 탄소 강도 모니터링**: 10초마다 업데이트
- ✅ **자동 워크로드 배포**: Kubernetes Job 자동 생성
- ✅ **멀티 클러스터 관리**: 3개 지역 클러스터 (KR, JP, CN)
- ✅ **실시간 모니터링**: Prometheus + Grafana

---

## 🌐 접속 정보

시작 후 다음 URL로 접속:

| 서비스 | URL | 계정 |
|--------|-----|------|
| **Hub API** | http://localhost:8080 | - |
| **Prometheus** | http://localhost:9090 | - |
| **Grafana** | http://localhost:3000 | admin/admin |

### Grafana 대시보드

1. http://localhost:3000 접속
2. admin/admin 로그인
3. "CASPIAN Carbon-Aware Scheduling" 대시보드 열기

---

## 💡 사용 예시

### 1. AppWrapper 제출
```bash
curl -X POST http://localhost:8080/hub/appwrappers \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "my-job",
    "cpu": 2.0,
    "mem_gb": 4.0,
    "runtime_minutes": 30,
    "deadline_minutes": 120
  }'
```

### 2. 스케줄링 트리거 (CASPIAN 최적화)
```bash
curl -X POST http://localhost:8080/hub/schedule
```

### 3. 디스패치 트리거 (Kubernetes 배포)
```bash
curl -X POST http://localhost:8080/hub/dispatch
```

### 4. 배포 확인
```bash
kubectl --context kind-carbon-kr get jobs,pods
kubectl --context kind-carbon-jp get jobs,pods
kubectl --context kind-carbon-cn get jobs,pods
```

### 5. 시스템 상태 확인
```bash
curl http://localhost:8080/hub/stats | python3 -m json.tool
```

---

## 📁 프로젝트 구조

```
carbon/
├── hub/                    # Hub Cluster 구현 (핵심)
│   ├── app.py             # Hub API 서버 (8080)
│   ├── scheduler.py       # CASPIAN 스케줄러 (5분)
│   ├── dispatcher.py      # Kubernetes 디스패처 (30초)
│   ├── store.py           # 데이터 저장소
│   └── models.py          # AppWrapper, ClusterInfo
│
├── app/                    # 공유 컴포넌트
│   ├── optimizer.py       # MILP 최적화 알고리즘
│   ├── carbon_client.py   # 탄소 데이터 수집 (10초)
│   ├── metrics.py         # Prometheus 메트릭
│   └── schemas.py         # Pydantic 스키마
│
├── dashboards/            # Grafana 대시보드
│   └── carbon-hub-dashboard.json  # CASPIAN 대시보드
│
├── grafana/               # Grafana 프로비저닝
│   └── provisioning/
│
├── start-caspian.sh       # 🚀 완전 자동 시작 (Linux/Mac)
├── start-caspian.bat      # 🚀 완전 자동 시작 (Windows)
├── stop-caspian.sh        # 🛑 시스템 종료
│
├── docker-compose.yml     # Docker Compose 설정
├── Dockerfile             # Hub 컨테이너 이미지
└── prometheus.yml         # Prometheus 설정
```

**상세 구조**: [프로젝트_구조.md](프로젝트_구조.md) 참조

---

## 🔧 요구사항

### 필수 소프트웨어
- Docker (v20.10+) + Docker Compose
- Kind (v0.20+)
- kubectl (v1.28+)
- curl

### 확인
```bash
docker --version
kind --version
kubectl version --client
```

---

## 🎯 CASPIAN 작동 원리

### 3단계 스케줄링 프로세스

```
1️⃣ Collect (수집)
   ↓ ClusterInfo (carbon_intensity, resources)

2️⃣ Optimize (최적화)
   ↓ MILP Solver (탄소 배출 최소화)

3️⃣ Update (업데이트)
   ↓ targetCluster 설정, gate OPEN

4️⃣ Dispatch (배포)
   ↓ Kubernetes Job 생성
```

### 목적 함수
```
minimize: Σ (carbon_intensity × energy_consumption)
```

### 제약 조건
- 각 작업은 정확히 한 번만 스케줄링
- 리소스 용량 제한 (CPU, 메모리)
- 시간 윈도우 제약 (deadline)
- Affinity 제약

---

## 📊 메트릭

### Hub API `/metrics` 엔드포인트

```bash
curl http://localhost:8080/metrics
```

주요 메트릭:
- `grid_carbon_intensity_gco2_per_kwh{zone}` - 지역별 탄소 강도
- `appwrappers_total` - 총 AppWrapper 수
- `appwrappers_running` - 실행 중
- `clusters_total` - 총 클러스터 수
- `clusters_ready` - Ready 클러스터 수

---

## 🛠️ 유용한 명령어

### 로그 확인
```bash
docker logs -f carbon-hub        # Hub 로그
docker logs -f carbon-prometheus # Prometheus 로그
docker logs -f carbon-grafana    # Grafana 로그
```

### 시스템 종료
```bash
bash stop-caspian.sh             # 전체 종료
docker-compose down              # Docker만 종료
```

### 완전 초기화
```bash
docker-compose down
kind delete cluster --name carbon-kr
kind delete cluster --name carbon-jp
kind delete cluster --name carbon-cn
```

---

## 🔄 자동 실행 주기

| 작업 | 주기 | 설명 |
|------|------|------|
| Carbon Client | 10초 | 탄소 강도 업데이트 |
| Hub Scheduler | 5분 | CASPIAN 스케줄링 |
| Hub Dispatcher | 30초 | Kubernetes 배포 |
| Prometheus | 10초 | 메트릭 수집 |
| Grafana | 5초 | 대시보드 갱신 |

---

## 📚 문서

### 시작 가이드
- **[QUICKSTART.md](QUICKSTART.md)** - 초간단 가이드 (1분)
- **[시동_가이드.md](시동_가이드.md)** - 상세 시작 가이드
- **[README.md](README.md)** - 이 문서

### 기술 문서
- **[프로젝트_구조.md](프로젝트_구조.md)** - 📁 전체 파일 구조 및 역할
- **[MOCK_데이터_설정_가이드.md](MOCK_데이터_설정_가이드.md)** - 🎯 Mock 데이터 조절 방법
- **[시스템_완료_보고서.md](시스템_완료_보고서.md)** - 시스템 현황
- **[HUB_SPOKE_구현_가이드.md](HUB_SPOKE_구현_가이드.md)** - 구현 상세
- **[CASPIAN_알고리즘_설명.md](CASPIAN_알고리즘_설명.md)** - 알고리즘 설명

---

## 🎉 완료 체크리스트

시작 후 확인:

- [ ] Hub API 응답: http://localhost:8080/hub/stats
- [ ] Prometheus 실행: http://localhost:9090
- [ ] Grafana 대시보드: http://localhost:3000
- [ ] 클러스터 3개 Ready: `kubectl config get-contexts | grep carbon`
- [ ] 테스트 Job 제출 및 배포 성공

---

## 🚨 트러블슈팅

### Hub API가 시작되지 않음
```bash
docker logs carbon-hub
docker-compose restart hub
```

### Job이 배포되지 않음
```bash
# kubeconfig 확인
cat kubeconfig-docker | grep "server:"

# 클러스터 상태 확인
kubectl --context kind-carbon-kr get nodes
```

### Grafana 대시보드가 없음
```bash
docker-compose restart grafana
ls -la dashboards/carbon-hub-dashboard.json
```

---

## 🌟 주요 특징

1. **완전 자동화**: 한 줄 명령어로 전체 시스템 시작
2. **실시간 모니터링**: Grafana 대시보드로 탄소 강도 시각화
3. **MILP 최적화**: PuLP + CBC 솔버 기반
4. **멀티 클러스터**: 3개 지역 클러스터 관리
5. **Kubernetes 네이티브**: 실제 K8s Job 배포

---

## 📞 빠른 참조

```bash
# 시작
bash start-caspian.sh

# 상태 확인
curl http://localhost:8080/hub/stats

# Job 제출
curl -X POST http://localhost:8080/hub/appwrappers \
  -H "Content-Type: application/json" \
  -d '{"job_id":"test","cpu":2.0,"mem_gb":4.0,"runtime_minutes":30,"deadline_minutes":120}'

# 스케줄링
curl -X POST http://localhost:8080/hub/schedule

# 배포
curl -X POST http://localhost:8080/hub/dispatch

# 종료
bash stop-caspian.sh
```

---

**시작 명령어**:
```bash
bash start-caspian.sh
```

**그게 전부입니다! 🚀**

---

## 📄 License

This project is a proof-of-concept for carbon-aware Kubernetes scheduling.

## 🤝 Contributing

This is a research prototype. Feel free to explore and experiment!

---

**Made with ❤️ for a greener cloud**
