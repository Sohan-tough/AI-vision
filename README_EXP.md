# 🎓 Vision Code Navigation System - Viva Presentation Guide

**Team Members:** 4-Person Group Presentation  
**Project:** AI-Powered Vision Code Navigation System  
**Technology Stack:** Flask, OpenCV, Tesseract OCR, RapidFuzz, Groq AI

---

## 👤 **Member 1: Image Preprocessing & OCR Pipeline**

### 🖼️ **Image Preprocessing Module Overview**

**Presentation Opening:**
"I'll explain how our system processes mobile screenshots through a sophisticated multi-stage OCR pipeline that handles real-world challenges like poor lighting, rotation, and varying image quality."

### **Stage 1: Image Region Extraction**

#### **Code Location:** `ocr/image_cropper.py`

```python
def crop_regions(image: Image.Image, bbox: dict, expand_ratio: float = 0.25):
    # Extract two strategic regions:
    # 1. Main region - exact user selection
    # 2. Nearby region - 25% expanded context for semantic understanding
    
    main_crop = img_arr[y1:y2, x1:x2]           # Precise selection
    nearby_crop = img_arr[ny1:ny2, nx1:nx2]     # Contextual area
    
    return main_crop, nearby_crop
```

**Key Technical Features:**
- **Dual Region Strategy**: Main selection + contextual information
- **Safe Boundary Checking**: Prevents cropping outside image bounds using `_safe_bbox()`
- **Context Expansion**: 25% expansion captures surrounding UI elements
- **NumPy Integration**: Efficient array operations for image manipulation

### **Stage 2: Multi-Variant Preprocessing Pipeline**

#### **Code Location:** `ocr/text_extractor.py`

```python
def preprocess_variants(img: np.ndarray) -> List[np.ndarray]:
    # Creates 4 optimized versions for different OCR scenarios:
    
    # 1. Original RGB image (baseline)
    original = img
    
    # 2. Deskewed version (rotation corrected)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)  # 2x upscale
    contrast = cv2.convertScaleAbs(gray, alpha=1.4, beta=8)  # Enhance contrast
    blur = cv2.GaussianBlur(contrast, (3, 3), 0)  # Noise reduction
    deskewed = _deskew(blur)  # Auto-rotation correction
    
    # 3. Thresholded version (binary black/white)
    _, thresh = cv2.threshold(deskewed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 4. Sharpened version (edge enhanced)
    sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(deskewed, -1, sharpen_kernel)
    
    return [original, deskewed_rgb, thresh_rgb, sharpened_rgb]
```

**Advanced Preprocessing Techniques:**
1. **2x Upscaling**: Enhances small text recognition using cubic interpolation
2. **Contrast Enhancement**: `alpha=1.4, beta=8` for optimal visibility
3. **Gaussian Blur**: 3x3 kernel for noise reduction
4. **Automatic Deskewing**: Corrects rotation using `cv2.minAreaRect` and affine transformation
5. **OTSU Thresholding**: Adaptive binarization for varying lighting conditions
6. **Edge Sharpening**: Custom convolution kernel for text clarity

### **Stage 3: Multi-Pass OCR Extraction**

```python
def _extract_tokens_and_lines(img: np.ndarray, conf_threshold: float = 0.40):
    # Tesseract Configuration for UI text
    data = pytesseract.image_to_data(
        img, 
        output_type=pytesseract.Output.DICT, 
        config="--oem 3 --psm 6"  # LSTM engine, uniform text block
    )
    
    # Extract tokens with confidence filtering
    for i in range(len(data["text"])):
        confidence = float(data["conf"][i]) / 100.0
        if confidence >= conf_threshold and _valid_token(token):
            tokens.append(clean_token)
```

**OCR Configuration Details:**
- **OEM 3**: LSTM OCR Engine Mode (most accurate for modern text)
- **PSM 6**: Page Segmentation Mode for uniform text blocks (ideal for UI)
- **Confidence Filtering**: Only keeps text above 40% confidence threshold
- **Token Validation**: Filters out numbers, symbols, and short words

### **Stage 4: Intelligent Text Selection**

