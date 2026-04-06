"""
_store.py — 磁碟路徑管理、raw/ wiki/ 讀寫、YAML frontmatter 解析
"""
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# --- Configuration ---

_base_path: Path | None = None


def _get_base() -> Path:
    """Return the knowledge base path, initializing if needed."""
    global _base_path
    if _base_path is None:
        env = os.getenv("KNOWLEDGE_BASE")
        _base_path = Path(env) if env else Path.home() / "linebot" / "knowledge"
    return _base_path


def set_base(path: str | Path) -> None:
    """Override the knowledge base path."""
    global _base_path
    _base_path = Path(path)


def raw_dir() -> Path:
    return _get_base() / "raw"


def wiki_dir() -> Path:
    return _get_base() / "wiki"


def index_db_path() -> Path:
    return _get_base() / "index.db"


def ensure_dirs() -> None:
    """Create raw/, wiki/, and base directory if they don't exist."""
    raw_dir().mkdir(parents=True, exist_ok=True)
    wiki_dir().mkdir(parents=True, exist_ok=True)


# --- Slugify ---


def slugify(text: str, max_len: int = 60) -> str:
    """Convert text to a filesystem-safe slug."""
    text = unicodedata.normalize("NFKC", text)
    # Keep CJK characters, alphanumeric, spaces
    text = re.sub(r"[^\w\s\u4e00-\u9fff\u3400-\u4dbf]", "", text)
    text = re.sub(r"\s+", "_", text.strip())
    text = text[:max_len].rstrip("_")
    return text.lower() if text else "untitled"


def make_raw_id(title: str | None = None) -> str:
    """Generate a raw article ID: {YYYYMMDD}_{HHMMSS}_{hash}. Pure timestamp + short hash, no slugified title."""
    import hashlib
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d_%H%M%S")
    seed = f"{ts}{title or ''}{id(now)}"
    short_hash = hashlib.sha256(seed.encode()).hexdigest()[:6]
    return f"{ts}_{short_hash}"


# --- Frontmatter ---


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Parse YAML frontmatter from a markdown string.

    Returns:
        (metadata_dict, body_content)
    """
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    meta_str = parts[1].strip()
    body = parts[2].lstrip("\n")

    meta = {}
    for line in meta_str.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        # Parse simple types
        if value.startswith("[") and value.endswith("]"):
            # Simple list: [a, b, c]
            inner = value[1:-1]
            meta[key] = [v.strip().strip("\"'") for v in inner.split(",") if v.strip()]
        elif value.lower() in ("true", "false"):
            meta[key] = value.lower() == "true"
        elif value in ("null", "~", ""):
            meta[key] = None
        elif value.startswith('"') and value.endswith('"'):
            meta[key] = value[1:-1]
        else:
            meta[key] = value

    return meta, body


def render_frontmatter(meta: dict) -> str:
    """Render a metadata dict as YAML frontmatter string."""
    lines = ["---"]
    for key, value in meta.items():
        if value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, list):
            items = ", ".join(f'"{v}"' for v in value)
            lines.append(f"{key}: [{items}]")
        else:
            # Quote strings that contain special chars
            sv = str(value)
            if any(c in sv for c in ":#[]{}"):
                lines.append(f'{key}: "{sv}"')
            else:
                lines.append(f"{key}: {sv}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# --- File I/O ---


def write_article(directory: Path, article_id: str, meta: dict, body: str) -> Path:
    """Write a markdown file with frontmatter to the given directory."""
    path = directory / f"{article_id}.md"
    content = render_frontmatter(meta) + "\n" + body
    path.write_text(content, encoding="utf-8")
    return path


def read_article(directory: Path, article_id: str) -> tuple[dict, str]:
    """
    Read a markdown file from the given directory.

    Returns:
        (metadata_dict, body_content)

    Raises:
        FileNotFoundError if the article doesn't exist.
    """
    path = directory / f"{article_id}.md"
    text = path.read_text(encoding="utf-8")
    return parse_frontmatter(text)


def read_article_full(directory: Path, article_id: str) -> str:
    """Read the full content of an article (frontmatter + body)."""
    path = directory / f"{article_id}.md"
    return path.read_text(encoding="utf-8")


def delete_article(directory: Path, article_id: str) -> bool:
    """Delete an article file. Returns True if it existed."""
    path = directory / f"{article_id}.md"
    if path.exists():
        path.unlink()
        return True
    return False


def list_articles(directory: Path) -> list[dict]:
    """
    List all .md files in a directory, parsing their frontmatter.

    Returns:
        List of metadata dicts (each includes 'id' from filename stem).
    """
    articles = []
    if not directory.exists():
        return articles
    for path in sorted(directory.glob("*.md")):
        if path.name.startswith("_"):
            continue
        meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        meta.setdefault("id", path.stem)
        articles.append(meta)
    return articles
