"""
_lint.py — wiki/ 連結分析、lint report
"""
import re

from . import _store, _index

# Match [[wikilinks]] including [[link|display text]]
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


def extract_wikilinks(content: str) -> list[str]:
    """Extract all [[wikilink]] targets from markdown content."""
    return _WIKILINK_RE.findall(content)


def update_links_for_article(article_id: str, content: str) -> None:
    """Parse wikilinks from content and update the link graph index."""
    targets = extract_wikilinks(content)
    # Normalize link targets to article IDs (slug form)
    normalized = [_store.slugify(t) for t in targets]
    _index.set_links(article_id, normalized)


def get_lint_report() -> dict:
    """
    Analyze wiki/ for issues. Pure file analysis, no LLM needed.

    Returns:
        {
            "orphans": [{"id", "title"}],         # no incoming links
            "broken_links": [{"from", "to"}],      # link target doesn't exist
            "missing_backlinks": [{"from", "to"}],  # A→B but B doesn't mention A
            "stats": {"total_articles", "total_links"}
        }
    """
    wiki_articles = _store.list_articles(_store.wiki_dir())
    wiki_ids = {a["id"] for a in wiki_articles}
    wiki_titles = {a["id"]: a.get("title", a["id"]) for a in wiki_articles}

    # Rebuild link graph from files
    all_outlinks: dict[str, list[str]] = {}
    all_inlinks: dict[str, list[str]] = {aid: [] for aid in wiki_ids}

    for article in wiki_articles:
        aid = article["id"]
        try:
            _, body = _store.read_article(_store.wiki_dir(), aid)
            targets = extract_wikilinks(body)
            normalized = [_store.slugify(t) for t in targets]
            all_outlinks[aid] = normalized

            # Update index
            _index.set_links(aid, normalized)

            for target in normalized:
                if target in all_inlinks:
                    all_inlinks[target].append(aid)
        except FileNotFoundError:
            continue

    # Orphans: articles with no incoming links (excluding index)
    orphans = [
        {"id": aid, "title": wiki_titles.get(aid, aid)}
        for aid in wiki_ids
        if not all_inlinks.get(aid) and aid != "index"
    ]

    # Broken links: link targets that don't exist as wiki articles
    broken = []
    for from_id, targets in all_outlinks.items():
        for target in targets:
            if target not in wiki_ids:
                broken.append({"from": from_id, "to": target})

    # Missing backlinks: A→B exists but B→A doesn't
    missing_backlinks = []
    for from_id, targets in all_outlinks.items():
        for target in targets:
            if target in wiki_ids:
                target_links = all_outlinks.get(target, [])
                if from_id not in target_links:
                    missing_backlinks.append({"from": from_id, "to": target})

    total_links = sum(len(v) for v in all_outlinks.values())

    return {
        "orphans": orphans,
        "broken_links": broken,
        "missing_backlinks": missing_backlinks,
        "stats": {
            "total_articles": len(wiki_ids),
            "total_links": total_links,
        },
    }


def get_wiki_graph() -> dict:
    """
    Return the full wiki link graph.

    Returns:
        {"articles": [{"id", "title", "links_to": [...], "linked_from": [...]}]}
    """
    wiki_articles = _store.list_articles(_store.wiki_dir())
    wiki_ids = {a["id"] for a in wiki_articles}

    result = []
    for article in wiki_articles:
        aid = article["id"]
        outlinks = _index.get_outlinks(aid)
        backlinks = _index.get_backlinks(aid)
        result.append({
            "id": aid,
            "title": article.get("title", aid),
            "links_to": [l for l in outlinks if l in wiki_ids],
            "linked_from": [l for l in backlinks if l in wiki_ids],
        })

    return {"articles": result}
