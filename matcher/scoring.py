import re
from typing import List, Set

from rapidfuzz import fuzz

GENERIC_UI_TERMS = {
    "add",
    "back",
    "cancel",
    "close",
    "done",
    "edit",
    "go",
    "home",
    "learn",
    "login",
    "menu",
    "more",
    "next",
    "ok",
    "open",
    "save",
    "search",
    "send",
    "settings",
    "shop",
    "signin",
    "signup",
    "start",
    "submit",
    "view",
}


def tokenize(text: str) -> List[str]:
    if not text:
        return []
    return re.findall(r"[a-z0-9][a-z0-9_-]*", text.lower())


def token_set(text: str) -> Set[str]:
    return set(tokenize(text))


def text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a, b = a.lower().strip(), b.lower().strip()
    s1 = fuzz.ratio(a, b)
    s2 = fuzz.partial_ratio(a, b)
    s3 = fuzz.token_set_ratio(a, b)
    return max(s1, s2, s3) / 100.0


def nearby_similarity(ocr_nearby: List[str], code_nearby: List[str]) -> float:
    if not ocr_nearby or not code_nearby:
        return 0.0
    ocr_joined = " ".join(ocr_nearby)
    code_joined = " ".join(code_nearby)
    return text_similarity(ocr_joined, code_joined)


def tag_similarity(code_tag: str) -> float:
    if not code_tag:
        return 0.0
    high_value_tags = {"button", "a", "input", "label", "h1", "h2", "h3"}
    medium_value_tags = {"span", "p", "textarea", "option", "python_ui"}
    code_tag = code_tag.lower()
    if code_tag in high_value_tags:
        return 1.0
    if code_tag in medium_value_tags:
        return 0.7
    return 0.35


def heading_priority_bonus(tag: str) -> float:
    """
    Extra priority bonus for semantically important tags.
    Used to break ties when same text appears in
    multiple locations (heading vs footer etc.)
    """
    tag = (tag or "").lower()
    if tag in {"h1", "h2"}:
        return 0.12
    if tag in {"button", "a"}:
        return 0.08
    if tag in {"h3", "h4"}:
        return 0.06
    if tag in {"label", "input", "textarea"}:
        return 0.05
    if tag in {"span", "p", "python_ui"}:
        return 0.02
    return 0.0


def token_overlap_score(a: str, b: str) -> float:
    a_tokens = token_set(a)
    b_tokens = token_set(b)
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = len(a_tokens & b_tokens)
    return overlap / max(len(a_tokens), 1)


def generic_query_penalty(text: str) -> float:
    tokens = token_set(text)
    if not tokens:
        return 0.0
    if len(tokens) == 1 and next(iter(tokens)) in GENERIC_UI_TERMS:
        return 0.18
    if tokens and tokens.issubset(GENERIC_UI_TERMS):
        return 0.1
    return 0.0


def is_weak_query(text: str) -> bool:
    tokens = tokenize(text)
    joined = text.strip()
    if not joined:
        return True
    if len(joined) <= 3:
        return True
    if len(tokens) <= 1 and len(joined) <= 6:
        return True
    return False


def render_source_bonus(file_path: str, tag: str, text_sim: float) -> float:
    file_path = (file_path or "").lower()
    tag = (tag or "").lower()
    if text_sim < 0.7:
        return 0.0

    if file_path.endswith((".html", ".jsx", ".tsx")):
        return 0.08
    if "/templates/" in file_path or file_path.startswith("templates/"):
        return 0.1
    if tag in {"h1", "h2", "h3", "p", "span", "button", "a", "label"}:
        return 0.04
    return 0.0


def supporting_file_penalty(file_path: str, text_sim: float, exact_match: bool) -> float:
    file_path = (file_path or "").lower()
    if file_path.endswith(".js") and not file_path.endswith((".jsx", ".tsx")) and text_sim < 0.95 and not exact_match:
        return 0.12
    if file_path.endswith(".css") and text_sim < 0.95 and not exact_match:
        return 0.08
    return 0.0


def specific_element_bonus(tag: str, line_span: int, text_word_count: int) -> float:
    tag = (tag or "").lower()
    if tag in {"button", "a", "label", "option", "h1", "h2", "h3", "h4", "p", "span"} and line_span <= 6:
        return 0.08
    if tag in {"input", "textarea"} and line_span <= 4:
        return 0.08
    if tag in {"div", "section"} and line_span <= 4 and text_word_count <= 6:
        return 0.03
    return 0.0


def broad_container_penalty(tag: str, line_span: int, text_word_count: int, exact_match: bool) -> float:
    tag = (tag or "").lower()
    if exact_match:
        return 0.0
    if tag in {"html", "body", "head"}:
        return 0.4
    if tag in {"main", "header", "footer", "section", "article", "div"} and line_span >= 12:
        return 0.18
    if text_word_count >= 20:
        return 0.14
    if text_word_count >= 10 and line_span >= 8:
        return 0.08
    return 0.0


def final_score(
    text_sim: float,
    search_sim: float,
    nearby_sim: float,
    token_overlap: float,
    tag_sim: float,
    exact_match_bonus: float = 0.0,
    generic_penalty: float = 0.0,
    source_bonus: float = 0.0,
    support_penalty: float = 0.0,
    specificity_bonus: float = 0.0,
    container_penalty: float = 0.0,
) -> float:
    score = (
        0.35 * text_sim
        + 0.20 * search_sim
        + 0.15 * nearby_sim
        + 0.10 * token_overlap
        + 0.20 * tag_sim
        + exact_match_bonus
        + source_bonus
        + specificity_bonus
        - generic_penalty
        - support_penalty
        - container_penalty
    )
    return max(0.0, min(score, 1.0))
