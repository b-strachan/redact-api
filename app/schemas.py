from pydantic import BaseModel, Field
from typing import List, Optional

# Request model for text redaction
class RedactRequest(BaseModel):
    text: str = Field(..., example="My name is John Doe and my phone is 555-0199.")
    entities_to_redact: List[str] = Field(
        # These are the standard Presidio entity names
        default=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "US_SSN", "LOCATION", "DATE_TIME", "DOB_DATE"],
        description="List of entity types to redact"
    )

# Response model
class RedactResponse(BaseModel):
    original_length: int
    redacted_text: str
    items_redacted: int