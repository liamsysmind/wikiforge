# WikiForge

Karpathy-style LLM Knowledge Base. Forge structured wiki from raw materials.

```
raw/     ← raw materials (articles, documents, URLs)
  ↓ LLM compile
wiki/    ← structured wiki (summaries, concepts, [[wikilinks]])
  ↓ LLM lint
wiki/    ← self-repair: fix inconsistencies, fill gaps, build links
```

## Design Principles

- **Independent module** — no dependency on any chat platform, LLM SDK, or application framework
- **LLM-agnostic** — the module provides data and storage; the caller drives the LLM
- **File-based** — all knowledge stored as human-readable Markdown with YAML frontmatter
- **Obsidian-compatible** — wiki/ is a valid Obsidian vault
- **SQLite FTS5** — full-text search with BM25 ranking, no vector DB needed

## Install

```bash
pip install git+https://github.com/liamsysmind/wikiforge.git
```

## Quick Start

```python
import knowledge

knowledge.init()  # creates ~/linebot/knowledge/{raw,wiki,index.db}

# Ingest
article_id = knowledge.ingest_text("Some content", title="My Article", tags=["test"])
knowledge.ingest_file("/path/to/document.pdf", tags=["paper"])
knowledge.ingest_url("https://example.com", "Page content", title="Example")

# Search
results = knowledge.search("query", scope="wiki", limit=10)

# Read / Write wiki
content = knowledge.read_wiki("article_id")
knowledge.write_wiki("my_article", "# Title\n\nContent with [[wikilinks]]")

# Compile pipeline
tasks = knowledge.get_compile_tasks()  # uncompiled raw articles
knowledge.mark_compiled(raw_id, wiki_id)

# Lint
report = knowledge.get_lint_report()  # orphans, broken links, missing backlinks
```

## Configuration

```bash
export KNOWLEDGE_BASE=~/linebot/knowledge  # default
```

Or in code:
```python
knowledge.init(base_path="/custom/path")
```

## Data Layout

```
~/linebot/knowledge/
  raw/          # markdown files with YAML frontmatter
  wiki/         # compiled wiki articles (Obsidian vault)
  index.db      # SQLite FTS5 search index
```
