from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


class RedactionService:
    def __init__(self):
        print("Initializing NLP Engine...")

        # 1. SETUP: Configure Spacy
        nlp_configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
        }

        provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
        nlp_engine = provider.create_engine()

        self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        self.anonymizer = AnonymizerEngine()

        # 2. CUSTOM RULES
        self.add_legal_recognizer()
        self.add_phone_backup_recognizer()
        self.add_dob_recognizer()

        print("NLP Model & Custom Rules Loaded.")

    def add_legal_recognizer(self):
        regex = r"(?i)\bCase\s?No\.?\s?\d{2}-\d{4}\b"
        pattern = Pattern(name="legal_case_pattern", regex=regex, score=0.85)
        recognizer = PatternRecognizer(supported_entity="LEGAL_CASE_ID", patterns=[pattern])
        self.analyzer.registry.add_recognizer(recognizer)

    def add_phone_backup_recognizer(self):
        regex = r"(?:\b04\d{2}[- ]?\d{3}[- ]?\d{3}\b)|(?:\b\d{3}[-.]?\d{4}\b)|(?:\b0[2378][- ]?\d{4}[- ]?\d{4}\b)"
        pattern = Pattern(name="phone_backup_pattern", regex=regex, score=0.6)
        recognizer = PatternRecognizer(supported_entity="PHONE_NUMBER", patterns=[pattern])
        self.analyzer.registry.add_recognizer(recognizer)

    def add_dob_recognizer(self):
        # High score (0.95) to override standard Date detection
        regex = r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"
        pattern = Pattern(name="dob_pattern", regex=regex, score=0.95)
        recognizer = PatternRecognizer(supported_entity="DATE_OF_BIRTH", patterns=[pattern])
        self.analyzer.registry.add_recognizer(recognizer)

    def redact_text(self, text: str, entities: list) -> tuple[str, int]:
        try:
            # 3. FORCE OVERRIDE: Ignore what the user sent, force these entities
            # We add DATE_OF_BIRTH and DATE_TIME to ensure they are caught
            analysis_entities = list(set(entities + ["LEGAL_CASE_ID", "PHONE_NUMBER", "DATE_OF_BIRTH", "DATE_TIME"]))

            results = self.analyzer.analyze(
                text=text,
                entities=analysis_entities,
                language='en'
            )

            operators = {
                "LEGAL_CASE_ID": OperatorConfig("replace", {"new_value": "[CASE_ID]"}),
                "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE]"}),
                "DATE_OF_BIRTH": OperatorConfig("replace", {"new_value": "[DOB]"}),
                "DATE_TIME": OperatorConfig("replace", {"new_value": "[DATE]"}),
                "DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"})
            }

            anonymized_result = self.anonymizer.anonymize(
                text=text,
                analyzer_results=results,
                operators=operators
            )

            return anonymized_result.text, len(results)

        except Exception as e:
            print(f"CRASH: {str(e)}")
            raise e


redactor = RedactionService()