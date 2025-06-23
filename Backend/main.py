import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from app.extract_temp import extract_data
from app.fill_form import fill_pdf_form, fill_pdf_from_bytes
from app.extract import process_files_async
from dotenv import load_dotenv
import tempfile
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/retrieve_pdf_ocr_results")
async def retrieve_pdf_ocr_results(file: UploadFile = File(...)):
    pdf_bytes = await file.read()
    result = extract_data(pdf_bytes)
    output = fill_pdf_form(result["fields"])
    return {"extracted": result["fields"], "output": output}


@app.post("/process_pdfs/")
async def process_pdfs(
    referral_pdf: UploadFile = File(...), pa_pdf: UploadFile = File(...)
):
    # Read file bytes
    referral_bytes = await referral_pdf.read()
    pa_bytes = await pa_pdf.read()

    # Return filled PDF file as a downloadable response
    return await process_files_async(pa_pdf_bytes=pa_bytes, referral_pdf_bytes=referral_bytes)
