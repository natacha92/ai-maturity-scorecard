"""
COMEX report generation — Executive deliverables.
5 sections: Executive Summary, Heatmap, Top 5 Priorities, Risk Note, Evidence Annex.
"""

import json
from engine.scoring import get_maturity_level, MATURITY_LEVELS
from engine.recommendations import get_recommendations, generate_roadmap
from engine.classification import classify_client


def generate_executive_summary(scores, client_name, classification=None):
    """Generate a 1-page executive summary."""
    global_score = scores["global_score"]
    maturity = scores["maturity_level"]
    domain_scores = scores["domains"]

    # Identify strongest and weakest domains
    sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1])
    weakest = sorted_domains[:2]
    strongest = sorted_domains[-2:]

    # Key risks
    risks = []
    for domain, score in sorted_domains:
        if score <= 30:
            risks.append(f"Critical gap in {domain} (score: {score}%)")
        elif score <= 50:
            risks.append(f"Below target in {domain} (score: {score}%)")

    summary = {
        "client_name": client_name,
        "global_score": global_score,
        "maturity_level": maturity["label"],
        "maturity_description": maturity["description"],
        "classification": classification or {},
        "headline": _generate_headline(global_score, maturity, client_name),
        "position_statement": _generate_position(global_score, maturity),
        "key_strengths": [
            {"domain": d, "score": s, "assessment": _assess_domain(s)}
            for d, s in strongest
        ],
        "key_weaknesses": [
            {"domain": d, "score": s, "assessment": _assess_domain(s)}
            for d, s in weakest
        ],
        "key_risks": risks[:5],
        "top_priorities": [d for d, _ in weakest],
        "decision_needed": _generate_decisions(weakest, maturity),
    }
    return summary


def generate_domain_heatmap_data(scores):
    """Generate data for the COMEX heatmap visualization."""
    domain_scores = scores["domains"]
    subdomain_scores = scores["subdomains"]

    heatmap = []
    for domain, score in domain_scores.items():
        entry = {
            "domain": domain,
            "score": score,
            "level": get_maturity_level(score)["label"],
            "color": _score_to_color(score),
            "subdomains": [],
        }
        for sub, sub_score in subdomain_scores.get(domain, {}).items():
            entry["subdomains"].append({
                "name": sub,
                "score": sub_score,
                "level": get_maturity_level(sub_score)["label"],
                "color": _score_to_color(sub_score),
            })
        heatmap.append(entry)

    return heatmap


def generate_top5_priorities(scores):
    """Generate top 5 priorities / 90-day roadmap for COMEX."""
    recommendations = get_recommendations(
        scores["domains"], scores.get("subdomains")
    )

    priorities = []
    for rec in recommendations[:5]:
        priorities.append({
            "rank": len(priorities) + 1,
            "action": rec["title"],
            "domain": rec["domain"],
            "impact": rec["impact"],
            "effort": rec["effort"],
            "horizon": rec["horizon"],
            "description": rec["text"],
        })

    return priorities


def generate_risk_note(scores):
    """Generate risk & compliance note."""
    domain_scores = scores["domains"]

    risks = []

    # Check security & compliance specifically
    sec_score = domain_scores.get("Security & Compliance", 0)
    if sec_score <= 30:
        risks.append({
            "category": "Regulatory",
            "severity": "critical",
            "description": "Organization is not prepared for EU AI Act compliance. Immediate action required.",
            "exposure": "High risk of non-compliance penalties and reputational damage.",
        })
    elif sec_score <= 60:
        risks.append({
            "category": "Regulatory",
            "severity": "high",
            "description": "EU AI Act preparation is underway but significant gaps remain.",
            "exposure": "Moderate risk — timeline pressure for compliance deadlines.",
        })

    # Governance risk
    gov_score = domain_scores.get("Governance", 0)
    if gov_score <= 30:
        risks.append({
            "category": "Governance",
            "severity": "critical",
            "description": "No formal AI governance in place. Risk of uncontrolled AI proliferation.",
            "exposure": "Shadow AI, inconsistent quality, liability exposure.",
        })
    elif gov_score <= 50:
        risks.append({
            "category": "Governance",
            "severity": "high",
            "description": "AI governance is nascent. Key decisions lack structured oversight.",
            "exposure": "Inconsistent project outcomes and resource allocation.",
        })

    # Data risk
    data_score = domain_scores.get("Data Foundation", 0)
    if data_score <= 30:
        risks.append({
            "category": "Data",
            "severity": "high",
            "description": "Data foundation is weak. AI initiatives will be limited by data quality and availability.",
            "exposure": "Poor model performance, unreliable insights, wasted investment.",
        })

    # Adoption risk
    adoption_score = domain_scores.get("Adoption & Change", 0)
    if adoption_score <= 30:
        risks.append({
            "category": "Organizational",
            "severity": "medium",
            "description": "Low AI literacy and adoption readiness. Risk of project failure due to user resistance.",
            "exposure": "Low ROI on AI investments, employee disengagement.",
        })

    # Technology risk
    tech_score = domain_scores.get("Technology & Infrastructure", 0)
    if tech_score <= 30:
        risks.append({
            "category": "Technical",
            "severity": "medium",
            "description": "Insufficient technical infrastructure for AI at scale.",
            "exposure": "Inability to move from POC to production. Technical debt accumulation.",
        })

    # Overall attention points
    attention_points = []
    for domain, score in domain_scores.items():
        if score <= 40:
            attention_points.append(f"{domain}: requires immediate attention (score {score}%)")

    return {
        "risks": sorted(risks, key=lambda r: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(r["severity"], 4)),
        "attention_points": attention_points,
        "overall_risk_level": _overall_risk(risks),
    }


