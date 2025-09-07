from pydantic import BaseModel, Field

from typing import List, Optional

class Parts(BaseModel):
    type: str
    text: str

class Message(BaseModel):
    id: Optional[str]
    parts: List[Parts]
    role: str

class InferenceRequest(BaseModel):
    id: str
    messages: List[Message]

