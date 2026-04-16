"""
PageIndex Tree Builder: generates hierarchical tree index from document text using LLM.
"""
import json
import logging
import re
from typing import List, Optional

from core.config import settings
from services.llm_service import llm_service

logger = logging.getLogger(__name__)

TREE_GENERATION_SYSTEM = """你是一个文档结构分析专家。根据提供的带行号的文档内容，生成层级目录结构。

输出要求：只输出JSON，不要输出任何其他文字，不要使用```json```标记。

JSON格式：
{{"title":"文档根节点","node_id":"0001","start_index":1,"end_index":总行数,"summary":"一句话摘要","nodes":[{{"title":"章节标题","node_id":"0002","start_index":起始行号,"end_index":结束行号,"summary":"一句话摘要","nodes":[]}}]}}

规则：
1. 每个节点必须包含：title, node_id, start_index, end_index, summary, nodes
2. start_index和end_index是行号（从1开始）
3. node_id从"0001"开始递增，4位数字字符串
4. 最多{max_children}个子节点
5. summary用一句话概括该段落内容
6. 直接输出JSON，不要任何解释"""

TREE_GENERATION_PROMPT = """分析以下文档，生成目录结构JSON。

文档内容（带行号）：
---
{numbered_text}
---

直接输出JSON："""

TREE_MERGE_SYSTEM = """你是文档结构合并专家。将多个子树合并为一个统一的目录树。

只输出JSON，不要任何其他文字。

规则：
1. node_id从"0001"重新编号
2. 合并重复的章节
3. 保留所有summary"""

TREE_MERGE_PROMPT = """将以下子树合并为一个统一的目录树：

{trees_text}

输出合并后的JSON："""


