import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from parser.repo_cloner import should_skip_dir


SUPPORTED_EXTENSIONS = {".html", ".js", ".jsx", ".ts", ".tsx", ".css"}
ELEMENT_PATTERN = re.compile(r"<(?P<tag>[a-zA-Z][a-zA-Z0-9]*)\s*(?P<attrs>[^>]*)>(?P<body>.*?)</\1>", re.DOTALL)
ATTR_PATTERN = re.compile(r'([a-zA-Z_:][a-zA-Z0-9_:.-]*)\s*=\s*["\']([^"\']+)["\']')
FUNC_COMPONENT_PATTERN = re.compile(r"(?:function|const)\s+([A-Z][A-Za-z0-9_]*)")


@dataclass
class ParsedChunk:
    text: str
    tag: str
    file: str
    line_start: int
    line_end: int
    component: str
    class_name: str
    element_id: str
    aria_label: str
    placeholder: str
    nearby_text: List[str]
    snippet: str

    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "tag": self.tag,
            "file": self.file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "component": self.component,
            "class": self.class_name,
            "id": self.element_id,
            "aria_label": self.aria_label,
            "placeholder": self.placeholder,
            "nearby_text": self.nearby_text,
            "snippet": self.snippet,
        }


def _extract_attrs(attrs_raw: str) -> Dict[str, str]:
    return {k.lower(): v.strip() for k, v in ATTR_PATTERN.findall(attrs_raw or "")}


def _approx_line_number(text: str, idx: int) -> int:
    return text[:idx].count("\n") + 1


def _clean_text(value: str) -> str:
    value = re.sub(r"\{[^}]+\}", " ", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _extract_component_name(content: str, fallback: str) -> str:
    match = FUNC_COMPONENT_PATTERN.search(content)
    if match:
        return match.group(1)
    return fallback


def _extract_nearby_texts(content: str, element_start: int, window_chars: int = 400) -> List[str]:
    start = max(0, element_start - window_chars)
    end = min(len(content), element_start + window_chars)
    snippet = content[start:end]
    raw_texts = [_clean_text(t) for t in re.findall(r">([^<>]{1,120})<", snippet)]
    filtered = []
    for text in raw_texts:
        if text and len(text) > 1 and text not in filtered:
            filtered.append(text)
    return filtered[:8]


def parse_file(file_path: str, repo_root: str) -> List[Dict]:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return []

    rel_path = os.path.relpath(file_path, repo_root)
    component_name = _extract_component_name(content, os.path.splitext(os.path.basename(file_path))[0])
    chunks: List[Dict] = []

    for match in ELEMENT_PATTERN.finditer(content):
        attrs = _extract_attrs(match.group("attrs"))
        body_text = _clean_text(match.group("body"))
        aria_label = attrs.get("aria-label", "")
        placeholder = attrs.get("placeholder", "")
        value = attrs.get("value", "")

        visible_text = body_text or aria_label or placeholder or value
        if not visible_text:
            continue

        start_idx = match.start()
        line_start = _approx_line_number(content, start_idx)
        line_end = _approx_line_number(content, match.end())
        nearby = _extract_nearby_texts(content, start_idx)

        chunk = ParsedChunk(
            text=visible_text,
            tag=match.group("tag"),
            file=rel_path,
            line_start=line_start,
            line_end=line_end,
            component=component_name,
            class_name=attrs.get("class", attrs.get("classname", "")),
            element_id=attrs.get("id", ""),
            aria_label=aria_label,
            placeholder=placeholder,
            nearby_text=nearby,
            snippet=match.group(0)[:1200],
        )
        chunks.append(chunk.to_dict())

    return chunks


def parse_frontend_files(repo_root: str) -> List[Dict]:
    all_chunks: List[Dict] = []

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            file_path = os.path.join(root, filename)
            all_chunks.extend(parse_file(file_path, repo_root))

    return all_chunks
