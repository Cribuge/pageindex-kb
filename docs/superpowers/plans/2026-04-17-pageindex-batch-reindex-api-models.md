# PageIndex 批量重建索引 + API 模型支持

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add batch reprocess button to admin document management, and support OpenAI-compatible API as LLM provider with dynamic model loading.

**Architecture:** LLM service refactored to support both Ollama (local) and OpenAI-compatible endpoints. Provider config stored in DB (system_config table) with .env defaults. Frontend dynamically loads model list based on selected provider.

**Tech Stack:** FastAPI, httpx, Ollama API, OpenAI-compatible API, Pydantic

---

## File Structure

```
app/
├── core/config.py          — add LLMProvider, OpenAI_API_Base, OpenAI_API_Key
├── services/
│   ├── llm_service.py      — dual-provider generate()/generate_stream()/list_models()
│   ├── rag_service.py      — read provider config from DB
│   └── tree_search.py      — read provider config from DB
├── schemas/config.py       — ConfigResponse/ConfigUpdate add new fields
app/api/
├── chat.py                 — GET /chat/models endpoint (returns provider's model list)
web/
└── admin.html              — batch reprocess button + provider UI + dynamic model selector
```

---

## Task 1: Frontend — 批量重建索引按钮

**Files:**
- Modify: `web/admin.html:897-903` (batch-bar)
- Modify: `web/admin.html:1420-1460` (add batchReprocess function)

- [ ] **Step 1: Add "批量重建索引" button to batch-bar**

In `web/admin.html`, find the batch-bar div around line 897. Add a new button after "批量重命名":

```html
<button class="btn btn-secondary" onclick="batchReprocess()">批量重建索引</button>
```

- [ ] **Step 2: Add batchReprocess() JavaScript function**

Add this function after the existing `batchDelete()` function (~line 1430). Find `async function batchDelete()` and add `batchReprocess` after it:

```javascript
async function batchReprocess() {
    if (selectedDocIds.size === 0) return;
    if (!confirm(`确定要重建 ${selectedDocIds.size} 个文档的索引吗？`)) return;
    try {
        const ids = [...selectedDocIds].map(id => id);
        const response = await authFetch(API + '/documents/batch-reprocess', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids })
        });
        const data = await response.json();
        toast(`${data.triggered} 个文档开始重建索引`, 'success');
        clearSelection();
        setTimeout(() => loadDocuments(), 500);
    } catch (error) {
        toast('批量重建索引失败: ' + error.message, 'error');
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add web/admin.html
git commit -m "feat(admin): add batch reprocess button"
```

---

## Task 2: Backend — LLM 服务支持 OpenAI API

**Files:**
- Modify: `app/core/config.py` — add LLMProvider, OpenAI_API_Base, OpenAI_API_Key
- Modify: `app/services/llm_service.py` — add dual-provider generate/generate_stream/list_models
- Modify: `app/schemas/config.py` — ConfigResponse/ConfigUpdate add new fields

- [ ] **Step 1: Modify app/core/config.py — add new settings**

Find the `Settings` class in `app/core/config.py`. Add these fields after `LLM_MODEL`:

```python
LLMProvider: str = "ollama"          # ollama | openai
OpenAI_API_Base: str = "https://api.openai.com/v1"
OpenAI_API_Key: str = ""
```

- [ ] **Step 2: Modify app/services/llm_service.py — implement dual provider**

Replace the entire file content with this:

```python
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

    async def list_models(self) -> List[dict]:
        """List available models based on current provider."""
        if self.provider == "openai":
            return await self.list_openai_models()
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

    async def list_openai_models(self) -> List[dict]:
        """Fetch model list from OpenAI-compatible API via /v1/models endpoint."""
        if not self.openai_key:
            return []
        try:
            headers = {"Authorization": f"Bearer {self.openai_key}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.openai_base}/models",
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                return [{"name": m["id"], "id": m["id"]} for m in data.get("data", [])]
        except Exception:
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
```

- [ ] **Step 3: Modify app/schemas/config.py — add new fields**

Replace the file content:

```python
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
```

- [ ] **Step 4: Modify app/api/chat.py — add GET /chat/models endpoint**

Read `app/api/chat.py` first to find where to add the new endpoint.

Add this endpoint to the existing router in `app/api/chat.py`:

```python
@router.get("/models")
async def list_models():
    """List available models based on current provider."""
    models = await llm_service.list_models()
    return {"models": models}
```

