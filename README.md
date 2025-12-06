# 📄 AI Agent Certificate Data Extractor  
### Automated system for processing PDF/Image certificates using OCR, LLM extraction, deduplication, embeddings, and Google Sheets sync.

---

## 🚀 Overview

This project is an **AI-powered automated certificate processing system** that can:

- Ingest **multiple PDF/Image certificates**  
- Perform **OCR (text extraction)**  
- Use a local **Mistral (Ollama)** model to extract structured certificate fields  
- Store searchable embeddings in **ChromaDB**  
- Prevent duplicates using **multi-layer deduplication**  
- Push structured rows directly into **Google Sheets**  
- Allow users to **chat with the entire certificate database** using a **RAG pipeline**  
- Provide a full **Streamlit UI** for easy use  

This is designed for colleges/institutions that handle multiple faculty documents and want an automated, intelligent data extraction workflow.

---

## 🧠 Features

### 🔹 1. Multi-File Upload (PDFs & Images)
Upload multiple certificates at once via a clean Streamlit interface.

---

### 🔹 2. OCR + LLM Extraction
- Uses **PyPDFLoader** for selectable text  
- Falls back to **OCR (Tesseract)** for scanned PDFs/images  
- Feeds extracted text to a local **Mistral (Ollama)** LLM  
- Model returns a strict **9-field structured list**:
  - Professor Name  
  - Issue Date  
  - Certificate Number  
  - Course / Exam / Purpose  
  - Grade / Marks  
  - Institution  
  - Registration / Roll No  
  - Address  
  - Other Details  

---

### 🔹 3. Multi-Layer Deduplication  
To ensure **no duplicate certificates** are processed:

1. **SHA-256 File Hashing**  
2. **Content Hashing (text-based)**  
3. **ChromaDB chunk ID dedupe**

This means the system skips certificates that:

✔ Have the same file  
✔ Have the same extracted text  
✔ Are already embedded in the vector DB  

---

### 🔹 4. ChromaDB Embeddings  
- Documents are chunked  
- Embedded using a custom embedding model  
- Stored persistently in `chroma/`

---

### 🔹 5. RAG-Based Chat System  
Users can ask questions like:

> "Which certificates belong to Dr. Sharma?"  
> "What grade was achieved in NPTEL course?"  
> "How many FDP certificates are uploaded?"

The system retrieves relevant chunks and generates an answer using Mistral.

---

### 🔹 6. Google Sheets Integration  
Structured certificate data is automatically appended to your Google Sheet:

- Uses Google Sheets API  
- Auto-handles header creation  
- Includes error handling  
- Perfect for creating a centralized digital record  

---

### 🔹 7. Streamlit UI  
User-friendly interface includes:

- 📤 Upload & Process certificates  
- 💬 Chat with Vector Database  
- 📊 View synced Google Sheet data  
- 🔄 Reset tools  

---

## 🏗️ Project Structure

AI-Agent-Certificate-Data-Extractor/
│
├── app.py                          # Streamlit UI
├── populate_database.py             # CLI ingestion script
├── query_data.py                    # LLM extraction prompt
├── gs_connectivity.py               # Google Sheet API wrapper
├── get_embedding_function.py        # Embedding model
├── processed_doc_hashes.txt         # Content-level dedupe registry
├── chroma/                          # Vector storage (auto-created)
├── data/                            # Uploaded files (auto-created)
├── outputs/                         # Raw model responses
└── reset_vector_db.py               # Clear vector DB & metadata

---

## 🛠️ Installation & Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/AI-Agent-Certificate-Data-Extractor.git
cd AI-Agent-Certificate-Data-Extractor

2. Create Virtual Environment

python3 -m venv venv
source venv/bin/activate

3. Install Dependencies

pip install -r requirements.txt

4. Install & Run Ollama (Mistral Model)

ollama pull mistral

5. Add Google Sheets Credentials

Place your service account file as:

gs-credentials.json

And update SHEET_ID in gs_connectivity.py.

⸻

▶️ Run Streamlit App

streamlit run app.py


⸻

🧹 Reset Vector Database (If Needed)

python reset_vector_db.py


⸻

📌 Example Use Cases
	•	College/University certificate documentation
	•	Digital archiving of faculty records
	•	Automated extraction for NPTEL, FDP, Workshop, seminar certificates
	•	HR/academic verification systems

⸻
