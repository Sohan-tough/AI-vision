import os
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Dict, List

from parser.repo_cloner import should_skip_dir


SUPPORTED_EXTENSIONS = {".html", ".js", ".jsx", ".ts", ".tsx", ".css", ".py"}
ELEMENT_PATTERN = re.compile(r"<(?P<tag>[a-zA-Z][a-zA-Z0-9]*)\s*(?P<attrs>[^>]*)>(?P<body>.*?)</\1>", re.DOTALL)
ATTR_PATTERN = re.compile(r'([a-zA-Z_:][a-zA-Z0-9_:.-]*)\s*=\s*["\']([^"\']+)["\']')
FUNC_COMPONENT_PATTERN = re.compile(r"(?:function|const)\s+([A-Z][A-Za-z0-9_]*)")
PYTHON_UI_PATTERN = re.compile(r"(st\.|tk\.|wx\.|qt\.)\w+\([^)]*[\"']([^\"']+)[\"'][^)]*\)", re.IGNORECASE)
NESTED_ELEMENT_PATTERN = re.compile(r"<([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>.*?</\1>", re.DOTALL)
VOID_HTML_TAGS = {"input", "img", "br", "hr", "meta", "link"}
HTML_TEXT_TAGS = {
    "a", "button", "h1", "h2", "h3", "h4", "h5", "h6",
    "label", "li", "option", "p", "span", "title",
    "div", "section", "article", "header", "nav", "main",
    "footer", "textarea",
}


@dataclass
class ParsedChunk:
    text: str
    tag: str
    file: str
    line_start: int
    line_end: int
    exact_line_start: int
    exact_line_end: int
    component: str
    class_name: str
    element_id: str
    aria_label: str
    placeholder: str
    nearby_text: List[str]
    search_text: str
    element_search_text: str
    element_snippet: str
    snippet: str

    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "tag": self.tag,
            "file": self.file,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "exact_line_start": self.exact_line_start,
            "exact_line_end": self.exact_line_end,
            "component": self.component,
            "class": self.class_name,
            "id": self.element_id,
            "aria_label": self.aria_label,
            "placeholder": self.placeholder,
            "nearby_text": self.nearby_text,
            "search_text": self.search_text,
            "element_search_text": self.element_search_text,
            "element_snippet": self.element_snippet,
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


def _extract_direct_text(body: str) -> str:
    if not body:
        return ""

    direct = body
    previous = None
    while previous != direct:
        previous = direct
        direct = NESTED_ELEMENT_PATTERN.sub(" ", direct)

    return _clean_text(direct)


def _make_context_snippet(content: str, start_idx: int, end_idx: int, radius: int = 700) -> str:
    left = max(0, start_idx - radius)
    right = min(len(content), end_idx + radius)
    return content[left:right].strip()[:2200]


def _build_search_text(
    visible_text: str,
    component_name: str,
    attrs: Dict[str, str],
    nearby: List[str],
    rel_path: str,
) -> str:
    parts = [
        visible_text,
        component_name,
        attrs.get("class", attrs.get("classname", "")),
        attrs.get("id", ""),
        attrs.get("aria-label", ""),
        attrs.get("placeholder", ""),
        " ".join(nearby),
        rel_path,
    ]
    return _clean_text(" ".join(part for part in parts if part))


def _locate_exact_lines(raw_snippet: str, line_start: int, candidates: List[str], fallback_end: int) -> tuple[int, int]:
    for candidate in candidates:
        if not candidate:
            continue
        idx = raw_snippet.find(candidate)
        if idx >= 0:
            local_line_start = raw_snippet[:idx].count("\n")
            local_line_end = local_line_start + candidate.count("\n")
            return line_start + local_line_start, line_start + local_line_end
    return line_start, fallback_end


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


def _line_offsets(content: str) -> List[int]:
    offsets = [0]
    for idx, char in enumerate(content):
        if char == "\n":
            offsets.append(idx + 1)
    return offsets


def _line_col_to_index(line_offsets: List[int], line: int, col: int, content_len: int) -> int:
    if not line_offsets:
        return 0
    line = max(1, min(line, len(line_offsets)))
    base = line_offsets[line - 1]
    return min(base + max(col, 0), content_len)