```python
def _select_best_phrase(candidates: List[Tuple[str, float]]) -> str:
    # Quality scoring algorithm
    def _phrase_quality(text: str, confidence: float) -> float:
        words = text.split()
        word_bonus = min(len(words), 5) * 0.18      # Multi-word bonus
        length_bonus = min(len(text), 48) / 120.0   # Length optimization
        return confidence + word_bonus + length_bonus
    
    # Select highest quality phrase across all variants
    best_key = max(merged_scores, key=merged_scores.get)
    return original_texts[best_key]
```

**Demo Points for Presentation:**
- Show before/after preprocessing images
- Demonstrate how different variants handle various image conditions
- Explain confidence-based filtering results
- Show token validation and cleaning process

---

## 👤 **Member 2: Repository Cloning, Chunking & Parsing**

### 📁 **Repository Processing Pipeline Overview**

**Presentation Opening:**
"I'll demonstrate how our system automatically clones GitHub repositories and intelligently parses frontend code to extract UI-relevant components for semantic matching."

### **Stage 1: Intelligent Repository Cloning**

#### **Code Location:** `parser/repo_cloner.py`

```python
def clone_repo(repo_url: str) -> Tuple[str, str]:
    # Advanced cloning with retry logic and validation
    
    # URL validation
    if not _is_valid_github_url(repo_url):
        raise ValueError("Invalid GitHub repository URL.")
    
    # Temporary directory management
    temp_dir = tempfile.mkdtemp(prefix="vision_nav_repo_")
    repo_dir = os.path.join(temp_dir, "repo")
    
    # Retry mechanism for network resilience
    for attempt in range(3):  # 3 attempts with 2-second delays
        try:
            Repo.clone_from(repo_url, repo_dir, depth=1)  # Shallow clone
            return repo_dir, temp_dir
        except GitCommandError as exc:
            if attempt < 2:
                time.sleep(2)  # Wait before retry
                continue
            raise RuntimeError(f"Failed after 3 attempts: {exc}")
```

**Key Technical Features:**
- **Shallow Cloning**: `depth=1` for efficiency (only latest commit)
- **Retry Mechanism**: 3 attempts with exponential backoff
- **Security Validation**: GitHub URL verification and sanitization
- **Temporary Storage**: Auto-cleanup with `tempfile.mkdtemp()`
- **Network Resilience**: Handles DNS issues and connection timeouts

### **Stage 2: Intelligent File Discovery & Filtering**

#### **Code Location:** `parser/file_parser.py`

```python
# Supported file types for UI component extraction
SUPPORTED_EXTENSIONS = {".html", ".js", ".jsx", ".ts", ".tsx", ".css", ".py"}

# Directory exclusion patterns
IGNORE_DIRS = {".git", "node_modules", "dist", "build", "venv", "__pycache__"}

def parse_frontend_files(repo_root: str) -> List[Dict]:
    # Safety checks to prevent self-parsing
    current_dir = os.getcwd()
    if os.path.samefile(repo_root, current_dir):
        print("Warning: Refusing to parse current working directory")
        return []
    
    # Recursive file discovery with filtering
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]  # In-place filtering
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                chunks.extend(parse_file(file_path, repo_root))
```

**Filtering Strategy:**
- **File Types**: HTML, JS, JSX, TS, TSX, CSS, Python UI frameworks
- **Directory Exclusions**: Build artifacts, dependencies, version control
- **Safety Mechanisms**: Prevents parsing application's own files
- **Performance Optimization**: Early filtering reduces processing overhead

### **Stage 3: Advanced Code Chunking & Pattern Recognition**

