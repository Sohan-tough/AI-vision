import re
from collections import Counter
from typing import Dict, List, Tuple

import cv2
import numpy as np
import pytesseract
from rapidfuzz import fuzz


def _deskew(gray: np.ndarray) -> np.ndarray:
    coords = np.column_stack(np.where(gray > 0))
    if len(coords) < 50:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < 0.5:
        return gray
    h, w = gray.shape[:2]
    m = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(gray, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def preprocess_variants(img: np.ndarray) -> List[np.ndarray]:
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    # Upscale for small text regions.
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    contrast = cv2.convertScaleAbs(gray, alpha=1.4, beta=8)
    blur = cv2.GaussianBlur(contrast, (3, 3), 0)
    deskewed = _deskew(blur)
    _, thresh = cv2.threshold(deskewed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(deskewed, -1, sharpen_kernel)
    return [img, cv2.cvtColor(deskewed, cv2.COLOR_GRAY2RGB), cv2.cvtColor(thresh, cv2.COLOR_GRAY2RGB), cv2.cvtColor(sharpened, cv2.COLOR_GRAY2RGB)]


def _clean_token(token: str) -> str:
    token = token.strip()
    token = re.sub(r"[^\w\-]", "", token)
    return token


def _valid_token(token: str) -> bool:
    if len(token) < 2:
        return False
    if re.fullmatch(r"[_\W]+", token):
        return False
    if re.fullmatch(r"\d+", token):
        return False
    return True


def _extract_tokens_with_conf(img: np.ndarray, conf_threshold: float = 0.40) -> List[str]:
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config="--oem 3 --psm 6")
    tokens = []
    n = len(data.get("text", []))
    for i in range(n):
        raw = data["text"][i] or ""
        conf_raw = data["conf"][i]
        try:
            conf = max(0.0, float(conf_raw)) / 100.0
        except Exception:
            conf = 0.0
        token = _clean_token(raw)
        if conf >= conf_threshold and _valid_token(token):
            tokens.append(token)
    return tokens


def _extract_tokens_and_lines(img: np.ndarray, conf_threshold: float = 0.40) -> Tuple[List[str], List[Tuple[str, float]]]:
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config="--oem 3 --psm 6")
    tokens: List[str] = []
    line_map: Dict[Tuple[int, int, int], List[Tuple[int, str, float]]] = {}
    n = len(data.get("text", []))
    for i in range(n):
        raw = data["text"][i] or ""
        conf_raw = data["conf"][i]
        try:
            conf = max(0.0, float(conf_raw)) / 100.0
        except Exception:
            conf = 0.0

        token = _clean_token(raw)
        if conf < conf_threshold or not _valid_token(token):
            continue

        tokens.append(token)
        key = (
            int(data.get("block_num", [0] * n)[i]),
            int(data.get("par_num", [0] * n)[i]),
            int(data.get("line_num", [0] * n)[i]),
        )
        left = int(data.get("left", [0] * n)[i])
        line_map.setdefault(key, []).append((left, token, conf))

    line_candidates: List[Tuple[str, float]] = []
    for items in line_map.values():
        ordered = sorted(items, key=lambda item: item[0])
        words = [token for _, token, _ in ordered]
        if not words:
            continue
        phrase = " ".join(words).strip()
        avg_conf = sum(conf for _, _, conf in ordered) / max(len(ordered), 1)
        if phrase:
            line_candidates.append((phrase, avg_conf))

    return tokens, line_candidates


def _majority_merge(pass_texts: List[str]) -> str:
    if not pass_texts:
        return ""
    if len(pass_texts) == 1:
        return pass_texts[0]
    counts = Counter(pass_texts)
    winner, winner_count = counts.most_common(1)[0]
    if winner_count >= 2:
        return winner

    best = pass_texts[0]
    best_score = -1
    for candidate in pass_texts:
        score = sum(fuzz.ratio(candidate.lower(), other.lower()) for other in pass_texts)
        if score > best_score:
            best_score = score
            best = candidate
    return best


def _phrase_quality(text: str, confidence: float) -> float:
    words = [word for word in text.split() if word]
    word_bonus = min(len(words), 5) * 0.18
    length_bonus = min(len(text), 48) / 120.0
    return confidence + word_bonus + length_bonus


def _select_best_phrase(candidates: List[Tuple[str, float]]) -> str:
    if not candidates:
        return ""

    merged_scores: Dict[str, float] = {}
    original_texts: Dict[str, str] = {}
    for text, confidence in candidates:
        normalized = re.sub(r"\s+", " ", text).strip().lower()
        if not normalized:
            continue
        score = _phrase_quality(text, confidence)
        merged_scores[normalized] = merged_scores.get(normalized, 0.0) + score
        existing = original_texts.get(normalized, "")
        if len(text) > len(existing):
            original_texts[normalized] = text

    if not merged_scores:
        return ""

    best_key = max(merged_scores, key=merged_scores.get)
    return original_texts[best_key]


def run_ocr_multistage(img: np.ndarray, conf_threshold: float = 0.40) -> Tuple[str, List[str]]:
    variants = preprocess_variants(img)
    phrase_candidates: List[Tuple[str, float]] = []
    fallback_candidate_texts: List[str] = []
    all_tokens: List[str] = []
    for variant in variants:
        tokens, line_candidates = _extract_tokens_and_lines(variant, conf_threshold=conf_threshold)
        if tokens:
            all_tokens.extend(tokens)
            phrase_candidates.extend(line_candidates)
            fallback_candidate_texts.append(" ".join(tokens))

    main_text = _select_best_phrase(phrase_candidates)
    if not main_text:
        main_text = _majority_merge(fallback_candidate_texts)

    nearby_unique = []
    seen = set()
    for token in all_tokens:
        key = token.lower()
        if key not in seen:
            nearby_unique.append(token)
            seen.add(key)
    return main_text, nearby_unique[:20]
