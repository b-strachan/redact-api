from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routers import v1
import os

from fastapi import FastAPI, Header, HTTPException
from typing import Optional

app = FastAPI()

# MVP: Hardcode keys here for now.
# Later, you will load this from a Database or Environment Variable.
VALID_PRO_KEYS = {
    "pro_key_bailey_001": "client_A",
    "pro_key_test_123": "test_user"
}


@app.post("/redact")
async def redact_text(
        data: dict,
        redact_api_key: Optional[str] = Header(None)  # Automatically looks for 'x-api-key' in headers
):
    # 1. Check if the user provided a key and if it's valid
    is_pro_user = False
    if redact_api_key and redact_api_key in VALID_PRO_KEYS:
        is_pro_user = True

    # 2. Logic Splitting
    if is_pro_user:
        # --- PRO LOGIC ---
        # No limits, better model, faster processing
        return {
            "status": "success",
            "tier": "PRO",
            "redacted_text": perform_advanced_redaction(data['text'])
        }
    else:
        # --- FREE LOGIC ---
        # Apply limits (e.g., max 500 chars) or mask less data
        if len(data['text']) > 500:
            return {"error": "Free tier limited to 500 characters. Please subscribe."}

        return {
            "status": "success",
            "tier": "FREE",
            "redacted_text": perform_basic_redaction(data['text'])
        }


def perform_advanced_redaction(text):
    # Your complex logic here
    return "Redacted PRO: " + text


def perform_basic_redaction(text):
    # Your basic logic here
    return "Redacted Basic: " + text

description = """
RedactionAI helps you automatically strip sensitive Australian PII data from text and files. 🇦🇺

## Features
* **Australian Logic:** Specifically tuned for Medicare, TFN, and AU Drivers Licenses.
* **Conflict Resolution:** Distinguishes between Mobile Numbers (04...) and Medicare Cards.
* **Smart Dates:** Context-aware date redaction.

## How to use
1. **Get an API Key:** (https://buy.stripe.com/14AcMYci9bZiexua8mak001)
2. **Authenticate:** Use the `Redact-API-Key` header.
3. **Send Data:** Post JSON to `/v1/redact/text`.
"""

app = FastAPI(
    title="RedactionAI API",
    description=description,
    version="1.0.0",
    contact={
        "name": "RedactionAI Support",
        "email": "bailey.r.strachan@gmail.com",
    },
    docs_url="/docs",
    redoc_url="/redoc"
)

# Mount the static directory
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(v1.router)

# Serve the HTML file on the homepage
@app.get("/")
def read_root():
    return FileResponse('app/static/index.html')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)