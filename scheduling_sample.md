
수학적 모델 정의(목적 함수, 제약식)
import pulp
from collections import defaultdict
from typing import Dict, Tuple
from .schemas import OptimizeInput, OptimizeOutput, PlanItem

def build_and_solve_full(inp: OptimizeInput, solver_name: str = "CBC") -> OptimizeOutput:
    regions = inp.regions
    H = inp.horizon_slots
    jobs = inp.jobs
    cap = defaultdict(lambda: {"cpu": 0, "mem": 0, "gpu": 0})
    ci = defaultdict(lambda: 0.0)
    for c in inp.capacities:
        cap[(c.region, c.slot)] = {"cpu": c.cpu_cap, "mem": c.mem_gb_cap, "gpu": c.gpu_cap}
    for p in inp.carbons:
        ci[(p.region, p.slot)] = p.ci_gco2_per_kwh

    watt_cpu = float(inp.costs.get("watt_cpu", 30.0))
    lam_dev = float(inp.costs.get("lambda_plan_dev", 100.0))
    net_matrix = inp.network_costs or {}
    allow_mig = inp.migration_allow

    prob = pulp.LpProblem("caspian_full", pulp.LpMinimize)
    x: Dict[Tuple[str, str, int], pulp.LpVariable] = {}
    for j in jobs:
        for r in regions:
            if j.affinity_regions and r not in j.affinity_regions:
                continue
            for t in range(j.release_slot, j.deadline_slot - j.runtime_slots + 2):
                x[(j.job_id, r, t)] = pulp.LpVariable(f"x__{j.job_id}__{r}__{t}", cat=pulp.LpBinary)

    SLOT_HOURS = max(inp.slot_seconds / 3600.0, 0.0001)
    obj_terms = []

    for j in jobs:
        prev = inp.prev_plan.get(j.job_id)
        prev_r = prev.get("region") if prev else None
        for r in regions:
            if j.affinity_regions and r not in j.affinity_regions:
                continue
            for t in range(j.release_slot, j.deadline_slot - j.runtime_slots + 2):
                var = x[(j.job_id, r, t)]
                ci_sum = sum(ci[(r, tau)] * (j.cpu * watt_cpu * SLOT_HOURS / 1000.0) for tau in range(t, t + j.runtime_slots))
                cost = ci_sum
                if prev_r:
                    if not allow_mig and r != prev_r:
                        cost += 1e6
                    elif allow_mig and r != prev_r:
                        net_cost = net_matrix.get(prev_r, {}).get(r, 0.0)
                        cost += lam_dev + (net_cost * j.data_gb)
                obj_terms.append(var * cost)
    prob += pulp.lpSum(obj_terms)

    for j in jobs:
        starts = []
        for r in regions:
            if j.affinity_regions and r not in j.affinity_regions:
                continue
            for t in range(j.release_slot, j.deadline_slot - j.runtime_slots + 2):
                starts.append(x[(j.job_id, r, t)])
        prob += pulp.lpSum(starts) == 1

    for r in regions:
        for tau in range(H):
            c = cap.get((r, tau), {"cpu": 0, "mem": 0, "gpu": 0})
            prob += pulp.lpSum(x[(j.job_id, r, t)] * j.cpu
                               for j in jobs
                               for t in range(j.release_slot, j.deadline_slot - j.runtime_slots + 2)
                               if (t <= tau < t + j.runtime_slots) and (j.affinity_regions == [] or r in j.affinity_regions)
                               and (j.job_id, r, t) in x) <= c["cpu"]

    solver = pulp.PULP_CBC_CMD(msg=False)
    status = prob.solve(solver)
    plans, mig = [], 0
    for j in jobs:
        chosen = None
        for r in regions:
            for t in range(j.release_slot, j.deadline_slot - j.runtime_slots + 2):
                if (j.job_id, r, t) in x and pulp.value(x[(j.job_id, r, t)]) > 0.5:
                    chosen = (r, t)
                    break
            if chosen:
                break
        if not chosen:
            raise RuntimeError(f"No placement for job {j.job_id}")
        prev_r = inp.prev_plan.get(j.job_id, {}).get("region")
        if prev_r and chosen[0] != prev_r:
            mig += 1
        plans.append(PlanItem(job_id=j.job_id, region=chosen[0], start_slot=chosen[1]))
    total = pulp.value(prob.objective) or 0.0
    return OptimizeOutput(plans=plans, co2_estimate_kg=total/1000.0, solver_status=pulp.LpStatus[status], migrations=mig)

