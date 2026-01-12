import math

from typing import List

from neo4j import GraphDatabase
from contextlib import contextmanager

from tests.notebooks.graph_ingestion.queries import (
    CREATE_GENERAL_MARK_BATCH,
    CREATE_DANGER_MARK,
    DELETE_ALL_NODES
)

class Neo4jClient():
    def __init__(self):
        self.driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "neo4j"))

    @contextmanager
    def create_sesson(self):
        with self.driver.session() as session:
            try:
                yield session
            except Exception as error:
                raise error
            finally:
                self.driver.close

    def create_general_mark(self, marks: List[dict], layer_name: str = "solent_generic_spatial_layer"):
        with self.create_sesson() as session:
            result = session.run(
                CREATE_GENERAL_MARK_BATCH,
                layer_name=layer_name,
                mark=marks,
            )
            added = result.single()["count"]
        
    def create_danger_mark(
        self,
        mark: List[dict],
        radius_deg: float = 0.0018,
        segments: int = 16,
        layer_name: str = "solent_generic_spatial_layer"
    ):
        """
        Generate a ring geometry around a point for Neo4j Spatial.

        :param mark: cleaned dict with mark properties name and coordinates.
        :param radius_deg: Radius in degrees (hardcoded approximation)
        :param segments: Number of segments in the ring
        :return: GeoJSON geometry dict
        """

        coords = []

        for i in range(segments):
            # RELIES ON FORMATE LAT,LON - IN THAT SPECIFIC ORDER!
            angle = 2 * math.pi * i / segments
            x = mark["coordinates"][1] + radius_deg * math.cos(angle)
            y = mark["coordinates"][0] + radius_deg * math.sin(angle)
            coords.append([x, y])

        # Close the ring
        coords.append(coords[0])

        ring_geometry = {
            "type": "LineString",
            "coordinates": coords
        }

        with self.create_session() as session:
            result = session.run(
                CREATE_DANGER_MARK,
                name=mark["name"],
                coordinates=mark["coordinates"],
                danger_zone=ring_geometry,
                layer_name=layer_name
            )
            added = result.single()["count"]
