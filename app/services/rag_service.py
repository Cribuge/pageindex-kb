"""
RAG service: combines PageIndex tree search with LLM answer generation.
"""
import time
from typing import AsyncIterator, List

from sqlalchemy.orm import Session

from core.config import settings
from services.llm_service import llm_service
from services.tree_search import tree_search

SYSTEM_PROMPT = """你是一个知识库问答助手。根据提供的文档内容回答用户问题。

规则：
1. 只使用提供的文档内容来回答
2. 如果文档中没有足够信息，请明确说明
3. 在回答中引用来源文档标题
4. 回答要准确、简洁、有条理
5. 使用与问题相同的语言回答"""

DEFAULT_SYSTEM_PROMPT = SYSTEM_PROMPT


class RAGService:

    def __init__(self):
        self.llm = llm_service
        self.search = tree_search

    def _get_config(self, db: Session) -> dict:
        """Read config from DB, fallback to defaults."""
        from models.config import SystemConfig

        defaults = {
            "llm_model": settings.LLM_MODEL,
            "temperature": 0.7,
            "max_tokens": 2048,
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
        }

        result = {}
        for key in defaults:
            row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            result[key] = row.value if row else defaults[key]
        return result

    async def query(self, query: str, db: Session) -> dict:
        """Non-streaming RAG query."""
        start_time = time.time()

        cfg = self._get_config(db)
        results = await self.search.search_all_documents(query, db)
        context = self._build_context(results)
        prompt = self._build_prompt(query, context)

        response = await self.llm.generate(
            prompt=prompt,
            system=cfg["system_prompt"],
            temperature=cfg["temperature"],
            max_tokens=cfg["max_tokens"],
            model=cfg["llm_model"],
        )

        latency_ms = int((time.time() - start_time) * 1000)

        return {
            "answer": response.get("response", ""),
            "sources": self._format_sources(results),
            "latency_ms": latency_ms,
        }

    async def query_stream(self, query: str, db: Session) -> AsyncIterator[dict]:
        """Streaming RAG query yielding SSE-compatible events."""
        start_time = time.time()

        cfg = self._get_config(db)

        yield {"type": "status", "data": {"stage": "searching"}}

        results = await self.search.search_all_documents(query, db)
        context = self._build_context(results)

        yield {"type": "status", "data": {"stage": "generating", "retrieved": len(results)}}

        prompt = self._build_prompt(query, context)
        async for token in self.llm.generate_stream(
            prompt=prompt,
            system=cfg["system_prompt"],
            temperature=cfg["temperature"],
            max_tokens=cfg["max_tokens"],
            model=cfg["llm_model"],
        ):
            yield {"type": "token", "data": token}

        latency_ms = int((time.time() - start_time) * 1000)

        yield {"type": "sources", "data": self._format_sources(results)}
        yield {"type": "done", "data": {"latency_ms": latency_ms}}

    def _build_context(self, results: List[dict]) -> str:
        parts = []
        for i, r in enumerate(results):
            part = f"【文档片段 {i+1}: {r['title']}】(来源: {r.get('document_title', '未知')})\n"
            if r.get("summary"):
                part += f"摘要: {r['summary']}\n"
            part += f"内容:\n{r.get('text_content', '')}"
            parts.append(part)
        return "\n\n---\n\n".join(parts)

    def _build_prompt(self, query: str, context: str) -> str:
        return f"""请根据以下文档内容回答问题。

【参考内容】
{context}

【问题】
{query}

回答："""

    def _format_sources(self, results: List[dict]) -> List[dict]:
        return [
            {
                "document_id": r.get("document_id", ""),
                "document_title": r.get("document_title", ""),
                "node_id": r.get("node_id", ""),
                "title": r.get("title", ""),
                "summary": r.get("summary", ""),
            }
            for r in results
        ]


rag_service = RAGService()
