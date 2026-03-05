import logging
import math
from contextlib import contextmanager
from typing import List

from neo4j import GraphDatabase
from shapely.geometry import shape

from src.kelder_api.components.neo4j_client.queries import (
    ADD_COASTLINE_LAYER,
    ADD_DANGER_LAYERS,
    ADD_NATIVE_LAYER,
    A_STAR_ROUTE_OPTIMISATION_WITH_NAMES,
    CHECK_GRAPH_EXISTS,
    CREATE_CARDINAL_MARK,
    CREATE_COASTLINE,
    CREATE_DANGER_MARK,
    CREATE_GENERAL_MARK,
    CREATE_GRAPH,
    CREATE_HARBOUR,
    CREATE_SAFE_EDGES,
    CREATE_WRECK,
    DELETE_ALL_NODES,
)

logger = logging.getLogger(__name__)

GDS_GRAPH_NAME = "solent_graph"


class Neo4jClient:
    def __init__(self, uri: str, username: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.layers = {
            "solent_marks": ADD_NATIVE_LAYER,
            "danger_zones": ADD_DANGER_LAYERS,
            "coastlines": ADD_COASTLINE_LAYER,
        }
        self._ensure_graph_projection()

    @contextmanager
    def _session(self):
        with self.driver.session() as session:
            try:
                yield session
            except Exception:
                raise

    def close(self):
        self.driver.close()

    # ------------------------------------------------------------------
    # Graph projection
    # ------------------------------------------------------------------

    def _ensure_graph_projection(self) -> None:
        """Project the spatial graph into GDS if it does not already exist."""
        with self._session() as session:
            result = session.run(CHECK_GRAPH_EXISTS, graph_name=GDS_GRAPH_NAME)
            exists = result.single()["exists"]
        if not exists:
            logger.info("GDS graph projection '%s' not found — creating.", GDS_GRAPH_NAME)
            with self._session() as session:
                session.run(CREATE_GRAPH, graph_name=GDS_GRAPH_NAME)
            logger.info("GDS graph projection '%s' created.", GDS_GRAPH_NAME)
        else:
            logger.info("GDS graph projection '%s' already exists.", GDS_GRAPH_NAME)

    def project_spatial_to_graph(self) -> None:
        with self._session() as session:
            session.run(CREATE_GRAPH, graph_name=GDS_GRAPH_NAME)

    # ------------------------------------------------------------------
    # Schema / layer setup
    # ------------------------------------------------------------------

    def create_layers(self) -> None:
        with self._session() as session:
            for layer_name, layer_query in self.layers.items():
                session.run(layer_query, layer_name=layer_name)

    def delete_all_nodes(self) -> None:
        with self._session() as session:
            try:
                session.run(DELETE_ALL_NODES)
            except Exception as e:
                logger.error("Failed to delete nodes: %s", e)

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def injest_special_purpose_mark(self, feature: dict) -> None:
        processed = _process_special_purpose(feature)
        with self._session() as session:
            try:
                session.run(
                    CREATE_GENERAL_MARK,
                    layer_name="solent_marks",
                    name=processed["name"],
                    type=processed["type"],
                    light=processed["light"],
                    coordinates=processed["coordinates"],
                )
            except KeyError as e:
                logger.warning("Missing key ingesting special purpose mark: %s", e)

    def injest_cardinal_mark(self, feature: dict, radius_deg: float = 0.0018) -> None:
        processed = _process_cardinal_marks(feature)
        coords_string = _build_danger_zone_coords(
            coordinates=processed["coordinates"],
            radius_deg=radius_deg,
            cardinal=processed["catagory"],
        )
        with self._session() as session:
            session.run(
                CREATE_CARDINAL_MARK,
                name=processed["name"],
                direction=processed["catagory"].upper(),
                light=processed["light"],
                coordinates=processed["coordinates"],
                danger_zone=coords_string,
                point_layer="solent_marks",
                danger_layer="danger_zones",
            )

    def injest_isolated_danger_mark(
        self, feature: dict, radius_deg: float = 0.0018, segments: int = 16
    ) -> None:
        processed = _process_isolated_danger(feature)
        coords_string = _build_danger_zone_coords(
            coordinates=processed["coordinates"],
            radius_deg=radius_deg,
            segments=segments,
        )
        with self._session() as session:
            try:
                session.run(
                    CREATE_DANGER_MARK,
                    name=processed["name"],
                    coordinates=processed["coordinates"],
                    danger_zone=coords_string,
                    point_layer="solent_marks",
                    danger_layer="danger_zones",
                )
            except KeyError as e:
                logger.warning("Missing key ingesting isolated danger mark: %s", e)

    def injest_lateral_mark(self, feature: dict) -> None:
        processed = _process_lateral_marks(feature)
        with self._session() as session:
            try:
                session.run(
                    CREATE_GENERAL_MARK,
                    layer_name="solent_marks",
                    name=processed["name"],
                    type=processed["type"],
                    light=processed["light"],
                    coordinates=processed["coordinates"],
                )
            except KeyError as e:
                logger.warning("Missing key ingesting lateral mark: %s", e)

    def injest_harbours(self, feature: dict) -> None:
        processed = _process_harbour(feature)
        with self._session() as session:
            try:
                session.run(
                    CREATE_HARBOUR,
                    layer_name="solent_marks",
                    name=processed["name"],
                    coordinates=processed["coordinates"],
                )
            except KeyError as e:
                logger.warning("Missing key ingesting harbour: %s", e)

    def injest_wreck(
        self, feature: dict, radius_deg: float = 0.0018, segments: int = 16
    ) -> None:
        processed = _process_wreck(feature)
        with self._session() as session:
            try:
                session.run(
                    CREATE_WRECK,
                    name=processed["name"],
                    type="WRECK",
                    coordinates=processed["coordinates"],
                    danger_zone=processed["danger_zone"],
                    point_layer="solent_marks",
                    danger_layer="danger_zones",
                )
            except KeyError as e:
                logger.warning("Missing key ingesting wreck: %s", e)

    def injest_coastline(self, feature: dict) -> None:
        processed = _process_coastline(feature)
        with self._session() as session:
            try:
                session.run(
                    CREATE_COASTLINE,
                    name=processed["name"],
                    type=processed["type"],
                    linestring=processed["linestring"],
                    coastline_layer="coastlines",
                )
            except Exception as e:
                logger.error("Failed to ingest coastline: %s", e)
                raise

    def create_safe_edges(self, max_distance_km: float = 2.0) -> list[dict]:
        with self._session() as session:
            try:
                result = session.run(CREATE_SAFE_EDGES, max_distance_km=max_distance_km)
                return result.data()
            except Exception as e:
                logger.error("Failed to create safe edges: %s", e)
                return []

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def a_star_by_name(self, name_from: str, name_to: str) -> list[dict]:
        """Run A* shortest path between two named marks.

        Returns the raw result rows from the GDS query. Each row contains:
          - sourceNodeName, targetNodeName
          - totalCost
          - nodeNames: list of mark names along the route
          - path: list of node property dicts with name, latitude, longitude, etc.
        """
        with self._session() as session:
            result = session.run(
                A_STAR_ROUTE_OPTIMISATION_WITH_NAMES,
                name_from=name_from,
                name_to=name_to,
                gds_graph=GDS_GRAPH_NAME,
            )
            return result.data()


# ------------------------------------------------------------------
# Feature processing helpers
# ------------------------------------------------------------------


def _parse_wkt_coordinates(coordinates: list) -> str:
    coords_string = [f"{lon} {lat}" for lon, lat in coordinates]
    return (
        str(coords_string)
        .replace("[", "")
        .replace("]", "")
        .replace('"', "")
        .replace("'", "")
    )


def _build_danger_zone_coords(
    coordinates: list,
    radius_deg: float = 0.0018,
    segments: int = 32,
    cardinal: str | None = None,
) -> str:
    lon = coordinates[0]
    lat = coordinates[1]

    center_lat = lat
    center_lon = lon

    if cardinal:
        cardinal = cardinal.lower().strip()
        if cardinal == "north":
            center_lat -= radius_deg * 1.05
        elif cardinal == "south":
            center_lat += radius_deg * 1.05
        elif cardinal == "east":
            center_lon -= radius_deg * 1.05
        elif cardinal == "west":
            center_lon += radius_deg * 1.05

    coords: list[list[float]] = []
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = center_lon + radius_deg * math.cos(angle)
        y = center_lat + radius_deg * math.sin(angle)
        coords.append([x, y])
    coords.append(coords[0])

    return _parse_wkt_coordinates(coords)


def _process_special_purpose(feature: dict) -> dict:
    name = feature["properties"].get("seamark:name")
    coordinates = feature["geometry"]["coordinates"]
    try:
        light_characteristic = (
            f"{feature['properties']['seamark:light:character']}"
            f"-{feature['properties']['seamark:light:colour']}"
            f"-group:{feature['properties']['seamark:light:group']}"
            f"-period:{feature['properties']['seamark:light:period']}"
        )
    except KeyError:
        light_characteristic = None
    return {
        "name": name,
        "type": "special_purpose",
        "coordinates": coordinates,
        "light": light_characteristic,
    }


def _process_cardinal_marks(feature: dict) -> dict:
    name = feature["properties"].get("seamark:name")
    coordinates = feature["geometry"]["coordinates"]
    seamark_type = feature["properties"].get("seamark:type", "buoy_cardinal")
    catagory = feature["properties"].get(f"seamark:{seamark_type}:category")
    try:
        light_characteristic = (
            f"{feature['properties']['seamark:light:character']}"
            f"-{feature['properties']['seamark:light:colour']}"
            f"-group:{feature['properties']['seamark:light:group']}"
            f"-period:{feature['properties']['seamark:light:period']}"
        )
    except KeyError:
        light_characteristic = None
    return {
        "name": name,
        "type": "cardinal_mark",
        "coordinates": coordinates,
        "catagory": catagory,
        "light": light_characteristic,
    }


def _process_isolated_danger(feature: dict) -> dict:
    name = feature["properties"].get("seamark:name")
    coordinates = feature["geometry"]["coordinates"]
    return {"name": name, "type": "isolated_danger", "coordinates": coordinates}


def _process_lateral_marks(feature: dict) -> dict:
    name = feature["properties"].get("seamark:name")
    coordinates = feature["geometry"]["coordinates"]
    try:
        catagory = feature["properties"]["seamark:buoy_lateral:category"]
    except KeyError:
        colour = feature["properties"].get("seamark:buoy_lateral:colour", "green")
        catagory = "port" if colour == "red" else "starboard"
    try:
        light_characteristic = (
            f"{feature['properties']['seamark:light:character']}"
            f"-{feature['properties']['seamark:light:colour']}"
            f"-group:{feature['properties']['seamark:light:group']}"
            f"-period:{feature['properties']['seamark:light:period']}"
        )
    except KeyError:
        light_characteristic = None
    return {
        "name": name,
        "type": f"{catagory}_lateral_mark",
        "coordinates": coordinates,
        "light": light_characteristic,
    }


def _process_harbour(feature: dict) -> dict:
    name = feature["properties"].get("name")
    geometry = shape(feature["geometry"])
    centroid = geometry.centroid
    return {
        "name": name,
        "type": feature["properties"].get("seamark:harbour:category"),
        "coordinates": [centroid.x, centroid.y],
    }


def _process_wreck(feature: dict) -> dict:
    name = feature["properties"].get("name")
    geometry = shape(feature["geometry"])
    centroid = geometry.centroid
    lon, lat = centroid.x, centroid.y

    if feature["geometry"]["type"] == "Polygon":
        polygon = _parse_wkt_coordinates(feature["geometry"]["coordinates"][0])
    elif feature["geometry"]["type"] == "LineString":
        polygon = _parse_wkt_coordinates(feature["geometry"]["coordinates"])
    elif feature["geometry"]["type"] == "Point":
        polygon = _build_danger_zone_coords([lon, lat])
    else:
        raise TypeError(f"Unsupported wreck geometry type: {feature['geometry']['type']}")

    return {
        "name": name,
        "coordinates": [lon, lat],
        "danger_zone": polygon,
    }


def _process_coastline(feature: dict) -> dict:
    name = feature["properties"].get("name")
    place_type = feature["properties"].get("place", "mainland")

    if feature["geometry"]["type"] == "Polygon":
        linestring = _parse_wkt_coordinates(feature["geometry"]["coordinates"][0])
    elif feature["geometry"]["type"] == "LineString":
        linestring = _parse_wkt_coordinates(feature["geometry"]["coordinates"])
    else:
        raise TypeError(f"Unsupported coastline geometry: {feature['geometry']['type']}")

    return {"name": name, "type": place_type, "linestring": linestring}
