"""
CASPIAN 최적화: Linear Programming을 사용한 탄소 인지형 스케줄링.
"""

import pulp
import logging
from collections import defaultdict
from typing import Dict, Tuple
from app.schemas import OptimizeInput, OptimizeOutput, PlanItem

logger = logging.getLogger(__name__)


def build_and_solve(inp: OptimizeInput, solver_name: str = "CBC") -> OptimizeOutput:
    """
    CASPIAN 최적화 모델 구축 및 해결.

    목적 함수: 총 탄소 배출량 + 마이그레이션 비용 최소화

    의사결정 변수:
      x[job_id, region, time_slot] = 작업이 (region, time_slot)에서 시작하면 1, 아니면 0

    제약 조건:
      1. 각 작업은 정확히 한 번만 스케줄링
      2. 리소스 용량 제한
      3. 시간 윈도우 제약 (release/deadline)
      4. 친화성(affinity) 제약
    """
    regions = inp.regions
    H = inp.horizon_slots
    jobs = inp.jobs

    # 용량 및 탄소 집약도 조회 테이블 구축
    cap = defaultdict(lambda: {"cpu": 0, "mem": 0, "gpu": 0})
    ci = defaultdict(lambda: 0.0)

    for c in inp.capacities:
        cap[(c.region, c.slot)] = {
            "cpu": c.cpu_cap,
            "mem": c.mem_gb_cap,
            "gpu": c.gpu_cap
        }

    for p in inp.carbons:
        ci[(p.region, p.slot)] = p.ci_gco2_per_kwh

    # 파라미터
    watt_cpu = float(inp.costs.get("watt_cpu", 30.0))  # CPU 코어당 와트
    lam_dev = float(inp.costs.get("lambda_plan_dev", 100.0))  # 마이그레이션 페널티
    net_matrix = inp.network_costs or {}
    allow_mig = inp.migration_allow

    # LP 문제 생성
    prob = pulp.LpProblem("caspian_carbon_scheduling", pulp.LpMinimize)

    # 의사결정 변수: x[job_id, region, start_time]
    x: Dict[Tuple[str, str, int], pulp.LpVariable] = {}

    for j in jobs:
        for r in regions:
            # affinity 리스트에 없는 지역은 건너뛰기
            if j.affinity_regions and r not in j.affinity_regions:
                continue

            # 데드라인 전에 작업을 완료할 수 있는지 확인
            for t in range(j.release_slot, min(j.deadline_slot - j.runtime_slots + 1, H)):
                var_name = f"x__{j.job_id}__{r}__{t}"
                x[(j.job_id, r, t)] = pulp.LpVariable(var_name, cat=pulp.LpBinary)

    # 목적 함수: 탄소 + 마이그레이션 비용 최소화
    SLOT_HOURS = max(inp.slot_seconds / 3600.0, 0.0001)
    obj_terms = []

    for j in jobs:
        prev = inp.prev_plan.get(j.job_id)
        prev_r = prev.get("region") if prev else None

        for r in regions:
            if j.affinity_regions and r not in j.affinity_regions:
                continue

            for t in range(j.release_slot, min(j.deadline_slot - j.runtime_slots + 1, H)):
                if (j.job_id, r, t) not in x:
                    continue

                var = x[(j.job_id, r, t)]

                # 탄소 비용: 모든 실행 슬롯에 대한 CI의 합
                ci_sum = sum(
                    ci[(r, tau)] * (j.cpu * watt_cpu * SLOT_HOURS / 1000.0)
                    for tau in range(t, min(t + j.runtime_slots, H))
                )

                cost = ci_sum

                # 마이그레이션 비용
                if prev_r:
                    if not allow_mig and r != prev_r:
                        # 큰 페널티로 마이그레이션 금지
                        cost += 1e6
                    elif allow_mig and r != prev_r:
                        # 마이그레이션 페널티 + 네트워크 비용 추가
                        net_cost = net_matrix.get(prev_r, {}).get(r, 0.0)
                        cost += lam_dev + (net_cost * j.data_gb)

                obj_terms.append(var * cost)

    prob += pulp.lpSum(obj_terms)

    # 제약 1: 각 작업은 정확히 한 번만 스케줄링
    for j in jobs:
        starts = []
        for r in regions:
            if j.affinity_regions and r not in j.affinity_regions:
                continue
            for t in range(j.release_slot, min(j.deadline_slot - j.runtime_slots + 1, H)):
                if (j.job_id, r, t) in x:
                    starts.append(x[(j.job_id, r, t)])

        if starts:
            prob += pulp.lpSum(starts) == 1, f"schedule_once_{j.job_id}"

    # 제약 2: 리소스 용량 제한
    for r in regions:
        for tau in range(H):
            c = cap.get((r, tau), {"cpu": 0, "mem": 0, "gpu": 0})

            if c["cpu"] > 0:
                # CPU 용량
                cpu_usage = []
                for j in jobs:
                    if j.affinity_regions and r not in j.affinity_regions:
                        continue
                    for t in range(max(0, tau - j.runtime_slots + 1), tau + 1):
                        if (j.job_id, r, t) in x and t <= tau < t + j.runtime_slots:
                            cpu_usage.append(x[(j.job_id, r, t)] * j.cpu)

                if cpu_usage:
                    prob += pulp.lpSum(cpu_usage) <= c["cpu"], f"cpu_cap_{r}_{tau}"

            if c["mem"] > 0:
                # 메모리 용량
                mem_usage = []
                for j in jobs:
                    if j.affinity_regions and r not in j.affinity_regions:
                        continue
                    for t in range(max(0, tau - j.runtime_slots + 1), tau + 1):
                        if (j.job_id, r, t) in x and t <= tau < t + j.runtime_slots:
                            mem_usage.append(x[(j.job_id, r, t)] * j.mem_gb)

                if mem_usage:
                    prob += pulp.lpSum(mem_usage) <= c["mem"], f"mem_cap_{r}_{tau}"

    # 해결
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=10)  # 10초 타임아웃
    status = prob.solve(solver)

    # 결과 추출
    plans = []
    mig = 0

    for j in jobs:
        chosen = None
        for r in regions:
            for t in range(j.release_slot, min(j.deadline_slot - j.runtime_slots + 1, H)):
                if (j.job_id, r, t) in x and pulp.value(x[(j.job_id, r, t)]) and pulp.value(x[(j.job_id, r, t)]) > 0.5:
                    chosen = (r, t)
                    break
            if chosen:
                break

        if not chosen:
            logger.warning(f"No placement found for job {j.job_id}")
            # 폴백으로 release 시간에 첫 번째 가용 지역에 할당
            chosen = (regions[0] if regions else "unknown", j.release_slot)

        prev_r = inp.prev_plan.get(j.job_id, {}).get("region")
        if prev_r and chosen[0] != prev_r:
            mig += 1

        plans.append(PlanItem(
            job_id=j.job_id,
            region=chosen[0],
            start_slot=chosen[1]
        ))

    total_co2 = pulp.value(prob.objective) or 0.0

    return OptimizeOutput(
        plans=plans,
        co2_estimate_kg=total_co2 / 1000.0,  # 그램을 킬로그램으로 변환
        solver_status=pulp.LpStatus[status],
        migrations=mig
    )
