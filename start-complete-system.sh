#!/bin/bash

# CASPIAN 완전 자동화 시작 스크립트
# Hub 클러스터 + Spoke 클러스터 3개 + 모든 서비스 배포 + 클러스터 등록

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
echo "  CASPIAN 완전한 Hub-Spoke 시스템"
echo "  자동 시작 스크립트"
echo "==========================================${NC}"
echo ""
echo -e "${BLUE}Hub 클러스터 + Spoke 클러스터 (KR, JP, CN)${NC}"
echo -e "${BLUE}+ Prometheus + Grafana + 자동 클러스터 등록${NC}"
echo ""

# Step 1: 환경 정리
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[1/10] 기존 환경 정리...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

for cluster in carbon-hub carbon-kr carbon-jp carbon-cn; do
    if kind get clusters 2>/dev/null | grep -q "^${cluster}$"; then
        echo -e "${BLUE}→ 기존 클러스터 삭제: ${cluster}${NC}"
        kind delete cluster --name "${cluster}" 2>/dev/null || true
    fi
done

echo -e "${GREEN}✓ 환경 정리 완료${NC}"
echo ""

# Step 2: Hub 클러스터 생성
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[2/10] Hub 클러스터 생성...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

kind create cluster --config=clusters/cluster-hub.yaml --wait 60s
echo -e "${GREEN}✓ Hub 클러스터 생성 완료${NC}"
echo ""

# Step 3: Spoke 클러스터 생성
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[3/10] Spoke 클러스터 생성...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

kind create cluster --config=clusters/cluster-kr.yaml --wait 60s &
PID_KR=$!
kind create cluster --config=clusters/cluster-jp.yaml --wait 60s &
PID_JP=$!
kind create cluster --config=clusters/cluster-cn.yaml --wait 60s &
PID_CN=$!

wait $PID_KR
echo -e "${GREEN}  ✓ carbon-kr 생성 완료${NC}"
wait $PID_JP
echo -e "${GREEN}  ✓ carbon-jp 생성 완료${NC}"
wait $PID_CN
echo -e "${GREEN}  ✓ carbon-cn 생성 완료${NC}"

echo -e "${GREEN}✓ 모든 Spoke 클러스터 생성 완료${NC}"
echo ""

# Step 4: Docker 이미지 빌드
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[4/10] Hub Docker 이미지 빌드...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

docker build -t carbon-hub:latest . > /dev/null 2>&1
echo -e "${GREEN}✓ Docker 이미지 빌드 완료${NC}"
echo ""

# Step 5: Hub 클러스터에 이미지 로드
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[5/10] Hub 클러스터에 이미지 로드...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

kind load docker-image carbon-hub:latest --name carbon-hub
echo -e "${GREEN}✓ 이미지 로드 완료${NC}"
echo ""

# Step 6: Spoke 클러스터 kubeconfig 생성
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[6/10] Spoke 클러스터 kubeconfig 생성...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Spoke 클러스터들의 kubeconfig를 하나로 합침
rm -f /tmp/kubeconfig-*
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

# Step 7: Hub 클러스터에 배포
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[7/10] Hub 클러스터에 애플리케이션 배포...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

kubectl config use-context kind-carbon-hub > /dev/null

# Namespace 생성
kubectl create namespace caspian-hub --dry-run=client -o yaml | kubectl apply -f - > /dev/null

# Spoke kubeconfig ConfigMap 생성
kubectl create configmap spoke-kubeconfig \
    --from-file=config=kubeconfig-spokes \
    --namespace=caspian-hub \
    --dry-run=client -o yaml | kubectl apply -f - > /dev/null

# Hub 애플리케이션 배포
kubectl apply -f k8s/hub-deployment.yaml > /dev/null

# 대시보드 ConfigMap 생성
kubectl create configmap grafana-dashboard-caspian \
    --from-file=carbon-hub-dashboard.json=./dashboards/carbon-hub-dashboard.json \
    --namespace=caspian-hub \
    --dry-run=client -o yaml | kubectl apply -f - > /dev/null

echo -e "${GREEN}✓ Hub 애플리케이션 배포 완료${NC}"
echo ""

# Step 8: Pod 준비 대기
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[8/10] Pod 준비 대기...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${BLUE}→ Hub API Pod 대기 중...${NC}"
kubectl wait --for=condition=ready pod -l app=hub-api -n caspian-hub --timeout=180s > /dev/null
echo -e "${GREEN}  ✓ Hub API Ready${NC}"

echo -e "${BLUE}→ Prometheus Pod 대기 중...${NC}"
kubectl wait --for=condition=ready pod -l app=prometheus -n caspian-hub --timeout=60s > /dev/null
echo -e "${GREEN}  ✓ Prometheus Ready${NC}"

echo -e "${BLUE}→ Grafana Pod 대기 중...${NC}"
kubectl wait --for=condition=ready pod -l app=grafana -n caspian-hub --timeout=60s > /dev/null
echo -e "${GREEN}  ✓ Grafana Ready${NC}"

echo -e "${GREEN}✓ 모든 Pod 준비 완료${NC}"
echo ""

# Step 9: Hub API 헬스 체크 및 클러스터 등록
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[9/10] Hub API 헬스 체크 및 클러스터 등록...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Hub API 헬스 체크 (최대 60초 대기)
echo -e "${BLUE}→ Hub API 헬스 체크 중...${NC}"
MAX_WAIT=60
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    if curl -s http://localhost:8080/hub/stats > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ Hub API 정상 작동${NC}"
        break
    fi
    echo -n "."
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done
echo ""

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo -e "${RED}❌ Hub API 시작 실패${NC}"
    kubectl logs -n caspian-hub -l app=hub-api --tail=50
    exit 1
fi

