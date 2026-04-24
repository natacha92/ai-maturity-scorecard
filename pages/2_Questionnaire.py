import streamlit as st
from pathlib import Path
from models.database import (
    init_db, get_session, Client, Assessment, Response, Attachment,
    DocumentReview, load_document_reviews,
)
from src.data_loader import load_questionnaire_cached, get_domains, get_specific_domains
from engine.rules import parse_rule
from engine.scoring import compute_scores, compute_completion, MATURITY_LEVELS
import json
from datetime import datetime, timezone

init_db()
QUESTIONNAIRE_PATH = str(Path("data/questionnaire.json"))

# ── Tags prédéfinis ────────────────────────────────────────────────────────────
PAIN_TAGS        = ["Double saisie","Pas de visibilité","Trop manuel","Dépendance à une personne",
                    "Mauvaise qualité de données","Outil mal utilisé","Pas de standard","Silotage"]
WEAKNESS_TAGS    = ["Pas de documentation","Pas de gouvernance","Architecture fragile",
                    "Pas de standardisation","Dépendance humaine","Dette technique"]
STRENGTH_TAGS    = ["ERP bien en place","Equipe engagée","Bonne base technique",
                    "Bonne adoption","Expertise interne","Processus documentés"]
OPPORTUNITY_TAGS = ["Automatisation possible","Quick win identifié","Gain rapide",
                    "Levier ROI fort","Partenaire disponible"]
RISK_TAGS        = ["Résistance au changement","Budget insuffisant","Dette technique",
                    "Dépendance fournisseur","Manque de compétences","Réglementation"]
CONFIDENCE_OPTIONS = {"Élevée": 1.0, "Moyenne": 0.75, "Faible": 0.5}
STATUS_OPTIONS     = ["non_vérifié","conforme","partiel","absent"]
STATUS_ICONS       = {"non_vérifié":"⬜","conforme":"✅","partiel":"⚠️","absent":"❌"}

# ── Dirty tracking : quelles questions ont été modifiées par l'utilisateur ────
if "dirty" not in st.session_state:
    st.session_state["dirty"] = set()

def mark_dirty(qid):
    st.session_state["dirty"].add(qid)

# ── Titre ──────────────────────────────────────────────────────────────────────
st.title("Questionnaire")
questions = load_questionnaire_cached(QUESTIONNAIRE_PATH)

# ── Sélection / reprise d'assessment ──────────────────────────────────────────
if st.session_state.get("assessment_id") and st.sidebar.button("Changer d'assessment"):
    st.session_state.pop("assessment_id", None)
    st.session_state["dirty"] = set()
    st.rerun()

if st.session_state.get("assessment_id"):
    assessment_id = st.session_state["assessment_id"]
    s = get_session()
    try:
        a = s.query(Assessment).get(assessment_id)
        c = s.query(Client).get(a.client_id) if a else None
        st.success(f"Assessment en cours : **{a.name}** — {c.name if c else ''}")
    finally:
        s.close()
else:
    s = get_session()
    try:
        clients_list = [{"id": c.id, "name": c.name} for c in s.query(Client).order_by(Client.name).all()]
    finally:
        s.close()

    if not clients_list:
        st.warning("Aucun client trouvé.")
        st.page_link("pages/1_Clients.py", label="Créer un client", icon="🏢")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        client_names = [c["name"] for c in clients_list]
        sel_client_name = st.selectbox("Client", client_names)
        sel_client = next(c for c in clients_list if c["name"] == sel_client_name)
    with col2:
        s = get_session()
        try:
            existing_list = [
                {"id": a.id, "name": a.name}
                for a in s.query(Assessment)
                .filter(Assessment.client_id == sel_client["id"])
                .filter(Assessment.status.in_(["draft","in_progress"]))
                .order_by(Assessment.updated_at.desc()).all()
            ]
        finally:
            s.close()
        options = ["Créer un nouvel assessment"] + [a["name"] for a in existing_list]
        choice  = st.selectbox("Assessment", options, key="assessment_selector")

    if choice == "Créer un nouvel assessment":
        name = st.text_input("Nom de l'assessment", value=f"Assessment — {sel_client_name}")
        if st.button("Démarrer"):
            s = get_session()
            try:
                a = Assessment(client_id=sel_client["id"], name=name, status="in_progress")
                s.add(a); s.commit()
                st.session_state["assessment_id"] = a.id
                st.session_state["dirty"] = set()
            finally:
                s.close()
            st.rerun()
        st.stop()
    else:
        sel = next(a for a in existing_list if a["name"] == choice)
        st.session_state["assessment_id"] = sel["id"]
        st.session_state["dirty"] = set()

