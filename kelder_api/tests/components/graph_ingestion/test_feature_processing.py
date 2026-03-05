from src.kelder_api.components.graph_ingestion.feature_processing import process_wreck


def test_process_wreck_point_keeps_lon_lat_order():
    feature = {
        "type": "Feature",
        "properties": {"name": "wreck-1"},
        "geometry": {"type": "Point", "coordinates": [-1.1, 50.8]},
    }

    result = process_wreck(feature)

    assert result["coordinates"] == [-1.1, 50.8]
    assert result["type"] == "WRECK"
    assert isinstance(result["danger_zone"], str)
    assert len(result["danger_zone"]) > 0
