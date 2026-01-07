from fastapi import FastAPI, Form, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

app = FastAPI()

# Tell FastAPI to look for HTML files in the "templates" folder
templates = Jinja2Templates(directory="templates")


# 1. The Home Page (GET Request)
# This runs when you first open the website. We send empty strings "" to the boxes.
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "original_text": "",  # Empty on start
        "result_text": ""  # Empty on start
    })


# 2. The Redaction Logic (POST Request)
# This runs when you click "Redact Now".
@app.post("/redact", response_class=HTMLResponse)
async def redact_text(
        request: Request,
        user_text: str = Form(...),  # Matches name="user_text" in HTML
        api_key: str = Form(default="")  # Matches name="api_key" in HTML
):
    # --- SIMULATED REDACTION LOGIC ---

    # Check if they are a PRO user
    is_pro = False
    if api_key == "pro_key_123":  # Simple check for the demo
        is_pro = True

    # Perform the redaction
    if is_pro:
        # Pro users get a different message or better processing
        redacted_result = f"[PRO MODE ACTIVE] Redacted: {user_text.replace('John', '[NAME]')}"
    else:
        # Free users logic
        redacted_result = f"[FREE MODE] Redacted: {user_text.replace('John', '****')}"

    # --- RELOAD THE PAGE WITH RESULTS ---
    return templates.TemplateResponse("index.html", {
        "request": request,
        "original_text": user_text,  # Put their original text back so they don't lose it
        "result_text": redacted_result  # Fill the right box with the answer
    })