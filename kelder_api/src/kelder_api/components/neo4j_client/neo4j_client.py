from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

from neo4j import GraphDatabase
from neo4j.exceptions import ClientError

from src.kelder_api.components.neo4j_client.feature_processing import (
    build_danger_zone_coords,
    process_cardinal_mark,
    process_coastline,
    process_harbour,
    process_isolated_danger,
    process_lateral_mark,
    process_special_purpose,
    process_wreck,
)
from src.kelder_api.components.neo4j_client.queries import (
    ADD_COASTLINE_LAYER,
    ADD_DANGER_LAYER,
    ADD_NATIVE_LAYER,
    A_STAR_ROUTE_OPTIMISATION_WITH_NAMES,
    CHECK_GRAPH_EXISTS,
    CREATE_COASTLINE,
    CREATE_DANGER_MARK,
    CREATE_GENERAL_MARK,
    CREATE_GRAPH,
    CREATE_HARBOUR,
    CREATE_SAFE_EDGES,
    DELETE_ALL_NODES,
    DROP_GRAPH_IF_EXISTS,
)

logger = logging.getLogger(__name__)

GDS_GRAPH_NAME = "solent_graph"


class Neo4jClient:
    def __init__(
        self,
        uri: str,
        username: str = "neo4j",
        password: str = "",
        database: str = "neo4j",
        auth_disabled: bool = True,
    ) -> None:
        auth = None if auth_disabled else (username, password)
        self.driver = GraphDatabase.driver(uri, auth=auth)
        self.database = database
        self.layers: dict[str, str] = {
            "solent_marks": ADD_NATIVE_LAYER,
            "danger_zones": ADD_DANGER_LAYER,
            "coastlines": ADD_COASTLINE_LAYER,
        }
        self._ensure_graph_projection()

    @contextmanager
    def _session(self) -> Generator[Any, None, None]:
        with self.driver.session(database=self.database) as session:
            yield session

    def close(self) -> None:
        self.driver.close()

    # ------------------------------------------------------------------
    # Schema / layer setup
    # ------------------------------------------------------------------

    def create_layers(self) -> None:
        with self._session() as session:
            for layer_name, query in self.layers.items():
                try:
                    session.run(query, layer_name=layer_name)
                except ClientError as error:
                    if "already exists" not in str(error).lower():
                        raise

    def delete_all_nodes(self) -> None:
        with self._session() as session:
            session.run(DELETE_ALL_NODES)

    # ------------------------------------------------------------------
    # Graph projection
    # ------------------------------------------------------------------

    def _ensure_graph_projection(self) -> None:
        """Check whether the GDS projection exists and create it if not.

        Called automatically on construction so the API is routing-ready
        without a manual setup step.
        """
        try:
            with self._session() as session:
                result = session.run(CHECK_GRAPH_EXISTS, graph_name=GDS_GRAPH_NAME)
                exists = result.single()["exists"]
            if not exists:
                logger.info(
                    "GDS graph projection '%s' not found — creating.", GDS_GRAPH_NAME
                )
                with self._session() as session:
                    session.run(CREATE_GRAPH, graph_name=GDS_GRAPH_NAME)
                logger.info("GDS graph projection '%s' created.", GDS_GRAPH_NAME)
            else:
                logger.info(
                    "GDS graph projection '%s' already exists.", GDS_GRAPH_NAME
                )
        except Exception as e:
            logger.warning(
                "Could not ensure GDS projection (graph may be empty): %s", e
            )

    def project_spatial_to_graph(self, graph_name: str = GDS_GRAPH_NAME) -> None:
        """Drop any existing GDS projection and recreate it.

        Used by the ingestion pipeline after edges have been created.
        """
        with self._session() as session:
            session.run(DROP_GRAPH_IF_EXISTS, graph_name=graph_name)
            session.run(CREATE_GRAPH, graph_name=graph_name)
        logger.info("GDS graph projection '%s' (re)created.", graph_name)

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest_special_purpose_mark(self, feature: dict) -> None:
        mark = process_special_purpose(feature)
        with self._session() as session:
            session.run(
                CREATE_GENERAL_MARK,
                layer_name="solent_marks",
                name=mark["name"],
                type=mark["type"],
                light=mark["light"],
                coordinates=mark["coordinates"],
            )

    def ingest_lateral_mark(self, feature: dict) -> None:
        mark = process_lateral_mark(feature)
        with self._session() as session:
            session.run(
                CREATE_GENERAL_MARK,
                layer_name="solent_marks",
                name=mark["name"],
                type=mark["type"],
                light=mark["light"],
                coordinates=mark["coordinates"],
            )

    def ingest_cardinal_mark(self, feature: dict, radius_deg: float = 0.0018) -> None:
        mark = process_cardinal_mark(feature)
        danger_zone = build_danger_zone_coords(
            coordinates=mark["coordinates"],
            radius_deg=radius_deg,
            cardinal=mark["category"],
        )
        with self._session() as session:
            session.run(
                CREATE_DANGER_MARK,
                point_layer="solent_marks",
                danger_layer="danger_zones",
                name=mark["name"],
                type=mark["type"],
                light=mark["light"],
                coordinates=mark["coordinates"],
                danger_zone=danger_zone,
            )

    def ingest_isolated_danger_mark(
        self, feature: dict, radius_deg: float = 0.0018, segments: int = 16
    ) -> None:
        mark = process_isolated_danger(feature)
        danger_zone = build_danger_zone_coords(
            coordinates=mark["coordinates"],
            radius_deg=radius_deg,
            segments=segments,
        )
        with self._session() as session:
            session.run(
                CREATE_DANGER_MARK,
                point_layer="solent_marks",
                danger_layer="danger_zones",
                name=mark["name"],
                type=mark["type"],
                light=mark["light"],
                coordinates=mark["coordinates"],
                danger_zone=danger_zone,
            )

    def ingest_harbours(self, feature: dict) -> None:
        harbour = process_harbour(feature)
        with self._session() as session:
            session.run(
                CREATE_HARBOUR,
                layer_name="solent_marks",
                name=harbour["name"],
                category=harbour["category"],
                coordinates=harbour["coordinates"],
            )

    def ingest_wreck(self, feature: dict) -> None:
        wreck = process_wreck(feature)
        with self._session() as session:
            session.run(
                CREATE_DANGER_MARK,
                point_layer="solent_marks",
                danger_layer="danger_zones",
                name=wreck["name"],
                type=wreck["type"],
                light=None,
                coordinates=wreck["coordinates"],
                danger_zone=wreck["danger_zone"],
            )

    def ingest_coastline(self, feature: dict) -> None:
        coastline = process_coastline(feature)
        with self._session() as session:
            session.run(
                CREATE_COASTLINE,
                coastline_layer="coastlines",
                name=coastline["name"],
                type=coastline["type"],
                linestring=coastline["linestring"],
            )

    def create_safe_edges(self, max_distance_km: float = 2.0) -> list[dict]:
        with self._session() as session:
            result = session.run(
                CREATE_SAFE_EDGES,
                point_layer="solent_marks",
                danger_layer="danger_zones",
                coastline_layer="coastlines",
                max_distance_km=max_distance_km,
            )
            return result.data()

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def a_star_by_name(self, name_from: str, name_to: str) -> list[dict]:
        """Run A* shortest path between two named marks.

        Returns result rows each containing sourceNodeName, targetNodeName,
        totalCost, nodeNames, and path (list of node property dicts).
        """
        with self._session() as session:
            result = session.run(
                A_STAR_ROUTE_OPTIMISATION_WITH_NAMES,
                name_from=name_from,
                name_to=name_to,
                gds_graph=GDS_GRAPH_NAME,
            )
            return result.data()
