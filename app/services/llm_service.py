"""
LLM service for Ollama with streaming support.
"""
import httpx
import json
from typing import Optional, AsyncIterator, List
from core.config import settings


class LLMService:

    def __init__(self):
        self.ollama_base = settings.OLLAMA_BASE_URL
        self.ollama_model = settings.LLM_MODEL

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> dict:
        return await self._ollama_generate(prompt, system, model or self.ollama_model, **kwargs)

    async def _ollama_generate(
        self,
        prompt: str,
        system: Optional[str],
        model: str,
        **kwargs,
    ) -> dict:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 0.9),
                "num_predict": kwargs.get("max_tokens", 2048),
            },
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.ollama_base}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        async for token in self._ollama_stream(prompt, system, model or self.ollama_model, **kwargs):
            yield token

    async def _ollama_stream(
        self,
        prompt: str,
        system: Optional[str],
        model: str,
        **kwargs,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 0.9),
                "num_predict": kwargs.get("max_tokens", 2048),
            },
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self.ollama_base}/api/generate",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

    async def list_models(self) -> List[dict]:
        """List available Ollama models."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.ollama_base}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [{"name": m["name"], "id": m["name"]} for m in data.get("models", [])]
        except Exception:
            return []

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.ollama_base}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def embed(self, text: str, model: str = "nomic-embed-text:latest") -> List[float]:
        """Get embedding vector for text using Ollama embeddings API."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.ollama_base}/api/embeddings",
                    json={"model": model, "prompt": text},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("embedding", [])
        except Exception:
            return []


llm_service = LLMService()
