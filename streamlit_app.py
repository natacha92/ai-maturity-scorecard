# import streamlit as st

# st.title("🎈 My new app")
# st.write(
#     "Let's start building! For help and inspiration, head over to [docs.streamlit.io](https://docs.streamlit.io/)."
# )


import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
from collections import defaultdict

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
        st.error("Le fichier questionnaire.json doit contenir un objet JSON racine.")
        st.stop()

    if not isinstance(data, dict):
        st.error("Le fichier questionnaire.json doit contenir une liste de questions.")
        st.stop()

    questions = data.get("questions")
    
    if not isinstance(questions, list):
        st.error("Le champ 'questions' doit contenir une liste de questions.")
        st.stop()

    required_fields = {"question_id", "question_label", "question_type", "type_reponse"}
    required_scored_fields = {
        "domaine_principal",
        "domaine_specifique",
        "niveau_scorecard",
        "ordre_domaine_principal",
        "ordre_domaine_specifique",
        "ordre_niveau",
    }
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
        
        ##########################################################
        # commenté tant que json non complété avec champs requis #
        ##########################################################
        # if item.get("question_type") == "scored":
        #     missing_scored = required_scored_fields - set(item.keys())
        #     if missing_scored:
        #         st.error(
        #             f"Question scorée invalide ({item.get('question_id', 'sans id')}) - champs métier manquants : {sorted(missing_scored)}"
        #         )
        #         st.stop()

    return questions


def get_domains(questions: List[Dict[str, Any]]) -> List[str]:
    domains = []
    for q in questions:
        domain = q.get("domaine_principal", "Autre")
        if domain not in domains:
            domains.append(domain)
    return domains


# ---------- Rules ----------

# def parse_rule(rule: Optional[str], responses: Dict[str, Dict[str, Any]]) -> bool:
#     if not rule or rule == "always":
#         return True

#     # V1 volontairement simple
#     # Format attendu: only_if(QUESTION_ID >= 1)
#     if rule.startswith("only_if(") and rule.endswith(")"):
#         expression = rule[len("only_if("):-1].strip()
#         for operator in [">=", "<=", "==", ">", "<"]:
#             if operator in expression:
#                 left, right = expression.split(operator, 1)
#                 left = left.strip()
#                 right = right.strip()
#                 response = responses.get(left)
#                 if not response:
#                     return False
                
#                 # retire les quotes éventuelles
#                 if (right.startswith("'") and right.endswith("'")) or (
#                     right.startswith('"') and right.endswith('"')
#                 ):
#                     target_text = right[1:-1]
#                     current_text = response.get("selected_choice") or response.get("value")
#                     if current_text is None:
#                         return False

#                     if operator == "==":
#                         return str(current_text) == target_text
#                     return False  # pour l'instant on ne gère que == sur du texte

#                 value = response.get("score")
#                 if value is None:
#                     return False
#                 try:
#                     target = float(right)
#                     current = float(value)
#                 except ValueError:
#                     return False

#                 if operator == ">=":
#                     return current >= target
#                 if operator == "<=":
#                     return current <= target
#                 if operator == "==":
#                     return current == target
#                 if operator == ">":
#                     return current > target
#                 if operator == "<":
#                     return current < target
#     return True
def parse_rule(rule: Optional[str], responses: Dict[str, Dict[str, Any]]) -> bool:
    if not rule or rule == "always":
        return True

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

                # comparaison texte
                if (right.startswith("'") and right.endswith("'")) or (
                    right.startswith('"') and right.endswith('"')
                ):
                    expected_text = right[1:-1]
                    current_text = response.get("selected_choice") or response.get("value")
                    if current_text is None:
                        return False
                    if operator == "==":
                        return str(current_text) == expected_text
                    return False

                # comparaison numérique
                value = response.get("score")
                if value is None:
                    return False

                try:
                    current_num = float(value)
                    expected_num = float(right)
                except ValueError:
                    return False

                if operator == ">=":
                    return current_num >= expected_num
                if operator == "<=":
                    return current_num <= expected_num
                if operator == "==":
                    return current_num == expected_num
                if operator == ">":
                    return current_num > expected_num
                if operator == "<":
                    return current_num < expected_num

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
        st.info("Cette question n'est pas applicable dans le contexte actuel.")
        return
    st.markdown(f"### {question.get('domaine_specifique', 'Question')}")
    ##USEFUL FOR DEBUG
    st.caption(f"Type: {question.get('question_type')} | Réponse: {question.get('type_reponse')}")
    if question.get("question_help"):
        st.caption(question["question_help"])

    #if question["question_type"] == "scored" and question["type_reponse"] == "single_choice":
    if question["type_reponse"] == "single_choice":
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

