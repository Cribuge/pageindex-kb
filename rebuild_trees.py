"""Batch rebuild trees for documents with poor quality tree indexes."""
import asyncio
from core.database import SessionLocal
from services.tree_builder import tree_builder
from models.document import Document, TreeNode

db = SessionLocal()
docs = db.query(Document).filter(Document.status == "INDEXED").all()

count = 0
for doc in docs:
    tree = doc.tree_index
    if not tree:
        continue
    summary = tree.get("summary", "")
    nodes = tree.get("nodes", [])
    is_bad = (
        not summary or
        summary.startswith("文档共") or
        (len(nodes) <= 1 and not summary)
    )
    if not is_bad:
        continue

    text = doc.full_text
    if not text:
        print("SKIP (no text): %s" % doc.title[:35])
        continue

    print("Rebuilding: %s (%d chars)" % (doc.title[:35], len(text)))
    try:
        new_tree = asyncio.run(tree_builder.build_tree(text))
        root_summary = new_tree.get("summary", "")
        if root_summary.startswith("文档共") or not root_summary:
            new_tree = tree_builder._create_fallback_tree(text)
            root_summary = new_tree.get("summary", "")

        doc.tree_index = new_tree
        db.query(TreeNode).filter(TreeNode.document_id == doc.id).delete()
        nodes_list = tree_builder.flatten_tree(new_tree, str(doc.id))
        for nd in nodes_list:
            node = TreeNode(**nd)
            db.add(node)
        db.commit()
        nc = tree_builder.count_nodes(new_tree)
        count += 1
        print("  OK: %d nodes, summary: %s" % (nc, root_summary[:40]))
    except Exception as e:
        print("  FAIL: %s" % str(e)[:80])
        db.rollback()

print("\nTotal rebuilt: %d" % count)
db.close()
