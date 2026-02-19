from typing import List

from neo4j import GraphDatabase
from contextlib import contextmanager

from tests.notebooks.graph_ingestion.queries import (
    ADD_NATIVE_LAYER,
    ADD_DANGER_LAYERS,
    ADD_COASTLINE_LAYER,
    CREATE_COASTLINE,
    CREATE_GENERAL_MARK,
    CREATE_DANGER_MARK,
    CREATE_CARDNAL_MARK,
    CREATE_GENERAL_MARK_BATCH,
    DELETE_ALL_NODES,
    CREATE_SAFE_EDGES,
    CREATE_HARBOUR,
    CREATE_WRECK
)
from tests.notebooks.graph_ingestion.utils import (
    process_special_purpose,
    process_isolated_danger,
    process_cardinal_marks,
    build_danger_zone_coords,
    process_coastline,
    process_lateral_marks,
    process_harbour,
    process_wreck,
)

class Neo4jClient():
    def __init__(self):
        self.driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "neo4j"))
        self.layers = {
            "solent_marks": ADD_NATIVE_LAYER,
            "danger_zones": ADD_DANGER_LAYERS,
            "coastlines": ADD_COASTLINE_LAYER,
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

    def injest_cardinal_mark(
        self,
        feature: dict,
        radius_deg: float = 0.0018,
    ):
        processed_features = process_cardinal_marks(feature, "buoy_cardinal")
        coords_string = build_danger_zone_coords(
            coordinates=processed_features["coordinates"],
            radius_deg=radius_deg,
            cardinal=processed_features["catagory"]
        )

        with self.create_session() as session:
            result = session.run(
                CREATE_CARDNAL_MARK,
                name=processed_features["name"],
                direction=processed_features["catagory"].upper(),
                light=processed_features['light'],
                coordinates=processed_features["coordinates"],
                danger_zone=coords_string,
                point_layer='solent_marks',
                danger_layer='danger_zones'
            )
        
    def injest_isolated_danger_mark(
        self,
        feature: dict,
        radius_deg: float = 0.0018,
        segments: int = 16,
    ):
        processed_features = process_isolated_danger(feature)
        coords_string = build_danger_zone_coords(
            coordinates=processed_features["coordinates"],
            radius_deg=radius_deg,
            segments=segments,
        )

        with self.create_session() as session:
            try:
                result = session.run(
                    CREATE_DANGER_MARK,
                    name=processed_features["name"],
                    coordinates=processed_features["coordinates"],
                    danger_zone=coords_string,
                    point_layer='solent_marks',
                    danger_layer='danger_zones'
                )
            except KeyError as e:
                print(e)
            

    def injest_special_purpose_mark(self, feature: dict):
        processed_features = process_special_purpose(feature)

        with self.create_session() as session:
            try:
                result = session.run(
                    CREATE_GENERAL_MARK,
                    layer_name='solent_marks',
                    name = processed_features["name"],
                    type = processed_features["type"],
                    light = processed_features["light"],
                    coordinates = processed_features["coordinates"]
                )
                added = result.single()
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
                    max_distance_km = 2,
                )
                return result.data()
            except Exception as e:
                print(e)

    def injest_coastline(self, feature: dict):
        processed_features = process_coastline(feature)
        with self.create_session() as session:
            try:
                result = session.run(
                    CREATE_COASTLINE,
                    name = processed_features["name"],
                    type = processed_features["type"],
                    linestring = processed_features["linestring"],
                    coastline_layer = "coastlines",
                )
                assert result.data()
            except Exception as e:
                print(e)
                raise

    def injest_lateral_mark(self, feature: dict):
        processed_features = process_lateral_marks(feature)

        with self.create_session() as session:
            try:
                result = session.run(
                    CREATE_GENERAL_MARK,
                    layer_name='solent_marks',
                    name = processed_features["name"],
                    type = processed_features["type"],
                    light = processed_features["light"],
                    coordinates = processed_features["coordinates"]
                )
                added = result.data()
            except KeyError as e:
                print(e)

    def injest_harbours(self, feature: dict):
        processed_features = process_harbour(feature)

        with self.create_session() as session:
            try:
                result = session.run(
                    CREATE_HARBOUR,
                    layer_name='solent_marks',
                    name = processed_features["name"],
                    coordinates = processed_features["coordinates"]
                )
                added = result.data()
            except KeyError as e:
                print(e)

    def injest_wreck(
        self,
        feature: dict,
        radius_deg: float = 0.0018,
        segments: int = 16,
    ):
        processed_features = process_wreck(feature)
        with self.create_session() as session:
            try:
                result = session.run(
                    CREATE_WRECK,
                    name=processed_features["name"],
                    type="WRECK",
                    coordinates=processed_features["coordinates"],
                    danger_zone=processed_features["danger_zone"],
                    point_layer='solent_marks',
                    danger_layer='danger_zones'
                )
            except KeyError as e:
                print(e)
    
            