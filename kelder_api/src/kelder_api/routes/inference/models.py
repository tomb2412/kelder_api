from typing import List, Optional

from pydantic import BaseModel


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
