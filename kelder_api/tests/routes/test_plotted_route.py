from __future__ import annotations

import json

import pytest

from src.kelder_api.components.db_manager.service import DBManager

ROUTE = [
    {
        "name": "Hamble Point",
        "latitude": 50.84,
        "latitude_hemisphere": "N",
        "longitude": 1.31,
        "longitude_hemisphere": "W",
    },
    {
        "name": None,
        "latitude": 50.80,
        "latitude_hemisphere": "N",
        "longitude": 1.29,
        "longitude_hemisphere": "W",
    },
]


@pytest.fixture()
def plotting_client(app_client, tmp_path):
    client, app = app_client
    app.state.db_manager = DBManager(tmp_path / "plans.db")
    app.state.redis_client.named_sets["PASSAGE_PLAN"] = []
    return client, app


def test_plotted_route_replaces_active_plan(plotting_client):
    client, app = plotting_client

    response = client.post("/passage_plan/waypoints", json={"course_to_steer": ROUTE})

    assert response.status_code == 200
    body = response.json()
    plan = body["passage_plan"]
    assert plan["departure_place_name"] == "Hamble Point"
    assert plan["desination_place_name"] == "Waypoint 2"
    assert [wp["name"] for wp in plan["course_to_steer"]] == [
        "Hamble Point",
        "Waypoint 2",
    ]
    # Western longitudes are stored signed so bearings are not mirrored.
    assert [wp["longitude"] for wp in plan["course_to_steer"]] == [-1.31, -1.29]
    assert len(plan["distance_between_waypoints"]) == 1
    assert 150 < plan["bearing_between_waypoints"][0] < 170

    active = app.state.redis_client.named_sets["PASSAGE_PLAN"][-1]
    assert json.loads(active.model_dump_json())["course_to_steer"][0]["longitude"] == (
        -1.31
    )
    stored = app.state.db_manager.fetch_passage_plan(body["plan_id"])
    assert stored.passage_plan.course_to_steer[1].longitude == -1.29


@pytest.mark.parametrize(
    "route, detail",
    [
        (ROUTE[:1], "A route needs at least two waypoints."),
        (
            [ROUTE[0], {**ROUTE[1], "longitude_hemisphere": "X"}],
            "Waypoint 2 has an invalid hemisphere.",
        ),
        (
            [{**ROUTE[0], "latitude": 95.0}, ROUTE[1]],
            "Waypoint 1 is outside valid latitude/longitude range.",
        ),
    ],
)
def test_invalid_routes_return_readable_detail(plotting_client, route, detail):
    client, app = plotting_client

    response = client.post("/passage_plan/waypoints", json={"course_to_steer": route})

    assert response.status_code == 400
    assert response.json() == {"detail": detail}
    assert app.state.redis_client.named_sets["PASSAGE_PLAN"] == []
    assert app.state.db_manager.list_passage_plans() == []
