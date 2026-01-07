from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


class RedactionService:
    def __init__(self):
        print("Initializing NLP Engine...")

        # 1. SETUP: Explicitly tell Presidio to use the model we downloaded
        nlp_configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
        }

        provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
        nlp_engine = provider.create_engine()

        self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        self.anonymizer = AnonymizerEngine()

        # 2. LOAD CUSTOM RULES
        self.add_legal_recognizer()
        self.add_dob_recognizer()
        self.add_australian_recognizers()

        # Load phone backup LAST so it doesn't override specific rules
        self.add_phone_backup_recognizer()

        print("NLP Model & Custom Rules Loaded.")

    def add_legal_recognizer(self):
        """Detects Legal Case Numbers (e.g., Case No. 24-1001)"""
        regex = r"(?i)\bCase\s?No\.?\s?\d{2}-\d{4}\b"
        pattern = Pattern(name="legal_case_pattern", regex=regex, score=0.85)
        recognizer = PatternRecognizer(supported_entity="LEGAL_CASE_ID", patterns=[pattern])
        self.analyzer.registry.add_recognizer(recognizer)

    def add_dob_recognizer(self):
        """Detects Date of Birth (Score 0.95 to beat generic dates)"""
        regex = r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"
        pattern = Pattern(name="dob_pattern", regex=regex, score=0.95)
        recognizer = PatternRecognizer(supported_entity="DATE_OF_BIRTH", patterns=[pattern])
        self.analyzer.registry.add_recognizer(recognizer)

    def add_australian_recognizers(self):
        """
        Adds support for Australian IDs with MAXIMUM aggression (Score 1.0).
        This ensures Medicare/TFN are never mistaken for phone numbers.
        """
        # 1. Medicare Card (Score 1.0)
        # Matches: 2123 45678 1
        medicare_regex = r"\b[2-6]\d{3}[- ]?\d{5}[- ]?\d{1}\b"
        medicare_pattern = Pattern(name="au_medicare", regex=medicare_regex, score=1.0)
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="AU_MEDICARE", patterns=[medicare_pattern])
        )

        # 2. Tax File Number (TFN) (Score 1.0)
        # Matches: 123 456 789
        tfn_regex = r"\b\d{3}[- ]?\d{3}[- ]?\d{3}\b"
        tfn_pattern = Pattern(name="au_tfn", regex=tfn_regex, score=1.0)
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="AU_TFN", patterns=[tfn_pattern])
        )

        # 3. Australian Driver's License
        # Matches 8-10 digits IF the word 'license'/'dl' is nearby
        dl_regex = r"\b\d{8,10}\b"
        dl_pattern = Pattern(name="au_drivers_license", regex=dl_regex, score=0.6)
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(
                supported_entity="AU_DRIVERS_LICENSE",
                patterns=[dl_pattern],
                context=["licence", "license", "driver", "dl", "vic roads", "rms"]
            )
        )

    def add_phone_backup_recognizer(self):
        """
        Backup regex for Phones, tuned to NOT match Medicare.
        """
        # Group 1: Aus Mobile (Must start with 04) -> 0412 345 678
        # Group 2: Aus Landline (Must start with 02/03/07/08) -> (03) 5555 1234
        # Group 3: US/Generic (Strict XXX-XXXX format) -> 555-1234

        regex = r"(?:\b04\d{2}[- ]?\d{3}[- ]?\d{3}\b)|(?:\b0[2378][- ]?\d{4}[- ]?\d{4}\b)|(?:\b\d{3}[-.]\d{4}\b)"

        pattern = Pattern(name="phone_backup_pattern", regex=regex, score=0.6)
        recognizer = PatternRecognizer(supported_entity="PHONE_NUMBER", patterns=[pattern])
        self.analyzer.registry.add_recognizer(recognizer)

    def redact_text(self, text: str, entities: list) -> tuple[str, int]:
        try:
            if not entities:
                return text, 0

            # 1. ANALYSIS STRATEGY:
            # We must ALWAYS look for the specific Australian rules (Medicare, TFN, etc).
            # Why? Because if we don't, the "Dumb" Phone rule will mistake a Medicare card
            # for a Phone Number.
            # So we force the AI to identify "Medicare" first (Score 1.0), which prevents
            # "Phone" (Score 0.6) from claiming it.

            forced_conflicts = ["AU_MEDICARE", "AU_TFN", "AU_DRIVERS_LICENSE"]
            analysis_entities = list(set(entities + forced_conflicts))

            results = self.analyzer.analyze(
                text=text,
                entities=analysis_entities,
                language='en'
            )

            # 2. FILTERING STRATEGY:
            # Now we have the results. Some might be "AU_MEDICARE" even though the user
            # didn't check the box. We filter those out NOW.

            final_results = []
            for result in results:
                # Only keep the result if the user actually asked for this entity type
                if result.entity_type in entities:
                    final_results.append(result)

            # 3. LABELS
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
                "DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"})
            }

            # 4. ANONYMIZE (Using only the filtered results)
            anonymized_result = self.anonymizer.anonymize(
                text=text,
                analyzer_results=final_results,
                operators=operators
            )

            return anonymized_result.text, len(final_results)

        except Exception as e:
            print(f"CRASH IN REDACTOR: {str(e)}")
            raise e
# Create singleton instance
redactor = RedactionService()