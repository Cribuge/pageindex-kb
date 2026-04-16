"""
Document management API endpoints.
"""
import uuid
from typing import Optional, List

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from models.document import Document, DocumentStatus, TreeNode
from schemas.document import DocumentResponse, DocumentDetail, DocumentList, TreeIndexResponse, BatchDeleteRequest, BatchReprocessRequest
from services.ingestion import run_ingestion_task
from services.storage import storage_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # Validate file type
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type '{ext}' not supported. Allowed: {settings.ALLOWED_EXTENSIONS}")

    # Read file data
    file_data = await file.read()

    # Create document record
    doc = Document(
        title=title or file.filename,
        file_type=ext,
        file_size=len(file_data),
        category=category if category else None,
        tags=[t.strip() for t in tags.split(",")] if tags else [],
        description=description,
        status=DocumentStatus.UPLOADING,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Start background ingestion
    background_tasks.add_task(run_ingestion_task, doc.id, file_data, file.filename, ext)

    return doc


@router.post("/batch-upload", response_model=List[DocumentResponse])
async def batch_upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    category: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    if len(files) > 20:
        raise HTTPException(400, "Maximum 20 files per batch")

    docs = []
    for file in files:
        ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else ""
        if ext not in settings.ALLOWED_EXTENSIONS:
            continue

        file_data = await file.read()
        doc = Document(
            title=file.filename,
            file_type=ext,
            file_size=len(file_data),
            category=category if category else None,
            status=DocumentStatus.UPLOADING,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        background_tasks.add_task(run_ingestion_task, doc.id, file_data, file.filename, ext)
        docs.append(doc)

    return docs


@router.get("/", response_model=DocumentList)
async def list_documents(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Document)

    if category:
        query = query.filter(Document.category == category)
    if status:
        query = query.filter(Document.status == status)
    if search:
        query = query.filter(Document.title.ilike(f"%{search}%"))

    total = query.count()
    items = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()

    return DocumentList(items=items, total=total)


@router.put("/{document_id}")
async def update_document(
    document_id: uuid.UUID,
    title: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    clear_category: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if title is not None:
        doc.title = title
    if clear_category == "true":
        doc.category = None
    elif category is not None:
        doc.category = category
    if tags is not None:
        doc.tags = [t.strip() for t in tags.split(",")] if tags else []
    db.commit()
    return {"message": "Document updated", "document_id": str(document_id)}


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/{document_id}/tree", response_model=TreeIndexResponse)
async def get_document_tree(document_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if not doc.tree_index:
        raise HTTPException(404, "Tree index not yet built")

    node_count = db.query(TreeNode).filter(TreeNode.document_id == document_id).count()
    return TreeIndexResponse(
        document_id=doc.id,
        tree_index=doc.tree_index,
        node_count=node_count,
    )


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    if not doc.file_path:
        raise HTTPException(400, "No file associated with this document")

    # Re-read file from storage
    file_data = storage_service.read_file(doc.file_path)
    background_tasks.add_task(run_ingestion_task, doc.id, file_data, doc.title, doc.file_type)

    return {"message": "Reprocessing started", "document_id": str(document_id)}


@router.delete("/{document_id}")
async def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    # Delete file from storage
    if doc.file_path:
        storage_service.delete_file(doc.file_path)

    # Delete from DB (cascades to tree_nodes)
    db.delete(doc)
    db.commit()

    return {"message": "Document deleted", "document_id": str(document_id)}


@router.post("/batch-delete")
async def batch_delete_documents(req: BatchDeleteRequest, db: Session = Depends(get_db)):
    deleted = 0
    for doc_id in req.ids:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            continue
        if doc.file_path:
            storage_service.delete_file(doc.file_path)
        db.delete(doc)
        deleted += 1
    db.commit()
    return {"deleted": deleted}


@router.post("/batch-reprocess")
async def batch_reprocess_documents(
    req: BatchReprocessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    triggered = 0
    for doc_id in req.ids:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc or not doc.file_path:
            continue
        file_data = storage_service.read_file(doc.file_path)
        background_tasks.add_task(run_ingestion_task, doc.id, file_data, doc.title, doc.file_type)
        triggered += 1
    return {"triggered": triggered}


@router.post("/categories/rename")
def rename_category(old_name: str = Form(...), new_name: str = Form(...), db: Session = Depends(get_db)):
    """
    Rename a category: update all documents with old_name category to new_name.
    If old_name does not exist as a category, return 404.
    """
    docs = db.query(Document).filter(Document.category == old_name).all()
    if not docs and old_name != "":
        raise HTTPException(status_code=404, detail="Category not found")
    for doc in docs:
        doc.category = new_name
    db.commit()
    return {"renamed": len(docs), "old": old_name, "new": new_name}
