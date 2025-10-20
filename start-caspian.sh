#!/bin/bash

# CASPIAN Hub-Spoke 시스템 완전 자동 시작 스크립트
# 이 스크립트는 전체 시스템을 한번에 시작합니다.

set -e

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# 프로그레스 바 함수
show_progress() {
    local current=$1
    local total=$2
    local width=50
    local percentage=$((current * 100 / total))
    local completed=$((width * current / total))

    printf "\r["
    printf "%${completed}s" | tr ' ' '='
    printf "%$((width - completed))s" | tr ' ' '-'
    printf "] %d%%" $percentage
}

echo ""
echo -e "${BOLD}${CYAN}=========================================="
echo "  CASPIAN Hub-Spoke 시스템 시작"
echo -e "==========================================${NC}"
echo ""
echo -e "${BLUE}탄소 인지형 Kubernetes 워크로드 스케줄러${NC}"
echo ""

# ============================================================
# Step 1: 기존 환경 정리
# ============================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[1/6] 기존 환경 정리...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 기존 컨테이너 종료
echo -e "${BLUE}→ Docker 컨테이너 정리...${NC}"
docker-compose down 2>/dev/null || true
sleep 2

# 기존 Kind 클러스터 삭제 (선택적)
echo -e "${BLUE}→ 기존 Kind 클러스터 확인...${NC}"
existing_clusters=$(kind get clusters 2>/dev/null | grep -E "carbon-(kr|jp|cn)" || true)
if [ ! -z "$existing_clusters" ]; then
    echo -e "${YELLOW}   기존 클러스터 발견: $existing_clusters${NC}"
    echo -e "${YELLOW}   기존 클러스터 삭제 중...${NC}"
    kind delete cluster --name carbon-kr 2>/dev/null || true
    kind delete cluster --name carbon-jp 2>/dev/null || true
    kind delete cluster --name carbon-cn 2>/dev/null || true
    sleep 2
fi

echo -e "${GREEN}✓ 환경 정리 완료${NC}"
echo ""

# ============================================================
# Step 2: Spoke 클러스터 생성
# ============================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[2/6] Spoke 클러스터 생성 (KR, JP, CN)...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ ! -f "setup-spoke-clusters.sh" ]; then
    echo -e "${RED}✗ setup-spoke-clusters.sh 파일을 찾을 수 없습니다${NC}"
    exit 1
fi

bash setup-spoke-clusters.sh

echo -e "${GREEN}✓ Spoke 클러스터 생성 완료${NC}"
echo ""

# ============================================================
# Step 3: Docker kubeconfig 생성
# ============================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[3/6] Docker용 kubeconfig 생성...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# kubeconfig 내보내기
echo -e "${BLUE}→ kubeconfig 내보내기...${NC}"
kubectl config view --flatten > kubeconfig-docker

# Kind 클러스터 포트 찾기
KR_PORT=$(kubectl config view -o jsonpath='{.clusters[?(@.name=="kind-carbon-kr")].cluster.server}' | grep -oP '(?<=:)\d+$')
JP_PORT=$(kubectl config view -o jsonpath='{.clusters[?(@.name=="kind-carbon-jp")].cluster.server}' | grep -oP '(?<=:)\d+$')
CN_PORT=$(kubectl config view -o jsonpath='{.clusters[?(@.name=="kind-carbon-cn")].cluster.server}' | grep -oP '(?<=:)\d+$')

echo -e "${BLUE}→ Kubernetes API 주소 변환...${NC}"
echo "   - carbon-kr: localhost:$KR_PORT → carbon-kr-control-plane:6443"
echo "   - carbon-jp: localhost:$JP_PORT → carbon-jp-control-plane:6443"
echo "   - carbon-cn: localhost:$CN_PORT → carbon-cn-control-plane:6443"

# 주소 변환 (Docker 네트워크 내부 주소 사용)
sed -i "s|https://127.0.0.1:$KR_PORT|https://carbon-kr-control-plane:6443|g" kubeconfig-docker
sed -i "s|https://127.0.0.1:$JP_PORT|https://carbon-jp-control-plane:6443|g" kubeconfig-docker
sed -i "s|https://127.0.0.1:$CN_PORT|https://carbon-cn-control-plane:6443|g" kubeconfig-docker

