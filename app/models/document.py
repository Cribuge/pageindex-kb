"""
Document and TreeNode database models.
"""
import uuid
import enum
from datetime import datetime

from sqlalchemy import Column, String, Integer, Text, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.database import Base


class DocumentStatus(str, enum.Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    TREE_BUILDING = "tree_building"
    INDEXED = "indexed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    file_path = Column(String(1000))
    file_type = Column(String(50))
    file_size = Column(Integer, default=0)
    category = Column(String(200))
    tags = Column(JSON, default=list)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.UPLOADING)
    checksum = Column(String(64))
    description = Column(Text)

    # PageIndex specific fields
    tree_index = Column(JSON)       # The hierarchical tree structure
    full_text = Column(Text)        # Extracted full text for context retrieval

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tree_nodes = relationship("TreeNode", back_populates="document", cascade="all, delete-orphan")


class TreeNode(Base):
    __tablename__ = "tree_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"))
    node_id = Column(String(20), nullable=False)        # e.g. "0006"
    title = Column(String(500))
    summary = Column(Text)
    start_index = Column(Integer)                        # line start in full_text
    end_index = Column(Integer)                          # line end in full_text
    depth = Column(Integer, default=0)
    parent_node_id = Column(String(20))                  # null for root
    path = Column(String(1000))                          # materialized path "0001/0003/0006"
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="tree_nodes")
