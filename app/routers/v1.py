import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from app.auth import get_api_key
from app.services.redactor import redactor
from app.schemas import RedactRequest, RedactResponse


router = APIRouter(prefix="/v1")


@router.post("/redact/text", response_model=RedactResponse, dependencies=[Depends(get_api_key)])
async def redact_text(request: RedactRequest):
    """
    Redacts text based on the provided list of entities.
    """
    try:
    
        redacted_text, count = redactor.redact_text(request.text, request.entities_to_redact)

        return RedactResponse(
            original_length=len(request.text),
            redacted_text=redacted_text,
            items_redacted=count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/redact/file", dependencies=[Depends(get_api_key)])
async def redact_file(
        file: UploadFile = File(...),
        # We accept the entities as a JSON string from the form
        entities_to_redact: str = Form(
            '["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "AU_MEDICARE", "AU_TFN", "AU_DRIVERS_LICENSE", "DATE_OF_BIRTH"]')
):
    """
    Redacts an uploaded file (Text/CSV).
    """
    try:
        # 1. Read the file
        content = await file.read()

        # Simple decoding (assuming UTF-8 text file)
        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File must be a valid text file (UTF-8).")

        # 2. Parse the list of entities from the string format
        try:
            entities_list = json.loads(entities_to_redact)
        except json.JSONDecodeError:
            # Fallback if parsing fails
            entities_list = ["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "AU_MEDICARE"]

      

        redacted_text, count = redactor.redact_text(text_content, entities_list)

        return {
            "filename": file.filename,
            "original_length": len(text_content),
            "redacted_content": redacted_text,
            "items_redacted": count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
