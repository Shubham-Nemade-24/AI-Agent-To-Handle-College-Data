# query_data.py
import os
from langchain.prompts import ChatPromptTemplate
from langchain_ollama import OllamaLLM

PROMPT_TEMPLATE = """
You are a highly accurate certificate data extractor.

Your task is to read the certificate text and extract the required details into a **single structured row** that matches the exact column order below:

[
  "Professor Name",
  "Certificate Issue Date",
  "Certificate Number",
  "Course / Exam / Purpose",
  "Grade / Marks",
  "Institution / Issuing Authority",
  "Registration / Roll No",
  "Address",
  "Other Details"
]

---

### OUTPUT FORMAT (strict):

Return ONLY a single Python list like:

["Professor Name", "YYYY-MM-DD", "CERT-001", "Course name", "Grade", "Institution", "ROLL123", "Address", "Extra details"]

- Use empty string "" if any field is missing.
- The output MUST be a valid Python list with 9 items.
- Do NOT add explanations, labels, or multiline text.
- Dates must be in **YYYY-MM-DD** format.
- "Other Details" should include any leftover information like signatures, comments, reference numbers, seals, or notes.

---

### CERTIFICATE TEXT:
{context}
"""


def run_extraction_on_context(context_text: str) -> str:
    """
    Calls the Ollama Mistral model with the given context.
    Returns the raw model response (string).
    """
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text)

    print("🤖 Invoking Mistral (Ollama) for extraction...")
    model = OllamaLLM(model="mistral")

    try:
        response_text = model.invoke(prompt)
    except Exception as e:
        raise RuntimeError(f"Model invocation failed: {e}")

    return response_text