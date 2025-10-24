#!/bin/bash

# CASPIAN 자동 마이그레이션 데모 스크립트
# 워크로드를 생성하고 탄소 강도 변화에 따른 마이그레이션을 자동으로 시연

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}${CYAN}============================================================${NC}"
echo -e "${BOLD}${CYAN}  CASPIAN - 자동 마이그레이션 데모${NC}"
echo -e "${BOLD}${CYAN}============================================================${NC}"
echo ""

# Hub API 상태 확인
echo -e "${BLUE}→ Hub API 상태 확인 중...${NC}"
if ! curl -s http://localhost:8080/hub/stats > /dev/null 2>&1; then
    echo -e "${RED}❌ Hub API가 실행되지 않았습니다!${NC}"
    echo ""
    echo "먼저 시스템을 시작하세요:"
    echo "  bash start-complete-system.sh"
    exit 1
fi
echo -e "${GREEN}✓ Hub API 정상 작동${NC}"
echo ""

# 클러스터 등록 확인
echo -e "${BLUE}→ 클러스터 등록 확인 중...${NC}"
CLUSTER_COUNT=$(curl -s http://localhost:8080/hub/stats | python -c "import sys,json; print(json.load(sys.stdin)['total_clusters'])" 2>/dev/null || echo "0")

if [ "$CLUSTER_COUNT" = "0" ]; then
    echo -e "${YELLOW}⚠ 클러스터가 등록되지 않았습니다. 자동 등록 중...${NC}"

    # 클러스터 자동 등록
    for cluster_info in "carbon-kr:KR" "carbon-jp:JP" "carbon-cn:CN"; do
        name=$(echo $cluster_info | cut -d: -f1)
        geo=$(echo $cluster_info | cut -d: -f2)

        curl -s -X POST http://localhost:8080/hub/clusters \
            -H 'Content-Type: application/json' \
            -d "{
                \"name\": \"$name\",
                \"geolocation\": \"$geo\",
                \"carbon_intensity\": 0.0,
                \"resources\": {
                    \"cpu_total\": 32,
                    \"cpu_available\": 32,
                    \"mem_total_gb\": 64,
                    \"mem_available_gb\": 64,
                    \"gpu_total\": 0,
                    \"gpu_available\": 0
                },
                \"kubeconfig_context\": \"kind-$name\"
            }" > /dev/null

        echo -e "${GREEN}  ✓ $name 등록 완료${NC}"
    done

    echo ""
    echo -e "${BLUE}→ 탄소 데이터 동기화 대기 중 (20초)...${NC}"
    sleep 20
fi

echo -e "${GREEN}✓ $CLUSTER_COUNT 개 클러스터 등록됨${NC}"
echo ""

# 현재 탄소 강도 확인
echo -e "${CYAN}📊 현재 탄소 강도:${NC}"
curl -s http://localhost:8080/hub/stats | python -c "
import sys, json
data = json.load(sys.stdin)
ci = data['carbon_intensity']
sorted_ci = sorted(ci.items(), key=lambda x: x[1])
for zone, value in sorted_ci:
    marker = ' <- 가장 낮음 (최적)' if zone == sorted_ci[0][0] else ''
    print(f'  {zone}: {value} gCO2/kWh{marker}')
"
echo ""

