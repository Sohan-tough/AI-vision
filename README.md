# Vision Code Navigation System (MVP)

Streamlit app that maps a UI screenshot region back to likely frontend code.

## Features

- Clone a GitHub repo and parse UI-oriented frontend chunks in memory
- OCR selected image region + expanded nearby context
- OCR noise handling with OpenCV preprocessing and confidence filtering
- Multi-stage matching (exact + fuzzy + nearby context)
- Top-3 candidate code matches with confidence
- Groq explanation of best matching snippet

## Setup

1. Create virtual environment and activate:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Configure env:
   - `cp .env.example .env`
   - set `GROQ_API_KEY` in `.env`
4. Ensure system OCR binary exists:
   - Debian/Ubuntu: `sudo apt install tesseract-ocr`

## Run

`streamlit run app.py`

## Notes

- No database; index is in memory for MVP simplicity.
- No vector DB/FAISS.
- For large repos, initial parsing may take time.
