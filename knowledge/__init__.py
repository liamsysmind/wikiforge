"""
knowledge — 獨立知識層模組（Karpathy 式 LLM Knowledge Base）

raw/ → LLM compile → wiki/ → LLM lint → wiki/

此模組不認識 LINE、Claude SDK、brain.py。
它只操作檔案和 SQLite。LLM 整合由 caller（brain.py）負責。
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import _store, _index, _ingest, _compile, _lint


# --- Initialization ---


def init(base_path: Optional[str | Path] = None) -> None:
    """
    Initialize the knowledge store.
    Creates raw/, wiki/, and index.db if they don't exist.

    Args:
        base_path: Override default ~/linebot/knowledge.
                   Also settable via KNOWLEDGE_BASE env var.
    """
    if base_path is not None:
        _store.set_base(base_path)
    _store.ensure_dirs()
    _index.init_db()


# --- Ingestion (raw/) ---


def ingest_file(
    file_path: str,
    *,
    tags: Optional[list[str]] = None,
    source: Optional[str] = None,
) -> str:
    """
    Ingest a file into raw/. Converts to Markdown via file_converter.

    Returns:
        The raw article ID.
    """
    return _ingest.ingest_file(file_path, tags=tags, source=source)


def ingest_url(
    url: str,
    content: str,
    *,
    tags: Optional[list[str]] = None,
    title: Optional[str] = None,
) -> str:
    """
    Ingest URL content into raw/. Caller fetches the content.

    Returns:
        The raw article ID.
    """
    return _ingest.ingest_url(url, content, tags=tags, title=title)


def ingest_text(
    text: str,
    *,
    title: Optional[str] = None,
    tags: Optional[list[str]] = None,
    source: Optional[str] = None,
) -> str:
    """
    Ingest raw text into raw/.

    Returns:
        The raw article ID.
    """
    return _ingest.ingest_text(text, title=title, tags=tags, source=source)


# --- Read ---


def read_raw(article_id: str) -> str:
    """Read full content of a raw/ article."""
    return _store.read_article_full(_store.raw_dir(), article_id)


def read_wiki(article_id: str) -> str:
    """Read full content of a wiki/ article."""
    return _store.read_article_full(_store.wiki_dir(), article_id)


def list_raw(*, uncompiled_only: bool = False) -> list[dict]:
    """List articles in raw/."""
    return _index.list_articles("raw", uncompiled_only=uncompiled_only)


def list_wiki() -> list[dict]:
    """List articles in wiki/."""
    return _index.list_articles("wiki")


# --- Wiki write ---


def write_wiki(
    article_id: str,
    content: str,
    *,
    title: Optional[str] = None,
) -> str:
    """
    Write or update a wiki/ article. Updates the FTS index and link graph.

    Args:
        article_id: Filename stem (slug form)
        content: Full markdown body (use [[wikilinks]] for cross-references)
        title: Optional title (extracted from content H1 if not provided)

    Returns:
        The wiki article ID.
    """
    if not title:
        # Extract title from first H1
        for line in content.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        else:
            title = article_id.replace("_", " ")

    now = datetime.now(timezone.utc).isoformat()

    meta = {
        "id": article_id,
        "title": title,
        "tags": [],
        "created_at": now,
        "updated_at": now,
    }

    # Check if article already exists to preserve created_at
    existing = _index.get_article_meta(article_id)
    if existing:
        meta["created_at"] = existing.get("created_at", now)
        meta["tags"] = existing.get("tags", [])

    _store.write_article(_store.wiki_dir(), article_id, meta, content)

    _index.upsert_article(
        article_id, scope="wiki", title=title, content=content,
        tags=meta["tags"], created_at=meta["created_at"], updated_at=now,
    )

    # Update link graph
    _lint.update_links_for_article(article_id, content)

    return article_id


def delete_wiki(article_id: str) -> bool:
    """Delete a wiki article and remove from index."""
    deleted = _store.delete_article(_store.wiki_dir(), article_id)
    if deleted:
        _index.delete_article(article_id)
    return deleted


# --- Search ---


def search(
    query: str,
    *,
    scope: str = "wiki",
    limit: int = 10,
) -> list[dict]:
    """
    Full-text search over wiki/ (or raw/) using SQLite FTS5 + BM25.

    Args:
        query: Search query (supports FTS5 syntax)
        scope: "wiki", "raw", or "all"
        limit: Max results
    """
    return _index.search(query, scope=scope, limit=limit)


# --- Compile pipeline ---


def get_compile_tasks() -> list[dict]:
    """Get raw articles that need compilation into wiki."""
    return _compile.get_compile_tasks()


def mark_compiled(raw_id: str, wiki_id: str) -> None:
    """Mark a raw article as compiled, linking to its wiki article."""
    _compile.mark_compiled(raw_id, wiki_id)


# --- Lint ---


def get_lint_report() -> dict:
    """
    Analyze wiki/ for issues.

    Returns:
        {"orphans": [...], "broken_links": [...],
         "missing_backlinks": [...], "stats": {...}}
    """
    return _lint.get_lint_report()


def get_wiki_graph() -> dict:
    """Return the full wiki link graph."""
    return _lint.get_wiki_graph()
