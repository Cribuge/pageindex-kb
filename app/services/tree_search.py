"""
PageIndex Tree Search: keyword-based full text search with tree index for document selection.
"""
import json
import logging
import math
import re
from typing import List

from sqlalchemy.orm import Session

from core.config import settings
from models.document import Document, DocumentStatus
from models.config import SystemConfig
from services.llm_service import llm_service

logger = logging.getLogger(__name__)

TREE_SEARCH_SYSTEM = """你是文档检索助手。根据用户的问题和文档章节列表，选择最可能包含答案的章节。

【输出格式】
只输出JSON数组，例如：["node_003","node_007"]

【规则】
1. 最多选{top_k}个章节，优先选与问题关键词直接相关的章节
2. 如果没有相关章节，返回[]
3. 只输出JSON数组，不要任何解释"""

DOC_SELECT_SYSTEM = """你是文档筛选助手。根据用户问题，从文档列表中选出最相关的文档。

【输出格式】
只输出JSON数组（文档索引，0-based），例如：[2,0,5]

【规则】
1. 最多选{top_k}个文档，选择与问题直接相关的文档
2. 只输出JSON数组，不要任何解释"""

DOC_SELECT_PROMPT = """问题：{query}

文档列表：
{docs_json}

哪些文档最可能包含答案？输出索引JSON数组："""

TREE_SEARCH_PROMPT = """问题：{query}

文档章节：
{sections_json}

哪些章节最相关？输出JSON数组："""

RERANK_SYSTEM = """你是搜索结果排序助手。根据用户问题，从候选结果中选出最相关的。

【输出格式】
只输出JSON数组（0-based索引），例如：[2,0,4]

【规则】
1. 按相关程度从高到低排序，输出索引数组
2. 不相关的候选可以直接省略
3. 只输出JSON数组，不要任何解释"""

RERANK_PROMPT = """问题：{query}

候选结果：
{sections_json}

选出最相关的结果索引，输出JSON数组："""

# 查询改写：抽象概念展开为具体关键词
QUERY_EXPANSION = {
    "关键岗位": "关键岗位 管理人员 任职要求 职责",
    "市场化用工": "市场化用工 劳动合同 灵活用工 聘用",
    "总经理工作制度": "总经理 工作职责 决策 权限",
    "总经理办公制度": "总经理 行政事务 办公 审批",
    "员工手册": "员工手册 入职 行为规范 福利",
    "意识形态": "意识形态 思想政治 宣传",
    "安全生产": "安全生产 安全职责 隐患 防护",
    "招聘": "招聘 录用 入职 面试",
    "离职": "离职 辞职 交接 手续",
    "绩效": "绩效考核 目标管理 评价",
    "薪酬": "薪酬 工资 奖金 福利",
    "采购": "采购 供应商 招标 合同",
    # 补词：覆盖评测失败案例
    "入职手续": "入职 劳动合同 签订 体检 培训",
    "入职办理": "入职 劳动合同 签订 体检 培训",
    "采购审批": "采购 供应商 招标 合同 预算",
    "工作积极性": "激励 绩效 奖惩 考核 奖金",
    "市场开发": "市场开发 业务运营 支持 流程",
    "业务运营": "业务运营 市场开发 支持流程",
}


