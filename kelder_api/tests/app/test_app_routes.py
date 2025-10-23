from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict

import pytest


@dataclass(frozen=True)
class RouteExpectation:
    method: str
    path: str
    expected_status: int
    expected_json: Any = None
    request_params: Dict[str, Any] | None = None
    request_json: Dict[str, Any] | None = None
    setup: Callable[[Any], None] | None = None
    is_stream: bool = False
    validator: Callable[[Any], None] | None = None


def _reset_redis_sets(app) -> None:
    sample_record = {
        "timestamp": "2024-01-01T12:00:00Z",
        "status": "A",
        "latitude_nmea": "5123.46",
        "longitude_nmea": "00123.99",
        "active_prn": [],
        "hdop": "",
        "satellites_in_view": {},
    }
    payload = json.dumps(sample_record)
    client = app.state.redis_client
    client.sorted_sets["sensor:ts:GPS"] = [(payload, 1.0)]
    client.named_sets["GPS"] = [sample_record]
    client.named_sets.setdefault("PASSAGE_PLAN", [{"summary": "Sample passage"}])


def _assert_journey(body: Any) -> None:
    assert body["start_latitude"] == "5123.46"
    assert body["end_longitude"] == "00124.01"


def _assert_tidal_predictions(body: Any) -> None:
    assert isinstance(body, list)
    assert body, "Expected at least one tidal prediction"
    first = body[0]
    assert "event" in first and "datetime_stamp" in first


def _assert_next_tidal_event(body: Any) -> None:
    assert isinstance(body, dict)
    # TODO: Once decided what the endpoint will return
    # assert body.get("event") == "High Water"
    # assert "datetime_stamp" in body


def _assert_tidal_height(body: Any) -> None:
    assert isinstance(body, dict)
    key = "height_of_tide" if "height_of_tide" in body else "height"
    assert key in body
    assert isinstance(body[key], (int, float))
    assert body[key] > 0


def _assert_velocity(body: Any) -> None:
    assert pytest.approx(body["speed_over_ground"]) == 7.2
    assert pytest.approx(body["course_over_ground"]) == 182.0
    assert isinstance(body.get("number_of_measurements"), int)
    assert "timestamp" in body


def _assert_compass(body: Any) -> None:
    assert isinstance(body, list)
    assert body
    assert round(body[0]["heading"]) == 123


class AppRoute(Enum):
    HEALTH = RouteExpectation("GET", "/health_check", 200, {"health": "True"})
    GPS_LATEST = RouteExpectation(
        "GET",
        "/gps_coords_latest",
        200,
        {
            "timestamp": "2024-01-01T12:00:00Z",
            "status": "A",
            "latitude_nmea": "5123.46",
            "longitude_nmea": "00123.99",
            "active_prn": [],
            "hdop": "",
            "satellites_in_view": {},
        },
    )
    GPS_LATEST_FAILURE = RouteExpectation(
        "GET",
        "/gps_coords_latest",
        500,
        setup=lambda app: setattr(app.state.gps_interface, "raise_latest", True),
    )
    GPS_LENGTH = RouteExpectation(
        "GET",
        "/gps_coords_length",
        200,
        expected_json=[
            {
                "timestamp": "2024-01-01T12:00:00Z",
                "status": "A",
                "latitude_nmea": "5123.46",
                "longitude_nmea": "00123.99",
                "active_prn": [],
                "hdop": "",
                "satellites_in_view": {},
            }
        ],
        request_params={"length": 1},
    )
    GPS_CARD = RouteExpectation(
        "GET",
        "/gps_card_data",
        200,
        {
            "timestamp": "12:00:00",
            "latitude": "5123.46",
            "longitude": "00123.99",
            "speed_over_ground": 7.2,
            "log": 12.5,
            "drift": 1.2,
            "dtw": 4.7,
        },
    )
    COMPASS_HEADING = RouteExpectation(
        "GET",
        "/compass_heading",
        200,
        validator=_assert_compass,
    )
    VELOCITY = RouteExpectation(
        "GET",
        "/velocity",
        200,
        validator=_assert_velocity,
    )
    PASSAGE_PLAN = RouteExpectation(
        "GET",
        "/passage_plan",
        200,
        {"passage_plan": {"summary": "Sample passage"}},
    )
    JOURNEY = RouteExpectation(
        "GET",
        "/get_journey",
        200,
        validator=_assert_journey,
    )
    REDIS_SET_SIZE = RouteExpectation(
        "GET",
        "/get_redis_set_size",
        200,
        {"GPS": 1, "list_length": 1},
        request_params={"sensor": "GPS"},
        setup=_reset_redis_sets,
    )
    REDIS_CLEAR = RouteExpectation(
        "GET",
        "/clear_redis_set",
        200,
        {"status": "cleared"},
        request_params={"sensor": "GPS"},
        setup=_reset_redis_sets,
    )
    TIDAL_HEIGHT = RouteExpectation(
        "GET",
        "/get_height_of_tide",
        200,
        validator=_assert_tidal_height,
    )
    TIDAL_PREDICTIONS = RouteExpectation(
        "GET",
        "/get_tidal_predictions",
        200,
        validator=_assert_tidal_predictions,
    )
    TIDAL_NEXT_EVENT = RouteExpectation(
        "GET",
        "/get_next_tidal_event",
        200,
        validator=_assert_next_tidal_event,
    )
    CHAT_STREAM = RouteExpectation(
        "POST",
        "/chat_stream",
        200,
        request_json={"message": "Hi"},
        is_stream=True,
    )


def test_app_initialisation_sets_state(app_client):
    _, app = app_client
    from tests.conftest import (
        DummyCompassInterface,
        DummyGPSInterface,
        DummyLogTracker,
        DummyRedisClient,
        DummyVelocityCalculator,
    )

    assert isinstance(app.state.redis_client, DummyRedisClient)
    assert isinstance(app.state.gps_interface, DummyGPSInterface)
    assert isinstance(app.state.compass_interface, DummyCompassInterface)
    assert isinstance(app.state.velocity_calculator, DummyVelocityCalculator)
    assert isinstance(app.state.log_tracker, DummyLogTracker)


@pytest.mark.parametrize("route", list(AppRoute))
def test_routes_behave_as_expected(app_client, route: AppRoute):
    client, app = app_client
    expectation = route.value

    if expectation.setup:
        expectation.setup(app)

    request_kwargs: Dict[str, Any] = {}
    if expectation.request_params:
        request_kwargs["params"] = expectation.request_params
    if expectation.request_json:
        request_kwargs["json"] = expectation.request_json

    if expectation.is_stream:
        with client.stream(
            expectation.method, expectation.path, **request_kwargs
        ) as response:
            assert response.status_code == expectation.expected_status
            chunks = list(response.iter_lines())
            assert any("text-delta" in chunk for chunk in chunks)
    else:
        response = client.request(
            expectation.method, expectation.path, **request_kwargs
        )
        assert response.status_code == expectation.expected_status
        if expectation.validator is not None:
            expectation.validator(response.json())
        elif expectation.expected_json is not None:
            assert response.json() == expectation.expected_json
