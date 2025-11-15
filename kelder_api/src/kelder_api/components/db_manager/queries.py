JOURNEY_HISTORY_TABLE = "journey_history"

CREATE_JOURNEY_HISTORY_TABLE = f"""
CREATE TABLE IF NOT EXISTS {JOURNEY_HISTORY_TABLE}(
    unique_key INTEGER PRIMARY KEY AUTOINCREMENT,
    departure_time TEXT NOT NULL,
    arrival_time TEXT NOT NULL,
    departure_location TEXT NOT NULL,
    arrival_location TEXT NOT NULL
);
""".strip()

INSERT_JOURNEY_HISTORY = f"""
INSERT INTO {JOURNEY_HISTORY_TABLE} (
    departure_time,
    arrival_time,
    departure_location,
    arrival_location
) VALUES (?, ?, ?, ?);
""".strip()

SELECT_ALL_JOURNEYS = f"""
SELECT unique_key, departure_time, arrival_time, departure_location, arrival_location
FROM {JOURNEY_HISTORY_TABLE}
ORDER BY departure_time DESC;
""".strip()

SELECT_JOURNEY_BY_ID = f"""
SELECT unique_key, departure_time, arrival_time, departure_location, arrival_location
FROM {JOURNEY_HISTORY_TABLE}
WHERE unique_key = ?;
""".strip()

SELECT_RECENT_JOURNEYS = f"""
SELECT unique_key, departure_time, arrival_time, departure_location, arrival_location
FROM {JOURNEY_HISTORY_TABLE}
ORDER BY departure_time DESC
LIMIT ?;
""".strip()

DELETE_JOURNEY_BY_ID = f"""
DELETE FROM {JOURNEY_HISTORY_TABLE}
WHERE unique_key = ?;
""".strip()

DELETE_ALL_JOURNEYS = f"DELETE FROM {JOURNEY_HISTORY_TABLE};"
