"""
Pydantic schemas for system config API.
"""
from typing import Optional

from pydantic import BaseModel


class ConfigUpdate(BaseModel):
    llm_model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    system_prompt: Optional[str] = None
    search_top_k: Optional[int] = None
    search_max_depth: Optional[int] = None
    tree_max_depth: Optional[int] = None
    tree_max_children: Optional[int] = None
    max_tree_context_chars: Optional[int] = None


class ConfigResponse(BaseModel):
    llm_model: str = "qwen2.5:7b"
    temperature: float = 0.7
    max_tokens: int = 2048
    system_prompt: str = ""
    search_top_k: int = 5
    search_max_depth: int = 4
    tree_max_depth: int = 5
    tree_max_children: int = 10
    max_tree_context_chars: int = 20000