```python
# Regex patterns for different UI frameworks
ELEMENT_PATTERN = re.compile(
    r"<(?P<tag>[a-zA-Z][a-zA-Z0-9]*)\s*(?P<attrs>[^>]*)>(?P<body>.*?)</\1>", 
    re.DOTALL
)
FUNC_COMPONENT_PATTERN = re.compile(r"(?:function|const)\s+([A-Z][A-Za-z0-9_]*)")
PYTHON_UI_PATTERN = re.compile(
    r"(st\.|tk\.|wx\.|qt\.)\w+\([^)]*[\"']([^\"']+)[\"'][^)]*\)", 
    re.IGNORECASE
)

def parse_file(file_path: str, repo_root: str) -> List[Dict]:
    # Multi-framework parsing strategy
    
    # HTML/JSX element extraction
    for match in ELEMENT_PATTERN.finditer(content):
        attrs = _extract_attrs(match.group("attrs"))
        body_text = _clean_text(match.group("body"))
        
        # Extract semantic information
        visible_text = body_text or attrs.get("aria-label", "") or attrs.get("placeholder", "")
        if visible_text:
            chunk = create_parsed_chunk(match, attrs, visible_text)
            chunks.append(chunk.to_dict())
    
    # Python UI framework support
    if file_path.endswith('.py'):
        for match in PYTHON_UI_PATTERN.finditer(content):
            ui_text = match.group(2)
            chunk = create_python_ui_chunk(match, ui_text)
            chunks.append(chunk.to_dict())
```

**Chunking Strategy:**
- **HTML Elements**: Tags, attributes, and content extraction
- **React Components**: Functional component identification
- **Python UI**: Streamlit, Tkinter, wxPython, Qt pattern matching
- **Attribute Mining**: Classes, IDs, ARIA labels, placeholders

### **Stage 4: Metadata Enrichment & Context Extraction**

```python
@dataclass
class ParsedChunk:
    text: str              # Visible text content
    tag: str               # HTML tag or component type
    file: str              # Source file path (relative)
    line_start: int        # Starting line number
    line_end: int          # Ending line number
    component: str         # Component/function name
    class_name: str        # CSS classes
    element_id: str        # Element ID
    aria_label: str        # Accessibility label
    placeholder: str       # Input placeholder
    nearby_text: List[str] # Surrounding context (8 items max)
    snippet: str           # Code snippet (1200 chars max)

def _extract_nearby_texts(content: str, element_start: int, window_chars: int = 400):
    # Context window extraction
    start = max(0, element_start - window_chars)
    end = min(len(content), element_start + window_chars)
    snippet = content[start:end]
    
    # Extract and clean nearby text tokens
    raw_texts = re.findall(r">([^<>]{1,120})<", snippet)
    filtered = [_clean_text(t) for t in raw_texts if t and len(t) > 1]
    return filtered[:8]  # Limit to 8 most relevant
```

**Demo Points for Presentation:**
- Show repository structure before/after parsing
- Demonstrate chunk extraction from different file types (React, HTML, Python)
- Explain metadata enrichment process with examples
- Show context window extraction and nearby text identification

---

## 👤 **Member 3: Groq AI Integration & Explanation Generation**

### 🤖 **AI-Powered Code Explanation System Overview**

**Presentation Opening:**
"I'll demonstrate how our system uses Groq's high-speed LLM inference to generate intelligent, contextual explanations of matched code snippets, helping developers understand the connection between UI screenshots and source code."

### **Stage 1: Groq Integration Architecture**

#### **Code Location:** `llm/groq_explainer.py`

```python
def explain_with_groq(match: Dict, query_context: Optional[Dict] = None) -> str:
    # Environment-based API key management
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "Groq explanation skipped: `GROQ_API_KEY` is not set in environment."
    
    # Extract comprehensive match context
    snippet = match.get("matched_excerpt") or match.get("snippet", "")
    component = match.get("component", "Unknown")
    file_path = match.get("file", "Unknown")
    line_start = match.get("line_start", "unknown")
    line_end = match.get("line_end", "unknown")
    tag = match.get("tag", "unknown")
    text = match.get("text", "")
    match_reasons = match.get("match_reasons", [])
    
    # OCR context integration
    ocr_text = query_context.get("ocr_text", "") if query_context else ""
    ocr_nearby = query_context.get("ocr_nearby", []) if query_context else []
```

**Technical Architecture:**
- **Environment Configuration**: Secure API key management
- **Context Aggregation**: Combines match data with OCR results
- **Error Handling**: Graceful fallback when API unavailable
- **Data Extraction**: Comprehensive metadata collection

### **Stage 2: Intelligent Prompt Engineering**

```python
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
```

