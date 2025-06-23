# extract.py

import io
import os
import json
import tempfile
import asyncio
from typing import List, Dict
import pymupdf
from mistralai import Mistral
from fastapi.responses import FileResponse
from app.misteralai_service import get_chat_response, get_chat_response_async, ocr_markdown_pages, ocr_markdown_pages_list

# Initialize Mistral client
client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))


async def get_fields_with_positions_async(pa_pdf_bytes: bytes) -> List[Dict]:
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
                    "description": "",
                }
            )
            w = w.next
    doc.close()

    fields_with_details = await get_fields_details_async(fields=fields, pdf_bytes=pa_pdf_bytes)
    return fields_with_details


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
                    "description": "",
                }
            )
            w = w.next
    doc.close()

    fields_with_details = get_fields_details(fields=fields, pdf_bytes=pa_pdf_bytes)
    return fields_with_details


async def get_fields_details_async(fields: List[Dict], pdf_bytes: bytes):
    import time
    start_time = time.time()
    
    # Get all pages as a list
    pages_list = ocr_markdown_pages_list(pdf_bytes)
    
    # Split fields into groups of maximum 20
    field_groups = [fields[i:i + 20] for i in range(0, len(fields), 20)]
    
    async def process_field_group(group_index, field_group):
        group_start = time.time()
        print(f"Starting processing for group {group_index + 1} with {len(field_group)} fields")
        
        # Get all page content for this group
        pages_content = []
        for field in field_group:
            page_num = field["page"]
            if page_num <= len(pages_list):
                page_content = pages_list[page_num - 1]
                if page_content not in pages_content:
                    pages_content.append(page_content)
        
        # Combine relevant page content
        combined_content = "\n\n".join(pages_content)
        
        chat_input = (
            f"Prior Authorization document fields (Group {group_index + 1}):\n{json.dumps(field_group, indent=2)}\n\n"
            f"Document content:\n{combined_content[:300]}...\n\n"
            "Please return a JSON array of fields as is with filling the description value with the meaningful short description based on this specific page. The output should be a valid JSON array."
        )

        resp = await get_chat_response_async(chat_input)
        
        group_end = time.time()
        print(f"Completed group {group_index + 1} in {group_end - group_start:.2f} seconds")

        try:
            content = resp.choices[0].message.content
            # Extract JSON from within the markdown code block if present
            start = content.find('[')
            end = content.rfind(']')
            if start != -1 and end != -1:
                json_str = content[start:end+1]
                return json.loads(json_str)
            else:
                raise ValueError("No JSON array found in response")
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(
                f"Invalid JSON from Mistral: {e}\n" + resp.choices[0].message.content
            )
    
    # Process all field groups concurrently
    tasks = [process_field_group(i, group) for i, group in enumerate(field_groups)]
    print(f"Starting {len(tasks)} concurrent tasks for {len(field_groups)} groups")
    
    results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    print(f"Total processing time: {end_time - start_time:.2f} seconds")
    
    # Flatten the results
    all_results = []
    for result in results:
        all_results.extend(result)
    
    return all_results


def get_fields_details(fields: List[Dict], pdf_bytes: bytes):

    pdf_text = "\n\n".join(ocr_markdown_pages(pdf_bytes).values())

    # Split fields into groups of 10
    field_groups = [fields[i:i + 10] for i in range(0, len(fields), 10)]
    
    all_results = []
    
    for group in field_groups:
        chat_input = (
            f"Prior Authorization document fields:\n{json.dumps(group, indent=2)}\n\n"
            f"Prior Authorization document pages:\n{pdf_text[:500]}...\n\n"
            "Please return a JSON array of fields as is with filling the description value with the meaningful short description based on the document pages. The output should be a valid JSON array."
        )

        resp = get_chat_response(chat_input)

        try:
            content = resp.choices[0].message.content
            # Extract JSON from within the markdown code block if present
            start = content.find('[')
            end = content.rfind(']')
            if start != -1 and end != -1:
                json_str = content[start:end+1]
                group_results = json.loads(json_str)
                all_results.extend(group_results)
            else:
                raise ValueError("No JSON array found in response")
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(
                f"Invalid JSON from Mistral: {e}\n" + resp.choices[0].message.content
            )
    
    return all_results


