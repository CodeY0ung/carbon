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
        "KR": {"carbonIntensity": 350, "fossilFreePercentage": 45},  # 한국 - 경쟁 1
        "JP": {"carbonIntensity": 340, "fossilFreePercentage": 48},  # 일본 - 경쟁 2 (KR과 자주 교차)
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
        Generate realistic mock carbon intensity data with irregular patterns.
        
        Simulates real-world grid behavior:
        - Multiple overlapping cycles (daily patterns, weather, demand fluctuations)
        - Random renewable energy variations (wind/solar intermittency)
        - Sudden demand spikes and drops
        - Occasional grid events
        
        This creates unpredictable but realistic patterns where the "best" region
        changes irregularly, triggering realistic migration scenarios.
        
        Args:
            zone: Zone code
        
        Returns:
            Mock data dictionary with time-varying carbon intensity
        """
        # Simulate network delay
        await asyncio.sleep(random.uniform(0.1, 0.5))
        
        base_data = self.MOCK_DATA.get(zone)
        if not base_data:
            base_data = {
                "carbonIntensity": random.randint(50, 600),
                "fossilFreePercentage": random.randint(20, 95)
            }
        
        current_time = time.time()
        
        # Base carbon intensity
        base_intensity = base_data["carbonIntensity"]
        
        # === Multi-frequency pattern mixing (irregular behavior) ===
        
        # Long cycle: ~10 minutes (simulates daily demand patterns)
        long_cycle = 600
        long_wave = math.sin(current_time / long_cycle * 2 * math.pi)
        
        # Medium cycle: ~3 minutes (simulates weather/cloud cover changes)
        med_cycle = 180
        med_wave = math.sin(current_time / med_cycle * 2 * math.pi)
        
        # Short cycle: ~1 minute (simulates rapid demand fluctuations)
        short_cycle = 60
        short_wave = math.sin(current_time / short_cycle * 2 * math.pi)
        
        # Zone-specific behavior patterns
        # KR and JP compete closely - frequent crossovers for migration testing
        if zone == "KR":
            # Korea: Fast-changing pattern with strong variations
            # Uses opposite phase for Japan to create frequent crossovers
            pattern = (long_wave * 100) + (med_wave * 80) + (short_wave * 60)
            # Frequent renewable surges (30% chance)
            if random.random() < 0.30:
                pattern -= random.randint(80, 150)
            # Occasional demand spikes (20% chance)
            if random.random() < 0.20:
                pattern += random.randint(60, 120)

        elif zone == "JP":
            # Japan: Inverse pattern to Korea for frequent crossovers
            # When KR goes up, JP tends to go down and vice versa
            pattern = (-long_wave * 90) + (-med_wave * 70) + (short_wave * 50)
            # Frequent solar/wind changes (30% chance)
            if random.random() < 0.30:
                pattern -= random.randint(70, 140)
            # Occasional peaks (20% chance)
            if random.random() < 0.20:
                pattern += random.randint(50, 110)
                
        elif zone == "CN":
            # China: High baseline (coal-heavy), less variable but still fluctuates
            pattern = (long_wave * 40) + (med_wave * 30) + (short_wave * 20)
            # Consistently high but not completely static
            
        elif zone == "CA":
            # Canada: Low baseline (hydro), very stable
            pattern = (long_wave * 30) + (med_wave * 20) + (short_wave * 15)
            # Occasional hydro adjustments (20% chance)
            if random.random() < 0.20:
                pattern -= random.randint(10, 30)
                
        elif zone == "BR":
            # Brazil: Medium baseline, depends on hydro reservoir levels
            pattern = (long_wave * 60) + (med_wave * 40) + (short_wave * 25)
            # Rain/drought effects (12% chance)
            if random.random() < 0.12:
                pattern += random.randint(-40, 60)
                
        elif zone == "BO":
            # Bolivia: Higher carbon, moderate variability
            pattern = (long_wave * 80) + (med_wave * 50) + (short_wave * 30)
            
        else:
            # Unknown zone: random pattern
            pattern = (long_wave * 70) + (med_wave * 50) + (short_wave * 30)
        
        # === Add realistic noise and events ===
        
        # Continuous random noise (measurement uncertainty, small grid fluctuations)
        continuous_noise = random.randint(-25, 25)
        
        # Rare significant events (5% chance: grid issues, major renewable output changes)
        event_noise = 0
        if random.random() < 0.05:
            event_noise = random.randint(-80, 80)
            if abs(event_noise) > 50:
                logger.info(f"Mock {zone}: Significant grid event! Δ{event_noise:+d} gCO2/kWh")
        
        # Calculate final carbon intensity
        final_intensity = int(base_intensity + pattern + continuous_noise + event_noise)
        
        # Ensure realistic bounds (grids don't go below 50 or above 800 gCO2/kWh)
        final_intensity = max(50, min(800, final_intensity))
        
        # Occasional detailed logging for monitoring
        if random.random() < 0.05:  # 5% chance
            logger.debug(
                f"Mock {zone}: base={base_intensity}, pattern={int(pattern)}, "
                f"noise={continuous_noise}, event={event_noise}, final={final_intensity}"
            )
        
        return {
            "zone": zone,
            "carbonIntensity": final_intensity,
            "fossilFreePercentage": base_data.get("fossilFreePercentage", 50),
            "datetime": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "fetchedAt": time.time(),
            "isMock": True,
            "mockPattern": "irregular_realistic"
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
