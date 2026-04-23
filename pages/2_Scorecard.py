import streamlit as st
from src.config import QUESTIONNAIRE_PATH
from src.data_loader import load_questionnaire_cached
from src.scoring import compute_scores, build_maturity_structure
from src.ui_scorecard import render_maturity_model
from src.state import init_session

init_session()

st.title("Scorecard")

questions = load_questionnaire_cached(QUESTIONNAIRE_PATH)
responses = st.session_state.responses

scores = compute_scores(questions, responses)
maturity = build_maturity_structure(questions, responses)

col1, col2 = st.columns([1, 2])
with col1:
    st.metric("Score global", scores["global_score"] if scores["global_score"] is not None else "N/A")
    st.json(scores)

with col2:
    render_maturity_model(maturity)