"""
Hub Dispatcher
AppWrapper를 실제 Spoke 클러스터에 배포
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from hub.models import AppWrapper, GateStatus
from hub.store import hub_store

logger = logging.getLogger(__name__)


class HubDispatcher:
    """
    Hub Cluster의 Dispatcher

    AppWrapper를 Spoke 클러스터에 배포:
    - dispatching gate가 열려있는 AppWrapper 감지
    - targetCluster에 실제 Kubernetes Job 생성
    - AppWrapper 상태 업데이트
    """

    def __init__(self, dispatch_interval: int = 30):
        """
        Dispatcher 초기화

        Args:
            dispatch_interval: 배포 확인 주기 (초, 기본값: 30)
        """
        self.dispatch_interval = dispatch_interval
        self._running = False
        self._task = None
        self._k8s_clients: Dict[str, client.BatchV1Api] = {}

        logger.info(f"Hub Dispatcher initialized (interval: {dispatch_interval}s)")

    def _get_k8s_client(self, context_name: str) -> client.BatchV1Api:
        """
        특정 context의 Kubernetes 클라이언트 가져오기

        Args:
            context_name: Kubeconfig context 이름

        Returns:
            Kubernetes BatchV1Api 클라이언트
        """
        if context_name not in self._k8s_clients:
            try:
                # 특정 context로 설정 로드
                config.load_kube_config(context=context_name)
                api_client = client.ApiClient()
                batch_api = client.BatchV1Api(api_client)
                self._k8s_clients[context_name] = batch_api
                logger.info(f"Created K8s client for context: {context_name}")
            except Exception as e:
                logger.error(f"Failed to create K8s client for {context_name}: {e}")
                raise

        return self._k8s_clients[context_name]

    async def start(self):
        """Dispatcher 시작"""
        if self._running:
            logger.warning("Dispatcher already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._dispatcher_loop())
        logger.info("Hub Dispatcher started")

    async def stop(self):
        """Dispatcher 중지"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Hub Dispatcher stopped")

    async def _dispatcher_loop(self):
        """
        Dispatcher 메인 루프
        주기적으로 배포 가능한 AppWrapper 확인 및 배포
        """
        logger.info("Dispatcher loop started")

        while self._running:
            try:
                await asyncio.sleep(self.dispatch_interval)
                await self.run_dispatch_cycle()

            except Exception as e:
                logger.error(f"Error in dispatcher loop: {e}", exc_info=True)

    async def run_dispatch_cycle(self):
        """
        배포 사이클 실행
        gate가 열린 AppWrapper를 Spoke 클러스터에 배포
        """
        # 배포 가능한 AppWrapper 찾기
        dispatchable = await self._find_dispatchable_appwrappers()

        if not dispatchable:
            logger.debug("No dispatchable AppWrappers")
            return

        logger.info(f"Found {len(dispatchable)} dispatchable AppWrappers")

        # 각 AppWrapper 배포
        for aw in dispatchable:
            try:
                await self._dispatch_appwrapper(aw)
            except Exception as e:
                logger.error(f"Failed to dispatch {aw.spec.job_id}: {e}", exc_info=True)

    async def _find_dispatchable_appwrappers(self) -> List[AppWrapper]:
        """
        배포 가능한 AppWrapper 찾기

        조건:
        1. targetCluster가 설정되어 있음
        2. 모든 dispatching gate가 열려있음
        3. 아직 배포되지 않음 (status.dispatched == False)

        Returns:
            배포 가능한 AppWrapper 리스트
        """
        all_appwrappers = await hub_store.get_all_appwrappers()
        dispatchable = []

        for aw in all_appwrappers:
            # targetCluster가 없으면 스킵
            if not aw.spec.target_cluster:
                continue

            # 이미 배포되었으면 스킵
            if aw.status.dispatched:
                continue

            # 모든 gate가 열려있는지 확인
            all_gates_open = all(
                gate.status == GateStatus.OPEN
                for gate in aw.spec.dispatching_gates
            )

            if all_gates_open:
                dispatchable.append(aw)

        return dispatchable

    async def _dispatch_appwrapper(self, appwrapper: AppWrapper):
        """
        AppWrapper를 Spoke 클러스터에 배포

        Args:
            appwrapper: 배포할 AppWrapper
        """
        job_id = appwrapper.spec.job_id
        target_cluster = appwrapper.spec.target_cluster

        logger.info(f"Dispatching {job_id} to {target_cluster}")

        # 클러스터 정보 가져오기
        cluster_info = await hub_store.get_cluster_info(target_cluster)
        if not cluster_info:
            raise ValueError(f"Cluster {target_cluster} not found")

        # Kubernetes Job 매니페스트 생성
        job_manifest = self._create_job_manifest(appwrapper)

        # Spoke 클러스터에 Job 생성
        try:
            batch_api = self._get_k8s_client(cluster_info.kubeconfig_context)

            # Job 생성 (동기 API를 비동기로 실행)
            await asyncio.to_thread(
                batch_api.create_namespaced_job,
                namespace="default",
                body=job_manifest
            )

            logger.info(f"Successfully created Job {job_id} in {target_cluster}")

            # AppWrapper 상태 업데이트
            appwrapper.status.dispatched = True
            appwrapper.status.phase = "Running"
            appwrapper.status.cluster = target_cluster
            appwrapper.status.start_time = time.time()
            appwrapper.status.message = f"Dispatched to {target_cluster}"

            await hub_store.update_appwrapper(job_id, appwrapper)

        except ApiException as e:
            logger.error(f"Kubernetes API error while dispatching {job_id}: {e}")
            appwrapper.status.message = f"Dispatch failed: {e.reason}"
            await hub_store.update_appwrapper(job_id, appwrapper)
            raise

    def _create_job_manifest(self, appwrapper: AppWrapper) -> client.V1Job:
        """
        AppWrapper로부터 Kubernetes Job 매니페스트 생성

        Args:
            appwrapper: AppWrapper

        Returns:
            Kubernetes Job 매니페스트
        """
        spec = appwrapper.spec

        # Job 매니페스트
        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=spec.job_id,
                labels={
                    "app": "caspian-workload",
                    "job-id": spec.job_id,
                    "scheduled-by": "caspian"
                },
                annotations={
                    "caspian.io/target-cluster": spec.target_cluster,
                    "caspian.io/estimated-co2": appwrapper.metadata.get("estimated_co2_g", "0")
                }
            ),
            spec=client.V1JobSpec(
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(
                        labels={
                            "app": "caspian-workload",
                            "job-id": spec.job_id
                        }
                    ),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
                                name="workload",
                                image=spec.image,
                                command=spec.command,
                                resources=client.V1ResourceRequirements(
                                    requests={
                                        "cpu": f"{spec.cpu}",
                                        "memory": f"{spec.mem_gb}Gi"
                                    },
                                    limits={
                                        "cpu": f"{spec.cpu}",
                                        "memory": f"{spec.mem_gb}Gi"
                                    }
                                )
                            )
                        ],
                        restart_policy="Never"
                    )
                ),
                backoff_limit=3,
                ttl_seconds_after_finished=3600  # 1시간 후 자동 삭제
            )
        )

        return job


# 전역 싱글톤 인스턴스
hub_dispatcher = HubDispatcher()
