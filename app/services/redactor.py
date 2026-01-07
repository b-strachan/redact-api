import re
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


class RedactionService:
    # --- REGEX DEFINITIONS ---
    # Updated to allow "compact" numbers (no spaces)
    # Medicare: Starts 2-6, followed by 9 digits (spaces optional)
    MEDICARE_REGEX = r"\b[2-6]\d{3}[-\s]*\d{5}[-\s]*\d{1}\b"

    # TFN: 9 digits (spaces optional)
    TFN_REGEX = r"\b\d{3}[-\s]*\d{3}[-\s]*\d{3}\b"

    # License: 8-10 digits, NOT starting with 04
    DL_REGEX = r"\b(?!04)\d{8,10}\b"

    def __init__(self):
        print("Initializing NLP Engine...")
        nlp_configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
        }
        provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
        nlp_engine = provider.create_engine()

        self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        self.anonymizer = AnonymizerEngine()

        self.add_legal_recognizer()
        self.add_dob_recognizer()
        self.add_australian_recognizers()
        self.add_phone_backup_recognizer()
        print("NLP Model & Custom Rules Loaded.")

    # --- MATH VALIDATORS (The Magic) ---
    def validate_medicare(self, number_str: str) -> bool:
        """Returns True if the digits pass the Australian Medicare checksum algorithm."""
        digits = [int(d) for d in number_str if d.isdigit()]
        if len(digits) != 10: return False

        # Medicare Algorithm:
        # Weights for first 8 digits: 1, 3, 7, 9, 1, 3, 7, 9
        weights = [1, 3, 7, 9, 1, 3, 7, 9]
        checksum = sum(digits[i] * weights[i] for i in range(8))

        # The remainder % 10 should equal the 9th digit (check digit)
        return (checksum % 10) == digits[8]

    def validate_tfn(self, number_str: str) -> bool:
        """Returns True if digits pass ATO TFN checksum."""
        digits = [int(d) for d in number_str if d.isdigit()]
        if len(digits) != 9: return False

        # TFN Algorithm Weights
        weights = [1, 4, 3, 7, 5, 8, 6, 9, 10]
        checksum = sum(digits[i] * weights[i] for i in range(9))

        return (checksum % 11) == 0

    # ------------------------------------

    def add_legal_recognizer(self):
        regex = r"(?i)\bCase\s?No\.?\s?\d{2}-\d{4}\b"
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="LEGAL_CASE_ID", patterns=[Pattern("case", regex, 0.85)])
        )

    def add_dob_recognizer(self):
        regex = r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="DATE_OF_BIRTH", patterns=[Pattern("dob", regex, 0.95)])
        )

    def add_australian_recognizers(self):
        # We set loose regexes here, and tighten them with Math in redact_text()
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="AU_MEDICARE", patterns=[Pattern("med", self.MEDICARE_REGEX, 1.0)])
        )
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="AU_TFN", patterns=[Pattern("tfn", self.TFN_REGEX, 1.0)])
        )
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(
                supported_entity="AU_DRIVERS_LICENSE",
                patterns=[Pattern("dl", self.DL_REGEX, 0.6)],
                context=["licence", "license", "driver", "dl", "vic roads", "rms"]
            )
        )

    def add_phone_backup_recognizer(self):
        regex = r"(?:\b04\d{2}[-\s]?\d{3}[-\s]?\d{3}\b)|(?:\b0[2378][-\s]?\d{4}[-\s]?\d{4}\b)|(?:\b\d{3}[-.]\d{4}\b)"
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="PHONE_NUMBER", patterns=[Pattern("phone", regex, 0.5)])
        )

    def redact_text(self, text: str, entities: list) -> tuple[str, int]:
        if not entities: return text, 0

        forced_conflicts = ["AU_MEDICARE", "AU_TFN", "AU_DRIVERS_LICENSE"]
        analysis_entities = list(set(entities + forced_conflicts))

        results = self.analyzer.analyze(text=text, entities=analysis_entities, language='en')

        final_results = []
        for result in results:
            entity_text = text[result.start:result.end]
            clean_digits = "".join(filter(str.isdigit, entity_text))

            # --- ADVANCED MATH VALIDATION ---

            # CHECK 1: Is this mathematically a Medicare Card?
            if self.validate_medicare(entity_text):
                # If it matches the math, IT IS MEDICARE. Period.
                if "AU_MEDICARE" in entities:
                    result.entity_type = "AU_MEDICARE"
                    final_results.append(result)
                continue  # If valid medicare but unchecked, skip (don't let it become license)

            # CHECK 2: Is this mathematically a TFN?
            if self.validate_tfn(entity_text):
                if "AU_TFN" in entities:
                    result.entity_type = "AU_TFN"
                    final_results.append(result)
                continue  # If valid TFN but unchecked, skip.

            # --- FALLBACKS (If math failed) ---

            # If it failed Math checks, it is NOT Medicare/TFN.
            # It might be a License or Phone.

            if result.entity_type == "AU_DRIVERS_LICENSE":
                # Only allow license if it DOESN'T look like a TFN/Medicare (which we already filtered)
                # and isn't a mobile (04)
                if "AU_DRIVERS_LICENSE" in entities:
                    final_results.append(result)

            elif result.entity_type == "PHONE_NUMBER":
                # Safety: Check if it looks like a License
                if re.search(self.DL_REGEX, entity_text):
                    if "AU_DRIVERS_LICENSE" in entities:
                        result.entity_type = "AU_DRIVERS_LICENSE"
                        final_results.append(result)
                elif "PHONE_NUMBER" in entities:
                    final_results.append(result)

            # Handle standard entities (Names, emails, etc)
            elif result.entity_type in entities and result.entity_type not in ["AU_MEDICARE", "AU_TFN",
                                                                               "AU_DRIVERS_LICENSE", "PHONE_NUMBER"]:
                final_results.append(result)

        # 4. ANONYMIZE
        operators = {
            "LEGAL_CASE_ID": OperatorConfig("replace", {"new_value": "[CASE_ID]"}),
            "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE]"}),
            "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[EMAIL]"}),
            "DATE_OF_BIRTH": OperatorConfig("replace", {"new_value": "[DOB]"}),
            "DATE_TIME": OperatorConfig("replace", {"new_value": "[DATE]"}),
            "AU_MEDICARE": OperatorConfig("replace", {"new_value": "[MEDICARE]"}),
            "AU_TFN": OperatorConfig("replace", {"new_value": "[TFN]"}),
            "AU_DRIVERS_LICENSE": OperatorConfig("replace", {"new_value": "[LICENSE]"}),
            "PERSON": OperatorConfig("replace", {"new_value": "[PERSON]"}),
            "LOCATION": OperatorConfig("replace", {"new_value": "[LOCATION]"}),
            "DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"})
        }

        anonymized_result = self.anonymizer.anonymize(
            text=text,
            analyzer_results=final_results,
            operators=operators
        )

        return anonymized_result.text, len(final_results)


redactor = RedactionService()