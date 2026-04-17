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
    llm_provider: Optional[str] = None
    openai_api_base: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_api_models_url: Optional[str] = None
    ollama_base: Optional[str] = None


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
    llm_provider: str = "ollama"
    openai_api_base: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_api_models_url: str = ""
    ollama_base: str = "http://localhost:11434"