assessment_id = st.session_state.get("assessment_id")
if not assessment_id:
    st.stop()

# ── Réponses sauvegardées en base ──────────────────────────────────────────────
s = get_session()
try:
    saved_responses = {
        r.question_id: r.to_scoring_dict()
        for r in s.query(Response).filter(Response.assessment_id == assessment_id).all()
    }
finally:
    s.close()

st.divider()

# ── Sélection domaine ──────────────────────────────────────────────────────────
domains        = get_domains(questions)
selected_domain= st.selectbox("Domaine", domains, key="domain_selector")
sub_domains    = get_specific_domains(questions, selected_domain)

# ── Progression live ───────────────────────────────────────────────────────────
def live_responses_for_progress():
    """Saved + dirty uniquement — sans toucher aux non-dirty."""
    live  = dict(saved_responses)
    dirty = st.session_state.get("dirty", set())
    for qid in dirty:
        if st.session_state.get(f"na_{qid}", False):
            live[qid] = {"score": None, "label": None, "is_na": True}
            continue
        radio_val = st.session_state.get(f"radio_{qid}")
        if radio_val is not None:
            q_meta = next((q for q in questions if q["question_id"] == qid), {})
            score  = next((c["score"] for c in q_meta.get("choices",[]) if c["label"] == radio_val), None)
            live[qid] = {"score": score, "label": radio_val, "is_na": False}
    return live

# Charge les document reviews pour le comptage des preuves
_s = get_session()
try:
    _doc_review_qids = {
        r.question_id
        for r in _s.query(DocumentReview).filter(
            DocumentReview.assessment_id == assessment_id,
            DocumentReview.document_remis == True
        ).all()
    }
finally:
    _s.close()

live = live_responses_for_progress()

# ── Compteurs par type de question ────────────────────────────────────────────
def count_by_type(qtype_filter):
    total, answered = 0, 0
    for q in questions:
        if q.get("question_type") not in qtype_filter:
            continue
        if q.get("domaine_principal") != selected_domain:
            continue
        if not parse_rule(q.get("applicability_rule", "always"), live):
            continue
        total += 1
        qid = q["question_id"]
        if qtype_filter == ["evidence"]:
            if qid in _doc_review_qids:
                answered += 1
        else:
            if qid in live:
                answered += 1
    return answered, total

app_ans,   app_tot   = count_by_type(["applicability"])
sc_ans,    sc_tot    = count_by_type(["scored"])
evid_ans,  evid_tot  = count_by_type(["evidence"])

app_pct  = int(app_ans  / app_tot  * 100) if app_tot  > 0 else 0
sc_pct   = int(sc_ans   / sc_tot   * 100) if sc_tot   > 0 else 0
evid_pct = int(evid_ans / evid_tot * 100) if evid_tot > 0 else 0

col_c1, col_c2, col_c3 = st.columns(3)
with col_c1:
    st.progress(app_pct / 100,
        text=f"🔘 Applicabilité : {app_ans}/{app_tot} ({app_pct}%)")
with col_c2:
    st.progress(sc_pct / 100,
        text=f"📝 Questions notées : {sc_ans}/{sc_tot} ({sc_pct}%)")
with col_c3:
    if evid_tot > 0:
        st.progress(evid_pct / 100,
            text=f"📁 Preuves analysées : {evid_ans}/{evid_tot} ({evid_pct}%)")

st.subheader(f"📋 {selected_domain}")

# ── all_responses : applicabilité dynamique ────────────────────────────────────
# On part des réponses sauvegardées, puis on y ajoute les valeurs actuelles
# des widgets APP depuis st.session_state (uniquement si l'utilisateur a interagi).
all_responses = dict(saved_responses)

