from fastapi import APIRouter, Depends, UploadFile, File
from app.schemas import RedactRequest, RedactResponse
from app.auth import get_api_key
from app.services.redactor import redactor

router = APIRouter(
    prefix="/v1",
    tags=["Redaction"],
    dependencies=[Depends(get_api_key)]  # Locks all these routes behind the API Key
)


@router.post("/redact/text", response_model=RedactResponse)
async def redact_text_string(request: RedactRequest):
    """
    Redacts sensitive PII from a raw text string.
    """
    clean_text, count = redactor.redact_text(request.text, request.entities_to_redact)

    return RedactResponse(
        original_length=len(request.text),
        redacted_text=clean_text,
        items_redacted=count
    )


@router.post("/redact/file")
async def redact_file(file: UploadFile = File(...)):
    """
    Redacts a text file. (Expand this later to handle PDF/Docx processing).
    """
    content = await file.read()
    text_content = content.decode("utf-8")

    # Default redaction for files
    clean_text, count = redactor.redact_text(text_content, ["EMAIL", "PHONE"])

    return {
        "filename": file.filename,
        "redacted_content": clean_text
    }