"""
_ingest.py — 素材匯入：file/url/text → raw/ markdown with frontmatter
"""
from datetime import datetime, timezone
from typing import Optional

from . import _store, _index


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_file_hash(title: str) -> tuple[str | None, str]:
    """Extract leading SHA1 hash from title if present. Returns (hash, clean_title)."""
    import re
    match = re.match(r"^([A-Fa-f0-9]{40})_(.+)$", title)
    if match:
        return match.group(1), match.group(2)
    return None, title


def _find_duplicate(file_hash: str) -> str | None:
    """Check if a file with this hash already exists in raw/."""
    if not file_hash:
        return None
    articles = _store.list_articles(_store.raw_dir())
    for a in articles:
        if a.get("file_hash") == file_hash:
            return a["id"]
    return None


def ingest_file(
    file_path: str,
    *,
    title: Optional[str] = None,
    tags: Optional[list[str]] = None,
    source: Optional[str] = None,
) -> str:
    """
    Ingest a file into raw/. Converts to Markdown via file_converter.
    Deduplicates by SHA1 hash if present in filename.

    Returns:
        The raw article ID.

    Raises:
        ValueError: If a duplicate file is detected.
    """
    from file2md import convert_to_markdown  # github.com/liamsysmind/file2md

    content = convert_to_markdown(file_path)

    # Derive title from filename if not provided
    if not title:
        from pathlib import Path as P
        title = P(file_path).stem.replace("_", " ").replace("-", " ")

    # Extract hash and clean title
    file_hash, display_title = _extract_file_hash(title)

    # Check for duplicates
    if file_hash:
        existing = _find_duplicate(file_hash)
        if existing:
            raise ValueError(f"Duplicate file detected (hash={file_hash[:12]}...), existing article: {existing}")

    article_id = _store.make_raw_id(display_title)
    now = _now_iso()

    meta = {
        "id": article_id,
        "title": display_title,
        "source": source or "file",
        "source_url": None,
        "file_hash": file_hash,
        "original_file": file_path,
        "tags": tags or [],
        "created_at": now,
        "compiled": False,
        "compiled_to": None,
    }

    _store.write_article(_store.raw_dir(), article_id, meta, content)

    _index.upsert_article(
        article_id, scope="raw", title=display_title, content=content,
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
