import streamlit as st

def init_session() -> None:
    defaults = {
        "responses": {},
        "client_name": "",
        "assessment_name": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value