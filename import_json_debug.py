from pathlib import Path
import json

def load_questionnaire(path):
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Questionnaire introuvable: {path}")

    raw = path.read_text(encoding="utf-8", errors="replace")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        start = max(0, e.pos - 120)
        end = min(len(raw), e.pos + 120)
        snippet = raw[start:end]
        raise ValueError(
            f"Erreur JSON à la ligne {e.lineno}, colonne {e.colno}, position {e.pos}\n"
            f"Extrait:\n{snippet}"
        )

    if not isinstance(data, dict):
        raise TypeError("Le JSON doit être un objet racine")

    if "questions" not in data:
        raise ValueError("Le champ 'questions' est manquant")

    questions = data["questions"]

    if not isinstance(questions, list):
        raise TypeError("'questions' doit être une liste")
    return data

questions = load_questionnaire("data/questionnaire.json")
print(f"{len(questions)} questions chargées")
