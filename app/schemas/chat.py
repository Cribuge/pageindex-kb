"""
Pydantic schemas for chat API.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str
    session_id: Optional[uuid.UUID] = None


class SourceReference(BaseModel):
    document_id: str
    document_title: str
    node_id: str
    title: str
    summary: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceReference] = []
    session_id: uuid.UUID
    model_name: Optional[str] = None
    latency_ms: Optional[int] = None


class ChatSessionCreate(BaseModel):
    title: Optional[str] = None


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    sources: Optional[Any] = None
    model_name: Optional[str]
    latency_ms: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True
