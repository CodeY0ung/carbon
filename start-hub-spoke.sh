#!/bin/bash

# CASPIAN 완전한 Hub-Spoke 시스템 시작 스크립트
# Hub 클러스터 + Spoke 클러스터 3개

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}${CYAN}=========================================="
echo "  CASPIAN 완전한 Hub-Spoke 시스템 시작"
echo "==========================================${NC}"
echo ""
echo -e "${BLUE}Hub 클러스터 + Spoke 클러스터 (KR, JP, CN)${NC}"
echo ""

# Step 1: 환경 정리
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[1/7] 기존 환경 정리...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 기존 클러스터 확인 및 삭제
for cluster in carbon-hub carbon-kr carbon-jp carbon-cn; do
    if kind get clusters 2>/dev/null | grep -q "^${cluster}$"; then
        echo -e "${BLUE}→ 기존 클러스터 삭제: ${cluster}${NC}"
        kind delete cluster --name "${cluster}" 2>/dev/null || true
    fi
done

echo -e "${GREEN}✓ 환경 정리 완료${NC}"
echo ""

# Step 2: 클러스터 생성
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[2/7] 모든 클러스터 생성...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

bash setup-all-clusters.sh

echo -e "${GREEN}✓ 모든 클러스터 생성 완료${NC}"
echo ""

# Step 3: Hub Docker 이미지 빌드
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[3/7] Hub Docker 이미지 빌드...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${BLUE}→ Docker 이미지 빌드 중...${NC}"
docker build -t carbon-hub:latest .

echo -e "${GREEN}✓ Docker 이미지 빌드 완료${NC}"
echo ""

# Step 4: Hub 클러스터에 이미지 로드
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[4/7] Hub 클러스터에 이미지 로드...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${BLUE}→ Hub 클러스터에 이미지 로드 중...${NC}"
kind load docker-image carbon-hub:latest --name carbon-hub

echo -e "${GREEN}✓ 이미지 로드 완료${NC}"
echo ""

# Step 5: Spoke 클러스터 kubeconfig 생성
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[5/7] Spoke 클러스터 kubeconfig 생성...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Hub 클러스터에서 Spoke 클러스터에 접근할 수 있도록 kubeconfig 생성
echo -e "${BLUE}→ Spoke 클러스터 kubeconfig 내보내기...${NC}"

# Spoke 클러스터들의 kubeconfig를 하나로 합침
KUBECONFIG_FILES=""
for cluster in carbon-kr carbon-jp carbon-cn; do
    kubectl config view --minify --flatten --context "kind-${cluster}" > "/tmp/kubeconfig-${cluster}"

    # API 서버 주소를 컨테이너 이름으로 변경
    KIND_PORT=$(docker port ${cluster}-control-plane 6443/tcp | cut -d: -f2)
    sed -i "s|https://127.0.0.1:${KIND_PORT}|https://${cluster}-control-plane:6443|g" "/tmp/kubeconfig-${cluster}"

    KUBECONFIG_FILES="${KUBECONFIG_FILES}:/tmp/kubeconfig-${cluster}"
done

# 모든 kubeconfig 합치기
KUBECONFIG="${KUBECONFIG_FILES:1}" kubectl config view --flatten > kubeconfig-spokes

echo -e "${GREEN}✓ Spoke kubeconfig 생성 완료${NC}"
echo ""

# Step 6: Hub 클러스터에 배포
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[6/7] Hub 클러스터에 애플리케이션 배포...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

kubectl config use-context kind-carbon-hub

# Spoke kubeconfig를 ConfigMap으로 생성
echo -e "${BLUE}→ Spoke kubeconfig ConfigMap 생성...${NC}"
kubectl create namespace caspian-hub --dry-run=client -o yaml | kubectl apply -f -
kubectl create configmap spoke-kubeconfig \
    --from-file=config=kubeconfig-spokes \
    --namespace=caspian-hub \
    --dry-run=client -o yaml | kubectl apply -f -

# Hub 애플리케이션 배포
echo -e "${BLUE}→ Hub 애플리케이션 배포 중...${NC}"
kubectl apply -f k8s/hub-deployment.yaml

echo -e "${GREEN}✓ Hub 배포 완료${NC}"
echo ""

# Step 7: 시스템 준비 대기 및 클러스터 등록
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[7/7] 시스템 준비 및 클러스터 등록...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${BLUE}→ Hub API 준비 대기 중 (최대 120초)...${NC}"