def generate_evidence_annex(scores, responses, questionnaire):
    """Generate evidence annex with key responses and references."""
    questions = {q["question_id"]: q for q in questionnaire["questions"]}

    low_scores = []
    high_scores = []

    for qid, q_score in scores["questions"].items():
        if q_score is None:
            continue
        q = questions.get(qid)
        if not q:
            continue

        resp = responses.get(qid, {})
        
        # Score sur 100 si ce n'est pas déjà le cas
        score_pct = (q_score / 4.0) * 100 if q_score <= 4 else q_score

        entry = {
            "question_id": qid,
            "domain":    q.get("domaine_principal", "Autre"),    # ← corrigé
            "subdomain": q.get("domaine_specifique", "Autre"),   # ← corrigé
            "question":  q.get("question_label", qid),           # ← corrigé
            "score":     round(score_pct, 1),
            "answer":    resp.get("label") or resp.get("answer_text", ""),  # ← corrigé
            "comment":   resp.get("answer_text", ""),
        }

        if score_pct <= 25:
            low_scores.append(entry)
        elif score_pct >= 75:
            high_scores.append(entry)

    return {
        "critical_findings": sorted(low_scores, key=lambda x: x["score"])[:10],
        "strengths": sorted(high_scores, key=lambda x: -x["score"])[:10],
        "references": [
            {"id": "eu_ai_act",    "title": "EU AI Act",                              "type": "Regulation"},
            {"id": "nist_ai_rmf",  "title": "NIST AI Risk Management Framework",      "type": "Framework"},
            {"id": "iso_42001",    "title": "ISO/IEC 42001 AI Management System",     "type": "Standard"},
            {"id": "gdpr",         "title": "GDPR — General Data Protection Regulation", "type": "Regulation"},
        ],
    }

def generate_full_comex_report(scores, responses, questionnaire, client_name):
    """Generate complete COMEX report with all 5 sections."""
    classification = classify_client(scores["domains"], scores["global_score"])

    return {
        "executive_summary": generate_executive_summary(scores, client_name, classification),
        "heatmap": generate_domain_heatmap_data(scores),
        "priorities": generate_top5_priorities(scores),
        "risk_note": generate_risk_note(scores),
        "evidence": generate_evidence_annex(scores, responses, questionnaire),
    }


# --- Helper functions ---

def _generate_headline(score, maturity, client_name):
    if score <= 30:
        return f"{client_name} is at the beginning of its AI journey. Foundational investments are needed."
    elif score <= 60:
        return f"{client_name} has initiated AI efforts but industrialization is required to unlock value."
    elif score <= 80:
        return f"{client_name} is actively deploying AI. Focus on optimization and governance to reach maturity."
    return f"{client_name} demonstrates advanced AI maturity. Continuous improvement and innovation are key."


def _generate_position(score, maturity):
    return (
        f"With a global maturity score of {score}%, the organization is at "
        f"the '{maturity['label']}' level: {maturity['description'].lower()}."
    )


def _assess_domain(score):
    if score <= 30:
        return "Critical — requires immediate action"
    elif score <= 50:
        return "Below expectations — significant improvement needed"
    elif score <= 70:
        return "On track — continue structured investment"
    elif score <= 85:
        return "Strong — optimize and sustain"
    return "Excellent — industry-leading"


def _generate_decisions(weakest, maturity):
    decisions = []
    for domain, score in weakest:
        if score <= 30:
            decisions.append(f"Approve investment in {domain} foundation (current: {score}%)")
        elif score <= 50:
            decisions.append(f"Accelerate {domain} improvement program (current: {score}%)")
    if not decisions:
        decisions.append("Continue current trajectory with quarterly reviews")
    return decisions


def _score_to_color(score):
    if score <= 30:
        return "red"
    elif score <= 60:
        return "orange"
    elif score <= 80:
        return "green"
    return "blue"


def _overall_risk(risks):
    if any(r["severity"] == "critical" for r in risks):
        return "critical"
    elif any(r["severity"] == "high" for r in risks):
        return "high"
    elif any(r["severity"] == "medium" for r in risks):
        return "medium"
    return "low"


def _get_answer_label(question, value):
    if value is None:
        return "N/A"
    for opt in question.get("options", []):
        if opt["value"] == value:
            return opt["label"]
    return str(value)
