#!/bin/bash
# CASPIAN 완전 자동화 시작 스크립트 - Git Bash 최적화 버전

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}${CYAN}=========================================="
echo "  CASPIAN Hub-Spoke 시스템 시작"
echo "==========================================${NC}"
echo ""

# Step 1: 환경 정리
echo -e "${YELLOW}[1/10] 환경 정리...${NC}"
pkill -f "kubectl.*port-forward" 2>/dev/null || true
for cluster in carbon-hub carbon-kr carbon-jp carbon-cn; do
    if kind get clusters 2>/dev/null | grep -q "^${cluster}$"; then
        echo "  → 삭제: ${cluster}"
        kind delete cluster --name "${cluster}" 2>/dev/null || true
    fi
done
echo -e "${GREEN}✓ 완료${NC}\n"

# Step 2: Hub 클러스터 생성
echo -e "${YELLOW}[2/10] Hub 클러스터 생성...${NC}"
kind create cluster --config=clusters/cluster-hub.yaml --wait 60s
echo -e "${GREEN}✓ 완료${NC}\n"

# Step 3: Spoke 클러스터 생성
echo -e "${YELLOW}[3/10] Spoke 클러스터 생성 (병렬)...${NC}"
kind create cluster --config=clusters/cluster-kr.yaml --wait 60s &
kind create cluster --config=clusters/cluster-jp.yaml --wait 60s &
kind create cluster --config=clusters/cluster-cn.yaml --wait 60s &
wait
echo -e "${GREEN}✓ 완료${NC}\n"

# Step 4: Docker 이미지 빌드
echo -e "${YELLOW}[4/10] Docker 이미지 빌드...${NC}"
docker build -t carbon-hub:latest . > /tmp/build.log 2>&1 || {
    echo -e "${RED}빌드 실패. 로그: tail /tmp/build.log${NC}"
    exit 1
}
echo -e "${GREEN}✓ 완료${NC}\n"

# Step 5: 이미지 로드
echo -e "${YELLOW}[5/10] Kind에 이미지 로드...${NC}"
kind load docker-image carbon-hub:latest --name carbon-hub
echo -e "${GREEN}✓ 완료${NC}\n"

# Step 6: Kubeconfig 생성
echo -e "${YELLOW}[6/10] Spoke kubeconfig 생성...${NC}"
rm -f /tmp/kubeconfig-*
KUBECONFIG_FILES=""
for cluster in carbon-kr carbon-jp carbon-cn; do
    kubectl config view --minify --flatten --context "kind-${cluster}" > "/tmp/kubeconfig-${cluster}"
    KIND_PORT=$(docker port ${cluster}-control-plane 6443/tcp | cut -d: -f2)
    sed -i "s|https://127.0.0.1:${KIND_PORT}|https://${cluster}-control-plane:6443|g" "/tmp/kubeconfig-${cluster}"
    KUBECONFIG_FILES="${KUBECONFIG_FILES}:/tmp/kubeconfig-${cluster}"
done
KUBECONFIG="${KUBECONFIG_FILES:1}" kubectl config view --flatten > kubeconfig-spokes
echo -e "${GREEN}✓ 완료${NC}\n"

# Step 7: 배포
echo -e "${YELLOW}[7/10] Hub 애플리케이션 배포...${NC}"
kubectl config use-context kind-carbon-hub > /dev/null
kubectl create namespace caspian-hub --dry-run=client -o yaml | kubectl apply -f - > /dev/null
kubectl create configmap spoke-kubeconfig --from-file=config=kubeconfig-spokes -n caspian-hub --dry-run=client -o yaml | kubectl apply -f - > /dev/null
kubectl apply -f k8s/hub-deployment.yaml > /dev/null
# Grafana dashboard ConfigMap 생성
if [ -f "./dashboards/carbon-hub-dashboard.json" ]; then
    kubectl create configmap grafana-dashboard-caspian --from-file=dashboard.json=./dashboards/carbon-hub-dashboard.json -n caspian-hub --dry-run=client -o yaml | kubectl apply -f - > /dev/null
fi
echo -e "${GREEN}✓ 완료${NC}\n"

# Step 8: Pod 대기
echo -e "${YELLOW}[8/10] Pod 준비 대기...${NC}"
kubectl wait --for=condition=ready pod -l app=hub-api -n caspian-hub --timeout=180s > /dev/null || {
    echo -e "${RED}Hub API 시작 실패${NC}"
    kubectl get pods -n caspian-hub
    exit 1
}
kubectl wait --for=condition=ready pod -l app=prometheus -n caspian-hub --timeout=60s > /dev/null 2>&1 || true
kubectl wait --for=condition=ready pod -l app=grafana -n caspian-hub --timeout=60s > /dev/null 2>&1 || true
echo -e "${GREEN}✓ 완료${NC}\n"

# Step 9: Port Forwarding
echo -e "${YELLOW}[9/10] Port Forwarding 시작...${NC}"
kubectl port-forward -n caspian-hub svc/hub-api 8080:8080 > /dev/null 2>&1 &
sleep 2
kubectl port-forward -n caspian-hub svc/prometheus 9090:9090 > /dev/null 2>&1 &
sleep 2
kubectl port-forward -n caspian-hub svc/grafana 3000:3000 > /dev/null 2>&1 &
sleep 3
echo -e "${GREEN}✓ 완료${NC}\n"

# Step 10: 클러스터 등록
echo -e "${YELLOW}[10/10] 클러스터 등록...${NC}"
MAX_WAIT=60
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    if curl -s http://localhost:8080/hub/stats > /dev/null 2>&1; then
        break
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

for cluster_info in "carbon-kr:KR" "carbon-jp:JP" "carbon-cn:CN"; do
    name=$(echo $cluster_info | cut -d: -f1)
    geo=$(echo $cluster_info | cut -d: -f2)
    curl -s -X POST http://localhost:8080/hub/clusters -H 'Content-Type: application/json' -d "{\"name\":\"$name\",\"geolocation\":\"$geo\",\"carbon_intensity\":0.0,\"resources\":{\"cpu_total\":32,\"cpu_available\":32,\"mem_total_gb\":64,\"mem_available_gb\":64,\"gpu_total\":0,\"gpu_available\":0},\"kubeconfig_context\":\"kind-$name\"}" > /dev/null
    echo "  ✓ $name"
done

sleep 15
echo -e "${GREEN}✓ 완료${NC}\n"

# 완료
echo -e "${BOLD}${GREEN}=========================================="
echo "  시스템 시작 완료! 🎉"
echo "==========================================${NC}\n"
echo -e "  Hub API:     ${GREEN}http://localhost:8080${NC}"
echo -e "  Prometheus:  ${GREEN}http://localhost:9090${NC}"
echo -e "  Grafana:     ${GREEN}http://localhost:3000${NC} (admin/admin)\n"
echo -e "${YELLOW}다음 단계:${NC}"
echo -e "  ${GREEN}bash auto-migration-demo.sh${NC}\n"
