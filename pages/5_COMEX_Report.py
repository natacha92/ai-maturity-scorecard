import streamlit as st
import json
from models.database import init_db, get_session, Client, Assessment, Response, Report
from src.data_loader import load_questionnaire_cached
from engine.scoring import compute_scores
from models.database import load_responses_for_scoring
from reports.comex import generate_full_comex_report
from engine.scoring import get_maturity_level
import json
from pathlib import Path

init_db()

st.title("COMEX Report")

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
            "client_name": client.name if client else "Unknown",
        })
finally:
    session.close()

if not assessment_options:
    st.info("No completed assessments.")
    st.stop()

selected_label = st.selectbox("Select Assessment", [a["label"] for a in assessment_options])
selected = next(a for a in assessment_options if a["label"] == selected_label)

# Load data
questionnaire_full = json.loads(Path("data/questionnaire.json").read_text(encoding="utf-8"))
questionnaire = questionnaire_full["questions"]
responses = load_responses_for_scoring(selected["id"])
scores = compute_scores(questionnaire, responses)
scores["maturity_level"] = get_maturity_level(scores["global_score"])
scores["subdomains"] = {}
scores["questions"] = {
    qid: resp.get("score")
    for qid, resp in responses.items()
    if resp.get("score") is not None
}


# Generate report
if st.button("Generate COMEX Report", type="primary"):
    report = generate_full_comex_report(scores, responses, questionnaire_full, selected["client_name"])

    # Save to DB
    session = get_session()
    try:
        db_report = Report(
            assessment_id=selected["id"],
            report_type="comex_full",
            content_json=json.dumps(report, default=str),
        )
        session.add(db_report)
        session.commit()
        st.success("Report generated and saved!")
    finally:
        session.close()

    st.session_state["comex_report"] = report

# Load last report from session or DB
report = st.session_state.get("comex_report")
if not report:
    session = get_session()
    try:
        db_report = (
            session.query(Report)
            .filter(Report.assessment_id == selected["id"], Report.report_type == "comex_full")
            .order_by(Report.generated_at.desc())
            .first()
        )
        if db_report:
            report = json.loads(db_report.content_json)
            st.session_state["comex_report"] = report
    finally:
        session.close()

if not report:
    st.info("Click 'Generate COMEX Report' to create the report.")
    st.stop()

# === SECTION 1: Executive Summary ===
st.divider()
st.header("1. Executive Summary")

summary = report["executive_summary"]

col1, col2 = st.columns([1, 2])
with col1:
    maturity_level = get_maturity_level(summary["global_score"])
    color = maturity_level["color"]
    st.metric("Score global", f"{summary['global_score']}%")
    st.markdown(
        f'<span style="background:{color};padding:4px 12px;border-radius:12px;'
        f'color:white;font-weight:bold">{maturity_level["label"]}</span>',
        unsafe_allow_html=True,
    )
    st.markdown(f"**Niveau :** {summary['maturity_level']}")

with col2:
    st.markdown(f"### {summary['headline']}")
    st.markdown(summary["position_statement"])

    if summary.get("classification", {}).get("archetype_name"):
        st.info(f"**Archetype:** {summary['classification']['archetype_name']} — {summary['classification'].get('description', '')}")

col_str, col_weak = st.columns(2)
with col_str:
    st.markdown("#### Key Strengths")
    for s in summary.get("key_strengths", []):
        st.markdown(f"- **{s['domain']}** ({s['score']}%) — {s['assessment']}")

with col_weak:
    st.markdown("#### Key Weaknesses")
    for w in summary.get("key_weaknesses", []):
        st.markdown(f"- **{w['domain']}** ({w['score']}%) — {w['assessment']}")

if summary.get("decision_needed"):
    st.markdown("#### Decisions Needed")
    for d in summary["decision_needed"]:
        st.markdown(f"- {d}")

# === SECTION 2: Domain Heatmap ===
st.divider()
st.header("2. Domain Heatmap")

heatmap_data = report["heatmap"]
for entry in heatmap_data:
    color_map = {"red": "🔴", "orange": "🟠", "green": "🟢", "blue": "🔵"}
    icon = color_map.get(entry["color"], "⚪")
    with st.expander(f"{icon} {entry['domain']} — {entry['score']:.0f}% ({entry['level']})"):
        for sub in entry["subdomains"]:
            sub_icon = color_map.get(sub["color"], "⚪")
            st.markdown(f"  {sub_icon} **{sub['name']}** — {sub['score']:.0f}% ({sub['level']})")

