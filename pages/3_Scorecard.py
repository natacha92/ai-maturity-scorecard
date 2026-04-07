import streamlit as st
from pathlib import Path
from models.database import init_db, get_session, Client, Assessment, Response, load_responses_for_scoring
from src.data_loader import load_questionnaire_cached
from engine.scoring import compute_scores, build_maturity_structure, compute_gap_analysis, get_maturity_level
from engine.classification import classify_client

init_db()

QUESTIONNAIRE_PATH = str(Path("data/questionnaire.json"))

st.title("📊 Scorecard")

# ── Sélection de l'assessment ─────────────────────────────────────────────────
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
            "label": f"{a.name} — {client.name if client else 'Inconnu'}",
            "client_name": client.name if client else "Inconnu",
        })
finally:
    session.close()

if not assessment_options:
    st.info("Aucun assessment terminé. Complétez un assessment d'abord.")
    st.page_link("pages/2_Questionnaire.py", label="Aller au questionnaire", icon="📋")

labels = [a["label"] for a in assessment_options]
selected_label = st.selectbox("Assessment", labels, key="scorecard_assessment_top")
if not selected_label:
    st.stop()
selected = assessment_options[labels.index(selected_label)]


# ── Chargement des réponses et calcul des scores ──────────────────────────────
questions  = load_questionnaire_cached(QUESTIONNAIRE_PATH)
responses  = load_responses_for_scoring(selected["id"])  # utilise to_scoring_dict()
scores     = compute_scores(questions, responses)
maturity   = build_maturity_structure(questions, responses)
gaps       = compute_gap_analysis(scores["domains"])
archetype  = classify_client(scores["domains"], scores["global_score"])

global_score   = scores.get("global_score")
maturity_level = get_maturity_level(global_score)

st.divider()

# ── Score global ──────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 2])

with col1:
    st.metric(
        "Score global",
        f"{global_score}%" if global_score is not None else "N/A",
    )
    st.markdown(
        f"**Niveau :** :{maturity_level['label']}",
        unsafe_allow_html=True,
    )
    # Badge couleur niveau
    color = maturity_level["color"]
    label = maturity_level["label"]
    st.markdown(
        f'<span style="background:{color};padding:4px 12px;border-radius:12px;'
        f'color:white;font-weight:bold">{label}</span>',
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(f"### Profil : {archetype['archetype_name']}")
    st.markdown(archetype["description"])
    st.info(f"💡 **Recommandation clé :** {archetype['key_recommendation']}")
    risk_colors = {"low": "🟢", "medium": "🟡", "high": "🔴"}
    st.caption(f"Niveau de risque : {risk_colors.get(archetype['risk_level'], '⚪')} {archetype['risk_level']}")

st.divider()

# ── Scores par domaine ────────────────────────────────────────────────────────
st.subheader("Scores par domaine")

for domain_data in maturity:
    domain_score = domain_data["score"]
    color        = domain_data["color"]
    label        = domain_data["maturity"]

    with st.expander(
        f"📂 {domain_data['label']} — "
        f"{domain_score}% ({label})" if domain_score is not None else f"📂 {domain_data['label']} — N/A"
    ):
        for seg in domain_data["segments"]:
            seg_score = seg["score"]
            col_label, col_bar, col_val = st.columns([3, 5, 1])
            with col_label:
                st.markdown(f"**{seg['label']}**")
                st.caption(seg["maturity"])
            with col_bar:
                if seg_score is not None:
                    st.progress(seg_score / 100)
            with col_val:
                st.markdown(f"**{seg_score}%**" if seg_score is not None else "N/A")

            # Capability groups si présents
            for cap in seg.get("capability_groups", []):
                cap_score = cap["score"]
                c1, c2, c3 = st.columns([3, 5, 1])
                with c1:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;↳ {cap['label']}")
                with c2:
                    if cap_score is not None:
                        st.progress(cap_score / 100)
                with c3:
                    st.markdown(f"{cap_score}%" if cap_score is not None else "N/A")

st.divider()

# ── Maturity Map (heatmap hiérarchique) ──────────────────────────────────────
st.subheader("🗺️ Maturity Map")

def score_to_bg(score):
    if score is None: return "#E5E7EB", "#6B7280"
    if score < 25:    return "#FEE2E2", "#DC2626"
    if score < 50:    return "#FEF3C7", "#D97706"
    if score < 75:    return "#FEF9C3", "#CA8A04"
    return "#DCFCE7", "#16A34A"

for domain_data in maturity:
    domain_score = domain_data["score"]
    bg, fg = score_to_bg(domain_score)

    # En-tête domaine
    st.markdown(
        f"""<div style="background:#1E3A5F;color:white;padding:10px 16px;
        border-radius:8px 8px 0 0;display:flex;justify-content:space-between;
        align-items:center;margin-top:16px;">
        <span style="font-weight:700;font-size:15px">{domain_data['label']}</span>
        <span style="background:{bg};color:{fg};padding:3px 10px;border-radius:12px;
        font-weight:700;font-size:14px">{domain_score}%</span>
        </div>""",
        unsafe_allow_html=True,
    )

    # Sous-domaines en grille
    segs = domain_data["segments"]
    n = len(segs)
    if n == 0:
        continue

    # Ligne labels
    cols_label = st.columns(n)
    for i, seg in enumerate(segs):
        seg_bg, seg_fg = score_to_bg(seg["score"])
        with cols_label[i]:
            st.markdown(
                f"""<div style="background:{seg_bg};border:1px solid {seg_fg};
                border-radius:6px;padding:8px 6px;text-align:center;min-height:80px;
                display:flex;flex-direction:column;justify-content:center;gap:4px">
                <div style="font-size:11px;font-weight:600;color:#1E3A5F;line-height:1.3">
                {seg['label']}</div>
                <div style="font-size:16px;font-weight:700;color:{seg_fg}">
                {seg['score']}%</div>
                <div style="font-size:10px;color:{seg_fg}">{seg['maturity']}</div>
                </div>""",
                unsafe_allow_html=True,
            )

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# Légende
st.markdown("""
<div style="display:flex;gap:16px;margin-top:8px;flex-wrap:wrap">
<span style="background:#FEE2E2;color:#DC2626;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600">🔴 Initial (0-25%)</span>
<span style="background:#FEF3C7;color:#D97706;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600">🟡 En développement (25-50%)</span>
<span style="background:#FEF9C3;color:#CA8A04;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600">🟨 Structuré (50-75%)</span>
<span style="background:#DCFCE7;color:#16A34A;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600">🟢 Optimisé (75-100%)</span>
</div>
""", unsafe_allow_html=True)

# ── Gap Analysis ──────────────────────────────────────────────────────────────
st.subheader("Analyse des écarts")

if gaps:
    for domain, gap_data in gaps.items():
        current = gap_data["current"]
        target  = gap_data["target"]
        gap     = gap_data["gap"]

        col_d, col_c, col_t, col_g = st.columns([3, 2, 2, 2])
        with col_d:
            st.markdown(f"**{domain}**")
        with col_c:
            st.metric("Actuel", f"{current}%")
        with col_t:
            st.metric("Cible", f"{target}%")
        with col_g:
            delta_color = "inverse" if gap > 0 else "normal"
            st.metric("Écart", f"{gap}%", delta=f"{-gap}%", delta_color=delta_color)
else:
    st.info("Aucun écart calculable.")

st.divider()

# ── Détail JSON (debug, masqué par défaut) ────────────────────────────────────
with st.expander("🔍 Données brutes (debug)", expanded=False):
    st.json(scores)