class TreeBuilder:

    def __init__(self):
        self.llm = llm_service

    async def build_tree(self, text: str, config: dict = None) -> dict:
        """Build PageIndex tree from document text."""
        if config is None:
            config = {}
        max_depth = config.get("tree_max_depth", settings.TREE_MAX_DEPTH)
        max_children = config.get("tree_max_children", settings.TREE_MAX_CHILDREN)
        max_context_chars = config.get("max_tree_context_chars", settings.MAX_TREE_CONTEXT_CHARS)

        if len(text) <= max_context_chars:
            return await self._single_pass_tree(text, max_depth=max_depth, max_children=max_children)
        else:
            return await self._segmented_tree(text, max_depth=max_depth, max_children=max_children, max_context_chars=max_context_chars)

    async def _single_pass_tree(self, text: str, max_depth: int = None, max_children: int = None) -> dict:
        """Generate tree in a single LLM call."""
        if max_depth is None:
            max_depth = settings.TREE_MAX_DEPTH
        if max_children is None:
            max_children = settings.TREE_MAX_CHILDREN
        numbered = self._number_lines(text)
        system = TREE_GENERATION_SYSTEM.format(
            max_depth=max_depth,
            max_children=max_children,
        )
        prompt = TREE_GENERATION_PROMPT.format(numbered_text=numbered)

        for attempt in range(3):
            try:
                response = await self.llm.generate(
                    prompt=prompt,
                    system=system,
                    temperature=0.1,
                    max_tokens=8192,
                )
                raw = response.get("response", "")
                logger.info(f"Tree generation attempt {attempt+1}, response length: {len(raw)}")
                if not raw or not raw.strip():
                    logger.warning(f"Empty LLM response on attempt {attempt+1}")
                    continue

                tree_json = self._parse_json_response(raw)
                if tree_json and "title" in tree_json:
                    self._reassign_node_ids(tree_json)
                    logger.info(f"Tree generated successfully: {self.count_nodes(tree_json)} nodes")
                    return tree_json
                elif tree_json:
                    # Try to normalize non-standard JSON structure
                    normalized = self._normalize_tree(tree_json)
                    if normalized and "title" in normalized:
                        self._reassign_node_ids(normalized)
                        logger.info(f"Normalized tree: {self.count_nodes(normalized)} nodes")
                        return normalized
                    logger.warning(f"Parsed JSON but missing title: {str(tree_json)[:200]}")
            except Exception as e:
                logger.error(f"Tree generation attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    # 缩短文本重试（减少20%而非50%）
                    text = text[:int(len(text) * 0.8)]
                    numbered = self._number_lines(text)
                    prompt = TREE_GENERATION_PROMPT.format(numbered_text=numbered)

        logger.error("All tree generation attempts failed, using fallback")
        return self._create_fallback_tree(text)

    async def _segmented_tree(self, text: str, max_depth: int = None, max_children: int = None, max_context_chars: int = None) -> dict:
        """Split text into segments, build sub-trees, merge."""
        if max_context_chars is None:
            max_context_chars = settings.MAX_TREE_CONTEXT_CHARS
        segments = self._split_text(text, chunk_size=max_context_chars, overlap=2000)

        sub_trees = []
        line_offset = 0
        for segment in segments:
            tree = await self._single_pass_tree(segment, max_depth=max_depth, max_children=max_children)
            self._adjust_indices(tree, line_offset)
            sub_trees.append(tree)
            line_offset += segment.count("\n")

        if len(sub_trees) == 1:
            return sub_trees[0]

        return await self._merge_trees(sub_trees)

    def _number_lines(self, text: str) -> str:
        lines = text.split("\n")
        return "\n".join(f"{i+1}| {line}" for i, line in enumerate(lines))

    def _split_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        paragraphs = text.split("\n\n")
        segments = []
        current = ""

        for para in paragraphs:
            if len(current) + len(para) + 2 > chunk_size and current:
                segments.append(current)
                overlap_text = current[-overlap:] if overlap else ""
                current = overlap_text + "\n\n" + para if overlap_text else para
            else:
                current = current + "\n\n" + para if current else para

        if current.strip():
            segments.append(current)
        return segments

    async def _merge_trees(self, trees: List[dict]) -> dict:
        trees_text = "\n\n".join(
            f"子树{i+1}:\n{json.dumps(t, ensure_ascii=False, indent=2)}"
            for i, t in enumerate(trees)
        )

        try:
            response = await self.llm.generate(
                prompt=TREE_MERGE_PROMPT.format(trees_text=trees_text),
                system=TREE_MERGE_SYSTEM,
                temperature=0.1,
                max_tokens=8192,
            )
            merged = self._parse_json_response(response.get("response", ""))
            self._reassign_node_ids(merged)
            return merged
        except Exception as e:
            logger.error(f"Tree merge failed: {e}, using first tree as fallback")
            return trees[0]

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from LLM response with robust error handling."""
        text = text.strip()
        if not text:
            raise ValueError("Empty response")

        # Remove markdown code fences
        if "```" in text:
            # Extract content between ``` markers
            pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
            match = re.search(pattern, text, re.DOTALL)
            if match:
                text = match.group(1).strip()

        # Try to find JSON object in the text
        # Look for outermost { }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            text = text[first_brace:last_brace + 1]

        # Fix common LLM JSON issues
        # Remove trailing commas before } or ]
        text = re.sub(r",\s*([}\]])", r"\1", text)
        # Fix missing commas between JSON properties (common LLM issue)
        # e.g., "summary": "xxx" "nodes": → "summary": "xxx", "nodes":
        text = re.sub(r'"\s*\n\s*"([a-zA-Z_]+)": ', r'",\n"\1": ', text)

        try:
            result = json.loads(text)
            if not isinstance(result, dict):
                raise ValueError(f"Expected dict, got {type(result)}")
            return result
        except json.JSONDecodeError as e:
            # Try to repair truncated JSON by closing open brackets/braces
            repaired = self._repair_truncated_json(text)
            if repaired != text:
                try:
                    result = json.loads(repaired)
                    if isinstance(result, dict):
                        logger.info("Successfully repaired truncated JSON")
                        return result
                except json.JSONDecodeError:
                    pass
            logger.error(f"JSON parse failed: {e}")
            logger.error(f"Raw text (first 500 chars): {text[:500]}")
            raise

    def _repair_truncated_json(self, text: str) -> str:
        """Attempt to repair truncated JSON by closing open brackets/braces."""
        stack = []
        in_string = False
        escape = False
        last_complete = -1

        for i, ch in enumerate(text):
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue

            if ch == '{':
                stack.append('}')
            elif ch == '[':
                stack.append(']')
            elif ch in ('}', ']'):
                if stack and stack[-1] == ch:
                    stack.pop()
                    if not stack:
                        last_complete = i

        if last_complete < len(text) - 1:
            # JSON was truncated, try closing from the last complete structure
            # Find the last valid node boundary in tree structure
            # Strategy: go back to last complete } for a node
            truncated = text[:last_complete + 1] if last_complete >= 0 else text
            # Close remaining open brackets
            while stack:
                closing = stack.pop()
                if closing == '}':
                    truncated += '}'
                elif closing == ']':
                    truncated += ']'
            return truncated
        return text

    def _normalize_tree(self, data: dict) -> dict:
        """Normalize non-standard JSON structure to standard tree format."""
        # If it's already a valid tree, return as-is
        if "title" in data and "node_id" in data:
            return data

        # If LLM produced a structured dict without 'title', try to extract a tree
        # e.g., {"制度名称": "...", "主要内容": {"子模块1": {...}}}
        def to_tree(obj, prefix="0001", depth=0):
            if not isinstance(obj, dict):
                return None

            # Find a title-like field
            title_keys = ["title", "标题", "名称", "制度名称", "name", "name_zh"]
            title = None
            for k in title_keys:
                if k in obj:
                    title = str(obj[k])[:40]
                    break

            if not title:
                # Use first key as title
                keys = [k for k in obj.keys() if isinstance(obj[k], str)]
                if keys:
                    title = f"{keys[0]}: {str(obj[keys[0]])[:30]}"
                else:
                    title = list(obj.keys())[0] if obj else "未知"

            # Find child nodes
            nodes = []
            for key, val in obj.items():
                if isinstance(val, dict):
                    child = to_tree(val, f"{len(nodes)+1:04d}", depth + 1)
                    if child:
                        nodes.append(child)
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            child = to_tree(item, f"{len(nodes)+1:04d}", depth + 1)
                            if child:
                                nodes.append(child)

            # Find summary
            summary_keys = ["summary", "摘要", "目的", "制定目的", "描述", "适用范围"]
            summary = ""
            for k in summary_keys:
                if k in obj and isinstance(obj[k], str):
                    summary = obj[k][:80]
                    break

            return {
                "title": title,
                "node_id": prefix,
                "start_index": 1,
                "end_index": 1,
                "summary": summary,
                "nodes": nodes[:settings.TREE_MAX_CHILDREN],
            }

        return to_tree(data)

    def _reassign_node_ids(self, tree: dict, counter: Optional[List[int]] = None):
        if counter is None:
            counter = [0]
        counter[0] += 1
        tree["node_id"] = f"{counter[0]:04d}"
        for child in tree.get("nodes", []):
            self._reassign_node_ids(child, counter)

    def _adjust_indices(self, tree: dict, offset: int):
        tree["start_index"] = tree.get("start_index", 1) + offset
        tree["end_index"] = tree.get("end_index", 1) + offset
        for child in tree.get("nodes", []):
            self._adjust_indices(child, offset)

    def _create_fallback_tree(self, text: str) -> dict:
        """Create a tree with paragraph-level nodes when LLM generation fails."""
        # Try to split by double newline first, then by single newline
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) < 3:
            # Split into chunks of ~500 chars
            chunk_size = 500
            paragraphs = [text[i:i+chunk_size].strip() for i in range(0, len(text), chunk_size) if text[i:i+chunk_size].strip()]

        lines = text.split("\n")

        # Build nodes from paragraphs by finding their line ranges
        nodes = []
        current_line = 0
        for i, para in enumerate(paragraphs[:settings.TREE_MAX_CHILDREN]):
            para_lines = para.split("\n")
            start = current_line + 1
            end = current_line + len(para_lines)
            # Use first line as title, clean up
            title = para_lines[0][:50].strip()
            if not title:
                title = f"段落 {i+1}"
            # Generate a better summary: first 2 meaningful lines
            summary_lines = [l.strip() for l in para_lines if l.strip()]
            summary = "\n".join(summary_lines[:2])[:80]
            nodes.append({
                "title": title,
                "node_id": f"{i+2:04d}",
                "start_index": start,
                "end_index": end,
                "summary": summary,
                "nodes": [],
            })
            current_line = end

        # Generate a root summary from first few lines
        first_lines = [l.strip() for l in lines[:5] if l.strip()]
        root_summary = "\n".join(first_lines[:2])[:80] if first_lines else "文档内容"

        line_count = len(lines)
        return {
            "title": root_summary[:40] if root_summary else "文档根节点",
            "node_id": "0001",
            "start_index": 1,
            "end_index": line_count,
            "summary": root_summary,
            "nodes": nodes,
        }

    def flatten_tree(self, tree: dict, doc_id: str, parent_id: Optional[str] = None, depth: int = 0, path: str = "") -> List[dict]:
        current_path = f"{path}/{tree['node_id']}" if path else tree["node_id"]
        node = {
            "node_id": tree["node_id"],
            "title": tree.get("title", ""),
            "summary": tree.get("summary", ""),
            "start_index": tree.get("start_index", 1),
            "end_index": tree.get("end_index", 1),
            "depth": depth,
            "parent_node_id": parent_id,
            "document_id": doc_id,
            "path": current_path,
        }
        nodes = [node]
        for child in tree.get("nodes", []):
            nodes.extend(self.flatten_tree(child, doc_id, tree["node_id"], depth + 1, current_path))
        return nodes

    def count_nodes(self, tree: dict) -> int:
        count = 1
        for child in tree.get("nodes", []):
            count += self.count_nodes(child)
        return count


tree_builder = TreeBuilder()
