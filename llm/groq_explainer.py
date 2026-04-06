import os
from typing import Dict, Optional

from groq import Groq


def explain_with_groq(match: Dict, query_context: Optional[Dict] = None) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "Groq explanation skipped: `GROQ_API_KEY` is not set in environment."

    snippet = match.get("matched_excerpt") or match.get("snippet", "")
    component = match.get("component", "Unknown")
    file_path = match.get("file", "Unknown")
    line_start = match.get("line_start", "unknown")
    line_end = match.get("line_end", "unknown")
    tag = match.get("tag", "unknown")
    text = match.get("text", "")
    match_reasons = match.get("match_reasons", [])

    ocr_text = ""
    ocr_nearby = []
    if query_context:
        ocr_text = query_context.get("ocr_text", "")
        ocr_nearby = query_context.get("ocr_nearby", [])

    prompt = f"""
You are analyzing a retrieved code candidate for a UI screenshot match.

RETRIEVAL CONTEXT:
- OCR text from screenshot: "{ocr_text}"
- Nearby OCR tokens: {", ".join(ocr_nearby[:10]) if ocr_nearby else "None"}
- Match reasons: {", ".join(match_reasons) if match_reasons else "Not provided"}

CANDIDATE LOCATION:
- File: {file_path}
- Lines: {line_start}-{line_end}

CANDIDATE DETAILS:
- Component: {component}
- Tag type: {tag}
- Visible text: "{text}"

Code snippet:
{snippet}

Instructions:
1. Start by stating what UI component this most likely is (for example: page heading, button, form field, section title, card text, navigation item, paragraph).
2. Explain only what is directly supported by the provided code.
3. Mention any visible styling linkage such as classes, IDs, semantic tags, or stylesheet connections if present in the snippet.
4. Mention visible functionality or interaction only if the snippet shows it. If not, say "Not visible in provided code".
5. Do not invent props, state, handlers, routes, or external behavior unless visible in the snippet.
6. End with one short sentence on why this snippet likely matched the screenshot text.
"""
    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a careful code analyst. Stay grounded in the supplied code and explicitly acknowledge uncertainty when evidence is missing."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=300,
        )
        return completion.choices[0].message.content.strip()
    except Exception as exc:
        return f"Groq explanation failed: {exc}"