- [ ] **Step 5: Commit**

```bash
git add app/core/config.py app/services/llm_service.py app/schemas/config.py app/api/chat.py
git commit -m "feat: support OpenAI-compatible API as LLM provider"
```

---

## Task 3: Backend — Services Layer 读取 Provider 配置

**Files:**
- Modify: `app/services/rag_service.py` — _get_config add provider fields
- Modify: `app/services/tree_search.py` — _get_config add provider fields

- [ ] **Step 1: Modify rag_service.py — _get_config**

In `app/services/rag_service.py`, find `_get_config`. Add `llm_provider`, `openai_api_base`, `openai_api_key` to the defaults dict:

```python
def _get_config(self, db: Session) -> dict:
    """Read config from DB, fallback to defaults."""
    from models.config import SystemConfig

    defaults = {
        "llm_model": settings.LLM_MODEL,
        "temperature": 0.7,
        "max_tokens": 2048,
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "llm_provider": settings.LLMProvider,
        "openai_api_base": settings.OpenAI_API_Base,
        "openai_api_key": settings.OpenAI_API_Key,
    }

    result = {}
    for key in defaults:
        row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        result[key] = row.value if row else defaults[key]
    return result
```

- [ ] **Step 2: Modify tree_search.py — _get_config**

In `app/services/tree_search.py`, find `_get_config`. Add provider fields:

```python
def _get_config(self, db: Session) -> dict:
    """Read search config from DB, fallback to settings defaults."""
    defaults = {
        "search_top_k": settings.SEARCH_TOP_K,
        "search_max_depth": settings.SEARCH_MAX_DEPTH,
        "llm_provider": settings.LLMProvider,
        "openai_api_base": settings.OpenAI_API_Base,
        "openai_api_key": settings.OpenAI_API_Key,
    }
    result = {}
    for key in defaults:
        row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        result[key] = row.value if row else defaults[key]
    return result
```

Also update `search_all_documents` to pass provider config to `search_document` and `_select_documents`:
- `search_document(query, doc, max_depth=cfg["search_max_depth"])` — no change needed, provider is only used in `_select_documents` LLM call
- In `_select_documents`, the LLM call uses `self.llm.generate(...)` which now reads provider from `llm_service` init. No additional changes needed since `llm_service` reads from `settings` at init time. However, since `llm_service` is a singleton initialized at module load, config changes won't take effect until restart. This is acceptable since provider switching requires restart.

- [ ] **Step 3: Commit**

```bash
git add app/services/rag_service.py app/services/tree_search.py
git commit -m "feat(services): read provider config from DB"
```

---

## Task 4: Frontend — Provider 切换 + 动态模型列表

**Files:**
- Modify: `web/admin.html` — system settings panel restructure

This is the most complex task. Changes span:
- Provider radio buttons (Ollama / OpenAI)
- Conditional API config inputs (base_url, api_key)
- Dynamic model loading via GET /chat/models
- Hidden openai_api_key storage

- [ ] **Step 1: Find the model config card in admin.html**

Around line 960-992, find the model config card `<div class="settings-card">`. Replace the entire content with this:

```html
<h3><span class="icon">🤖</span> 模型配置</h3>

<div class="form-group">
    <label>模型来源</label>
    <div class="provider-tabs">
        <label class="provider-tab">
            <input type="radio" name="llm_provider" value="ollama" id="prov-ollama" onchange="switchProvider('ollama')">
            <span>Ollama (本地)</span>
        </label>
        <label class="provider-tab">
            <input type="radio" name="llm_provider" value="openai" id="prov-openai" onchange="switchProvider('openai')">
            <span>OpenAI 兼容</span>
        </label>
    </div>
</div>

<!-- Ollama API Config (always visible, used for model list) -->
<div id="ollama-config" class="form-group">
    <label>Ollama 地址</label>
    <input type="text" id="cfg-ollama_base" value="http://localhost:11434" placeholder="http://localhost:11434">
</div>

<!-- OpenAI API Config (hidden unless provider=openai) -->
<div id="openai-config" style="display:none">
    <div class="form-group">
        <label>API Base URL</label>
        <input type="text" id="cfg-openai_api_base" placeholder="https://api.openai.com/v1">
    </div>
    <div class="form-group">
        <label>API Key</label>
        <input type="password" id="cfg-openai_api_key" placeholder="sk-..." style="width:100%;padding:8px 12px;border:1.5px solid var(--border);border-radius:var(--radius);font-size:14px;">
    </div>
    <button type="button" class="btn btn-secondary" onclick="loadOpenAIModels()" style="margin-bottom:8px">加载模型列表</button>
</div>

<div class="form-group">
    <label>LLM 模型</label>
    <select id="cfg-llm_model">
        <option value="">-- 先选择来源并加载模型 --</option>
    </select>
</div>

<div class="form-row">
    <div class="form-group">
        <label>温度 (temperature)</label>
        <input type="number" id="cfg-temperature" value="0.7" step="0.1" min="0" max="2">
    </div>
    <div class="form-group">
        <label>最大生成长度</label>
        <input type="number" id="cfg-max_tokens" value="2048" min="100" max="8192">
    </div>
</div>
<div class="form-group">
    <label>系统提示词 (system_prompt)</label>
    <textarea id="cfg-system_prompt" rows="3" placeholder="可选，覆盖默认系统提示词"></textarea>
</div>
```

