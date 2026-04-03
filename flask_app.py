import io
import os
import base64
from typing import Optional

from flask import Flask, request, jsonify, render_template, send_from_directory
from PIL import Image
from dotenv import load_dotenv
import tempfile
import uuid

from llm.groq_explainer import explain_with_groq
from matcher.fuzzy_matcher import match_chunks
from ocr.image_cropper import crop_regions
from ocr.text_extractor import run_ocr_multistage
from parser.component_indexer import build_index, index_stats
from parser.file_parser import parse_frontend_files
from parser.repo_cloner import cleanup_temp_dir, clone_repo
from utils.helpers import format_match_title, pretty_nearby

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Global state (in production, use Redis or database)
app_state = {
    'index': [],
    'index_stats': {},
    'repo_root': None,
    'temp_dir': None
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
        app_state['index_stats'] = {}
        app_state['repo_root'] = None
        app_state['temp_dir'] = None
        
        # Clone repository
        repo_root, temp_dir = clone_repo(repo_url)
        app_state['repo_root'] = repo_root
        app_state['temp_dir'] = temp_dir
        
        # Parse and build index
        parsed = parse_frontend_files(repo_root)
        app_state['index'] = build_index(parsed)
        app_state['index_stats'] = index_stats(app_state['index'])
        
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
        
        # Validate required fields
        required_fields = ['image_data', 'bbox', 'conf_threshold']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Check if index exists
        if not app_state['index']:
            return jsonify({'error': 'Please clone and index a repository first'}), 400
        
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
        
        ocr_main = main_text or nearby_text
        
        if not ocr_main:
            return jsonify({
                'success': True,
                'ocr_main': '',
                'ocr_nearby': ocr_nearby,
                'matches': [],
                'message': 'OCR did not find reliable text in selected area'
            })
        
        # Find matches
        matches = match_chunks(ocr_main, ocr_nearby, app_state['index'], top_k=3)
        
        # Get explanation for top match
        explanation = ""
        if matches:
            try:
                explanation = explain_with_groq(matches[0])
            except Exception as e:
                explanation = f"Error getting explanation: {str(e)}"
        
        return jsonify({
            'success': True,
            'ocr_main': ocr_main,
            'ocr_nearby': ocr_nearby,
            'matches': matches,
            'explanation': explanation,
            'message': 'OCR and matching completed successfully' if matches else 'No confident code matches found'
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to process image: {str(e)}'}), 500

@app.route('/api/status', methods=['GET'])
def status_api():
    """Get current application status"""
    return jsonify({
        'index_loaded': len(app_state['index']) > 0,
        'stats': app_state['index_stats'],
        'repo_active': app_state['repo_root'] is not None
    })

if __name__ == '__main__':
    # Create templates and static directories
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    app.run(host='0.0.0.0', port=5000, debug=True)