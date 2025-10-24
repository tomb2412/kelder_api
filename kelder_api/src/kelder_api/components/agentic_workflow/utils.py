from typing import List

from src.kelder_api.components.agentic_workflow.models import (
    NodeType,
    Node
)

def clean_user_message(new_messages, users_message):
    # Preserve original messages while filtering out any None entries.
    return [msg for msg in new_messages if msg is not None]


def find_models(models: List[Node], node_type: NodeType):
    """Simple method to search the state workflow and return the node"""
    return [m for m in models if getattr(m, "node_type") == node_type]
