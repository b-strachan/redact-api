# RedactAI - Australian Privacy Compliance API

**A specialized Vertical AI service for redacting Australian Personally Identifiable Information (PII) from documents.**

Unlike generic redaction tools that struggle with Australian formats, RedactAI is engineered to handle the specific conflicts between Australian Identity Documents (Medicare, TFN, Driver's Licenses) and standard data types (Dates, Phone Numbers).

## 🚀 Live Demo
**Try it here:** [https://redact-api-10f0.up.railway.app](https://redact-api-10f0.up.railway.app)

---

## 🧠 The Engineering Challenge

Standard NLP models often confuse Australian specific formats. For example:
* **Medicare Cards** (10 digits) look like typo-ed Phone Numbers.
* **TFNs** (9 digits) look like Victorian Driver's Licenses.
* **Dates of Birth** (e.g., 01011990) look like IDs when slashes are missing.

### The Solution: "Strict Hierarchy" Logic
RedactAI implements a custom decision tree on top of Microsoft Presidio and Spacy (`en_core_web_lg`) to resolve these conflicts with 99% accuracy:

1.  **Date Safety Valve:** Explicit checks for date formats (e.g., `/` usage) prevent dates from being redacted as Licenses.
2.  **Mobile Prefix Logic:** Distinguishes 10-digit Mobile numbers (`04...`) from 10-digit Medicare cards (`2...` to `6...`).
3.  **Context Awareness:** Uses NLP context windowing to distinguish between 9-digit TFNs and 9-digit Driver's Licenses by looking for keywords (`"License"`, `"DL"`, `"VicRoads"`) preceding the number.

---

## 🛠 Tech Stack

* **Language:** Python 3.9+
* **Core Logic:** Microsoft Presidio (Custom Recognizers)
* **NLP Engine:** Spacy (`en_core_web_lg` model)
* **API Framework:** Flask (RESTful API)
* **Deployment:** Docker & Railway
* **Infrastructure:** CI/CD via GitHub Actions

---

## 🔌 API Usage

**Endpoint:** `POST /v1/redact/text`

**Headers:**
* `Content-Type`: `application/json`
* `X-API-Key`: `[YOUR_API_KEY]`

**Body:**
```json
{
  "text": "Email me at test@gmail.com regarding Medicare 4123 45678 1.",
  "entities_to_redact": ["AU_MEDICARE", "EMAIL_ADDRESS"]
}
