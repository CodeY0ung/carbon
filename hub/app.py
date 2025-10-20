"""
Hub Cluster FastAPI 애플리케이션
중앙 허브의 API 엔드포인트
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
import uvicorn
import logging
import time
from contextlib import asynccontextmanager
from typing import List, Dict

from hub.models import (
    AppWrapper, AppWrapperSpec, ClusterInfo, ClusterResources,
    ClusterStatus, GateStatus
)
from hub.store import hub_store
from hub.scheduler import hub_scheduler
from hub.dispatcher import hub_dispatcher
from app.carbon_client import CarbonClient
from app.metrics import setup_metrics, metrics_registry
import os

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 전역 인스턴스
carbon_client: CarbonClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Hub Cluster 앱 라이프사이클 관리
    """
    # 시작
    global carbon_client

    logger.info("=" * 60)
    logger.info("Starting CASPIAN Hub Cluster")
    logger.info("=" * 60)

    # CarbonClient 초기화
    api_key = os.getenv("ELECTRICITYMAP_API_KEY", "your_api_key_here")
    zones_str = os.getenv("CARBON_ZONES", "KR,JP,CN")
    zones = [z.strip() for z in zones_str.split(",")]

    carbon_client = CarbonClient(api_key=api_key, poll_interval=10)
    await carbon_client.start_polling(zones)
    logger.info(f"Carbon client started for zones: {zones}")

    # ClusterInfo 초기 동기화 루프 시작
    import asyncio
    async def sync_cluster_info():
        """탄소 데이터를 ClusterInfo로 동기화"""
        while True:
            await asyncio.sleep(15)  # 15초마다
            zones_data = carbon_client.latest_data
            if zones_data:
                for zone_name, data in zones_data.items():
                    if data:
                        ci = data.get('carbonIntensity')
                        if ci:
                            # ClusterInfo 업데이트
                            cluster_info = await hub_store.get_cluster_info(zone_name)
                            if cluster_info:
                                cluster_info.carbon_intensity = ci
                                cluster_info.last_updated = time.time()
                                await hub_store.update_cluster_info(cluster_info)

    sync_task = asyncio.create_task(sync_cluster_info())

    # Hub Scheduler 시작
    await hub_scheduler.start()

    # Hub Dispatcher 시작
    await hub_dispatcher.start()

    logger.info("Hub Cluster started successfully")

    yield

    # 종료
    logger.info("Shutting down Hub Cluster")

    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass

    await hub_scheduler.stop()
    await hub_dispatcher.stop()

    if carbon_client:
        await carbon_client.stop_polling()

    logger.info("Hub Cluster shutdown complete")


app = FastAPI(
    title="CASPIAN Hub Cluster API",
    description="중앙 허브 클러스터 - 스케줄링, 최적화, 디스패칭",
    version="1.0.0",
    lifespan=lifespan
)

# Prometheus 메트릭 설정
metrics = setup_metrics()


# ==================== Health Check ====================

@app.get("/")
async def root():
    """헬스체크"""
    return {
        "status": "healthy",
        "service": "caspian-hub-cluster",
        "version": "1.0.0"
    }


# ==================== ClusterInfo 관리 ====================

@app.post("/hub/clusters")
async def register_cluster(cluster_info: ClusterInfo):
    """
    Spoke 클러스터 등록

    Spoke 클러스터가 Hub에 자신의 정보를 등록
    """
    # last_updated 자동 설정
    if cluster_info.last_updated is None:
        cluster_info.last_updated = time.time()

    await hub_store.update_cluster_info(cluster_info)
    logger.info(f"Registered cluster: {cluster_info.name}")

    return {
        "status": "registered",
        "cluster": cluster_info.name
    }


@app.get("/hub/clusters")
async def list_clusters():
    """모든 클러스터 정보 조회"""
    clusters = await hub_store.get_all_cluster_info()
    return {
        "clusters": [c.dict() for c in clusters],
        "total": len(clusters)
    }