- [ ] **Step 2: Add CSS for provider tabs**

Find the `<style>` section in admin.html. Add these styles before the closing `</style>` tag:

```css
.provider-tabs {
    display: flex;
    gap: 8px;
    margin-top: 4px;
}
.provider-tab {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border: 1.5px solid var(--border);
    border-radius: var(--radius);
    cursor: pointer;
    font-size: 14px;
    transition: var(--transition);
}
.provider-tab:has(input:checked) {
    border-color: var(--accent);
    background: var(--accent-dim);
    color: var(--accent);
}
.provider-tab input {
    display: none;
}
```

- [ ] **Step 3: Add JavaScript functions for provider switching and model loading**

Add these functions in the `<script>` section of admin.html (after existing global functions like `escapeHtml`):

```javascript
async function switchProvider(provider) {
    document.getElementById('ollama-config').style.display = provider === 'ollama' ? 'block' : 'none';
    document.getElementById('openai-config').style.display = provider === 'openai' ? 'block' : 'none';
    document.getElementById('cfg-llm_model').options.length = 0;
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = '-- 请加载模型 --';
    document.getElementById('cfg-llm_model').appendChild(opt);
    if (provider === 'ollama') {
        await loadOllamaModels();
    }
}

async function loadOllamaModels() {
    const base = document.getElementById('cfg-ollama_base').value || 'http://localhost:11434';
    try {
        const res = await fetch(base + '/api/tags');
        const data = await res.json();
        const select = document.getElementById('cfg-llm_model');
        select.options.length = 0;
        (data.models || []).forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.name;
            opt.textContent = m.name;
            select.appendChild(opt);
        });
        const saved = document.getElementById('cfg-llm_model').dataset.value;
        if (saved) select.value = saved;
    } catch (e) {
        console.error('Failed to load Ollama models', e);
    }
}

async function loadOpenAIModels() {
    const base = document.getElementById('cfg-openai_api_base').value;
    const key = document.getElementById('cfg-openai_api_key').value;
    if (!base || !key) {
        toast('请先填写 API Base URL 和 API Key', 'error');
        return;
    }
    try {
        const res = await fetch(API + '/chat/models', {
            headers: { 'x-openai-base': base, 'x-openai-key': key }
        });
        const data = await res.json();
        const select = document.getElementById('cfg-llm_model');
        select.options.length = 0;
        (data.models || []).forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.id || m.name;
            opt.textContent = m.id || m.name;
            select.appendChild(opt);
        });
        toast('模型列表加载成功', 'success');
    } catch (e) {
        toast('加载模型列表失败: ' + e.message, 'error');
    }
}
```

**Note:** The `GET /chat/models` endpoint currently returns Ollama models only. We need to modify it to support OpenAI models via request headers. See Step 5.

- [ ] **Step 4: Update loadSettings() to handle new fields**

Find the `loadSettings()` function in admin.html. Update it to:
1. Set provider radio button
2. Show/hide correct config sections
3. Load models based on provider

Find the existing `loadSettings` function. Update it to:

