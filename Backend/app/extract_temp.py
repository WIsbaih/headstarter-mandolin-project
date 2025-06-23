import os
import base64
from dotenv import load_dotenv
from mistralai import Mistral

load_dotenv()
client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

def extract_data(pdf_bytes: bytes) -> dict:
    # Encode PDF to base64
    encoded = base64.b64encode(pdf_bytes).decode("utf-8")
    
    ocr_resp = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{encoded}"
        },
        include_image_base64=False
    )
    
    # Debug: print raw OCR response to understand its structure
    #print("OCR response:", ocr_resp)
    
    # Extract markdown text from each page
    all_text = "\n\n".join(
        getattr(page, "markdown", "")
        for page in getattr(ocr_resp, "pages", [])
    )

    #print("All text:", all_text)

    # Build prompt for AI to extract structured data
    prompt = (
        "Extract the following fields from this medical referral document as JSON:\n"
        "- patient_name\n"
        "- date_of_birth\n"
        "- diagnosis\n"
        "- cpt_codes (if any)\n\n"
        f"Document Text:\n{all_text}"
    )
    
    chat_resp = client.chat.complete(
        model="mistral-large-latest",
        messages=[{"role": "user", "content": prompt}]
    )
    
    return {
        "raw_text": all_text,
        "fields": chat_resp.choices[0].message.content
    }
