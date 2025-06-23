# extract.py

import io
import os
import json
import tempfile
from typing import List, Dict
import pymupdf
from mistralai import Mistral
from fastapi.responses import FileResponse
import base64

# Initialize Mistral client
client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))


def get_fields_with_positions(pa_pdf_bytes: bytes) -> List[Dict]:
    """Extract PA form fields with their type, page number, position, and label."""
    doc = pymupdf.open(stream=pa_pdf_bytes, filetype="pdf")
    fields = []
    for page_index in range(len(doc)):
        page = doc[page_index]
        w = page.first_widget
        while w:
            fields.append(
                {
                    "name": w.field_name,
                    "type": w.field_type_string,
                    "page": page_index + 1,
                    "bbox": tuple(w.rect),  # (x0, y0, x1, y1)
                    "label": w.field_label or "",
                }
            )
            w = w.next
    doc.close()
    return fields


def ocr_markdown_pages(pdf_bytes: bytes) -> Dict[int, str]:
    # Encode PDF to base64
    encoded = base64.b64encode(pdf_bytes).decode("utf-8")
    
    """OCR the PDF and return markdown text per page for contextual extraction."""
    resp = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{encoded}"
        },
        include_image_base64=False,
    )
    return {page.index + 1: getattr(page, "markdown", "") for page in resp.pages}


def process_referral(
    pa_fields: List[Dict], referral_pdf_bytes: bytes, pa_text: str
) -> Dict[str, str]:
    """
    OCR referral PDF and extract each PA field value via Mistral Chat.
    Context includes PA form structure and referral text.
    """
    referral_pages = ocr_markdown_pages(referral_pdf_bytes)
    referral_text = "\n\n".join(referral_pages.values())[:2000]

    chat_input = (
        f"PA field definitions (for context):\n{json.dumps(pa_fields, indent=2)}\n\n"
        f"PA form context:\n{pa_text[:1000]}...\n\n"
        f"Referral document excerpts:\n{referral_text}...\n\n"
        "Please return a JSON mapping field names to values. "
        'For checkboxes/radios use "Yes" or "No".'
    )

    resp = client.chat.complete(
        model="mistral-large-latest", messages=[{"role": "user", "content": chat_input}]
    )
    try:
        content = resp.choices[0].message.content
        # Extract JSON from within the markdown code block if present
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            json_str = content[start:end+1]
            return json.loads(json_str)
        else:
            raise ValueError("No JSON object found in response")
    except (json.JSONDecodeError, ValueError):
        raise ValueError(
            "Invalid JSON from Mistral:\n" + resp.choices[0].message.content
        )


def fill_pa(pa_pdf_bytes: bytes, filled_data: Dict[str, str]) -> str:
    """Fill PA PDF form (text + buttons) and save to a temp file."""
    doc = pymupdf.open(stream=pa_pdf_bytes, filetype="pdf")

    for page in doc:
        for field in page.widgets():
            field_name = field.field_name
            if field_name in filled_data:
                value = filled_data.get(field_name)
                if value is None:
                    continue

                if value == "":
                    field.field_value = ""
                    field.update()
                    continue

                if field.field_type == 1:  # Checkbox
                    if str(value).lower() in ("yes", "true", "1", "on"):
                        field.field_value = True
                    else:
                        field.field_value = False
                elif field.field_type == 2:  # Radio button
                    if field.choice_values and value in field.choice_values:
                        field.field_value = value
                else:
                    field.field_value = str(value)
                
                field.update()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_path = tmp.name
    tmp.close()
    doc.save(tmp_path, garbage=4, deflate=True, clean=True)
    doc.close()
    return tmp_path


def process_files(pa_pdf_bytes: bytes, referral_pdf_bytes: bytes) -> FileResponse:
    """
    Full workflow:
    1. Extract PA field metadata
    2. OCR PA to get context
    3. OCR referral + use Mistral Chat to extract values
    4. Fill PA PDF
    5. Return the filled PA as FileResponse
    """
    fields = get_fields_with_positions(pa_pdf_bytes)
    pa_context = "\n\n".join(ocr_markdown_pages(pa_pdf_bytes).values())
    filled_data = process_referral(fields, referral_pdf_bytes, pa_context)
    filled_path = fill_pa(pa_pdf_bytes, filled_data)
    return FileResponse(
        filled_path,
        media_type="application/pdf",
        filename="filled_PA.pdf",
        headers={"Content-Disposition": "attachment; filename=filled_PA.pdf"},
    )
