
from prometheus_client import Gauge, start_http_server
import time
import carbon_scheduler  # 기존 스케줄링 로직 불러오기

# Prometheus 메트릭 정의
job_count = Gauge('carbon_job_count', 'Total number of jobs processed')
carbon_saving = Gauge('carbon_saving_percent', 'Carbon saving compared to baseline')
late_jobs = Gauge('late_job_count', 'Number of jobs that missed deadline')

def update_metrics():
    while True:
        try:
            result = carbon_scheduler.run_scheduler()
            job_count.set(result.get('job_count', 0))
            carbon_saving.set(result.get('carbon_saving', 0.0))
            late_jobs.set(result.get('late_jobs', 0))
        except Exception as e:
            print(f"Error running scheduler: {e}")
        time.sleep(10)

if __name__ == '__main__':
    print("Starting Prometheus exporter on port 8000...")
    start_http_server(8000)
    update_metrics()
