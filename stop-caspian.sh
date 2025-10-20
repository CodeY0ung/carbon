#!/bin/bash

# CASPIAN Hub-Spoke 시스템 종료 스크립트

# 색상 정의
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo ""
echo -e "${BOLD}${CYAN}=========================================="
echo "  CASPIAN Hub-Spoke 시스템 종료"
echo -e "==========================================${NC}"
echo ""

# Docker 컨테이너 종료
echo -e "${YELLOW}[1/2] Docker 컨테이너 종료...${NC}"
docker-compose down
echo -e "${GREEN}✓ Docker 컨테이너 종료 완료${NC}"
echo ""

# Kind 클러스터 종료 확인
echo -e "${YELLOW}[2/2] Kind 클러스터 처리...${NC}"
existing_clusters=$(kind get clusters 2>/dev/null | grep -E "carbon-(kr|jp|cn)" || true)

if [ ! -z "$existing_clusters" ]; then
    echo -e "${BLUE}→ 발견된 클러스터: $existing_clusters${NC}"
    echo ""
    read -p "Kind 클러스터도 삭제하시겠습니까? (y/N): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}   클러스터 삭제 중...${NC}"
        kind delete cluster --name carbon-kr 2>/dev/null || true
        kind delete cluster --name carbon-jp 2>/dev/null || true
        kind delete cluster --name carbon-cn 2>/dev/null || true
        echo -e "${GREEN}✓ Kind 클러스터 삭제 완료${NC}"
    else
        echo -e "${BLUE}→ Kind 클러스터는 유지됩니다${NC}"
    fi
else
    echo -e "${BLUE}→ Kind 클러스터 없음${NC}"
fi
echo ""

echo -e "${BOLD}${GREEN}=========================================="
echo "  시스템 종료 완료"
echo -e "==========================================${NC}"
echo ""
echo -e "${BLUE}다시 시작하려면: bash start-caspian.sh${NC}"
echo ""
