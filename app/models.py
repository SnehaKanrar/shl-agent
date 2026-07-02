from typing import List, Literal, Optional
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


class Recommendation(BaseModel):
    name: str
    url: str
    test_type: str  # letters joined, e.g. "K" or "K P" -- matches spec's example


class ChatResponse(BaseModel):
    reply: str
    recommendations: List[Recommendation] = []
    end_of_conversation: bool = False
