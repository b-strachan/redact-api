from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import nlp_engine
from presidio_anonymizer import AnonymizerEngine


def __init__(self):
    # ... (previous setup code) ...

    self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
    self.anonymizer = AnonymizerEngine()

    # Load all your custom rules
    self.add_legal_recognizer()
    self.add_phone_backup_recognizer()
    self.add_dob_recognizer()  # <--- Add this line!

    print("NLP Model & Custom Rules Loaded.")

def __init__(self):
    print("Loading NLP Model...")
    self.analyzer = AnalyzerEngine()
    self.anonymizer = AnonymizerEngine()

    # --- Add Custom "Niche" Logic Here ---
    # Example: Detect Legal Case Numbers like "Case No. 22-9983"
    self.add_custom_recognizer(
        pattern_name="LEGAL_CASE_ID",
        regex_pattern=r"(?i)\bCase\s?No\.?\s?\d{2}-\d{4}\b"
    )
    print("NLP Model & Custom Rules Loaded.")