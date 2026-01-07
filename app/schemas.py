from pydantic import BaseModel, Field
from typing import List, Optional

# Request model for text redaction
class RedactRequest(BaseModel):
    # Updated example to be Australian-relevant
    text: str = Field(..., example="My name is John Doe, my TFN is 123 456 789 and I live in Geelong.")
    entities_to_redact: List[str] = Field(
        # These are the standard Presidio entity names + Your Custom Aussie ones
        default=[
            "PERSON",
            "PHONE_NUMBER",
            "EMAIL_ADDRESS",
            "AU_MEDICARE",
            "AU_TFN",
            "AU_DRIVERS_LICENSE",
            "LOCATION",
            "DATE_TIME",
            "DATE_OF_BIRTH"
        ],
        description="List of entity types to redact"
    )

# Response model
class RedactResponse(BaseModel):
    original_length: int
    redacted_text: str
    items_redacted: int  # <--- Restored this name so main.py doesn't crash