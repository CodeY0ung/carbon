"""
Hub Cluster 데이터 모델
ClusterInfo, AppWrapper 등 Hub에서 사용하는 모델 정의
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from enum import Enum


class GateStatus(str, Enum):
    """Dispatching Gate 상태"""
    OPEN = "open"      # 배포 허용
    CLOSED = "closed"  # 배포 차단


class ClusterStatus(str, Enum):
    """Spoke 클러스터 상태"""
    READY = "ready"
    NOT_READY = "not_ready"
    UNKNOWN = "unknown"


class ClusterResources(BaseModel):
    """클러스터 리소스 정보"""
    cpu_available: float = Field(description="가용 CPU 코어 수")
    cpu_total: float = Field(description="전체 CPU 코어 수")
    mem_available_gb: float = Field(description="가용 메모리 (GB)")
    mem_total_gb: float = Field(description="전체 메모리 (GB)")
    gpu_available: int = Field(default=0, description="가용 GPU 개수")
    gpu_total: int = Field(default=0, description="전체 GPU 개수")


class ClusterInfo(BaseModel):
    """
    Spoke 클러스터 정보
    각 Spoke 클러스터의 지리적 위치, 탄소 집약도, 리소스 상태
    """
    name: str = Field(description="클러스터 이름 (KR, JP, CN 등)")
    geolocation: str = Field(description="지리적 위치 (한국, 일본, 중국 등)")
    carbon_intensity: float = Field(description="현재 탄소 집약도 (gCO2/kWh)")
    status: ClusterStatus = Field(default=ClusterStatus.READY)
    resources: ClusterResources = Field(description="클러스터 리소스 정보")
    kubeconfig_context: str = Field(description="Kubeconfig context 이름")
    last_updated: Optional[float] = Field(default=None, description="마지막 업데이트 시간 (Unix timestamp)")


class DispatchingGate(BaseModel):
    """
    AppWrapper의 배포 게이트
    sustainability gate를 통해 탄소 기반 배포 제어
    """
    name: str = Field(default="sustainability-gate", description="게이트 이름")
    status: GateStatus = Field(default=GateStatus.CLOSED, description="게이트 상태")
    reason: Optional[str] = Field(default=None, description="게이트 상태 이유")


class AppWrapperSpec(BaseModel):
    """
    AppWrapper 명세
    작업의 요구사항 및 배포 정보
    """
    job_id: str = Field(description="작업 ID")
    cpu: float = Field(gt=0, description="필요한 CPU 코어 수")
    mem_gb: float = Field(gt=0, description="필요한 메모리 (GB)")
    gpu: int = Field(ge=0, default=0, description="필요한 GPU 개수")
    runtime_minutes: int = Field(gt=0, description="예상 실행 시간 (분)")
    deadline_minutes: int = Field(gt=0, description="데드라인 (분)")
    data_gb: float = Field(ge=0, default=0, description="데이터 크기 (GB)")
    affinity_clusters: List[str] = Field(default_factory=list, description="선호 클러스터")
    image: str = Field(default="busybox:latest", description="컨테이너 이미지")
    command: List[str] = Field(default_factory=lambda: ["sleep", "3600"], description="실행 명령")

    # CASPIAN이 결정할 필드
    target_cluster: Optional[str] = Field(default=None, description="배치될 클러스터")
    dispatching_gates: List[DispatchingGate] = Field(
        default_factory=lambda: [DispatchingGate()],
        description="배포 게이트"
    )


class AppWrapperStatus(BaseModel):
    """AppWrapper 상태"""
    phase: str = Field(default="Pending", description="현재 단계 (Pending, Running, Completed, Failed)")
    dispatched: bool = Field(default=False, description="배포 여부")
    cluster: Optional[str] = Field(default=None, description="실제 배포된 클러스터")
    start_time: Optional[float] = Field(default=None, description="시작 시간")
    completion_time: Optional[float] = Field(default=None, description="완료 시간")
    message: Optional[str] = Field(default=None, description="상태 메시지")


class AppWrapper(BaseModel):
    """
    AppWrapper - CASPIAN의 작업 단위
    MCAD와 유사한 구조로 작업 정의 및 배포 정보 포함
    """
    metadata: Dict[str, str] = Field(default_factory=dict, description="메타데이터")
    spec: AppWrapperSpec = Field(description="AppWrapper 명세")
    status: AppWrapperStatus = Field(default_factory=AppWrapperStatus, description="AppWrapper 상태")


class SchedulingDecision(BaseModel):
    """
    스케줄링 결정
    Optimizer가 반환하는 배치 결정
    """
    job_id: str
    target_cluster: str
    start_time_minutes: int = Field(description="시작 시간 (분 단위)")
    estimated_co2_g: float = Field(description="예상 CO2 배출량 (g)")
    reason: str = Field(description="배치 이유")
