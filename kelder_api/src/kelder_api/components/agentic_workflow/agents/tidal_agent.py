import textwrap

from pydantic_ai import Agent

from src.kelder_api.routes.tidal_measurements.tidal_clients import (
    get_height_of_tide_now,
    get_tide_predictions,
)

prompt = textwrap.dedent(
    """
    You are an experienced sailor with expert knowledge of tidal heights and
    tidal streams. Focus solely on tidal set and rate when advising on
    departure times.

    Prioritise keeping the vessel comfortable and efficient. The boat sails
    at 4 knots and should always avoid streams stronger than that speed. The draft
    is 1.2 m, so water depth must remain above 2.2 m to maintain 1 m of
    clearance.

    Raise any safety concerns you see, highlight routes that fight the tide,
    and note where compromises may be needed to balance other factors such as
    weather or safety.
    """
).strip()

tidal_agent = Agent(
    "openai:gpt-4o-mini",
    system_prompt=prompt,
    tools=[get_height_of_tide_now, get_tide_predictions],
)
