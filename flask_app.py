import io
import os
import base64
import re

from flask import Flask, request, jsonify, render_template, send_from_directory
from PIL import Image
from dotenv import load_dotenv

from llm.groq_explainer import explain_with_groq
from matcher.fuzzy_matcher import match_chunks
from ocr.image_cropper import crop_regions
from ocr.text_extractor import run_ocr_multistage
from parser.component_indexer import (
    build_full_index,
    index_stats,
)
from parser.component_extractor import lookup
from parser.file_parser import parse_frontend_files
from parser.repo_cloner import cleanup_temp_dir, clone_repo
load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Global state (in production, use Redis or database)
app_state = {
    'index': [],
    'lookup_table': {},
    'index_stats': {},
    'repo_root': None,
    'temp_dir': None
}


def is_weak_main_text(text):
    text = (text or "").strip()
    if not text:
        return True
    words = [word for word in text.split() if any(ch.isalpha() for ch in word)]
    if len(text) <= 3:
        return True
    if len(words) <= 1 and len(text) <= 6:
        return True
    return False


def _read_text_file(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        return ""


def _find_first_line(content, patterns):
    lines = content.splitlines()
    for pattern in patterns:
        if not pattern:
            continue
        for idx, line in enumerate(lines, start=1):
            if pattern in line:
                start = max(1, idx - 1)
                end = min(len(lines), idx + 1)
                excerpt = "\n".join(lines[start - 1:end])
                return idx, excerpt
    return None, ""


def _extract_match_tokens(match):
    classes = [value for value in (match.get('class', '') or '').split() if value]
    return {
        'id': (match.get('id', '') or '').strip(),
        'classes': classes,
        'tag': (match.get('tag', '') or '').strip(),
        'text': (match.get('text', '') or '').strip(),
    }


def _make_reference(label, file_path, line, excerpt):
    return {
        'label': label,
        'file': file_path,
        'line': line,
        'code': excerpt.strip(),
    }


def _find_behavior_references(repo_root, match):
    tokens = _extract_match_tokens(match)
    search_terms = []
    if tokens['id']:
        search_terms.extend([f"'{tokens['id']}'", f'"{tokens["id"]}"', tokens['id']])
    if tokens['text']:
        search_terms.extend([tokens['text']])

    results = []
    seen = set()
    script_exts = {'.js', '.jsx', '.ts', '.tsx', '.py'}
    for root, _, files in os.walk(repo_root):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in script_exts:
                continue
            path = os.path.join(root, filename)
            rel_path = os.path.relpath(path, repo_root)
            content = _read_text_file(path)
            if not content:
                continue
            line_no, excerpt = _find_first_line(content, search_terms)
            if not line_no:
                continue
            key = (rel_path, line_no)
            if key in seen:
                continue
            seen.add(key)
            results.append(_make_reference('Behavior', rel_path, line_no, excerpt))
    return results[:3]


def _find_style_references(repo_root, match):
    tokens = _extract_match_tokens(match)
    search_terms = []
    if tokens['id']:
        search_terms.append(f"#{tokens['id']}")
    for class_name in tokens['classes']:
        search_terms.append(f".{class_name}")

    results = []
    seen = set()
    for root, _, files in os.walk(repo_root):
        for filename in files:
            if os.path.splitext(filename)[1].lower() != '.css':
                continue
            path = os.path.join(root, filename)
            rel_path = os.path.relpath(path, repo_root)
            content = _read_text_file(path)
            if not content:
                continue
            line_no, excerpt = _find_first_line(content, search_terms)
            if not line_no:
                continue
            key = (rel_path, line_no)
            if key in seen:
                continue
            seen.add(key)
            results.append(_make_reference('Styling', rel_path, line_no, excerpt))
    return results[:3]


def build_navigation_payload(match, repo_root):
    if not match:
        return {}

    primary_line = match.get('exact_line_start') or match.get('line_start')
    primary = _make_reference(
        'Primary match',
        match.get('file', ''),
        primary_line,
        match.get('matched_excerpt', '') or match.get('element_snippet', '') or match.get('snippet', ''),
    )
    summary = f"Likely {match.get('tag', 'UI element')} rendering '{match.get('text', '')}'." if match.get('text') else ""

    return {
        'primary': primary,
        'behavior': _find_behavior_references(repo_root, match),
        'styling': _find_style_references(repo_root, match),
        'summary': summary,
    }

def base64_to_image(base64_string):
    """Convert base64 string to PIL Image"""
    try:
        # Remove data URL prefix if present
        if ',' in base64_string:
            base64_string = base64_string.split(',')[1]
        
        image_data = base64.b64decode(base64_string)
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        return image
    except Exception as e:
        print(f"Error converting base64 to image: {e}")
        return None


def build_related_files(match, index):
    file_path = (match or {}).get('file', '') or ''
    if not file_path:
        return []

    root_name = os.path.splitext(os.path.basename(file_path))[0].lower()
    if not root_name:
        return []

    related = []
    seen = {file_path}
    priority_exts = {'.css': 0, '.js': 1, '.jsx': 2, '.ts': 3, '.tsx': 4}

    for item in index:
        candidate = item.get('file', '')
        if not candidate or candidate in seen:
            continue

        candidate_name = os.path.splitext(os.path.basename(candidate))[0].lower()
        candidate_ext = os.path.splitext(candidate)[1].lower()
        if candidate_ext not in priority_exts:
            continue

        component_name = (item.get('component', '') or '').lower()
        if candidate_name == root_name or component_name == root_name:
            related.append(candidate)
            seen.add(candidate)

    related.sort(key=lambda path: (priority_exts.get(os.path.splitext(path)[1].lower(), 99), path))
    return related[:5]

@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

@app.route('/api/clone-repo', methods=['POST'])
def clone_repo_api():
    """Clone repository and build index"""
    try:
        data = request.get_json()
        repo_url = data.get('repo_url', '').strip()
        
        if not repo_url:
            return jsonify({'error': 'Repository URL is required'}), 400
        
        # Cleanup previous repo if exists
        if app_state['temp_dir']:
            cleanup_temp_dir(app_state['temp_dir'])
        
        # Reset state
        app_state['index'] = []
        app_state['lookup_table'] = {}
        app_state['index_stats'] = {}
        app_state['repo_root'] = None
        app_state['temp_dir'] = None
        
        # Clone repository
        repo_root, temp_dir = clone_repo(repo_url)
        app_state['repo_root'] = repo_root
        app_state['temp_dir'] = temp_dir
        
        # Parse and build index + lookup table
        parsed = parse_frontend_files(repo_root)
        app_state['index'], app_state['lookup_table'] = \
            build_full_index(parsed)
        app_state['index_stats'] = index_stats(
            app_state['index'],
            app_state['lookup_table'],
        )
        
        if not app_state['index']:
            return jsonify({
                'success': True,
                'message': 'Repository cloned but no parsable UI chunks found',
                'stats': app_state['index_stats']
            })
        
        return jsonify({
            'success': True,
            'message': f"Successfully indexed {app_state['index_stats']['total_chunks']} UI chunks",
            'stats': app_state['index_stats']
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to clone repository: {str(e)}'}), 500

@app.route('/api/clear-repo', methods=['POST'])
def clear_repo_api():
    """Clear repository cache"""
    try:
        if app_state['temp_dir']:
            cleanup_temp_dir(app_state['temp_dir'])
        
        app_state['repo_root'] = None
        app_state['temp_dir'] = None
        app_state['index'] = []
        app_state['lookup_table'] = {}
        app_state['index_stats'] = {}
        
        return jsonify({
            'success': True,
            'message': 'Repository cache cleared'
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to clear cache: {str(e)}'}), 500

@app.route('/api/process-image', methods=['POST'])
def process_image_api():
    """Process image with OCR and matching"""
    try:
        data = request.get_json()
        
        # Debug logging
        print(f"Received process-image request with keys: {list(data.keys()) if data else 'None'}")
        
        # Validate required fields
        required_fields = ['image_data', 'bbox', 'conf_threshold']
        for field in required_fields:
            if field not in data:
                error_msg = f'Missing required field: {field}'
                print(f"Validation error: {error_msg}")
                return jsonify({'error': error_msg}), 400
        
        # Check if index exists and is not from current directory
        if not app_state['index']:
            error_msg = 'Please clone and index a repository first'
            print(f"Index error: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        # Additional safety check: Ensure we have a valid repo_root that's not current directory
        if not app_state['repo_root']:
            error_msg = 'No repository loaded. Please clone a repository first.'
            print(f"Repo error: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        try:
            current_dir = os.getcwd()
            if os.path.samefile(app_state['repo_root'], current_dir):
                error_msg = 'Invalid repository state. Please clone a different repository.'
                print(f"Safety error: {error_msg}")
                return jsonify({'error': error_msg}), 400
        except (OSError, FileNotFoundError):
            # If samefile fails, do a simple path comparison as fallback
            if os.path.abspath(app_state['repo_root']) == os.path.abspath(current_dir):
                error_msg = 'Invalid repository state. Please clone a different repository.'
                print(f"Safety error (fallback): {error_msg}")
                return jsonify({'error': error_msg}), 400
        
        # Convert base64 to image
        image = base64_to_image(data['image_data'])
        if image is None:
            return jsonify({'error': 'Invalid image data'}), 400
        
        bbox = data['bbox']
        conf_threshold = data['conf_threshold']
        
        # Validate bbox
        if not all(key in bbox for key in ['x', 'y', 'width', 'height']):
            return jsonify({'error': 'Invalid bounding box format'}), 400
        
        if bbox['width'] <= 0 or bbox['height'] <= 0:
            return jsonify({'error': 'Invalid bounding box dimensions'}), 400
        
        # Process image
        main_region, nearby_region = crop_regions(image, bbox)
        main_text, main_tokens = run_ocr_multistage(main_region, conf_threshold=conf_threshold)
        nearby_text, nearby_tokens = run_ocr_multistage(nearby_region, conf_threshold=conf_threshold)
        
        # Merge nearby context
        ocr_nearby = []
        seen = set()
        for token in (main_tokens + nearby_tokens):
            key = token.lower()
            if key not in seen:
                ocr_nearby.append(token)
                seen.add(key)
        
        ocr_main = main_text
        if is_weak_main_text(ocr_main) and nearby_text and not is_weak_main_text(nearby_text):
            ocr_main = nearby_text
        elif not ocr_main:
            ocr_main = nearby_text
        
        if not ocr_main:
            return jsonify({
                'success': True,
                'ocr_main': '',
                'ocr_nearby': ocr_nearby,
                'matches': [],
                'message': 'OCR did not find reliable text in selected area'
            })
        
        # Step 1: Try direct lookup first (fast, accurate)
        lookup_results = lookup(
            ocr_main,
            app_state['lookup_table'],
            max_results=5,
        )

        if lookup_results:
            # Lookup found candidates - run through scorer
            # to get proper scores and reasons
            # Use only the top candidates not full index
            matches = match_chunks(
                ocr_main,
                ocr_nearby,
                lookup_results,
                top_k=3,
            )
            # If lookup + scoring returns nothing good,
            # fall back to full index search
            if not matches or matches[0].get('score', 0) < 0.35:
                matches = match_chunks(
                    ocr_main,
                    ocr_nearby,
                    app_state['index'],
                    top_k=3,
                )
        else:
            # Step 2: Lookup found nothing, use full fuzzy search
            matches = match_chunks(
                ocr_main,
                ocr_nearby,
                app_state['index'],
                top_k=3,
            )
        
        navigation = build_navigation_payload(matches[0], app_state['repo_root']) if matches else {}

        # Get explanation for top match only when confidence is reasonable
        explanation = ""
        if matches and matches[0].get('score', 0) >= 0.45:
            try:
                explanation = explain_with_groq(matches[0], {
                    'ocr_text': ocr_main,
                    'ocr_nearby': ocr_nearby,
                })
            except Exception as e:
                explanation = f"Error getting explanation: {str(e)}"
        elif matches:
            explanation = "Top match confidence is still low, so explanation was skipped to avoid overconfident output."

        return jsonify({
            'success': True,
            'ocr_main': ocr_main,
            'ocr_nearby': ocr_nearby,
            'matches': matches,
            'navigation': navigation,
            'explanation': explanation,
            'related_files': build_related_files(matches[0], app_state['index']) if matches else [],
            'message': 'OCR and matching completed successfully' if matches else 'No confident code matches found'
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to process image: {str(e)}'}), 500

@app.route('/api/status', methods=['GET'])
def status_api():
    """Get current application status"""
    return jsonify({
        'index_loaded': len(app_state['index']) > 0,
        'lookup_ready': len(app_state['lookup_table']) > 0,
        'stats': app_state['index_stats'],
        'repo_active': app_state['repo_root'] is not None
    })

if __name__ == '__main__':
    # Create templates and static directories
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