for q in questions:
    if q.get("question_type") != "applicability":
        continue
    qid = q["question_id"]
    radio_val = st.session_state.get(f"radio_{qid}")
    if radio_val is not None:
        choices = q.get("choices", [])
        score   = next((c["score"] for c in choices if c["label"] == radio_val), None)
        all_responses[qid] = {"label": radio_val, "score": score, "is_na": False}

# ── Rendu ──────────────────────────────────────────────────────────────────────
for sub_domain in sub_domains:
    st.markdown(f"### {sub_domain}")
    sub_questions = [
        q for q in questions
        if q.get("domaine_principal") == selected_domain
        and q.get("domaine_specifique") == sub_domain
    ]

    for q in sub_questions:
        qid   = q["question_id"]
        qtype = q.get("question_type")
        if not parse_rule(q.get("applicability_rule","always"), all_responses):
            continue
        saved = saved_responses.get(qid, {})

        # Calcul de l'état de la question
        dirty = st.session_state.get("dirty", set())
        if qid in dirty:
            q_status = "🔄"
        elif qid in saved_responses:
            q_status = "✅"
        else:
            q_status = "⬜"

        # APPLICABILITY
        if qtype == "applicability":
            with st.container(border=True):
                col_lbl, col_st = st.columns([5, 1])
                with col_lbl:
                    st.markdown(f"**{q['question_label']}**")
                with col_st:
                    st.markdown(f"<div style='text-align:right'>{q_status}</div>", unsafe_allow_html=True)
                choices = q.get("choices", [])
                labels  = [c["label"] for c in choices]
                saved_lbl   = saved.get("label")
                # index=None si jamais répondu → aucune option pré-sélectionnée
                if saved_lbl in labels:
                    default_idx = labels.index(saved_lbl)
                else:
                    default_idx = None
                sel_label = st.radio(qid, labels, index=default_idx,
                    key=f"radio_{qid}", label_visibility="collapsed",
                    on_change=mark_dirty, args=(qid,))
                if sel_label is not None:
                    # Marque dirty si valeur différente du sauvegardé
                    if sel_label != saved_lbl and qid not in dirty:
                        mark_dirty(qid)
                    score = next((c["score"] for c in choices if c["label"] == sel_label), None)
                    all_responses[qid] = {"label": sel_label, "score": score, "is_na": False}
            continue

        # SCORED + EVIDENCE
        with st.container(border=True):
            col_q, col_na = st.columns([5, 1])
            with col_q:
                st.markdown(f"**{q['question_label']}**")
                if qtype == "evidence" and q.get("documents_attendus"):
                    parts_obl = [d["label"] for d in q["documents_attendus"] if d.get("obligatoire")]
                    parts_opt = [d["label"] for d in q["documents_attendus"] if not d.get("obligatoire")]
                    if parts_obl:
                        st.caption(f"🔴 **Obligatoires :** {', '.join(parts_obl)}")
                    if parts_opt:
                        st.caption(f"🟡 **Optionnels :** {', '.join(parts_opt)}")
                elif q.get("question_help"):
                    st.caption(q["question_help"])

            if qtype == "scored" and any([q.get("description_niveau"),
                                          q.get("outils_necessaires"), q.get("niveau_label")]):
                with st.expander("📖 En savoir plus"):
                    if q.get("niveau_label"):      st.markdown(f"**{q['niveau_label']}**")
                    if q.get("description_niveau"):st.markdown(q["description_niveau"])
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if q.get("outils_necessaires"):
                            st.markdown("**🔧 Outils nécessaires**")
                            for o in q["outils_necessaires"]: st.markdown(f"- {o}")
                    with col_b:
                        if q.get("outils_optionnels"):
                            st.markdown("**⚙️ Optionnels**")
                            for o in q["outils_optionnels"]: st.markdown(f"- {o}")
                    if q.get("dependances_inter_domaines"):
                        st.info(f"🔗 {q['dependances_inter_domaines']}")
                    if q.get("conditions_progression"):
                        st.success(f"🎯 {q['conditions_progression']}")
                    if q.get("pre_requis_metier") and q["pre_requis_metier"] != "Aucun":
                        st.warning(f"⚠️ {q['pre_requis_metier']}")

            is_na = False
            if q.get("na_allowed", False):
                with col_na:
                    is_na = st.checkbox("N/A", value=saved.get("is_na", False),
                        key=f"na_{qid}", on_change=mark_dirty, args=(qid,))

            if is_na:
                all_responses[qid] = {"label": None, "score": None, "is_na": True}
                continue

            if q.get("type_reponse") == "single_choice":
                choices = q.get("choices", [])
                labels  = [c["label"] for c in choices]
                saved_lbl   = saved.get("label")
                # index=None si jamais répondu → aucune option pré-sélectionnée
                if saved_lbl in labels:
                    default_idx = labels.index(saved_lbl)
                else:
                    default_idx = None
                sel_label = st.radio(qid, labels, index=default_idx,
                    key=f"radio_{qid}", label_visibility="collapsed",
                    on_change=mark_dirty, args=(qid,))
                if sel_label is not None:
                    score = next((c["score"] for c in choices if c["label"] == sel_label), None)
                    all_responses[qid] = {"label": sel_label, "score": score, "is_na": False}

            elif q.get("type_reponse") == "text":
                answer_text = st.text_area("Votre réponse",
                    value=saved.get("answer_text",""),
                    key=f"text_{qid}", label_visibility="collapsed",
                    placeholder="Décrivez les éléments de preuve...",
                    on_change=mark_dirty, args=(qid,))
                all_responses[qid] = {"label": None, "score": None, "is_na": False, "answer_text": answer_text}

            # Icône d'état en bas à droite
            st.markdown(
                f"<div style='text-align:right; color:#888; font-size:0.9em'>{q_status}</div>",
                unsafe_allow_html=True
            )

        # CONTEXTE & INSIGHTS
        if qtype in ("scored", "evidence"):
            with st.expander("🧩 Contexte & Insights", expanded=False):
                saved_conf = next((lbl for lbl, v in CONFIDENCE_OPTIONS.items()
                    if v == saved.get("consultant_confidence", 1.0)), "Élevée")
                conf_lbl = st.selectbox("🎯 Confiance consultant",
                    list(CONFIDENCE_OPTIONS.keys()),
                    index=list(CONFIDENCE_OPTIONS.keys()).index(saved_conf),
                    key=f"confidence_{qid}", on_change=mark_dirty, args=(qid,))
                tools_raw = saved.get("current_tools", [])
                tools_val = st.text_input("🔧 Outils en place",
                    value=", ".join(tools_raw) if tools_raw else "",
                    key=f"tools_{qid}", placeholder="SAP, Excel...",
                    on_change=mark_dirty, args=(qid,))
                docs_raw = saved.get("current_documents", [])
                docs_val = st.text_input("📄 Documents existants",
                    value=", ".join(docs_raw) if isinstance(docs_raw, list) else "",
                    key=f"docs_{qid}", placeholder="Procédures, chartes...",
                    on_change=mark_dirty, args=(qid,))
                st.markdown("**🔥 Analyse rapide**")
                col_pain, col_weak = st.columns(2)
                with col_pain:
                    pain_sel = st.multiselect("🟥 Douleurs", PAIN_TAGS+["Autre"],
                        default=[p for p in saved.get("pain_points",[]) if p in PAIN_TAGS+["Autre"]],
                        key=f"pain_{qid}", on_change=mark_dirty, args=(qid,))
                    pain_other = st.text_input("Précisez", key=f"pain_other_{qid}",
                        label_visibility="collapsed", placeholder="Autre douleur...") if "Autre" in pain_sel else ""
                with col_weak:
                    weak_sel = st.multiselect("🟧 Faiblesses", WEAKNESS_TAGS+["Autre"],
                        default=[w for w in saved.get("weaknesses",[]) if w in WEAKNESS_TAGS+["Autre"]],
                        key=f"weak_{qid}", on_change=mark_dirty, args=(qid,))
                    weak_other = st.text_input("Précisez", key=f"weak_other_{qid}",
                        label_visibility="collapsed", placeholder="Autre faiblesse...") if "Autre" in weak_sel else ""
                col_str2, col_opp = st.columns(2)
                with col_str2:
                    str_sel = st.multiselect("🟩 Forces", STRENGTH_TAGS+["Autre"],
                        default=[s for s in saved.get("strengths",[]) if s in STRENGTH_TAGS+["Autre"]],
                        key=f"str_{qid}", on_change=mark_dirty, args=(qid,))
                    str_other = st.text_input("Précisez", key=f"str_other_{qid}",
                        label_visibility="collapsed", placeholder="Autre force...") if "Autre" in str_sel else ""
                with col_opp:
                    opp_sel = st.multiselect("🟦 Opportunités", OPPORTUNITY_TAGS+["Autre"],
                        default=[o for o in saved.get("opportunities",[]) if o in OPPORTUNITY_TAGS+["Autre"]],
                        key=f"opp_{qid}", on_change=mark_dirty, args=(qid,))
                    opp_other = st.text_input("Précisez", key=f"opp_other_{qid}",
                        label_visibility="collapsed", placeholder="Autre opportunité...") if "Autre" in opp_sel else ""
                risk_sel = st.multiselect("🟪 Risques", RISK_TAGS+["Autre"],
                    default=[r for r in saved.get("risks",[]) if r in RISK_TAGS+["Autre"]],
                    key=f"risk_{qid}", on_change=mark_dirty, args=(qid,))
                risk_other = st.text_input("Précisez", key=f"risk_other_{qid}",
                    label_visibility="collapsed", placeholder="Autre risque...") if "Autre" in risk_sel else ""
                note = st.text_area("📝 Note consultant",
                    value=saved.get("consultant_note",""),
                    key=f"note_{qid}", placeholder="Observations...", height=80,
                    on_change=mark_dirty, args=(qid,))

            def _mg(sel, other):
                return [x for x in sel if x != "Autre"] + ([other] if isinstance(other, str) and other.strip() else [])
            if qid in all_responses:
                all_responses[qid].update({
                    "current_tools":        [t.strip() for t in tools_val.split(",") if t.strip()],
                    "current_documents":    [d.strip() for d in docs_val.split(",") if d.strip()],
                    "pain_points":          _mg(pain_sel, pain_other),
                    "weaknesses":           _mg(weak_sel, weak_other),
                    "strengths":            _mg(str_sel,  str_other),
                    "opportunities":        _mg(opp_sel,  opp_other),
                    "risks":                _mg(risk_sel, risk_other),
                    "consultant_confidence":CONFIDENCE_OPTIONS[conf_lbl],
                    "consultant_note":      note,
                })

        # PIÈCES JOINTES
        uploaded_files = st.file_uploader("📎 Ajouter des preuves",
            key=f"upload_{qid}", accept_multiple_files=True)
        if uploaded_files and assessment_id:
            attach_dir = Path(f"data/attachments/{assessment_id}/{qid}")
            attach_dir.mkdir(parents=True, exist_ok=True)
            s = get_session()
            try:
                for uf in uploaded_files:
                    fp = attach_dir / uf.name
                    if not fp.exists():
                        fp.write_bytes(uf.getbuffer())
                        s.add(Attachment(assessment_id=assessment_id, question_id=qid,
                            filename=uf.name, filepath=str(fp), mimetype=uf.type or ""))
                s.commit()
            finally:
                s.close()
        if assessment_id:
            s = get_session()
            try:
                atts = s.query(Attachment).filter_by(assessment_id=assessment_id, question_id=qid).all()
                if atts:
                    st.caption(f"📁 {len(atts)} fichier(s) attaché(s)")
                    for att in atts:
                        cf, cd = st.columns([4, 1])
                        with cf: st.caption(f"📄 {att.filename}")
                        with cd:
                            if Path(att.filepath).exists():
                                with open(att.filepath,"rb") as f:
                                    st.download_button("⬇️", data=f.read(),
                                        file_name=att.filename, key=f"dl_{att.id}")
            finally:
                s.close()

        # ANALYSE DOCUMENTAIRE
        if qtype == "evidence" and assessment_id:
            with st.expander("🔍 Analyse documentaire", expanded=False):
                docs_attendus = q.get("documents_attendus", [])
                s = get_session()
                try:
                    existing_reviews = (s.query(DocumentReview)
                        .filter_by(assessment_id=assessment_id, question_id=qid)
                        .order_by(DocumentReview.id).all())
                    revs_data = [r.to_dict() for r in existing_reviews]
                    atts_q    = s.query(Attachment).filter_by(assessment_id=assessment_id, question_id=qid).all()
                    att_map   = {a.id: a.filename for a in atts_q}
                finally:
                    s.close()

                revs_by_doc = {r["doc_id"]: r for r in revs_data if r.get("doc_id")}
                free_revs   = [r for r in revs_data if not r.get("doc_id")]
                att_opts    = ["— Aucun fichier lié —"] + [f"{aid} — {fn}" for aid, fn in att_map.items()]

                def _att_id(sv):
                    if sv == "— Aucun fichier lié —": return None
                    try: return int(sv.split(" — ")[0])
                    except: return None

                def _review_form(rev, kp):
                    rid  = rev["id"]
                    icon = STATUS_ICONS.get(rev["status"],"⬜")
                    st.markdown(f"**{icon} {rev['document_label']}**")
                    cs, cc = st.columns(2)
                    with cs:
                        ns = st.selectbox("Statut", STATUS_OPTIONS,
                            index=STATUS_OPTIONS.index(rev["status"]) if rev["status"] in STATUS_OPTIONS else 0,
                            key=f"{kp}_s_{rid}",
                            format_func=lambda x: f"{STATUS_ICONS[x]} {x.replace('_',' ').capitalize()}")
                    with cc:
                        nc = st.selectbox("Confiance", ["Élevée","Moyenne","Faible"],
                            index=["Élevée","Moyenne","Faible"].index(rev["expert_confidence"])
                                  if rev["expert_confidence"] in ["Élevée","Moyenne","Faible"] else 1,
                            key=f"{kp}_c_{rid}")
                    cur_att = next((f"{aid} — {fn}" for aid,fn in att_map.items()
                        if aid == rev.get("attachment_id")), "— Aucun fichier lié —")
                    la = st.selectbox("📎 Fichier", att_opts,
                        index=att_opts.index(cur_att) if cur_att in att_opts else 0,
                        key=f"{kp}_a_{rid}")
                    dm = next((d for d in docs_attendus if d.get("doc_id") == rev.get("doc_id")), None)
                    if dm and dm.get("points_a_valider"):
                        st.markdown("**🔎 Points à vérifier**")
                        for pt in dm["points_a_valider"]: st.caption(f"• {pt}")
                    nt = st.text_area("✅ Trouvés",   value=rev["elements_trouves"],   key=f"{kp}_f_{rid}", height=70)
                    nm = st.text_area("❌ Manquants", value=rev["elements_manquants"], key=f"{kp}_m_{rid}", height=70)
                    no = st.text_area("📝 Observation",value=rev["observation"],       key=f"{kp}_o_{rid}", height=55)
                    csav, cdel = st.columns([3,1])
                    with csav:
                        if st.button("💾 Sauvegarder", key=f"{kp}_sv_{rid}"):
                            s2 = get_session()
                            try:
                                db = s2.query(DocumentReview).get(rid)
                                if db:
                                    db.document_remis     = st.session_state.get(f"{kp}_remis_{rid}", rev.get("document_remis", False))
                                    db.status             = ns
                                    db.expert_confidence  = nc
                                    db.attachment_id      = _att_id(la)
                                    db.elements_trouves   = nt
                                    db.elements_manquants = nm
                                    db.observation        = no
                                    db.reviewed_at        = datetime.now(timezone.utc)
                                    s2.commit()
                                    st.success("Sauvegardé !")
                                    st.rerun()
                            finally: s2.close()
                    with cdel:
                        if st.button("🗑️", key=f"{kp}_dl_{rid}"):
                            s2 = get_session()
                            try:
                                db = s2.query(DocumentReview).get(rid)
                                if db: s2.delete(db); s2.commit(); st.rerun()
                            finally: s2.close()

                if docs_attendus:
                    st.markdown("**📋 Documents attendus**")
                    for doc in docs_attendus:
                        doc_id = doc["doc_id"]
                        badge  = "🔴 obligatoire" if doc["obligatoire"] else "🟡 optionnel"
                        rev    = revs_by_doc.get(doc_id)
                        with st.container(border=True):
                            # En-tête : nom du doc + badge + checkbox "Document remis"
                            cl, cb, cr = st.columns([4, 1, 2])
                            with cl:
                                st.markdown(f"**{doc['label']}**")
                            with cb:
                                st.caption(badge)
                            with cr:
                                # Checkbox rapide visible sans ouvrir l'analyse
                                remis_val = rev.get("document_remis", False) if rev else False
                                remis_key = f"remis_{qid}_{doc_id}"
                                new_remis = st.checkbox(
                                    "✅ Document remis",
                                    value=remis_val,
                                    key=remis_key,
                                )
                                # Sauvegarde immédiate si la coche change
                                if rev and new_remis != remis_val:
                                    s2 = get_session()
                                    try:
                                        db = s2.query(DocumentReview).get(rev["id"])
                                        if db:
                                            db.document_remis = new_remis
                                            s2.commit()
                                            st.rerun()
                                    finally:
                                        s2.close()
                                elif not rev and new_remis:
                                    # Pas encore de review → on en crée un automatiquement
                                    s2 = get_session()
                                    try:
                                        s2.add(DocumentReview(
                                            assessment_id=assessment_id,
                                            question_id=qid, doc_id=doc_id,
                                            document_label=doc["label"],
                                            status="non_vérifié",
                                            document_remis=True,
                                        ))
                                        s2.commit()
                                        st.rerun()
                                    finally:
                                        s2.close()
                            if rev:
                                with st.expander("🔍 Analyser ce document", expanded=False):
                                    _review_form(rev, f"da_{qid}_{doc_id}")
                            else:
                                ci, ca = st.columns([2,3])
                                with ci:
                                    ist = st.selectbox("Statut initial", STATUS_OPTIONS,
                                        key=f"ist_{qid}_{doc_id}",
                                        format_func=lambda x: f"{STATUS_ICONS[x]} {x.replace('_',' ').capitalize()}")
                                with ca:
                                    lan = st.selectbox("📎 Fichier", att_opts, key=f"lan_{qid}_{doc_id}")
                                if st.button("➕ Commencer l'analyse détaillée", key=f"cr_{qid}_{doc_id}"):
                                    s2 = get_session()
                                    try:
                                        s2.add(DocumentReview(assessment_id=assessment_id,
                                            question_id=qid, doc_id=doc_id,
                                            document_label=doc["label"],
                                            attachment_id=_att_id(lan), status=ist,
                                            document_remis=st.session_state.get(remis_key, False)))
                                        s2.commit(); st.rerun()
                                    finally: s2.close()

                st.markdown("---")
                st.markdown("**➕ Document non listé**")
                if free_revs:
                    for rev in free_revs:
                        with st.container(border=True):
                            _review_form(rev, f"fr_{qid}")
                cfl, cfa = st.columns([3,2])
                with cfl:
                    ndl = st.text_input("Nom", key=f"ndl_{qid}", placeholder="Note interne...")
                with cfa:
                    fatt = st.selectbox("📎 Fichier", att_opts, key=f"fatt_{qid}")
                if st.button("➕ Ajouter", key=f"fadd_{qid}") and ndl.strip():
                    s2 = get_session()
                    try:
                        s2.add(DocumentReview(assessment_id=assessment_id, question_id=qid,
                            doc_id=None, document_label=ndl.strip(),
                            attachment_id=_att_id(fatt), status="non_vérifié"))
                        s2.commit(); st.rerun()
                    finally: s2.close()

        st.divider()

