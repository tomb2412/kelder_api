import math

from typing import List

from neo4j import GraphDatabase
from contextlib import contextmanager

from tests.notebooks.graph_ingestion.queries import (
    ADD_NATIVE_LAYER,
    ADD_DANGER_LAYERS,
    CREATE_SPECIAL_PURPOSE_MARK,
    CREATE_DANGER_MARK,
    CREATE_GENERAL_MARK_BATCH,
    DELETE_ALL_NODES,
    CREATE_SAFE_EDGES
)
from tests.notebooks.graph_ingestion.utils import (
    process_special_purpose,
    process_isolated_danger
)

class Neo4jClient():
    def __init__(self):
        self.driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "neo4j"))
        self.layers = {
            "solent_marks": ADD_NATIVE_LAYER,
            "danger_zones": ADD_DANGER_LAYERS,
        }

    @contextmanager
    def create_session(self):
        with self.driver.session() as session:
            try:
                yield session
            except Exception as error:
                raise error
            finally:
                self.driver.close
    
    def create_layers(self, name = None):
        with self.create_session() as session:
            for layer_name, layer_query in self.layers.items():
                result = session.run(
                    layer_query,
                    layer_name = layer_name
                )

    def create_general_mark(self, marks: List[dict], layer_name: str = "solent_makrs"):
        with self.create_session() as session:
            result = session.run(
                CREATE_GENERAL_MARK_BATCH,
                layer_name=layer_name,
                mark=marks,
            )
            added = result.single()["count"]
        
    def create_danger_mark(
        self,
        mark: dict,
        radius_deg: float = 0.0018,
        segments: int = 16,
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

        coords_string = [f"{lon} {lat}" for lat, lon in coords]
        coords_string = str(coords_string).replace(
            "[","").replace(
            "]","").replace(
            "\"", "").replace(
            "\'","")
        
        print(coords_string)
        print(mark["coordinates"])

        with self.create_session() as session:
            result = session.run(
                CREATE_DANGER_MARK,
                name=mark["name"],
                coordinates=mark["coordinates"],
                danger_zone=coords_string,
                point_layer='solent_marks',
                danger_layer='danger_zones'
            )
            

    def injest_special_purpose_mark(self, feature: dict):
        processed_features = process_special_purpose(feature)

        with self.create_session() as session:
            try:
                result = session.run(
                    CREATE_SPECIAL_PURPOSE_MARK,
                    layer_name='solent_marks',
                    name = processed_features["name"],
                    type = processed_features["type"],
                    light = processed_features["light"],
                    coordinates = processed_features["coordinates"]
                )
                added = result.single()
            except KeyError as e:
                print(e)

    def injest_isolated_danger_mark(self, feature: dict):
        processed_features = process_isolated_danger(feature)
        try: 
            self.create_danger_mark(processed_features)
        except KeyError as e:
            print(e)

    def delete_all_nodes(self):
        with self.create_session() as session:
            try:
                result = session.run(
                    DELETE_ALL_NODES
                )
            except Exception as e:
                print(e)
    
    def create_safe_edges(self):
        with self.create_session() as session:
            try:
                result = session.run(
                    CREATE_SAFE_EDGES,
                    max_distance_km = 1,
                )
                return result.single()
            except Exception as e:
                print(e)
