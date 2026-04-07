import streamlit as st
from models.database import init_db, get_session, Client, Assessment, Response
from src.data_loader import load_questionnaire_cached
from engine.scoring import compute_scores
from models.database import load_responses_for_scoring
from engine.recommendations import get_recommendations, generate_roadmap, seed_recommendations

init_db()
seed_recommendations()

st.title("Recommendations & Roadmap")

# --- Select assessment ---
session = get_session()
try:
    completed = (
        session.query(Assessment)
        .filter(Assessment.status == "completed")
        .order_by(Assessment.updated_at.desc())
        .all()
    )
    assessment_options = []
    for a in completed:
        client = session.query(Client).get(a.client_id)
        assessment_options.append({
            "id": a.id,
            "label": f"{a.name} — {client.name if client else 'Unknown'}",
        })
finally:
    session.close()

if not assessment_options:
    st.info("No completed assessments.")
    st.stop()

selected_label = st.selectbox("Select Assessment", [a["label"] for a in assessment_options])
selected = next(a for a in assessment_options if a["label"] == selected_label)

# Load scores
questionnaire = load_questionnaire_cached("data/questionnaire.json")
scores = compute_scores(questionnaire, load_responses_for_scoring(selected["id"]))
recommendations = get_recommendations(scores["domains"], scores.get("subdomains"))
roadmap = generate_roadmap(recommendations)

# --- Recommendations list ---
st.divider()
st.subheader(f"Recommendations ({len(recommendations)} found)")

PRIORITY_LABELS = {1: "🔴 Critical", 2: "🟠 High", 3: "🟡 Medium", 4: "🔵 Low", 5: "⚪ Nice-to-have"}
IMPACT_ICONS = {"high": "⬆️", "medium": "➡️", "low": "⬇️"}
EFFORT_ICONS = {"low": "🟢", "medium": "🟡", "high": "🔴"}

for rec in recommendations:
    with st.expander(
        f"{PRIORITY_LABELS.get(rec['priority'], '⚪')} {rec['title']} — {rec['domain']}"
    ):
        col1, col2, col3 = st.columns(3)
        col1.metric("Impact", f"{IMPACT_ICONS.get(rec['impact'], '')} {rec['impact'].title()}")
        col2.metric("Effort", f"{EFFORT_ICONS.get(rec['effort'], '')} {rec['effort'].title()}")
        col3.metric("Horizon", rec["horizon"])

        st.markdown(rec["text"])

        if rec.get("subdomain"):
            st.caption(f"Subdomain: {rec['subdomain']}")

# --- Roadmap ---
st.divider()
st.subheader("90-Day Roadmap")

for horizon, label, color in [("30d", "First 30 Days", "🟢"), ("60d", "30-60 Days", "🟡"), ("90d", "60-90 Days", "🔴")]:
    items = roadmap.get(horizon, [])
    if items:
        st.markdown(f"### {color} {label}")
        for i, rec in enumerate(items, 1):
            st.markdown(
                f"**{i}.** {rec['title']} "
                f"({rec['domain']}) — Impact: {rec['impact']} / Effort: {rec['effort']}"
            )
    else:
        st.markdown(f"### {color} {label}")
        st.caption("No actions in this period.")

# --- Summary table ---
st.divider()
st.subheader("Action Plan Summary")

import pandas as pd

if recommendations:
    df = pd.DataFrame([
        {
            "Priority": rec["priority"],
            "Action": rec["title"],
            "Domain": rec["domain"],
            "Impact": rec["impact"].title(),
            "Effort": rec["effort"].title(),
            "Horizon": rec["horizon"],
        }
        for rec in recommendations
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)
