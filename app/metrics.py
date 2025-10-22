"""
탄소 인지형 스케줄링 애플리케이션을 위한 Prometheus 메트릭.
"""

from prometheus_client import Counter, Gauge, CollectorRegistry

# 메트릭을 위한 커스텀 레지스트리 생성
metrics_registry = CollectorRegistry()

# 필수 메트릭
# 그리드 탄소 집약도 게이지 - 지역별 현재 탄소 집약도 추적
grid_carbon_intensity_gco2_per_kwh = Gauge(
    'grid_carbon_intensity_gco2_per_kwh',
    'Current grid carbon intensity in gCO2/kWh',
    ['zone'],
    registry=metrics_registry
)

# 탄소 데이터 최종 업데이트 타임스탬프
carbon_last_updated_unix = Gauge(
    'carbon_last_updated_unix',
    'Unix timestamp of last carbon intensity update',
    registry=metrics_registry
)

# API 요청 카운터
api_requests_total = Counter(
    'api_requests_total',
    'Total number of API requests',
    ['endpoint', 'method', 'status'],
    registry=metrics_registry
)

# Best zone 지표 - 최적 지역은 1, 나머지는 0
best_zone_indicator = Gauge(
    'best_zone_indicator',
    'Indicator for the best zone (1=best, 0=not best)',
    ['zone'],
    registry=metrics_registry
)

# Hub 메트릭
appwrappers_total = Gauge(
    'appwrappers_total',
    'Total number of AppWrappers',
    registry=metrics_registry
)

appwrappers_pending = Gauge(
    'appwrappers_pending',
    'Number of pending AppWrappers',
    registry=metrics_registry
)

appwrappers_running = Gauge(
    'appwrappers_running',
    'Number of running AppWrappers',
    registry=metrics_registry
)

appwrappers_completed = Gauge(
    'appwrappers_completed',
    'Number of completed AppWrappers',
    registry=metrics_registry
)

clusters_total = Gauge(
    'clusters_total',
    'Total number of clusters',
    registry=metrics_registry
)

clusters_ready = Gauge(
    'clusters_ready',
    'Number of ready clusters',
    registry=metrics_registry
)


def setup_metrics():
    """Hub용 메트릭 딕셔너리 반환"""
    return {
        'carbon_intensity': grid_carbon_intensity_gco2_per_kwh,
        'carbon_last_updated': carbon_last_updated_unix,
        'api_requests': api_requests_total,
        'best_zone': best_zone_indicator,
        'appwrappers_total': appwrappers_total,
        'appwrappers_pending': appwrappers_pending,
        'appwrappers_running': appwrappers_running,
        'appwrappers_completed': appwrappers_completed,
        'clusters_total': clusters_total,
        'clusters_ready': clusters_ready,
        'migrations_total': migrations_total,
        'migration_data_transferred': migration_data_transferred_gb,
        'migrations_in_progress': migrations_in_progress,
        'migration_cost': migration_cost_gco2
    }

# 마이그레이션 메트릭
migrations_total = Counter(
    'migrations_total',
    'Total number of workload migrations',
    ['from_cluster', 'to_cluster'],
    registry=metrics_registry
)

migration_data_transferred_gb = Counter(
    'migration_data_transferred_gb',
    'Total data transferred during migrations in GB',
    ['from_cluster', 'to_cluster'],
    registry=metrics_registry
)

migrations_in_progress = Gauge(
    'migrations_in_progress',
    'Number of migrations currently in progress',
    registry=metrics_registry
)

migration_cost_gco2 = Counter(
    'migration_cost_gco2',
    'Total carbon cost of migrations in gCO2',
    ['from_cluster', 'to_cluster'],
    registry=metrics_registry
)