**Prompt Engineering Strategy:**
- **Structured Context**: Clear separation of OCR data, location, and code details
- **Grounded Analysis**: Instructions to stay within provided evidence
- **Component Identification**: Systematic UI element classification
- **Evidence-Based Reasoning**: Prevents hallucination of unsupported features
- **Match Justification**: Explains the connection between screenshot and code

### **Stage 3: Groq API Configuration & Optimization**

```python
try:
    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",           # Fast, efficient model
        messages=[
            {
                "role": "system", 
                "content": "You are a careful code analyst. Stay grounded in the supplied code and explicitly acknowledge uncertainty when evidence is missing."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,        # Low temperature for consistent, factual responses
        max_tokens=300,         # Concise explanations
    )
    return completion.choices[0].message.content.strip()
except Exception as exc:
    return f"Groq explanation failed: {exc}"
```

**API Configuration Details:**
- **Model Selection**: `llama-3.1-8b-instant` for speed and accuracy balance
- **Temperature**: 0.1 for deterministic, factual responses
- **Token Limit**: 300 tokens for concise explanations
- **System Prompt**: Reinforces grounded analysis approach
- **Error Handling**: Comprehensive exception management

### **Stage 4: Explanation Quality & Integration**

**Example Generated Explanation:**
```
This appears to be a navigation button component. The code shows a <button> element with the class "btn btn-secondary" indicating Bootstrap styling for a secondary button appearance. The button contains the text "Clear Cache" which matches the OCR text from the screenshot. The button includes an ID "clearBtn" for JavaScript event handling, though the specific click handler is not visible in this code snippet. This snippet likely matched the screenshot text because of the exact text match "Clear Cache" and the button tag indicating an interactive UI element.
```

**Quality Assurance Features:**
- **Component Classification**: Identifies UI element type
- **Styling Analysis**: Describes CSS classes and visual appearance
- **Functionality Assessment**: Notes interactive elements and limitations
- **Match Reasoning**: Explains why this code matched the screenshot
- **Evidence Boundaries**: Acknowledges what's not visible in the code

**Demo Points for Presentation:**
- Show live Groq API call with real match data
- Demonstrate different explanation styles for various UI components
- Explain prompt engineering strategy and why it prevents hallucination
- Show how OCR context influences explanation quality

---

## 👤 **Member 4: Advanced Scoring & Fuzzy Matching System**

### 🎯 **Hybrid Scoring Algorithm Overview**

**Presentation Opening:**
"I'll explain our sophisticated hybrid scoring system that combines heuristic algorithms with fuzzy logic to accurately match UI screenshots to source code, handling OCR errors and providing confidence-based ranking."

### **Stage 1: Multi-Factor Heuristic Scoring**

#### **Code Location:** `matcher/scoring.py`

```python
def final_score(
    text_sim: float,           # 35% - Core text similarity
    search_sim: float,         # 20% - Broader context matching  
    nearby_sim: float,         # 15% - Spatial context similarity
    token_overlap: float,      # 10% - Keyword intersection
    tag_sim: float,           # 20% - Semantic element weighting
    exact_match_bonus: float = 0.0,    # +0.22 for perfect matches
    generic_penalty: float = 0.0,     # -0.18 for generic terms
    source_bonus: float = 0.0,        # +0.10 for render files
    support_penalty: float = 0.0,     # -0.12 for logic files
    specificity_bonus: float = 0.0,   # +0.08 for specific elements
    container_penalty: float = 0.0,   # -0.40 for broad containers
) -> float:
    score = (
        0.35 * text_sim +
        0.20 * search_sim +
        0.15 * nearby_sim +
        0.10 * token_overlap +
        0.20 * tag_sim +
        exact_match_bonus +
        source_bonus +
        specificity_bonus -
        generic_penalty -
        support_penalty -
        container_penalty
    )
    return max(0.0, min(score, 1.0))  # Clamp to [0,1] range
```

**Scoring Components Breakdown:**