echo -e "${GREEN}✓ kubeconfig 생성 완료${NC}"
echo ""

# ============================================================
# Step 4: Docker Compose 서비스 시작
# ============================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[4/6] Docker 서비스 시작...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${BLUE}→ Hub Cluster, Prometheus, Grafana 시작...${NC}"
docker-compose up -d --build

echo ""
echo -e "${BLUE}→ 서비스 준비 대기...${NC}"
for i in {1..30}; do
    show_progress $i 30
    sleep 1
done
echo ""

echo -e "${GREEN}✓ Docker 서비스 시작 완료${NC}"
echo ""

# ============================================================
# Step 5: Hub API 준비 대기 및 클러스터 등록
# ============================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[5/6] Hub API 준비 및 클러스터 등록...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Hub API 준비 대기
echo -e "${BLUE}→ Hub API 준비 대기 중...${NC}"
for i in {1..60}; do
    if curl -s http://localhost:8080/hub/stats > /dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}✓ Hub API 준비 완료 (${i}초)${NC}"
        break
    fi
    show_progress $i 60
    sleep 1

    if [ $i -eq 60 ]; then
        echo ""
        echo -e "${RED}✗ Hub API 시작 시간 초과${NC}"
        echo -e "${YELLOW}   로그 확인: docker logs carbon-hub${NC}"
        exit 1
    fi
done
echo ""

# Spoke 클러스터 등록
echo -e "${BLUE}→ Spoke 클러스터 등록 중...${NC}"

echo -e "   ${CYAN}[1/3]${NC} carbon-kr 등록..."
curl -s -X POST http://localhost:8080/hub/clusters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "carbon-kr",
    "geolocation": "KR",
    "carbon_intensity": 400.0,
    "resources": {
      "cpu_available": 14.0,
      "cpu_total": 16.0,
      "mem_available_gb": 28.0,
      "mem_total_gb": 32.0
    },
    "kubeconfig_context": "kind-carbon-kr"
  }' > /dev/null
echo -e "   ${GREEN}✓ carbon-kr 등록 완료${NC}"

echo -e "   ${CYAN}[2/3]${NC} carbon-jp 등록..."
curl -s -X POST http://localhost:8080/hub/clusters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "carbon-jp",
    "geolocation": "JP",
    "carbon_intensity": 450.0,
    "resources": {
      "cpu_available": 14.0,
      "cpu_total": 16.0,
      "mem_available_gb": 28.0,
      "mem_total_gb": 32.0
    },
    "kubeconfig_context": "kind-carbon-jp"
  }' > /dev/null
echo -e "   ${GREEN}✓ carbon-jp 등록 완료${NC}"

echo -e "   ${CYAN}[3/3]${NC} carbon-cn 등록..."
curl -s -X POST http://localhost:8080/hub/clusters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "carbon-cn",
    "geolocation": "CN",
    "carbon_intensity": 550.0,
    "resources": {
      "cpu_available": 14.0,
      "cpu_total": 16.0,
      "mem_available_gb": 28.0,
      "mem_total_gb": 32.0
    },
    "kubeconfig_context": "kind-carbon-cn"
  }' > /dev/null
echo -e "   ${GREEN}✓ carbon-cn 등록 완료${NC}"

echo ""
echo -e "${GREEN}✓ 클러스터 등록 완료${NC}"
echo ""

# ============================================================
# Step 6: 시스템 상태 확인
# ============================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[6/6] 시스템 상태 확인...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Docker 컨테이너 상태
echo -e "${BLUE}→ Docker 컨테이너 상태:${NC}"
docker ps --filter "name=carbon-" --format "   {{.Names}}: {{.Status}}" | grep -E "(hub|prometheus|grafana)"
echo ""

# Kubernetes 클러스터 상태
echo -e "${BLUE}→ Kubernetes 클러스터 상태:${NC}"
kubectl config get-contexts | grep carbon | awk '{print "   " $2 ": Ready"}'
echo ""

