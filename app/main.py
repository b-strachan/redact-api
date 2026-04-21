from fastapi import FastAPI, Form, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from typing import List, Optional

# Import the AI engines
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Initialize the engines once (when server starts)
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Render the empty form on first load
    return templates.TemplateResponse("index.html", {
        "request": request,
        "original_text": "",
        "result_text": ""
    })


@app.post("/redact", response_class=HTMLResponse)
async def redact_text(
        request: Request,
        user_text: str = Form(...),
        entities: List[str] = Form(default=[]),  # Gets the checkboxes!
        api_key: str = Form(default="")
):
    # 1. CHECK FOR PRO ACCESS
    is_pro = False
    if api_key in VALID_KEYS:
        is_pro = True

    # 2. CONFIGURE ENTITIES
    # If the user selected nothing, default to standard PII
    if not entities:
        entities = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"]

    # 3. RUN ANALYSIS (The "Brain")
    # This scans the text for the selected entities
    results = analyzer.analyze(
        text=user_text,
        entities=entities,
        language='en'
    )

    # 4. RUN ANONYMIZATION (The "Redactor")
    # This replaces the found entities with <REDACTED>
    anonymized_result = anonymizer.anonymize(
        text=user_text,
        analyzer_results=results
    )

    final_text = anonymized_result.text

    # 5. (OPTIONAL) ADD PRO BADGE
    # If they are pro, maybe we show them something special?
    if is_pro:
        pass  # Logic for pro users (e.g. handle images, PDFs, etc.)
    else:
        # Free Tier Limitation: Truncate very long text?
        if len(final_text) > 1000:
            final_text = final_text[:1000] + "\n\n[TEXT TRUNCATED - SUBSCRIBE FOR UNLIMITED]"

    # 6. RETURN RESULTS
    return templates.TemplateResponse("index.html", {
        "request": request,
        "original_text": user_text,
        "result_text": final_text
    })
