"""
PageIndex Tree Search: keyword-based full text search with tree index for document selection.
"""
import json
import logging
import re
from typing import List

from sqlalchemy.orm import Session

from core.config import settings
from models.document import Document, DocumentStatus
from models.config import SystemConfig
from services.llm_service import llm_service

logger = logging.getLogger(__name__)

TREE_SEARCH_SYSTEM = """你是文档检索助手。根据用户的问题和文档章节列表，选择最可能包含答案的章节。

只输出一个JSON数组，例如：["0003","0007"]

规则：
1. 最多选{top_k}个章节
2. 如果没有相关章节，返回[]
3. 只输出JSON数组，不要任何解释"""

DOC_SELECT_SYSTEM = """你是文档筛选助手。根据用户问题，从文档列表中选出最相关的文档。

只输出一个JSON数组（文档索引，0-based），例如：[2,0,5]

规则：
1. 最多选{top_k}个文档
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

只输出JSON数组（0-based索引），例如：[2,0,4]"""

RERANK_PROMPT = """问题：{query}

候选结果：
{sections_json}

选出最相关的结果索引，输出JSON数组："""


class TreeSearch:

    def __init__(self):
        self.llm = llm_service

    def _get_config(self, db: Session) -> dict:
        """Read search config from DB, fallback to settings defaults."""
        defaults = {
            "search_top_k": settings.SEARCH_TOP_K,
            "search_max_depth": settings.SEARCH_MAX_DEPTH,
            "llm_provider": settings.LLMProvider,
            "openai_api_base": settings.OpenAI_API_Base,
            "openai_api_key": settings.OpenAI_API_Key,
            "anthropic_api_base": settings.Anthropic_API_Base,
            "anthropic_api_key": settings.Anthropic_API_Key,
        }
        result = {}
        for key in defaults:
            row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            result[key] = row.value if row else defaults[key]
        return result

    async def search_document(self, query: str, document: Document, max_depth: int = None) -> List[dict]:
        """Search within a single document using keyword extraction + text matching + tree context."""
        if not document.tree_index or not document.full_text:
            return []

        full_text = document.full_text
        tree = document.tree_index

        # Extract keywords from query
        keywords = self._extract_keywords(query)

        # Split full text into paragraphs
        paragraphs = self._split_into_paragraphs(full_text)

        # Score each paragraph by keyword hits
        scored = []
        for para in paragraphs:
            if len(para["text"].strip()) < 20:
                continue
            score = 0
            for kw in keywords:
                if len(kw) < 2:
                    continue
                count = para["text"].count(kw)
                score += count * len(kw)  # Longer keywords weighted more
            if score > 0:
                scored.append((score, para))

        if not scored:
            # No keyword match, try tree-based search as fallback
            return await self._tree_search_fallback(query, document, max_depth)

        # Sort by score, take top chunks
        scored.sort(key=lambda x: -x[0])
        top_chunks = scored[:5]

        # Build results with context window
        results = []
        seen_ranges = set()
        for score, para in top_chunks:
            line_start = para["line_start"]
            line_end = para["line_end"]
            # Merge overlapping ranges
            key = (line_start, line_end)
            if key in seen_ranges:
                continue
            seen_ranges.add(key)

            # Expand context: include neighboring lines
            lines = full_text.split("\n")
            ctx_start = max(0, line_start - 3)
            ctx_end = min(len(lines), line_end + 3)
            text = "\n".join(lines[ctx_start:ctx_end])

            # Find which tree node this belongs to
            node_title = self._find_node_for_line(tree, line_start) or tree.get("title", "")

            results.append({
                "node_id": "",
                "title": node_title,
                "summary": "",
                "text_content": text,
                "score": score,
            })

        # Fill in document info
        for r in results:
            r["document_id"] = str(document.id)
            r["document_title"] = document.title

        return results

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract Chinese keywords from query using jieba."""
        try:
            import jieba
            import jieba.analyse
            keywords = list(jieba.cut_for_search(query))
            keywords.extend(jieba.analyse.extract_tags(query, topK=5))
            # Deduplicate and filter
            seen = set()
            result = []
            for kw in keywords:
                kw = kw.strip()
                if len(kw) >= 2 and kw not in seen:
                    seen.add(kw)
                    result.append(kw)
            return result
        except ImportError:
            # Fallback: simple character-level split for Chinese
            words = re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}', query)
            return list(set(words))

    def _split_into_paragraphs(self, text: str) -> List[dict]:
        """Split text into paragraphs with line number tracking."""
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
        """Find the most specific tree node containing a given line number."""
        best_title = tree.get("title", "")
        for child in tree.get("nodes", []):
            start = child.get("start_index", 1)
            end = child.get("end_index", 999999)
            if start <= line_num + 1 <= end:
                child_title = child.get("title", "")
                if child_title:
                    best_title = child_title
                # Check deeper
                deeper = self._find_node_for_line(child, line_num)
                if deeper != child.get("title", ""):
                    return deeper
                return child_title
        return best_title

    async def _tree_search_fallback(self, query: str, document: Document, max_depth: int = None) -> List[dict]:
        """Fallback: use tree index + LLM to find relevant nodes."""
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

        # Step 1: Pre-filter documents by relevance
        selected_docs = await self._select_documents(query, documents)
        if not selected_docs:
            selected_docs = documents
            logger.info("Document pre-selection returned none, searching all")

        # Step 2: Search within selected documents
        all_results = []
        for doc in selected_docs:
            try:
                results = await self.search_document(query, doc, max_depth=cfg["search_max_depth"])
                all_results.extend(results)
                logger.info(f"Searched doc '{doc.title}': {len(results)} results, {sum(len(r.get('text_content','')) for r in results)} chars")
            except Exception as e:
                logger.error(f"Error searching document {doc.id}: {e}")
                continue

        if not all_results:
            logger.warning("No results from any document")
            return []

        if len(all_results) > top_k:
            all_results = await self._global_rerank(query, all_results, top_k=top_k)

        return all_results[:top_k]

    async def _select_documents(self, query: str, documents: List) -> List:
        """Pre-select most relevant documents using keyword matching + LLM."""
        import jieba
        import jieba.analyse

        # Step 1: Keyword-based scoring
        keywords = set(jieba.cut_for_search(query))
        keywords.update(jieba.analyse.extract_tags(query, topK=5))

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
            if score > 0:
                scored.append((score, i, doc))

        scored.sort(key=lambda x: -x[0])
        keyword_candidates = scored[:15]

        if not keyword_candidates:
            keyword_candidates = [(0, i, doc) for i, doc in enumerate(documents)]

        # Step 2: If we have a small candidate set, return them directly
        if len(keyword_candidates) <= 5:
            return [d for _, _, d in keyword_candidates]

        # Step 3: Use LLM to refine among keyword candidates
        docs_info = [
            {
                "index": j,
                "title": doc.title,
                "summary": (doc.tree_index or {}).get("summary", "")[:80],
            }
            for j, (_, _, doc) in enumerate(keyword_candidates)
        ]

        try:
            response = await self.llm.generate(
                prompt=DOC_SELECT_PROMPT.format(
                    query=query,
                    docs_json=json.dumps(docs_info, ensure_ascii=False, indent=2),
                ),
                system=DOC_SELECT_SYSTEM.format(top_k=5),
                temperature=0.1,
                max_tokens=256,
            )
            selected_indices = self._parse_id_array(response.get("response", ""))
            selected_indices = [int(x) for x in selected_indices if str(x).isdigit()]
            if selected_indices:
                result = [keyword_candidates[i][2] for i in selected_indices if i < len(keyword_candidates)]
                logger.info(f"Pre-selected {len(result)} documents from {len(documents)} (keyword narrowed to {len(keyword_candidates)})")
                return result
        except Exception as e:
            logger.error(f"LLM document selection failed: {e}")

        return [d for _, _, d in keyword_candidates[:5]]

    async def _traverse_tree(self, query: str, node: dict, full_text_lines: List[str], depth: int, max_depth: int = None) -> List[dict]:
        if max_depth is None:
            max_depth = settings.SEARCH_MAX_DEPTH
        children = node.get("nodes", [])

        if not children or depth >= max_depth:
            return [self._node_to_result(node, full_text_lines)]

        # 让LLM选择要深入的分支
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
            logger.info(f"Tree depth {depth}: LLM selected {selected_ids} from {[c['node_id'] for c in children]}")
        except Exception as e:
            logger.error(f"Tree search LLM call failed: {e}")
            selected_ids = []

        # Fallback: 如果LLM没有选出任何节点，选择所有子节点
        if not selected_ids:
            selected_ids = [c["node_id"] for c in children]
            logger.info(f"Tree depth {depth}: fallback to all children: {selected_ids}")

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
                max_tokens=256,
            )
            selected_indices = self._parse_id_array(response.get("response", ""))
            selected_indices = [int(x) for x in selected_indices if str(x).isdigit()]
            if selected_indices:
                return [results[i] for i in selected_indices if i < len(results)]
        except Exception as e:
            logger.error(f"Global rerank failed: {e}")

        return results[:top_k]


tree_search = TreeSearch()
