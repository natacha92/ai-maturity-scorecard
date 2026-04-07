import streamlit as st
from pathlib import Path
from models.database import init_db, get_session, Client, Assessment, Response
from src.data_loader import load_questionnaire_cached, get_domains, get_specific_domains
from engine.rules import parse_rule
from engine.scoring import compute_scores, compute_completion, MATURITY_LEVELS

init_db()

QUESTIONNAIRE_PATH = str(Path("data/questionnaire.json"))

# ── Titre ─────────────────────────────────────────────────────────────────────
st.title("🧩 Nouvel Assessment")

# ── Chargement du questionnaire ───────────────────────────────────────────────
questions = load_questionnaire_cached(QUESTIONNAIRE_PATH)
# ── Si assessment déjà en cours, on saute la sélection ───────────────────────
if st.session_state.get("assessment_id") and st.sidebar.button("🔄 Changer d'assessment"):
    st.session_state.pop("assessment_id", None)
    st.rerun()

if st.session_state.get("assessment_id"):
    assessment_id = st.session_state["assessment_id"]
    # Affiche juste le nom pour contexte
    session = get_session()
    try:
        a = session.query(Assessment).get(assessment_id)
        c = session.query(Client).get(a.client_id) if a else None
        st.success(f"Assessment en cours : **{a.name}** — {c.name if c else ''}")
    finally:
        session.close()
else:
    # ── Sélection client ──────────────────────────────────────────────────────
    session = get_session()
    try:
        clients = session.query(Client).order_by(Client.name).all()
        clients_list = [{"id": c.id, "name": c.name} for c in clients]
    finally:
        session.close()

    if not clients_list:
        st.warning("Aucun client trouvé. Créez un client d'abord.")
        st.page_link("pages/1_Clients.py", label="Aller à la gestion des clients", icon="🏢")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        client_names = [c["name"] for c in clients_list]
        selected_client_name = st.selectbox("Client", client_names)
        selected_client = next(c for c in clients_list if c["name"] == selected_client_name)

    with col2:
        session = get_session()
        try:
            existing = (
                session.query(Assessment)
                .filter(Assessment.client_id == selected_client["id"])
                .filter(Assessment.status.in_(["draft", "in_progress"]))
                .order_by(Assessment.updated_at.desc())
                .all()
            )
            existing_list = [{"id": a.id, "name": a.name} for a in existing]
        finally:
            session.close()

        options = ["Créer un nouvel assessment"] + [a["name"] for a in existing_list]
        choice = st.selectbox("Assessment", options, key="assessment_selector")

    if choice == "Créer un nouvel assessment":
        assessment_name = st.text_input(
            "Nom de l'assessment",
            value=f"Assessment — {selected_client_name}"
        )
        if st.button("▶️ Démarrer"):
            session = get_session()
            try:
                assessment = Assessment(
                    client_id=selected_client["id"],
                    name=assessment_name,
                    status="in_progress",
                )
                session.add(assessment)
                session.commit()
                st.session_state["assessment_id"] = assessment.id
            finally:
                session.close()
            st.rerun()
        st.stop()
    else:
        selected_assessment = next(a for a in existing_list if a["name"] == choice)
        st.session_state["assessment_id"] = selected_assessment["id"]

assessment_id = st.session_state.get("assessment_id")
if not assessment_id:
    st.stop()

# ── Chargement des réponses existantes ────────────────────────────────────────
session = get_session()
try:
    existing_responses = (
        session.query(Response)
        .filter(Response.assessment_id == assessment_id)
        .all()
    )
    # Format attendu par rules.py et scoring.py
    saved_responses = {
        r.question_id: r.to_scoring_dict()
        for r in existing_responses
    }
finally:
    session.close()

st.divider()

# ── Barre de progression ──────────────────────────────────────────────────────
answered, total = compute_completion(questions, saved_responses)
pct = int((answered / total * 100) if total > 0 else 0)
st.progress(pct / 100, text=f"Progression : {answered}/{total} questions ({pct}%)")

# ── Sélection domaine principal ───────────────────────────────────────────────
domains = get_domains(questions)
selected_domain = st.selectbox("Domaine", domains, key="domain_selector")

# Sous-domaines du domaine sélectionné
sub_domains = get_specific_domains(questions, selected_domain)

st.subheader(f"📋 {selected_domain}")

# ── Rendu des questions ───────────────────────────────────────────────────────
# On fusionne saved + current pour que l'applicabilité soit dynamique
all_responses = dict(saved_responses)
new_responses = {}  # réponses saisies dans cette session