def process_referral(
    pa_fields: List[Dict], referral_pdf_bytes: bytes
) -> Dict[str, str]:
    """
    OCR referral PDF and extract each PA field value via Mistral Chat.
    Context includes PA form structure and referral text.
    """
    referral_pages = ocr_markdown_pages(referral_pdf_bytes)
    referral_text = "\n\n".join(referral_pages.values())[:2000]

    chat_input = (
        "Insurance Prior Authorization PDF fields (with bounding boxes):\n"
        f"{json.dumps(pa_fields, indent=2)}\n\n"
        "Referral document excerpts:\n"
        f"{referral_text}...\n\n"
        "Instructions:\n"
        "- Map each Prior Authorization field to its value from the referral document.\n"
        '- For checkboxes and radio buttons, use "Yes" or "No" only.\n'
        '- Use the "bbox" property to match fields spatially if needed.\n'
        "- Return only a valid JSON object mapping field names to values. Do NOT include comments or explanations—just the JSON.\n"
    )

    resp = get_chat_response(chat_input)
    try:
        content = resp.choices[0].message.content
        # Extract JSON from within the markdown code block if present
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            json_str = content[start : end + 1]
            # Remove comments from JSON string
            import re
            # Remove single-line comments (// ...)
            json_str = re.sub(r'//.*?(?=\n|$)', '', json_str)
            # Remove multi-line comments (/* ... */)
            json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
            # Clean up any extra whitespace
            json_str = re.sub(r'\n\s*\n', '\n', json_str)
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
    
    print(f"Filling PDF with {len(filled_data)} fields")
    checkbox_count = 0
    text_count = 0

    for page in doc:
        for field in page.widgets():
            field_name = field.field_name
            if field_name in filled_data:
                value = filled_data.get(field_name)
                if value is None:
                    continue

                print(f"Processing field: {field_name} = '{value}' (type: {field.field_type_string}, field_type: {field.field_type})")

                if value == "":
                    field.field_value = ""
                    field.update()
                    continue

                if field.field_type == 1:  # Checkbox
                    checkbox_count += 1
                    # Check for various "yes" values
                    if str(value).lower() in ("yes", "true", "1", "on", "checked"):
                        print(f"Setting checkbox {field_name} to True")
                        field.field_value = True
                        field.update()
                    else:
                        print(f"Setting checkbox {field_name} to False")
                        field.field_value = False
                        field.update()
                    if field.choice_values and value in field.choice_values:
                        field.field_value = value
                        field.update()
                else:  # Text field
                    text_count += 1
                    field.field_value = str(value)
                    field.update()

    print(f"Processed {checkbox_count} checkboxes and {text_count} text fields")
    
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_path = tmp.name
    tmp.close()
    doc.save(tmp_path, garbage=4, deflate=True, clean=True)
    doc.close()
    return tmp_path


async def process_files_async(pa_pdf_bytes: bytes, referral_pdf_bytes: bytes) -> FileResponse:
    """
    Full workflow (async version):
    1. Extract PA field metadata
    2. OCR PA to get context
    3. OCR referral + use Mistral Chat to extract values
    4. Fill PA PDF
    5. Return the filled PA as FileResponse
    """
    fields = await get_fields_with_positions_async(pa_pdf_bytes)
    filled_data = process_referral(fields, referral_pdf_bytes)
    filled_path = fill_pa(pa_pdf_bytes, filled_data)
    return FileResponse(
        filled_path,
        media_type="application/pdf",
        filename="filled_PA.pdf",
        headers={"Content-Disposition": "attachment; filename=filled_PA.pdf"},
    )


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
