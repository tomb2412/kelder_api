from __future__ import annotations

from pathlib import Path

from metaflow import FlowSpec, Parameter, step

from src.kelder_api.components.graph_ingestion.service import (
    DEFAULT_GEOJSON_PATH,
    ingest_geojson_map,
    load_geojson,
)
from src.kelder_api.components.neo4j_client import Neo4jClient


class SeaMarksGraphIngestionFlow(FlowSpec):
    """
    Metaflow pipeline that ingests sea marks and coastlines into Neo4j Spatial.

    Stages:
    1) reset + create layers
    2) ingest seamarks and coastlines
    3) create safe edges
    4) project to a GDS graph
    """

    map_path = Parameter(
        "map_path",
        help="Path to GeoJSON seamarks input file",
        default=str(DEFAULT_GEOJSON_PATH),
        type=str,
    )
    neo4j_uri = Parameter(
        "neo4j_uri",
        help="Neo4j bolt URI",
        default="bolt://localhost:7687",
        type=str,
    )
    neo4j_user = Parameter(
        "neo4j_user",
        help="Neo4j username (ignored when auth is disabled)",
        default="neo4j",
        type=str,
    )
    neo4j_password = Parameter(
        "neo4j_password",
        help="Neo4j password (ignored when auth is disabled)",
        default="",
        type=str,
    )
    neo4j_database = Parameter(
        "neo4j_database",
        help="Neo4j database name",
        default="neo4j",
        type=str,
    )
    neo4j_auth_disabled = Parameter(
        "neo4j_auth_disabled",
        help="Disable Neo4j auth (matches docker-compose NEO4J_AUTH=none)",
        default=True,
        type=bool,
    )
    clear_existing = Parameter(
        "clear_existing",
        help="Delete all existing graph nodes before ingestion",
        default=True,
        type=bool,
    )
    max_distance_km = Parameter(
        "max_distance_km",
        help="Maximum distance used for safe-edge creation",
        default=2.0,
        type=float,
    )
    graph_name = Parameter(
        "graph_name",
        help="GDS graph projection name",
        default="solent_graph",
        type=str,
    )

    @step
    def start(self):
        self.resolved_map_path = str(Path(self.map_path).expanduser().resolve())
        payload = load_geojson(self.resolved_map_path)
        self.total_features = len(payload["features"])
        self.next(self.prepare_graph)

    @step
    def prepare_graph(self):
        client = self._client()
        try:
            if self.clear_existing:
                client.delete_all_nodes()
            client.create_layers()
        finally:
            client.close()
        self.next(self.ingest_marks)

    @step
    def ingest_marks(self):
        payload = load_geojson(self.resolved_map_path)
        client = self._client()
        try:
            summary = ingest_geojson_map(payload, client)
        finally:
            client.close()

        self.marks_inserted = summary.marks_inserted
        self.coastlines_inserted = summary.coastlines_inserted
        self.unsupported_mark_types = summary.unsupported_mark_types
        self.next(self.create_edges)

    @step
    def create_edges(self):
        client = self._client()
        try:
            edges = client.create_safe_edges(max_distance_km=self.max_distance_km)
        finally:
            client.close()

        self.safe_edge_count = len(edges)
        self.next(self.project_graph)

    @step
    def project_graph(self):
        client = self._client()
        try:
            client.project_spatial_to_graph(graph_name=self.graph_name)
        finally:
            client.close()
        self.next(self.end)

    @step
    def end(self):
        print(f"GeoJSON source:         {self.resolved_map_path}")
        print(f"Total features:         {self.total_features}")
        print(f"Marks inserted:         {self.marks_inserted}")
        print(f"Coastlines inserted:    {self.coastlines_inserted}")
        print(f"Safe edges created:     {self.safe_edge_count}")
        print(f"Unsupported types:      {self.unsupported_mark_types}")

    def _client(self) -> Neo4jClient:
        return Neo4jClient(
            uri=self.neo4j_uri,
            username=self.neo4j_user,
            password=self.neo4j_password,
            database=self.neo4j_database,
            auth_disabled=self.neo4j_auth_disabled,
        )


if __name__ == "__main__":
    SeaMarksGraphIngestionFlow()
