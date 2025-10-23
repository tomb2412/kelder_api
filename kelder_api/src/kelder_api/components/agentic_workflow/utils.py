from typing import List

from pydantic_ai.models import ModelRequest, ModelResponse

from src.kelder_api.components.agentic_workflow.models import (
    NodeType,
    Node
)

def clean_user_message(new_messages, users_message):
    cleaned_messages = []

    for msg in new_messages:
        if isinstance(msg, ModelRequest) or isinstance(msg, ModelResponse):
            for part in msg.parts:
                if hasattr(part, "content") and isinstance(part.content, str):
                    if getattr(part, "tool_name", None) == "final_result":
                        part.content = "Final result processed."
                    else:
                        part.content = users_message

        cleaned_messages.append(msg)
    return cleaned_messages


def find_models(models: List[Node], node_type: NodeType):
    """Simple method to search the state workflow and return the node"""
    return [m for m in models if getattr(m, "node_type") == node_type]
