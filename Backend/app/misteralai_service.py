import os
import base64
from dotenv import load_dotenv
from mistralai import ChatCompletionResponse, Mistral
from typing import Dict, List

load_dotenv()
client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

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

def ocr_markdown_pages_list(pdf_bytes: bytes) -> List[str]:
    # Encode PDF to base64
    encoded = base64.b64encode(pdf_bytes).decode("utf-8")
    
    """OCR the PDF and return markdown text as a list of pages."""
    resp = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{encoded}"
        },
        include_image_base64=False,
    )
    return [getattr(page, "markdown", "") for page in resp.pages]

def get_chat_response(chat_prompt: str) -> ChatCompletionResponse:
    return client.chat.complete(
        model="mistral-small-latest", messages=[{"role": "user", "content": chat_prompt}]
    )

async def get_chat_response_async(chat_prompt: str) -> ChatCompletionResponse:
    return await client.chat.complete_async(
        model="mistral-small-latest", messages=[{"role": "user", "content": chat_prompt}]
    )