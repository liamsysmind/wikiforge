"""
_ingest.py — 素材匯入：file/url/text → raw/ markdown with frontmatter
"""
from datetime import datetime, timezone
from typing import Optional

from . import _store, _index


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    from file_converter import convert_to_markdown

    content = convert_to_markdown(file_path)

    # Derive title from filename
    from pathlib import Path as P
    title = P(file_path).stem.replace("_", " ").replace("-", " ")

    article_id = _store.make_raw_id(title)
    now = _now_iso()

    meta = {
        "id": article_id,
        "title": title,
        "source": source or "file",
        "source_url": None,
        "original_file": file_path,
        "tags": tags or [],
        "created_at": now,
        "compiled": False,
        "compiled_to": None,
    }

    _store.write_article(_store.raw_dir(), article_id, meta, content)

    _index.upsert_article(
        article_id, scope="raw", title=title, content=content,
        source=source or "file", tags=tags, created_at=now,
    )

    return article_id


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
    if not title:
        # Extract domain as fallback title
        from urllib.parse import urlparse
        title = urlparse(url).netloc or "web_content"

    article_id = _store.make_raw_id(title)
    now = _now_iso()

    meta = {
        "id": article_id,
        "title": title,
        "source": "url",
        "source_url": url,
        "original_file": None,
        "tags": tags or [],
        "created_at": now,
        "compiled": False,
        "compiled_to": None,
    }

    _store.write_article(_store.raw_dir(), article_id, meta, content)

    _index.upsert_article(
        article_id, scope="raw", title=title, content=content,
        source="url", source_url=url, tags=tags, created_at=now,
    )

    return article_id


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
    title = title or text[:50].strip().replace("\n", " ")
    article_id = _store.make_raw_id(title)
    now = _now_iso()

    meta = {
        "id": article_id,
        "title": title,
        "source": source or "text",
        "source_url": None,
        "original_file": None,
        "tags": tags or [],
        "created_at": now,
        "compiled": False,
        "compiled_to": None,
    }

    _store.write_article(_store.raw_dir(), article_id, meta, text)

    _index.upsert_article(
        article_id, scope="raw", title=title, content=text,
        source=source or "text", tags=tags, created_at=now,
    )

    return article_id
