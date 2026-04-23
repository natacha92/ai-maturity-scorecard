import streamlit as st
from src.config import QUESTIONNAIRE_PATH, ASSESSMENTS_DIR
from src.data_loader import load_questionnaire
from src.scoring import compute_scores
from src.persistence import save_assessment
from src.state import init_session

init_session()

st.title("Administration")

questions = load_questionnaire(QUESTIONNAIRE_PATH)
responses = st.session_state.responses
scores = compute_scores(questions, responses)

if st.button("Sauvegarder l'audit"):
    if not st.session_state.client_name:
        st.warning("Veuillez renseigner le nom du client.")
    else:
        path = save_assessment(
            ASSESSMENTS_DIR,
            st.session_state.client_name,
            st.session_state.assessment_name,
            responses,
            scores,
        )
        st.success(f"Audit sauvegardé : {path}")