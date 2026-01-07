from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


class RedactionService:
    def __init__(self):
        print("Initializing NLP Engine...")

        # 1. SETUP: Explicitly tell Presidio to use the large Spacy model
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
        Australian IDs with MAXIMUM aggression (Score 1.0).
        """
        # 1. Medicare Card (Score 1.0)
        # UPDATED REGEX: uses [- ]+ to allow multiple spaces/dashes
        medicare_regex = r"\b[2-6]\d{3}[- ]+\d{5}[- ]+\d{1}\b"
        medicare_pattern = Pattern(name="au_medicare", regex=medicare_regex, score=1.0)
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="AU_MEDICARE", patterns=[medicare_pattern])
        )

        # 2. Tax File Number (TFN) (Score 1.0)
        tfn_regex = r"\b\d{3}[- ]+\d{3}[- ]+\d{3}\b"
        tfn_pattern = Pattern(name="au_tfn", regex=tfn_regex, score=1.0)
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="AU_TFN", patterns=[tfn_pattern])
        )

        # 3. Australian Driver's License (Context required)
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
        Backup regex for Phones. Score lowered to 0.5 to ensure it loses to Medicare (1.0).
        """
        # Group 1: Aus Mobile (04xx xxx xxx)
        # Group 2: Aus Landline (03 xxxx xxxx)
        # Group 3: Generic (requires dash/dot)
        regex = r"(?:\b04\d{2}[- ]?\d{3}[- ]?\d{3}\b)|(?:\b0[2378][- ]?\d{4}[- ]?\d{4}\b)|(?:\b\d{3}[-.]\d{4}\b)"

        # CHANGED: Score lowered from 0.6 to 0.5
        pattern = Pattern(name="phone_backup_pattern", regex=regex, score=0.5)
        recognizer = PatternRecognizer(supported_entity="PHONE_NUMBER", patterns=[pattern])
        self.analyzer.registry.add_recognizer(recognizer)

    def redact_text(self, text: str, entities: list) -> tuple[str, int]:
        try:
            if not entities:
                return text, 0

            # 1. ANALYSIS STRATEGY:
            # We add Australian tags to the search list NO MATTER WHAT.
            # This ensures "Medicare" (Score 1.0) is detected first, defeating "Phone" (Score 0.5).
            forced_conflicts = ["AU_MEDICARE", "AU_TFN", "AU_DRIVERS_LICENSE"]
            analysis_entities = list(set(entities + forced_conflicts))

            results = self.analyzer.analyze(
                text=text,
                entities=analysis_entities,
                language='en'
            )

            # 2. FILTERING STRATEGY:
            # If the AI found "AU_MEDICARE", but the user didn't ask for it,
            # we simply discard that result.
            # Because "AU_MEDICARE" already won the battle against "PHONE_NUMBER",
            # discarding it leaves the text clean (no redaction).

            final_results = []
            for result in results:
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
                "LOCATION": OperatorConfig("replace", {"new_value": "[LOCATION]"}),
                "DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"})
            }

            # 4. ANONYMIZE
            anonymized_result = self.anonymizer.anonymize(
                text=text,
                analyzer_results=final_results,
                operators=operators
            )

            return anonymized_result.text, len(final_results)

        except Exception as e:
            print(f"CRASH IN REDACTOR: {str(e)}")
            raise e


# Singleton instance
redactor = RedactionService()