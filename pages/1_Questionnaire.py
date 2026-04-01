import streamlit as st
from src.config import QUESTIONNAIRE_PATH
from src.data_loader import load_questionnaire_cached, get_domains
from src.ui_questions import render_question
from src.state import init_session
from src.rules import parse_rule

init_session()

st.title("Questionnaire")

questions = load_questionnaire_cached(QUESTIONNAIRE_PATH)
responses = st.session_state.responses

domains = get_domains(questions)
selected_domain = st.selectbox("Choisir un domaine", domains)

filtered_questions = [
    q for q in questions
    if q.get("domaine_principal", "Autre") == selected_domain
]

applicable_questions = [
    q for q in filtered_questions
    if parse_rule(q.get("applicability_rule", "always"), responses)
]

for question in applicable_questions:
    with st.container(border=True):
        render_question(question, responses)
