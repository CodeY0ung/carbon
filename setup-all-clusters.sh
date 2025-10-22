#!/bin/bash

# Hub-Spoke 클러스터 전체 생성 스크립트
# Hub 클러스터 1개 + Spoke 클러스터 3개 (KR, JP, CN)

set -e

echo "========================================="
echo "CASPIAN Hub-Spoke 클러스터 생성"
echo "========================================="
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Kind 설치 확인
if ! command -v kind &> /dev/null; then
    echo -e "${RED}❌ Kind가 설치되어 있지 않습니다.${NC}"
    echo "설치 방법: https://kind.sigs.k8s.io/docs/user/quick-start/#installation"
    exit 1
fi

echo -e "${GREEN}✓ Kind 설치 확인됨${NC}"

# 클러스터 생성 함수
create_cluster() {
    local cluster_name=$1
    local config_file=$2
    local context_name="kind-${cluster_name}"

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Creating cluster: ${cluster_name}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # 기존 클러스터 확인 및 삭제
    if kind get clusters 2>/dev/null | grep -q "^${cluster_name}$"; then
        echo -e "${YELLOW}⚠️  Cluster ${cluster_name} already exists. Deleting...${NC}"
        kind delete cluster --name "${cluster_name}"
    fi

    # 클러스터 생성
    if [ -f "$config_file" ]; then
        kind create cluster --config="$config_file"
    else
        echo -e "${RED}❌ Config file not found: ${config_file}${NC}"
        exit 1
    fi

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Cluster ${cluster_name} created successfully${NC}"

        # Context 확인
        kubectl config use-context "${context_name}"
        echo ""
        echo "Cluster info:"
        kubectl cluster-info --context "${context_name}"
        echo ""
        echo "Nodes:"
        kubectl get nodes --context "${context_name}"
    else
        echo -e "${RED}❌ Failed to create cluster ${cluster_name}${NC}"
        exit 1
    fi
}

# 1. Hub 클러스터 생성
echo ""
echo -e "${BLUE}[1/4] Hub 클러스터 생성...${NC}"
create_cluster "carbon-hub" "clusters/cluster-hub.yaml"

# 2. Spoke 클러스터들 생성
echo ""
echo -e "${BLUE}[2/4] Spoke 클러스터 - KR 생성...${NC}"
create_cluster "carbon-kr" "clusters/cluster-kr.yaml"

echo ""
echo -e "${BLUE}[3/4] Spoke 클러스터 - JP 생성...${NC}"
create_cluster "carbon-jp" "clusters/cluster-jp.yaml"

echo ""
echo -e "${BLUE}[4/4] Spoke 클러스터 - CN 생성...${NC}"
create_cluster "carbon-cn" "clusters/cluster-cn.yaml"

echo ""
echo "========================================="
echo "모든 클러스터 생성 완료!"
echo "========================================="
echo ""

# 생성된 클러스터 확인
echo "생성된 클러스터:"
kind get clusters | grep "carbon-"

echo ""
echo "Kubectl contexts:"
kubectl config get-contexts | grep "carbon-"

echo ""
echo "========================================="
echo "클러스터 구조:"
echo "========================================="
echo -e "${GREEN}Hub Cluster:${NC}"
echo "  - carbon-hub (control-plane + 1 worker)"
echo ""
echo -e "${GREEN}Spoke Clusters:${NC}"
echo "  - carbon-kr (control-plane + 2 workers)"
echo "  - carbon-jp (control-plane + 2 workers)"
echo "  - carbon-cn (control-plane + 2 workers)"
echo ""