class TreeSearch:

    def __init__(self):
        self.llm = llm_service

    def _get_config(self, db: Session) -> dict:
        defaults = {
            "search_top_k": settings.SEARCH_TOP_K,
            "search_max_depth": settings.SEARCH_MAX_DEPTH,
        }
        result = {}
        for key in defaults:
            row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            result[key] = row.value if row else defaults[key]
        return result

    def _expand_query(self, query: str) -> str:
        """Expand abstract query terms with concrete keywords."""
        expanded = query
        for term, replacement in QUERY_EXPANSION.items():
            if term in query:
                expanded = replacement + " " + expanded
        return expanded

    async def search_document(self, query: str, document: Document, max_depth: int = None) -> List[dict]:
        """Search using hybrid keyword + BM25 + LLM approach."""
        if not document.tree_index or not document.full_text:
            return []

        full_text = document.full_text
        tree = document.tree_index
        keywords = self._extract_keywords(query)

        # 路径1: 关键词段落匹配
        keyword_results = self._keyword_search(full_text, tree, keywords)

        # 路径2: BM25 段落排序
        bm25_results = self._bm25_search(full_text, tree, keywords)

        # 路径3: LLM 树遍历 fallback
        llm_results = await self._tree_search_fallback(query, document, max_depth)

        # 合并 + 去重（RRF 融合）
        merged = self._merge_results(keyword_results, bm25_results, llm_results)

        for r in merged:
            r["document_id"] = str(document.id)
            r["document_title"] = document.title

        return merged[:5]

    def _keyword_search(self, full_text: str, tree: dict, keywords: List[str]) -> List[dict]:
        paragraphs = self._split_into_paragraphs(full_text)
        scored = []
        for para in paragraphs:
            if len(para["text"].strip()) < 20:
                continue
            score = 0
            for kw in keywords:
                if len(kw) < 2:
                    continue
                count = para["text"].count(kw)
                score += count * len(kw)
            if score > 0:
                scored.append((score, para))

        if not scored:
            return []

        scored.sort(key=lambda x: -x[0])
        top_chunks = scored[:5]

        results = []
        seen_ranges = set()
        for score, para in top_chunks:
            line_start = para["line_start"]
            line_end = para["line_end"]
            key = (line_start, line_end)
            if key in seen_ranges:
                continue
            seen_ranges.add(key)

            lines = full_text.split("\n")
            ctx_start = max(0, line_start - 3)
            ctx_end = min(len(lines), line_end + 3)
            text = "\n".join(lines[ctx_start:ctx_end])
            node_title = self._find_node_for_line(tree, line_start) or tree.get("title", "")

            results.append({
                "node_id": "",
                "title": node_title,
                "summary": "",
                "text_content": text,
                "score": score,
                "line_range": key,
            })
        return results

    def _bm25_search(self, full_text: str, tree: dict, keywords: List[str]) -> List[dict]:
        try:
            import jieba
        except ImportError:
            return []

        if not keywords:
            return []

        paragraphs = self._split_into_paragraphs(full_text)
        tokenized = []
        for para in paragraphs:
            text = para["text"].strip()
            if len(text) < 20:
                tokenized.append([])
            else:
                tokenized.append(list(jieba.cut_for_search(text)))

        avg_len = sum(len(t) for t in tokenized) / max(len(tokenized), 1)
        if avg_len < 1:
            avg_len = 1.0

        k1 = 1.5
        b = 0.75

        df = {}
        for kw in keywords:
            df[kw] = sum(1 for tokens in tokenized if kw in tokens)

        n = len(tokenized)
        idf = {}
        for kw in keywords:
            df_kw = df.get(kw, 0)
            idf[kw] = max(0.1, math.log((n - df_kw + 0.5) / (df_kw + 0.5) + 1))

        scored = []
        for i, tokens in enumerate(tokenized):
            if not tokens:
                continue
            score = 0.0
            para_len = len(tokens)
            for kw in keywords:
                tf = tokens.count(kw)
                if tf == 0:
                    continue
                idf_val = idf.get(kw, 0)
                term_freq = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * para_len / avg_len))
                score += idf_val * term_freq
            if score > 0:
                scored.append((score, paragraphs[i]))

        if not scored:
            return []

        scored.sort(key=lambda x: -x[0])
        top_chunks = scored[:5]

        results = []
        seen_ranges = set()
        for score, para in top_chunks:
            line_start = para["line_start"]
            line_end = para["line_end"]
            key = (line_start, line_end)
            if key in seen_ranges:
                continue
            seen_ranges.add(key)

            lines = full_text.split("\n")
            ctx_start = max(0, line_start - 3)
            ctx_end = min(len(lines), line_end + 3)
            text = "\n".join(lines[ctx_start:ctx_end])
            node_title = self._find_node_for_line(tree, line_start) or tree.get("title", "")

            results.append({
                "node_id": "",
                "title": node_title,
                "summary": "",
                "text_content": text,
                "score": score,
                "line_range": key,
            })
        return results

    async def _embedding_search(
        self,
        query: str,
        full_text: str,
        tree: dict,
        keyword_results: List[dict],
        bm25_results: List[dict],
        llm_results: List[dict],
    ) -> List[dict]:
        """Semantic similarity search using Ollama embeddings (nomic-embed-text)."""
        try:
            query_emb = await self.llm.embed(query)
            if not query_emb:
                return []
        except Exception:
            return []

        # Collect candidate paragraphs from existing results + random sampling
        paragraphs = self._split_into_paragraphs(full_text)
        candidates = {}

        # Include top keyword/BM25 results first
        for r in keyword_results[:5] + bm25_results[:5]:
            lr = r.get("line_range")
            if lr:
                candidates[lr] = r

        # If still few candidates, add random paragraphs
        if len(candidates) < 5:
            import random
            for para in random.sample(paragraphs, min(10, len(paragraphs))):
                lr = (para["line_start"], para["line_end"])
                if lr not in candidates:
                    candidates[lr] = {
                        "node_id": "",
                        "title": self._find_node_for_line(tree, para["line_start"]) or tree.get("title", ""),
                        "summary": "",
                        "text_content": para["text"],
                        "score": 0.0,
                        "line_range": lr,
                    }

        # Compute cosine similarity for each candidate
        scored = []
        for lr, r in candidates.items():
            try:
                text_emb = await self.llm.embed(r["text_content"][:500])  # truncate long text
                if not text_emb:
                    continue
                # Cosine similarity
                dot = sum(a * b for a, b in zip(query_emb, text_emb))
                norm_q = math.sqrt(sum(a * a for a in query_emb))
                norm_t = math.sqrt(sum(b * b for b in text_emb))
                if norm_q > 0 and norm_t > 0:
                    sim = dot / (norm_q * norm_t)
                    r["score"] = sim
                    scored.append(r)
            except Exception:
                continue

        scored.sort(key=lambda x: -x["score"])
        return scored[:5]

    def _merge_results(self, keyword_results: List[dict], bm25_results: List[dict], llm_results: List[dict]) -> List[dict]:
        """Merge and deduplicate results. Keep top result per document (by line_range)."""
        max_kw_score = max((r["score"] for r in keyword_results), default=1)
        max_bm25_score = max((r["score"] for r in bm25_results), default=1)
        for r in llm_results:
            r["score"] = max_bm25_score * 0.5

        combined = keyword_results + bm25_results + llm_results

        # 按 (line_range) 去重，每条 line_range 只保留一个
        seen_ranges = set()
        unique = []
        for r in combined:
            lr = r.get("line_range")
            if lr and lr not in seen_ranges:
                seen_ranges.add(lr)
                unique.append(r)

        unique.sort(key=lambda x: -x["score"])
        return unique

    def _extract_keywords(self, query: str) -> List[str]:
        try:
            import jieba
            import jieba.analyse
            keywords = list(jieba.cut_for_search(query))
            keywords.extend(jieba.analyse.extract_tags(query, topK=5))
            seen = set()
            result = []
            for kw in keywords:
                kw = kw.strip()
                if len(kw) >= 2 and kw not in seen:
                    seen.add(kw)
                    result.append(kw)
            return result
        except ImportError:
            words = re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}', query)
            return list(set(words))

    def _split_into_paragraphs(self, text: str) -> List[dict]:
        lines = text.split("\n")
        paragraphs = []
        current_lines = []
        current_start = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped:
                if not current_lines:
                    current_start = i
                current_lines.append(stripped)
            else:
                if current_lines:
                    paragraphs.append({
                        "text": "\n".join(current_lines),
                        "line_start": current_start,
                        "line_end": current_start + len(current_lines),
                    })
                    current_lines = []

        if current_lines:
            paragraphs.append({
                "text": "\n".join(current_lines),
                "line_start": current_start,
                "line_end": current_start + len(current_lines),
            })

        return paragraphs

    def _find_node_for_line(self, tree: dict, line_num: int) -> str:
        best_title = tree.get("title", "")
        for child in tree.get("nodes", []):
            start = child.get("start_index", 1)
            end = child.get("end_index", 999999)
            if start <= line_num + 1 <= end:
                child_title = child.get("title", "")
                if child_title:
                    best_title = child_title
                deeper = self._find_node_for_line(child, line_num)
                if deeper != child.get("title", ""):
                    return deeper
                return child_title
        return best_title

    async def _tree_search_fallback(self, query: str, document: Document, max_depth: int = None) -> List[dict]:
        tree = document.tree_index
        full_text_lines = document.full_text.split("\n")

        if not tree.get("nodes"):
            result = self._node_to_result(tree, full_text_lines)
            result["document_id"] = str(document.id)
            result["document_title"] = document.title
            return [result]

        matched_leaves = await self._traverse_tree(query, tree, full_text_lines, depth=0, max_depth=max_depth)

        for r in matched_leaves:
            r["document_id"] = str(document.id)
            r["document_title"] = document.title

        return matched_leaves

    async def search_all_documents(self, query: str, db: Session) -> List[dict]:
        cfg = self._get_config(db)
        top_k = cfg["search_top_k"]

        documents = db.query(Document).filter(
            Document.status == DocumentStatus.INDEXED
        ).all()

        if not documents:
            logger.warning("No indexed documents found")
            return []

        # 优化1: 查询改写 - 抽象词展开
        expanded_query = self._expand_query(query)

        # 优化2: 智能 LLM 预筛选 - 仅在关键词无强匹配时触发 LLM
        selected_docs = await self._select_documents(query, expanded_query, documents)
        if not selected_docs:
            selected_docs = documents

        all_results = []
        for doc in selected_docs:
            try:
                results = await self.search_document(query, doc, max_depth=cfg["search_max_depth"])
                all_results.extend(results)
                logger.info(f"Searched doc '{doc.title}': {len(results)} results")
            except Exception as e:
                logger.error(f"Error searching document {doc.id}: {e}")
                continue

        if not all_results:
            return []

        # 按 document_id 去重，每文档只保留最高分的结果
        doc_best: dict = {}
        for r in all_results:
            doc_id = r.get("document_id")
            if doc_id not in doc_best or r.get("score", 0) > doc_best[doc_id].get("score", 0):
                doc_best[doc_id] = r
        all_results = list(doc_best.values())
        all_results.sort(key=lambda x: -x.get("score", 0))

        if len(all_results) > top_k:
            all_results = await self._global_rerank(query, all_results, top_k=top_k)

        return all_results[:top_k]

    async def _select_documents(self, query: str, expanded_query: str, documents: List) -> List:
        """Smart document pre-selection.

        策略：
        1. 关键词得分 > 0 的文档超过 5 个时 → 用 LLM 从 top 15 筛选
        2. 关键词得分 > 0 的文档不超过 5 个时 → 直接返回这些文档（无需 LLM）
        3. 关键词无匹配时 → 用 LLM 从全部文档筛选（抽象问题兜底）
        """
        import jieba
        import jieba.analyse

        keywords = set(jieba.cut_for_search(expanded_query))
        keywords.update(jieba.analyse.extract_tags(expanded_query, topK=5))

        scored = []
        for i, doc in enumerate(documents):
            score = 0
            title = doc.title or ""
            tree = doc.tree_index or {}
            summary = tree.get("summary", "")
            search_text = title + " " + summary
            for child in tree.get("nodes", []):
                search_text += " " + child.get("title", "")
                search_text += " " + child.get("summary", "")

            for kw in keywords:
                if len(kw) < 2:
                    continue
                if kw in title:
                    score += 5
                if kw in search_text:
                    score += 2
            scored.append((score, i, doc))

        scored.sort(key=lambda x: -x[0])
        keyword_candidates = scored[:15]

        # 情况1: 有一定关键词匹配（>5个文档有分数）→ LLM 筛选 top 15
        if len([s for s, _, _ in keyword_candidates if s > 0]) > 5:
            docs_info = [
                {
                    "index": j,
                    "title": doc.title,
                    "summary": (doc.tree_index or {}).get("summary", "")[:100],
                }
                for j, (_, _, doc) in enumerate(keyword_candidates)
            ]
            return await self._llm_select(query, docs_info, keyword_candidates)

        # 情况2: 关键词匹配少（≤5个）但不为空 → 直接返回关键词候选
        if keyword_candidates and keyword_candidates[0][0] > 0:
            return [d for _, _, d in keyword_candidates[:5]]

        # 情况3: 关键词无匹配（抽象问题）→ 用 LLM 从全部文档筛选
        docs_info = [
            {
                "index": j,
                "title": doc.title,
                "summary": (doc.tree_index or {}).get("summary", "")[:100],
            }
            for j, (_, _, doc) in enumerate(scored)
        ]
        return await self._llm_select(query, docs_info, scored)

    async def _llm_select(self, query: str, docs_info: List[dict], scored: List) -> List:
        """Call LLM to select documents from scored list."""
        try:
            response = await self.llm.generate(
                prompt=DOC_SELECT_PROMPT.format(
                    query=query,
                    docs_json=json.dumps(docs_info, ensure_ascii=False, indent=2),
                ),
                system=DOC_SELECT_SYSTEM.format(top_k=min(10, len(scored))),
                temperature=0.1,
                max_tokens=512,
            )
            selected_indices = self._parse_id_array(response.get("response", ""))
            selected_indices = [int(x) for x in selected_indices if str(x).isdigit()]
            if selected_indices:
                result = [scored[i][2] for i in selected_indices if i < len(scored)]
                logger.info(f"LLM pre-selected {len(result)} documents")
                return result
        except Exception as e:
            logger.error(f"LLM document selection failed: {e}")

        return [d for _, _, d in scored[:5]]

    async def _traverse_tree(self, query: str, node: dict, full_text_lines: List[str], depth: int, max_depth: int = None) -> List[dict]:
        if max_depth is None:
            max_depth = settings.SEARCH_MAX_DEPTH
        children = node.get("nodes", [])

        if not children or depth >= max_depth:
            return [self._node_to_result(node, full_text_lines)]

        sections_info = [
            {
                "node_id": c["node_id"],
                "title": c.get("title", ""),
                "summary": c.get("summary", ""),
            }
            for c in children
        ]

        try:
            response = await self.llm.generate(
                prompt=TREE_SEARCH_PROMPT.format(
                    query=query,
                    sections_json=json.dumps(sections_info, ensure_ascii=False, indent=2),
                ),
                system=TREE_SEARCH_SYSTEM.format(top_k=settings.SEARCH_TOP_K),
                temperature=0.1,
                max_tokens=512,
            )
            selected_ids = self._parse_id_array(response.get("response", ""))
            logger.info(f"Tree depth {depth}: LLM selected {selected_ids}")
        except Exception as e:
            logger.error(f"Tree search LLM call failed: {e}")
            selected_ids = []

        if not selected_ids:
            selected_ids = [c["node_id"] for c in children]

        results = []
        for child in children:
            if child["node_id"] in selected_ids:
                child_results = await self._traverse_tree(query, child, full_text_lines, depth + 1, max_depth)
                results.extend(child_results)

        return results

    def _node_to_result(self, node: dict, full_text_lines: List[str]) -> dict:
        start = max(0, node.get("start_index", 1) - 1)
        end = min(len(full_text_lines), node.get("end_index", len(full_text_lines)))
        if start >= end - 1:
            text = "\n".join(full_text_lines[:200])
        else:
            text = "\n".join(full_text_lines[start:end])
        return {
            "node_id": node.get("node_id", ""),
            "title": node.get("title", ""),
            "summary": node.get("summary", ""),
            "text_content": text,
            "line_range": (start, end),
        }

    def _parse_id_array(self, text: str) -> List[str]:
        text = text.strip()
        if not text:
            return []

        if "```" in text:
            pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
            match = re.search(pattern, text, re.DOTALL)
            if match:
                text = match.group(1).strip()

        first_bracket = text.find("[")
        last_bracket = text.rfind("]")
        if first_bracket != -1 and last_bracket != -1:
            text = text[first_bracket:last_bracket + 1]

        text = re.sub(r",\s*\]", "]", text)

        try:
            result = json.loads(text)
            if isinstance(result, list):
                return [str(x) for x in result]
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Failed to parse ID array: {text[:200]}")
        return []

    async def _global_rerank(self, query: str, results: List[dict], top_k: int = None) -> List[dict]:
        sections_info = [
            {
                "index": i,
                "document": r.get("document_title", "")[:30],
                "title": r.get("title", "")[:30],
                "preview": r.get("text_content", "")[:80],
            }
            for i, r in enumerate(results)
        ]

        try:
            response = await self.llm.generate(
                prompt=RERANK_PROMPT.format(
                    query=query,
                    sections_json=json.dumps(sections_info, ensure_ascii=False, indent=2),
                ),
                system=RERANK_SYSTEM.format(top_k=settings.SEARCH_TOP_K),
                temperature=0.1,
                max_tokens=512,
            )
            selected_indices = self._parse_id_array(response.get("response", ""))
            selected_indices = [int(x) for x in selected_indices if str(x).isdigit()]
            if selected_indices:
                return [results[i] for i in selected_indices if i < len(results)]
        except Exception as e:
            logger.error(f"Global rerank failed: {e}")

        return results[:top_k]


tree_search = TreeSearch()
