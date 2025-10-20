"""
ElectricityMap API에서 탄소 집약도 데이터를 가져오는 클라이언트.
30초마다 백그라운드 폴링으로 다중 지역 모니터링 지원.
"""

import httpx
import logging
import asyncio
import time
import os
import random
import math
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CarbonClient:
    """다중 지역 지원으로 ElectricityMap API와 상호작용하는 클라이언트."""

    BASE_URL = "https://api-access.electricitymaps.com/free-tier"
    FALLBACK_URL = "https://api.electricitymap.org/v3"

    # API를 사용할 수 없을 때 테스트용 Mock 데이터
    MOCK_DATA = {
        "CA": {"carbonIntensity": 120, "fossilFreePercentage": 75},  # 캐나다 - 재생에너지 높음
        "BR": {"carbonIntensity": 180, "fossilFreePercentage": 65},  # 브라질 - 수력발전
        "BO": {"carbonIntensity": 450, "fossilFreePercentage": 35},  # 볼리비아
        "CN": {"carbonIntensity": 650, "fossilFreePercentage": 20},  # 중국 - 항상 최악 (높은 탄소)
        "KR": {"carbonIntensity": 350, "fossilFreePercentage": 45},  # 한국 - 중간, 변동
        "JP": {"carbonIntensity": 380, "fossilFreePercentage": 40},  # 일본 - 중간, 변동
    }

    def __init__(self, api_key: str, poll_interval: int = 30, use_mock: bool = False):
        """
        탄소 클라이언트 초기화.

        Args:
            api_key: ElectricityMap API 키
            poll_interval: 폴링 간격 (초 단위, 기본값: 30)
            use_mock: 실제 API 대신 mock 데이터 사용 (기본값: False)
        """
        self.api_key = api_key
        self.poll_interval = poll_interval
        self.use_mock = use_mock or os.getenv("USE_MOCK_DATA", "false").lower() == "true"
        self.headers = {
            "auth-token": api_key,
            "User-Agent": "carbon-aware-scheduler/0.2.0"
        }
        # 여러 지역의 데이터 저장: {zone: data}
        self._zones_data: Dict[str, Optional[Dict]] = {}
        self._polling_tasks: List[asyncio.Task] = []
        self._running = False

        if self.use_mock:
            logger.warning("⚠️  MOCK MODE ENABLED - Using simulated carbon intensity data")

    @property
    def latest_data(self) -> Dict[str, Optional[Dict]]:
        """모든 지역의 최신 캐시된 탄소 집약도 데이터 조회."""
        return self._zones_data

    def get_zone_data(self, zone: str) -> Optional[Dict]:
        """
        특정 지역의 캐시된 데이터 조회.

        Args:
            zone: 지역 코드

        Returns:
            지역의 탄소 집약도 데이터 또는 None
        """
        return self._zones_data.get(zone)

    def get_best_zone(self) -> Optional[Dict]:
        """
        최저 탄소 집약도를 가진 지역 찾기.

        Returns:
            지역 정보 및 탄소 집약도가 포함된 딕셔너리, 또는 None
        """
        valid_zones = {
            zone: data
            for zone, data in self._zones_data.items()
            if data and data.get('carbonIntensity') is not None
        }

        if not valid_zones:
            return None

        best_zone = min(
            valid_zones.items(),
            key=lambda x: x[1]['carbonIntensity']
        )

        return {
            'zone': best_zone[0],
            'carbonIntensity': best_zone[1]['carbonIntensity'],
            'datetime': best_zone[1].get('datetime'),
            'fetchedAt': best_zone[1].get('fetchedAt'),
            'allZones': {
                zone: data.get('carbonIntensity')
                for zone, data in valid_zones.items()
            }
        }

    async def fetch_latest(self, zone: str) -> Optional[Dict]:
        """
        Fetch current carbon intensity for a given zone using ElectricityMap free-tier API.

        Args:
            zone: Zone code (e.g., 'KR', 'JP', 'DE', 'FR')

        Returns:
            Dictionary with carbon intensity data or None on error

        Example response:
        {
            "zone": "KR",
            "carbonIntensity": 352,
            "datetime": "2024-01-15T10:00:00.000Z",
            "updatedAt": "2024-01-15T10:05:23.145Z"
        }
        """
        if self.use_mock:
            return await self._fetch_mock_data(zone)

        urls_to_try = [
            f"{self.BASE_URL}/carbon-intensity/latest?zone={zone}",
            f"{self.FALLBACK_URL}/carbon-intensity/latest?zone={zone}",
        ]

        last_error = None

        for url in urls_to_try:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url, headers=self.headers)
                    response.raise_for_status()
                    data = response.json()
                    data['fetchedAt'] = time.time()
                    logger.info(f"✅ Successfully fetched {zone}: {data.get('carbonIntensity')} gCO2/kWh")
                    return data

            except httpx.TimeoutException:
                logger.error(f"⏱ Timeout fetching carbon data for {zone}")
                last_error = "Timeout"
            except httpx.HTTPStatusError as e:
                logger.error(f"⚠️ HTTP error for {zone}: {e.response.status_code}")
                last_error = f"HTTP {e.response.status_code}"
            except httpx.RequestError as e:
                logger.error(f"❌ Request error fetching data for {zone}: {e}")
                last_error = str(e)
            except Exception as e:
                logger.error(f"❌ Unexpected error fetching data for {zone}: {e}")
                last_error = str(e)

        logger.error(f"All API endpoints failed for {zone}. Last error: {last_error}")
        return None

    async def _fetch_mock_data(self, zone: str) -> Optional[Dict]:
        """
        Generate realistic mock carbon intensity data with time-based patterns.

        Each region has different peak/off-peak patterns to simulate realistic
        workload migration scenarios where the best region changes over time.

        Args:
            zone: Zone code

        Returns:
            Mock data dictionary with time-varying carbon intensity
        """
        # Simulate network delay
        await asyncio.sleep(random.uniform(0.1, 0.5))

        base_data = self.MOCK_DATA.get(zone)
        if not base_data:
            # Generate random data for unknown zones
            base_data = {
                "carbonIntensity": random.randint(50, 600),
                "fossilFreePercentage": random.randint(20, 95)
            }

        # Create time-based patterns that shift the "best" region over time
        # This simulates realistic grid conditions where different regions
        # have different peak/off-peak hours
        current_time = time.time()

        # Use a faster cycle (5 minutes = 300 seconds) for demo purposes
        # In production, this would be based on actual time of day
        cycle_seconds = 300  # 5-minute cycle
        phase = (current_time % cycle_seconds) / cycle_seconds  # 0.0 to 1.0

        # Each zone has a different sine wave pattern with different phases
        # This creates realistic scenarios where regions alternate as the best option
        if zone == "CA":
            # Canada: Low carbon (renewable hydro), slight variation
            wave = math.sin(phase * 2 * math.pi)
            carbon_offset = int(wave * 80)  # ±80 gCO2/kWh variation
        elif zone == "BR":
            # Brazil: Medium carbon, 120° phase shift
            wave = math.sin((phase + 0.33) * 2 * math.pi)
            carbon_offset = int(wave * 100)
        elif zone == "BO":
            # Bolivia: Higher carbon, 240° phase shift
            wave = math.sin((phase + 0.67) * 2 * math.pi)
            carbon_offset = int(wave * 150)
        elif zone == "CN":
            # China: Always worst - minimal variation (stays high)
            wave = math.sin(phase * 2 * math.pi)
            carbon_offset = int(wave * 100)  # ±100 gCO2/kWh - small variation, stays worst
        elif zone == "KR":
            # Korea: Moderate fluctuation - competes with JP for 1st/2nd place
            wave = math.sin(phase * 2 * math.pi)
            carbon_offset = int(wave * 30)  # ±50 gCO2/kWh variation
        elif zone == "JP":
            # Japan: Opposite pattern to KR - they alternate for 1st/2nd place
            wave = math.sin((phase + 0.5) * 2 * math.pi)  # 180° phase shift from KR
            carbon_offset = int(wave * 70)  # ±95 gCO2/kWh variation
        else:
            # Unknown zone: random pattern
            wave = math.sin((phase + random.random()) * 2 * math.pi)
            carbon_offset = int(wave * 100)

        # Add small random noise for realism
        noise = random.randint(-15, 15)

        # Calculate final carbon intensity
        base_intensity = base_data["carbonIntensity"]
        final_intensity = max(50, base_intensity + carbon_offset + noise)

        # Log the pattern for debugging (only occasionally to avoid spam)
        if random.random() < 0.1:  # 10% chance
            logger.debug(
                f"Mock {zone}: base={base_intensity}, offset={carbon_offset}, "
                f"noise={noise}, final={final_intensity}, phase={phase:.2f}"
            )

        return {
            "zone": zone,
            "carbonIntensity": final_intensity,
            "fossilFreePercentage": base_data.get("fossilFreePercentage", 50),
            "datetime": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "fetchedAt": time.time(),
            "isMock": True,
            "mockPhase": phase,  # Include for debugging
            "mockOffset": carbon_offset
        }

    async def _poll_loop(self, zone: str):
        """
        Background polling loop that fetches carbon data every poll_interval seconds.

        Args:
            zone: Zone code to poll
        """
        logger.info(f"Starting carbon intensity polling for zone {zone} every {self.poll_interval}s")

        while self._running:
            try:
                data = await self.fetch_latest(zone)
                if data:
                    self._zones_data[zone] = data
                    logger.info(
                        f"Updated carbon intensity for {zone}: "
                        f"{data.get('carbonIntensity')} gCO2/kWh"
                    )
                else:
                    logger.warning(f"Failed to fetch carbon data for {zone}")

            except Exception as e:
                logger.error(f"Error in polling loop for {zone}: {e}")

            # Wait for next poll
            await asyncio.sleep(self.poll_interval)

    async def start_polling(self, zones: List[str]):
        """
        Start background polling for multiple zones.

        Args:
            zones: List of zone codes to poll (e.g., ['KR', 'JP', 'DE'])
        """
        if self._running:
            logger.warning("Polling already running")
            return

        self._running = True

        logger.info(f"Starting multi-zone monitoring for: {', '.join(zones)}")

        # Initialize zones data
        for zone in zones:
            self._zones_data[zone] = None

        # Fetch initial data for all zones
        initial_tasks = [self.fetch_latest(zone) for zone in zones]
        initial_results = await asyncio.gather(*initial_tasks)

        for zone, data in zip(zones, initial_results):
            if data:
                self._zones_data[zone] = data
                logger.info(f"Initial carbon intensity for {zone}: {data.get('carbonIntensity')} gCO2/kWh")
            else:
                logger.warning(f"Failed to fetch initial data for {zone}")

        # Start background polling tasks for each zone
        for zone in zones:
            task = asyncio.create_task(self._poll_loop(zone))
            self._polling_tasks.append(task)

        logger.info(f"Background polling started for {len(zones)} zones")

    async def stop_polling(self):
        """Stop background polling for all zones."""
        if not self._running:
            return

        self._running = False

        # Cancel all polling tasks
        for task in self._polling_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._polling_tasks.clear()
        logger.info("Background polling stopped for all zones")
