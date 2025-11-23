from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Generator, Sequence

from src.kelder_api.components.db_manager.models import JourneyHistoryRecord
from src.kelder_api.components.db_manager.queries import (
    CREATE_JOURNEY_HISTORY_TABLE,
    DELETE_ALL_JOURNEYS,
    DELETE_JOURNEY_BY_ID,
    INSERT_JOURNEY_HISTORY,
    SELECT_ALL_JOURNEYS,
    SELECT_JOURNEY_BY_ID,
    SELECT_RECENT_JOURNEYS,
)
from src.kelder_api.configuration.logging_config import setup_logging

if TYPE_CHECKING:
    from src.kelder_api.components.log.models import JourneyData

setup_logging(component="db_manager")
logger = logging.getLogger("db_manager")

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "assets" / "journey_history.db"


class DBManager:
    """High level helper around the SQLite journey history database."""

    def __init__(self, database_path: str | Path | None = None):
        self.database_path = Path(database_path) if database_path else DEFAULT_DB_PATH
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialised = False

    @contextmanager
    def _cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        connection = sqlite3.connect(self.database_path)
        try:
            cursor = connection.cursor()
            yield cursor
            connection.commit()
        except sqlite3.DatabaseError as error:
            connection.rollback()
            logger.error("SQLite error while executing query: %s", error, exc_info=True)
            raise
        finally:
            cursor.close()
            connection.close()

    def _ensure_initialised(self) -> None:
        if self._initialised:
            return

        with self._cursor() as cursor:
            cursor.execute(CREATE_JOURNEY_HISTORY_TABLE)
        self._initialised = True
        logger.info("Journey history database ready at %s", self.database_path)

    def save_trip(self, record: JourneyHistoryRecord) -> JourneyHistoryRecord:
        """Insert a trip record and return it populated with the primary key."""
        self._ensure_initialised()

        with self._cursor() as cursor:
            cursor.execute(INSERT_JOURNEY_HISTORY, record.as_db_values())
            unique_key = cursor.lastrowid

        logger.debug("Persisted journey %s", unique_key)
        return record.with_unique_key(unique_key)

    def save_from_journey_data(self, journey: "JourneyData") -> JourneyHistoryRecord:
        """Convenience wrapper when callers already have JourneyData."""
        return self.save_trip(JourneyHistoryRecord.from_journey_data(journey))

    def list_trips(self, limit: int | None = None) -> list[JourneyHistoryRecord]:
        """Retrieve trips ordered by departure time (newest first)."""
        if limit is None:
            return self._fetch_records(SELECT_ALL_JOURNEYS)
        return self._fetch_records(SELECT_RECENT_JOURNEYS, (limit,))

    def fetch_trip(self, unique_key: int) -> JourneyHistoryRecord | None:
        """Fetch a single trip by unique key."""
        results = self._fetch_records(SELECT_JOURNEY_BY_ID, (unique_key,))
        return results[0] if results else None

    def latest_trip(self) -> JourneyHistoryRecord | None:
        """Return the most recently started trip, if one exists."""
        trips = self.list_trips(limit=1)
        return trips[0] if trips else None

    def delete_trip(self, unique_key: int) -> bool:
        """Delete a single trip by unique key."""
        self._ensure_initialised()
        with self._cursor() as cursor:
            cursor.execute(DELETE_JOURNEY_BY_ID, (unique_key,))
            deleted = cursor.rowcount > 0
        return deleted

    def clear_history(self) -> None:
        """Delete all trip history rows - primarily useful for tests."""
        self._ensure_initialised()
        with self._cursor() as cursor:
            cursor.execute(DELETE_ALL_JOURNEYS)

    def _fetch_records(
        self, query: str, params: Sequence | None = None
    ) -> list[JourneyHistoryRecord]:
        """Execute a select query and parse the results."""
        self._ensure_initialised()
        with self._cursor() as cursor:
            cursor.execute(query, params if params is not None else ())
            rows = cursor.fetchall()
        return [JourneyHistoryRecord.from_row(row) for row in rows]