#### **1. Text Similarity (35% Weight)**
```python
def text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a, b = a.lower().strip(), b.lower().strip()
    
    # Triple similarity approach
    s1 = fuzz.ratio(a, b)           # Overall similarity
    s2 = fuzz.partial_ratio(a, b)   # Substring matching
    s3 = fuzz.token_set_ratio(a, b) # Token-based matching
    
    return max(s1, s2, s3) / 100.0  # Take best result
```

#### **2. Tag Semantic Weighting (20% Weight)**
```python
def tag_similarity(code_tag: str) -> float:
    code_tag = code_tag.lower()
    
    # High-value interactive elements
    if code_tag in {"button", "a", "input", "label", "h1", "h2", "h3"}:
        return 1.0
    
    # Medium-value content elements  
    if code_tag in {"span", "p", "textarea", "option", "python_ui"}:
        return 0.7
    
    # Low-value structural elements
    return 0.35
```

#### **3. Dynamic Bonus System**
```python
def specific_element_bonus(tag: str, line_span: int, text_word_count: int) -> float:
    tag = tag.lower()
    
    # Specific UI elements with small footprint get priority
    if tag in {"button", "a", "label", "option", "h1", "h2", "h3", "h4", "p", "span"} and line_span <= 6:
        return 0.08
    
    if tag in {"input", "textarea"} and line_span <= 4:
        return 0.08
    
    # Compact containers with minimal text
    if tag in {"div", "section"} and line_span <= 4 and text_word_count <= 6:
        return 0.03
    
    return 0.0
```

#### **4. Intelligent Penalty System**
```python
def broad_container_penalty(tag: str, line_span: int, text_word_count: int, exact_match: bool) -> float:
    if exact_match:
        return 0.0  # No penalty for exact matches
    
    tag = tag.lower()
    
    # Heavy penalty for document structure
    if tag in {"html", "body", "head"}:
        return 0.4
    
    # Moderate penalty for large containers
    if tag in {"main", "header", "footer", "section", "article", "div"} and line_span >= 12:
        return 0.18
    
    # Text-based penalties
    if text_word_count >= 20:
        return 0.14
    if text_word_count >= 10 and line_span >= 8:
        return 0.08
    
    return 0.0
```

### **Stage 2: Fuzzy Logic Inference System**

#### **Code Location:** `matcher/fuzzy_inference.py`

```python
def fuzzy_match_confidence(**kwargs) -> Dict[str, object]:
    # Extract similarity metrics
    text = _quality_memberships(text_sim)
    search = _quality_memberships(search_sim)
    nearby = _quality_memberships(nearby_sim)
    overlap = _quality_memberships(token_overlap)
    tag = _quality_memberships(tag_sim)
    penalty = _penalty_memberships(total_penalty)
    
    # Fuzzy rule evaluation
    low_rules = {
        "weak_text_and_search": min(text["low"], search["low"]),
        "high_penalty": penalty["high"],
        "weak_text_with_low_overlap": min(text["low"], overlap["low"]),
    }
    
    high_rules = {
        "high_text_and_tag": min(text["high"], tag["high"]),
        "high_text_and_search": min(text["high"], search["high"]),
        "exact_or_source_backed_match": max(exact["medium"], min(text["medium"], source["high"])),
        "context_supported_visible_match": min(text["medium"], nearby["high"], overlap["medium"]),
    }
    
    # Defuzzification using weighted centroid
    confidence = (
        low_strength * 0.2 +
        medium_strength * 0.55 +
        high_strength * 0.9
    ) / total_strength
    
    return {
        "score": round(confidence, 4),
        "label": best_label.capitalize(),
        "rule_strengths": fired_rules[:5]
    }
```

**Fuzzy Logic Components:**

#### **1. Membership Functions**
```python
def triangular(x: float, a: float, b: float, c: float) -> float:
    # Triangular membership function for medium quality
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if x < b:
        return (x - a) / (b - a)
    return (c - x) / (c - b)

def trapezoidal(x: float, a: float, b: float, c: float, d: float) -> float:
    # Trapezoidal membership function for low/high quality
    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if x < b:
        return (x - a) / (b - a)
    return (d - x) / (d - c)
```

#### **2. Quality Membership Ranges**
- **Low Quality**: trapezoidal(0.0, 0.0, 0.22, 0.45)
- **Medium Quality**: triangular(0.25, 0.52, 0.78)
- **High Quality**: trapezoidal(0.58, 0.78, 1.0, 1.0)

