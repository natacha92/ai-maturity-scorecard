import streamlit as st
from pathlib import Path
from models.database import (
    init_db, get_session, Client, Assessment, DocumentReview,
    load_document_reviews, compute_document_coverage,
)
from src.data_loader import load_questionnaire_cached
import pandas as pd

init_db()

QUESTIONNAIRE_PATH = str(Path("data/questionnaire.json"))

st.title("📋 Audit Documentaire")
st.caption(
    "Vue d'ensemble de l'analyse des documents fournis par le client. "
    "Chaque ligne correspond à un document analysé sur une question de preuve (evidence)."
)

# ── Sélection de l'assessment ─────────────────────────────────────────────────
session = get_session()
try:
    assessments = (
        session.query(Assessment)
        .filter(Assessment.status.in_(["in_progress", "completed"]))
        .order_by(Assessment.updated_at.desc())
        .all()
    )
    options = []
    for a in assessments:
        client = session.query(Client).get(a.client_id)
        options.append({
            "id":    a.id,
            "label": f"{a.name} — {client.name if client else 'Inconnu'}",
        })
finally:
    session.close()

if not options:
    st.info("Aucun assessment en cours ou terminé.")
    st.page_link("pages/2_Questionnaire.py", label="Créer un assessment", icon="📋")
    st.stop()

labels = [o["label"] for o in options]
selected_label = st.selectbox("Assessment", labels)
selected = options[labels.index(selected_label)]
assessment_id = selected["id"]

# ── Chargement des données ────────────────────────────────────────────────────
questions    = load_questionnaire_cached(QUESTIONNAIRE_PATH)
reviews_map  = load_document_reviews(assessment_id)   # {qid: [review_dict, ...]}
coverage     = compute_document_coverage(assessment_id)

# Index des questions evidence par qid pour lookup rapide
evidence_qs = {
    q["question_id"]: q
    for q in questions
    if q.get("question_type") == "evidence"
}

# ── Métriques globales ────────────────────────────────────────────────────────
st.divider()
g = coverage["global"]

if g["total"] == 0:
    st.info(
        "Aucun document analysé pour cet assessment. "
        "Allez dans le questionnaire, ouvrez une question de preuve et cliquez sur "
        "**🔍 Analyse documentaire** pour commencer."
    )
else:
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Taux de couverture", f"{g['taux']}%" if g['taux'] is not None else "N/A")
    col2.metric("✅ Conformes",  g["conforme"])
    col3.metric("⚠️ Partiels",   g["partiel"])
    col4.metric("❌ Absents",    g["absent"])
    col5.metric("Total analysés", g["total"])

    # Barre de couverture globale
    if g["taux"] is not None:
        st.progress(
            g["taux"] / 100,
            text=f"Couverture documentaire globale : {g['taux']}%"
        )

st.divider()

# ── Filtres ───────────────────────────────────────────────────────────────────
STATUS_ICONS = {
    "non_vérifié": "⬜ Non vérifié",
    "conforme":    "✅ Conforme",
    "partiel":     "⚠️ Partiel",
    "absent":      "❌ Absent",
}

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    filter_domain = st.selectbox(
        "Filtrer par domaine",
        ["Tous"] + sorted({q.get("domaine_principal", "") for q in evidence_qs.values()}),
    )
with col_f2:
    filter_status = st.multiselect(
        "Filtrer par statut",
        list(STATUS_ICONS.values()),
        default=list(STATUS_ICONS.values()),
    )
with col_f3:
    filter_only_with_reviews = st.checkbox(
        "Uniquement les questions avec documents analysés",
        value=False,
    )

# Statuts sélectionnés (valeurs brutes)
selected_statuses = [k for k, v in STATUS_ICONS.items() if v in filter_status]

# ── Tableau de synthèse ───────────────────────────────────────────────────────
st.subheader("📄 Détail par document")

rows = []
for qid, q in evidence_qs.items():
    # Filtre domaine
    if filter_domain != "Tous" and q.get("domaine_principal") != filter_domain:
        continue

    q_reviews = reviews_map.get(qid, [])

    # Filtre "uniquement avec reviews"
    if filter_only_with_reviews and not q_reviews:
        continue

    if not q_reviews:
        # Question sans aucun document analysé
        if "non_vérifié" not in selected_statuses:
            continue
        rows.append({
            "Domaine":            q.get("domaine_principal", ""),
            "Sous-domaine":       q.get("domaine_specifique", ""),
            "Question":           q.get("question_label", "")[:80] + "...",
            "question_id":        qid,
            "Document":           "— Aucun document ajouté —",
            "Statut":             "⬜ Non vérifié",
            "Éléments trouvés":   "",
            "Éléments manquants": "",
            "Confiance expert":   "",
            "Observation":        "",
            "review_id":          None,
        })
    else:
        for rev in q_reviews:
            if rev["status"] not in selected_statuses:
                continue
            rows.append({
                "Domaine":            q.get("domaine_principal", ""),
                "Sous-domaine":       q.get("domaine_specifique", ""),
                "Question":           q.get("question_label", "")[:80] + "...",
                "question_id":        qid,
                "Document":           rev["document_label"],
                "Statut":             STATUS_ICONS.get(rev["status"], rev["status"]),
                "Éléments trouvés":   rev["elements_trouves"],
                "Éléments manquants": rev["elements_manquants"],
                "Confiance expert":   rev["expert_confidence"],
                "Observation":        rev["observation"],
                "review_id":          rev["id"],
            })

