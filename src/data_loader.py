import json
from pathlib import Path
from typing import Any, Dict, List
import streamlit as st

def load_questionnaire(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        st.error(f"Questionnaire introuvable: {path}")
        st.stop()

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        st.error("Le fichier questionnaire.json doit contenir un objet JSON racine.")
        st.stop()

    questions = data.get("questions")
    if not isinstance(questions, list):
        st.error("Le champ 'questions' doit contenir une liste de questions.")
        st.stop()

    required_fields = {"question_id", "question_label", "question_type", "type_reponse"}
    for item in questions:
        if not isinstance(item, dict):
            st.error("Chaque élément de 'questions' doit être un objet JSON.")
            st.stop()

        missing = required_fields - set(item.keys())
        if missing:
            st.error(
                f"Question invalide ({item.get('question_id', 'sans id')}) - champs manquants : {sorted(missing)}"
            )
            st.stop()

    return questions

def get_domains(questions: List[Dict[str, Any]]) -> List[str]:
    domains = []
    for q in questions:
        domain = q.get("domaine_principal", "Autre")
        if domain not in domains:
            domains.append(domain)
    return domains

@st.cache_data(show_spinner=False)
def load_questionnaire_cached(path_str: str) -> List[Dict[str, Any]]:
    return load_questionnaire(Path(path_str))