# def save_assessment(client_name: str, assessment_name: str, responses: Dict[str, Dict[str, Any]], scores: Dict[str, Any]) -> Path:
#     ASSESSMENTS_DIR.mkdir(parents=True, exist_ok=True)
#     safe_client = client_name.strip().replace(" ", "_") or "client_sans_nom"
#     safe_assessment = assessment_name.strip().replace(" ", "_") or "audit"
#     output_path = ASSESSMENTS_DIR / f"{safe_client}__{safe_assessment}.json"

#     payload = {
#         "client_name": client_name,
#         "assessment_name": assessment_name,
#         "responses": list(responses.values()),
#         "scores": scores,
#     }

#     with output_path.open("w", encoding="utf-8") as f:
#         json.dump(payload, f, ensure_ascii=False, indent=2)

#     return output_path

def save_assessment(client_name, assessment_name, responses, scores):
    ASSESSMENTS_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "assessment_id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),

        "client": {
            "name": client_name,
            "secteur": None,
            "taille": None
        },

        "assessment": {
            "name": assessment_name,
            "version": "v1",
            "consultant": None
        },

        "responses": [],
        "scores": scores
    }

    for r in responses.values():
        payload["responses"].append({
            "question_id": r.get("question_id"),
            "question_type": r.get("question_type"),

            "answer": {
                "selected_choice": r.get("selected_choice"),
                "score": r.get("score")
            },

            "context": {
                "comment": r.get("comment"),
                "current_tools": r.get("current_tools", []),
                "current_documents": r.get("current_documents", []),
                "pain_points": r.get("pain_points", []),
                "weaknesses": r.get("weaknesses", []),
                "obstacles": r.get("obstacles", [])
            }
        })

    safe_client = client_name.replace(" ", "_") or "client"
    safe_assessment = assessment_name.replace(" ", "_") or "audit"

    path = ASSESSMENTS_DIR / f"{safe_client}__{safe_assessment}.json"

    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return path

#----------- RESULT -------

def score_to_color(score: Optional[float]) -> str:
    if score is None:
        return "#F3F4F6"  # gris clair
    if score < 25:
        return "#E5E7EB"  # gris
    if score < 50:
        return "#FACC15"  # jaune
    return "#22C55E"      # vert

# def build_maturity_structure(questions, responses):
    levels = {}

    for q in questions:
        if q.get("question_type") != "scored":
            continue
        if not parse_rule(q.get("applicability_rule", "always"), responses):
            continue

        qid = q["question_id"]
        response = responses.get(qid)

        if not response or response.get("score") is None:
            continue

        level = q.get("domaine_principal", "Autre")
        segment = q.get("domaine_specifique", "Autre")

        score = float(response["score"])
        weight = float(q.get("poids", 1))

        if level not in levels:
            levels[level] = {
                "segments": {},
                "sum": 0,
                "weight": 0
            }

        if segment not in levels[level]["segments"]:
            levels[level]["segments"][segment] = {
                "sum": 0,
                "weight": 0
            }

        levels[level]["segments"][segment]["sum"] += score * weight
        levels[level]["segments"][segment]["weight"] += weight

        levels[level]["sum"] += score * weight
        levels[level]["weight"] += weight

    result = []

    for level_name, level_data in levels.items():
        segments = []

        for seg_name, seg_data in level_data["segments"].items():
            seg_score = None
            if seg_data["weight"]:
                seg_score = round((seg_data["sum"] / seg_data["weight"]) * 25)

            segments.append({
                "label": seg_name,
                "score": seg_score,
                "color": score_to_color(seg_score)
            })

        level_score = None
        if level_data["weight"]:
            level_score = round((level_data["sum"] / level_data["weight"]) * 25)

        result.append({
            "label": level_name,
            "score": level_score,
            "segments": segments
        })

    return result
