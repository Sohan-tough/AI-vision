import os
from typing import Dict

from groq import Groq


def explain_with_groq(match: Dict) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "Groq explanation skipped: `GROQ_API_KEY` is not set in environment."

    snippet = match.get("snippet", "")
    component = match.get("component", "Unknown")
    file_path = match.get("file", "Unknown")

    prompt = f"""
Explain this frontend code snippet in simple terms.
Mention:
- what UI element it creates,
- where it likely appears on screen,
- why it appears,
- which component it belongs to,
- important props/state hints,
- any click/navigation behavior.

Component: {component}
File: {file_path}

Code:
{snippet}
"""
    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a concise frontend code explainer."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=450,
        )
        return completion.choices[0].message.content.strip()
    except Exception as exc:
        return f"Groq explanation failed: {exc}"
