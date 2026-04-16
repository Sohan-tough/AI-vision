from typing import Dict, List

from matcher.scoring import (
    broad_container_penalty,
    final_score,
    generic_query_penalty,
    heading_priority_bonus,
    is_weak_query,
    nearby_similarity,
    render_source_bonus,
    specific_element_bonus,
    tag_similarity,
    supporting_file_penalty,
    text_similarity,
    token_overlap_score,
)
from matcher.fuzzy_inference import fuzzy_match_confidence


def _extract_match_excerpt(element_snippet: str, snippet: str, query_text: str, chunk_text: str) -> str:
    preferred_snippet = element_snippet or snippet
    if not preferred_snippet:
        return ""

    lines = [line.rstrip() for line in preferred_snippet.splitlines() if line.strip()]
    if not lines:
        return ""

    needles = [value.strip().lower() for value in (query_text, chunk_text) if value and value.strip()]
    for needle in needles:
        for idx, line in enumerate(lines):
            if needle in line.lower():
                start = max(0, idx - 1)
                end = min(len(lines), idx + 2)
                return "\n".join(lines[start:end])

    return "\n".join(lines[:3])


def match_chunks(ocr_text: str, ocr_nearby: List[str], index: List[Dict], top_k: int = 3) -> List[Dict]:
    if not index:
        return []

    grouped_results: Dict[str, Dict] = {}
    query_penalty = generic_query_penalty(ocr_text)
    weak_query = is_weak_query(ocr_text)

    for chunk in index:
        chunk_text = chunk.get("text", "")
        element_search_text = chunk.get("element_search_text") or chunk_text
        search_text = chunk.get("search_text") or " ".join(
            [
                chunk_text,
                chunk.get("component", ""),
                chunk.get("class", ""),
                chunk.get("id", ""),
                chunk.get("aria_label", ""),
                chunk.get("placeholder", ""),
                " ".join(chunk.get("nearby_text", [])),
                chunk.get("file", ""),
            ]
        )
        text_sim = text_similarity(ocr_text, chunk_text)
        element_text_sim = text_similarity(ocr_text, element_search_text)
        search_sim = text_similarity(ocr_text, search_text)
        overlap_sim = token_overlap_score(ocr_text, search_text)
        line_span = max(1, int(chunk.get("line_end", 0) or 0) - int(chunk.get("line_start", 0) or 0) + 1)
        text_word_count = len((chunk_text or "").split())
        exact_line_start = chunk.get("exact_line_start") or chunk.get("line_start") or 0
        exact_line_end = chunk.get("exact_line_end") or chunk.get("line_end") or 0

        exact_match_bonus = 0.0
        exact_text_match = ocr_text and chunk_text and ocr_text.strip().lower() == chunk_text.strip().lower()
        exact_element_match = ocr_text and element_search_text and ocr_text.strip().lower() in element_search_text.strip().lower()
        if exact_text_match or exact_element_match:
            exact_match_bonus = 0.22
            text_sim = 1.0
            search_sim = max(search_sim, 0.95)
            element_text_sim = max(element_text_sim, 0.98)

        nearby_sim = nearby_similarity(ocr_nearby, chunk.get("nearby_text", []))
        effective_nearby_sim = nearby_sim if weak_query else nearby_sim * 0.35
        tag_sim = tag_similarity(chunk.get("tag", ""))
        source_bonus = render_source_bonus(chunk.get("file", ""), chunk.get("tag", ""), text_sim)
        support_penalty = supporting_file_penalty(
            chunk.get("file", ""),
            text_sim,
            exact_match=exact_match_bonus > 0,
        )
        specificity_bonus = specific_element_bonus(chunk.get("tag", ""), line_span, text_word_count)
        specificity_bonus += heading_priority_bonus(
            chunk.get("tag", "")
        )
        container_penalty = broad_container_penalty(
            chunk.get("tag", ""),
            line_span,
            text_word_count,
            exact_match=exact_match_bonus > 0,
        )
        effective_penalty = max(0.0, query_penalty - (0.08 if effective_nearby_sim > 0.45 else 0.0))
        heuristic_score = final_score(
            text_sim=text_sim,
            search_sim=search_sim,
            nearby_sim=effective_nearby_sim,
            token_overlap=overlap_sim,
            tag_sim=tag_sim,
            exact_match_bonus=exact_match_bonus,
            generic_penalty=effective_penalty,
            source_bonus=source_bonus,
            support_penalty=support_penalty,
            specificity_bonus=specificity_bonus,
            container_penalty=container_penalty,
        )
        fuzzy_result = fuzzy_match_confidence(
            text_sim=text_sim,
            search_sim=search_sim,
            nearby_sim=effective_nearby_sim,
            token_overlap=overlap_sim,
            tag_sim=tag_sim,
            exact_match_bonus=exact_match_bonus,
            generic_penalty=effective_penalty,
            support_penalty=support_penalty,
            container_penalty=container_penalty,
            specificity_bonus=specificity_bonus,
            source_bonus=source_bonus,
        )
        score = (0.75 * heuristic_score) + (0.25 * fuzzy_result["score"])

        # If the element itself does not meaningfully resemble the OCR text,
        # treat broader parent/context matches as weak evidence.
        if not weak_query and element_text_sim < 0.55 and text_sim < 0.75:
            score *= 0.35
        elif weak_query and element_text_sim < 0.4 and text_sim < 0.65:
            score *= 0.6

        if score <= 0.2:
            continue

        reason_parts: List[str] = []
        if exact_match_bonus > 0:
            reason_parts.append("exact OCR text match")
        elif element_text_sim >= 0.9:
            reason_parts.append("element snippet strongly matches OCR text")
        elif text_sim >= 0.82:
            reason_parts.append("strong text similarity")
        elif search_sim >= 0.82:
            reason_parts.append("text matched broader component context")

        if effective_nearby_sim >= 0.45:
            reason_parts.append("nearby OCR text matched nearby code context")
        elif nearby_sim >= 0.45 and not weak_query:
            reason_parts.append("nearby OCR text gave minor supporting context")
        if overlap_sim >= 0.5:
            reason_parts.append("keyword overlap with component metadata")
        if tag_sim >= 0.95:
            reason_parts.append(f"high-signal tag `{chunk.get('tag', '')}`")
        if source_bonus > 0.07:
            reason_parts.append("render-source file strongly matches visible UI text")
        if support_penalty > 0.0:
            reason_parts.append("supporting logic file was deprioritized")
        if specificity_bonus > 0.0:
            reason_parts.append("specific UI element match was preferred")
        if container_penalty >= 0.18:
            reason_parts.append("broad container match was penalized")
        if element_text_sim < 0.55 and text_sim >= 0.75:
            reason_parts.append("match relied mostly on broader context")

        group_key = f"{chunk.get('file', '')}::{exact_line_start}:{exact_line_end}::{chunk.get('tag', '')}"
        grouped = grouped_results.get(group_key)

        scored = dict(chunk)
        scored["score"] = score
        scored["score_pct"] = round(score * 100, 2)
        scored["heuristic_score"] = round(heuristic_score, 4)
        scored["fuzzy_score"] = fuzzy_result["score"]
        scored["fuzzy_label"] = fuzzy_result["label"]
        scored["fuzzy_rules"] = fuzzy_result["rule_strengths"]
        scored["text_similarity"] = round(text_sim, 3)
        scored["element_text_similarity"] = round(element_text_sim, 3)
        scored["search_similarity"] = round(search_sim, 3)
        scored["nearby_similarity"] = round(effective_nearby_sim, 3)
        scored["token_overlap"] = round(overlap_sim, 3)
        scored["match_reasons"] = reason_parts or ["partial textual match"]
        scored["matched_excerpt"] = _extract_match_excerpt(
            chunk.get("element_snippet", ""),
            chunk.get("snippet", ""),
            ocr_text,
            chunk_text,
        )

        if not grouped:
            grouped_results[group_key] = scored
            grouped_results[group_key]["evidence_count"] = 1
            grouped_results[group_key]["_best_chunk_score"] = score
            continue

        grouped["evidence_count"] += 1
        grouped["score"] = min(1.0, max(grouped["score"], score) + 0.04)
        grouped["score_pct"] = round(grouped["score"] * 100, 2)
        grouped["heuristic_score"] = max(grouped.get("heuristic_score", 0), round(heuristic_score, 4))
        grouped["fuzzy_score"] = max(grouped.get("fuzzy_score", 0), fuzzy_result["score"])
        grouped["text_similarity"] = max(grouped["text_similarity"], round(text_sim, 3))
        grouped["element_text_similarity"] = max(grouped["element_text_similarity"], round(element_text_sim, 3))
        grouped["search_similarity"] = max(grouped["search_similarity"], round(search_sim, 3))
        grouped["nearby_similarity"] = max(grouped["nearby_similarity"], round(effective_nearby_sim, 3))
        grouped["token_overlap"] = max(grouped["token_overlap"], round(overlap_sim, 3))

        merged_reasons = grouped["match_reasons"] + reason_parts
        deduped_reasons: List[str] = []
        seen = set()
        for reason in merged_reasons:
            if reason not in seen:
                deduped_reasons.append(reason)
                seen.add(reason)
        grouped["match_reasons"] = deduped_reasons[:4]

        if score > grouped.get("_best_chunk_score", grouped["score"]):
            for field in (
                "text",
                "tag",
                "line_start",
                "line_end",
                "exact_line_start",
                "exact_line_end",
                "snippet",
                "matched_excerpt",
                "class",
                "id",
                "aria_label",
                "placeholder",
            ):
                grouped[field] = chunk.get(field, grouped.get(field))
            grouped["fuzzy_label"] = fuzzy_result["label"]
            grouped["fuzzy_rules"] = fuzzy_result["rule_strengths"]
            grouped["_best_chunk_score"] = score

    results = list(grouped_results.values())
    for result in results:
        result.pop("_best_chunk_score", None)
        if result.get("evidence_count", 0) > 1:
            reasons = result.get("match_reasons", [])
            if "multiple matching snippets in the same component" not in reasons:
                reasons.append("multiple matching snippets in the same component")
            result["match_reasons"] = reasons[:4]

    results.sort(
        key=lambda x: (
            x["score"],
            x.get("element_text_similarity", 0),
            x["text_similarity"],
            x.get("evidence_count", 0),
        ),
        reverse=True,
    )
    return results[:top_k]
