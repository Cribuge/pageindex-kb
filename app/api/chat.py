"""
Chat API endpoints with SSE streaming support.
"""
import json
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from core.database import get_db
from models.chat import ChatSession, ChatMessage
from schemas.chat import ChatRequest, ChatResponse, ChatSessionResponse, ChatMessageResponse
from services.rag_service import rag_service
from services.llm_service import llm_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/")
async def chat_query(request: ChatRequest, db: Session = Depends(get_db)):
    """Non-streaming RAG query."""
    # Get or create session
    session = None
    if request.session_id:
        session = db.query(ChatSession).filter(ChatSession.id == request.session_id).first()

    if not session:
        session = ChatSession(title=request.query[:100])
        db.add(session)
        db.commit()
        db.refresh(session)

    # Save user message
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=request.query,
    )
    db.add(user_msg)
    db.commit()

    # Execute RAG query
    result = await rag_service.query(request.query, db)

    # Save assistant message
    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=result["answer"],
        sources=result["sources"],
        latency_ms=result["latency_ms"],
    )
    db.add(assistant_msg)
    db.commit()

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        session_id=session.id,
        latency_ms=result["latency_ms"],
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    """Streaming RAG query via SSE."""
    # Get or create session
    session = None
    if request.session_id:
        session = db.query(ChatSession).filter(ChatSession.id == request.session_id).first()

    if not session:
        session = ChatSession(title=request.query[:100])
        db.add(session)
        db.commit()
        db.refresh(session)

    # Save user message
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=request.query,
    )
    db.add(user_msg)
    db.commit()

    session_id = session.id

    async def event_generator():
        full_answer = ""
        sources = []
        latency_ms = 0

        async for event in rag_service.query_stream(request.query, db):
            event_type = event["type"]
            data = event["data"]

            if event_type == "token":
                full_answer += data
            elif event_type == "sources":
                sources = data
            elif event_type == "done":
                latency_ms = data.get("latency_ms", 0)

            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        # Save assistant message after streaming completes
        db2 = Session.object_session(session) or db
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=full_answer,
            sources=sources,
            latency_ms=latency_ms,
        )
        db2.add(assistant_msg)
        db2.commit()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    sessions = db.query(ChatSession).order_by(
        ChatSession.updated_at.desc()
    ).offset(skip).limit(limit).all()

    result = []
    for s in sessions:
        msg_count = db.query(ChatMessage).filter(ChatMessage.session_id == s.id).count()
        result.append(ChatSessionResponse(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=msg_count,
        ))
    return result


@router.get("/sessions/{session_id}", response_model=list[ChatMessageResponse])
async def get_session_messages(session_id: uuid.UUID, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")

    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()

    return messages


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")

    db.delete(session)
    db.commit()
    return {"message": "Session deleted", "session_id": str(session_id)}


@router.get("/models")
async def list_models(
    openai_base: str = None,
    openai_key: str = None,
    models_url: str = None,
    anthropic_base: str = None,
    anthropic_key: str = None,
):
    """List available models.

    Supports OpenAI-compatible (via openai_base/key) and Anthropic (via anthropic_base/key).
    Falls back to current provider settings if no overrides provided.
    """
    import logging
    logger = logging.getLogger(__name__)

    if anthropic_base and anthropic_key:
        original_provider = llm_service.provider
        original_base = llm_service.anthropic_base
        original_key = llm_service.anthropic_key
        llm_service.provider = "anthropic"
        llm_service.anthropic_base = anthropic_base
        llm_service.anthropic_key = anthropic_key
        logger.info(f"[list_models] Using Anthropic: base={anthropic_base}")
        models = await llm_service.list_models()
        logger.info(f"[list_models] Anthropic returned {len(models)} models: {[m['id'] for m in models]}")
        llm_service.provider = original_provider
        llm_service.anthropic_base = original_base
        llm_service.anthropic_key = original_key
        return {"models": models}

    if openai_base and openai_key:
        original_provider = llm_service.provider
        original_base = llm_service.openai_base
        original_key = llm_service.openai_key
        llm_service.provider = "openai"
        llm_service.openai_base = openai_base
        llm_service.openai_key = openai_key
        logger.info(f"[list_models] Using OpenAI: base={openai_base}, models_url={models_url}")
        models = await llm_service.list_models(models_url)
        logger.info(f"[list_models] OpenAI returned {len(models)} models: {[m['id'] for m in models]}")
        llm_service.provider = original_provider
        llm_service.openai_base = original_base
        llm_service.openai_key = original_key
        return {"models": models}

    models = await llm_service.list_models()
    return {"models": models}