# ── Sauvegarde ─────────────────────────────────────────────────────────────────
def build_to_save():
    dirty = st.session_state.get("dirty", set())
    result = {}
    for qid in dirty:
        qm = next((q for q in questions if q["question_id"] == qid), None)
        if qm is None: continue
        is_na = st.session_state.get(f"na_{qid}", False)
        if is_na:
            label, score = None, None
        else:
            label = st.session_state.get(f"radio_{qid}")
            if label is None:
                label = st.session_state.get(f"text_{qid}", "")
                score = None
            else:
                score = next((c["score"] for c in qm.get("choices",[]) if c["label"] == label), None)
        def _mss(sk, ok):
            sel = st.session_state.get(sk, [])
            oth = st.session_state.get(ok, "")
            return [x for x in sel if x != "Autre"] + ([oth] if isinstance(oth, str) and oth.strip() else [])
        result[qid] = {
            "label": label, "score": score, "is_na": is_na,
            "answer_text":          st.session_state.get(f"text_{qid}", ""),
            "current_tools":        [t.strip() for t in st.session_state.get(f"tools_{qid}","").split(",") if t.strip()],
            "current_documents":    [d.strip() for d in st.session_state.get(f"docs_{qid}","").split(",") if d.strip()],
            "pain_points":          _mss(f"pain_{qid}", f"pain_other_{qid}"),
            "weaknesses":           _mss(f"weak_{qid}", f"weak_other_{qid}"),
            "strengths":            _mss(f"str_{qid}",  f"str_other_{qid}"),
            "opportunities":        _mss(f"opp_{qid}",  f"opp_other_{qid}"),
            "risks":                _mss(f"risk_{qid}", f"risk_other_{qid}"),
            "consultant_confidence":CONFIDENCE_OPTIONS.get(st.session_state.get(f"confidence_{qid}","Élevée"), 1.0),
            "consultant_note":      st.session_state.get(f"note_{qid}", ""),
        }
    return result

