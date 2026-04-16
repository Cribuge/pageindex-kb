"""
Document ingestion pipeline: extract text -> build PageIndex tree -> store.
"""
import hashlib
import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models.document import Document, DocumentStatus, TreeNode
from services.document_processor import document_processor
from services.storage import storage_service
from services.tree_builder import tree_builder

logger = logging.getLogger(__name__)


async def run_ingestion_task(document_id: uuid.UUID, file_data: bytes, filename: str, file_type: str):
    """Background task wrapper for document ingestion."""
    db = SessionLocal()
    try:
        await _process_document(db, document_id, file_data, filename, file_type)
    except Exception as e:
        logger.error(f"Ingestion failed for {document_id}: {e}")
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = DocumentStatus.FAILED
            db.commit()
    finally:
        db.close()


def _get_tree_config(db: Session) -> dict:
    """Read tree config from DB, fallback to settings defaults."""
    from models.config import SystemConfig
    from core.config import settings

    defaults = {
        "tree_max_depth": settings.TREE_MAX_DEPTH,
        "tree_max_children": settings.TREE_MAX_CHILDREN,
        "max_tree_context_chars": settings.MAX_TREE_CONTEXT_CHARS,
    }

    result = {}
    for key in defaults:
        row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        result[key] = row.value if row else defaults[key]
    return result


async def _process_document(db: Session, document_id: uuid.UUID, file_data: bytes, filename: str, file_type: str):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        return

    # Step 1: Save file locally
    doc.status = DocumentStatus.PROCESSING
    db.commit()

    relative_path = storage_service.save_file(file_data, filename, str(document_id))
    doc.file_path = relative_path
    doc.file_size = len(file_data)
    doc.checksum = hashlib.sha256(file_data).hexdigest()
    db.commit()

    # Step 2: Extract text
    full_path = storage_service.get_full_path(relative_path)
    text_chunks = document_processor.process_file(full_path, file_type)

    if not text_chunks:
        doc.status = DocumentStatus.FAILED
        db.commit()
        return

    full_text = "\n\n".join(chunk[0] for chunk in text_chunks)
    doc.full_text = full_text
    doc.status = DocumentStatus.TREE_BUILDING
    db.commit()

    # Step 3: Build PageIndex tree
    tree_cfg = _get_tree_config(db)
    tree = await tree_builder.build_tree(full_text, config=tree_cfg)
    doc.tree_index = tree

    # Step 4: Flatten and store tree nodes
    # Delete old nodes if reprocessing
    db.query(TreeNode).filter(TreeNode.document_id == document_id).delete()

    nodes = tree_builder.flatten_tree(tree, str(document_id))
    for node_data in nodes:
        node = TreeNode(**node_data)
        db.add(node)

    doc.status = DocumentStatus.INDEXED
    db.commit()
    logger.info(f"Document {document_id} indexed: {len(nodes)} tree nodes")
