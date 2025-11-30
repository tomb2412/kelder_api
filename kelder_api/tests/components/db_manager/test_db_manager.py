from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Callable

import pytest

from src.kelder_api.components.db_manager.models import (
    JourneyHistoryRecord,
    JourneyLocation,
)
from src.kelder_api.components.db_manager.queries import JOURNEY_HISTORY_TABLE
from src.kelder_api.components.db_manager.service import DBManager
from src.kelder_api.components.log.models import JourneyData


@pytest.fixture()
def journey_record_factory() -> Callable[..., JourneyHistoryRecord]:
    base_time = datetime(2025, 1, 10, 9, tzinfo=timezone.utc)

    def _factory(
        *,
        days_offset: int = 0,
        hours_offset: int = 0,
        distance: float = 12.5,
        gps_data: str | None = None,
    ) -> JourneyHistoryRecord:
        departure = base_time + timedelta(days=days_offset, hours=hours_offset)
        arrival = departure + timedelta(hours=6, minutes=30)
        return JourneyHistoryRecord(
            departure_time=departure,
            arrival_time=arrival,
            departure_location=JourneyLocation(
                latitude="52.13.77", longitude="002.11.27"
            ),
            arrival_location=JourneyLocation(
                latitude="52.14.30", longitude="002.12.30"
            ),
            distance_travelled=distance,
            gps_data=gps_data,
        )

    return _factory


def test_save_trip_persists_record(db_manager: DBManager, journey_record_factory):
    record = journey_record_factory()

    stored = db_manager.save_trip(record)

    assert stored.unique_key is not None
    persisted = db_manager.fetch_trip(stored.unique_key)
    assert persisted is not None
    assert persisted.departure_location.latitude == "52.13.77"
    assert persisted.distance_travelled == pytest.approx(record.distance_travelled)
    assert persisted.gps_data is None


def test_list_trips_returns_newest_first(
    db_manager: DBManager, journey_record_factory
) -> None:
    first = db_manager.save_trip(journey_record_factory())
    second = db_manager.save_trip(journey_record_factory(days_offset=1))

    keys = [trip.unique_key for trip in db_manager.list_trips()]

    assert keys == [second.unique_key, first.unique_key]


def test_fetch_trip_returns_none_for_unknown_id(db_manager: DBManager) -> None:
    assert db_manager.fetch_trip(9999) is None


def test_delete_trip_removes_row(db_manager: DBManager, journey_record_factory) -> None:
    record = db_manager.save_trip(journey_record_factory())

    assert db_manager.delete_trip(record.unique_key) is True
    assert db_manager.fetch_trip(record.unique_key) is None
    assert not db_manager.delete_trip(record.unique_key)


def test_latest_trip_returns_most_recent(
    db_manager: DBManager, journey_record_factory
) -> None:
    db_manager.save_trip(journey_record_factory())
    latest = db_manager.save_trip(journey_record_factory(days_offset=2))

    assert db_manager.latest_trip().unique_key == latest.unique_key


def test_save_trip_persists_gps_data(db_manager: DBManager, journey_record_factory):
    gps_blob = "0123456789," * 1000
    record = journey_record_factory(gps_data=gps_blob)

    stored = db_manager.save_trip(record)
    fetched = db_manager.fetch_trip(stored.unique_key)

    assert fetched is not None
    assert fetched.gps_data == gps_blob


def test_save_from_journey_data_round_trips(db_manager: DBManager) -> None:
    journey_data = JourneyData(
        timestamp=datetime(2025, 3, 15, 7, tzinfo=timezone.utc),
        end_datetime=datetime(2025, 3, 15, 15, tzinfo=timezone.utc),
        start_latitude="5045.2000",
        start_longitude="00110.3000",
        end_latitude="5055.1000",
        end_longitude="00140.2000",
        gps_data="[]",
    )

    stored = db_manager.save_from_journey_data(journey_data)

    fetched = db_manager.fetch_trip(stored.unique_key)
    assert fetched is not None
    assert fetched.departure_location.latitude == journey_data.start_latitude
    assert fetched.arrival_location.longitude == journey_data.end_longitude
    assert fetched.distance_travelled == pytest.approx(journey_data.distance_travelled)
    assert fetched.gps_data == journey_data.gps_data


def test_existing_database_is_migrated_to_include_gps_column(db_path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            f"""
            CREATE TABLE {JOURNEY_HISTORY_TABLE}(
                unique_key INTEGER PRIMARY KEY AUTOINCREMENT,
                departure_time TEXT NOT NULL,
                arrival_time TEXT NOT NULL,
                departure_location TEXT NOT NULL,
                arrival_location TEXT NOT NULL,
                distance_travelled REAL NOT NULL
            );
            """
        )

    manager = DBManager(db_path)
    manager.list_trips()

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                f"PRAGMA table_info({JOURNEY_HISTORY_TABLE});"
            )
        }

    assert "gps_data" in columns
