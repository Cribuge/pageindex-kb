"""
System configuration API endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import verify_token
from models.config import SystemConfig
from schemas.config import ConfigUpdate, ConfigResponse

router = APIRouter(prefix="/config", tags=["config"])

CONFIG_KEYS = [
    "llm_model",
    "ollama_base",
    "temperature",
    "max_tokens",
    "system_prompt",
    "search_top_k",
    "search_max_depth",
    "tree_max_depth",
    "tree_max_children",
    "max_tree_context_chars",
]


@router.get("", response_model=ConfigResponse)
def get_config(db: Session = Depends(get_db)) -> ConfigResponse:
    """Read config from DB, fallback to settings defaults."""
    defaults = {
        "llm_model": settings.LLM_MODEL,
        "ollama_base": settings.OLLAMA_BASE_URL,
        "temperature": 0.7,
        "max_tokens": 2048,
        "system_prompt": "",
        "search_top_k": settings.SEARCH_TOP_K,
        "search_max_depth": settings.SEARCH_MAX_DEPTH,  # 3
        "tree_max_depth": settings.TREE_MAX_DEPTH,
        "tree_max_children": settings.TREE_MAX_CHILDREN,
        "max_tree_context_chars": settings.MAX_TREE_CONTEXT_CHARS,
    }

    result = {}
    for key in CONFIG_KEYS:
        row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        result[key] = row.value if row else defaults[key]

    return ConfigResponse(**result)


@router.put("", response_model=ConfigResponse)
def update_config(cfg: ConfigUpdate, db: Session = Depends(get_db), _auth: bool = Depends(verify_token)) -> ConfigResponse:
    """Upsert config values. Only non-None fields are updated."""
    for key, value in cfg.model_dump(exclude_unset=True).items():
        if key not in CONFIG_KEYS:
            continue
        row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if row:
            row.value = value
        else:
            db.add(SystemConfig(key=key, value=value))
    db.commit()

    # Return full config after update
    return get_config(db)
