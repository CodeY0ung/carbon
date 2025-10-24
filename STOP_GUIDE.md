# CASPIAN 시스템 종료 가이드

## 빠른 시작

### Linux/Mac
```bash
bash stop-all-services.sh
```

### Windows
**방법 1: 배치 파일 사용 (권장)**
```cmd
stop-system.bat
```

**방법 2: Git Bash 직접 사용**
```bash
bash stop-all-services.sh
```

**방법 3: PowerShell**
```powershell
& "C:\Program Files\Git\bin\bash.exe" stop-all-services.sh
```

---

## 종료 프로세스 상세 설명

### 1. Port Forwarding 중지
```bash
# 실행 중인 모든 kubectl port-forward 프로세스 종료
pkill -f "kubectl.*port-forward"
```

**중지되는 서비스:**
- Grafana (port 3000)
- Prometheus (port 9090)
- Hub API (port 8080)

### 2. Kind 클러스터 삭제
```bash
# 모든 Kind 클러스터 목록 확인 및 삭제
kind get clusters
kind delete cluster --name carbon-hub
kind delete cluster --name carbon-kr
kind delete cluster --name carbon-jp
kind delete cluster --name carbon-cn
```

**삭제되는 클러스터:**
- `carbon-hub`: Hub 클러스터 (Prometheus, Grafana, Hub API)
- `carbon-kr`: 한국 Spoke 클러스터
- `carbon-jp`: 일본 Spoke 클러스터
- `carbon-cn`: 중국 Spoke 클러스터

### 3. Docker 리소스 정리
```bash
# carbon-hub 관련 컨테이너 중지 및 제거
docker stop <container-id>
docker rm <container-id>
```

**정리되는 리소스:**
- Hub API 컨테이너
- Kind 노드 컨테이너
- 네트워크 설정

### 4. 임시 파일 삭제
```bash
# Grafana 대시보드 임시 파일 삭제
rm -f dashboard-complete.json
rm -f dashboard-updated.json
rm -f current-dashboard.json
rm -f dashboard-for-configmap.json
```

---

## 수동 종료 (문제 해결)

스크립트가 작동하지 않는 경우 수동으로 종료:

### Step 1: Port Forwarding 확인 및 중지
```bash
# 실행 중인 port-forward 프로세스 확인
ps aux | grep "kubectl.*port-forward"

# PID를 찾아서 수동 종료
kill <PID>
```

### Step 2: Kind 클러스터 확인 및 삭제
```bash
# 클러스터 목록 확인
kind get clusters

# 하나씩 삭제
kind delete cluster --name carbon-hub
kind delete cluster --name carbon-kr
kind delete cluster --name carbon-jp
kind delete cluster --name carbon-cn
```

### Step 3: Docker 컨테이너 확인
```bash
# 실행 중인 컨테이너 확인
docker ps | grep kind

# Kind 관련 컨테이너 모두 중지
docker stop $(docker ps -a | grep "kind" | awk '{print $1}')
docker rm $(docker ps -a | grep "kind" | awk '{print $1}')
```

### Step 4: 네트워크 확인
```bash
# Kind 네트워크 확인
docker network ls | grep kind

# 필요시 네트워크 삭제
docker network rm <network-name>
```

---

## 부분 종료 (선택적)

### Hub만 종료 (Spoke는 유지)
```bash
kind delete cluster --name carbon-hub
```

### 특정 Spoke만 종료
```bash
kind delete cluster --name carbon-kr
# 또는
kind delete cluster --name carbon-jp
# 또는
kind delete cluster --name carbon-cn
```

### Port Forwarding만 중지 (클러스터는 유지)
```bash
pkill -f "kubectl.*port-forward"
```

---

## 완전 초기화 (모든 데이터 삭제)

시스템을 완전히 초기화하려면:

```bash
# 1. 모든 서비스 중지
bash stop-all-services.sh

# 2. Docker 이미지 삭제
docker rmi carbon-hub:latest

# 3. Docker 볼륨 정리 (선택)
docker volume prune -f

# 4. Docker 이미지 정리 (선택)
docker image prune -a -f

# 5. 임시 파일 모두 삭제
rm -f *.json
rm -f *.log
```

**⚠️ 경고**: 이 작업은 모든 데이터를 삭제하므로 신중하게 실행하세요!

---

## 종료 후 확인

시스템이 완전히 종료되었는지 확인:

```bash
# 1. Kind 클러스터 확인
kind get clusters
# 출력: No kind clusters found.

# 2. Docker 컨테이너 확인
docker ps | grep kind
# 출력: (없음)

# 3. Port 사용 확인
netstat -tuln | grep -E "3000|8080|9090"
# 출력: (없음)

# 4. kubectl 프로세스 확인
ps aux | grep kubectl
# 출력: (검색 프로세스만 표시됨)
```

---

## 재시작 방법

시스템을 다시 시작하려면:

### Linux/Mac
```bash
bash start-complete-system.sh
```

### Windows
```cmd
start-system.bat
```

---

## 문제 해결

### "Error: no kind clusters found"
- **원인**: 이미 클러스터가 삭제됨
- **해결**: 무시하고 계속 진행

### "Error: context deadline exceeded"
- **원인**: Docker가 응답하지 않음
- **해결**: Docker Desktop 재시작 후 다시 시도

### Port가 여전히 사용 중
- **확인**: `netstat -tuln | grep <port>`
- **해결**:
  ```bash
  lsof -i :<port>  # Mac/Linux
  # 또는
  netstat -ano | findstr :<port>  # Windows

  # PID를 찾아서 종료
  kill <PID>  # Mac/Linux
  taskkill /PID <PID> /F  # Windows
  ```

### Docker 디스크 공간 부족
```bash
# Docker 정리
docker system prune -a -f --volumes

# 디스크 사용량 확인
docker system df
```

---

## 빠른 참조

| 작업 | 명령어 |
|------|--------|
| 전체 종료 | `bash stop-all-services.sh` |
| Hub만 종료 | `kind delete cluster --name carbon-hub` |
| Port forwarding 중지 | `pkill -f "kubectl.*port-forward"` |
| Docker 정리 | `docker system prune -f` |
| 재시작 | `bash start-complete-system.sh` |

---

## 추가 정보

- **로그 위치**: 각 Pod의 로그는 `kubectl logs` 명령으로 확인
- **데이터 지속성**: Kind 클러스터는 삭제 시 모든 데이터가 사라집니다
- **백업**: 중요한 설정은 Git에 커밋하여 보관하세요

---

**작성일**: 2025-10-23
**버전**: 1.0
**프로젝트**: CASPIAN - Carbon-Aware Scheduling Platform