# Spoke 클러스터 등록
echo -e "${BLUE}→ Spoke 클러스터 등록 중...${NC}"

curl -s -X POST http://localhost:8080/hub/clusters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "carbon-kr",
    "geolocation": "KR",
    "carbon_intensity": 400.0,
    "resources": {
      "cpu_available": 6.0,
      "cpu_total": 8.0,
      "mem_available_gb": 14.0,
      "mem_total_gb": 16.0,
      "gpu_available": 0,
      "gpu_total": 0
    },
    "kubeconfig_context": "kind-carbon-kr"
  }' > /dev/null
echo -e "${GREEN}  ✓ carbon-kr 등록 완료${NC}"

curl -s -X POST http://localhost:8080/hub/clusters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "carbon-jp",
    "geolocation": "JP",
    "carbon_intensity": 450.0,
    "resources": {
      "cpu_available": 6.0,
      "cpu_total": 8.0,
      "mem_available_gb": 14.0,
      "mem_total_gb": 16.0,
      "gpu_available": 0,
      "gpu_total": 0
    },
    "kubeconfig_context": "kind-carbon-jp"
  }' > /dev/null
echo -e "${GREEN}  ✓ carbon-jp 등록 완료${NC}"

curl -s -X POST http://localhost:8080/hub/clusters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "carbon-cn",
    "geolocation": "CN",
    "carbon_intensity": 550.0,
    "resources": {
      "cpu_available": 6.0,
      "cpu_total": 8.0,
      "mem_available_gb": 14.0,
      "mem_total_gb": 16.0,
      "gpu_available": 0,
      "gpu_total": 0
    },
    "kubeconfig_context": "kind-carbon-cn"
  }' > /dev/null
echo -e "${GREEN}  ✓ carbon-cn 등록 완료${NC}"

echo -e "${GREEN}✓ 모든 클러스터 등록 완료${NC}"
echo ""

# Step 10: 시스템 검증
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}[10/10] 시스템 검증...${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Hub API 상태 확인
echo -e "${BLUE}→ Hub API 상태 확인...${NC}"
HUB_STATS=$(curl -s http://localhost:8080/hub/stats)
CLUSTER_COUNT=$(echo $HUB_STATS | python -c "import sys, json; print(json.load(sys.stdin)['total_clusters'])" 2>/dev/null || echo "0")

if [ "$CLUSTER_COUNT" = "3" ]; then
    echo -e "${GREEN}  ✓ Hub API: 3개 클러스터 등록 확인${NC}"
else
    echo -e "${RED}  ✗ Hub API: 클러스터 등록 실패 (${CLUSTER_COUNT}/3)${NC}"
fi

# Prometheus 메트릭 확인
echo -e "${BLUE}→ Prometheus 메트릭 확인...${NC}"
if curl -s http://localhost:8080/metrics | grep -q "clusters_total"; then
    echo -e "${GREEN}  ✓ Prometheus 메트릭 정상 노출${NC}"
else
    echo -e "${RED}  ✗ Prometheus 메트릭 노출 실패${NC}"
fi

# Grafana 접속 확인
echo -e "${BLUE}→ Grafana 대시보드 확인...${NC}"
if curl -s http://admin:admin@localhost:3000/api/search?query=CASPIAN | grep -q "caspian-hub"; then
    echo -e "${GREEN}  ✓ Grafana 대시보드 프로비저닝 완료${NC}"
else
    echo -e "${RED}  ✗ Grafana 대시보드 프로비저닝 실패${NC}"
fi

echo ""
echo -e "${BOLD}${GREEN}=========================================="
echo "  시스템 시작 완료!"
echo "==========================================${NC}"
echo ""

# 시스템 상태 요약
echo -e "${CYAN}📊 시스템 상태:${NC}"
echo ""
curl -s http://localhost:8080/hub/stats | python -m json.tool
echo ""

# 클러스터 상태
echo -e "${CYAN}🌐 클러스터 상태:${NC}"
echo ""
echo -e "${BOLD}Hub 클러스터:${NC}"
kubectl get nodes --context kind-carbon-hub --no-headers | awk '{printf "  %-30s %s\n", $1, $2}'
echo ""
echo -e "${BOLD}Spoke 클러스터:${NC}"
for cluster in carbon-kr carbon-jp carbon-cn; do
    echo -e "${GREEN}→ ${cluster}:${NC}"
    kubectl get nodes --context "kind-${cluster}" --no-headers | awk '{printf "  %-30s %s\n", $1, $2}'
done
echo ""

# Pod 상태
echo -e "${CYAN}🐳 Hub Pod 상태:${NC}"
kubectl get pods -n caspian-hub --context kind-carbon-hub
echo ""

# 접속 정보
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}📡 접속 정보:${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  Hub API:        ${GREEN}http://localhost:8080${NC}"
echo -e "  Hub Stats:      ${GREEN}http://localhost:8080/hub/stats${NC}"
echo -e "  Hub Metrics:    ${GREEN}http://localhost:8080/metrics${NC}"
echo -e "  Prometheus:     ${GREEN}http://localhost:9090${NC}"
echo -e "  Grafana:        ${GREEN}http://localhost:3000${NC} (admin/admin)"
echo -e "  Dashboard:      ${GREEN}http://localhost:3000/d/caspian-hub${NC}"
echo ""

# 사용 예제
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}🚀 다음 단계 - 테스트 작업 제출:${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "1. AppWrapper 제출:"
echo "   curl -X POST http://localhost:8080/hub/appwrappers \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"job_id\":\"test-1\",\"cpu\":2.0,\"mem_gb\":4.0,\"runtime_minutes\":30,\"deadline_minutes\":120}'"
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
echo -e "${GREEN}시스템이 정상적으로 시작되었습니다! 🎉${NC}"
echo ""
