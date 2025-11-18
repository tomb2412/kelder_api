import json
import logging
from typing import Any, List

from rtree import index

from src.kelder_api.components.agentic_workflow.models import (
    Node,
    ReasoningEndNodes,
    State,
)

logger = logging.getLogger(__name__)


def clean_user_message(new_messages, users_message):
    # Preserve original messages while filtering out any None entries.
    return [msg for msg in new_messages if msg is not None]


def find_models(models: List[Node], node_type: ReasoningEndNodes):
    """Simple method to search the state workflow and return the node"""
    return [m for m in models if getattr(m, "node_type") == node_type]


async def notify_progress(state: State, node_name: str):
    callback = state.progress_callback
    if callback is None:
        return
    await callback(node_name)


def load_map(map_path: str) -> list[dict[str, Any]]:
    """Load seamark metadata from disk."""
    try:
        with map.open() as marks_file:
            return json.load(marks_file)
    except FileNotFoundError:
        logger.warning("Marks file %s was not found", map)
        raise
    except json.JSONDecodeError:
        logger.exception("Marks file %s contains invalid JSON", map)


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
