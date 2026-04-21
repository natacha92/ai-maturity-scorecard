import streamlit as st
from pathlib import Path
from models.database import (
    init_db, get_session, Client, Assessment, Response, Attachment,
    DocumentReview, load_document_reviews, load_responses_for_scoring,
)
from src.data_loader import load_questionnaire_cached, get_domains, get_specific_domains
from engine.rules import parse_rule
from engine.scoring import compute_scores, compute_completion, MATURITY_LEVELS
import json
from datetime import datetime, timezone

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

    # Tags prédéfinis par thème
    PAIN_TAGS = [
        "Double saisie", "Pas de visibilité", "Trop manuel",
        "Dépendance à une personne", "Mauvaise qualité de données",
        "Outil mal utilisé", "Pas de standard", "Silotage"
    ]
    WEAKNESS_TAGS = [
        "Pas de documentation", "Pas de gouvernance",
        "Architecture fragile", "Pas de standardisation",
        "Dépendance humaine", "Dette technique"
    ]
    STRENGTH_TAGS = [
        "ERP bien en place", "Équipe engagée",
        "Bonne base technique", "Bonne adoption",
        "Expertise interne", "Processus documentés"
    ]
    OPPORTUNITY_TAGS = [
        "Automatisation possible", "Quick win identifié",
        "Gain rapide", "Levier ROI fort", "Partenaire disponible"
    ]
    RISK_TAGS = [
        "Résistance au changement", "Budget insuffisant",
        "Dette technique", "Dépendance fournisseur",
        "Manque de compétences", "Réglementation"
    ]
