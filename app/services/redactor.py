import re
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


class RedactionService:
    def __init__(self):
        print("Initializing NLP Engine...")

        # 1. SETUP SPACY
        nlp_configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
        }

        provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
        nlp_engine = provider.create_engine()

        self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        self.anonymizer = AnonymizerEngine()

        # 2. LOAD RULES
        self.add_dob_recognizer()
        self.add_generic_aussie_catcher()
        self.add_phone_backup_recognizer()

        print("NLP Model & Custom Rules Loaded.")

    def add_dob_recognizer(self):
        regex = r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="DATE_OF_BIRTH", patterns=[Pattern("dob", regex, 0.95)])
        )

    def add_generic_aussie_catcher(self):
        """
        Catches ALL 8-10 digit numbers.
        We assign the correct label in the logic loop below.
        """
        regex = r"\b\d{3}[-\s]?\d{3}[-\s]?\d{2,4}\b"
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="AU_GENERIC_ID", patterns=[Pattern("au_id", regex, 0.8)])
        )

    def add_phone_backup_recognizer(self):
        regex = r"(?:\b04\d{2}[-\s]?\d{3}[-\s]?\d{3}\b)|(?:\b0[2378][-\s]?\d{4}[-\s]?\d{4}\b)|(?:\b\d{3}[-.]\d{4}\b)"
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="PHONE_NUMBER", patterns=[Pattern("phone", regex, 0.6)])
        )

    def check_context(self, text, start_index, keywords, window=30):
        """
        Looks at the text immediately BEFORE the number to see if a keyword exists.
        """
        snippet = text[max(0, start_index - window):start_index].lower()
        return any(word in snippet for word in keywords)

    def redact_text(self, text: str, entities: list) -> tuple[str, int]:
        if not entities: return text, 0

        # FORCE CHECK for our generic ID catcher
        analysis_entities = list(set(entities + ["AU_GENERIC_ID", "PHONE_NUMBER", "DATE_TIME"]))

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

            # --- 0. DATE SAFETY CHECK (The Fix) ---
            # If it has slashes, it's a Date. Period.
            # This prevents "23/07/2000" (8 digits) from being seen as a License.
            if "/" in entity_text:
                detected_type = "DATE_TIME"
            if ":" in entity_text:
                detected_type = "DATE_TIME"

            # 1. MOBILE PHONE: Starts with 04, Length 10
            elif clean_digits.startswith("04") and len(clean_digits) == 10:
                detected_type = "PHONE_NUMBER"

            # 2. MEDICARE: Starts with 2-6, Length 10
            elif clean_digits and clean_digits[0] in "23456" and len(clean_digits) == 10:
                detected_type = "AU_MEDICARE"

            # 3. THE 9-DIGIT CONFLICT (TFN vs License)
            elif len(clean_digits) == 9:
                # Check context for "License" words
                if self.check_context(text, result.start, ["license", "licence", "driver", "dl", "vic roads"]):
                    detected_type = "AU_DRIVERS_LICENSE"
                else:
                    detected_type = "AU_TFN"

            # 4. LICENSE: Length 8 or 10 (Fallback)
            elif 8 <= len(clean_digits) <= 10:
                detected_type = "AU_DRIVERS_LICENSE"

            # 5. KEEP ORIGINAL
            else:
                detected_type = result.entity_type

            # --- FILTERING ---
            # If detected as DATE_TIME, map it to what the user asked for (DOB or Date)
            if detected_type == "DATE_TIME":
                if "DATE_OF_BIRTH" in entities:
                    result.entity_type = "DATE_OF_BIRTH"
                    final_results.append(result)
                elif "DATE_TIME" in entities:
                    result.entity_type = "DATE_TIME"
                    final_results.append(result)

            elif detected_type and detected_type in entities:
                result.entity_type = detected_type
                final_results.append(result)

        # LABELS
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


redactor = RedactionService()