class _HTMLChunkParser(HTMLParser):
    def __init__(self, content: str, rel_path: str, component_name: str):
        super().__init__(convert_charrefs=True)
        self.content = content
        self.rel_path = rel_path
        self.component_name = component_name
        self.chunks: List[Dict] = []
        self.stack: List[Dict] = []
        self.line_offsets = _line_offsets(content)

    def handle_starttag(self, tag: str, attrs) -> None:
        attr_map = {key.lower(): (value or "").strip() for key, value in attrs}
        line, col = self.getpos()
        start_idx = _line_col_to_index(
            self.line_offsets,
            line,
            col,
            len(self.content),
        )
        node = {
            "tag": tag.lower(),
            "attrs": attr_map,
            "start_idx": start_idx,
            "line_start": line,
            "direct_parts": [],
        }
        self.stack.append(node)

        if node["tag"] in VOID_HTML_TAGS:
            self._emit_chunk(node, start_idx)
            self.stack.pop()

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        if self.stack:
            self.stack[-1]["direct_parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for idx in range(len(self.stack) - 1, -1, -1):
            if self.stack[idx]["tag"] != tag:
                continue

            node = self.stack.pop(idx)
            line, col = self.getpos()
            end_idx = _line_col_to_index(
                self.line_offsets,
                line,
                col,
                len(self.content),
            )
            close_end = self.content.find(">", end_idx)
            if close_end == -1:
                close_end = end_idx
            else:
                close_end += 1
            self._emit_chunk(node, close_end)
            break

    def _emit_chunk(self, node: Dict, end_idx: int) -> None:
        tag = node["tag"]
        attrs = node["attrs"]
        raw_snippet = self.content[node["start_idx"]:max(end_idx, node["start_idx"])]
        visible_text = _clean_text(" ".join(node["direct_parts"]))
        aria_label = attrs.get("aria-label", "")
        placeholder = attrs.get("placeholder", "")
        value = attrs.get("value", "")
        visible_text = visible_text or aria_label or placeholder or value

        if not visible_text:
            return

        if tag not in HTML_TEXT_TAGS and tag not in VOID_HTML_TAGS:
            return

        line_end = _approx_line_number(self.content, max(end_idx - 1, node["start_idx"]))
        exact_line_start, exact_line_end = _locate_exact_lines(
            raw_snippet,
            node["line_start"],
            [visible_text, aria_label, placeholder, value],
            line_end,
        )
        nearby = _extract_nearby_texts(self.content, node["start_idx"])
        context_snippet = _make_context_snippet(
            self.content,
            node["start_idx"],
            end_idx,
        )
        search_text = _build_search_text(
            visible_text,
            self.component_name,
            attrs,
            nearby,
            self.rel_path,
        )
        element_search_text = _clean_text(
            " ".join(
                filter(
                    None,
                    [
                        visible_text,
                        attrs.get("id", ""),
                        attrs.get("class", attrs.get("classname", "")),
                        aria_label,
                        placeholder,
                        value,
                        tag,
                    ],
                )
            )
        )

        chunk = ParsedChunk(
            text=visible_text,
            tag=tag,
            file=self.rel_path,
            line_start=node["line_start"],
            line_end=line_end,
            exact_line_start=exact_line_start,
            exact_line_end=exact_line_end,
            component=self.component_name,
            class_name=attrs.get("class", attrs.get("classname", "")),
            element_id=attrs.get("id", ""),
            aria_label=aria_label,
            placeholder=placeholder,
            nearby_text=nearby,
            search_text=search_text,
            element_search_text=element_search_text,
            element_snippet=raw_snippet[:800],
            snippet=context_snippet,
        )
        self.chunks.append(chunk.to_dict())


def _parse_markup_file(content: str, rel_path: str, component_name: str) -> List[Dict]:
    parser = _HTMLChunkParser(content, rel_path, component_name)
    parser.feed(content)
    parser.close()
    return parser.chunks


def parse_file(file_path: str, repo_root: str) -> List[Dict]:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return []

    rel_path = os.path.relpath(file_path, repo_root)
    component_name = _extract_component_name(content, os.path.splitext(os.path.basename(file_path))[0])
    chunks: List[Dict] = []
    ext = os.path.splitext(file_path)[1].lower()

    if ext in {".html", ".htm"}:
        chunks.extend(_parse_markup_file(content, rel_path, component_name))
    else:
        for match in ELEMENT_PATTERN.finditer(content):
            raw_snippet = match.group(0)
            attrs = _extract_attrs(match.group("attrs"))
            raw_body = match.group("body")
            direct_text = _extract_direct_text(raw_body)
            body_text = _clean_text(raw_body)
            aria_label = attrs.get("aria-label", "")
            placeholder = attrs.get("placeholder", "")
            value = attrs.get("value", "")

            visible_text = direct_text or aria_label or placeholder or value
            if not visible_text:
                continue

            start_idx = match.start()
            line_start = _approx_line_number(content, start_idx)
            line_end = _approx_line_number(content, match.end())
            exact_line_start, exact_line_end = _locate_exact_lines(
                raw_snippet,
                line_start,
                [direct_text, aria_label, placeholder, value, body_text],
                line_end,
            )
            nearby = _extract_nearby_texts(content, start_idx)
            context_snippet = _make_context_snippet(content, start_idx, match.end())
            search_text = _build_search_text(" ".join(filter(None, [visible_text, body_text])), component_name, attrs, nearby, rel_path)
            element_search_text = _clean_text(
                " ".join(
                    filter(
                        None,
                        [
                            visible_text,
                            attrs.get("id", ""),
                            attrs.get("class", attrs.get("classname", "")),
                            aria_label,
                            placeholder,
                            value,
                            match.group("tag"),
                        ],
                    )
                )
            )

            chunk = ParsedChunk(
                text=visible_text,
                tag=match.group("tag"),
                file=rel_path,
                line_start=line_start,
                line_end=line_end,
                exact_line_start=exact_line_start,
                exact_line_end=exact_line_end,
                component=component_name,
                class_name=attrs.get("class", attrs.get("classname", "")),
                element_id=attrs.get("id", ""),
                aria_label=aria_label,
                placeholder=placeholder,
                nearby_text=nearby,
                search_text=search_text,
                element_search_text=element_search_text,
                element_snippet=raw_snippet[:800],
                snippet=context_snippet,
            )
            chunks.append(chunk.to_dict())

    # Parse Python UI elements
    if ext == ".py":
        for match in PYTHON_UI_PATTERN.finditer(content):
            raw_snippet = match.group(0)
            ui_text = match.group(2)
            if not ui_text:
                continue

            start_idx = match.start()
            line_start = _approx_line_number(content, start_idx)
            line_end = _approx_line_number(content, match.end())
            exact_line_start, exact_line_end = _locate_exact_lines(
                raw_snippet,
                line_start,
                [ui_text],
                line_end,
            )
            nearby = _extract_nearby_texts(content, start_idx)
            context_snippet = _make_context_snippet(content, start_idx, match.end())
            search_text = _clean_text(" ".join([ui_text, component_name, " ".join(nearby), rel_path]))
            element_search_text = _clean_text(" ".join([ui_text, "python_ui"]))

            chunk = ParsedChunk(
                text=ui_text,
                tag="python_ui",
                file=rel_path,
                line_start=line_start,
                line_end=line_end,
                exact_line_start=exact_line_start,
                exact_line_end=exact_line_end,
                component=component_name,
                class_name="",
                element_id="",
                aria_label="",
                placeholder="",
                nearby_text=nearby,
                search_text=search_text,
                element_search_text=element_search_text,
                element_snippet=match.group(0)[:800],
                snippet=context_snippet,
            )
            chunks.append(chunk.to_dict())

    return chunks


def parse_frontend_files(repo_root: str) -> List[Dict]:
    all_chunks: List[Dict] = []
    
    # Safety check: Only prevent parsing if repo_root is exactly the current working directory
    current_dir = os.getcwd()
    try:
        if os.path.samefile(repo_root, current_dir):
            print(f"Warning: Refusing to parse current working directory: {repo_root}")
            return []
    except (OSError, FileNotFoundError):
        # If samefile fails, do a simple path comparison as fallback
        if os.path.abspath(repo_root) == os.path.abspath(current_dir):
            print(f"Warning: Refusing to parse current working directory: {repo_root}")
            return []

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            file_path = os.path.join(root, filename)
            all_chunks.extend(parse_file(file_path, repo_root))

    return all_chunks
