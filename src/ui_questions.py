from typing import Any, Dict
import streamlit as st
from src.rules import parse_rule

def render_single_choice(question: Dict[str, Any], existing: Dict[str, Any]) -> Dict[str, Any]:
    choices = question.get("choices", [])
    labels = [choice["label"] for choice in choices]
    selected_label = existing.get("selected_choice")
    default_index = labels.index(selected_label) if selected_label in labels else 0

    selected = st.radio(
        question["question_label"],
        labels,
        index=default_index if labels else 0,
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
        comment = st.text_area("Commentaire", value=existing.get("comment", ""), key=f"comment_{question_id}")
        tools = st.text_input("Outils actuels", value=", ".join(existing.get("current_tools", [])), key=f"tools_{question_id}")
        docs = st.text_input("Documents ou preuves", value=", ".join(existing.get("current_documents", [])), key=f"docs_{question_id}")
        pain_points = st.text_area("Douleurs / difficultés", value="\n".join(existing.get("pain_points", [])), key=f"pain_{question_id}")
        weaknesses = st.text_area("Faiblesses perçues", value="\n".join(existing.get("weaknesses", [])), key=f"weak_{question_id}")
        obstacles = st.text_area("Obstacles / risques", value="\n".join(existing.get("obstacles", [])), key=f"obs_{question_id}")

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

    ## AFFICHE LE RUBAN POUR LES QUESTIONS QUI DEVIENNENT NON VALABLES
    visible = parse_rule(question.get("applicability_rule", "always"), responses)
    if not visible:
        st.info("Cette question n'est pas applicable dans le contexte actuel.")
        return   


    st.markdown(f"### {question.get('domaine_specifique', 'Question')}")
    if question.get("question_help"):
        st.caption(question["question_help"])

    if question["type_reponse"] == "single_choice":
        answer = render_single_choice(question, existing)
    elif question["type_reponse"] == "text":
        answer = render_text_question(question, existing)
    else:
        st.warning(f"Type de question non géré : {qid}")
        return

    context_fields = render_context_fields(qid, existing)

    responses[qid] = {
        "question_id": qid,
        "question_type": question.get("question_type"),
        **answer,
        **context_fields,
    }