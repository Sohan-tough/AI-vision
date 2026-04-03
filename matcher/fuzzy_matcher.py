from typing import Dict, List

from matcher.scoring import final_score, nearby_similarity, tag_similarity, text_similarity


def match_chunks(ocr_text: str, ocr_nearby: List[str], index: List[Dict], top_k: int = 3) -> List[Dict]:
    if not index:
        return []

    results = []
    for chunk in index:
        chunk_text = chunk.get("text", "")
        text_sim = text_similarity(ocr_text, chunk_text)

        # Favor exact matches strongly.
        if ocr_text and chunk_text and ocr_text.strip().lower() == chunk_text.strip().lower():
            text_sim = 1.0

        nearby_sim = nearby_similarity(ocr_nearby, chunk.get("nearby_text", []))
        tag_sim = tag_similarity(chunk.get("tag", ""))
        score = final_score(text_sim, nearby_sim, tag_sim)

        if score > 0.15:
            scored = dict(chunk)
            scored["score"] = score
            scored["score_pct"] = round(score * 100, 2)
            scored["text_similarity"] = round(text_sim, 3)
            scored["nearby_similarity"] = round(nearby_sim, 3)
            results.append(scored)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
