import re
from typing import Dict, List


HIGH_PRIORITY_TAGS = {
    "button", "a", "h1", "h2", "h3",
    "input", "label", "h4", "h5",
}

MEDIUM_PRIORITY_TAGS = {
    "span", "p", "li", "option",
    "textarea", "python_ui",
}

LOW_PRIORITY_TAGS = {
    "div", "section", "article",
    "header", "nav", "main",
}

FOOTER_SIGNALS = {
    "built with", "powered by", "copyright",
    "all rights reserved", "made with",
    "©", "credits", "attribution",
    "license", "version",
}

COMMENT_SIGNALS = {"# ", "// ", "/* ", "<!--"}


def _normalise_key(text: str) -> str:
    """
    Normalise text for use as lookup key.
    Lowercases, strips whitespace, collapses spaces.
    """
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def _tag_priority(tag: str) -> int:
    """
    Return priority score for a tag.
    Lower number = higher priority.
    """
    tag = (tag or "").lower()
    if tag in HIGH_PRIORITY_TAGS:
        return 0
    if tag in MEDIUM_PRIORITY_TAGS:
        return 1
    if tag in LOW_PRIORITY_TAGS:
        return 2
    return 3


def _is_footer_context(chunk: dict) -> bool:
    """
    Detect if a chunk is in footer/metadata context.
    These are lower priority even with exact text match.
    """
    check_text = " ".join(filter(None, [
        chunk.get("snippet", ""),
        chunk.get("element_snippet", ""),
        chunk.get("text", ""),
    ])).lower()

    if any(sig in check_text for sig in FOOTER_SIGNALS):
        return True

    tag = (chunk.get("tag", "") or "").lower()
    if tag == "footer":
        return True

    return False


def _is_comment_context(chunk: dict) -> bool:
    """Detect if chunk is inside a code comment."""
    check_text = " ".join(filter(None, [
        chunk.get("snippet", ""),
        chunk.get("element_snippet", ""),
    ])).lower()
    return any(sig in check_text for sig in COMMENT_SIGNALS)


def _chunk_sort_key(chunk: dict) -> tuple:
    """
    Sort key for ranking chunks with same lookup text.
    Lower tuple = higher priority = comes first.

    Priority order:
      1. Tag type (button/h1 before div/footer)
      2. Not in footer context
      3. Not in comment context
      4. Shorter line span (more specific element)
      5. File type (.html/.jsx before .js/.css)
    """
    tag_prio = _tag_priority(chunk.get("tag", ""))
    footer_prio = 1 if _is_footer_context(chunk) else 0
    comment_prio = 1 if _is_comment_context(chunk) else 0
    line_span = max(
        1,
        int(chunk.get("line_end", 0) or 0)
        - int(chunk.get("line_start", 0) or 0) + 1,
    )

    file_path = (chunk.get("file", "") or "").lower()
    if file_path.endswith((".html", ".htm")):
        file_prio = 0
    elif file_path.endswith((".jsx", ".tsx", ".vue")):
        file_prio = 1
    elif file_path.endswith(".py"):
        file_prio = 2
    elif file_path.endswith((".js", ".ts")):
        file_prio = 3
    else:
        file_prio = 4

    return (tag_prio, footer_prio, comment_prio, line_span, file_prio)


def build_lookup_table(chunks: List[dict]) -> Dict[str, List[dict]]:
    """
    Build a lookup table from parsed chunks.

    Input:  flat list of chunk dicts (from build_index)
    Output: dict mapping normalised text -> sorted list of chunks
    """
    table: Dict[str, List[dict]] = {}

    for chunk in chunks:
        visible_text = chunk.get("text", "")
        if not visible_text:
            continue

        key = _normalise_key(visible_text)
        if not key or len(key) < 2:
            continue

        if key not in table:
            table[key] = []
        table[key].append(chunk)

        for alt_field in ("aria_label", "placeholder"):
            alt_text = chunk.get(alt_field, "")
            if not alt_text:
                continue
            alt_key = _normalise_key(alt_text)
            if alt_key and alt_key != key and len(alt_key) >= 2:
                if alt_key not in table:
                    table[alt_key] = []
                table[alt_key].append(chunk)

    for key in table:
        table[key].sort(key=_chunk_sort_key)

    return table


def lookup(
    ocr_text: str,
    table: Dict[str, List[dict]],
    max_results: int = 5,
) -> List[dict]:
    """
    Look up OCR text in the pre-built table.

    Tries exact normalised match first.
    Then tries partial matches for multi-word queries.
    """
    if not ocr_text or not table:
        return []

    key = _normalise_key(ocr_text)
    if not key:
        return []

    compact_key = key.replace(" ", "")

    if key in table:
        return table[key][:max_results]

    for table_key, table_chunks in table.items():
        if table_key.replace(" ", "") == compact_key:
            return table_chunks[:max_results]

    results = []
    seen_keys = set()

    for table_key, table_chunks in table.items():
        if table_key in key or key in table_key:
            for chunk in table_chunks[:3]:
                chunk_id = (
                    chunk.get("file", ""),
                    chunk.get("exact_line_start", 0),
                )
                if chunk_id not in seen_keys:
                    seen_keys.add(chunk_id)
                    results.append(chunk)

    results.sort(key=_chunk_sort_key)
    return results[:max_results]


def get_table_stats(table: Dict[str, List[dict]]) -> dict:
    """Return stats about the lookup table."""
    total_entries = sum(len(v) for v in table.values())
    return {
        "unique_text_keys": len(table),
        "total_indexed_entries": total_entries,
        "avg_entries_per_key": round(
            total_entries / max(len(table), 1), 2
        ),
    }
