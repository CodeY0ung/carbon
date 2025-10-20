#!/bin/bash

# Spoke Clusters 생성 스크립트
# KR, JP, CN 3개의 Kind 클러스터 생성

set -e

echo "========================================="
echo "CASPIAN Spoke Clusters 생성"
echo "========================================="
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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
    local context_name="kind-${cluster_name}"

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Creating cluster: ${cluster_name}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # 기존 클러스터 확인
    if kind get clusters | grep -q "^${cluster_name}$"; then
        echo -e "${YELLOW}⚠️  Cluster ${cluster_name} already exists${NC}"
        read -p "Delete and recreate? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Deleting ${cluster_name}..."
            kind delete cluster --name "${cluster_name}"
        else
            echo "Skipping ${cluster_name}"
            return
        fi
    fi

    # 클러스터 생성
    cat <<EOF | kind create cluster --name "${cluster_name}" --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ${cluster_name}
nodes:
- role: control-plane
- role: worker
- role: worker
EOF

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

# 3개 클러스터 생성
create_cluster "carbon-kr"
create_cluster "carbon-jp"
create_cluster "carbon-cn"

echo ""
echo "========================================="
echo "모든 Spoke 클러스터 생성 완료!"
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
echo "다음 단계:"
echo "========================================="
echo "1. Hub Cluster API 시작:"
echo "   python -m uvicorn hub.app:app --host 0.0.0.0 --port 8080"
echo ""
echo "2. Spoke 클러스터 정보 등록:"
echo "   curl -X POST http://localhost:8080/hub/clusters ..."
echo ""
echo "3. AppWrapper 제출:"
echo "   curl -X POST http://localhost:8080/hub/appwrappers ..."
echo ""
