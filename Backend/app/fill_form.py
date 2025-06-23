
import io
from pdfrw import PdfReader, PdfWriter, PdfDict

def fill_pdf_form(structured_text: str) -> dict:
    return {"message": "PDF would be filled here.", "data": structured_text}

def fill_pdf_from_bytes(input_pdf_bytes: bytes, output_pdf_path: str, data: dict):
    template_pdf = PdfReader(io.BytesIO(input_pdf_bytes))
    for page in template_pdf.pages:
        annotations = page.Annots
        if annotations:
            for annotation in annotations:
                if annotation.Subtype == "/Widget" and annotation.T:
                    key = annotation.T[1:-1]  # strip parentheses
                    if key in data:
                        annotation.update(
                            PdfDict(V=f"{data[key]}")
                        )
                        annotation.update(PdfDict(Ff=1))  # read-only (optional)
    PdfWriter().write(output_pdf_path, template_pdf)
