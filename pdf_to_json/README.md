# NEXUS — PDF to Structured JSON Converter

Converts academic PDF documents into structured JSON with metadata. Two modes available:

| Script | Method | Requires API Key? |
|---|---|---|
| `main.py` | **Local only** — `pymupdf4llm` with heuristic metadata extraction | No |
| `main_llm.py` | **LLM-powered** — `pymupdf4llm` + OpenRouter Elephant model | Yes |

## Output Schema

```json
{
  "document_id": "locally generated UUID",
  "title": "string",
  "category": "syllabus | circular | academic_calendar | hostel_rules",
  "target_audience": "string (e.g. students, faculty, general)",
  "date_issued": "YYYY-MM-DD",
  "content_markdown": "markdown formatted version of the document"
}
```

---

## Prerequisites

- Python 3.10+
- *(LLM mode only)* An [OpenRouter](https://openrouter.ai) API key
- *(Optional)* Tesseract OCR installed on your system for scanned PDFs (e.g., `sudo dnf install tesseract` on Fedora, `sudo apt install tesseract-ocr` on Ubuntu)

---

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd NEXUS
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables *(LLM mode only)*

Create a `.env` file in the project root:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

> **Note:** The `.env` file is git-ignored to protect your API key. This is only needed for `main_llm.py`.

---

## Usage

### Local mode (no LLM)

```bash
source venv/bin/activate
python main.py path/to/document.pdf
```

Extracts the PDF to markdown using `pymupdf4llm` and detects metadata (title, category, date, audience) heuristically via keyword matching.

### LLM mode (OpenRouter Elephant)

```bash
source venv/bin/activate
python main_llm.py path/to/document.pdf
```

Extracts the PDF to markdown using `pymupdf4llm`, then sends it to the `openrouter/elephant-alpha` model for intelligent metadata extraction.

### Save prompt

Both scripts will prompt you for where to save the output JSON:

```
Save JSON to [/current/dir/document.json]:
```

- **Press Enter** to save with the default path (CWD, same name as the PDF with `.json` extension)
- **Type a custom path** to save elsewhere

### Example

```bash
$ python main_llm.py placement_data_mtech.pdf
📄 Extracting markdown from placement_data_mtech.pdf…
  ✔ Extracted 6223 chars of markdown
🤖 Sending to openrouter/elephant-alpha for metadata extraction…
  Calling openrouter/elephant-alpha…
  ✔ LLM returned valid metadata
Save JSON to [/home/user/NEXUS/placement_data_mtech.json]:
✔ Saved to /home/user/NEXUS/placement_data_mtech.json
```

---

## Using as a Library

```python
# Local mode
from main import process_pdf
result = process_pdf("path/to/document.pdf")

# LLM mode
from main_llm import process_pdf
result = process_pdf("path/to/document.pdf")

print(result["title"])
print(result["category"])
```

---

## Project Structure

```
NEXUS/
├── main.py              # Local-only converter (pymupdf4llm + heuristics)
├── main_llm.py          # LLM-powered converter (pymupdf4llm + OpenRouter Elephant)
├── requirements.txt     # Python dependencies
├── .env                 # API key (git-ignored, LLM mode only)
├── .gitignore
└── README.md
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `OPENROUTER_API_KEY is not set` | Add your key to `.env` (only needed for `main_llm.py`) |
| `No extractable text found in the PDF` | The PDF may be image-based (scanned). Install `tesseract` on your system to enable automatic OCR support. |
| `LLM did not return valid JSON` | Retry — the model may have returned malformed output |
| Rate-limited (429) | The script retries automatically up to 5 times with exponential backoff |