def save_to_db(to_save, status=None):
    s = get_session()
    try:
        for qid, resp in to_save.items():
            qm  = next((q for q in questions if q["question_id"] == qid), {})
            ex  = s.query(Response).filter(
                Response.assessment_id == assessment_id,
                Response.question_id == qid).first()
            data = dict(
                question_type        = qm.get("question_type",""),
                selected_label       = resp.get("label"),
                selected_score       = resp.get("score"),
                answer_text          = resp.get("answer_text",""),
                is_na                = resp.get("is_na", False),
                current_tools        = json.dumps(resp.get("current_tools",[])),
                current_documents    = json.dumps(resp.get("current_documents",[])),
                pain_points          = json.dumps(resp.get("pain_points",[])),
                weaknesses           = json.dumps(resp.get("weaknesses",[])),
                strengths            = json.dumps(resp.get("strengths",[])),
                opportunities        = json.dumps(resp.get("opportunities",[])),
                risks                = json.dumps(resp.get("risks",[])),
                consultant_confidence= resp.get("consultant_confidence", 1.0),
                consultant_note      = resp.get("consultant_note",""),
            )
            if ex:
                for k, v in data.items(): setattr(ex, k, v)
            else:
                s.add(Response(assessment_id=assessment_id, question_id=qid, **data))
        if status:
            a = s.query(Assessment).get(assessment_id)
            if a: a.status = status
        s.commit()
    finally:
        s.close()

