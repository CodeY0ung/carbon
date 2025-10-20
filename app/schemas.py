"""
CASPIAN 최적화 모델을 위한 데이터 스키마.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class JobSpec(BaseModel):
    """스케줄링을 위한 작업 명세."""
    job_id: str
    cpu: float = Field(gt=0, description="필요한 CPU 코어 수")
    mem_gb: float = Field(gt=0, description="메모리 (GB)")
    gpu: int = Field(ge=0, default=0, description="GPU 개수")
    runtime_slots: int = Field(gt=0, description="실행할 시간 슬롯 수")
    release_slot: int = Field(ge=0, default=0, description="최조 시작 가능 시간 슬롯")
    deadline_slot: int = Field(gt=0, description="최종 완료 시간 슬롯")
    data_gb: float = Field(ge=0, default=0, description="마이그레이션용 데이터 크기")
    affinity_regions: List[str] = Field(default_factory=list, description="선호 지역")


class ClusterCapacity(BaseModel):
    """특정 시간 슬롯에서의 클러스터 리소스 용량."""
    region: str
    slot: int = Field(ge=0)
    cpu_cap: float = Field(gt=0)
    mem_gb_cap: float = Field(gt=0)
    gpu_cap: int = Field(ge=0, default=0)


class CarbonPoint(BaseModel):
    """특정 지역 및 시간 슬롯에서의 탄소 집약도."""
    region: str
    slot: int = Field(ge=0)
    ci_gco2_per_kwh: float = Field(gt=0, description="탄소 집약도 (gCO2/kWh)")


class PlanItem(BaseModel):
    """스케줄된 작업 배치."""
    job_id: str
    region: str
    start_slot: int = Field(ge=0)


class OptimizeInput(BaseModel):
    """최적화 입력."""
    jobs: List[JobSpec]
    capacities: List[ClusterCapacity]
    carbons: List[CarbonPoint]
    regions: List[str]
    slot_seconds: float = Field(gt=0, default=300, description="시간 슬롯 길이 (초)")
    horizon_slots: int = Field(gt=0, description="계획 구간 (슬롯 수)")
    costs: Dict[str, float] = Field(default_factory=dict)
    network_costs: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    migration_allow: bool = Field(default=True)
    prev_plan: Dict[str, Dict[str, str]] = Field(default_factory=dict, description="이전 작업 배치")


class OptimizeOutput(BaseModel):
    """최적화 출력."""
    plans: List[PlanItem]
    co2_estimate_kg: float
    solver_status: str
    migrations: int = 0
