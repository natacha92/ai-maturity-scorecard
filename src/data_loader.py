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

<<<<<<< HEAD
# ── Index rapide par question_id ──────────────────────────────────────────────

def build_question_index(questions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Retourne un dict {question_id: question} pour accès O(1)."""
    return {q["question_id"]: q for q in questions}

# ── Filtres par type ──────────────────────────────────────────────────────────

def get_scored_questions(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Uniquement les questions qui contribuent au score."""
    return [q for q in questions if q.get("question_type") == "scored"]

def get_applicability_questions(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Questions qui activent/désactivent d'autres questions."""
    return [q for q in questions if q.get("question_type") == "applicability"]

def get_evidence_questions(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Champs texte libre (preuves), sans impact sur le score."""
    return [q for q in questions if q.get("question_type") == "evidence"]

# ── Navigation domaines / groupes ─────────────────────────────────────────────

def get_domains(questions: List[Dict[str, Any]]) -> List[str]:
    """Liste ordonnée des domaines principaux (ordre_domaine_principal)."""
    seen = {}
    for q in questions:
        domain = q.get("domaine_principal")
        order = q.get("ordre_domaine_principal", 99)
        if domain and domain not in seen:
            seen[domain] = order
    return sorted(seen, key=lambda d: seen[d])

def get_specific_domains(questions: List[Dict[str, Any]], domaine_principal: str) -> List[str]:
    """Sous-domaines d'un domaine principal, triés par ordre_domaine_specifique."""
    seen = {}
    for q in questions:
        if q.get("domaine_principal") != domaine_principal:
            continue
        sub = q.get("domaine_specifique")
        order = q.get("ordre_domaine_specifique", 99)
        if sub and sub not in seen:
            seen[sub] = order
    return sorted(seen, key=lambda d: seen[d])

def get_capability_groups(questions: List[Dict[str, Any]], domaine_specifique: str) -> List[str]:
    """Groupes de capacités dans un sous-domaine (ex: 'ERP', 'CRM'...)."""
    groups = []
    for q in questions:
        if q.get("domaine_specifique") != domaine_specifique:
            continue
        group = q.get("capability_group")
        if group and group != "NA" and group not in groups:
            groups.append(group)
    return groups


# def get_domains(questions: List[Dict[str, Any]]) -> List[str]:
#     domains = []
#     for q in questions:
#         domain = q.get("domaine_principal", "Autre")
#         if domain not in domains:
#             domains.append(domain)
#     return domains

# ── Règles d'applicabilité ────────────────────────────────────────────────────

def is_question_applicable(
    question: Dict[str, Any],
    responses: Dict[str, Any]  # {question_id: label_répondu ou score}
) -> bool:
    """
    Interprète applicability_rule et retourne True si la question doit être affichée.
    Supporte : 'always', 'only_if(QID == Valeur)', 'only_if(QID >= N)'
    """
    rule = question.get("applicability_rule", "always")

    if rule == "always":
        return True

    if rule.startswith("only_if(") and rule.endswith(")"):
        condition = rule[len("only_if("):-1]

        # Cas : QID == 'Label'
        if "==" in condition:
            parts = condition.split("==")
            qid = parts[0].strip()
            expected = parts[1].strip().strip("'\"")
            return responses.get(qid) == expected

        # Cas : QID >= N
        if ">=" in condition:
            parts = condition.split(">=")
            qid = parts[0].strip()
            threshold = int(parts[1].strip())
            return int(responses.get(qid, -1)) >= threshold

    # Règle non reconnue → on affiche par sécurité
    return True
=======
def get_domains(questions: List[Dict[str, Any]]) -> List[str]:
    domains = []
    for q in questions:
        domain = q.get("domaine_principal", "Autre")
        if domain not in domains:
            domains.append(domain)
    return domains
>>>>>>> 4d21a07f1eb59284ad0d7a8d4c38ce706e8e8fdd

@st.cache_data(show_spinner=False)
def load_questionnaire_cached(path_str: str) -> List[Dict[str, Any]]:
    return load_questionnaire(Path(path_str))