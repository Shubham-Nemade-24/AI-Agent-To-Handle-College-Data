# AI Agent To Handle College Data

# Certificate Extraction & Vector Search System  
### Local PDF → Chroma Vector DB → Mistral LLM → Google Sheet Automation  

This project processes certificate PDFs stored locally and extracts structured information from them using a complete pipeline consisting of:

- PDF loading with optional OCR
- Text chunking and embedding
- Chroma vector database storage
- Local Mistral model (via Ollama) for information extraction
- Automatic Google Sheets data entry
- Local logging of extraction output

This system ensures:

- Each PDF is embedded only once  
- Re-embedding occurs automatically if a PDF changes  
- Extracted data follows a strict structure  
- Results are appended into a single Google Sheet  
- All LLM outputs are archived locally  

---

## Features

### PDF ingestion  
Supports text-based and image-based PDFs with automatic OCR fallback.

### Deduplication and change detection  
Each PDF is hashed (SHA256).  
A `processed.json` file tracks:

- File hash  
- Chunk IDs  
- Last processed timestamp  

If nothing changed, the PDF is skipped.

### Vector database  
- Uses Chroma (local and persistent)  
- Automatically reprocesses missing/corrupted chunks  
- Prevents duplicate chunks  

### LLM-based extraction  
Uses Mistral via Ollama to extract:

[“Professor Name”, “Certificate Issue Date”, “Certificate Number”,
“Course/Exam/Purpose”, “Grade/Marks”, “Institution/Issuing Authority”,
“Registration/Roll No”, “Address”, “Other Details”]

### Google Sheets integration  
- Adds extracted rows to the same Google Sheet  
- Creates header automatically  

### Output logging  
Saves raw extraction output into:

outputs/extraction__.txt

---

## Project Structure

Chat_with_pdfs_locally/
│
├── populate_database.py        # Ingest PDFs → Update vector DB → Trigger extraction
├── query_data.py               # Extraction logic using Mistral
├── gs_connectivity.py          # Google Sheet writing logic
├── get_embedding_function.py   # Embedding loader
├── processed.json              # Tracks processed PDF metadata
│
├── data/                       # Input PDFs
│    ├── file1.pdf
│    ├── file2.pdf
│    └── …
│
├── chroma/                     # Vector store (auto-created)
├── outputs/                    # Raw extraction logs (auto-created)
│
└── gs-credentials.json         # Google Sheets service account key

---

## Requirements

### Install Python dependencies

```bash
pip install langchain langchain-community langchain-chroma \
    langchain-text-splitters langchain-ollama \
    pdf2image pytesseract pillow \
    gspread google-auth

System dependencies

macOS

brew install tesseract
brew install poppler

Ubuntu

sudo apt install tesseract-ocr poppler-utils

Ollama setup

Install Ollama: https://ollama.ai/

Pull Mistral:

ollama pull mistral

Start Ollama server:

ollama serve


⸻

Running the Complete Pipeline

Run everything with one command:

python populate_database.py

What happens:
	1.	Loads PDFs from data/
	2.	Performs OCR if needed
	3.	Splits text & generates embeddings
	4.	Stores embeddings in Chroma
	5.	Checks for duplicates using processed.json
	6.	For each new/updated PDF:
	•	Runs extraction
	•	Saves raw extraction in outputs/
	•	Appends cleaned output to Google Sheet

⸻

Resetting the System

To completely reset vector DB and metadata:

python populate_database.py --reset

Manual equivalent:

rm -rf chroma processed.json


⸻

Deduplication Logic Explained

For each PDF:
	1.	Compute file hash
	2.	Lookup PDF entry in processed.json
	3.	If hash matches:
	•	Verify all chunk IDs exist in Chroma
	•	If yes → skip
	•	If missing → re-ingest
	4.	If hash differs:
	•	Delete old chunks
	•	Re-ingest
	5.	Update metadata

Ensures consistency without duplicate embeddings.

⸻

Google Sheet Output Example

| Professor Name | Certificate Issue Date | Certificate Number |
| Course/Exam/Purpose | Grade/Marks | Institution | Roll No | Address | Other Details |
|----------------|-------------------------|---------------------|
| Dr. Sharma     | 2025-10-20             | CERT-001            |
| ML Workshop     | A       | IIT Bombay  | REG123 | Mumbai |         |


⸻

Extraction Logging Example

File saved at:

outputs/extraction_DocScanner_20250206_193211.txt

Contents:

Source: data/DocScanner.pdf
Model response:
["Dr. Sharma", "2025-10-20", "CERT-001", "AI Workshop", "A", "SPPU", "ROLL123", "", ""]


⸻

Troubleshooting

Problem: “File already processed” but vector DB empty

Run:

python populate_database.py --reset

Problem: Incorrect extraction

Check raw logs in outputs/.

Problem: Google Sheet not updating

Check:
	•	gs-credentials.json exists
	•	Service account email has edit permission
	•	Sheet ID is correct

⸻

Optional Enhancements

Possible future upgrades:
	•	Process DOCX, images
	•	Streamlit/Flask UI
	•	Progress bars
	•	Strict date normalization
	•	CSV export
	•	Parallel ingestion

⸻

License

For educational and institutional use.

⸻
