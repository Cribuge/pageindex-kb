"""
Pydantic schemas for document API.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel


class DocumentCreate(BaseModel):
    title: str
    category: Optional[str] = None
    tags: Optional[List[str]] = []
    description: Optional[str] = None


class DocumentResponse(BaseModel):
    id: uuid.UUID
    title: str
    file_type: Optional[str]
    file_size: int
    category: Optional[str]
    tags: Optional[List[str]]
    status: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentList(BaseModel):
    items: List[DocumentResponse]
    total: int


class TreeNodeResponse(BaseModel):
    id: uuid.UUID
    node_id: str
    title: str
    summary: Optional[str]
    start_index: int
    end_index: int
    depth: int
    parent_node_id: Optional[str]
    path: Optional[str]

    class Config:
        from_attributes = True


class DocumentDetail(DocumentResponse):
    tree_nodes: List[TreeNodeResponse] = []


class TreeIndexResponse(BaseModel):
    document_id: uuid.UUID
    tree_index: Any
    node_count: int


class BatchDeleteRequest(BaseModel):
    ids: List[uuid.UUID]


class BatchReprocessRequest(BaseModel):
    ids: List[uuid.UUID]


class DocumentUpdateRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    clear_category: bool = False


class CategoryRenameRequest(BaseModel):
    old_name: str = ""
    new_name: str
