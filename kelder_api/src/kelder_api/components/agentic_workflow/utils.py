from pydantic_ai.models import ModelRequest, ModelResponse

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
