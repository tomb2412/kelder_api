import json
from pathlib import Path
from typing import Any

from rtree import index

from src.kelder_api.configuration.logging_controller import get_logger

logger = get_logger(__name__, "agent_workflow")


def load_map(map_path: Path) -> list[dict[str, Any]]:
    """Load seamark metadata from disk."""
    try:
        with map_path.open() as marks_file:
            return json.load(marks_file)
    except FileNotFoundError:
        logger.warning("Map file %s was not found", map_path)
        return []
    except json.JSONDecodeError:
        logger.exception("Map file %s contains invalid JSON", map_path)
        return []


def build_marks_index(marks: list[dict[str, Any]]):
    """Create an R-tree index for quick nearest lookups."""
    if not marks:
        return None

    idx = index.Index()
    inserted = 0

    for idx_counter, mark in enumerate(marks):
        coordinates = mark.get("coordinates")
        if not isinstance(coordinates, (list, tuple)) or len(coordinates) != 2:
            continue

        try:
            longitude = float(coordinates[0])
            latitude = float(coordinates[1])
        except (TypeError, ValueError):
            continue

        bounds = (longitude, latitude, longitude, latitude)
        idx.insert(idx_counter, bounds, obj=mark)
        inserted += 1

    if inserted == 0:
        return None
    return idx
