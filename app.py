import io
import os
from typing import Optional

import numpy as np
import streamlit as st
from PIL import Image
from dotenv import load_dotenv
from streamlit_drawable_canvas import st_canvas

from llm.groq_explainer import explain_with_groq
from matcher.fuzzy_matcher import match_chunks
from ocr.image_cropper import crop_regions
from ocr.text_extractor import run_ocr_multistage
from parser.component_indexer import build_index, index_stats
from parser.file_parser import parse_frontend_files
from parser.repo_cloner import cleanup_temp_dir, clone_repo
from utils.helpers import ensure_session_defaults, format_match_title, pretty_nearby, tesseract_check_hint


load_dotenv()
st.set_page_config(page_title="Vision Code Navigation MVP", layout="wide")
ensure_session_defaults(st.session_state)


def _reset_repo_state():
    st.session_state.index = []
    st.session_state.index_stats = {}
    st.session_state.matches = []
    st.session_state.ocr_main = ""
    st.session_state.ocr_nearby = []


def _load_image_from_input(uploaded_file, camera_file) -> Optional[Image.Image]:
    file_obj = uploaded_file or camera_file
    if not file_obj:
        return None
    data = file_obj.read()
    if not data:
        return None
    return Image.open(io.BytesIO(data)).convert("RGB")


st.title("Vision Code Navigation System (MVP)")
st.caption("Clone repo -> parse UI text -> select image region -> OCR -> fuzzy match -> Groq explanation")

with st.sidebar:
    st.header("1) Repository")
    repo_url = st.text_input("GitHub repository URL", placeholder="https://github.com/user/project")

    col_a, col_b = st.columns(2)
    with col_a:
        build_index_btn = st.button("Clone + Build Index", use_container_width=True, type="primary")
    with col_b:
        clear_repo_btn = st.button("Clear Repo Cache", use_container_width=True)

    if clear_repo_btn:
        if st.session_state.temp_dir:
            cleanup_temp_dir(st.session_state.temp_dir)
        st.session_state.repo_root = None
        st.session_state.temp_dir = None
        _reset_repo_state()
        st.success("Cleared cloned repo and in-memory index.")

    if build_index_btn:
        if not repo_url.strip():
            st.error("Please provide a valid GitHub URL.")
        else:
            try:
                if st.session_state.temp_dir:
                    cleanup_temp_dir(st.session_state.temp_dir)
                _reset_repo_state()

                with st.spinner("Cloning repository..."):
                    repo_root, temp_dir = clone_repo(repo_url.strip())
                st.session_state.repo_root = repo_root
                st.session_state.temp_dir = temp_dir

                with st.spinner("Parsing frontend files..."):
                    parsed = parse_frontend_files(repo_root)
                st.session_state.index = build_index(parsed)
                st.session_state.index_stats = index_stats(st.session_state.index)

                if not st.session_state.index:
                    st.warning("No parsable UI chunks found in the repository.")
                else:
                    st.success(f"Indexed {st.session_state.index_stats['total_chunks']} UI chunks.")
            except Exception as exc:
                st.error(f"Repo indexing failed: {exc}")

    st.divider()
    st.header("2) OCR Settings")
    conf_threshold = st.slider("OCR confidence threshold", min_value=0.10, max_value=0.95, value=0.40, step=0.05)
    st.caption(tesseract_check_hint())

left, right = st.columns([1.1, 1], gap="large")

