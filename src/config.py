from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
QUESTIONNAIRE_PATH = DATA_DIR / "questionnaire.json"
ASSESSMENTS_DIR = DATA_DIR / "assessments"