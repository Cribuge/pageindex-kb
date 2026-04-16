# PageIndex 知识库

基于 **PageIndex 层级树索引** 的本地知识库问答系统。无需向量数据库，通过文档结构树 + LLM 实现精准检索。

## 核心特性

- **PageIndex 树索引**：将文档解析为层级树结构，搜索时沿树分支精准定位相关章节
- **无向量架构**：不使用任何向量数据库，依赖关键词匹配 + 树结构 + LLM 重排
- **流式对话**：支持 SSE 流式输出，实时显示 LLM 回复
- **多格式支持**：PDF、Word(.doc/.docx)、Excel(.xls/.xlsx)、TXT、Markdown
- **文档管理**：分类管理、批量操作、重命名、重新索引
- **可配置参数**：模型选择、温度、TOP_K、树深度等均可通过界面调整

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│  Web (Nginx) — 静态页面，端口 3001                   │
├─────────────────────────────────────────────────────┤
│  API (FastAPI) — 文档上传、搜索问答、配置管理，端口 8001 │
├─────────────────────────────────────────────────────┤
│  Ollama — LLM 模型推理（qwen2.5:7b），端口 11434    │
├─────────────────────────────────────────────────────┤
│  PostgreSQL — 文档元数据、树节点、配置持久化，端口 5433 │
└─────────────────────────────────────────────────────┘
```

## 快速启动

### 前置要求

- Docker Desktop（已启动）
- Windows 系统（已验证）

### 启动服务

双击运行 `启动知识库.bat`，选择 `1` 启动所有服务。

或手动执行：

```bash
cd knowledge-base-pageindex
docker --context desktop-linux compose up -d
```

等待约 10 秒后访问：

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:3001 |
| API 文档 | http://localhost:8001/docs |
| Ollama | http://localhost:11434 |

### 停止服务

在 `启动知识库.bat` 中选择 `2`，或：

```bash
docker --context desktop-linux compose stop
```

## 使用流程

### 1. 上传文档

左侧导航点击 **上传文档**，拖拽或选择文件。支持 PDF、Word、Excel、TXT、Markdown，单文件最大 100MB。

上传后系统自动：
1. 提取文档全文
2. 构建 PageIndex 层级树
3. 存储树节点到数据库

### 2. 管理文档

左侧导航点击 **文档管理**：
- **分类卡片**：按分类统计文档数量，点击进入分类查看文档列表
- **批量操作**：勾选多个文档后可批量删除或重建索引
- **重命名**：点击文档行操作栏铅笔图标
- **设置分类**：点击文件夹图标，选择或新建分类
- **查看树索引**：点击图表图标，可视化查看该文档的树结构
- **删除**：点击删除图标

### 3. 智能对话

左侧导航点击 **智能对话**，输入问题。系统会：
1. 在已索引的文档中搜索相关内容
2. 结合检索上下文生成回答
3. 流式输出结果

### 4. 系统设置（规划中）

左侧导航点击 **系统设置**，可配置：
- LLM 模型（需 Ollama 已下载对应模型）
- Temperature、Max Tokens
- 检索参数（TOP_K、搜索深度）
- 树索引参数（最大深度、最大子节点数）

## 项目结构

```
knowledge-base-pageindex/
├── app/
│   ├── api/
│   │   ├── chat.py          # 对话 API（/chat/stream 流式问答）
│   │   ├── config.py        # 系统配置 API（GET/PUT /config）
│   │   └── document.py      # 文档管理 API（上传/删除/更新/树索引）
│   ├── core/
│   │   ├── config.py        # Pydantic Settings（所有配置项）
│   │   └── database.py      # SQLAlchemy Session 管理
│   ├── models/
│   │   ├── chat.py          # ChatHistory 模型
│   │   ├── config.py        # SystemConfig 键值对模型
│   │   └── document.py      # Document、TreeNode 模型
│   ├── schemas/
│   │   ├── chat.py          # ChatRequest/Response
│   │   ├── config.py        # ConfigUpdate/ConfigResponse
│   │   └── document.py      # DocumentResponse、TreeIndexResponse
│   ├── services/
│   │   ├── document_processor.py  # 文本提取（PDF/Word/Excel/TXT）
│   │   ├── ingestion.py     # 后台上传处理流程
│   │   ├── llm_service.py    # Ollama LLM 调用封装
│   │   ├── rag_service.py   # RAG 问答核心逻辑
│   │   ├── storage.py       # 文件存储服务
│   │   ├── tree_builder.py  # PageIndex 树构建（LLM 生成结构）
│   │   └── tree_search.py   # 树搜索（关键词 + LLM 选择分支）
│   ├── main.py              # FastAPI 应用入口
│   └── requirements.txt
├── web/
│   ├── index.html           # 前端单页应用（HTML/CSS/JS）
│   └── nginx.conf           # Nginx 配置（反向代理 + 上传限制）
├── scripts/
│   ├── init_db.py           # 数据库初始化
│   └── ingest.py            # 批量导入脚本
├── docker-compose.yml       # 容器编排配置
├── 启动知识库.bat            # Windows 启动菜单脚本
└── README.md
```

## 配置说明

### 环境变量（`app/core/config.py`）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `postgresql://...@postgres:5432/pageindex_kb` | 数据库连接 |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama 服务地址 |
| `LLM_MODEL` | `qwen2.5:7b` | 使用的 LLM 模型 |
| `UPLOAD_DIR` | `/app/uploads` | 文件存储目录 |
| `TREE_MAX_DEPTH` | `5` | 树索引最大深度 |
| `TREE_MAX_CHILDREN` | `10` | 每个节点最大子节点数 |
| `SEARCH_MAX_DEPTH` | `4` | 搜索时最大遍历深度 |
| `SEARCH_TOP_K` | `5` | 返回结果数量 |