if not rows:
    st.info("Aucun document correspondant aux filtres sélectionnés.")
else:
    # ── Vue par sous-domaine ─────────────────────────────────────
    df = pd.DataFrame(rows)

    for domain in df["Domaine"].unique():
        df_domain = df[df["Domaine"] == domain]

        # Calcule le taux de conformité du domaine
        status_vals = df_domain["Statut"].tolist()
        score_map   = {"✅ Conforme": 1.0, "⚠️ Partiel": 0.5, "❌ Absent": 0.0}
        scores_d    = [score_map[s] for s in status_vals if s in score_map]
        taux_d      = round(sum(scores_d) / len(scores_d) * 100) if scores_d else None

        taux_str = f" — {taux_d}%" if taux_d is not None else ""
        with st.expander(f"📂 {domain}{taux_str}", expanded=True):

            for subdom in df_domain["Sous-domaine"].unique():
                df_sub = df_domain[df_domain["Sous-domaine"] == subdom]
                scores_s = [score_map[s] for s in df_sub["Statut"].tolist() if s in score_map]
                taux_s   = round(sum(scores_s) / len(scores_s) * 100) if scores_s else None

                st.markdown(
                    f"**{subdom}**"
                    + (f" — {taux_s}%" if taux_s is not None else "")
                )

                for _, row in df_sub.iterrows():
                    with st.container(border=True):
                        col_q, col_d, col_s = st.columns([4, 3, 2])
                        with col_q:
                            st.markdown(f"*{row['Question']}*")
                            st.caption(row["question_id"])
                        with col_d:
                            st.markdown(f"📄 **{row['Document']}**")
                            if row["Confiance expert"]:
                                st.caption(f"Confiance : {row['Confiance expert']}")
                        with col_s:
                            st.markdown(f"### {row['Statut']}")

                        if row["Éléments trouvés"] or row["Éléments manquants"] or row["Observation"]:
                            col_e1, col_e2 = st.columns(2)
                            with col_e1:
                                if row["Éléments trouvés"]:
                                    st.markdown("**✅ Éléments trouvés**")
                                    st.caption(row["Éléments trouvés"])
                            with col_e2:
                                if row["Éléments manquants"]:
                                    st.markdown("**❌ Éléments manquants**")
                                    st.caption(row["Éléments manquants"])
                            if row["Observation"]:
                                st.info(f"📝 {row['Observation']}")

                st.divider()

    # ── Export CSV ────────────────────────────────────────────────
    st.subheader("📥 Export")
    export_cols = [
        "Domaine", "Sous-domaine", "Question", "Document",
        "Statut", "Éléments trouvés", "Éléments manquants",
        "Confiance expert", "Observation"
    ]
    csv = df[export_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Exporter la grille d'audit (CSV)",
        data=csv,
        file_name=f"audit_documentaire_{assessment_id}.csv",
        mime="text/csv",
        use_container_width=True,
    )

# ── Vue par statut (résumé) ───────────────────────────────────────────────────
if rows:
    st.divider()
    st.subheader("📊 Résumé par statut")

    df_full = pd.DataFrame(rows)
    status_counts = df_full["Statut"].value_counts().reset_index()
    status_counts.columns = ["Statut", "Nombre"]
    st.dataframe(status_counts, use_container_width=True, hide_index=True)

    # Questions sans aucun document analysé
    all_evidence_qids  = set(evidence_qs.keys())
    reviewed_qids      = set(reviews_map.keys())
    unreviewed_qids    = all_evidence_qids - reviewed_qids

    if unreviewed_qids:
        st.warning(
            f"**{len(unreviewed_qids)} questions de preuve sans aucun document analysé.** "
            "Ajoutez des documents dans le questionnaire pour compléter l'audit."
        )
        with st.expander("Voir les questions non analysées"):
            for qid in sorted(unreviewed_qids):
                q = evidence_qs.get(qid, {})
                st.markdown(
                    f"- **{qid}** — {q.get('domaine_specifique', '')} — "
                    f"{q.get('question_label', '')[:70]}..."
                )