st.divider()
col_save, col_complete = st.columns(2)
with col_save:
    if st.button("💾 Sauvegarder", type="secondary", use_container_width=True):
        to_save = build_to_save()
        if to_save:
            save_to_db(to_save)
            st.session_state["dirty"] = set()
            st.success(f"✅ {len(to_save)} réponse(s) sauvegardée(s).")
            st.rerun()
        else:
            st.info("Aucune modification à sauvegarder.")
with col_complete:
    if st.button("✅ Terminer l'assessment", type="primary", use_container_width=True):
        save_to_db(build_to_save(), status="completed")
        st.session_state["dirty"] = set()
        st.success("Assessment terminé !")
        st.rerun()

# ── Sidebar scores ─────────────────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.subheader("📊 Scores en direct")
doc_reviews_live = load_document_reviews(assessment_id) if assessment_id else {}
scores       = compute_scores(questions, all_responses, document_reviews=doc_reviews_live)
global_score = scores.get("global_score")
if scores.get("avg_confidence") is not None:
    st.sidebar.metric("Confiance moyenne", f"{int(scores['avg_confidence']*100)}%")
if global_score is not None:
    st.sidebar.metric("Score global", f"{global_score}%")
    maturity = next((m for m in MATURITY_LEVELS if m["min"] <= global_score <= m["max"]), MATURITY_LEVELS[-1])
    st.sidebar.caption(f"Niveau : {maturity['label']}")
    for domain, score in scores["domains"].items():
        if score is not None:
            st.sidebar.progress(score / 100, text=f"{domain}: {score}%")
else:
    st.sidebar.caption("Répondez aux questions pour voir le score.")