### **Stage 3: Hybrid Score Integration**

#### **Code Location:** `matcher/fuzzy_matcher.py`

```python
def match_chunks(ocr_text: str, ocr_nearby: List[str], index: List[Dict], top_k: int = 3):
    for chunk in index:
        # Calculate all similarity metrics
        text_sim = text_similarity(ocr_text, chunk_text)
        search_sim = text_similarity(ocr_text, search_text)
        nearby_sim = nearby_similarity(ocr_nearby, chunk.get("nearby_text", []))
        overlap_sim = token_overlap_score(ocr_text, search_text)
        tag_sim = tag_similarity(chunk.get("tag", ""))
        
        # Apply bonuses and penalties
        exact_match_bonus = 0.22 if exact_match else 0.0
        source_bonus = render_source_bonus(chunk.get("file", ""), chunk.get("tag", ""), text_sim)
        specificity_bonus = specific_element_bonus(chunk.get("tag", ""), line_span, text_word_count)
        container_penalty = broad_container_penalty(chunk.get("tag", ""), line_span, text_word_count, exact_match)
        
        # Calculate heuristic score
        heuristic_score = final_score(
            text_sim, search_sim, nearby_sim, overlap_sim, tag_sim,
            exact_match_bonus, generic_penalty, source_bonus, 
            support_penalty, specificity_bonus, container_penalty
        )
        
        # Calculate fuzzy inference score
        fuzzy_result = fuzzy_match_confidence(
            text_sim=text_sim, search_sim=search_sim, nearby_sim=nearby_sim,
            token_overlap=overlap_sim, tag_sim=tag_sim, exact_match_bonus=exact_match_bonus,
            generic_penalty=generic_penalty, support_penalty=support_penalty,
            container_penalty=container_penalty, specificity_bonus=specificity_bonus,
            source_bonus=source_bonus
        )
        
        # Hybrid combination: 75% heuristic + 25% fuzzy
        final_score = (0.75 * heuristic_score) + (0.25 * fuzzy_result["score"])
        
        # Convert to percentage for display
        score_percentage = round(final_score * 100, 2)
```

### **Stage 4: Result Ranking & Quality Assurance**

```python
# Multi-criteria sorting for optimal results
results.sort(
    key=lambda x: (
        x["score"],                           # Primary: Final confidence score
        x.get("element_text_similarity", 0), # Secondary: Element-specific match
        x["text_similarity"],                 # Tertiary: General text similarity
        x.get("evidence_count", 0),          # Quaternary: Multiple evidence sources
    ),
    reverse=True
)

# Return top-k results with comprehensive metadata
return results[:top_k]
```

**Demo Points for Presentation:**
- Show live scoring calculation with real OCR input
- Demonstrate how different similarity metrics contribute to final score
- Explain fuzzy rule firing with concrete examples
- Show how bonuses and penalties affect ranking
- Compare results with and without fuzzy logic enhancement

---

## 🎯 **Presentation Tips & Demo Flow**

### **Recommended Demo Sequence:**
1. **Member 1**: Show image preprocessing pipeline with before/after examples
2. **Member 2**: Demonstrate repository cloning and parsing with live GitHub repo
3. **Member 4**: Explain scoring system with step-by-step calculation
4. **Member 3**: Show AI explanation generation with live Groq API call

### **Technical Questions to Prepare For:**
- Why use 4 preprocessing variants instead of just one?
- How does the system handle different programming languages?
- What makes the fuzzy logic approach better than simple string matching?
- How does the AI explanation prevent hallucination?
- What happens when OCR confidence is very low?
- How does the system scale to large repositories?

### **Key Metrics to Highlight:**
- **Processing Speed**: Multi-stage pipeline optimized for real-time use
- **Accuracy**: Hybrid scoring achieves high precision in matching
- **Robustness**: Handles various image qualities and OCR errors
- **Scalability**: Efficient indexing supports large codebases
- **User Experience**: Mobile-optimized touch interface

**Good luck with your viva presentation! 🎓✨**