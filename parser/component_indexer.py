from typing import Dict, List

from parser.component_extractor import (
    build_lookup_table,
    get_table_stats,
)


def build_index(parsed_chunks: List[Dict]) -> List[Dict]:
    """
    MVP in-memory index.
    Kept as a list for simplicity and transparency.
    """
    return parsed_chunks


def build_full_index(parsed_chunks: List[Dict]) -> tuple:
    """
    Build both the flat index AND the lookup table.

    Returns:
      (flat_index, lookup_table)

    flat_index   -> existing list of chunk dicts
    lookup_table -> new pre-built dict for O(1) search
    """
    flat_index = build_index(parsed_chunks)
    lookup_table = build_lookup_table(flat_index)
    return flat_index, lookup_table


def index_stats(
    index: List[Dict],
    lookup_table: Dict = None,
) -> Dict:
    files = {item.get("file", "") for item in index}
    components = {item.get("component", "") for item in index}

    stats = {
        "total_chunks": len(index),
        "total_files": len([f for f in files if f]),
        "total_components": len([c for c in components if c]),
    }

    if lookup_table is not None:
        stats["lookup_keys"] = len(lookup_table)

    return stats
