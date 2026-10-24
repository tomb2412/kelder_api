from __future__ import annotations

import pytest
from pydantic_ai.exceptions import ModelHTTPError

from src.kelder_api.routes.inference.utils import describe_workflow_error


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (
            ModelHTTPError(429, "gpt-4o-mini", {"code": "insufficient_quota"}),
            "quota is used up",
        ),
        (
            ModelHTTPError(429, "gpt-4o-mini", {"code": "rate_limit_exceeded"}),
            "try again in a minute",
        ),
        (ModelHTTPError(503, "gpt-4o-mini", None), "having problems"),
        (RuntimeError("boom"), "Agent workflow failed"),
    ],
)
def test_describe_workflow_error(exc, expected):
    assert expected in describe_workflow_error(exc)
