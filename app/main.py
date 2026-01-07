from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routers import v1
import os

# UPDATED BRANDING
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
        "email": "support@redactionai.com",
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