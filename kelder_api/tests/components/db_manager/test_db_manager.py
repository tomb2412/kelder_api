from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import pytest

from src.kelder_api.components.db_manager.models import (
    JourneyHistoryRecord,
    JourneyLocation,
)
from src.kelder_api.components.db_manager.service import DBManager
from src.kelder_api.components.log.models import JourneyData


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "journey_history.db"


@pytest.fixture()
def db_manager(db_path: Path) -> DBManager:
    manager = DBManager(db_path)
    manager.clear_history()
    return manager


@pytest.fixture()
def journey_record_factory() -> Callable[..., JourneyHistoryRecord]:
    base_time = datetime(2025, 1, 10, 9, tzinfo=timezone.utc)

    def _factory(
        *, days_offset: int = 0, hours_offset: int = 0
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
        )

    return _factory


def test_save_trip_persists_record(db_manager: DBManager, journey_record_factory):
    record = journey_record_factory()

    stored = db_manager.save_trip(record)

    assert stored.unique_key is not None
    persisted = db_manager.fetch_trip(stored.unique_key)
    assert persisted is not None
    assert persisted.departure_location.latitude == "52.13.77"


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


def test_save_from_journey_data_round_trips(db_manager: DBManager) -> None:
    journey_data = JourneyData(
        timestamp=datetime(2025, 3, 15, 7, tzinfo=timezone.utc),
        end_datetime=datetime(2025, 3, 15, 15, tzinfo=timezone.utc),
        start_latitude="50.45.20",
        start_longitude="001.10.30",
        end_latitude="50.55.10",
        end_longitude="001.40.20",
    )

    stored = db_manager.save_from_journey_data(journey_data)

    fetched = db_manager.fetch_trip(stored.unique_key)
    assert fetched is not None
    assert fetched.departure_location.latitude == journey_data.start_latitude
    assert fetched.arrival_location.longitude == journey_data.end_longitude
