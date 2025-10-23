import logging
from datetime import date
from typing import List

from async_lru import alru_cache
from httpx import AsyncClient

from src.kelder_api.routes.tidal_measurements.models import TideInfo

PORTSMOUTH_STATION_ID = "0065"
COWES_STATION_ID = "0060"
SOUTHAMPTON_STATION_ID = "0062"

PORTSMOUTH_OD_TO_CD_DIFF = 2.73
PORTSMOUTH_STATION_ID_ENV_AGENCY = "E71839"

# https://environment.data.gov.uk/flood-monitoring/id/stations/E71839/readings.json?today&_sorted

logger = logging.getLogger(__name__)


async def get_height_of_tide_now() -> TideInfo:
    """
    Current height of water.
    https://environment.data.gov.uk/flood-monitoring/tidegauge/index.html#filter=7
    https://ntslf.org/tides/datum
    """
    logger.debug("Requesting current height of water")
    async with AsyncClient() as client:
        response = await client.get(
            f"https://environment.data.gov.uk/flood-monitoring/id/stations/{PORTSMOUTH_STATION_ID_ENV_AGENCY}/readings.json?today&_sorted"
        )

    return TideInfo(
        datetime_stamp=response.json()["items"][0]["dateTime"],
        height_of_tide=response.json()["items"][0]["value"] + PORTSMOUTH_OD_TO_CD_DIFF,
    )


@alru_cache(maxsize=1)
async def get_tide_predictions(date: date) -> List[TideInfo]:
    """Returns predicted tidal high and low water events for the next 7 days - Very reliable"""
    logger.debug(f"Requesting tidal prediction on: {date.strftime('%d/%m/%Y')}")
    tidal_events = []
    async with AsyncClient() as client:
        response = await client.get(
            f"https://admiraltyapi.azure-api.net/uktidalapi/api/V1/Stations/{PORTSMOUTH_STATION_ID}/TidalEvents?duration=7",
            headers={"Ocp-Apim-Subscription-Key": "cc5e647a8e5e4353b622a62abb220432"},
        )

    for tidal_event in response.json():
        tidal_events.append(
            # TypeError: str.replace() takes no keyword arguments
            TideInfo(
                datetime_stamp=tidal_event["DateTime"], # 2025-10-20T03:33:00
                height_of_tide=tidal_event["Height"],
                event=tidal_event["EventType"],
            )
        )

    return tidal_events
