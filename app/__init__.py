from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import nlp_engine
from presidio_anonymizer import AnonymizerEngine


def __init__(self):

    self.add_legal_recognizer()
    self.add_phone_backup_recognizer()
    self.add_dob_recognizer()

   
    self.add_australian_recognizers()

def __init__(self):
    self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
    self.anonymizer = AnonymizerEngine()


    self.add_legal_recognizer()
    self.add_phone_backup_recognizer()
    self.add_dob_recognizer()  # <--- Add this line!

    print("NLP Model & Custom Rules Loaded.")

def __init__(self):
    print("Loading NLP Model...")
    self.analyzer = AnalyzerEngine()
    self.anonymizer = AnonymizerEngine()
