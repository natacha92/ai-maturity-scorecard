import streamlit as st
from src.state import init_session

st.set_page_config(
    page_title="AI Maturity Matrix",
    layout="wide",
)

init_session()

st.title("AI Maturity Matrix")
st.write("Application de diagnostic de maturité IA.")

with st.sidebar:
    st.header("Contexte de l'audit")
    st.session_state.client_name = st.text_input("Nom du client", value=st.session_state.client_name)
    st.session_state.assessment_name = st.text_input("Nom de l'audit", value=st.session_state.assessment_name)

st.info("Utilise le menu de gauche pour naviguer entre les pages.")