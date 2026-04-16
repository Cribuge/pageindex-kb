"""
PageIndex Knowledge Base - FastAPI application entry point.
"""
import time
import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import OperationalError

from core.config import settings
from core.database import get_db, engine, Base
from models.document import Document, DocumentStatus, TreeNode
from models.chat import ChatSession
from models.config import SystemConfig
from api import document, chat, config
from services.llm_service import llm_service

logger = logging.getLogger(__name__)


def init_db_with_retry(max_retries=10, delay=3):
    """Create tables with retry in case PostgreSQL is still starting."""
    for attempt in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")
            return
        except OperationalError:
            logger.warning(f"DB not ready, retrying ({attempt+1}/{max_retries})...")
            time.sleep(delay)
    raise RuntimeError("Failed to connect to database after retries")


init_db_with_retry()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(document.router)
app.include_router(chat.router)
app.include_router(config.router)


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "architecture": "PageIndex (vectorless, reasoning-based RAG)",
    }


@app.get("/ping")
async def ping():
    return {"status": "pong"}


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    ollama_ok = await llm_service.check_health()

    try:
        db.execute(func.now())
        postgres_ok = True
    except Exception:
        postgres_ok = False

    return {
        "ollama": ollama_ok,
        "postgres": postgres_ok,
        "overall": ollama_ok and postgres_ok,
    }


@app.get("/stats")
async def stats(db: Session = Depends(get_db)):
    total_docs = db.query(Document).count()
    indexed_docs = db.query(Document).filter(Document.status == DocumentStatus.INDEXED).count()
    total_nodes = db.query(TreeNode).count()
    total_sessions = db.query(ChatSession).count()

    return {
        "total_documents": total_docs,
        "indexed_documents": indexed_docs,
        "total_tree_nodes": total_nodes,
        "total_sessions": total_sessions,
    }
