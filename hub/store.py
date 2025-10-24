"""
Hub Store
AppWrapper 및 ClusterInfo 저장 관리
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
from hub.models import AppWrapper, ClusterInfo, AppWrapperStatus

logger = logging.getLogger(__name__)


class HubStore:
    """
    Hub Cluster의 중앙 저장소

    - AppWrapper 관리
    - ClusterInfo 관리
    - 스케줄링 히스토리
    """

    def __init__(self):
        """Hub Store 초기화"""
        self._appwrappers: Dict[str, AppWrapper] = {}
        self._cluster_info: Dict[str, ClusterInfo] = {}
        self._lock = asyncio.Lock()
        logger.info("Hub Store initialized")

    # ==================== AppWrapper 관리 ====================

    async def add_appwrapper(self, appwrapper: AppWrapper) -> str:
        """
        AppWrapper 추가

        Args:
            appwrapper: AppWrapper 객체

        Returns:
            Job ID
        """
        async with self._lock:
            job_id = appwrapper.spec.job_id
            self._appwrappers[job_id] = appwrapper
            logger.info(f"Added AppWrapper {job_id}: {appwrapper.spec.cpu} CPU, {appwrapper.spec.mem_gb}GB RAM")
            return job_id

    async def get_appwrapper(self, job_id: str) -> Optional[AppWrapper]:
        """특정 AppWrapper 조회"""
        async with self._lock:
            return self._appwrappers.get(job_id)

    async def get_all_appwrappers(self) -> List[AppWrapper]:
        """모든 AppWrapper 조회"""
        async with self._lock:
            return list(self._appwrappers.values())

    async def get_pending_appwrappers(self) -> List[AppWrapper]:
        """
        배포 대기 중인 AppWrapper 조회
        target_cluster가 없거나 dispatching gate가 닫혀있는 것들
        """
        async with self._lock:
            pending = []
            for aw in self._appwrappers.values():
                # target_cluster가 없으면 pending
                if not aw.spec.target_cluster:
                    pending.append(aw)
                    continue

                # dispatching gate가 모두 열려있지 않으면 pending
                all_open = all(gate.status == "open" for gate in aw.spec.dispatching_gates)
                if not all_open and aw.status.phase == "Pending":
                    pending.append(aw)

            return pending

    async def get_running_appwrappers(self) -> List[AppWrapper]:
        """
        실행 중인 AppWrapper 조회
        마이그레이션 대상이 될 수 있는 Running 상태의 워크로드
        """
        async with self._lock:
            running = []
            for aw in self._appwrappers.values():
                if aw.status.phase == "Running":
                    running.append(aw)
            return running

    async def update_appwrapper(self, job_id: str, appwrapper: AppWrapper):
        """AppWrapper 업데이트"""
        async with self._lock:
            self._appwrappers[job_id] = appwrapper
            logger.info(f"Updated AppWrapper {job_id}")

    async def remove_appwrapper(self, job_id: str) -> bool:
        """AppWrapper 삭제"""
        async with self._lock:
            if job_id in self._appwrappers:
                del self._appwrappers[job_id]
                logger.info(f"Removed AppWrapper {job_id}")
                return True
            return False

    # ==================== ClusterInfo 관리 ====================

    async def update_cluster_info(self, cluster_info: ClusterInfo):
        """
        ClusterInfo 업데이트
        Spoke 클러스터로부터 받은 정보 저장

        Args:
            cluster_info: 클러스터 정보
        """
        async with self._lock:
            self._cluster_info[cluster_info.name] = cluster_info
            logger.info(
                f"Updated ClusterInfo {cluster_info.name}: "
                f"CI={cluster_info.carbon_intensity} gCO2/kWh, "
                f"CPU={cluster_info.resources.cpu_available}/{cluster_info.resources.cpu_total}"
            )

    async def get_cluster_info(self, cluster_name: str) -> Optional[ClusterInfo]:
        """특정 클러스터 정보 조회"""
        async with self._lock:
            return self._cluster_info.get(cluster_name)

    async def get_all_cluster_info(self) -> List[ClusterInfo]:
        """모든 클러스터 정보 조회"""
        async with self._lock:
            return list(self._cluster_info.values())

    async def get_ready_clusters(self) -> List[ClusterInfo]:
        """준비 상태인 클러스터만 조회"""
        async with self._lock:
            return [
                ci for ci in self._cluster_info.values()
                if ci.status == "ready"
            ]

    # ==================== 통계 ====================

    async def get_stats(self) -> Dict:
        """Hub Store 통계"""
        async with self._lock:
            total_appwrappers = len(self._appwrappers)
            pending = sum(1 for aw in self._appwrappers.values() if aw.status.phase == "Pending")
            running = sum(1 for aw in self._appwrappers.values() if aw.status.phase == "Running")
            completed = sum(1 for aw in self._appwrappers.values() if aw.status.phase == "Completed")

            return {
                "total_appwrappers": total_appwrappers,
                "pending": pending,
                "running": running,
                "completed": completed,
                "total_clusters": len(self._cluster_info),
                "ready_clusters": sum(1 for ci in self._cluster_info.values() if ci.status == "ready")
            }


# 전역 싱글톤 인스턴스
hub_store = HubStore()
