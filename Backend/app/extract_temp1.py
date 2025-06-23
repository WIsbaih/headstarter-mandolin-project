# extract.py
import os
import io
import json
import tempfile
from typing import List, Dict

import PyPDF2
from mistralai import Mistral
from fastapi.responses import FileResponse

# Initialize Mistral client
client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

def get_field_names(pa_pdf_bytes: bytes) -> List[str]:
    """Retrieve the list of form field names from the PA PDF."""
    reader = PyPDF2.PdfReader(io.BytesIO(pa_pdf_bytes))
    fields = reader.get_fields() or {}
    return list(fields.keys())

def process_referral(referral_bytes: bytes, field_names: List[str]) -> Dict[str, str]:
    """OCR the referral PDF and extract PA field values via Mistral Chat."""
    # Run Mistral OCR
    ocr_resp = client.ocr.process(
        model="mistral-ocr-latest",
        document={"type": "document_bytes", "content": referral_bytes},
        include_image_base64=False
    )

    # Combine markdown text from all OCR'd pages
    full_text = "\n\n".join(getattr(page, "markdown", "") for page in ocr_resp.pages)

    # Build prompt using field names
    prompt = (
        f"Extract values for these PA form fields as JSON:\n"
        f"{json.dumps(field_names)}\n\n"
        f"Referral Document Text:\n{full_text}\n\n"
        "Return only a JSON object like {\"FieldName1\": \"value1\", ...}. "
        "If a field is missing, use an empty string."
    )

    # Mistral Chat completion
    chat_resp = client.chat.complete(
        model="mistral-large-latest",
        messages=[{"role": "user", "content": prompt}]
    )

    # Parse and return
    try:
        return json.loads(chat_resp.choices[0].message.content.strip())
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON from Mistral: " + chat_resp.choices[0].message.content)

def fill_pa(pa_pdf_bytes: bytes, data: Dict[str, str]) -> str:
    """Fill the PA PDF with the extracted field values and save it."""
    reader = PyPDF2.PdfReader(io.BytesIO(pa_pdf_bytes))
    writer = PyPDF2.PdfWriter()
    for pg in reader.pages:
        writer.add_page(pg)
    writer.update_page_form_field_values(writer.pages[0], data)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    writer.write(tmp)
    tmp.close()
    return tmp.name

def process_files(pa_pdf: bytes, referral_pdf: bytes) -> FileResponse:
    """End-to-end: Extract fields, OCR referral, map values, fill PA, and return PDF."""
    field_names = get_field_names(pa_pdf)
    extracted = process_referral(referral_pdf, field_names)
    output_path = fill_pa(pa_pdf, extracted)
    return FileResponse(output_path, media_type="application/pdf", filename="filled_PA.pdf")