# 테스트 워크로드 생성
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 1: 테스트 워크로드 생성${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

WORKLOAD_COUNT=${1:-3}  # 기본값: 3개 워크로드

echo -e "${BLUE}→ ${WORKLOAD_COUNT}개의 테스트 워크로드 생성 중...${NC}"

for i in $(seq 1 $WORKLOAD_COUNT); do
    RESULT=$(curl -s -X POST http://localhost:8080/hub/appwrappers \
        -H 'Content-Type: application/json' \
        -d "{
            \"job_id\": \"demo-workload-$i\",
            \"cpu\": 2.0,
            \"mem_gb\": 4.0,
            \"data_gb\": 30.0,
            \"runtime_minutes\": 120,
            \"deadline_minutes\": 480
        }")

    STATUS=$(echo $RESULT | python -c "import sys,json; print(json.load(sys.stdin).get('status', 'error'))" 2>/dev/null || echo "error")

    if [ "$STATUS" = "submitted" ]; then
        echo -e "${GREEN}  ✓ demo-workload-$i 생성 완료${NC}"
    else
        echo -e "${RED}  ✗ demo-workload-$i 생성 실패${NC}"
    fi
done

echo ""
echo -e "${GREEN}✓ 워크로드 생성 완료${NC}"
echo ""

# 초기 스케줄링
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 2: 초기 스케줄링${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${BLUE}→ 스케줄링 실행 중...${NC}"
curl -s -X POST http://localhost:8080/hub/schedule > /dev/null
echo -e "${GREEN}✓ 초기 배치 완료${NC}"
echo ""

# 배치 결과 확인
echo -e "${CYAN}📦 워크로드 배치 현황:${NC}"
curl -s http://localhost:8080/hub/appwrappers | python -c "
import sys, json
data = json.load(sys.stdin)
aws = data.get('appwrappers', [])

if not aws:
    print('  워크로드 없음')
else:
    for aw in aws:
        job_id = aw['spec']['job_id']
        cluster = aw['spec'].get('target_cluster', 'Not assigned')
        print(f'  {job_id}: {cluster}')
"
echo ""

# 마이그레이션 모니터링
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Step 3: 마이그레이션 모니터링${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${BLUE}탄소 강도가 변하면서 자동으로 마이그레이션이 발생합니다...${NC}"
echo -e "${YELLOW}(매 30초마다 재스케줄링, 총 10분간 모니터링)${NC}"
echo ""

CYCLES=${2:-20}  # 기본값: 20 사이클 (10분)

for i in $(seq 1 $CYCLES); do
    echo -e "${CYAN}━━━ Cycle $i/${CYCLES} ━━━${NC}"

    # 현재 탄소 강도
    echo -n "  탄소: "
    curl -s http://localhost:8080/hub/stats | python -c "
import sys, json
data = json.load(sys.stdin)
ci = data['carbon_intensity']
sorted_ci = sorted(ci.items(), key=lambda x: x[1])
parts = [f'{z}={v}' + (' ⭐' if z == sorted_ci[0][0] else '') for z, v in sorted_ci]
print(', '.join(parts))
" 2>/dev/null || echo "N/A"

    # 재스케줄링 실행 (30초마다)
    if [ $((i % 3)) -eq 0 ]; then
        curl -s -X POST http://localhost:8080/hub/schedule > /dev/null
        echo -e "  ${BLUE}[재스케줄링 실행됨]${NC}"
    fi

    # 마이그레이션 메트릭 확인
    MIGRATIONS=$(curl -s http://localhost:8080/metrics | grep "migrations_total{" | head -1)
    if [ -n "$MIGRATIONS" ]; then
        echo -e "  ${GREEN}마이그레이션: $MIGRATIONS${NC}"
    fi

    sleep 10
done

echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}최종 결과${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 최종 워크로드 배치
echo -e "${CYAN}📦 최종 워크로드 배치:${NC}"
curl -s http://localhost:8080/hub/appwrappers | python -c "
import sys, json
data = json.load(sys.stdin)
aws = data.get('appwrappers', [])

if not aws:
    print('  워크로드 없음')
else:
    for aw in aws:
        job_id = aw['spec']['job_id']
        cluster = aw['spec'].get('target_cluster', 'Not assigned')
        print(f'  {job_id}: {cluster}')
"
echo ""

# 마이그레이션 통계
echo -e "${CYAN}🔄 마이그레이션 통계:${NC}"
curl -s http://localhost:8080/metrics | grep -E "migrations_total|migration_data|migration_cost|migrations_in_progress" | while read line; do
    if [[ ! "$line" =~ ^# ]]; then
        echo "  $line"
    fi
done
echo ""

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  데모 완료! Grafana에서 마이그레이션 확인:${NC}"
echo -e "${GREEN}  http://localhost:3000/d/caspian-hub${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
