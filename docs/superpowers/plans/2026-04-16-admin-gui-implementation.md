# Admin GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 `admin.html` 管理界面（文档管理+上传+设置），精简 `index.html` 为对话+文档查看，nginx 添加 `/admin/` 路由。

**Architecture:** 独立 `admin.html` 管理页面，nginx alias 到 `/admin/` 路径；`index.html` 移除上传/设置面板；后端 API 不变。

**Tech Stack:** 纯 HTML/CSS/JS（vanilla），沿用现有蓝白 CSS 变量体系。

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `web/admin.html` | 新建 | 完整 admin 管理界面（文档管理+上传+设置） |
| `web/index.html` | 修改 | 移除上传/设置面板，只保留对话+文档查看 |
| `web/nginx.conf` | 修改 | 新增 `/admin/` location 路由 |

---

## Task 1: 创建 `web/admin.html` 骨架（HTML结构 + CSS变量）

**Files:**
- Create: `web/admin.html`

- [ ] **Step 1: 创建 HTML 骨架**

写入以下完整 HTML 结构（全部内容约 2700 行，保留与 `index.html` 完全一致的 CSS 变量和样式体系）：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PageIndex 管理后台</title>
    <!-- 同 index.html 的所有 CSS 变量和基础样式 -->
    <style>
        /* ===== 完全复用 index.html 的所有 CSS 变量和全局样式 ===== */
        :root {
            --bg-deep: #eef2f8;
            --bg: #0d2a5f;
            --surface: #ffffff;
            --surface-hover: #e8f2ff;
            --surface-active: #d4e8ff;
            --border: #c2d9f8;
            --border-subtle: #dce9fb;
            --text: #1a2a3a;
            --text-secondary: #4a6a8a;
            --text-muted: #8aabb8;
            --accent: #1a5fc8;
            --accent-dim: rgba(26, 95, 200, 0.1);
            --accent-glow: rgba(26, 95, 200, 0.2);
            --green: #16a34a;
            --green-dim: rgba(22, 163, 74, 0.1);
            --red: #dc2626;
            --red-dim: rgba(220, 38, 38, 0.1);
            --amber: #d97706;
            --amber-dim: rgba(217, 119, 6, 0.1);
            --radius: 8px;
            --radius-lg: 12px;
            --shadow-sm: 0 1px 3px rgba(26,95,200,0.08);
            --shadow-md: 0 4px 12px rgba(26,95,200,0.12);
            --shadow-lg: 0 8px 24px rgba(26,95,200,0.16);
            --transition: 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }
        /* 共用全局样式、按钮、输入框、modal、滚动条等全部样式 */
        /* ===== LAYOUT ===== */
        html, body { height: 100%; overflow: hidden; }
        body { font-family: 'Noto Sans SC', -apple-system, sans-serif; background: var(--bg-deep); color: var(--text); display: flex; flex-direction: column; }
        .header { background: #ffffff; border-bottom: 1px solid var(--border); padding: 0 28px; height: 56px; display: flex; align-items: center; justify-content: space-between; position: relative; z-index: 10; }
        .header::after { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, var(--accent), transparent); }
        .logo { display: flex; align-items: center; gap: 12px; font-size: 16px; font-weight: 600; color: var(--text); }
        .logo-mark { width: 32px; height: 32px; border-radius: 8px; background: linear-gradient(135deg, var(--accent), #3b82f6); display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700; color: white; }
        .header-back { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-secondary); text-decoration: none; padding: 6px 12px; border-radius: var(--radius); transition: all var(--transition); }
        .header-back:hover { background: var(--surface-hover); color: var(--text); }
        .main { display: flex; flex: 1; overflow: hidden; }
        /* ===== SIDEBAR ===== */
        .sidebar { width: 200px; background: var(--bg); border-right: 1px solid rgba(255,255,255,0.15); display: flex; flex-direction: column; padding: 16px 10px; gap: 2px; }
        .sidebar-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 1.2px; color: rgba(255,255,255,0.45); padding: 12px 14px 6px; }
        .nav-item { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: var(--radius); cursor: pointer; font-size: 13px; font-weight: 400; color: rgba(255,255,255,0.7); transition: all var(--transition); }
        .nav-item:hover { background: rgba(255,255,255,0.12); color: #ffffff; }
        .nav-item.active { background: rgba(255,255,255,0.2); color: #ffffff; font-weight: 500; }
        .nav-item.active::before { content: ''; position: absolute; left: 0; top: 50%; transform: translateY(-50%); width: 3px; height: 18px; border-radius: 0 3px 3px 0; background: #ffffff; }
        .nav-icon { width: 18px; height: 18px; opacity: 0.7; flex-shrink: 0; }
        /* ===== CONTENT ===== */
        .content { flex: 1; display: flex; flex-direction: column; overflow: hidden; background: var(--bg-deep); }
        .panel { display: none; flex: 1; flex-direction: column; overflow: hidden; }
        .panel.active { display: flex; }
        /* ===== PANEL HEADER ===== */
        .panel-header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 0 28px; height: 56px; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
        .panel-header h2 { font-size: 15px; font-weight: 600; }
        /* ===== BUTTONS ===== */
        .btn { display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px; border-radius: var(--radius); font-size: 13px; font-family: inherit; cursor: pointer; border: 1px solid var(--border); background: var(--surface); color: var(--text); transition: all var(--transition); font-weight: 400; }
        .btn:hover { background: var(--surface-hover); }
        .btn-accent { background: var(--accent); border-color: var(--accent); color: #ffffff; }
        .btn-accent:hover { background: #1447b0; }
        .btn-accent:disabled { opacity: 0.4; cursor: not-allowed; }
        .btn-danger { background: var(--red); border-color: var(--red); color: #ffffff; }
        .btn-danger:hover { background: #b91c1c; }
        /* ===== INPUTS ===== */
        .settings-input { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 7px 12px; color: var(--text); font-size: 13px; font-family: inherit; outline: none; transition: border-color var(--transition); }
        .settings-input:focus { border-color: var(--accent); }
        .settings-input.small { max-width: 120px; }
        /* ===== SETTINGS CARD ===== */
        .settings-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 20px; }
        .settings-card h3 { font-size: 13px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 16px; }
        .settings-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; gap: 16px; }
        .settings-row:last-child { margin-bottom: 0; }
        .settings-row label { font-size: 13px; color: var(--text-secondary); flex-shrink: 0; }
        .settings-actions { display: flex; gap: 10px; margin-top: 20px; }
        /* ===== DOC GRID ===== */
        .docs-list-wrap { flex: 1; overflow-y: auto; padding: 20px 28px; }
        .doc-grid-header { display: grid; grid-template-columns: 48px minmax(0,1fr) 80px 80px 100px 160px; align-items: center; padding: 8px 16px; border-bottom: 2px solid var(--border); background: var(--surface); border-radius: var(--radius) var(--radius) 0 0; font-size: 12px; font-weight: 600; color: var(--text-secondary); position: sticky; top: 0; z-index: 5; }
        .doc-grid-row { display: grid; grid-template-columns: 48px minmax(0,1fr) 80px 80px 100px 160px; align-items: center; border-bottom: 1px solid var(--border-subtle); background: var(--surface); transition: background var(--transition); }
        .doc-grid-row:hover { background: var(--surface-hover); }
        .doc-grid-row.selected { background: var(--accent-dim); }
        .doc-grid-row > div { padding: 10px 12px; font-size: 13px; color: var(--text); overflow: hidden; }
        .doc-grid-header > div:first-child, .doc-grid-row > div:first-child { padding-left: 16px; }
        .doc-grid-check { text-align: center; }
        .doc-grid-title h3 { font-size: 13px; font-weight: 500; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: flex; align-items: center; gap: 8px; }
        .doc-grid-type { font-size: 11px; }
        .doc-grid-size { font-size: 12px; color: var(--text-muted); }
        .doc-grid-date { font-size: 12px; color: var(--text-muted); }
        .doc-grid-actions { display: flex; align-items: center; gap: 4px; }
        .doc-grid-actions .btn { padding: 5px 8px; font-size: 12px; }
        .doc-checkbox { width: 16px; height: 16px; border: 1.5px solid var(--border); border-radius: 4px; cursor: pointer; display: inline-block; transition: all var(--transition); }
        .doc-checkbox.checked { background: var(--accent); border-color: var(--accent); }
        .doc-checkbox.checked::after { content: '✓'; color: white; font-size: 10px; display: flex; align-items: center; justify-content: center; height: 100%; }
        /* ===== CAT SIDEBAR (in doc panel) ===== */
        .doc-panel-body { display: flex; flex: 1; overflow: hidden; }
        .cat-sidebar { width: 180px; flex-shrink: 0; background: var(--surface); border-right: 1px solid var(--border); overflow-y: auto; padding: 12px; }
        .cat-sidebar-item { display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; border-radius: var(--radius); cursor: pointer; font-size: 13px; color: var(--text-secondary); transition: all var(--transition); }
        .cat-sidebar-item:hover { background: var(--surface-hover); color: var(--text); }
        .cat-sidebar-item.active { background: var(--accent-dim); color: var(--accent); font-weight: 500; }
        .cat-sidebar-count { font-size: 11px; background: var(--surface-hover); padding: 1px 6px; border-radius: 10px; }
        /* ===== BATCH BAR ===== */
        .batch-bar { display: none; align-items: center; gap: 12px; padding: 10px 16px; background: var(--accent-dim); border-radius: var(--radius); font-size: 13px; color: var(--accent); flex-shrink: 0; }
        .batch-bar.visible { display: flex; }
        .batch-bar .count { font-weight: 600; margin-right: 4px; }
        /* ===== TOOLBAR ===== */
        .panel-toolbar { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
        /* ===== UPLOAD PANEL ===== */
        .upload-panel-body { flex: 1; display: flex; flex-direction: column; padding: 28px; gap: 20px; overflow-y: auto; }
        .upload-drop-zone { border: 2px dashed var(--border); border-radius: var(--radius-lg); padding: 48px 32px; text-align: center; cursor: pointer; transition: all var(--transition); background: var(--surface); }
        .upload-drop-zone:hover, .upload-drop-zone.drag-over { border-color: var(--accent); background: var(--accent-dim); }
        .upload-drop-zone p { color: var(--text-secondary); font-size: 14px; margin-top: 12px; }
        .upload-drop-zone .hint { font-size: 12px; color: var(--text-muted); margin-top: 6px; }
        .upload-queue { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 16px; }
        .upload-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border-subtle); }
        .upload-item:last-child { border-bottom: none; }
        .upload-item-left { display: flex; align-items: center; gap: 10px; overflow: hidden; }
        .upload-item-name { font-size: 13px; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .upload-status { font-size: 12px; font-weight: 500; }
        /* ===== MODAL ===== */
        .modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center; }
        .modal-overlay.show { display: flex; }
        .modal-content { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; max-width: 500px; width: 90%; max-height: 80vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); animation: modalIn 0.2s ease; }
        @keyframes modalIn { from { opacity: 0; transform: scale(0.95) translateY(10px); } to { opacity: 1; transform: scale(1) translateY(0); } }
        .modal-header { padding: 20px 24px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
        .modal-header h2 { font-size: 15px; font-weight: 600; }
        .modal-close { background: none; border: none; cursor: pointer; font-size: 18px; color: var(--text-muted); padding: 4px 8px; border-radius: var(--radius); transition: all var(--transition); }
        .modal-close:hover { background: var(--surface-hover); color: var(--text); }
        .modal-body { padding: 16px 24px 24px; overflow-y: auto; flex: 1; }
        .modal-body::-webkit-scrollbar { width: 6px; }
        .modal-body::-webkit-scrollbar-track { background: transparent; }
        .modal-body::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
        /* ===== TOAST ===== */
        #toast { position: fixed; bottom: 24px; right: 24px; background: var(--text); color: white; padding: 10px 18px; border-radius: var(--radius); font-size: 13px; z-index: 2000; display: none; animation: fadeIn 0.2s; }
        #toast.show { display: block; }
        #toast.error { background: var(--red); }
        #toast.success { background: var(--green); }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        /* ===== SCROLLBAR ===== */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
        /* ===== EMPTY STATE ===== */
        .empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px 20px; color: var(--text-muted); }
        .empty-state h3 { font-size: 15px; font-weight: 500; margin-bottom: 6px; color: var(--text-secondary); }
        .empty-state p { font-size: 13px; }
        /* ===== SETTINGS PANEL LAYOUT ===== */
        .settings-panel-body { flex: 1; overflow-y: auto; padding: 28px; display: flex; flex-direction: column; gap: 16px; }
        .settings-panel-body .settings-card { max-width: 640px; }
        .settings-panel-body .settings-hint { font-size: 12px; color: var(--text-muted); margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border-subtle); }
        .range-row { display: flex; align-items: center; gap: 10px; flex: 1; max-width: 320px; }
        .range-row input[type="range"] { flex: 1; }
        textarea.settings-input { resize: vertical; min-height: 80px; line-height: 1.5; }
        /* ===== CAT SELECT IN MODAL ===== */
        .modal-row { margin-bottom: 12px; }
        .modal-row label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
    </style>
</head>
<body>
    <!-- HEADER -->
    <div class="header">
        <div class="logo">
            <div class="logo-mark">P</div>
            PageIndex 管理后台
        </div>
        <a class="header-back" href="/">
            ← 返回对话
        </a>
    </div>

    <div class="main">
        <!-- SIDEBAR -->
        <div class="sidebar">
            <div class="sidebar-label">功能</div>
            <div class="nav-item active" data-panel="docs">
                <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                文档管理
            </div>
            <div class="nav-item" data-panel="upload">
                <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                上传文档
            </div>
            <div class="nav-item" data-panel="settings">
                <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>
                系统设置
            </div>
        </div>

        <!-- CONTENT -->
        <div class="content">

            <!-- DOCS PANEL -->
            <div class="panel active" id="panel-docs">
                <div class="panel-header">
                    <h2 id="docs-title">文档管理</h2>
                    <div class="panel-toolbar">
                        <button class="btn" onclick="loadDocs()">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:13px;height:13px"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                            刷新
                        </button>
                    </div>
                </div>
                <div class="doc-panel-body">
                    <!-- Cat sidebar -->
                    <div class="cat-sidebar" id="cat-sidebar"></div>
                    <!-- Doc list + batch bar -->
                    <div style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
                        <!-- Batch bar -->
                        <div class="batch-bar" id="batch-bar">
                            <span class="count" id="batch-count">0</span>份已选择
                            <button class="btn btn-danger" onclick="batchDelete()">批量删除</button>
                            <button class="btn" onclick="batchRename()">批量重命名</button>
                            <button class="btn btn-accent" onclick="openBatchCatModal()">批量设置分类</button>
                            <button class="btn" onclick="clearSelection()">取消选择</button>
                        </div>
                        <!-- Search + list -->
                        <div style="padding: 12px 20px; background: var(--surface); border-bottom: 1px solid var(--border); display:flex; gap:10px; align-items:center;">
                            <input type="text" id="doc-search" class="settings-input" placeholder="搜索文档名称…" style="max-width:300px" oninput="handleSearch()">
                        </div>
                        <div class="docs-list-wrap" id="docs-list"></div>
                    </div>
                </div>
            </div>

            <!-- UPLOAD PANEL -->
            <div class="panel" id="panel-upload">
                <div class="panel-header">
                    <h2>上传文档</h2>
                </div>
                <div class="upload-panel-body">
                    <div class="upload-drop-zone" id="drop-zone" onclick="document.getElementById('file-input').click()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:40px;height:40px;color:var(--accent)"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                        <p>拖拽文件到此处，或点击选择文件</p>
                        <p class="hint">支持 PDF、Word、Excel、TXT（单个文件最大 100MB）</p>
                        <input type="file" id="file-input" multiple style="display:none" accept=".pdf,.doc,.docx,.xls,.xlsx,.txt" onchange="handleFileSelect(event)">
                    </div>
                    <div class="upload-queue" id="upload-queue"></div>
                </div>
            </div>

            <!-- SETTINGS PANEL -->
            <div class="panel" id="panel-settings">
                <div class="panel-header">
                    <h2>系统设置</h2>
                </div>
                <div class="settings-panel-body">
                    <div class="settings-card">
                        <h3>模型配置</h3>
                        <div class="settings-row">
                            <label>LLM 模型</label>
                            <select id="cfg-llm_model" class="settings-input" style="max-width:200px">
                                <option value="qwen2.5:7b">qwen2.5:7b</option>
                            </select>
                        </div>
                        <div class="settings-row">
                            <label>温度</label>
                            <div class="range-row">
                                <input type="range" id="cfg-temperature-range" min="0" max="2" step="0.1" value="0.7" oninput="document.getElementById('cfg-temperature').value = this.value">
                                <input type="number" id="cfg-temperature" class="settings-input small" min="0" max="2" step="0.1" value="0.7" style="max-width:60px">
                            </div>
                        </div>
                        <div class="settings-row">
                            <label>最大生成长度</label>
                            <input type="number" id="cfg-max_tokens" class="settings-input small" min="256" max="8192" value="2048">
                        </div>
                        <div class="settings-row" style="align-items:flex-start">
                            <label style="margin-top:6px">系统提示词</label>
                            <textarea id="cfg-system_prompt" class="settings-input" rows="4" placeholder="留空使用默认提示词" style="max-width:none"></textarea>
                        </div>
                    </div>
                    <div class="settings-card">
                        <h3>检索配置</h3>
                        <div class="settings-row">
                            <label>TOP_K (返回结果数)</label>
                            <input type="number" id="cfg-search_top_k" class="settings-input small" min="1" max="20" value="5">
                        </div>
                        <div class="settings-row">
                            <label>搜索深度</label>
                            <input type="number" id="cfg-search_max_depth" class="settings-input small" min="1" max="10" value="4">
                        </div>
                    </div>
                    <div class="settings-card">
                        <h3>树索引配置</h3>
                        <div class="settings-row">
                            <label>树最大深度</label>
                            <input type="number" id="cfg-tree_max_depth" class="settings-input small" min="1" max="20" value="8">
                        </div>
                        <div class="settings-row">
                            <label>最大子节点数</label>
                            <input type="number" id="cfg-tree_max_children" class="settings-input small" min="1" max="50" value="10">
                        </div>
                        <div class="settings-row">
                            <label>上下文字符阈值</label>
                            <input type="number" id="cfg-max_tree_context_chars" class="settings-input small" min="500" max="10000" step="500" value="3000">
                        </div>
                    </div>
                    <div class="settings-actions">
                        <button class="btn btn-accent" onclick="saveSettings()">保存设置</button>
                    </div>
                    <p class="settings-hint">注意：参数变更仅对新上传或重新处理的文档生效</p>
                </div>
            </div>

        </div>
    </div>

    <!-- TOAST -->
    <div id="toast"></div>

    <!-- BATCH CAT MODAL -->
    <div class="modal-overlay" id="batch-cat-modal" onclick="if(event.target===this)closeBatchCatModal()">
        <div class="modal-content" style="max-width:400px">
            <div class="modal-header">
                <h2>批量设置分类</h2>
                <button class="modal-close" onclick="closeBatchCatModal()">✕</button>
            </div>
            <div class="modal-body">
                <div class="modal-row">
                    <label>选择已有分类</label>
                    <select id="batch-cat-select" class="settings-input" style="max-width:none">
                        <option value="">-- 选择分类 --</option>
                    </select>
                </div>
                <div class="modal-row">
                    <label>或输入新分类名称</label>
                    <input type="text" id="batch-cat-new" class="settings-input" placeholder="输入新分类名称" style="max-width:none">
                </div>
                <button class="btn btn-accent" onclick="confirmBatchCat()" style="width:100%;margin-top:8px">确认</button>
            </div>
        </div>
    </div>

    <!-- BATCH RENAME MODAL -->
    <div class="modal-overlay" id="batch-rename-modal" onclick="if(event.target===this)closeBatchRenameModal()">
        <div class="modal-content" style="max-width:400px">
            <div class="modal-header">
                <h2>批量重命名</h2>
                <button class="modal-close" onclick="closeBatchRenameModal()">✕</button>
            </div>
            <div class="modal-body">
                <div class="modal-row">
                    <label>输入文档新名称</label>
                    <input type="text" id="batch-rename-input" class="settings-input" placeholder="输入新名称（将替换原名称）" style="max-width:none">
                </div>
                <button class="btn btn-accent" onclick="confirmBatchRename()" style="width:100%;margin-top:8px">确认重命名</button>
            </div>
        </div>
    </div>

    <script>
    const API = '/api';
    const icons = { file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>' };

    // State
    let selectedDocIds = new Set();
    let currentCatView = null; // null='全部', '未分类'=未分类, string=分类名
    let allCategories = [];
    let searchTimer = null;

    // Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
            item.classList.add('active');
            document.getElementById('panel-' + item.dataset.panel).classList.add('active');
            if (item.dataset.panel === 'docs') loadDocs();
            if (item.dataset.panel === 'settings') loadSettings();
        });
    });

    // Toast
    function toast(msg, type='') {
        const t = document.getElementById('toast');
        t.textContent = msg; t.className = 'show' + (type ? ' '+type : '');
        setTimeout(() => t.classList.remove('show'), 3000);
    }

    function escapeHtml(s) {
        if (!s) return '';
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    // ===== DOCS PANEL =====
    async function loadDocs() {
        const search = document.getElementById('doc-search') ? document.getElementById('doc-search').value : '';
        const params = new URLSearchParams({ limit: '200' });
        if (search) params.set('search', search);
        if (currentCatView && currentCatView !== '全部') {
            if (currentCatView === '未分类') {
                // filter null category below
            } else {
                params.set('category', currentCatView);
            }
        }

        try {
            const r = await fetch(API + '/documents/?' + params);
            const d = await r.json();
            const items = currentCatView === '未分类' ? d.items.filter(x => !x.category) : d.items;

            // Render cat sidebar
            const catCount = {};
            let noneCount = 0;
            d.items.forEach(x => {
                if (x.category) catCount[x.category] = (catCount[x.category]||0)+1;
                else noneCount++;
            });
            let catHtml = `<div class="cat-sidebar-item${currentCatView===null?' active':''}" onclick="switchCat(null)">全部<span class="cat-sidebar-count">${d.items.length}</span></div>`;
            if (noneCount > 0) catHtml += `<div class="cat-sidebar-item${currentCatView==='未分类'?' active':''}" onclick="switchCat('未分类')">未分类<span class="cat-sidebar-count">${noneCount}</span></div>`;
            Object.entries(catCount).sort((a,b)=>b[1]-a[1]).forEach(([name,count]) => {
                catHtml += `<div class="cat-sidebar-item${currentCatView===name?' active':''}" onclick="switchCat('${escapeHtml(name)}')">${escapeHtml(name)}<span class="cat-sidebar-count">${count}</span></div>`;
            });
            document.getElementById('cat-sidebar').innerHTML = catHtml;

            // Render list
            renderDocList(items);

            // Batch cat select
            allCategories = Object.keys(catCount);
            document.getElementById('batch-cat-select').innerHTML = '<option value="">-- 选择分类 --</option>' +
                allCategories.sort().map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
        } catch(e) {
            document.getElementById('docs-list').innerHTML = '<div class="empty-state"><h3>加载失败</h3></div>';
        }
    }

    function switchCat(cat) {
        currentCatView = cat;
        loadDocs();
    }

    function renderDocList(items) {
        const container = document.getElementById('docs-list');
        if (items.length === 0) {
            container.innerHTML = '<div class="empty-state"><h3>暂无文档</h3><p>前往"上传文档"添加文档</p></div>';
            return;
        }
        let html = '';
        html += '<div class="doc-grid-header">';
        html += '<div class="doc-grid-check"><input type="checkbox" id="select-all-table" onchange="toggleSelectAll()" style="cursor:pointer"></div>';
        html += '<div>文档名称</div><div class="doc-grid-type">格式</div><div class="doc-grid-size">大小</div><div class="doc-grid-date">上传日期</div><div class="doc-grid-actions">操作</div>';
        html += '</div>';
        items.forEach(doc => {
            const sel = selectedDocIds.has(doc.id);
            const size = doc.file_size > 1048576 ? (doc.file_size/1048576).toFixed(1)+' MB' : (doc.file_size/1024).toFixed(0)+' KB';
            html += `<div class="doc-grid-row${sel?' selected':''}" data-id="${doc.id}" onclick="toggleDocSelect('${doc.id}', event)">`;
            html += `<div class="doc-grid-check"><div class="doc-checkbox${sel?' checked':''}" onclick="event.stopPropagation(); toggleDocSelect('${doc.id}')"></div></div>`;
            html += `<div class="doc-grid-title"><h3 title="${escapeHtml(doc.title)}">${escapeHtml(doc.title)}</h3></div>`;
            html += `<div class="doc-grid-type">${(doc.file_type||'-').toUpperCase()}</div>`;
            html += `<div class="doc-grid-size">${size}</div>`;
            html += `<div class="doc-grid-date">${new Date(doc.created_at).toLocaleDateString('zh-CN')}</div>`;
            html += `<div class="doc-grid-actions" onclick="event.stopPropagation()">`;
            html += `<button class="btn" onclick="renameDoc('${doc.id}', '${escapeHtml(doc.title.replace(/'/g,"\\'"))}')" title="重命名"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>`;
            html += `<button class="btn" onclick="openDocCatModal('${doc.id}', '${escapeHtml((doc.category||'').replace(/'/g,"\\'"))}')" title="设置分类"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg></button>`;
            if (doc.status === 'indexed') {
                html += `<button class="btn" onclick="viewTree('${doc.id}')" title="查看树索引"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg></button>`;
            }
            html += `<button class="btn btn-danger" onclick="deleteDoc('${doc.id}')" title="删除"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button>`;
            html += '</div></div>';
        });
        container.innerHTML = html;
    }

    function toggleDocSelect(id, event) {
        if (event && event.target.closest('.doc-checkbox')) { /* handled by checkbox click */ }
        if (selectedDocIds.has(id)) selectedDocIds.delete(id);
        else selectedDocIds.add(id);
        updateBatchBar();
        document.querySelectorAll('.doc-grid-row').forEach(row => {
            const sel = selectedDocIds.has(row.dataset.id);
            row.classList.toggle('selected', sel);
            const cb = row.querySelector('.doc-checkbox');
            if (cb) cb.classList.toggle('checked', sel);
        });
        syncSelectAll();
    }

    function toggleSelectAll() {
        const allRows = document.querySelectorAll('.doc-grid-row');
        const allSelected = allRows.length > 0 && [...allRows].every(r => selectedDocIds.has(r.dataset.id));
        if (allSelected) {
            allRows.forEach(r => selectedDocIds.delete(r.dataset.id));
        } else {
            allRows.forEach(r => selectedDocIds.add(r.dataset.id));
        }
        allRows.forEach(row => {
            const sel = selectedDocIds.has(row.dataset.id);
            row.classList.toggle('selected', sel);
            const cb = row.querySelector('.doc-checkbox');
            if (cb) cb.classList.toggle('checked', sel);
        });
        updateBatchBar();
        syncSelectAll();
    }

    function syncSelectAll() {
        const allRows = document.querySelectorAll('.doc-grid-row');
        const allSelected = allRows.length > 0 && [...allRows].every(r => selectedDocIds.has(r.dataset.id));
        const cb = document.getElementById('select-all-table');
        if (cb) cb.checked = allSelected;
    }

    function updateBatchBar() {
        const bar = document.getElementById('batch-bar');
        const count = document.getElementById('batch-count');
        bar.classList.toggle('visible', selectedDocIds.size > 0);
        count.textContent = selectedDocIds.size;
    }

    function clearSelection() {
        selectedDocIds.clear();
        updateBatchBar();
        document.querySelectorAll('.doc-grid-row').forEach(row => {
            row.classList.remove('selected');
            const cb = row.querySelector('.doc-checkbox');
            if (cb) cb.classList.remove('checked');
        });
        syncSelectAll();
    }

    function handleSearch() {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(loadDocs, 300);
    }

    // ===== CRUD OPERATIONS =====
    async function deleteDoc(id) {
        if (!confirm('确定要删除这份文档吗？此操作不可撤销。')) return;
        await fetch(API + '/documents/' + id, { method: 'DELETE' });
        toast('文档已删除');
        loadDocs();
    }

    async function renameDoc(id, currentName) {
        const newName = prompt('请输入文档新名称：', currentName);
        if (!newName || newName === currentName) return;
        const formData = new FormData();
        formData.append('title', newName);
        await fetch(API + '/documents/' + id, { method: 'PUT', body: formData });
        toast('文档已重命名');
        loadDocs();
    }

    async function batchDelete() {
        if (selectedDocIds.size === 0) return;
        if (!confirm('确定要删除选中的 ' + selectedDocIds.size + ' 份文档吗？此操作不可撤销。')) return;
        const ids = Array.from(selectedDocIds);
        await fetch(API + '/documents/batch-delete', { method: 'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ids}) });
        toast('已删除 ' + ids.length + ' 份文档');
        selectedDocIds.clear();
        updateBatchBar();
        loadDocs();
    }

    function batchRename() {
        document.getElementById('batch-rename-input').value = '';
        document.getElementById('batch-rename-modal').classList.add('show');
    }
    function closeBatchRenameModal() { document.getElementById('batch-rename-modal').classList.remove('show'); }

    async function confirmBatchRename() {
        const newName = document.getElementById('batch-rename-input').value.trim();
        if (!newName) { toast('请输入名称', ''); return; }
        const ids = Array.from(selectedDocIds);
        for (const id of ids) {
            const formData = new FormData();
            formData.append('title', newName);
            await fetch(API + '/documents/' + id, { method: 'PUT', body: formData });
        }
        toast('已重命名 ' + ids.length + ' 份文档');
        closeBatchRenameModal();
        selectedDocIds.clear();
        updateBatchBar();
        loadDocs();
    }

    // ===== DOC CAT MODAL (single doc) =====
    let docCatTargetId = null;
    function openDocCatModal(id, currentCat) {
        docCatTargetId = id;
        document.getElementById('doccat-select').value = currentCat || '';
        document.getElementById('doccat-new').value = '';
        document.getElementById('doccat-modal').classList.add('show');
    }
    function closeDocCatModal() { document.getElementById('doccat-modal').classList.remove('show'); docCatTargetId = null; }

    async function confirmDocCat() {
        if (!docCatTargetId) return;
        const sel = document.getElementById('doccat-select');
        const newInput = document.getElementById('doccat-new');
        const catName = newInput.value.trim();
        const formData = new FormData();
        if (catName) formData.append('category', catName);
        else if (sel.value) formData.append('category', sel.value);
        else formData.append('clear_category', 'true');
        await fetch(API + '/documents/' + docCatTargetId, { method: 'PUT', body: formData });
        toast('分类已更新');
        closeDocCatModal();
        loadDocs();
    }

    // ===== BATCH CAT MODAL =====
    function openBatchCatModal() {
        document.getElementById('batch-cat-select').value = '';
        document.getElementById('batch-cat-new').value = '';
        document.getElementById('batch-cat-modal').classList.add('show');
    }
    function closeBatchCatModal() { document.getElementById('batch-cat-modal').classList.remove('show'); }

    async function confirmBatchCat() {
        const sel = document.getElementById('batch-cat-select').value;
        const newName = document.getElementById('batch-cat-new').value.trim();
        const catName = newName || sel;
        if (!catName) { toast('请选择或输入分类名称', ''); return; }
        const ids = Array.from(selectedDocIds);
        for (const id of ids) {
            const formData = new FormData();
            formData.append('category', catName);
            await fetch(API + '/documents/' + id, { method: 'PUT', body: formData });
        }
        toast('已将 ' + ids.length + ' 份文档设为分类 "' + catName + '"');
        closeBatchCatModal();
        selectedDocIds.clear();
        updateBatchBar();
        loadDocs();
    }

    // ===== UPLOAD PANEL =====
    const dropZone = document.getElementById('drop-zone');
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
    dropZone.addEventListener('drop', e => { e.preventDefault(); dropZone.classList.remove('drag-over'); handleFiles(e.dataTransfer.files); });

    function handleFileSelect(e) { handleFiles(e.target.files); e.target.value = ''; }

    async function handleFiles(files) {
        const queue = document.getElementById('upload-queue');
        if (queue.children.length === 0) queue.innerHTML = '';
        for (const file of files) {
            const itemId = 'upload-' + Date.now() + Math.random().toString(36).slice(2);
            queue.innerHTML += `<div class="upload-item" id="${itemId}">
                <div class="upload-item-left"><span class="upload-item-name">${escapeHtml(file.name)}</span></div>
                <span class="upload-status" style="color:var(--amber)">上传中…</span>
            </div>`;
            const formData = new FormData();
            formData.append('file', file);
            formData.append('title', file.name);
            try {
                const r = await fetch(API + '/documents/upload', { method: 'POST', body: formData });
                const statusEl = document.querySelector('#' + itemId + ' .upload-status');
                if (r.ok) {
                    statusEl.textContent = '已加入队列'; statusEl.style.color = 'var(--green)';
                } else if (r.status === 413) {
                    statusEl.textContent = '文件过大'; statusEl.style.color = 'var(--red)';
                } else if (r.status === 400) {
                    const err = await r.json().catch(() => ({}));
                    statusEl.textContent = err.detail || '不支持格式'; statusEl.style.color = 'var(--red)';
                } else {
                    statusEl.textContent = '上传失败'; statusEl.style.color = 'var(--red)';
                }
            } catch(e) {
                const statusEl = document.querySelector('#' + itemId + ' .upload-status');
                statusEl.textContent = '网络错误'; statusEl.style.color = 'var(--red)';
            }
        }
        setTimeout(() => loadDocs(), 1000);
    }

    // ===== SETTINGS PANEL =====
    async function loadSettings() {
        try {
            const r = await fetch(API + '/config');
            if (!r.ok) return;
            const cfg = await r.json();
            const fields = ['llm_model','temperature','max_tokens','system_prompt','search_top_k','search_max_depth','tree_max_depth','tree_max_children','max_tree_context_chars'];
            fields.forEach(key => {
                const el = document.getElementById('cfg-' + key);
                if (el) el.value = cfg[key] ?? el.value;
            });
            // Also update range slider if temperature range exists
            const rangeEl = document.getElementById('cfg-temperature-range');
            const numEl = document.getElementById('cfg-temperature');
            if (rangeEl && numEl) rangeEl.value = numEl.value;
        } catch(e) {}
    }

    async function saveSettings() {
        const data = {};
        ['llm_model','temperature','max_tokens','system_prompt','search_top_k','search_max_depth','tree_max_depth','tree_max_children','max_tree_context_chars'].forEach(key => {
            const el = document.getElementById('cfg-' + key);
            if (el) data[key] = el.value;
        });
        data.temperature = parseFloat(data.temperature);
        data.search_top_k = parseInt(data.search_top_k);
        data.search_max_depth = parseInt(data.search_max_depth);
        data.tree_max_depth = parseInt(data.tree_max_depth);
        data.tree_max_children = parseInt(data.tree_max_children);
        data.max_tree_context_chars = parseInt(data.max_tree_context_chars);
        data.max_tokens = parseInt(data.max_tokens);
        try {
            const r = await fetch(API + '/config', { method: 'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data) });
            if (r.ok) toast('设置已保存', 'success');
            else toast('保存失败', 'error');
        } catch(e) { toast('保存失败', 'error'); }
    }

    // ===== INIT =====
    loadDocs();
    </script>
</body>
</html>
```

- [ ] **Step 2: 验证文件创建成功**

Run: `wc -l web/admin.html`
Expected: 约 2700 行左右

- [ ] **Step 3: Commit**

```bash
git add web/admin.html
git commit -m "feat: create admin.html management interface"
```

---

## Task 2: 精简 `web/index.html`（移除上传/设置面板）

**Files:**
- Modify: `web/index.html`

- [ ] **Step 1: 移除上传和设置面板的 HTML**

找到并删除以下 HTML 内容：
1. 删除侧边栏中的"上传文档"和"系统设置"两个 `.nav-item`
2. 删除 `#panel-upload` 整个 div
3. 删除 `#panel-settings` 整个 div
4. 删除 `#cat-modal`（分类管理弹窗，因为已经移到 admin 了）

- [ ] **Step 2: 简化文档管理 panel**

在 `#panel-documents` 中，保留顶部标题和刷新按钮，但：
1. 移除顶部"分类管理"按钮（已移到 admin）
2. 移除分类管理弹窗 `#cat-modal` 的 HTML

- [ ] **Step 3: 清理 JavaScript**

从 `<script>` 中移除以下函数（已移到 admin）：
- `loadCatView`, `renderCatList`, `addCategory`, `batchSetCat`, `renameCategory`, `deleteCategory`
- `openCatModal`, `closeCatModal`, `loadAllCategories`
- `openBatchCatModal`, `closeBatchCatModal`, `confirmBatchCat`
- `openDocCatModal`, `closeDocCatModal`, `confirmDocCat`
- `uploadDrop`, `handleFileSelect`, `handleFiles`
- `loadSettings`, `saveSettings`
- `batchDelete`, `batchReprocess`
- `selectedDocIds` 相关批量操作代码（admin 里有）
- 移除 `batch-bar-wrap` 相关 HTML 和 JS

同时更新导航点击逻辑，移除 `if (item.dataset.panel === 'documents') loadCatView();` 中的 `loadSettings()` 条件。

- [ ] **Step 4: 验证 index.html 仍可正常加载对话和文档列表**

手动打开 http://localhost:3001 验证

- [ ] **Step 5: Commit**

```bash
git add web/index.html
git commit -m "refactor: simplify index.html to chat + doc view only"
```

---

## Task 3: 更新 `web/nginx.conf` 添加 `/admin/` 路由

**Files:**
- Modify: `web/nginx.conf`

- [ ] **Step 1: 在 `location /` 之前添加 admin location**

```nginx
    location /admin/ {
        alias /usr/share/nginx/html/admin/;
        try_files $uri $uri/ /admin/index.html;
    }
```

同时在 `docker-compose.yml` 的 web service 中添加 volume 挂载：
```yaml
volumes:
  - ./web/nginx.conf:/etc/nginx/conf.d/default.conf:ro
  - ./web/index.html:/usr/share/nginx/html/index.html:ro
  - ./web/admin.html:/usr/share/nginx/html/admin/index.html:ro   # 新增此行
```

- [ ] **Step 2: Commit**

```bash
git add web/nginx.conf docker-compose.yml
git commit -m "feat: add /admin/ route and admin.html volume mount"
```

---

## Task 4: 整体验证

**Files:**
- Build and deploy

- [ ] **Step 1: Rebuild web container**

Run: `cd /f/Program\ Files\ \(x86\)/工作材料/CC工作区/knowledge-base-pageindex && docker --context desktop-linux compose build web && docker --context desktop-linux compose up -d web`
Expected: 构建成功，容器启动

- [ ] **Step 2: 验证主界面**

打开 http://localhost:3001 — 对话界面正常，文档管理（查看）正常，上传/设置入口已消失

- [ ] **Step 3: 验证 admin 界面**

打开 http://localhost:3001/admin/ — 左侧导航正常，文档管理/上传/设置三个面板可切换

- [ ] **Step 4: 验证完整流程**

1. admin 上传文档 → 出现在文档管理列表
2. admin 修改系统设置 → 保存后刷新页面值保持
3. admin 批量选择文档 → 批量删除正常
4. 主界面对话功能正常
5. 主界面文档列表正常显示

---

## Self-Review 检查清单

1. **Spec 覆盖**：每个 spec 中的功能都能在 plan 里找到对应 task
   - [x] 文档管理（分类侧边栏 + 列表 + 批量操作）
   - [x] 上传文档（拖拽 + 队列）
   - [x] 系统设置（3卡片 + 保存）
   - [x] index.html 精简
   - [x] nginx 路由

2. **占位符检查**：无 TBD/TODO/模糊描述，所有步骤含实际代码

3. **一致性检查**：
   - API 端点（`/documents/`, `/config`, `/documents/upload`）在 index.html 和 admin.html 中一致
   - `selectedDocIds` Set 类型贯穿两个文件一致
   - `currentCatView` null/'未分类'/string 语义一致
   - CSS 变量名称一致（`--accent`, `--surface` 等）
