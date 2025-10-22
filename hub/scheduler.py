"""
Hub Scheduler
원래 설계의 3단계 프로세스 구현:
1. Spoke 클러스터로부터 정보 수집 (탄소 집약도, 가용 리소스)
2. Optimizer 호출하여 최적 배치 계산
3. AppWrapper 업데이트 (targetCluster, dispatchingGates)
"""

import asyncio
import logging
import time
from typing import List, Dict
from hub.models import (
    AppWrapper, ClusterInfo, SchedulingDecision,
    GateStatus, DispatchingGate, AppWrapperStatus
)
from hub.store import hub_store
from app.schemas import OptimizeInput, JobSpec, ClusterCapacity, CarbonPoint
from app.optimizer import build_and_solve
from app.metrics import (
    migrations_total,
    migration_data_transferred_gb,
    migrations_in_progress,
    migration_cost_gco2
)

logger = logging.getLogger(__name__)


class HubScheduler:
    """
    Hub Cluster의 중앙 스케줄러

    주기적으로 호출되어:
    1. Spoke 클러스터 정보 수집
    2. CASPIAN Optimizer 호출
    3. AppWrapper 업데이트
    """

    def __init__(self, schedule_interval: int = 300):
        """
        Hub Scheduler 초기화

        Args:
            schedule_interval: 스케줄링 주기 (초, 기본값: 300 = 5분)
        """
        self.schedule_interval = schedule_interval
        self.slot_seconds = 300  # 5분 슬롯
        self.horizon_slots = 12  # 1시간 예측 구간
        self._running = False
        self._task = None

        logger.info(f"Hub Scheduler initialized (interval: {schedule_interval}s)")

    async def start(self):
        """스케줄러 시작"""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Hub Scheduler started")

    async def stop(self):
        """스케줄러 중지"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Hub Scheduler stopped")

    async def _scheduler_loop(self):
        """
        스케줄러 메인 루프
        주기적으로 스케줄링 실행
        """
        logger.info("Scheduler loop started")

        while self._running:
            try:
                await asyncio.sleep(self.schedule_interval)
                await self.run_scheduling_cycle()

            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)

    async def run_scheduling_cycle(self):
        """
        스케줄링 사이클 실행
        원래 설계의 3단계 프로세스
        """
        logger.info("=" * 60)
        logger.info("Starting scheduling cycle")

        # Step 0: 대기 중인 AppWrapper 확인
        pending_appwrappers = await hub_store.get_pending_appwrappers()
        if not pending_appwrappers:
            logger.info("No pending AppWrappers, skipping cycle")
            return

        logger.info(f"Found {len(pending_appwrappers)} pending AppWrappers")

        # ===== Step 1: Spoke 클러스터로부터 정보 수집 =====
        cluster_infos = await self._collect_cluster_info()
        if not cluster_infos:
            logger.warning("No cluster info available, skipping cycle")
            return

        logger.info(f"Step 1: Collected info from {len(cluster_infos)} clusters")
        for ci in cluster_infos:
            logger.info(
                f"  - {ci.name}: CI={ci.carbon_intensity} gCO2/kWh, "
                f"CPU={ci.resources.cpu_available}/{ci.resources.cpu_total}"
            )

        # ===== Step 2: CASPIAN Optimizer 호출 =====
        decisions = await self._call_optimizer(pending_appwrappers, cluster_infos)
        if not decisions:
            logger.warning("No scheduling decisions from optimizer")
            return

        logger.info(f"Step 2: Optimizer returned {len(decisions)} decisions")

        # ===== Step 3: AppWrapper 업데이트 =====
        await self._update_appwrappers(decisions)
        logger.info("Step 3: Updated AppWrappers with scheduling decisions")

        logger.info("Scheduling cycle completed")
        logger.info("=" * 60)

    async def _collect_cluster_info(self) -> List[ClusterInfo]:
        """
        Step 1: Spoke 클러스터로부터 정보 수집

        Returns:
            준비 상태인 클러스터 정보 리스트
        """
        cluster_infos = await hub_store.get_ready_clusters()

        if not cluster_infos:
            logger.warning("No ready clusters available")

        return cluster_infos

    async def _call_optimizer(
        self,
        appwrappers: List[AppWrapper],
        cluster_infos: List[ClusterInfo]
    ) -> List[SchedulingDecision]:
        """
        Step 2: CASPIAN Optimizer 호출

        Args:
            appwrappers: 대기 중인 AppWrapper 리스트
            cluster_infos: 클러스터 정보 리스트

        Returns:
            스케줄링 결정 리스트
        """
        # AppWrapper를 JobSpec으로 변환
        jobs = []
        for aw in appwrappers:
            spec = aw.spec
            # 분 단위를 슬롯 단위로 변환 (5분 슬롯)
            runtime_slots = max(1, spec.runtime_minutes // 5)
            deadline_slots = max(runtime_slots, spec.deadline_minutes // 5)

            job = JobSpec(
                job_id=spec.job_id,
                cpu=spec.cpu,
                mem_gb=spec.mem_gb,
                gpu=spec.gpu,
                runtime_slots=runtime_slots,
                release_slot=0,
                deadline_slot=deadline_slots,
                data_gb=spec.data_gb,
                affinity_regions=spec.affinity_clusters
            )
            jobs.append(job)

        # ClusterInfo로부터 용량 및 탄소 데이터 구축
        regions = [ci.name for ci in cluster_infos]
        capacities = []
        carbons = []

        for ci in cluster_infos:
            for slot in range(self.horizon_slots):
                # 용량
                capacities.append(ClusterCapacity(
                    region=ci.name,
                    slot=slot,
                    cpu_cap=ci.resources.cpu_available,
                    mem_gb_cap=ci.resources.mem_available_gb,
                    gpu_cap=ci.resources.gpu_available
                ))

                # 탄소 집약도 (현재는 고정값, 향후 예측 데이터 사용)
                carbons.append(CarbonPoint(
                    region=ci.name,
                    slot=slot,
                    ci_gco2_per_kwh=ci.carbon_intensity
                ))

        # CASPIAN 최적화 입력 구성
        opt_input = OptimizeInput(
            jobs=jobs,
            capacities=capacities,
            carbons=carbons,
            regions=regions,
            slot_seconds=self.slot_seconds,
            horizon_slots=self.horizon_slots,
            costs={
                "watt_cpu": 30.0,
                "lambda_plan_dev": 100.0
            },
            network_costs={},
            migration_allow=True,
            prev_plan={}
        )

        # 최적화 실행
        result = build_and_solve(opt_input)

        logger.info(
            f"Optimizer result: {result.solver_status}, "
            f"CO2={result.co2_estimate_kg:.3f}kg, "
            f"migrations={result.migrations}"
        )

        # 결과를 SchedulingDecision으로 변환
        decisions = []
        for plan in result.plans:
            # 해당 작업의 탄소 배출량 추정
            job = next((j for j in jobs if j.job_id == plan.job_id), None)
            if not job:
                continue

            cluster = next((ci for ci in cluster_infos if ci.name == plan.region), None)
            if not cluster:
                continue

            # 간단한 CO2 계산
            estimated_co2 = (
                cluster.carbon_intensity *
                job.cpu *
                30.0 *  # watt per CPU
                (job.runtime_slots * self.slot_seconds / 3600.0) /
                1000.0
            )

            decision = SchedulingDecision(
                job_id=plan.job_id,
                target_cluster=plan.region,
                start_time_minutes=plan.start_slot * 5,
                estimated_co2_g=estimated_co2,
                reason=f"Optimal placement for minimum carbon footprint"
            )
            decisions.append(decision)

        return decisions

    async def _update_appwrappers(self, decisions: List[SchedulingDecision]):
        """
        Step 3: AppWrapper 업데이트
        targetCluster 설정 및 dispatching gate 열기
        마이그레이션 메트릭 기록

        Args:
            decisions: 스케줄링 결정 리스트
        """
        for decision in decisions:
            appwrapper = await hub_store.get_appwrapper(decision.job_id)
            if not appwrapper:
                logger.warning(f"AppWrapper {decision.job_id} not found")
                continue

            # 이전 클러스터 할당 확인 (마이그레이션 감지)
            previous_cluster = appwrapper.spec.target_cluster
            new_cluster = decision.target_cluster
            is_migration = previous_cluster and previous_cluster != new_cluster

            # 마이그레이션 발생 시 메트릭 기록
            if is_migration:
                data_gb = appwrapper.spec.data_gb
                
                # 마이그레이션 카운트 증가
                migrations_total.labels(
                    from_cluster=previous_cluster,
                    to_cluster=new_cluster
                ).inc()
                
                # 전송 데이터 기록
                migration_data_transferred_gb.labels(
                    from_cluster=previous_cluster,
                    to_cluster=new_cluster
                ).inc(data_gb)
                
                # 마이그레이션 비용 계산 및 기록
                # lam_dev (100.0) + net_cost * data_gb
                # 네트워크 비용은 현재 0으로 가정
                migration_carbon_cost = 100.0  # lam_dev 기본값
                migration_cost_gco2.labels(
                    from_cluster=previous_cluster,
                    to_cluster=new_cluster
                ).inc(migration_carbon_cost)
                
                logger.info(
                    f"  MIGRATION detected for {decision.job_id}: "
                    f"{previous_cluster} -> {new_cluster}, "
                    f"data={data_gb:.2f}GB, cost={migration_carbon_cost:.2f}gCO2"
                )

            # targetCluster 설정
            appwrapper.spec.target_cluster = decision.target_cluster

            # dispatching gate 열기 (sustainability gate)
            for gate in appwrapper.spec.dispatching_gates:
                gate.status = GateStatus.OPEN
                gate.reason = decision.reason

            # 메타데이터 업데이트
            appwrapper.metadata["scheduled_at"] = str(time.time())
            appwrapper.metadata["estimated_co2_g"] = str(decision.estimated_co2_g)
            
            if is_migration:
                appwrapper.metadata["migrated_from"] = previous_cluster
                appwrapper.metadata["migration_time"] = str(time.time())

            # 저장
            await hub_store.update_appwrapper(decision.job_id, appwrapper)

            logger.info(
                f"  Updated {decision.job_id}: "
                f"target={decision.target_cluster}, "
                f"CO2={decision.estimated_co2_g:.2f}g"
            )


# 전역 싱글톤 인스턴스
hub_scheduler = HubScheduler()
