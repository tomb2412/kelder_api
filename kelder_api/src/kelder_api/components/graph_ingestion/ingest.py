"""CLI script to ingest a GeoJSON seamarks file into Neo4j.

Usage
-----
    uv run python -m src.kelder_api.components.graph_ingestion.ingest \\
        --map-path /path/to/seamarks.geojson

    uv run python -m src.kelder_api.components.graph_ingestion.ingest \\
        --map-path /path/to/seamarks.geojson \\
        --neo4j-uri bolt://localhost:7687 \\
        --no-clear-existing \\
        --max-distance-km 2.0
"""

from __future__ import annotations

import argparse
import sys
import time

from src.kelder_api.components.graph_ingestion.service import (
    DEFAULT_GEOJSON_PATH,
    ingest_geojson_map,
    load_geojson,
)
from src.kelder_api.components.neo4j_client import Neo4jClient


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest GeoJSON sea marks into Neo4j Spatial and build a GDS graph."
    )
    parser.add_argument(
        "--map-path",
        default=str(DEFAULT_GEOJSON_PATH),
        help="Path to the GeoJSON seamarks file (default: raw_maps/seamarks_and_coastlines_solent.geojson)",
    )
    parser.add_argument(
        "--neo4j-uri",
        default="bolt://localhost:7687",
        help="Neo4j bolt URI (default: bolt://localhost:7687)",
    )
    parser.add_argument(
        "--neo4j-user",
        default="neo4j",
        help="Neo4j username (ignored when auth is disabled)",
    )
    parser.add_argument(
        "--neo4j-password",
        default="",
        help="Neo4j password (ignored when auth is disabled)",
    )
    parser.add_argument(
        "--neo4j-database",
        default="neo4j",
        help="Neo4j database name (default: neo4j)",
    )
    parser.add_argument(
        "--auth-disabled",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Disable Neo4j authentication (default: true, matching NEO4J_AUTH=none)",
    )
    parser.add_argument(
        "--clear-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Delete all existing nodes before ingestion (default: true)",
    )
    parser.add_argument(
        "--max-distance-km",
        type=float,
        default=2.0,
        help="Maximum distance in km for safe-edge creation (default: 2.0)",
    )
    parser.add_argument(
        "--graph-name",
        default="solent_graph",
        help="GDS graph projection name (default: solent_graph)",
    )
    return parser.parse_args()


def run(args: argparse.Namespace) -> None:
    print(f"Loading GeoJSON from: {args.map_path}")
    raw_map = load_geojson(args.map_path)
    total = len(raw_map["features"])
    print(f"Loaded {total} features.")

    print(f"Connecting to Neo4j at {args.neo4j_uri} ...")
    client = Neo4jClient(
        uri=args.neo4j_uri,
        username=args.neo4j_user,
        password=args.neo4j_password,
        database=args.neo4j_database,
        auth_disabled=args.auth_disabled,
    )

    try:
        if args.clear_existing:
            print("Clearing existing nodes ...")
            client.delete_all_nodes()

        print("Creating spatial layers ...")
        client.create_layers()

        print("Ingesting marks and coastlines ...")
        summary = ingest_geojson_map(raw_map, client)
        print(f"  Marks inserted:      {summary.marks_inserted}")
        print(f"  Coastlines inserted: {summary.coastlines_inserted}")
        if summary.unsupported_mark_types:
            print(f"  Unsupported types:   {summary.unsupported_mark_types}")

        print(f"Creating safe edges (max {args.max_distance_km} km) ...")
        t0 = time.time()
        edges = client.create_safe_edges(max_distance_km=args.max_distance_km)
        print(f"  Safe edges created:  {len(edges)}  ({time.time() - t0:.1f}s)")

        print(f"Projecting GDS graph '{args.graph_name}' ...")
        client.project_spatial_to_graph(graph_name=args.graph_name)
        print("Done.")

    finally:
        client.close()


def main() -> None:
    args = _parse_args()
    try:
        run(args)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
