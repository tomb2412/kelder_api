from typing import List

from src.kelder_api.components.agentic_workflow.models import (
    Node,
    ReasoningEndNodes,
    State,
)


def clean_user_message(new_messages, users_message):
    # Preserve original messages while filtering out any None entries.
    return [msg for msg in new_messages if msg is not None]


def find_models(models: List[Node], node_type: ReasoningEndNodes):
    """Simple method to search the state workflow and return the node"""
    return [m for m in models if getattr(m, "node_type") == node_type]


async def notify_progress(state: State, node_name: str):
    callback = state.progress_callback
    if callback is None:
        return
    await callback(node_name)