탄소인지형 스케줄링 알고리즘 구현
import argparse, yaml
from optimizer.schemas import OptimizeInput, JobSpec, ClusterCapacity, CarbonPoint
from optimizer.model_full import build_and_solve_full

def synthetic_input(cfg):
    regions = [r["name"] for r in cfg["regions"]]
    H = cfg["horizon_slots"]
    jobs = [
        JobSpec(job_id=f"job-{i}", cpu=(i % 3) + 1, mem_gb=2, runtime_slots=2,
                release_slot=0, deadline_slot=min(H-1, 4+i), data_gb=1.5)
        for i in range(3)
    ]
    capacities = [ClusterCapacity(region=r, slot=t, cpu_cap=6, mem_gb_cap=24, gpu_cap=0)
                  for r in regions for t in range(H)]
    carbons = []
    for r in regions:
        base = 400 if r == "KR" else (300 if r == "JP" else 350)
        for t in range(H):
            carbons.append(CarbonPoint(region=r, slot=t, ci_gco2_per_kwh=base + (t%4)*20))
    return OptimizeInput(
        jobs=jobs,
        capacities=capacities,
        carbons=carbons,
        regions=regions,
        slot_seconds=cfg["slot_seconds"],
        horizon_slots=H,
        costs=cfg["costs"],
        network_costs=cfg["network_costs"],
        migration_allow=cfg["migration_policy"]["allow"]
    )

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    inp = synthetic_input(cfg)
    out = build_and_solve_full(inp)

    print("\n===== CASPIAN MODEL TEST RUN =====")
    print("Solver Status:", out.solver_status)
    print("Total CO₂ (kg):", round(out.co2_estimate_kg, 3))
    print("Migrations:", out.migrations)
    print("Plan:")
    for p in out.plans:
        print(f" - {p.job_id}: {p.region} @ slot {p.start_slot}")
    print("==================================\n")

실시간 재스케줄링 루프
import time, yaml
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from dispatcher.mcad_dispatcher import MCADDispatcher
from hub.store import store
from hub.controller import HubController
from hub.app import MIG_C

def run_loop(config_path: str = "config.yaml"):
    cfg = yaml.safe_load(open(config_path))
    hub = HubController(cfg)
    disp = MCADDispatcher(namespace=cfg["mcad"]["namespace"], dry_run=cfg["kubectl"]["dry_run"])
    slot_s = cfg["slot_seconds"]

    while True:
        jobs = store.list_jobs()
        if not jobs:
            time.sleep(5)
            continue
        out = hub.optimize(jobs)
        print(f"status={out.solver_status} co2={out.co2_estimate_kg:.3f}kg migrations={out.migrations}")
        if out.migrations:
            MIG_C.inc(out.migrations)
        for item in out.plans:
            if item.start_slot == 0:
                kubecontext = next(r["kubecontext"] for r in cfg["regions"] if r["name"] == item.region)
                job = store.jobs[item.job_id]
                disp.dispatch_appwrapper(kubecontext, item.job_id, item.region, cfg["job_defaults"]["image"], job.cpu, job.mem_gb)
        store.save_plan(out.plans)
        time.sleep(slot_s)

if __name__ == "__main__":
    import threading
    import uvicorn

    # 1️⃣ 스케줄러 루프를 별도 스레드로 실행
    def start_scheduler():
        run_loop("config.yaml")

    t = threading.Thread(target=start_scheduler, daemon=True)
    t.start()

    # 2️⃣ 동시에 FastAPI 모니터링 서버 실행
    uvicorn.run("hub.app:app", host="0.0.0.0", port=8080)
