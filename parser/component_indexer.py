from typing import Dict, List


def build_index(parsed_chunks: List[Dict]) -> List[Dict]:
    """
    MVP in-memory index.
    Kept as a list for simplicity and transparency.
    """
    return parsed_chunks


def index_stats(index: List[Dict]) -> Dict:
    files = {item.get("file", "") for item in index}
    components = {item.get("component", "") for item in index}
    return {
        "total_chunks": len(index),
        "total_files": len([f for f in files if f]),
        "total_components": len([c for c in components if c]),
    }
