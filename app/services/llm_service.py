"""
LLM service for Ollama and OpenAI-compatible API integration with streaming support.
"""
import httpx
import json
from typing import Optional, AsyncIterator, List, Dict, Any
from core.config import settings


class LLMService:

    def __init__(self):
        self.provider = settings.LLMProvider
        self.ollama_base = settings.OLLAMA_BASE_URL
        self.ollama_model = settings.LLM_MODEL
        self.openai_base = settings.OpenAI_API_Base
        self.openai_key = settings.OpenAI_API_Key

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> dict:
        if self.provider == "openai":
            return await self._openai_generate(prompt, system, model, **kwargs)
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

    async def _openai_generate(
        self,
        prompt: str,
        system: Optional[str],
        model: Optional[str],
        **kwargs,
    ) -> dict:
        model = model or self.ollama_model
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
        }

        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.openai_base}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return {"response": data["choices"][0]["message"]["content"]}

    async def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        if self.provider == "openai":
            async for token in self._openai_stream(prompt, system, model, **kwargs):
                yield token
            return
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

    async def _openai_stream(
        self,
        prompt: str,
        system: Optional[str],
        model: Optional[str],
        **kwargs,
    ) -> AsyncIterator[str]:
        model = model or self.ollama_model
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
        }

        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self.openai_base}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line and line.startswith("data:"):
                        if line.strip() == "data: [DONE]":
                            break
                        try:
                            data = json.loads(line[5:])
                            delta = data["choices"][0].get("delta", {})
                            if delta.get("content"):
                                yield delta["content"]
                        except json.JSONDecodeError:
                            continue

    async def list_models(self, models_url: str = None) -> List[dict]:
        """List available models based on current provider."""
        if self.provider == "openai":
            return await self.list_openai_models(models_url)
        return await self.list_ollama_models()

    async def list_ollama_models(self) -> List[dict]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.ollama_base}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [{"name": m["name"], "id": m["name"]} for m in data.get("models", [])]
        except Exception:
            return []

    async def list_openai_models(self, models_url: str = None) -> List[dict]:
        """Fetch model list from OpenAI-compatible API.

        If models_url is provided, use it directly (supports custom endpoints).
        Otherwise fall back to {base}/v1/models then {base}/models.
        """
        import logging
        logger = logging.getLogger(__name__)

        if not self.openai_key:
            return []

        # Determine URL to call
        if models_url:
            url = models_url if models_url.startswith("http") else f"{self.openai_base.rstrip('/')}/{models_url.lstrip('/')}"
        else:
            # Try common endpoints
            for endpoint in ["/v1/models", "/models"]:
                url = f"{self.openai_base.rstrip('/')}{endpoint}"
                try:
                    headers = {"Authorization": f"Bearer {self.openai_key}"}
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(url, headers=headers)
                        if response.status_code == 200:
                            data = response.json()
                            # Support {data: [...]} or [...] format
                            models_data = data.get("data", data) if isinstance(data, dict) else data
                            return [{"name": m["id"], "id": m["id"]} for m in models_data if isinstance(m, dict)]
                        logger.warning(f"list_openai_models: {url} returned {response.status_code}")
                except Exception as e:
                    logger.warning(f"list_openai_models: {url} failed: {e}")
                    continue
            return []

        # Direct URL provided
        try:
            headers = {"Authorization": f"Bearer {self.openai_key}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                models_data = data.get("data", data) if isinstance(data, dict) else data
                return [{"name": m["id"], "id": m["id"]} for m in models_data if isinstance(m, dict)]
        except Exception as e:
            logger.error(f"list_openai_models: {url} failed: {e}")
            return []

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                if self.provider == "openai":
                    resp = await client.get(
                        f"{self.openai_base}/models",
                        headers={"Authorization": f"Bearer {self.openai_key}"},
                    )
                else:
                    resp = await client.get(f"{self.ollama_base}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False


llm_service = LLMService()
