from src.kelder_api.components.graph_ingestion.service import ingest_geojson_map


class _DummyClient:
    def __init__(self) -> None:
        self.calls = {
            "ingest_special_purpose_mark": 0,
            "ingest_isolated_danger_mark": 0,
            "ingest_cardinal_mark": 0,
            "ingest_lateral_mark": 0,
            "ingest_harbours": 0,
            "ingest_wreck": 0,
            "ingest_coastline": 0,
        }

    def ingest_special_purpose_mark(self, feature: dict) -> None:
        self.calls["ingest_special_purpose_mark"] += 1

    def ingest_isolated_danger_mark(self, feature: dict) -> None:
        self.calls["ingest_isolated_danger_mark"] += 1

    def ingest_cardinal_mark(self, feature: dict) -> None:
        self.calls["ingest_cardinal_mark"] += 1

    def ingest_lateral_mark(self, feature: dict) -> None:
        self.calls["ingest_lateral_mark"] += 1

    def ingest_harbours(self, feature: dict) -> None:
        self.calls["ingest_harbours"] += 1

    def ingest_wreck(self, feature: dict) -> None:
        self.calls["ingest_wreck"] += 1

    def ingest_coastline(self, feature: dict) -> None:
        self.calls["ingest_coastline"] += 1


def test_ingest_geojson_map_routes_expected_mark_types():
    raw_map = {
        "type": "FeatureCollection",
        "features": [
            {"properties": {"seamark:type": "buoy_special_purpose"}},
            {"properties": {"seamark:type": "beacon_isolated_danger"}},
            {"properties": {"seamark:type": "buoy_cardinal"}},
            {"properties": {"seamark:type": "beacon_lateral"}},
            {"properties": {"seamark:type": "harbour"}},
            {"properties": {"seamark:type": "wreck"}},
            {"properties": {"seamark:type": "rock"}},
            {"properties": {"natural": "coastline"}},
            {"properties": {"seamark:type": "rock"}},
        ],
    }
    client = _DummyClient()

    summary = ingest_geojson_map(raw_map=raw_map, client=client)

    assert summary.total_features == 9
    assert summary.marks_inserted == 6
    assert summary.coastlines_inserted == 1
    assert summary.unsupported_mark_types == ["rock"]
    assert client.calls["ingest_special_purpose_mark"] == 1
    assert client.calls["ingest_isolated_danger_mark"] == 1
    assert client.calls["ingest_cardinal_mark"] == 1
    assert client.calls["ingest_lateral_mark"] == 1
    assert client.calls["ingest_harbours"] == 1
    assert client.calls["ingest_wreck"] == 1
    assert client.calls["ingest_coastline"] == 1
