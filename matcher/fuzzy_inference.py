from typing import Dict


def triangular(x: float, a: float, b: float, c: float) -> float:
    x = max(0.0, min(1.0, float(x)))
    if x == b:
        return 1.0
    if a == b and x <= b:
        return 1.0
    if b == c and x >= b:
        return 1.0
    if x <= a or x >= c:
        return 0.0
    if x < b:
        return max(0.0, min(1.0, (x - a) / max(b - a, 1e-9)))
    return max(0.0, min(1.0, (c - x) / max(c - b, 1e-9)))


def trapezoidal(x: float, a: float, b: float, c: float, d: float) -> float:
    x = max(0.0, min(1.0, float(x)))
    if a == b and x <= b:
        return 1.0
    if c == d and x >= c:
        return 1.0
    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if x < b:
        return (x - a) / max(b - a, 1e-9)
    return (d - x) / max(d - c, 1e-9)


def _quality_memberships(value: float) -> Dict[str, float]:
    return {
        "low": trapezoidal(value, 0.0, 0.0, 0.22, 0.45),
        "medium": triangular(value, 0.25, 0.52, 0.78),
        "high": trapezoidal(value, 0.58, 0.78, 1.0, 1.0),
    }


def _penalty_memberships(value: float) -> Dict[str, float]:
    return {
        "low": trapezoidal(value, 0.0, 0.0, 0.04, 0.1),
        "medium": triangular(value, 0.05, 0.16, 0.28),
        "high": trapezoidal(value, 0.18, 0.3, 1.0, 1.0),
    }


def fuzzy_match_confidence(
    *,
    text_sim: float,
    search_sim: float,
    nearby_sim: float,
    token_overlap: float,
    tag_sim: float,
    exact_match_bonus: float = 0.0,
    generic_penalty: float = 0.0,
    support_penalty: float = 0.0,
    container_penalty: float = 0.0,
    specificity_bonus: float = 0.0,
    source_bonus: float = 0.0,
) -> Dict[str, object]:
    text = _quality_memberships(text_sim)
    search = _quality_memberships(search_sim)
    nearby = _quality_memberships(nearby_sim)
    overlap = _quality_memberships(token_overlap)
    tag = _quality_memberships(tag_sim)
    penalty = _penalty_memberships(
        min(1.0, generic_penalty + support_penalty + container_penalty)
    )
    specificity = _quality_memberships(min(1.0, specificity_bonus * 6.0))
    source = _quality_memberships(min(1.0, source_bonus * 8.0))
    exact = _quality_memberships(min(1.0, exact_match_bonus * 4.0))

    low_rules = {
        "weak_text_and_search": min(text["low"], search["low"]),
        "high_penalty": penalty["high"],
        "weak_text_with_low_overlap": min(text["low"], overlap["low"]),
    }
    medium_rules = {
        "medium_text_with_context": min(text["medium"], max(search["medium"], nearby["medium"])),
        "high_text_but_medium_penalty": min(text["high"], penalty["medium"]),
        "specific_element_with_medium_text": min(specificity["high"], text["medium"]),
    }
    high_rules = {
        "high_text_and_tag": min(text["high"], tag["high"]),
        "high_text_and_search": min(text["high"], search["high"]),
        "exact_or_source_backed_match": max(exact["medium"], min(text["medium"], source["high"])),
        "context_supported_visible_match": min(text["medium"], nearby["high"], overlap["medium"]),
    }

    low_strength = max(low_rules.values()) if low_rules else 0.0
    medium_strength = max(medium_rules.values()) if medium_rules else 0.0
    high_strength = max(high_rules.values()) if high_rules else 0.0

    denominator = low_strength + medium_strength + high_strength
    if denominator == 0:
        confidence = 0.0
    else:
        confidence = (
            low_strength * 0.2
            + medium_strength * 0.55
            + high_strength * 0.9
        ) / denominator

    labels = {
        "low": low_strength,
        "medium": medium_strength,
        "high": high_strength,
    }
    best_label = max(labels, key=labels.get)

    fired_rules = []
    for name, strength in {**low_rules, **medium_rules, **high_rules}.items():
        if strength >= 0.18:
            fired_rules.append({"rule": name, "strength": round(strength, 3)})

    fired_rules.sort(key=lambda item: item["strength"], reverse=True)

    return {
        "score": round(max(0.0, min(1.0, confidence)), 4),
        "label": best_label.capitalize(),
        "memberships": {
            "text": {k: round(v, 3) for k, v in text.items()},
            "search": {k: round(v, 3) for k, v in search.items()},
            "nearby": {k: round(v, 3) for k, v in nearby.items()},
            "overlap": {k: round(v, 3) for k, v in overlap.items()},
            "tag": {k: round(v, 3) for k, v in tag.items()},
            "penalty": {k: round(v, 3) for k, v in penalty.items()},
        },
        "rule_strengths": fired_rules[:5],
    }