# Visual heatmap simplifié (sans Plotly)
if scores.get("domains"):
    for domain, score in scores["domains"].items():
        if score is not None:
            st.progress(score / 100, text=f"{domain}: {score}%")

# === SECTION 3: Top 5 Priorities ===
st.divider()
st.header("3. Top 5 Priorities — 90-Day Roadmap")

priorities = report["priorities"]
if priorities:
    import pandas as pd
    df_priorities = pd.DataFrame([
        {
            "#": p["rank"],
            "Action": p["action"],
            "Domain": p["domain"],
            "Impact": p["impact"].title(),
            "Effort": p["effort"].title(),
            "Horizon": p["horizon"],
        }
        for p in priorities
    ])
    st.dataframe(df_priorities, use_container_width=True, hide_index=True)

    for p in priorities:
        with st.expander(f"#{p['rank']} — {p['action']}"):
            st.markdown(p["description"])
            st.caption(f"Domain: {p['domain']} | Impact: {p['impact']} | Effort: {p['effort']} | Horizon: {p['horizon']}")
else:
    st.info("No priority recommendations generated.")

# === SECTION 4: Risk & Compliance Note ===
st.divider()
st.header("4. Risk & Compliance Note")

risk_note = report["risk_note"]
risk_level = risk_note.get("overall_risk_level", "unknown")
risk_colors = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
st.markdown(f"**Overall Risk Level:** {risk_colors.get(risk_level, '⚪')} {risk_level.upper()}")

for risk in risk_note.get("risks", []):
    severity_icon = risk_colors.get(risk["severity"], "⚪")
    with st.expander(f"{severity_icon} [{risk['severity'].upper()}] {risk['category']}"):
        st.markdown(risk["description"])
        st.caption(f"**Exposure:** {risk['exposure']}")

if risk_note.get("attention_points"):
    st.markdown("#### Attention Points")
    for ap in risk_note["attention_points"]:
        st.markdown(f"- {ap}")

# === SECTION 5: Evidence Annex ===
st.divider()
st.header("5. Evidence Annex")

evidence = report["evidence"]

col_findings, col_strengths = st.columns(2)
with col_findings:
    st.markdown("#### Critical Findings")
    for f in evidence.get("critical_findings", []):
        st.markdown(f"- **{f['domain']}** / {f['subdomain']}: {f['question']}")
        st.caption(f"Answer: {f['answer']} (Score: {f['score']}%)")
        if f.get("comment"):
            st.caption(f"Comment: {f['comment']}")

with col_strengths:
    st.markdown("#### Strengths")
    for s in evidence.get("strengths", []):
        st.markdown(f"- **{s['domain']}** / {s['subdomain']}: {s['question']}")
        st.caption(f"Answer: {s['answer']} (Score: {s['score']}%)")

st.markdown("#### References")
for ref in evidence.get("references", []):
    st.markdown(f"- **{ref['title']}** ({ref['type']})")

# --- Export ---
st.divider()

col_json, col_pdf = st.columns(2)

with col_json:
    st.download_button(
        "📥 Download Full Report (JSON)",
        data=json.dumps(report, indent=2, default=str),
        file_name=f"COMEX_Report_{selected['client_name'].replace(' ', '_')}.json",
        mime="application/json",
    )