def build_maturity_structure(
    questions: List[Dict[str, Any]],
    responses: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}

    for q in questions:
        if q.get("question_type") != "scored":
            continue

        if not parse_rule(q.get("applicability_rule", "always"), responses):
            continue

        qid = q["question_id"]
        response = responses.get(qid)

        if not response or response.get("score") is None:
            continue

        domain = q.get("domaine_principal", "Autre")
        segment = q.get("domaine_specifique", "Autre")

        domain_order = q.get("ordre_domaine_principal", 999)
        segment_order = q.get("ordre_domaine_specifique", 999)

        weight = float(q.get("poids", 1))
        score = float(response["score"])  # score entre 0 et 4
        score_pct = (score / 4.0) * 100.0

        if domain not in grouped:
            grouped[domain] = {
                "label": domain,
                "score_sum": 0.0,
                "weight_sum": 0.0,
                "order": domain_order,
                "segments": {}
            }

        if segment not in grouped[domain]["segments"]:
            grouped[domain]["segments"][segment] = {
                "label": segment,
                "score_sum": 0.0,
                "weight_sum": 0.0,
                "order": segment_order
            }

        grouped[domain]["segments"][segment]["score_sum"] += score_pct * weight
        grouped[domain]["segments"][segment]["weight_sum"] += weight

        grouped[domain]["score_sum"] += score_pct * weight
        grouped[domain]["weight_sum"] += weight

    result = []

    for _, domain_data in sorted(grouped.items(), key=lambda x: x[1]["order"]):
        segments = []

        for _, seg_data in sorted(domain_data["segments"].items(), key=lambda x: x[1]["order"]):
            seg_score = None
            if seg_data["weight_sum"] > 0:
                seg_score = round(seg_data["score_sum"] / seg_data["weight_sum"])

            segments.append({
                "label": seg_data["label"],
                "score": seg_score,
                "color": score_to_color(seg_score),
            })

        level_score = None
        if domain_data["weight_sum"] > 0:
            level_score = round(domain_data["score_sum"] / domain_data["weight_sum"])

        result.append({
            "label": domain_data["label"],
            "score": level_score,
            "segments": segments,
        })

    return result

def render_maturity_model(levels):
    st.markdown("""
    <style>
    .maturity-wrapper {
        display:flex;
        flex-direction:column;
        gap:20px;
        margin-top:20px;
    }
    .level {
        border:1px solid #D1D5DB;
        border-radius:10px;
        overflow:hidden;
        background:white;
    }
    .level-header {
        background:#2F3E8F;
        color:white;
        display:flex;
        justify-content:space-between;
        padding:12px 16px;
        font-weight:600;
        font-size:18px;
    }
    .segments {
        display:flex;
    }
    .segment {
        flex:1;
        padding:14px;
        text-align:center;
        border-right:1px solid #E5E7EB;
    }
    .segment:last-child {
        border-right:none;
    }
    .segment-label {
        font-size:13px;
        margin-bottom:6px;
    }
    .segment-score {
        font-weight:600;
        font-size:18px;
    }
    .arrow {
        text-align:center;
        font-size:28px;
        color:#9CA3AF;
    }
    </style>
    """, unsafe_allow_html=True)

    html = '<div class="maturity-wrapper">'

    for i, level in enumerate(levels):
        segments_html = ""

        for seg in level["segments"]:
            segments_html += f"""
            <div class="segment" style="background:{seg['color']}">
                <div class="segment-label">{seg['label']}</div>
                <div class="segment-score">{seg['score'] if seg['score'] is not None else "N/A"}%</div>
            </div>
            """

        html += f"""
        <div class="level">
            <div class="level-header">
                <span>{level['label']}</span>
                <span>{level['score'] if level['score'] is not None else "N/A"}%</span>
            </div>
            <div class="segments">
                {segments_html}
            </div>
        </div>
        """

        # flèche entre niveaux
        if i < len(levels) - 1:
            html += '<div class="arrow">↓</div>'

    html += "</div>"

    
    components.html(html, height=220 * max(len(levels), 1), scrolling=False)

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
            if not st.session_state.client_name:
                st.warning("Veuillez renseigner le nom du client")
            else:
                path = save_assessment(
                    st.session_state.client_name,
                    st.session_state.assessment_name,
                    responses,
                    current_scores
                )
                st.success(f"Audit sauvegardé : {path}")
                

    domains = get_domains(questions)
    selected_domain = st.selectbox("Choisir un domaine", domains)

    filtered_questions = [q for q in questions if q.get("domaine_principal", "Autre") == selected_domain]

    for question in filtered_questions:
        with st.container(border=True):
            render_question(question, responses)

    st.divider()
    st.subheader("Scorecard")
    maturity = build_maturity_structure(questions, responses)
    render_maturity_model(maturity)
    st.divider()
    st.subheader("Synthèse des scores")
    final_scores = compute_scores(questions, responses)
    st.json(final_scores)

    st.subheader("Réponses brutes")
    st.json(list(responses.values()))


if __name__ == "__main__":
    main()
