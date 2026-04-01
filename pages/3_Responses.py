import streamlit as st
from src.state import init_session

init_session()

st.title("Réponses brutes")
st.json(list(st.session_state.responses.values()))