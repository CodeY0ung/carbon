"""
Kopf-based Kubernetes operator for carbon-aware scheduling.
Watches for Pod/Job resources with label 'carbon-aware=true' and modifies their
scheduling preferences based on current carbon intensity.
"""

import kopf
import logging
import os
import httpx
from typing import Dict, Optional
from kubernetes import client, config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
CARBON_API_URL = os.getenv("CARBON_API_URL", "http://fastapi-service.carbon-poc.svc.cluster.local:8000")
HIGH_THRESHOLD = int(os.getenv("HIGH_THRESHOLD", "300"))  # gCO2/kWh
LOW_THRESHOLD = int(os.getenv("LOW_THRESHOLD", "150"))    # gCO2/kWh
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"


async def get_best_zone() -> Optional[Dict]:
    """
    Fetch the zone with lowest carbon intensity from the FastAPI /best-zone endpoint.

    Returns:
        Dictionary with best zone data (zone, carbonIntensity, allZones) or None if unavailable
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CARBON_API_URL}/best-zone",
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            return data
    except Exception as e:
        logger.error(f"Failed to fetch best zone carbon intensity: {e}")
        return None


def determine_scheduling_strategy(carbon_intensity: Optional[int]) -> Dict:
    """
    Determine scheduling strategy based on carbon intensity.

    Args:
        carbon_intensity: Current carbon intensity in gCO2/kWh

    Returns:
        Dictionary with scheduling decision and node preferences
    """
    if carbon_intensity is None:
        return {
            "strategy": "default",
            "reason": "carbon_data_unavailable",
            "node_selector": None,
            "node_affinity": None
        }

    if carbon_intensity > HIGH_THRESHOLD:
        # High carbon: prefer low-priority nodes or defer
        logger.info(f"High carbon intensity ({carbon_intensity} > {HIGH_THRESHOLD}): preferring low-priority nodes")
        return {
            "strategy": "low_priority",
            "reason": "high_carbon_intensity",
            "node_selector": {"energy_profile": "low_priority"},
            "node_affinity": {
                "preferredDuringSchedulingIgnoredDuringExecution": [
                    {
                        "weight": 100,
                        "preference": {
                            "matchExpressions": [
                                {
                                    "key": "energy_profile",
                                    "operator": "In",
                                    "values": ["low_priority", "renewable"]
                                }
                            ]
                        }
                    }
                ]
            }
        }
    elif carbon_intensity <= LOW_THRESHOLD:
        # Low carbon: prefer low-carbon/renewable nodes
        logger.info(f"Low carbon intensity ({carbon_intensity} <= {LOW_THRESHOLD}): preferring low-carbon nodes")
        return {
            "strategy": "low_carbon",
            "reason": "low_carbon_intensity",
            "node_selector": None,  # Don't require specific nodes
            "node_affinity": {
                "preferredDuringSchedulingIgnoredDuringExecution": [
                    {
                        "weight": 100,
                        "preference": {
                            "matchExpressions": [
                                {
                                    "key": "energy_profile",
                                    "operator": "In",
                                    "values": ["low_carbon", "renewable"]
                                }
                            ]
                        }
                    }
                ]
            }
        }
    else:
        # Medium carbon: no specific preference
        logger.info(f"Medium carbon intensity ({carbon_intensity}): using default scheduling")
        return {
            "strategy": "default",
            "reason": "medium_carbon_intensity",
            "node_selector": None,
            "node_affinity": None
        }


@kopf.on.create('v1', 'pods')
async def on_pod_create(spec, name, namespace, labels, meta, **kwargs):
    """
    Handler for Pod creation events.
    Watches pods with label 'carbon-aware=true' and modifies their scheduling.
    """
    # Check if pod is marked for carbon-aware scheduling
    if not labels or labels.get("carbon-aware") != "true":
        return

    logger.info(f"Carbon-aware Pod detected: {namespace}/{name}")

    # Get best zone (lowest carbon intensity)
    carbon_data = await get_best_zone()

    if not carbon_data:
        logger.warning(f"Could not fetch best zone carbon data for Pod {namespace}/{name}")
        return

    carbon_intensity = carbon_data.get("carbonIntensity")
    zone = carbon_data.get("zone", "unknown")
    all_zones = carbon_data.get("allZones", {})

    # Determine scheduling strategy
    strategy = determine_scheduling_strategy(carbon_intensity)

    logger.info(
        f"Pod {namespace}/{name}: best_zone={zone} carbon={carbon_intensity} gCO2/kWh, "
        f"all_zones={all_zones}, strategy={strategy['strategy']}, reason={strategy['reason']}"
    )

    # Build patch
    patch = {
        'metadata': {
            'annotations': {
                'carbon-intensity': str(carbon_intensity) if carbon_intensity else 'unknown',
                'carbon-zone': zone,
                'carbon-all-zones': str(all_zones),
                'carbon-strategy': strategy['strategy'],
                'carbon-reason': strategy['reason'],
            }
        }
    }

    # Add scheduling modifications if not default strategy
    if strategy['node_selector'] or strategy['node_affinity']:
        spec_patch = {}

        if strategy['node_selector']:
            spec_patch['nodeSelector'] = strategy['node_selector']

        if strategy['node_affinity']:
            spec_patch['affinity'] = {
                'nodeAffinity': strategy['node_affinity']
            }

        patch['spec'] = spec_patch

    if DRY_RUN:
        logger.info(f"[DRY-RUN] Would patch Pod {namespace}/{name} with: {patch}")
        return

    return patch


@kopf.on.create('batch', 'v1', 'jobs')
async def on_job_create(spec, name, namespace, labels, **kwargs):
    """
    Handler for Job creation events.
    Watches jobs with label 'carbon-aware=true' and modifies their pod template.
    """
    # Check if job is marked for carbon-aware scheduling
    if not labels or labels.get("carbon-aware") != "true":
        return

    logger.info(f"Carbon-aware Job detected: {namespace}/{name}")

    # Get best zone (lowest carbon intensity)
    carbon_data = await get_best_zone()

    if not carbon_data:
        logger.warning(f"Could not fetch best zone carbon data for Job {namespace}/{name}")
        return

    carbon_intensity = carbon_data.get("carbonIntensity")
    zone = carbon_data.get("zone", "unknown")
    all_zones = carbon_data.get("allZones", {})

    # Determine scheduling strategy
    strategy = determine_scheduling_strategy(carbon_intensity)

    logger.info(
        f"Job {namespace}/{name}: best_zone={zone} carbon={carbon_intensity} gCO2/kWh, "
        f"all_zones={all_zones}, strategy={strategy['strategy']}, reason={strategy['reason']}"
    )

    # Build patch for Job
    patch = {
        'metadata': {
            'annotations': {
                'carbon-intensity': str(carbon_intensity) if carbon_intensity else 'unknown',
                'carbon-zone': zone,
                'carbon-all-zones': str(all_zones),
                'carbon-strategy': strategy['strategy'],
                'carbon-reason': strategy['reason'],
            }
        }
    }

    # Patch the pod template in the job spec
    if strategy['node_selector'] or strategy['node_affinity']:
        template_patch = {}

        # Add annotations to pod template
        if 'template' not in patch:
            patch['spec'] = {'template': {'metadata': {'annotations': {}}}}

        spec_patch = {}

        if strategy['node_selector']:
            spec_patch['nodeSelector'] = strategy['node_selector']

        if strategy['node_affinity']:
            spec_patch['affinity'] = {
                'nodeAffinity': strategy['node_affinity']
            }

        if 'spec' not in patch:
            patch['spec'] = {}

        patch['spec']['template'] = {
            'metadata': {
                'annotations': {
                    'carbon-intensity': str(carbon_intensity) if carbon_intensity else 'unknown',
                    'carbon-strategy': strategy['strategy'],
                }
            },
            'spec': spec_patch
        }

    if DRY_RUN:
        logger.info(f"[DRY-RUN] Would patch Job {namespace}/{name} with: {patch}")
        return

    return patch


@kopf.on.startup()
async def configure(settings: kopf.OperatorSettings, **_):
    """
    Configure the operator on startup.
    """
    settings.posting.level = logging.INFO

    logger.info("=" * 60)
    logger.info("Carbon-Aware Scheduling Operator")
    logger.info("=" * 60)
    logger.info(f"Carbon API URL: {CARBON_API_URL}")
    logger.info(f"High Threshold: {HIGH_THRESHOLD} gCO2/kWh")
    logger.info(f"Low Threshold: {LOW_THRESHOLD} gCO2/kWh")
    logger.info(f"Dry Run Mode: {DRY_RUN}")
    logger.info("=" * 60)

    # Test connection to Carbon API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{CARBON_API_URL}/", timeout=5.0)
            if response.status_code == 200:
                logger.info("✓ Successfully connected to Carbon API")
            else:
                logger.warning(f"⚠ Carbon API returned status {response.status_code}")
    except Exception as e:
        logger.error(f"✗ Failed to connect to Carbon API: {e}")
        logger.error("  The operator will continue but may not function correctly")

    logger.info("Operator started successfully. Watching for carbon-aware=true resources...")