# Hub API가 준비될 때까지 대기
MAX_WAIT=120
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    if curl -s http://localhost:8080/hub/stats > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Hub API 준비 완료!${NC}"
        break
    fi

    if kubectl get pods -n caspian-hub -l app=hub-api 2>/dev/null | grep -q "Running"; then
        echo -n "."
    else
        echo -n "⏳"
    fi

    sleep 5
    ELAPSED=$((ELAPSED + 5))
done
echo ""

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo -e "${RED}❌ Hub API 시작 시간 초과${NC}"
    echo ""
    echo "Pod 상태 확인:"
    kubectl get pods -n caspian-hub
    echo ""
    echo "Pod 로그 확인:"
    kubectl logs -n caspian-hub -l app=hub-api --tail=50
    exit 1
fi

# Spoke 클러스터 자동 등록
echo ""
echo -e "${BLUE}→ Spoke 클러스터 등록 중...${NC}"

# carbon-kr 등록
curl -X POST http://localhost:8080/hub/clusters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "carbon-kr",
    "geolocation": "KR",
    "carbon_intensity": 400.0,
    "resources": {
      "cpu_available": 14.0,
      "cpu_total": 16.0,
      "mem_available_gb": 28.0,
      "mem_total_gb": 32.0,
      "gpu_available": 0,
      "gpu_total": 0
    },
    "kubeconfig_context": "kind-carbon-kr"
  }' > /dev/null 2>&1

echo -e "${GREEN}  ✓ carbon-kr 등록 완료${NC}"

# carbon-jp 등록
curl -X POST http://localhost:8080/hub/clusters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "carbon-jp",
    "geolocation": "JP",
    "carbon_intensity": 450.0,
    "resources": {
      "cpu_available": 14.0,
      "cpu_total": 16.0,
      "mem_available_gb": 28.0,
      "mem_total_gb": 32.0,
      "gpu_available": 0,
      "gpu_total": 0
    },
    "kubeconfig_context": "kind-carbon-jp"
  }' > /dev/null 2>&1

echo -e "${GREEN}  ✓ carbon-jp 등록 완료${NC}"

# carbon-cn 등록
curl -X POST http://localhost:8080/hub/clusters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "carbon-cn",
    "geolocation": "CN",
    "carbon_intensity": 550.0,
    "resources": {
      "cpu_available": 14.0,
      "cpu_total": 16.0,
      "mem_available_gb": 28.0,
      "mem_total_gb": 32.0,
      "gpu_available": 0,
      "gpu_total": 0
    },
    "kubeconfig_context": "kind-carbon-cn"
  }' > /dev/null 2>&1

echo -e "${GREEN}  ✓ carbon-cn 등록 완료${NC}"

echo ""
echo -e "${BOLD}${GREEN}=========================================="
echo "  시스템 시작 완료!"
echo "==========================================${NC}"
echo ""

# 시스템 상태 확인
echo -e "${CYAN}📊 시스템 상태:${NC}"
echo ""

# Hub 클러스터 상태
echo -e "${BOLD}Hub 클러스터 (carbon-hub):${NC}"
kubectl get nodes --context kind-carbon-hub
echo ""
kubectl get pods -n caspian-hub --context kind-carbon-hub
echo ""

# Spoke 클러스터 상태
echo -e "${BOLD}Spoke 클러스터:${NC}"
for cluster in carbon-kr carbon-jp carbon-cn; do
    echo -e "${GREEN}→ ${cluster}:${NC}"
    kubectl get nodes --context "kind-${cluster}" | tail -n +2
done
echo ""

# Hub API 상태
echo -e "${CYAN}📡 Hub API 상태:${NC}"
curl -s http://localhost:8080/hub/stats | python -m json.tool
echo ""

# 등록된 클러스터
echo -e "${CYAN}🌐 등록된 클러스터:${NC}"
curl -s http://localhost:8080/hub/clusters | python -m json.tool
echo ""

echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}접속 정보:${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  Hub API:        ${GREEN}http://localhost:8080${NC}"
echo -e "  Prometheus:     ${GREEN}http://localhost:9090${NC}"
echo -e "  Grafana:        ${GREEN}http://localhost:3000${NC} (admin/admin)"
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}다음 단계:${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "1. AppWrapper 제출:"
echo "   curl -X POST http://localhost:8080/hub/appwrappers \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"job_id\":\"test\",\"cpu\":2.0,\"mem_gb\":4.0,\"runtime_minutes\":30,\"deadline_minutes\":120}'"
echo ""
echo "2. 스케줄링 실행:"
echo "   curl -X POST http://localhost:8080/hub/schedule"
echo ""
echo "3. Job 배포:"
echo "   curl -X POST http://localhost:8080/hub/dispatch"
echo ""
echo "4. Job 상태 확인:"
echo "   kubectl get jobs,pods --context kind-carbon-kr"
echo ""