with left:
    st.subheader("Image Input + Bounding Box")
    uploaded_file = st.file_uploader("Upload screenshot/photo", type=["png", "jpg", "jpeg", "webp", "bmp"])
    camera_file = st.camera_input("Or capture from camera")
    image = _load_image_from_input(uploaded_file, camera_file)

    bbox = None
    if image:
        img_w, img_h = image.size
        st.write("Draw a rectangle around the target UI element.")
        canvas_result = st_canvas(
            fill_color="rgba(255, 0, 0, 0.15)",
            stroke_width=2,
            stroke_color="#FF0000",
            background_image=image,
            update_streamlit=True,
            drawing_mode="rect",
            width=img_w,
            height=img_h,
            key="roi_canvas",
        )

        if canvas_result and canvas_result.json_data and canvas_result.json_data.get("objects"):
            rect = canvas_result.json_data["objects"][-1]
            bbox = {
                "x": int(rect.get("left", 0)),
                "y": int(rect.get("top", 0)),
                "width": int(rect.get("width", 1) * rect.get("scaleX", 1)),
                "height": int(rect.get("height", 1) * rect.get("scaleY", 1)),
            }
            st.info(f"Selected box: x={bbox['x']} y={bbox['y']} w={bbox['width']} h={bbox['height']}")

    run_btn = st.button("Run OCR + Match", use_container_width=True, type="primary")
    if run_btn:
        if not st.session_state.index:
            st.error("Please clone and index a repository first.")
        elif image is None:
            st.error("Please upload or capture an image.")
        elif bbox is None:
            st.error("Please draw a bounding box first.")
        else:
            try:
                main_region, nearby_region = crop_regions(image, bbox)
                main_text, main_tokens = run_ocr_multistage(main_region, conf_threshold=conf_threshold)
                nearby_text, nearby_tokens = run_ocr_multistage(nearby_region, conf_threshold=conf_threshold)

                # Nearby context is merged token-level context from both OCR regions.
                ocr_nearby = []
                seen = set()
                for token in (main_tokens + nearby_tokens):
                    key = token.lower()
                    if key not in seen:
                        ocr_nearby.append(token)
                        seen.add(key)

                st.session_state.ocr_main = main_text or nearby_text
                st.session_state.ocr_nearby = ocr_nearby
                st.session_state.matches = match_chunks(st.session_state.ocr_main, st.session_state.ocr_nearby, st.session_state.index, top_k=3)

                if not st.session_state.ocr_main:
                    st.warning("OCR did not find reliable text in selected area.")
                elif not st.session_state.matches:
                    st.warning("No confident code matches were found.")
                else:
                    st.success("OCR and matching completed.")
            except Exception as exc:
                st.error(f"OCR or matching failed: {exc}")

with right:
    st.subheader("Match Results")
    if st.session_state.ocr_main:
        st.markdown(f"**OCR Main Text:** `{st.session_state.ocr_main}`")
    if st.session_state.ocr_nearby:
        st.markdown(f"**OCR Nearby Tokens:** {pretty_nearby(st.session_state.ocr_nearby, limit=16)}")

    matches = st.session_state.matches
    if matches:
        for i, match in enumerate(matches, start=1):
            with st.expander(format_match_title(match, i), expanded=(i == 1)):
                st.markdown(f"**Confidence:** {match.get('score_pct', 0)}%")
                st.markdown(f"**File:** `{match.get('file', 'N/A')}`")
                st.markdown(f"**Component:** `{match.get('component', 'N/A')}`")
                st.markdown(f"**Lines:** {match.get('line_start', '?')}-{match.get('line_end', '?')}")
                st.markdown(f"**Tag:** `{match.get('tag', '')}`")
                st.markdown(f"**Nearby match hint:** {pretty_nearby(match.get('nearby_text', []))}")
                st.code(match.get("snippet", ""), language="tsx")

                if i == 1:
                    with st.spinner("Asking Groq for explanation..."):
                        explanation = explain_with_groq(match)
                    st.markdown("**Groq Explanation**")
                    st.write(explanation)
    else:
        st.info("No match results yet. Build index, draw a box, then run OCR + match.")

st.divider()
stats = st.session_state.index_stats or {}
if stats:
    c1, c2, c3 = st.columns(3)
    c1.metric("Indexed Chunks", stats.get("total_chunks", 0))
    c2.metric("Parsed Files", stats.get("total_files", 0))
    c3.metric("Components", stats.get("total_components", 0))

if st.session_state.repo_root:
    st.caption(f"Active cloned repo path: {st.session_state.repo_root}")
