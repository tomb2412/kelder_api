from __future__ import annotations

from src.kelder_api.components.agentic_workflow.agents.models import (
    PassagePlan,
    Waypoint,
)


def _plan(*names: str | None) -> PassagePlan:
    return PassagePlan(
        departure_place_name="Hamble",
        desination_place_name="Cowes",
        course_to_steer=[
            Waypoint(name=name, latitude=50.8, longitude=-1.3) for name in names
        ],
    )


def test_unnamed_waypoints_are_named_by_number():
    plan = _plan("Hamble Point", None, "  ", "Cowes")

    assert [wp.name for wp in plan.course_to_steer] == [
        "Hamble Point",
        "Waypoint 2",
        "Waypoint 3",
        "Cowes",
    ]


def test_generated_names_are_renumbered_after_a_waypoint_is_removed():
    # "Waypoint 2" was deleted on the map, so the old "Waypoint 3" moves up.
    plan = _plan("Hamble Point", "Waypoint 3", "Cowes")

    assert plan.course_to_steer[1].name == "Waypoint 2"
