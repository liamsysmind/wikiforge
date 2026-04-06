"""
_compile.py — compile pipeline 資料準備（不呼叫 LLM）
"""
from . import _store, _index


def get_compile_tasks() -> list[dict]:
    """
    Get raw articles that need compilation into wiki.

    Returns:
        List of dicts: {"raw_id", "title", "content"}
    """
    uncompiled = _index.list_articles("raw", uncompiled_only=True)
    tasks = []
    for article in uncompiled:
        try:
            _, body = _store.read_article(_store.raw_dir(), article["id"])
            tasks.append({
                "raw_id": article["id"],
                "title": article["title"],
                "content": body,
            })
        except FileNotFoundError:
            continue
    return tasks


def mark_compiled(raw_id: str, wiki_id: str) -> None:
    """Mark a raw article as compiled, linking to its wiki counterpart."""
    _index.mark_compiled(raw_id, wiki_id)

    # Also update the raw file's frontmatter
    try:
        meta, body = _store.read_article(_store.raw_dir(), raw_id)
        meta["compiled"] = True
        meta["compiled_to"] = wiki_id
        _store.write_article(_store.raw_dir(), raw_id, meta, body)
    except FileNotFoundError:
        pass
