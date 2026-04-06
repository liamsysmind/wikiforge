"""
_index.py — SQLite FTS5 全文搜尋索引
"""
import json
import sqlite3
from typing import Optional

from . import _store


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_store.index_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                id,
                title,
                content,
                scope,
                tags,
                tokenize='unicode61'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                title TEXT NOT NULL,
                source TEXT,
                source_url TEXT,
                tags TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                compiled INTEGER DEFAULT 0,
                compiled_to TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS links (
                from_id TEXT NOT NULL,
                to_id TEXT NOT NULL,
                PRIMARY KEY (from_id, to_id)
            )
        """)


def upsert_article(
    article_id: str,
    scope: str,
    title: str,
    content: str,
    *,
    source: Optional[str] = None,
    source_url: Optional[str] = None,
    tags: Optional[list[str]] = None,
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
) -> None:
    """Insert or update an article in both the metadata table and FTS index."""
    tags_json = json.dumps(tags or [], ensure_ascii=False)
    tags_fts = " ".join(tags or [])

    with _connect() as conn:
        # Metadata table
        conn.execute(
            """INSERT INTO articles (id, scope, title, source, source_url, tags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   title=excluded.title, source=excluded.source,
                   source_url=excluded.source_url, tags=excluded.tags,
                   updated_at=excluded.updated_at""",
            (article_id, scope, title, source, source_url, tags_json,
             created_at, updated_at),
        )
        # FTS: delete old entry then insert new
        conn.execute("DELETE FROM articles_fts WHERE id = ?", (article_id,))
        conn.execute(
            "INSERT INTO articles_fts (id, title, content, scope, tags) VALUES (?, ?, ?, ?, ?)",
            (article_id, title, content, scope, tags_fts),
        )


def delete_article(article_id: str) -> None:
    """Remove an article from both tables."""
    with _connect() as conn:
        conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))
        conn.execute("DELETE FROM articles_fts WHERE id = ?", (article_id,))
        conn.execute("DELETE FROM links WHERE from_id = ? OR to_id = ?",
                      (article_id, article_id))


def mark_compiled(raw_id: str, wiki_id: str) -> None:
    """Mark a raw article as compiled, linking to its wiki counterpart."""
    with _connect() as conn:
        conn.execute(
            "UPDATE articles SET compiled = 1, compiled_to = ? WHERE id = ?",
            (wiki_id, raw_id),
        )


def search(
    query: str,
    *,
    scope: str = "wiki",
    limit: int = 10,
) -> list[dict]:
    """
    Full-text search using FTS5 with BM25 ranking.

    Args:
        query: FTS5 query string
        scope: "wiki", "raw", or "all"
        limit: Max results

    Returns:
        List of dicts with id, title, snippet, score, scope.
    """
    with _connect() as conn:
        if scope == "all":
            rows = conn.execute(
                """SELECT id, title, snippet(articles_fts, 2, '<b>', '</b>', '...', 32) as snippet,
                          rank as score, scope
                   FROM articles_fts
                   WHERE articles_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, title, snippet(articles_fts, 2, '<b>', '</b>', '...', 32) as snippet,
                          rank as score, scope
                   FROM articles_fts
                   WHERE articles_fts MATCH ? AND scope = ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, scope, limit),
            ).fetchall()

    return [
        {"id": r["id"], "title": r["title"], "snippet": r["snippet"],
         "score": r["score"], "scope": r["scope"]}
        for r in rows
    ]


def get_article_meta(article_id: str) -> Optional[dict]:
    """Get metadata for a single article."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM articles WHERE id = ?", (article_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["tags"] = json.loads(d["tags"]) if d["tags"] else []
    d["compiled"] = bool(d["compiled"])
    return d


def list_articles(scope: str, *, uncompiled_only: bool = False) -> list[dict]:
    """List articles from the metadata table."""
    with _connect() as conn:
        if uncompiled_only:
            rows = conn.execute(
                "SELECT * FROM articles WHERE scope = ? AND compiled = 0 ORDER BY created_at",
                (scope,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM articles WHERE scope = ? ORDER BY created_at",
                (scope,),
            ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        d["compiled"] = bool(d["compiled"])
        result.append(d)
    return result


# --- Link graph ---


def set_links(from_id: str, to_ids: list[str]) -> None:
    """Replace all outgoing links for an article."""
    with _connect() as conn:
        conn.execute("DELETE FROM links WHERE from_id = ?", (from_id,))
        for to_id in to_ids:
            conn.execute(
                "INSERT OR IGNORE INTO links (from_id, to_id) VALUES (?, ?)",
                (from_id, to_id),
            )


def get_backlinks(article_id: str) -> list[str]:
    """Get all articles that link to this one."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT from_id FROM links WHERE to_id = ?", (article_id,)
        ).fetchall()
    return [r["from_id"] for r in rows]


def get_outlinks(article_id: str) -> list[str]:
    """Get all articles this one links to."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT to_id FROM links WHERE from_id = ?", (article_id,)
        ).fetchall()
    return [r["to_id"] for r in rows]


def get_all_links() -> list[dict]:
    """Get the full link graph."""
    with _connect() as conn:
        rows = conn.execute("SELECT from_id, to_id FROM links").fetchall()
    return [{"from": r["from_id"], "to": r["to_id"]} for r in rows]