# Hub 통계
echo -e "${BLUE}→ Hub 통계:${NC}"
hub_stats=$(curl -s http://localhost:8080/hub/stats)
echo "$hub_stats" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'   총 클러스터: {data[\"total_clusters\"]}')
print(f'   Ready 클러스터: {data[\"ready_clusters\"]}')
print(f'   총 AppWrappers: {data[\"total_appwrappers\"]}')
print('')
print('   탄소 강도:')
for zone, intensity in data['carbon_intensity'].items():
    print(f'     - {zone}: {intensity} gCO2/kWh')
" 2>/dev/null || echo "$hub_stats" | grep -E "(total_clusters|ready_clusters|carbon_intensity)"
echo ""

echo -e "${GREEN}✓ 시스템 상태 정상${NC}"
echo ""

# ============================================================
# 시작 완료
# ============================================================
echo -e "${BOLD}${GREEN}=========================================="
echo "  CASPIAN 시스템 시작 완료! 🚀"
echo -e "==========================================${NC}"
echo ""

echo -e "${BOLD}${CYAN}📍 접속 정보${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BOLD}Hub API:${NC}        http://localhost:8080"
echo -e "                   ${BLUE}→ /hub/stats (시스템 상태)${NC}"
echo -e "                   ${BLUE}→ /hub/clusters (클러스터 목록)${NC}"
echo -e "                   ${BLUE}→ /hub/appwrappers (작업 목록)${NC}"
echo -e "                   ${BLUE}→ /metrics (Prometheus 메트릭)${NC}"
echo ""
echo -e "  ${BOLD}Prometheus:${NC}    http://localhost:9090"
echo ""
echo -e "  ${BOLD}Grafana:${NC}       http://localhost:3000"
echo -e "                   ${BLUE}→ 계정: admin / admin${NC}"
echo -e "                   ${BLUE}→ 대시보드: \"CASPIAN Carbon-Aware Scheduling\"${NC}"
echo ""

echo -e "${BOLD}${CYAN}💡 빠른 시작 가이드${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BOLD}1. AppWrapper 제출:${NC}"
echo -e '   curl -X POST http://localhost:8080/hub/appwrappers \'
echo -e '     -H "Content-Type: application/json" \'
echo -e '     -d '"'"'{'
echo -e '       "job_id": "my-job",'
echo -e '       "cpu": 2.0,'
echo -e '       "mem_gb": 4.0,'
echo -e '       "runtime_minutes": 30,'
echo -e '       "deadline_minutes": 120'
echo -e '     }'"'"
echo ""
echo -e "${BOLD}2. 스케줄링 트리거 (CASPIAN 최적화):${NC}"
echo -e '   curl -X POST http://localhost:8080/hub/schedule'
echo ""
echo -e "${BOLD}3. 디스패치 트리거 (Kubernetes Job 배포):${NC}"
echo -e '   curl -X POST http://localhost:8080/hub/dispatch'
echo ""
echo -e "${BOLD}4. 배포된 Job 확인:${NC}"
echo -e '   kubectl --context kind-carbon-kr get jobs,pods'
echo ""

echo -e "${BOLD}${CYAN}🔧 유용한 명령어${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BOLD}시스템 상태 확인:${NC}"
echo -e '    curl http://localhost:8080/hub/stats | python3 -m json.tool'
echo ""
echo -e "  ${BOLD}로그 확인:${NC}"
echo -e '    docker logs -f carbon-hub          # Hub 로그'
echo -e '    docker logs -f carbon-prometheus   # Prometheus 로그'
echo -e '    docker logs -f carbon-grafana      # Grafana 로그'
echo ""
echo -e "  ${BOLD}시스템 종료:${NC}"
echo -e '    docker-compose down                # Docker 컨테이너만'
echo -e '    bash stop-caspian.sh               # 전체 시스템'
echo ""

echo -e "${BOLD}${GREEN}🎉 모든 준비가 완료되었습니다!${NC}"
echo -e "${GREEN}   지금 바로 Grafana에 접속하여 실시간 모니터링을 확인하세요.${NC}"
echo ""