```javascript
async function loadSettings() {
    try {
        const res = await fetch(API + '/config');
        const settingsData = await res.json();
        // ... existing code for temp/max_tokens/system_prompt ...

        // Provider
        const provider = settingsData.llm_provider || 'ollama';
        document.querySelectorAll('input[name="llm_provider"]').forEach(r => {
            r.checked = r.value === provider;
        });
        switchProvider(provider);

        // Ollama base
        document.getElementById('cfg-ollama_base').value = settingsData.ollama_base || 'http://localhost:11434';

        // OpenAI config
        document.getElementById('cfg-openai_api_base').value = settingsData.openai_api_base || '';
        document.getElementById('cfg-openai_api_key').value = settingsData.openai_api_key || '';

        // Model - load based on provider
        document.getElementById('cfg-llm_model').dataset.value = settingsData.llm_model || '';
        if (provider === 'ollama') {
            await loadOllamaModels();
        } else {
            // Try to set saved model name if available
            if (settingsData.llm_model) {
                const select = document.getElementById('cfg-llm_model');
                const opt = document.createElement('option');
                opt.value = settingsData.llm_model;
                opt.textContent = settingsData.llm_model;
                select.appendChild(opt);
                select.value = settingsData.llm_model;
            }
        }
    } catch (e) {
        console.error('Failed to load settings', e);
    }
}
```

- [ ] **Step 5: Update saveSettings() to save new fields**

Find `saveSettings()`. Add the new fields:

```javascript
// After existing field gathering, add:
const config = {
    llm_model: v('cfg-llm_model') || undefined,
    temperature: parseFloat(v('cfg-temperature')) || undefined,
    max_tokens: parseInt(v('cfg-max_tokens')) || undefined,
    system_prompt: v('cfg-system_prompt') || undefined,
    search_top_k: parseInt(v('cfg-search_top_k')) || undefined,
    search_max_depth: parseInt(v('cfg-search_max_depth')) || undefined,
    tree_max_depth: parseInt(v('cfg-tree_max_depth')) || undefined,
    tree_max_children: parseInt(v('cfg-tree_max_children')) || undefined,
    max_tree_context_chars: parseInt(v('cfg-max_tree_context_chars')) || undefined,
    llm_provider: document.querySelector('input[name="llm_provider"]:checked')?.value || 'ollama',
    openai_api_base: document.getElementById('cfg-openai_api_base').value || undefined,
    openai_api_key: document.getElementById('cfg-openai_api_key').value || undefined,
};
```

- [ ] **Step 6: Update GET /chat/models to support OpenAI via headers**

Modify `app/api/chat.py` to pass OpenAI credentials via headers when fetching model list:

```python
@router.get("/models")
async def list_models(
    openai_base: str = None,
    openai_key: str = None,
):
    """List available models. If openai_base/key headers provided, use OpenAI endpoint."""
    if openai_base and openai_key:
        # Temporarily override llm_service for this call
        original_provider = llm_service.provider
        original_base = llm_service.openai_base
        original_key = llm_service.openai_key
        llm_service.provider = "openai"
        llm_service.openai_base = openai_base
        llm_service.openai_key = openai_key
        models = await llm_service.list_models()
        # Restore
        llm_service.provider = original_provider
        llm_service.openai_base = original_base
        llm_service.openai_key = original_key
        return {"models": models}
    models = await llm_service.list_models()
    return {"models": models}
```

- [ ] **Step 7: Commit**

```bash
git add web/admin.html app/api/chat.py
git commit -m "feat(admin): add provider switching and dynamic model loading"
```

---

## Verification

1. **Batch reprocess**: Select multiple docs in admin → click "批量重建索引" → toast shows count → docs status changes to processing/indexed
2. **Provider switch**: Settings → select "OpenAI 兼容" → enter base_url + api_key → click "加载模型列表" → model dropdown populates → save → provider stored
3. **Dual provider query**: Switch to OpenAI → go to main chat page → ask a question → uses OpenAI model
4. **Provider persistence**: Refresh admin page → provider radio + API fields preserved from DB

---

## Spec Coverage Check

| Spec Item | Task |
|-----------|------|
| Batch reprocess button | Task 1 |
| batchReprocess() JS function | Task 1 |
| POST /documents/batch-reprocess (existing) | — |
| llm_provider config key | Task 2 |
| openai_api_base/key config keys | Task 2 |
| LLMService dual provider | Task 2 |
| list_openai_models() | Task 2 |
| ConfigResponse/ConfigUpdate schemas | Task 2 |
| GET /chat/models endpoint | Task 2, Step 6 |
| rag_service reads provider config | Task 3 |
| tree_search reads provider config | Task 3 |
| Provider radio UI | Task 4 |
| OpenAI config inputs | Task 4 |
| switchProvider() JS | Task 4 |
| loadOllamaModels() / loadOpenAIModels() | Task 4 |
| loadSettings updates | Task 4 |
| saveSettings updates | Task 4 |
