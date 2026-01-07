import re
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


class RedactionService:
    # Regex Definitions
    # Medicare: 2-6 start, 10 digits total, allows spaces/dashes
    MEDICARE_REGEX = r"\b[2-6]\d{3}[-\s]+\d{5}[-\s]+\d{1}\b"
    # TFN: 9 digits, allows spaces/dashes
    TFN_REGEX = r"\b\d{3}[-\s]+\d{3}[-\s]+\d{3}\b"

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

        # Load Rules
        self.add_legal_recognizer()
        self.add_dob_recognizer()
        self.add_australian_recognizers()
        self.add_phone_backup_recognizer()

        print("NLP Model & Custom Rules Loaded.")

    def add_legal_recognizer(self):
        regex = r"(?i)\bCase\s?No\.?\s?\d{2}-\d{4}\b"
        pattern = Pattern(name="legal_case_pattern", regex=regex, score=0.85)
        recognizer = PatternRecognizer(supported_entity="LEGAL_CASE_ID", patterns=[pattern])
        self.analyzer.registry.add_recognizer(recognizer)

    def add_dob_recognizer(self):
        regex = r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"
        pattern = Pattern(name="dob_pattern", regex=regex, score=0.95)
        recognizer = PatternRecognizer(supported_entity="DATE_OF_BIRTH", patterns=[pattern])
        self.analyzer.registry.add_recognizer(recognizer)

    def add_australian_recognizers(self):
        # 1. Medicare (Score 1.0)
        medicare_pattern = Pattern(name="au_medicare", regex=self.MEDICARE_REGEX, score=1.0)
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="AU_MEDICARE", patterns=[medicare_pattern])
        )

        # 2. TFN (Score 1.0)
        tfn_pattern = Pattern(name="au_tfn", regex=self.TFN_REGEX, score=1.0)
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="AU_TFN", patterns=[tfn_pattern])
        )

        # 3. License (Score 0.6)
        # CRITICAL FIX: (?!04) ensures we don't match Mobile Numbers
        dl_regex = r"\b(?!04)\d{8,10}\b"

        dl_pattern = Pattern(name="au_drivers_license", regex=dl_regex, score=0.6)
        self.analyzer.registry.add_recognizer(
            PatternRecognizer(
                supported_entity="AU_DRIVERS_LICENSE",
                patterns=[dl_pattern],
                context=["licence", "license", "driver", "dl", "vic roads", "rms"]
            )
        )

    def add_phone_backup_recognizer(self):
        # Score 0.5 (Lower than License 0.6, but since License excludes 04, Phone wins 04)
        regex = r"(?:\b04\d{2}[-\s]?\d{3}[-\s]?\d{3}\b)|(?:\b0[2378][-\s]?\d{4}[-\s]?\d{4}\b)|(?:\b\d{3}[-.]\d{4}\b)"
        pattern = Pattern(name="phone_backup_pattern", regex=regex, score=0.5)
        recognizer = PatternRecognizer(supported_entity="PHONE_NUMBER", patterns=[pattern])
        self.analyzer.registry.add_recognizer(recognizer)

    def redact_text(self, text: str, entities: list) -> tuple[str, int]:
        try:
            if not entities:
                return text, 0

            # 1. Force Aussie Checks
            forced_conflicts = ["AU_MEDICARE", "AU_TFN", "AU_DRIVERS_LICENSE"]
            analysis_entities = list(set(entities + forced_conflicts))

            results = self.analyzer.analyze(
                text=text,
                entities=analysis_entities,
                language='en'
            )

            # 2. Safety Valve Filter
            final_results = []
            for result in results:

                # Safety Valve: If it's a Phone Number, ensure it's not actually Medicare
                if result.entity_type == "PHONE_NUMBER":
                    entity_text = text[result.start:result.end]
                    if re.search(self.MEDICARE_REGEX, entity_text):
                        if "AU_MEDICARE" not in entities:
                            continue

                            # Standard Filter
                if result.entity_type in entities:
                    final_results.append(result)

            # 3. Labels
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

        except Exception as e:
            print(f"CRASH IN REDACTOR: {str(e)}")
            raise e


redactor = RedactionService()