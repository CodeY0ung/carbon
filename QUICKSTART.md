# 🚀 CASPIAN 빠른 시작

## 한 줄로 시작하기

```bash
bash start-caspian.sh
```

## 접속 주소

시작 완료 후 (약 2-3분):

| 서비스 | URL | 계정 |
|--------|-----|------|
| Hub API | http://localhost:8080 | - |
| Prometheus | http://localhost:9090 | - |
| Grafana | http://localhost:3000 | admin/admin |

## 테스트하기

### 1. AppWrapper 제출
```bash
curl -X POST http://localhost:8080/hub/appwrappers \
  -H "Content-Type: application/json" \
  -d '{"job_id":"test-job","cpu":2.0,"mem_gb":4.0,"runtime_minutes":30,"deadline_minutes":120}'
```

### 2. 스케줄링 + 배포
```bash
curl -X POST http://localhost:8080/hub/schedule
curl -X POST http://localhost:8080/hub/dispatch
```

### 3. 확인
```bash
kubectl --context kind-carbon-kr get jobs,pods
```

## 종료하기

```bash
bash stop-caspian.sh
```

---

**그게 전부입니다!** 🎉

더 자세한 내용은 [시동_가이드.md](시동_가이드.md)를 참조하세요.
