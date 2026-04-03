# 🔍 Vision Code Navigation System

A powerful web application that bridges the gap between UI screenshots and source code. Simply upload a screenshot, draw a selection box around any UI element, and instantly find the corresponding code in your repository with AI-powered explanations.

## ✨ Features

### 🎯 **Core Functionality**
- **Repository Integration**: Clone and index GitHub repositories automatically
- **Smart OCR Processing**: Extract text from UI screenshots with confidence-based filtering
- **Intelligent Code Matching**: Multi-stage fuzzy matching algorithm finds relevant code snippets
- **AI-Powered Explanations**: Get detailed explanations of matched code using Groq AI
- **Real-time Results**: View top 3 candidate matches with confidence scores

### 📱 **Mobile-First Design**
- **Touch-Friendly Interface**: Native touch and drag selection for mobile devices
- **Responsive Layout**: Optimized for all screen sizes from mobile to desktop
- **Camera Integration**: Capture screenshots directly from your mobile device
- **Intuitive Controls**: Large buttons and touch-optimized interactions

### 🛠️ **Technical Highlights**
- **Flask Backend**: RESTful API architecture for scalability
- **Advanced OCR**: Multi-stage text extraction with OpenCV preprocessing
- **Fuzzy Matching**: Sophisticated algorithm combining exact, fuzzy, and contextual matching
- **Real-time Processing**: Efficient in-memory indexing for fast results

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Tesseract OCR engine
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Sohan-tough/AI-vision.git
   cd AI-vision
   ```

2. **Set up virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Tesseract OCR**
   ```bash
   # Ubuntu/Debian
   sudo apt install tesseract-ocr
   
   # macOS
   brew install tesseract
   
   # Windows
   # Download from: https://github.com/UB-Mannheim/tesseract/wiki
   ```

5. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and set your GROQ_API_KEY
   ```

### Running the Application

```bash
python flask_app.py
```

The application will be available at `http://localhost:5000`

## 📖 How to Use

### 1. **Repository Setup**
- Enter a GitHub repository URL
- Click "Clone + Build Index" to analyze the codebase
- Wait for the indexing process to complete

### 2. **Image Processing**
- Upload a screenshot or capture one using your device camera
- Use touch and drag to select the UI element you want to analyze
- Adjust OCR confidence threshold if needed (default: 0.40)

### 3. **Get Results**
- Click "Run OCR + Match" to process your selection
- View extracted text and nearby context tokens
- Explore top 3 code matches with confidence scores
- Read AI-generated explanations for the best match

## 🏗️ Architecture

### Backend Components
- **Flask API**: RESTful endpoints for all operations
- **Repository Parser**: Analyzes frontend files and extracts UI components
- **OCR Engine**: Multi-stage text extraction with confidence filtering
- **Matching Algorithm**: Sophisticated fuzzy matching with contextual awareness
- **AI Integration**: Groq API for intelligent code explanations

### Frontend Components
- **Responsive HTML**: Mobile-first design with semantic markup
- **Modern CSS**: Flexbox/Grid layouts with smooth animations
- **Vanilla JavaScript**: Touch event handling and API communication
- **Progressive Enhancement**: Works on all devices and browsers

## 🔧 Configuration

### Environment Variables
```bash
GROQ_API_KEY=your_groq_api_key_here
```

### OCR Settings
- **Confidence Threshold**: Adjustable from 0.1 to 0.95 (default: 0.40)
- **Preprocessing**: Automatic noise reduction and image enhancement
- **Multi-stage Processing**: Fallback mechanisms for better text extraction

## 📁 Project Structure

```
├── flask_app.py              # Main Flask application
├── templates/
│   └── index.html            # Frontend HTML template
├── static/
│   ├── style.css            # Responsive CSS styles
│   └── script.js            # JavaScript for interactions
├── llm/
│   └── groq_explainer.py    # AI explanation service
├── matcher/
│   ├── fuzzy_matcher.py     # Core matching algorithm
│   └── scoring.py           # Confidence scoring
├── ocr/
│   ├── text_extractor.py    # OCR processing
│   └── image_cropper.py     # Image region extraction
├── parser/
│   ├── repo_cloner.py       # GitHub repository handling
│   ├── file_parser.py       # Code parsing and indexing
│   └── component_indexer.py # UI component extraction
└── utils/
    └── helpers.py           # Utility functions
```

## 🌐 API Endpoints

- `GET /` - Serve the main application
- `POST /api/clone-repo` - Clone and index a repository
- `POST /api/clear-repo` - Clear repository cache
- `POST /api/process-image` - Process image with OCR and matching
- `GET /api/status` - Get application status

## 🔒 Security & Privacy

- **No Data Storage**: All processing happens in memory
- **Temporary Files**: Automatically cleaned up after processing
- **API Rate Limiting**: Built-in protection against abuse
- **Input Validation**: Comprehensive validation for all inputs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Tesseract OCR** for text extraction capabilities
- **OpenCV** for image processing
- **Groq** for AI-powered explanations
- **Flask** for the robust web framework

## 📞 Support

If you encounter any issues or have questions:
- Open an issue on GitHub
- Check the documentation
- Review the troubleshooting guide

---

**Made with ❤️ for developers who want to bridge the gap between UI and code**
