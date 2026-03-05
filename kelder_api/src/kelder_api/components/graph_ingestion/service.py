from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from src.kelder_api.components.graph_ingestion.neo4j_client import (
        GraphIngestionNeo4jClient,
    )

DEFAULT_GEOJSON_PATH = (
    Path(__file__).resolve().parents[4]
    / "raw_maps"
    / "seamarks_and_coastlines_solent.geojson"
)


@dataclass
class IngestionSummary:
    total_features: int
    marks_inserted: int
    coastlines_inserted: int
    unsupported_mark_types: list[str]


def load_geojson(path: str | Path) -> dict[str, Any]:
    geojson_path = Path(path).expanduser().resolve()
    if not geojson_path.exists():
        raise FileNotFoundError(f"GeoJSON file not found: {geojson_path}")

    with geojson_path.open(encoding="utf-8") as data_file:
        payload = json.load(data_file)

    if not isinstance(payload.get("features"), list):
        raise ValueError("GeoJSON payload must contain a `features` list")

    return payload


def ingest_geojson_map(
    raw_map: dict[str, Any], client: "GraphIngestionNeo4jClient"
) -> IngestionSummary:
    seamark_processors: dict[str, Callable[[dict], None]] = {
        "buoy_special_purpose": client.ingest_special_purpose_mark,
        "beacon_special_purpose": client.ingest_special_purpose_mark,
        "buoy_isolated_danger": client.ingest_isolated_danger_mark,
        "beacon_isolated_danger": client.ingest_isolated_danger_mark,
        "buoy_cardinal": client.ingest_cardinal_mark,
        "beacon_cardinal": client.ingest_cardinal_mark,
        "buoy_lateral": client.ingest_lateral_mark,
        "beacon_lateral": client.ingest_lateral_mark,
        "harbour": client.ingest_harbours,
        "wreck": client.ingest_wreck,
    }

    features = raw_map["features"]
    mark_count = 0
    coastline_count = 0
    unsupported_types: list[str] = []

    for feature in features:
        properties = feature.get("properties", {})

        seamark_type = properties.get("seamark:type")
        if seamark_type:
            processor = seamark_processors.get(seamark_type)
            if processor is None:
                if seamark_type not in unsupported_types:
                    unsupported_types.append(seamark_type)
            else:
                processor(feature)
                mark_count += 1

        if properties.get("natural") == "coastline":
            client.ingest_coastline(feature)
            coastline_count += 1

    return IngestionSummary(
        total_features=len(features),
        marks_inserted=mark_count,
        coastlines_inserted=coastline_count,
        unsupported_mark_types=unsupported_types,
    )
