from typing import List

from rapidfuzz import fuzz


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
    high_value_tags = {"button", "a", "input", "label", "h1", "h2", "h3", "span"}
    return 1.0 if code_tag.lower() in high_value_tags else 0.4


def final_score(text_sim: float, nearby_sim: float, tag_sim: float) -> float:
    score = 0.5 * text_sim + 0.3 * nearby_sim + 0.2 * tag_sim
    return max(0.0, min(score, 1.0))
