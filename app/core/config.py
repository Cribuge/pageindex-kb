"""
Application configuration using Pydantic Settings.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "PageIndex Knowledge Base"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://kb_user:kb_password@localhost:5433/pageindex_kb"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:7b"

    # LLM Provider
    LLMProvider: str = "ollama"          # ollama | openai
    OpenAI_API_Base: str = "https://api.openai.com/v1"
    OpenAI_API_Key: str = ""

    # Storage
    UPLOAD_DIR: str = "./uploads"

    # PageIndex tree generation
    TREE_MAX_DEPTH: int = 5
    TREE_MAX_CHILDREN: int = 10
    MAX_TREE_CONTEXT_CHARS: int = 20000

    # PageIndex tree search
    SEARCH_MAX_DEPTH: int = 4
    SEARCH_TOP_K: int = 5

    # Allowed file types
    ALLOWED_EXTENSIONS: list = ["pdf", "docx", "doc", "txt", "md", "xlsx", "xls"]

    class Config:
        env_file = ".env"


settings = Settings()
