# Windows에서 CASPIAN 실행하기

## 문제: CMD/PowerShell에서 bash 스크립트 실행 안됨

### 원인
Windows CMD나 PowerShell에서는 `kind`, `kubectl` 등의 명령어 경로가 설정되지 않아 스크립트가 실패합니다.

## ✅ 해결 방법 (3가지)

### 방법 1: Windows 배치 파일 사용 (가장 간단!)

```cmd
start-system.bat
```

또는 더블클릭으로 실행:
```
C:\Users\USER\Desktop\carbon\start-system.bat
```

**장점:**
- 한 번의 클릭/명령으로 실행
- Git Bash를 자동으로 찾아서 실행
- 에러 메시지 표시

---

### 방법 2: Git Bash 직접 사용 (권장!)

1. **Git Bash 실행**
   - 시작 메뉴 → "Git Bash" 검색
   - 또는 폴더에서 우클릭 → "Git Bash Here"

2. **프로젝트 폴더로 이동**
   ```bash
   cd /c/Users/USER/Desktop/carbon
   ```

3. **시스템 시작**
   ```bash
   bash start-complete-system.sh
   ```

**장점:**
- PATH 문제 없음
- 컬러 출력 지원
- Linux 명령어 사용 가능

---

### 방법 3: PowerShell에서 Git Bash 호출

PowerShell을 열고:

```powershell
& "C:\Program Files\Git\bin\bash.exe" --login -i -c "cd /c/Users/USER/Desktop/carbon && bash start-complete-system.sh"
```

---

## 🔧 시스템 요구사항

시스템 시작 전 다음이 설치되어 있어야 합니다:

### 필수 도구
- ✅ **Docker Desktop** (실행 중이어야 함)
- ✅ **Kind** (Kubernetes in Docker)
- ✅ **kubectl** (Kubernetes CLI)
- ✅ **Git Bash** (Windows용 Bash)

### 설치 확인
Git Bash에서:
```bash
docker --version
kind version
kubectl version --client
```

모두 버전이 표시되면 정상!

---

## 📋 전체 실행 과정

### 1단계: Docker Desktop 실행
- Docker Desktop이 실행 중인지 확인
- 시스템 트레이에 Docker 아이콘이 초록색이어야 함

### 2단계: Git Bash 열기
```
시작 → Git Bash
```

### 3단계: 프로젝트 폴더 이동
```bash
cd /c/Users/USER/Desktop/carbon
```

### 4단계: 시스템 시작
```bash
bash start-complete-system.sh
```

### 5단계: 시작 완료 대기
약 3-5분 소요:
- [1/10] 환경 정리
- [2/10] Hub 클러스터 생성
- [3/10] Spoke 클러스터 생성 (KR, JP, CN)
- [4/10] Docker 이미지 빌드
- [5/10] 이미지 로드
- [6/10] Kubeconfig 생성
- [7/10] 애플리케이션 배포
- [8/10] Pod 준비 대기
- [9/10] 클러스터 등록
- [10/10] 시스템 검증

### 6단계: 접속
```
Hub API:     http://localhost:8080
Prometheus:  http://localhost:9090
Grafana:     http://localhost:3000 (admin/admin)
Dashboard:   http://localhost:3000/d/caspian-hub
```

---

## ❌ 자주 발생하는 오류와 해결

### 오류 1: "kind: command not found"
**원인:** PATH에 kind가 없음

**해결:**
- Git Bash 사용 (방법 2)
- 또는 start-system.bat 사용 (방법 1)

---

### 오류 2: "Cannot connect to the Docker daemon"
**원인:** Docker Desktop이 실행되지 않음

**해결:**
1. Docker Desktop 실행
2. 트레이 아이콘이 초록색이 될 때까지 대기
3. 스크립트 재실행

---

### 오류 3: "Error response from daemon: conflict"
**원인:** 이미 클러스터가 실행 중

**해결:**
```bash
# 기존 클러스터 삭제
kind delete cluster --name carbon-hub
kind delete cluster --name carbon-kr
kind delete cluster --name carbon-jp
kind delete cluster --name carbon-cn

# 재시작
bash start-complete-system.sh
```

---

### 오류 4: "port is already allocated"
**원인:** 포트(8080, 9090, 3000)가 이미 사용 중

**해결:**
```bash
# 어떤 프로세스가 사용 중인지 확인
netstat -ano | findstr :8080
netstat -ano | findstr :9090
netstat -ano | findstr :3000

# 해당 프로세스 종료 또는 시스템 재시작
```

---

## 🛑 시스템 종료

Git Bash에서:
```bash
cd /c/Users/USER/Desktop/carbon
bash stop-caspian.sh
```

또는:
```bash
kind delete cluster --name carbon-hub
kind delete cluster --name carbon-kr
kind delete cluster --name carbon-jp
kind delete cluster --name carbon-cn
```

---

## 💡 팁

### 빠른 재시작
```bash
# 종료
bash stop-caspian.sh

# 시작 (같은 터미널에서)
bash start-complete-system.sh
```

### 로그 확인
```bash
# Hub API 로그
kubectl --context kind-carbon-hub logs -n caspian-hub -l app=hub-api --tail=50

# 마이그레이션 로그
kubectl --context kind-carbon-hub logs -n caspian-hub -l app=hub-api | grep MIGRATION
```

### 상태 확인
```bash
# 클러스터 상태
kubectl --context kind-carbon-hub get pods -n caspian-hub

# 시스템 상태
curl http://localhost:8080/hub/stats | python -m json.tool
```

---

## 📞 문제 해결이 안되면?

1. **Docker Desktop 재시작**
2. **컴퓨터 재부팅**
3. **모든 클러스터 삭제 후 재시작**
   ```bash
   kind delete clusters --all
   bash start-complete-system.sh
   ```

---

**작성일:** 2025-10-22  
**버전:** 1.0