for sub_domain in sub_domains:
    st.markdown(f"### {sub_domain}")

    sub_questions = [
        q for q in questions
        if q.get("domaine_principal") == selected_domain
        and q.get("domaine_specifique") == sub_domain
    ]

    for q in sub_questions:
        qid = q["question_id"]
        qtype = q.get("question_type")

        # Applicabilité dynamique (fusionne saved + en cours)
        if not parse_rule(q.get("applicability_rule", "always"), all_responses):
            continue

        saved = saved_responses.get(qid, {})

        with st.container(border=True):
            # En-tête question
            col_q, col_na = st.columns([5, 1])
            with col_q:
                st.markdown(f"**{q['question_label']}**")
                if q.get("question_help"):
                    st.caption(q["question_help"])

            # Checkbox N/A
            is_na = False
            if q.get("na_allowed", False):
                with col_na:
                    is_na = st.checkbox(
                        "N/A",
                        value=saved.get("is_na", False),
                        key=f"na_{qid}"
                    )

            if is_na:
                new_responses[qid] = {
                    "label": None, "score": None,
                    "is_na": True, "selected_choice": None, "answer_text": ""
                }
                all_responses[qid] = new_responses[qid]
                continue

            # ── single_choice ─────────────────────────────────────────────
            if q.get("type_reponse") == "single_choice":
                choices = q.get("choices", [])
                labels = [c["label"] for c in choices]

                saved_label = saved.get("label")
                default_idx = labels.index(saved_label) if saved_label in labels else 0

                selected_label = st.radio(
                    qid,
                    labels,
                    index=default_idx,
                    key=f"radio_{qid}",
                    label_visibility="collapsed",
                )
                selected_score = next(
                    (c["score"] for c in choices if c["label"] == selected_label), None
                )
                new_responses[qid] = {
                    "label": selected_label,
                    "score": selected_score,
                    "is_na": False,
                    "selected_choice": selected_label,
                    "answer_text": ""
                }
                all_responses[qid] = new_responses[qid]

            # ── text (evidence) ───────────────────────────────────────────
            elif q.get("type_reponse") == "text":
                answer_text = st.text_area(
                    "Votre réponse",
                    value=saved.get("answer_text", ""),
                    key=f"text_{qid}",
                    label_visibility="collapsed",
                    placeholder="Décrivez les éléments de preuve...",
                )
                new_responses[qid] = {
                    "label": None, "score": None,
                    "is_na": False, "selected_choice": None,
                    "answer_text": answer_text
                }
                all_responses[qid] = new_responses[qid]

    st.divider()

# ── Sauvegarde ────────────────────────────────────────────────────────────────
def save_responses(session, responses_to_save, assessment_id, status=None):
    for qid, resp in responses_to_save.items():
        q_meta = next((q for q in questions if q["question_id"] == qid), {})
        existing = (
            session.query(Response)
            .filter(Response.assessment_id == assessment_id, Response.question_id == qid)
            .first()
        )
        data = dict(
            question_type=q_meta.get("question_type", ""),
            selected_label=resp.get("label"),
            selected_score=resp.get("score"),
            answer_text=resp.get("answer_text", ""),
            is_na=resp.get("is_na", False),
        )
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
        else:
            session.add(Response(assessment_id=assessment_id, question_id=qid, **data))

    if status:
        assessment = session.query(Assessment).get(assessment_id)
        if assessment:
            assessment.status = status
    session.commit()


col_save, col_complete = st.columns(2)

with col_save:
    if st.button("💾 Sauvegarder", type="secondary", use_container_width=True):
        session = get_session()
        try:
            save_responses(session, new_responses, assessment_id)
            st.success("Progression sauvegardée !")
        finally:
            session.close()

with col_complete:
    if st.button("✅ Terminer l'assessment", type="primary", use_container_width=True):
        session = get_session()
        try:
            save_responses(session, new_responses, assessment_id, status="completed")
            st.success("Assessment terminé ! Consultez les résultats.")
        finally:
            session.close()

# ── Sidebar scores live ───────────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.subheader("📊 Scores en direct")

scores = compute_scores(questions, all_responses)
global_score = scores.get("global_score")

if global_score is not None:
    st.sidebar.metric("Score global", f"{global_score}%")
    maturity = next(
        (m for m in MATURITY_LEVELS if m["min"] <= global_score <= m["max"]),
        MATURITY_LEVELS[-1]
    )
    st.sidebar.caption(f"Niveau : {maturity['label']}")

    for domain, score in scores["domains"].items():
        if score is not None:
            st.sidebar.progress(score / 100, text=f"{domain}: {score}%")
else:
    st.sidebar.caption("Répondez aux questions pour voir le score.")