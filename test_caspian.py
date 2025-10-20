"""
Test script for CASPIAN carbon-aware scheduler.
Submits sample jobs and monitors scheduling decisions.
"""

import httpx
import asyncio
import json
import time
from typing import List, Dict


BASE_URL = "http://localhost:8000"


async def submit_job(client: httpx.AsyncClient, job: Dict) -> Dict:
    """Submit a job to the scheduler."""
    response = await client.post(f"{BASE_URL}/jobs", json=job)
    response.raise_for_status()
    return response.json()


async def get_jobs(client: httpx.AsyncClient) -> Dict:
    """Get all pending jobs."""
    response = await client.get(f"{BASE_URL}/jobs")
    response.raise_for_status()
    return response.json()


async def get_plan(client: httpx.AsyncClient) -> Dict:
    """Get current scheduling plan."""
    response = await client.get(f"{BASE_URL}/plan")
    response.raise_for_status()
    return response.json()


async def get_zones(client: httpx.AsyncClient) -> Dict:
    """Get carbon intensity for all zones."""
    response = await client.get(f"{BASE_URL}/zones")
    response.raise_for_status()
    return response.json()


async def main():
    """Run CASPIAN test scenario."""

    print("=" * 80)
    print("CASPIAN Carbon-Aware Scheduler Test")
    print("=" * 80)
    print()

    async with httpx.AsyncClient(timeout=30.0) as client:

        # Step 1: Check current carbon intensity
        print("Step 1: Checking carbon intensity across regions...")
        zones = await get_zones(client)
        print(json.dumps(zones, indent=2))
        print()

        # Step 2: Submit sample jobs
        print("Step 2: Submitting test jobs...")

        sample_jobs = [
            {
                "job_id": "web-server-1",
                "cpu": 4.0,
                "mem_gb": 8.0,
                "gpu": 0,
                "runtime_slots": 6,  # 30 minutes (6 x 5min slots)
                "release_slot": 0,
                "deadline_slot": 12,  # Must complete within 1 hour
                "data_gb": 0.5,
                "affinity_regions": []  # Can run anywhere
            },
            {
                "job_id": "ml-training-1",
                "cpu": 8.0,
                "mem_gb": 16.0,
                "gpu": 0,
                "runtime_slots": 12,  # 1 hour
                "release_slot": 0,
                "deadline_slot": 12,
                "data_gb": 2.0,
                "affinity_regions": ["KR", "JP"]  # Prefer Korea/Japan
            },
            {
                "job_id": "data-processing-1",
                "cpu": 2.0,
                "mem_gb": 4.0,
                "gpu": 0,
                "runtime_slots": 3,  # 15 minutes
                "release_slot": 0,
                "deadline_slot": 8,
                "data_gb": 1.0,
                "affinity_regions": []
            },
            {
                "job_id": "batch-job-1",
                "cpu": 4.0,
                "mem_gb": 8.0,
                "gpu": 0,
                "runtime_slots": 4,  # 20 minutes
                "release_slot": 2,  # Can start from slot 2
                "deadline_slot": 12,
                "data_gb": 0.8,
                "affinity_regions": ["CN"]  # China only
            },
            {
                "job_id": "analytics-1",
                "cpu": 6.0,
                "mem_gb": 12.0,
                "gpu": 0,
                "runtime_slots": 8,  # 40 minutes
                "release_slot": 0,
                "deadline_slot": 10,
                "data_gb": 1.5,
                "affinity_regions": []
            }
        ]

        for job in sample_jobs:
            result = await submit_job(client, job)
            print(f"  ✓ Submitted {job['job_id']}: {result['message']}")

        print()

        # Step 3: View pending jobs
        print("Step 3: Viewing pending jobs...")
        jobs_status = await get_jobs(client)
        print(f"  Total jobs: {jobs_status['stats']['total_jobs']}")
        print(f"  Total CPU requested: {jobs_status['stats']['total_cpu_requested']} cores")
        print(f"  Total memory requested: {jobs_status['stats']['total_mem_gb_requested']} GB")
        print()

        # Step 4: Wait for first scheduling cycle (5 minutes in production, but we'll check immediately)
        print("Step 4: Waiting for CASPIAN optimization...")
        print("  (In production, this runs every 5 minutes)")
        print("  For testing, we'll trigger optimization immediately by waiting 10 seconds...")

        # In a real scenario, we'd wait 300 seconds for the scheduler loop
        # For testing, let's check if there's already a plan
        await asyncio.sleep(10)

        try:
            plan = await get_plan(client)
            if plan['total_planned_jobs'] > 0:
                print(f"  ✓ Optimization complete! {plan['total_planned_jobs']} jobs scheduled")
                print()

                # Step 5: Display optimization results
                print("Step 5: Optimization Results")
                print("-" * 80)

                # Show placement by region
                regions_used = {}
                for job_id, placement in plan['plan'].items():
                    region = placement['region']
                    if region not in regions_used:
                        regions_used[region] = []
                    regions_used[region].append({
                        'job_id': job_id,
                        'start_slot': placement['start_slot']
                    })

                for region in sorted(regions_used.keys()):
                    zone_data = zones['zones'].get(region, {})
                    ci = zone_data.get('carbonIntensity', 'N/A')
                    print(f"\nRegion: {region} (Carbon Intensity: {ci} gCO2/kWh)")
                    for job_info in regions_used[region]:
                        start_time = job_info['start_slot'] * 5  # minutes
                        print(f"  - {job_info['job_id']} → starts at slot {job_info['start_slot']} ({start_time} min)")

                print()
                print("-" * 80)

                # Summary
                print("\nSummary:")
                print(f"  Regions used: {', '.join(plan['regions'])}")
                print(f"  Jobs scheduled: {plan['total_planned_jobs']} / {plan['total_pending_jobs']}")

            else:
                print("  ℹ No optimization plan yet. Jobs will be scheduled in the next cycle.")
                print("  In production, the scheduler runs every 5 minutes.")

        except Exception as e:
            print(f"  Error getting plan: {e}")

        print()
        print("=" * 80)
        print("Test Complete!")
        print("=" * 80)
        print()
        print("Next steps:")
        print("  - View jobs: GET http://localhost:8000/jobs")
        print("  - View plan: GET http://localhost:8000/plan")
        print("  - View zones: GET http://localhost:8000/zones")
        print("  - Submit more jobs: POST http://localhost:8000/jobs")
        print()


if __name__ == "__main__":
    asyncio.run(main())