with col_pdf:
    if st.button("📄 Générer PDF"):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        import io

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)

        styles = getSampleStyleSheet()
        style_title    = ParagraphStyle("title",    fontSize=20, spaceAfter=12, textColor=colors.HexColor("#1E3A5F"), alignment=TA_CENTER, fontName="Helvetica-Bold")
        style_h1       = ParagraphStyle("h1",       fontSize=14, spaceBefore=16, spaceAfter=6,  textColor=colors.HexColor("#1E3A5F"), fontName="Helvetica-Bold")
        style_h2       = ParagraphStyle("h2",       fontSize=11, spaceBefore=10, spaceAfter=4,  textColor=colors.HexColor("#2C5F8A"), fontName="Helvetica-Bold")
        style_body     = ParagraphStyle("body",     fontSize=9,  spaceAfter=4,   leading=14)
        style_caption  = ParagraphStyle("caption",  fontSize=8,  spaceAfter=2,   textColor=colors.grey)

        story = []

        # ── Page de garde ──────────────────────────────────────────────────
        story.append(Spacer(1, 2*cm))
        story.append(Paragraph("COMEX Report", style_title))
        story.append(Paragraph(f"Client : {selected['client_name']}", style_title))
        story.append(Spacer(1, 0.5*cm))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1E3A5F")))
        story.append(Spacer(1, 1*cm))

        # ── Section 1 : Executive Summary ─────────────────────────────────
        story.append(Paragraph("1. Executive Summary", style_h1))
        summary = report["executive_summary"]
        story.append(Paragraph(f"<b>Score global :</b> {summary['global_score']}%", style_body))
        story.append(Paragraph(f"<b>Niveau :</b> {summary['maturity_level']}", style_body))
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(summary.get("headline", ""), style_h2))
        story.append(Paragraph(summary.get("position_statement", ""), style_body))

        if summary.get("key_strengths"):
            story.append(Paragraph("Points forts", style_h2))
            for s in summary["key_strengths"]:
                story.append(Paragraph(f"• <b>{s['domain']}</b> ({s['score']}%) — {s['assessment']}", style_body))

        if summary.get("key_weaknesses"):
            story.append(Paragraph("Points faibles", style_h2))
            for w in summary["key_weaknesses"]:
                story.append(Paragraph(f"• <b>{w['domain']}</b> ({w['score']}%) — {w['assessment']}", style_body))

        # ── Section 2 : Scores par domaine ────────────────────────────────
        story.append(Paragraph("2. Scores par domaine", style_h1))
        if scores.get("domains"):
            table_data = [["Domaine", "Score"]]
            for domain, score in scores["domains"].items():
                table_data.append([domain, f"{score}%" if score is not None else "N/A"])
            t = Table(table_data, colWidths=[13*cm, 4*cm])
            t.setStyle(TableStyle([
                ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
                ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
                ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE",    (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F4F6")]),
                ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                ("ALIGN",       (1, 0), (1, -1), "CENTER"),
                ("PADDING",     (0, 0), (-1, -1), 6),
            ]))
            story.append(t)

        # ── Section 3 : Top Priorités ─────────────────────────────────────
        story.append(Paragraph("3. Top Priorités — Roadmap 90 jours", style_h1))
        priorities = report.get("priorities", [])
        if priorities:
            table_data = [["#", "Action", "Domaine", "Impact", "Effort", "Horizon"]]
            for p in priorities:
                table_data.append([
                    str(p["rank"]), p["action"], p["domain"],
                    p["impact"].title(), p["effort"].title(), p["horizon"]
                ])
            t = Table(table_data, colWidths=[1*cm, 6*cm, 4*cm, 2*cm, 2*cm, 2*cm])
            t.setStyle(TableStyle([
                ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
                ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
                ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE",    (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F4F6")]),
                ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                ("PADDING",     (0, 0), (-1, -1), 5),
                ("WORDWRAP",    (1, 1), (1, -1), True),
            ]))
            story.append(t)

        # ── Section 4 : Risques ───────────────────────────────────────────
        story.append(Paragraph("4. Risk & Compliance", style_h1))
        risk_note = report.get("risk_note", {})
        story.append(Paragraph(f"<b>Niveau de risque global :</b> {risk_note.get('overall_risk_level', 'N/A').upper()}", style_body))
        for risk in risk_note.get("risks", []):
            story.append(Paragraph(f"• <b>[{risk['severity'].upper()}] {risk['category']}</b>", style_body))
            story.append(Paragraph(risk["description"], style_caption))

        # ── Section 5 : Evidence ──────────────────────────────────────────
        story.append(Paragraph("5. Evidence Annex", style_h1))
        evidence = report.get("evidence", {})
        if evidence.get("critical_findings"):
            story.append(Paragraph("Findings critiques", style_h2))
            for f in evidence["critical_findings"]:
                story.append(Paragraph(f"• <b>{f['domain']}</b> — {f['question']}", style_body))
                story.append(Paragraph(f"  Réponse : {f['answer']} (Score : {f['score']}%)", style_caption))

        if evidence.get("strengths"):
            story.append(Paragraph("Points forts", style_h2))
            for s in evidence["strengths"]:
                story.append(Paragraph(f"• <b>{s['domain']}</b> — {s['question']}", style_body))
                story.append(Paragraph(f"  Réponse : {s['answer']} (Score : {s['score']}%)", style_caption))

        # ── Génération ────────────────────────────────────────────────────
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        st.download_button(
            "📥 Télécharger le PDF",
            data=pdf_bytes,
            file_name=f"COMEX_Report_{selected['client_name'].replace(' ', '_')}.pdf",
            mime="application/pdf",
        )