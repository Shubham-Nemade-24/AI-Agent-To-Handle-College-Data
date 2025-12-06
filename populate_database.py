# populate_database.py
"""
Populate Chroma vector DB from PDFs in the `data/` folder.
For each PDF: ingest chunks; IF new chunks were added, run the extractor
on that document and append the returned row to Google Sheets.
"""

import argparse
import os
import shutil
import ast
from datetime import datetime
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.schema.document import Document
from get_embedding_function import get_embedding_function
from langchain_community.document_loaders import PyPDFLoader
from langchain_chroma import Chroma

# OCR imports
from pdf2image import convert_from_path
import pytesseract

# Import extraction + gs helpers
from query_data import run_extraction_on_context
import gs_connectivity as gs

CHROMA_PATH = "chroma"
DATA_PATH = "data"
OUTPUTS_DIR = "outputs"


def extract_text_with_ocr(pdf_path):
    print(f"🧠 Running OCR on image-based PDF: {os.path.basename(pdf_path)}")
    try:
        pages = convert_from_path(pdf_path)
        text = ""
        for i, page in enumerate(pages):
            page_text = pytesseract.image_to_string(page)
            text += f"\n--- Page {i + 1} ---\n" + page_text
        return Document(page_content=text.strip(), metadata={"source": pdf_path, "page": 1})
    except Exception as e:
        print(f"❌ OCR failed for {pdf_path}: {e}")
        return None


def load_documents_grouped_by_source():
    print(f"📂 Loading PDFs from '{DATA_PATH}'...")
    documents_by_source = {}
    if not os.path.exists(DATA_PATH):
        print(f"⚠️ Data path '{DATA_PATH}' does not exist. Create it and add PDFs.")
        return documents_by_source

    for filename in sorted(os.listdir(DATA_PATH)):
        if not filename.lower().endswith(".pdf"):
            continue
        pdf_path = os.path.join(DATA_PATH, filename)
        print(f"📄 Loading: {filename}")
        try:
            loader = PyPDFLoader(pdf_path)
            pages = loader.load()

            combined_text = " ".join([p.page_content for p in pages]).strip()
            if not combined_text:
                ocr_doc = extract_text_with_ocr(pdf_path)
                if ocr_doc:
                    documents_by_source[pdf_path] = [ocr_doc]
                else:
                    print(f"⚠️ Skipping {filename} (no text extracted)")
            else:
                for i, p in enumerate(pages):
                    if not isinstance(p.metadata, dict):
                        p.metadata = {}
                    p.metadata["source"] = pdf_path
                    p.metadata["page"] = p.metadata.get("page", i + 1)
                documents_by_source[pdf_path] = pages

        except Exception as e:
            print(f"⚠️ Error loading {filename}: {e} — falling back to OCR")
            ocr_doc = extract_text_with_ocr(pdf_path)
            if ocr_doc:
                documents_by_source[pdf_path] = [ocr_doc]
            else:
                print(f"❌ Skipping {filename}: {e}")

    print(f"✅ Total PDF sources loaded: {len(documents_by_source)}")
    return documents_by_source


def split_documents(documents):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=80,
        length_function=len,
        is_separator_regex=False,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"✂️ Split into {len(chunks)} text chunks.")
    return chunks


def calculate_chunk_ids(chunks):
    last_page_id = None
    chunk_index = 0
    for chunk in chunks:
        source = chunk.metadata.get("source", "unknown_source")
        page = chunk.metadata.get("page", 0)
        current_page_id = f"{source}:{page}"

        if current_page_id == last_page_id:
            chunk_index += 1
        else:
            chunk_index = 0

        chunk.metadata["id"] = f"{current_page_id}:{chunk_index}"
        last_page_id = current_page_id
    return chunks


def add_chunks_to_chroma(chunks):
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embedding_function())
    chunks = calculate_chunk_ids(chunks)

    try:
        existing_items = db.get(include=["ids"])
        existing_ids = set(existing_items.get("ids", []))
    except Exception:
        existing_ids = set()

    new_chunks = [c for c in chunks if c.metadata["id"] not in existing_ids]
    print(f"📦 Existing chunks: {len(existing_ids)}. New chunks to add: {len(new_chunks)}")

    if new_chunks:
        ids = [c.metadata["id"] for c in new_chunks]
        db.add_documents(new_chunks, ids=ids)
        print("✅ Added new chunks to Chroma and persisted.")
    else:
        print("ℹ️ No new chunks to add.")

    return new_chunks  # return newly added chunks (may be empty)


def save_raw_output(source, model_response):
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    base = os.path.splitext(os.path.basename(source))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{OUTPUTS_DIR}/extraction_{base}_{timestamp}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Source: {source}\n")
        f.write("Model response:\n")
        f.write(model_response.strip() + "\n")
    print(f"💾 Saved model response -> {filename}")


def try_parse_row(model_response: str):
    """
    Try to safely parse the model response into a Python list using ast.literal_eval.
    Returns list if successful and length==9, otherwise None.
    """
    try:
        parsed = ast.literal_eval(model_response.strip())
        if isinstance(parsed, (list, tuple)) and len(parsed) == 9:
            return list(parsed)
    except Exception:
        pass
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Reset the database.")
    args = parser.parse_args()

    if args.reset:
        if os.path.exists(CHROMA_PATH):
            shutil.rmtree(CHROMA_PATH)
            print("🗑️ Chroma database cleared.")

    sources = load_documents_grouped_by_source()
    if not sources:
        print("⚠️ No PDFs found to ingest.")
        return

    # Initialize sheet once (ensures header)
    try:
        gs.init_sheet()
    except Exception as e:
        print(f"⚠️ Google Sheets init failed: {e}")
        print("Make sure gs-credentials.json exists and SHEET_ID is correct.")
        sheet_available = False
    else:
        sheet_available = True

    for source, docs in sources.items():
        print(f"\n📄 Processing source: {os.path.basename(source)}")
        chunks = split_documents(docs)
        if not chunks:
            print("⚠️ No chunks for this source; skipping.")
            continue

        new_chunks = add_chunks_to_chroma(chunks)

        # Duplicate detection
        if not new_chunks:
            print("ℹ️ This file already exists in the vector database (no new chunks).")
            print("   Skipping embedding + extraction for this file to avoid duplicates.")
            continue

        # Build context text for LLM extraction
        context_text = "\n\n---\n\n".join([c.page_content for c in chunks])

        try:
            model_response = run_extraction_on_context(context_text)
        except Exception as e:
            print(f"❌ Extraction failed for {os.path.basename(source)}: {e}")
            continue

        save_raw_output(source, model_response)

        parsed_row = try_parse_row(model_response)
        if parsed_row is None:
            print("⚠️ Model response could not be parsed into a 9-item list. Saved raw output. Skipping sheet append.")
            continue

        if sheet_available:
            try:
                gs.append_row(parsed_row)
                print("✅ Appended extracted row to Google Sheet.")
            except Exception as e:
                print(f"❌ Failed to append to Google Sheet: {e}")
                print("Saved raw output locally.")

    print("\n🎉 All done.")


if __name__ == "__main__":
    main()