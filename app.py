import os
import hashlib
import pandas as pd
from PIL import Image

import streamlit as st

from langchain.schema.document import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_chroma import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain_ollama import OllamaLLM

import pytesseract

from populate_database import (
    DATA_PATH,
    CHROMA_PATH,
    extract_text_with_ocr,
    split_documents,
    add_chunks_to_chroma,
    save_raw_output,
    try_parse_row,
)
from query_data import run_extraction_on_context
import gs_connectivity as gs
from get_embedding_function import get_embedding_function


# ---------- Content-level dedupe registry ----------

DOC_HASHES_FILE = "processed_doc_hashes.txt"


def load_processed_hashes():
    """Load previously processed document content hashes (one per line)."""
    if not os.path.exists(DOC_HASHES_FILE):
        return set()
    with open(DOC_HASHES_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def store_processed_hash(doc_hash: str):
    """Append a new processed document content hash to the registry file."""
    with open(DOC_HASHES_FILE, "a", encoding="utf-8") as f:
        f.write(doc_hash + "\n")


# ---------- Helpers for processing uploads ----------

def ensure_data_dir():
    os.makedirs(DATA_PATH, exist_ok=True)


def save_uploaded_file(uploaded_file):
    """
    Save uploaded file into DATA_PATH with a content-hash-based filename.
    Returns (save_path, already_exists) where already_exists=True means
    a file with the same content hash was already present in the data folder.
    """
    ensure_data_dir()
    file_bytes = uploaded_file.read()
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    _, ext = os.path.splitext(uploaded_file.name)
    ext = ext.lower() or ".bin"
    save_path = os.path.join(DATA_PATH, f"{file_hash}{ext}")

    already_exists = os.path.exists(save_path)
    if not already_exists:
        with open(save_path, "wb") as f:
            f.write(file_bytes)

    return save_path, already_exists


def prepare_docs_from_pdf(pdf_path: str):
    """
    Load a single PDF and return a list of Documents, similar to
    load_documents_grouped_by_source() but for one file only.
    """
    try:
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()
        combined_text = " ".join([p.page_content for p in pages]).strip()
        if not combined_text:
            # Fall back to OCR if no text
            ocr_doc = extract_text_with_ocr(pdf_path)
            if ocr_doc:
                return [ocr_doc]
            else:
                raise ValueError("No text extracted from PDF, even with OCR.")
        else:
            # Ensure metadata
            for i, p in enumerate(pages):
                if not isinstance(p.metadata, dict):
                    p.metadata = {}
                p.metadata["source"] = pdf_path
                p.metadata["page"] = p.metadata.get("page", i + 1)
            return pages

    except Exception:
        # Last-resort OCR
        ocr_doc = extract_text_with_ocr(pdf_path)
        if ocr_doc:
            return [ocr_doc]
        raise


def prepare_docs_from_image(image_path: str):
    """
    Run OCR on an image file and wrap the text into a single Document.
    """
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)
    text = text.strip()
    if not text:
        raise ValueError("No text extracted from image via OCR.")
    doc = Document(page_content=text, metadata={"source": image_path, "page": 1})
    return [doc]


