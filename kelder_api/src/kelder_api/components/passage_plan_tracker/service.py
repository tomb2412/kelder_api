import logging
from datetime import datetime, timezone

from src.kelder_api.components.agentic_workflow.agents.models import PassagePlan, Waypoint
from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.passage_plan_tracker.models import PassagePlanProgress
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.redis_client.types import RedisSetNames
from src.kelder_api.components.velocity.utils import (
    bearing_degrees,
    convert_to_decimal_degrees,
    haversine,
)

logger = logging.getLogger("passage_plan_tracker")

REDIS_KEY = "progress:passage_plan"


class PassagePlanTracker:
    def __init__(self, redis_client: RedisClient, gps_interface: GPSInterface):
        self.redis_client = redis_client
        self.gps_interface = gps_interface

    async def calculate_progress(self) -> None:
        """Called by the orchestrator each tick to update passage plan progress."""
        # Read passage plan from Redis
        try:
            plan_data = (
                await self.redis_client.read_set(RedisSetNames.PASSAGE_PLAN)
            )[0]
        except IndexError:
            logger.debug("No passage plan set")
            await self._write_progress(
                PassagePlanProgress(
                    timestamp=datetime.now(timezone.utc),
                    distance_to_waypoint=None,
                    next_waypoint_name=None,
                    next_waypoint_index=None,
                )
            )
            return

        plan = PassagePlan(**plan_data)
        waypoints = plan.course_to_steer

        if not waypoints:
            logger.debug("Passage plan has no waypoints")
            await self._write_progress(
                PassagePlanProgress(
                    timestamp=datetime.now(timezone.utc),
                    distance_to_waypoint=None,
                    next_waypoint_name=None,
                    next_waypoint_index=None,
                )
            )
            return

        # Read latest GPS position
        gps_data = await self.gps_interface.read_gps_latest(active=True)
        if gps_data is None:
            logger.debug("No GPS fix available, skipping progress update")
            return

        # Convert NMEA to decimal degrees
        boat_lat = convert_to_decimal_degrees(gps_data.latitude_nmea)
        boat_lon = convert_to_decimal_degrees(gps_data.longitude_nmea)

        # Find next waypoint
        target_index, distance = self._find_next_waypoint(
            boat_lat, boat_lon, waypoints
        )

        await self._write_progress(
            PassagePlanProgress(
                timestamp=datetime.now(timezone.utc),
                distance_to_waypoint=round(distance, 2),
                next_waypoint_name=waypoints[target_index].name,
                next_waypoint_index=target_index,
            )
        )

    def _find_next_waypoint(
        self,
        boat_lat: float,
        boat_lon: float,
        waypoints: list[Waypoint],
    ) -> tuple[int, float]:
        """Determine the next waypoint and distance to it.

        Returns (target_index, distance_nm).
        """
        # Calculate distance from boat to each waypoint
        distances = [
            haversine(
                latitude_start=boat_lat,
                latitude_end=wp.latitude,
                longitude_start=boat_lon,
                longitude_end=wp.longitude,
            )
            for wp in waypoints
        ]

        # Single waypoint case
        if len(waypoints) == 1:
            return 0, distances[0]

        # Find closest waypoint
        closest_index = min(range(len(distances)), key=lambda i: distances[i])

        # If closest is the last waypoint, target it
        if closest_index >= len(waypoints) - 1:
            return closest_index, distances[closest_index]

        # Check if boat has passed the closest waypoint using bearing comparison
        leg_bearing = bearing_degrees(
            latitude_start=waypoints[closest_index].latitude,
            longitude_start=waypoints[closest_index].longitude,
            latitude_end=waypoints[closest_index + 1].latitude,
            longitude_end=waypoints[closest_index + 1].longitude,
        )
        boat_bearing = bearing_degrees(
            latitude_start=waypoints[closest_index].latitude,
            longitude_start=waypoints[closest_index].longitude,
            latitude_end=boat_lat,
            longitude_end=boat_lon,
        )

        angle_diff = abs(leg_bearing - boat_bearing)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff

        if angle_diff < 90:
            # Boat has passed closest waypoint — target the next one
            target_index = closest_index + 1
            return target_index, distances[target_index]

        return closest_index, distances[closest_index]

    async def _write_progress(self, progress: PassagePlanProgress) -> None:
        await self.redis_client.write_value(REDIS_KEY, progress.model_dump_json())

    async def read_progress_latest(self) -> PassagePlanProgress | None:
        raw = await self.redis_client.read_value(REDIS_KEY)
        if raw is None:
            return None
        return PassagePlanProgress.model_validate_json(raw)