@app.get("/hub/clusters/{cluster_name}")
async def get_cluster(cluster_name: str):
    """특정 클러스터 정보 조회"""
    cluster_info = await hub_store.get_cluster_info(cluster_name)
    if not cluster_info:
        raise HTTPException(status_code=404, detail=f"Cluster {cluster_name} not found")

    return cluster_info.dict()


# ==================== AppWrapper 관리 ====================

@app.post("/hub/appwrappers")
async def submit_appwrapper(spec: AppWrapperSpec):
    """
    AppWrapper 제출

    사용자가 작업을 제출하면 Hub가 스케줄링
    """
    # AppWrapper 생성
    appwrapper = AppWrapper(
        metadata={
            "submitted_at": str(time.time()),
            "user": "default"
        },
        spec=spec
    )

    job_id = await hub_store.add_appwrapper(appwrapper)

    logger.info(f"AppWrapper submitted: {job_id}")

    return {
        "status": "submitted",
        "job_id": job_id,
        "message": "AppWrapper will be scheduled in next cycle"
    }


@app.get("/hub/appwrappers")
async def list_appwrappers():
    """모든 AppWrapper 조회"""
    appwrappers = await hub_store.get_all_appwrappers()
    stats = await hub_store.get_stats()

    return {
        "appwrappers": [aw.dict() for aw in appwrappers],
        "stats": stats
    }


@app.get("/hub/appwrappers/{job_id}")
async def get_appwrapper(job_id: str):
    """특정 AppWrapper 조회"""
    appwrapper = await hub_store.get_appwrapper(job_id)
    if not appwrapper:
        raise HTTPException(status_code=404, detail=f"AppWrapper {job_id} not found")

    return appwrapper.dict()


@app.delete("/hub/appwrappers/{job_id}")
async def delete_appwrapper(job_id: str):
    """AppWrapper 삭제"""
    success = await hub_store.remove_appwrapper(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"AppWrapper {job_id} not found")

    return {
        "status": "deleted",
        "job_id": job_id
    }


# ==================== 수동 트리거 (테스트용) ====================

@app.post("/hub/schedule")
async def trigger_scheduling():
    """수동으로 스케줄링 사이클 트리거 (테스트용)"""
    await hub_scheduler.run_scheduling_cycle()

    return {
        "status": "completed",
        "message": "Scheduling cycle executed"
    }


@app.post("/hub/dispatch")
async def trigger_dispatch():
    """수동으로 배포 사이클 트리거 (테스트용)"""
    await hub_dispatcher.run_dispatch_cycle()

    return {
        "status": "completed",
        "message": "Dispatch cycle executed"
    }


# ==================== 통계 ====================

@app.get("/hub/stats")
async def get_stats():
    """Hub 통계"""
    stats = await hub_store.get_stats()

    # 탄소 데이터 추가
    carbon_data = {}
    if carbon_client:
        zones_data = carbon_client.latest_data
        if zones_data:
            for zone, data in zones_data.items():
                if data:
                    carbon_data[zone] = data.get('carbonIntensity', 0)

    return {
        **stats,
        "carbon_intensity": carbon_data
    }


# ==================== Prometheus Metrics ====================

@app.get("/metrics", response_class=PlainTextResponse)
async def get_metrics():
    """
    Prometheus 메트릭 노출
    """
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    # Hub 통계를 메트릭으로 업데이트
    stats = await hub_store.get_stats()
    metrics['appwrappers_total'].set(stats['total_appwrappers'])
    metrics['appwrappers_pending'].set(stats['pending'])
    metrics['appwrappers_running'].set(stats['running'])
    metrics['appwrappers_completed'].set(stats['completed'])
    metrics['clusters_total'].set(stats['total_clusters'])
    metrics['clusters_ready'].set(stats['ready_clusters'])

    # 탄소 강도 메트릭 업데이트
    if carbon_client:
        zones_data = carbon_client.latest_data
        for zone, data in zones_data.items():
            if data and 'carbonIntensity' in data:
                metrics['carbon_intensity'].labels(zone=zone).set(data['carbonIntensity'])

    return generate_latest(metrics_registry)


if __name__ == "__main__":
    logger.info("Starting Hub Cluster API server...")
    uvicorn.run(
        "hub.app:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info"
    )
