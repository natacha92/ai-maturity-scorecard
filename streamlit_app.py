# import streamlit as st

# st.title("🎈 My new app")
# st.write(
#     "Let's start building! For help and inspiration, head over to [docs.streamlit.io](https://docs.streamlit.io/)."
# )


import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st


DATA_DIR = Path("data")
QUESTIONNAIRE_PATH = DATA_DIR / "questionnaire.json"
ASSESSMENTS_DIR = DATA_DIR / "assessments"


# ---------- Data loading ----------

def load_questionnaire(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        st.error(f"Questionnaire introuvable: {path}")
        st.stop()

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        st.error("Le fichier questionnaire.json doit contenir une liste de questions.")
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

    return data["questions"]


def get_domains(questions: List[Dict[str, Any]]) -> List[str]:
    domains = []
    for q in questions:
        domain = q.get("domaine_principal", "Autre")
        if domain not in domains:
            domains.append(domain)
    return domains


# ---------- Rules ----------

def parse_rule(rule: Optional[str], responses: Dict[str, Dict[str, Any]]) -> bool:
    if not rule or rule == "always":
        return True

    # V1 volontairement simple
    # Format attendu: only_if(QUESTION_ID >= 1)
    if rule.startswith("only_if(") and rule.endswith(")"):
        expression = rule[len("only_if("):-1].strip()
        for operator in [">=", "<=", "==", ">", "<"]:
            if operator in expression:
                left, right = expression.split(operator, 1)
                left = left.strip()
                right = right.strip()
                response = responses.get(left)
                if not response:
                    return False
                value = response.get("score")
                if value is None:
                    return False
                try:
                    target = float(right)
                    current = float(value)
                except ValueError:
                    return False

                if operator == ">=":
                    return current >= target
                if operator == "<=":
                    return current <= target
                if operator == "==":
                    return current == target
                if operator == ">":
                    return current > target
                if operator == "<":
                    return current < target
    return True


# ---------- State ----------

def init_session() -> None:
    if "responses" not in st.session_state:
        st.session_state.responses = {}
    if "client_name" not in st.session_state:
        st.session_state.client_name = ""
    if "assessment_name" not in st.session_state:
        st.session_state.assessment_name = ""


# ---------- Rendering ----------

def render_single_choice(question: Dict[str, Any], existing: Dict[str, Any]) -> Dict[str, Any]:
    choices = question.get("choices", [])
    labels = [choice["label"] for choice in choices]
    selected_label = existing.get("selected_choice")
    default_index = labels.index(selected_label) if selected_label in labels else 0

    selected = st.radio(
        question["question_label"],
        labels,
        index=default_index if labels else None,
        key=f"choice_{question['question_id']}",
    )

    selected_choice = next((c for c in choices if c["label"] == selected), None)
    score = selected_choice.get("score") if selected_choice else None

    return {
        "selected_choice": selected,
        "score": score,
    }


def render_text_question(question: Dict[str, Any], existing: Dict[str, Any]) -> Dict[str, Any]:
    value = st.text_area(
        question["question_label"],
        value=existing.get("value", ""),
        key=f"text_{question['question_id']}",
    )
    return {"value": value, "score": None}


def render_context_fields(question_id: str, existing: Dict[str, Any]) -> Dict[str, Any]:
    with st.expander("Contexte complémentaire", expanded=False):
        comment = st.text_area(
            "Commentaire",
            value=existing.get("comment", ""),
            key=f"comment_{question_id}",
        )
        tools = st.text_input(
            "Outils actuels (séparés par des virgules)",
            value=", ".join(existing.get("current_tools", [])),
            key=f"tools_{question_id}",
        )
        docs = st.text_input(
            "Documents ou preuves disponibles",
            value=", ".join(existing.get("current_documents", [])),
            key=f"docs_{question_id}",
        )
        pain_points = st.text_area(
            "Douleurs / difficultés",
            value="\n".join(existing.get("pain_points", [])),
            key=f"pain_{question_id}",
        )
        weaknesses = st.text_area(
            "Faiblesses perçues",
            value="\n".join(existing.get("weaknesses", [])),
            key=f"weak_{question_id}",
        )
        obstacles = st.text_area(
            "Obstacles / risques",
            value="\n".join(existing.get("obstacles", [])),
            key=f"obs_{question_id}",
        )

    return {
        "comment": comment,
        "current_tools": [x.strip() for x in tools.split(",") if x.strip()],
        "current_documents": [x.strip() for x in docs.split(",") if x.strip()],
        "pain_points": [x.strip() for x in pain_points.splitlines() if x.strip()],
        "weaknesses": [x.strip() for x in weaknesses.splitlines() if x.strip()],
        "obstacles": [x.strip() for x in obstacles.splitlines() if x.strip()],
    }


def render_question(question: Dict[str, Any], responses: Dict[str, Dict[str, Any]]) -> None:
    qid = question["question_id"]
    existing = responses.get(qid, {})

    visible = parse_rule(question.get("applicability_rule", "always"), responses)
    if not visible:
        return

    st.markdown(f"### {question.get('domaine_specifique', 'Question')}")
    if question.get("question_help"):
        st.caption(question["question_help"])

    if question["question_type"] == "scored" and question["type_reponse"] == "single_choice":
        answer = render_single_choice(question, existing)
    elif question["type_reponse"] == "text":
        answer = render_text_question(question, existing)
    else:
        st.warning(f"Type de question non encore géré pour {qid}")
        return

    context_fields = render_context_fields(qid, existing)

    responses[qid] = {
        "question_id": qid,
        **answer,
        **context_fields,
    }


# ---------- Scoring ----------

def compute_scores(questions: List[Dict[str, Any]], responses: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    domain_scores: Dict[str, Dict[str, float]] = {}
    global_weighted_sum = 0.0
    global_weight = 0.0

    for q in questions:
        if not isinstance(q, dict):
            st.error(f"Question invalide (pas un dict) : {q}")
            continue
        if q.get("question_type") != "scored":
            continue
        if not parse_rule(q.get("applicability_rule", "always"), responses):
            continue

        qid = q["question_id"]
        response = responses.get(qid)
        if not response or response.get("score") is None:
            continue

        score = float(response["score"])
        weight = float(q.get("poids", 1))
        domain = q.get("domaine_principal", "Autre")

        if domain not in domain_scores:
            domain_scores[domain] = {"weighted_sum": 0.0, "weight": 0.0}

        domain_scores[domain]["weighted_sum"] += score * weight
        domain_scores[domain]["weight"] += weight
        global_weighted_sum += score * weight
        global_weight += weight

    result = {
        "global_score": round(global_weighted_sum / global_weight, 2) if global_weight else None,
        "domains": {},
    }

    for domain, agg in domain_scores.items():
        result["domains"][domain] = round(agg["weighted_sum"] / agg["weight"], 2) if agg["weight"] else None

    return result


# ---------- Persistence ----------

def save_assessment(client_name: str, assessment_name: str, responses: Dict[str, Dict[str, Any]], scores: Dict[str, Any]) -> Path:
    ASSESSMENTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_client = client_name.strip().replace(" ", "_") or "client_sans_nom"
    safe_assessment = assessment_name.strip().replace(" ", "_") or "audit"
    output_path = ASSESSMENTS_DIR / f"{safe_client}__{safe_assessment}.json"

    payload = {
        "client_name": client_name,
        "assessment_name": assessment_name,
        "responses": list(responses.values()),
        "scores": scores,
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return output_path


# ---------- App ----------

def main() -> None:
    st.set_page_config(page_title="AI Scorecard", layout="wide")
    init_session()

    st.title("AI Data Maturity Scorecard")
    st.write("Version V1 : questionnaire dynamique + scoring + collecte de contexte.")

    questions = load_questionnaire(QUESTIONNAIRE_PATH)
    responses = st.session_state.responses

    with st.sidebar:
        st.header("Contexte de l'audit")
        st.session_state.client_name = st.text_input("Nom du client", value=st.session_state.client_name)
        st.session_state.assessment_name = st.text_input("Nom de l'audit", value=st.session_state.assessment_name)

        current_scores = compute_scores(questions, responses)
        st.subheader("Score global")
        st.metric("Maturité actuelle", current_scores.get("global_score") if current_scores.get("global_score") is not None else "N/A")

        if st.button("Sauvegarder l'audit"):
            path = save_assessment(
                st.session_state.client_name,
                st.session_state.assessment_name,
                responses,
                current_scores,
            )
            st.success(f"Audit sauvegardé : {path}")

    domains = get_domains(questions)
    selected_domain = st.selectbox("Choisir un domaine", domains)

    filtered_questions = [q for q in questions if q.get("domaine_principal", "Autre") == selected_domain]

    for question in filtered_questions:
        with st.container(border=True):
            render_question(question, responses)

    st.divider()
    st.subheader("Synthèse des scores")
    final_scores = compute_scores(questions, responses)
    st.json(final_scores)

    st.subheader("Réponses brutes")
    st.json(list(responses.values()))


if __name__ == "__main__":
    main()
