import re
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


class RedactionService:
    def __init__(self):
        print("Initializing NLP Engine...")

        # Setting up Spacy with the large English model for better accuracy
        nlp_configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
        }

        provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
        nlp_engine = provider.create_engine()

        self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        self.anonymizer = AnonymizerEngine()

        # Loading my custom regex rules
        self.add_dob_recognizer()
        self.add_generic_aussie_catcher()
        self.add_phone_backup_recognizer()

        print("NLP Model & Custom Rules Loaded.")

    def add_dob_recognizer(self):
        # Explicitly catching DD/MM/YYYY or DD-MM-YYYY formats so they don't get mistaken for IDs
        regex = r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="DATE_OF_BIRTH", patterns=[Pattern("dob", regex, 0.95)])
        )

    def add_generic_aussie_catcher(self):
        """
        I'm catching ALL 8-10 digit numbers here.
        I will sort out whether it's Medicare, TFN, or License later in the logic loop.
        """
        regex = r"\b\d{3}[-\s]?\d{3}[-\s]?\d{2,4}\b"
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="AU_GENERIC_ID", patterns=[Pattern("au_id", regex, 0.8)])
        )

    def add_phone_backup_recognizer(self):
        # Backup regex for Aussie mobiles (04...) and landlines just in case Spacy misses them
        regex = r"(?:\b04\d{2}[-\s]?\d{3}[-\s]?\d{3}\b)|(?:\b0[2378][-\s]?\d{4}[-\s]?\d{4}\b)|(?:\b\d{3}[-.]\d{4}\b)"
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="PHONE_NUMBER", patterns=[Pattern("phone", regex, 0.6)])
        )

    def check_context(self, text, start_index, keywords, window=30):
        """
        Helper function to look at the words immediately BEFORE a number.
        Useful for distinguishing License numbers from TFNs.
        """
        snippet = text[max(0, start_index - window):start_index].lower()
        return any(word in snippet for word in keywords)

    def redact_text(self, text: str, entities: list) -> tuple[str, int]:
        if not entities: return text, 0

        # Force the analyzer to check for my custom generic ID and Date tags
        analysis_entities = list(set(entities + ["AU_GENERIC_ID", "PHONE_NUMBER", "DATE_TIME", "DATE_OF_BIRTH"]))

        results = self.analyzer.analyze(
            text=text,
            entities=analysis_entities,
            language='en'
        )

        final_results = []

        for result in results:
            entity_text = text[result.start:result.end]
            clean_digits = "".join(filter(str.isdigit, entity_text))

            detected_type = None

            # --- STEP 1: HARD DATE CHECK (Highest Priority) ---
            # If it has a slash (e.g. 01/01/1990), it is definitely a Date.
            # I accept this immediately to prevent it from falling into the License logic.
            if "/" in entity_text:
                detected_type = "DATE_TIME"

            # --- STEP 2: STRONG ID CHECKS ---
            # If it wasn't a slash-date, I check for specific ID patterns.
            if not detected_type:
                # A. MOBILE PHONE: Starts with 04 and is 10 digits long
                if clean_digits.startswith("04") and len(clean_digits) == 10:
                    detected_type = "PHONE_NUMBER"

                # B. MEDICARE: Starts with 2-6 and is 10 digits long
                elif clean_digits and clean_digits[0] in "23456" and len(clean_digits) == 10:
                    detected_type = "AU_MEDICARE"

                # C. 9-DIGIT CONFLICT (TFN vs License)
                elif len(clean_digits) == 9:
                    # If the word "license" or "driver" is nearby, it's a License
                    if self.check_context(text, result.start, ["license", "licence", "driver", "dl", "vic roads"]):
                        detected_type = "AU_DRIVERS_LICENSE"
                    else:
                        # Otherwise, default to TFN
                        detected_type = "AU_TFN"

            # --- STEP 3: SOFT DATE CHECK ---
            # If it wasn't a Strong ID, but Spacy thinks it's a date (e.g. "Jan 1st"), I trust it.
            if not detected_type and result.entity_type in ["DATE_TIME", "DATE_OF_BIRTH", "DATE"]:
                detected_type = "DATE_TIME"

            # --- STEP 4: WEAK ID CHECK (Fallback) ---
            # If it's an 8-10 digit number and nothing else matched, assume it's a License.
            if not detected_type and (8 <= len(clean_digits) <= 10):
                detected_type = "AU_DRIVERS_LICENSE"

            # --- STEP 5: DEFAULT FALLBACK ---
            # If none of my custom logic applied, use whatever Spacy found originally.
            if not detected_type:
                detected_type = result.entity_type

            # --- FINAL FILTERING ---

            # If it turned out to be a Date, map it to DOB if the user asked for DOBs
            if detected_type == "DATE_TIME" and "DATE_OF_BIRTH" in entities:
                detected_type = "DATE_OF_BIRTH"

            # Only add to results if the user actually requested this entity type
            if detected_type and detected_type in entities:
                result.entity_type = detected_type
                final_results.append(result)

        # mapping the tags to their replacement text
        operators = {
            "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE]"}),
            "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[EMAIL]"}),
            "DATE_OF_BIRTH": OperatorConfig("replace", {"new_value": "[DOB]"}),
            "DATE_TIME": OperatorConfig("replace", {"new_value": "[DATE]"}),
            "AU_MEDICARE": OperatorConfig("replace", {"new_value": "[MEDICARE]"}),
            "AU_TFN": OperatorConfig("replace", {"new_value": "[TFN]"}),
            "AU_DRIVERS_LICENSE": OperatorConfig("replace", {"new_value": "[LICENSE]"}),
            "PERSON": OperatorConfig("replace", {"new_value": "[PERSON]"}),
            "LOCATION": OperatorConfig("replace", {"new_value": "[LOCATION]"}),
            "AU_GENERIC_ID": OperatorConfig("replace", {"new_value": "[ID]"}),
            "DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"})
        }

        anonymized_result = self.anonymizer.anonymize(
            text=text,
            analyzer_results=final_results,
            operators=operators
        )

        return anonymized_result.text, len(final_results)


# Creating the singleton instance
redactor = RedactionService()