def process_document(source_path: str, is_pdf: bool):
    """
    Full pipeline for ONE document (PDF or image):
      - load/ocr -> docs
      - split into chunks
      - check content-hash dedupe
      - add to chroma (embedding)
      - if new chunks: call extraction LLM, save raw output, append to sheet
    Returns a dict with status + extra info for UI.
    """
    # 1. Prepare documents
    if is_pdf:
        docs = prepare_docs_from_pdf(source_path)
    else:
        docs = prepare_docs_from_image(source_path)

    # 2. Split into chunks
    chunks = split_documents(docs)
    if not chunks:
        return {"status": "error", "message": "No text chunks created from this document."}

    # 3. Build context text once (used for both content-hash and extraction)
    context_text = "\n\n---\n\n".join([c.page_content for c in chunks])

    # 4. Content-level dedupe based on extracted text
    doc_hash = hashlib.sha256(context_text.encode("utf-8")).hexdigest()
    processed_hashes = load_processed_hashes()
    if doc_hash in processed_hashes:
        return {
            "status": "exists",
            "message": "A document with the same content has already been processed. Skipping.",
        }

    # 5. Add to Chroma, check duplicates at vector DB level
    new_chunks = add_chunks_to_chroma(chunks)
    if not new_chunks:
        # This means all chunk IDs already exist in Chroma
        return {
            "status": "exists",
            "message": "This document already exists in the vector database. Skipping extraction.",
        }

    # 6. Run extraction LLM
    try:
        model_response = run_extraction_on_context(context_text)
    except Exception as e:
        return {"status": "error", "message": f"Extraction failed: {e}"}

    # 7. Save raw output
    save_raw_output(source_path, model_response)

    # 8. Parse into row and append to sheet
    parsed_row = try_parse_row(model_response)
    sheet_status = None
    if parsed_row is None:
        sheet_status = "parse_failed"
    else:
        try:
            gs.append_row(parsed_row)
            sheet_status = "appended"
        except Exception as e:
            sheet_status = f"sheet_error: {e}"

    # 9. Mark this content hash as processed (only after successful processing)
    store_processed_hash(doc_hash)

    return {
        "status": "processed",
        "message": "Document processed and embeddings stored.",
        "model_response": model_response,
        "parsed_row": parsed_row,
        "sheet_status": sheet_status,
    }


# ---------- QA over Vector DB ----------

def get_chroma_db():
    return Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=get_embedding_function(),
    )


def answer_question_over_db(question: str, k: int = 4):
    """
    Retrieve top-k relevant chunks from Chroma and answer using Ollama (Mistral).
    """
    db = get_chroma_db()
    try:
        docs = db.similarity_search(question, k=k)
    except Exception as e:
        return {
            "answer": None,
            "context_docs": [],
            "error": f"Error querying vector database: {e}",
        }

    if not docs:
        return {
            "answer": None,
            "context_docs": [],
            "error": "No documents found in the vector database.",
        }

    context_text = "\n\n---\n\n".join([d.page_content for d in docs])

    prompt_template = ChatPromptTemplate.from_template(
        """
You are a helpful assistant answering questions based on certificate and related documents.
Use ONLY the information provided in the CONTEXT below.
If the answer is not clearly contained in the context, say you do not know.

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
""".strip()
    )

    prompt = prompt_template.format(context=context_text, question=question)
    llm = OllamaLLM(model="mistral")
    try:
        answer = llm.invoke(prompt)
    except Exception as e:
        return {
            "answer": None,
            "context_docs": docs,
            "error": f"Model invocation failed: {e}",
        }

    return {
        "answer": answer,
        "context_docs": docs,
        "error": None,
    }


# ---------- Streamlit Pages ----------

