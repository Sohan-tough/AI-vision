import os
from typing import Dict, List


def ensure_session_defaults(session_state) -> None:
    defaults = {
        "repo_root": None,
        "temp_dir": None,
        "index": [],
        "index_stats": {},
        "ocr_main": "",
        "ocr_nearby": [],
        "matches": [],
    }
    for key, value in defaults.items():
        if key not in session_state:
            session_state[key] = value


def format_match_title(match: Dict, idx: int) -> str:
    component = match.get("component", "Unknown")
    text = match.get("text", "").strip() or "Untitled"
    return f"{idx}. {component} - {text}"


def pretty_nearby(values: List[str], limit: int = 8) -> str:
    values = [v for v in values if v]
    return ", ".join(values[:limit]) if values else "N/A"


def tesseract_check_hint() -> str:
    # pytesseract needs a system tesseract binary.
    return "Make sure Tesseract is installed on your OS (e.g., `sudo apt install tesseract-ocr`)."


def is_image_file(name: str) -> bool:
    ext = os.path.splitext(name.lower())[1]
    return ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
