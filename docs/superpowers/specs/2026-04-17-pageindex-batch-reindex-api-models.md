# PageIndex 批量重建索引 + API 模型支持

## Context

当前 admin.html 的文档批量操作缺少"重建索引"功能；LLM 模型选择仅支持 Ollama，不支持 OpenAI 兼容 API。

## Goals

1. 文档管理模块增加"批量重建索引"按钮
2. LLM 服务支持 OpenAI 兼容 API（Azure OpenAI、AnyProxy 等）
3. 前端模型选择器动态加载可用模型

---

## 功能一：批量重建索引

### 后端

已有 `POST /documents/batch-reprocess` 端点（`app/api/document.py`），无需修改。

### 前端

在 `web/admin.html` 的 batch-bar（id=`batch-bar`）添加一个按钮：

```html
<button class="btn btn-secondary" onclick="batchReprocess()">批量重建索引</button>
```

JS 函数 `batchReprocess()`:
- 获取 `selectedDocIds` 集合
- 调用 `POST /documents/batch-reprocess`，body: `{"ids": [...selectedIds]}`
- 成功 toast → 刷新文档列表 + 状态轮询
- 失败 toast 报错

---

## 功能二：API 模型支持

### 新增配置项

存储到 `system_config` 表（键值对），同时以 `.env` 为默认值。

| 配置键 | 类型 | 说明 |
|--------|------|------|
| `llm_provider` | string | `ollama`（默认）或 `openai` |
| `openai_api_base` | string | API base URL（如 `https://api.openai.com/v1`） |
| `openai_api_key` | string | API key |

### 后端改造

**`app/core/config.py`** — 新增字段：
```python
LLMProvider: str = "ollama"  # ollama | openai
OpenAI_API_Base: str = "https://api.openai.com/v1"
OpenAI_API_Key: str = ""
```

**`app/services/llm_service.py`** — 重构 `LLMService`：

```python
class LLMService:
    async def generate(self, prompt, system=None, model=None, **kwargs) -> dict:
        if self.provider == "ollama":
            return await self._ollama_generate(...)
        elif self.provider == "openai":
            return await self._openai_generate(...)

    async def _openai_generate(self, prompt, system, model, **kwargs) -> dict:
        # POST {openai_api_base}/chat/completions
        # Headers: Authorization: Bearer {api_key}
        # Body: model, messages=[{role:"system",...},{role:"user",content:prompt}], stream=False
        # 返回 {"response": ...} 兼容格式
```

`generate_stream` 同理，调用 `/chat/completions` 的 stream 模式。

**新增 `list_openai_models()` 方法：**
```python
async def list_openai_models(self) -> List[dict]:
    # GET {openai_api_base}/models
    # Headers: Authorization: Bearer {api_key}
    # 返回 [{"name": "...", "id": "..."}, ...]
```

**`app/services/rag_service.py`** — 读取 `llm_provider`、`openai_api_base`、`openai_api_key` 构造 `LLMService` 时传入配置。

**`app/services/tree_search.py`** — 同上。

**`app/api/config.py`** — `ConfigResponse` 包含新增的三个配置项（`llm_provider`、`openai_api_base`、`openai_api_key`）。

### 前端改造

**系统设置"模型配置"卡片改为：**

1. **Provider 切换**：单选按钮（Ollama / OpenAI 兼容），切换时显示/隐藏 API 配置区
2. **Ollama 模式**：显示模型下拉框，调用 `/api/chat/models`（Ollama tags API）获取模型列表
3. **OpenAI 模式**：
   - 显示 `base_url` 输入框（id=`cfg-openai_api_base`）
   - 显示 `api_key` 输入框（密码类型，id=`cfg-openai_api_key`）
   - "加载模型"按钮 → 调用 `GET {base_url}/v1/models` → 填充模型下拉框
   - 模型下拉框（id=`cfg-llm_model`）动态 option

**loadSettings()**:
- 加载 `llm_provider` → 切换显示区域
- 加载 `llm_model` → 填充下拉框（若是 Ollama 则调 API 获取，OpenAI 则直接使用已保存的值）

**saveSettings()**:
- 保存 `llm_provider`、`openai_api_base`、`openai_api_key`、`llm_model` 到 `PUT /config`

**注意**：`openai_api_key` 在前端不做掩码处理（用户自行确保安全），GET /config 时后端原样返回 key（前端按需决定是否显示）。

---

## 实现步骤

### Step 1: 后端 - llm_service 重构
- 修改 `generate()` / `generate_stream()` 支持 OpenAI 格式
- 新增 `_openai_generate()` 和 `list_openai_models()`
- `__init__` 从 settings 读取 provider/base/key

### Step 2: 后端 - config.py
- 新增 `LLMProvider`、`OpenAI_API_Base`、`OpenAI_API_Key` 字段

### Step 3: 后端 - services 层
- `rag_service.py`、`tree_search.py` 读取新的 provider 配置

### Step 4: 后端 - config API
- `schemas/config.py` 的 `ConfigResponse` 包含新字段
- GET/PUT 端点不变（schema 自动扩展）

### Step 5: 前端 - batch reprocess
- batch-bar 添加按钮
- `batchReprocess()` 函数

### Step 6: 前端 - provider 切换 + 动态模型
- 添加 provider 切换 UI
- OpenAI 配置区（base_url、api_key 输入框）
- 动态加载模型列表

### Step 7: .env 示例
```
LLMProvider=ollama
OpenAI_API_Base=https://api.openai.com/v1
OpenAI_API_Key=
```