# ── Dans la boucle de rendu des questions ────────────────────────────────────

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

        # Les applicability → rendu minimal, pas de bloc insights
        if qtype == "applicability":
            saved = saved_responses.get(qid, {})
            with st.container(border=True):
                st.markdown(f"**{q['question_label']}**")
                choices = q.get("choices", [])
                labels = [c["label"] for c in choices]
                saved_label = saved.get("label")
                default_idx = labels.index(saved_label) if saved_label in labels else 0
                selected_label = st.radio(
                    qid, labels, index=default_idx,
                    key=f"radio_{qid}", label_visibility="collapsed"
                )
                selected_score = next(
                    (c["score"] for c in choices if c["label"] == selected_label), None
                )
                new_responses[qid] = {
                    "label": selected_label, "score": selected_score,
                    "is_na": False, "selected_choice": selected_label, "answer_text": ""
                }
                all_responses[qid] = new_responses[qid]
            continue

        saved = saved_responses.get(qid, {})

        with st.container(border=True):
            # En-tête question
            col_q, col_na = st.columns([5, 1])
            with col_q:
                st.markdown(f"**{q['question_label']}**")
                if qtype == "evidence" and q.get("documents_attendus"):
                    # Affiche les documents attendus avec badge obligatoire/optionnel
                    docs_preview = q["documents_attendus"]
                    parts_obl = [d["label"] for d in docs_preview if d.get("obligatoire")]
                    parts_opt = [d["label"] for d in docs_preview if not d.get("obligatoire")]
                    if parts_obl:
                        st.caption(f"🔴 **Obligatoires :** {', '.join(parts_obl)}")
                    if parts_opt:
                        st.caption(f"🟡 **Optionnels :** {', '.join(parts_opt)}")
                elif q.get("question_help"):
                    st.caption(q["question_help"])
                    
            # ── Expander "En savoir plus" ─────────────────────────────────
            if qtype == "scored" and any([
                q.get("description_niveau"),
                q.get("outils_necessaires"),
                q.get("niveau_label"),
            ]):
                with st.expander("📖 En savoir plus sur ce niveau"):
                    if q.get("niveau_label"):
                        st.markdown(f"**{q['niveau_label']}**")
                    if q.get("description_niveau"):
                        st.markdown(q["description_niveau"])

                    col_a, col_b = st.columns(2)
                    with col_a:
                        if q.get("outils_necessaires"):
                            st.markdown("**🔧 Outils nécessaires**")
                            for o in q["outils_necessaires"]:
                                st.markdown(f"- {o}")
                    with col_b:
                        if q.get("outils_optionnels"):
                            st.markdown("**⚙️ Optionnels**")
                            for o in q["outils_optionnels"]:
                                st.markdown(f"- {o}")

                    if q.get("dependances_inter_domaines"):
                        st.info(f"🔗 **Dépendances :** {q['dependances_inter_domaines']}")
                    if q.get("conditions_progression"):
                        st.success(f"🎯 **Progression :** {q['conditions_progression']}")
                    if q.get("pre_requis_metier") and q["pre_requis_metier"] != "Aucun":
                        st.warning(f"⚠️ **Pré-requis :** {q['pre_requis_metier']}")
            

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



        # ── Bloc Contexte + Insights (scored ET evidence) ─────────────
        if qtype in ("scored", "evidence"):
            with st.expander("🧩 Contexte & Insights", expanded=False):
                
                confidence_options = {
                    "Élevée": 1.0,
                    "Moyenne": 0.75,
                    "Faible": 0.5,
                }

                saved_confidence = saved.get("consultant_confidence", 1.0)
                saved_confidence_label = next(
                    (label for label, value in confidence_options.items() if value == saved_confidence),
                    "Élevée"
                )

                consultant_confidence_label = st.selectbox(
                    "🎯 Niveau de confiance du consultant",
                    options=list(confidence_options.keys()),
                    index=list(confidence_options.keys()).index(saved_confidence_label),
                    key=f"confidence_{qid}",
                    help="Mesure la fiabilité de la réponse au regard des preuves disponibles."
                )

                consultant_confidence = confidence_options[consultant_confidence_label]
                
                # Outils actuels
                tools_raw = saved.get("current_tools", [])
                tools_val = st.text_input(
                    "🔧 Outils en place (séparés par virgule)",
                    value=", ".join(tools_raw) if tools_raw else "",
                    key=f"tools_{qid}",
                    placeholder="SAP, Excel, Power BI..."
                )

                # Documents
                docs_raw = saved.get("current_documents", [])
                docs_val = st.text_input(
                    "📄 Documents / process existants",
                    value=", ".join(docs_raw) if isinstance(docs_raw, list) else "",
                    key=f"docs_{qid}",
                    placeholder="Procédures, chartes, SLA..."
                )

                st.markdown("**🔥 Analyse rapide** *(multi-select + texte libre)*")

                col_pain, col_weak = st.columns(2)
                with col_pain:
                    pain_sel = st.multiselect(
                        "🟥 Douleurs",
                        PAIN_TAGS + ["Autre"],
                        default=[p for p in saved.get("pain_points", []) if p in PAIN_TAGS + ["Autre"]],
                        key=f"pain_{qid}"
                    )
                    pain_other = st.text_input("Autre douleur", key=f"pain_other_{qid}",
                                               value="" , label_visibility="collapsed",
                                               placeholder="Précisez...") if "Autre" in pain_sel else ""

                with col_weak:
                    weak_sel = st.multiselect(
                        "🟧 Faiblesses",
                        WEAKNESS_TAGS + ["Autre"],
                        default=[w for w in saved.get("weaknesses", []) if w in WEAKNESS_TAGS + ["Autre"]],
                        key=f"weak_{qid}"
                    )
                    weak_other = st.text_input("Autre faiblesse", key=f"weak_other_{qid}",
                                               value="", label_visibility="collapsed",
                                               placeholder="Précisez...") if "Autre" in weak_sel else ""

                col_str2, col_opp = st.columns(2)
                with col_str2:
                    str_sel = st.multiselect(
                        "🟩 Forces",
                        STRENGTH_TAGS + ["Autre"],
                        default=[s for s in saved.get("strengths", []) if s in STRENGTH_TAGS + ["Autre"]],
                        key=f"str_{qid}"
                    )
                    str_other = st.text_input("Autre force", key=f"str_other_{qid}",
                                              value="", label_visibility="collapsed",
                                              placeholder="Précisez...") if "Autre" in str_sel else ""

                with col_opp:
                    opp_sel = st.multiselect(
                        "🟦 Opportunités",
                        OPPORTUNITY_TAGS + ["Autre"],
                        default=[o for o in saved.get("opportunities", []) if o in OPPORTUNITY_TAGS + ["Autre"]],
                        key=f"opp_{qid}"
                    )
                    opp_other = st.text_input("Autre opportunité", key=f"opp_other_{qid}",
                                              value="", label_visibility="collapsed",
                                              placeholder="Précisez...") if "Autre" in opp_sel else ""

                risk_sel = st.multiselect(
                    "🟪 Risques",
                    RISK_TAGS + ["Autre"],
                    default=[r for r in saved.get("risks", []) if r in RISK_TAGS + ["Autre"]],
                    key=f"risk_{qid}"
                )
                risk_other = st.text_input("Autre risque", key=f"risk_other_{qid}",
                                           value="", label_visibility="collapsed",
                                           placeholder="Précisez...") if "Autre" in risk_sel else ""

                consultant_note = st.text_area(
                    "📝 Note consultant",
                    value=saved.get("consultant_note", ""),
                    key=f"note_{qid}",
                    placeholder="Observations, nuances, contexte interne...",
                    height=80,
                )

            # Consolidation dans new_responses
            def _merge(sel, other):
                return [x for x in sel if x != "Autre"] + ([other] if other.strip() else [])

            new_responses[qid].update({
                "current_tools":     [t.strip() for t in tools_val.split(",") if t.strip()],
                "current_documents": [d.strip() for d in docs_val.split(",") if d.strip()],
                "pain_points":       _merge(pain_sel, pain_other),
                "weaknesses":        _merge(weak_sel, weak_other),
                "strengths":         _merge(str_sel, str_other),
                "opportunities":     _merge(opp_sel, opp_other),
                "risks":             _merge(risk_sel, risk_other),
                "consultant_confidence": consultant_confidence,
                "consultant_note":   consultant_note,
            })

        # ── Pièces jointes (dans la boucle for q, hors container) ─
        uploaded_files = st.file_uploader(
            "📎 Ajouter des preuves",
            key=f"upload_{qid}",
            accept_multiple_files=True,
            help="Images, PDF, Word, Excel..."
        )

        if uploaded_files and assessment_id:
            attach_dir = Path(f"data/attachments/{assessment_id}/{qid}")
            attach_dir.mkdir(parents=True, exist_ok=True)

            session = get_session()
            try:
                for uf in uploaded_files:
                    filepath = attach_dir / uf.name
                    if not filepath.exists():
                        with open(filepath, "wb") as f:
                            f.write(uf.getbuffer())
                        session.add(Attachment(
                            assessment_id=assessment_id,
                            question_id=qid,
                            filename=uf.name,
                            filepath=str(filepath),
                            mimetype=uf.type or "",
                        ))
                session.commit()
            finally:
                session.close()

        # Affiche les pièces jointes existantes
        if assessment_id:
            session = get_session()
            try:
                existing_attachments = (
                    session.query(Attachment)
                    .filter_by(assessment_id=assessment_id, question_id=qid)
                    .all()
                )
                if existing_attachments:
                    st.caption(f"📁 {len(existing_attachments)} fichier(s) déjà attaché(s)")
                    for att in existing_attachments:
                        col_f, col_d = st.columns([4, 1])
                        with col_f:
                            st.caption(f"📄 {att.filename}")
                        with col_d:
                            if Path(att.filepath).exists():
                                with open(att.filepath, "rb") as f:
                                    st.download_button(
                                        "⬇️",
                                        data=f.read(),
                                        file_name=att.filename,
                                        key=f"dl_{att.id}",
                                    )
            finally:
                session.close()

        # ── Analyse documentaire (questions evidence uniquement) ──
        if qtype == "evidence" and assessment_id:
            with st.expander("🔍 Analyse documentaire", expanded=False):

                STATUS_OPTIONS     = ["non_vérifié", "conforme", "partiel", "absent"]
                STATUS_ICONS       = {"non_vérifié": "⬜", "conforme": "✅", "partiel": "⚠️", "absent": "❌"}
                CONFIDENCE_OPTIONS = ["Élevée", "Moyenne", "Faible"]

                # Documents attendus définis dans le JSON de la question
                docs_attendus = q.get("documents_attendus", [])

                # Charge les reviews existants et les fichiers uploadés
                session = get_session()
                try:
                    existing_reviews = (
                        session.query(DocumentReview)
                        .filter_by(assessment_id=assessment_id, question_id=qid)
                        .order_by(DocumentReview.id)
                        .all()
                    )
                    existing_reviews_data = [r.to_dict() for r in existing_reviews]
                    attachments_for_q = (
                        session.query(Attachment)
                        .filter_by(assessment_id=assessment_id, question_id=qid)
                        .all()
                    )
                    att_map = {a.id: a.filename for a in attachments_for_q}
                finally:
                    session.close()

                # Index des reviews existants par doc_id pour lookup rapide
                reviews_by_doc_id = {
                    r["doc_id"]: r
                    for r in existing_reviews_data
                    if r.get("doc_id")
                }
                # Reviews libres (sans doc_id = ajoutés manuellement)
                free_reviews = [r for r in existing_reviews_data if not r.get("doc_id")]

                # Sélecteur de fichier réutilisable
                att_options = ["— Aucun fichier lié —"] + [
                    f"{aid} — {fname}" for aid, fname in att_map.items()
                ]

                def _get_att_id(selected_str):
                    if selected_str == "— Aucun fichier lié —":
                        return None
                    try:
                        return int(selected_str.split(" — ")[0])
                    except (ValueError, IndexError):
                        return None

                def _render_review_form(rev, key_prefix):
                    """Affiche le formulaire d'analyse pour un review existant."""
                    rid  = rev["id"]
                    icon = STATUS_ICONS.get(rev["status"], "⬜")
                    st.markdown(f"**{icon} {rev['document_label']}**")

                    col_s, col_c = st.columns([2, 2])
                    with col_s:
                        new_status = st.selectbox(
                            "Statut",
                            STATUS_OPTIONS,
                            index=STATUS_OPTIONS.index(rev["status"])
                                  if rev["status"] in STATUS_OPTIONS else 0,
                            key=f"{key_prefix}_status_{rid}",
                            format_func=lambda x: f"{STATUS_ICONS[x]} {x.replace('_',' ').capitalize()}",
                        )
                    with col_c:
                        new_confidence = st.selectbox(
                            "Confiance expert",
                            CONFIDENCE_OPTIONS,
                            index=CONFIDENCE_OPTIONS.index(rev["expert_confidence"])
                                  if rev["expert_confidence"] in CONFIDENCE_OPTIONS else 1,
                            key=f"{key_prefix}_conf_{rid}",
                        )

                    # Lier à un fichier uploadé
                    current_att = next(
                        (f"{aid} — {fname}" for aid, fname in att_map.items()
                         if aid == rev.get("attachment_id")),
                        "— Aucun fichier lié —"
                    )
                    linked_att = st.selectbox(
                        "📎 Fichier lié",
                        att_options,
                        index=att_options.index(current_att) if current_att in att_options else 0,
                        key=f"{key_prefix}_att_{rid}",
                    )

                    # Points à valider (tirés du JSON) → guide l'auditeur
                    # On récupère le doc correspondant depuis docs_attendus
                    _doc_meta = next(
                        (d for d in docs_attendus if d.get("doc_id") == rev.get("doc_id")),
                        None
                    )
                    if _doc_meta and _doc_meta.get("points_a_valider"):
                        with st.container():
                            st.markdown("**🔎 Points à vérifier dans ce document**")
                            for pt in _doc_meta["points_a_valider"]:
                                st.caption(f"• {pt}")

                    new_trouves = st.text_area(
                        "✅ Éléments trouvés",
                        value=rev["elements_trouves"],
                        key=f"{key_prefix}_found_{rid}",
                        placeholder="Ex : politique datée mars 2024, rôles définis p.3...",
                        height=70,
                    )
                    new_manquants = st.text_area(
                        "❌ Éléments manquants",
                        value=rev["elements_manquants"],
                        key=f"{key_prefix}_miss_{rid}",
                        placeholder="Ex : aucune procédure de révision, DPO non nommé...",
                        height=70,
                    )
                    new_obs = st.text_area(
                        "📝 Observation",
                        value=rev["observation"],
                        key=f"{key_prefix}_obs_{rid}",
                        placeholder="Qualité globale, contexte, nuances...",
                        height=55,
                    )

                    col_save_r, col_del_r = st.columns([3, 1])
                    with col_save_r:
                        if st.button("💾 Sauvegarder", key=f"{key_prefix}_save_{rid}"):
                            session = get_session()
                            try:
                                db_rev = session.query(DocumentReview).get(rid)
                                if db_rev:
                                    db_rev.status             = new_status
                                    db_rev.expert_confidence  = new_confidence
                                    db_rev.attachment_id      = _get_att_id(linked_att)
                                    db_rev.elements_trouves   = new_trouves
                                    db_rev.elements_manquants = new_manquants
                                    db_rev.observation        = new_obs
                                    db_rev.reviewed_at        = datetime.now(timezone.utc)
                                    session.commit()
                                    st.success("Analyse sauvegardée !")
                            finally:
                                session.close()
                    with col_del_r:
                        if st.button("🗑️", key=f"{key_prefix}_del_{rid}", help="Supprimer"):
                            session = get_session()
                            try:
                                db_rev = session.query(DocumentReview).get(rid)
                                if db_rev:
                                    session.delete(db_rev)
                                    session.commit()
                                    st.rerun()
                            finally:
                                session.close()

                # ── Section 1 : Documents attendus (depuis le JSON) ──
                if docs_attendus:
                    st.markdown("**📋 Documents attendus pour cette question**")
                    for doc in docs_attendus:
                        doc_id    = doc["doc_id"]
                        badge     = "🔴 obligatoire" if doc["obligatoire"] else "🟡 optionnel"
                        rev = reviews_by_doc_id.get(doc_id)

                        with st.container(border=True):
                            col_lbl, col_badge = st.columns([5, 2])
                            with col_lbl:
                                st.markdown(f"**{doc['label']}**")
                                if doc.get("description"):
                                    st.caption(doc["description"])
                            with col_badge:
                                st.caption(badge)

                            if rev:
                                # Review existant → affiche le formulaire
                                _render_review_form(rev, key_prefix=f"da_{qid}_{doc_id}")
                            else:
                                # Pas encore de review → bouton pour créer
                                col_init, col_att = st.columns([2, 3])
                                with col_init:
                                    init_status = st.selectbox(
                                        "Statut initial",
                                        STATUS_OPTIONS,
                                        key=f"init_status_{qid}_{doc_id}",
                                        format_func=lambda x: f"{STATUS_ICONS[x]} {x.replace('_',' ').capitalize()}",
                                    )
                                with col_att:
                                    linked_att_new = st.selectbox(
                                        "📎 Fichier lié (optionnel)",
                                        att_options,
                                        key=f"init_att_{qid}_{doc_id}",
                                    )
                                if st.button(
                                    f"➕ Commencer l'analyse",
                                    key=f"create_rev_{qid}_{doc_id}"
                                ):
                                    session = get_session()
                                    try:
                                        session.add(DocumentReview(
                                            assessment_id  = assessment_id,
                                            question_id    = qid,
                                            doc_id         = doc_id,
                                            document_label = doc["label"],
                                            attachment_id  = _get_att_id(linked_att_new),
                                            status         = init_status,
                                        ))
                                        session.commit()
                                        st.rerun()
                                    finally:
                                        session.close()

                # ── Section 2 : Documents libres (ajoutés manuellement) ──
                st.markdown("---")
                st.markdown("**➕ Ajouter un document non listé**")
                st.caption(
                    "Pour un document non prévu dans la liste ci-dessus "
                    "(version alternative, document interne spécifique...)."
                )

                if free_reviews:
                    for rev in free_reviews:
                        with st.container(border=True):
                            _render_review_form(rev, key_prefix=f"free_{qid}")

                col_fl, col_fa = st.columns([3, 2])
                with col_fl:
                    new_doc_label = st.text_input(
                        "Nom du document",
                        key=f"free_label_{qid}",
                        placeholder="Ex : Note interne sur la gouvernance",
                    )
                with col_fa:
                    free_att = st.selectbox(
                        "📎 Fichier lié (optionnel)",
                        att_options,
                        key=f"free_att_{qid}",
                    )
                if st.button("➕ Ajouter", key=f"add_free_{qid}") and new_doc_label.strip():
                    session = get_session()
                    try:
                        session.add(DocumentReview(
                            assessment_id  = assessment_id,
                            question_id    = qid,
                            doc_id         = None,   # document libre
                            document_label = new_doc_label.strip(),
                            attachment_id  = _get_att_id(free_att),
                            status         = "non_vérifié",
                        ))
                        session.commit()
                        st.rerun()
                    finally:
                        session.close()

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
            question_type      = q_meta.get("question_type", ""),
            selected_label     = resp.get("label"),
            selected_score     = resp.get("score"),
            answer_text        = resp.get("answer_text", ""),
            is_na              = resp.get("is_na", False),
            current_tools      = json.dumps(resp.get("current_tools", [])),
            current_documents  = json.dumps(resp.get("current_documents", [])),
            pain_points        = json.dumps(resp.get("pain_points", [])),
            weaknesses         = json.dumps(resp.get("weaknesses", [])),
            strengths          = json.dumps(resp.get("strengths", [])),
            opportunities      = json.dumps(resp.get("opportunities", [])),
            risks              = json.dumps(resp.get("risks", [])),
            consultant_confidence=resp.get("consultant_confidence", 1.0),
            consultant_note    = resp.get("consultant_note", ""),
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

doc_reviews_live = load_document_reviews(assessment_id) if assessment_id else {}
scores = compute_scores(questions, all_responses, document_reviews=doc_reviews_live)
global_score = scores.get("global_score")

if scores.get("avg_confidence") is not None:
    st.sidebar.metric("Confiance moyenne", f"{int(scores['avg_confidence'] * 100)}%")

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