### 更换 LLM 模型

1. 确保 Ollama 已下载模型：`ollama pull deepseek-r1:14b`
2. 修改 `docker-compose.yml` 中 `LLM_MODEL` 值
3. 重启 API：`docker --context desktop-linux compose up -d api`

## 数据库模型

### Document

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 主键 |
| `title` | String | 文档标题 |
| `file_path` | String | 存储路径 |
| `file_type` | String | 文件格式 |
| `category` | String | 分类（可为 null） |
| `status` | Enum | uploading/processing/tree_building/indexed/failed |
| `tree_index` | JSON | PageIndex 树结构 |
| `full_text` | Text | 提取的完整文本 |

### TreeNode

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 主键 |
| `document_id` | UUID | 关联文档 |
| `node_id` | String | 节点编号（如 "0001/0003"） |
| `title` | String | 章节标题 |
| `summary` | Text | LLM 生成的章节摘要 |
| `start_index` | Integer | 文本起始行 |
| `end_index` | Integer | 文本结束行 |
| `depth` | Integer | 树深度 |
| `path` | String |  materialized path |

## API 端点

### 文档管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/documents/upload` | 上传单个文档 |
| `POST` | `/documents/batch-upload` | 批量上传（最多20个） |
| `GET` | `/documents/` | 列出文档（支持 category/status/search 过滤） |
| `GET` | `/documents/{id}` | 获取文档详情 |
| `PUT` | `/documents/{id}` | 更新文档（标题/分类/标签） |
| `DELETE` | `/documents/{id}` | 删除文档 |
| `POST` | `/documents/batch-delete` | 批量删除 |
| `POST` | `/documents/batch-reprocess` | 批量重建索引 |
| `GET` | `/documents/{id}/tree` | 获取文档树索引 |

### 对话

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/chat/stream` | 流式对话（SSE） |

### 系统配置

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/config` | 获取所有配置项 |
| `PUT` | `/config` | 更新配置项 |

## 常见问题

**Q: 上传文档失败，显示"网络错误"？**
A: 检查是否为 413（文件过大，超过 100MB）或 400（不支持的文件格式）。确认 Docker Desktop 已启动。

**Q: 对话返回"暂无相关文档"？**
A: 确认文档状态为 `indexed`（已索引）。失败状态可进入文档管理手动重新处理。

**Q: 如何更换为其他 LLM 模型？**
A: 修改 `docker-compose.yml` 中 `LLM_MODEL`，并确保 Ollama 已下载该模型。

**Q: 文档处理很慢？**
A: 树索引构建依赖 LLM 推理速度。qwen2.5:7b 在 CPU 上处理一页 PDF 约需 1-2 秒。

## License

基于 PageIndex 架构构建。