def page_upload_and_extract():
    st.header("Upload & Process Certificates")

    uploaded_files = st.file_uploader(
        "Upload certificate(s) (PDF or image)",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        st.write("**Selected files:**")
        for f in uploaded_files:
            st.write(f"- `{f.name}`")

        if st.button("Process uploaded files"):
            for uploaded_file in uploaded_files:
                with st.spinner(f"Processing `{uploaded_file.name}`..."):
                    # Save to data/ with hash-based name, detect duplicates at file level
                    save_path, already_exists = save_uploaded_file(uploaded_file)
                    is_pdf = save_path.lower().endswith(".pdf")

                    # If file already exists in data folder, skip all further processing
                    if already_exists:
                        st.warning(
                            f"`{uploaded_file.name}` already exists in the data folder "
                            f"as `{os.path.basename(save_path)}`. "
                            "Skipping embeddings and extraction to avoid duplicates."
                        )
                        continue

                    try:
                        result = process_document(save_path, is_pdf=is_pdf)
                    except Exception as e:
                        st.error(f"Unexpected error while processing `{uploaded_file.name}`: {e}")
                        continue

                    # Remember last result in session state (for sheet view fallback)
                    st.session_state["last_upload_result"] = result

                    status = result.get("status")
                    msg = result.get("message", "")

                    if status == "exists":
                        st.warning(f"`uploaded_file.name`: {msg}")
                    elif status == "processed":
                        st.success(f"`{uploaded_file.name}`: {msg}")
                    elif status == "error":
                        st.error(f"`{uploaded_file.name}`: {msg}")
                    else:
                        st.info(f"`{uploaded_file.name}`: {msg}")

                    # Show model response and parsed row per file
                    if "model_response" in result and result["model_response"] is not None:
                        with st.expander(f"Raw model response for `{uploaded_file.name}`"):
                            st.text(result["model_response"])

                    if result.get("parsed_row") is not None:
                        st.subheader(f"Parsed row (9 fields) for `{uploaded_file.name}`")
                        st.write(result["parsed_row"])
                    else:
                        st.info(
                            f"Model response for `{uploaded_file.name}` "
                            "could not be parsed into a 9-item list."
                        )

                    sheet_status = result.get("sheet_status")
                    if sheet_status == "appended":
                        st.success(f"`{uploaded_file.name}`: Row appended to Google Sheet.")
                    elif sheet_status == "parse_failed":
                        st.warning(
                            f"`{uploaded_file.name}`: Could not parse response into a row. "
                            "Nothing appended to sheet."
                        )
                    elif isinstance(sheet_status, str) and sheet_status.startswith("sheet_error"):
                        st.error(f"`{uploaded_file.name}`: Google Sheet error: {sheet_status}")


def page_chat_with_db():
    st.header("Chat with the Vector Database")

    question = st.text_input("Ask a question about all uploaded certificates/data:")

    if st.button("Ask"):
        if not question.strip():
            st.warning("Please enter a question first.")
            return

        with st.spinner("Retrieving relevant context and generating answer..."):
            result = answer_question_over_db(question)

        if result["error"]:
            st.error(result["error"])
            return

        st.subheader("Answer")
        st.write(result["answer"])

        with st.expander("Context used from vector DB"):
            for i, doc in enumerate(result["context_docs"], start=1):
                st.markdown(
                    f"**Chunk {i}** (source: `{doc.metadata.get('source', 'unknown')}`, "
                    f"page: {doc.metadata.get('page', '?')})"
                )
                st.text(doc.page_content)
                st.markdown("---")


def page_view_sheet():
    st.header("View Google Sheet Data")

    try:
        sheet = gs.init_sheet()
        records = sheet.get_all_records()
        if not records:
            st.info("Google Sheet is empty (no records yet).")
        else:
            df = pd.DataFrame(records)
            st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Could not load Google Sheet: {e}")
        st.markdown("---")
        st.subheader("Fallback: last model response of uploaded document (this session)")

        last = st.session_state.get("last_upload_result")
        if last and last.get("model_response"):
            st.text(last["model_response"])
        else:
            st.info("No uploaded document/model response available in this session.")


# ---------- Main App ----------

def main():
    st.set_page_config(
        page_title="AI Agent for Professor Certificate Data",
        page_icon="📄",
        layout="wide",
    )

    if "last_upload_result" not in st.session_state:
        st.session_state["last_upload_result"] = None

    st.title("📄 AI Agent for Managing Professor Certificate Data")

    page = st.sidebar.radio(
        "Navigation",
        ["Upload & Extract", "Chat with Database", "View Google Sheet"],
    )

    if page == "Upload & Extract":
        page_upload_and_extract()
    elif page == "Chat with Database":
        page_chat_with_db()
    elif page == "View Google Sheet":
        page_view_sheet()


if __name__ == "__main__":
    main()