from models.database import get_session, RecommendationRule


SEED_RULES = [
    # Governance — Initial
    {"domain": "Governance", "subdomain": "AI Strategy", "score_min": 0, "score_max": 30, "priority": 1,
     "title": "Define a formal AI strategy",
     "text": "Establish a documented AI strategy aligned with business objectives. Start by identifying 3-5 strategic AI goals and securing COMEX sponsorship.",
     "effort": "medium", "impact": "high", "horizon": "60d",
     "reference_ids": '["nist_ai_rmf"]'},
    {"domain": "Governance", "subdomain": "Roles & Organization", "score_min": 0, "score_max": 30, "priority": 1,
     "title": "Appoint an AI executive sponsor",
     "text": "Designate a COMEX-level sponsor for AI initiatives. Define clear roles: AI lead, data officer, and a cross-functional governance committee.",
     "effort": "low", "impact": "high", "horizon": "30d",
     "reference_ids": '[]'},
    {"domain": "Governance", "subdomain": "Ethics & Policies", "score_min": 0, "score_max": 30, "priority": 2,
     "title": "Draft an AI ethics charter",
     "text": "Create a foundational AI ethics document covering bias, transparency, and accountability. Use EU AI Act principles as a baseline.",
     "effort": "medium", "impact": "high", "horizon": "60d",
     "reference_ids": '["eu_ai_act"]'},
    # Governance — Structured
    {"domain": "Governance", "subdomain": "AI Strategy", "score_min": 31, "score_max": 60, "priority": 2,
     "title": "Align AI strategy with business KPIs",
     "text": "Map each AI initiative to measurable business outcomes. Create a portfolio view with expected ROI and resource requirements.",
     "effort": "medium", "impact": "high", "horizon": "60d",
     "reference_ids": '[]'},
    {"domain": "Governance", "subdomain": "Ethics & Policies", "score_min": 31, "score_max": 60, "priority": 2,
     "title": "Implement AI project approval process",
     "text": "Establish a structured intake process for new AI projects with business case requirements, risk assessment, and prioritization criteria.",
     "effort": "medium", "impact": "medium", "horizon": "60d",
     "reference_ids": '[]'},

    # Data Foundation — Initial
    {"domain": "Data Foundation", "subdomain": "Core Systems", "score_min": 0, "score_max": 30, "priority": 1,
     "title": "Assess and document core systems",
     "text": "Conduct an inventory of ERP, CRM, and other core systems. Document integration points, data flows, and known gaps.",
     "effort": "medium", "impact": "high", "horizon": "30d",
     "reference_ids": '[]'},
    {"domain": "Data Foundation", "subdomain": "Data Quality & Management", "score_min": 0, "score_max": 30, "priority": 1,
     "title": "Establish data quality baseline",
     "text": "Define data quality metrics (completeness, accuracy, timeliness) for critical datasets. Set up basic monitoring and assign data owners.",
     "effort": "medium", "impact": "high", "horizon": "60d",
     "reference_ids": '[]'},
    {"domain": "Data Foundation", "subdomain": "Data Architecture", "score_min": 0, "score_max": 30, "priority": 1,
     "title": "Plan centralized data platform",
     "text": "Design a target data architecture with a centralized data warehouse or lake. Prioritize breaking down critical data silos.",
     "effort": "high", "impact": "high", "horizon": "90d",
     "reference_ids": '[]'},
    # Data Foundation — Structured
    {"domain": "Data Foundation", "subdomain": "Data Quality & Management", "score_min": 31, "score_max": 60, "priority": 2,
     "title": "Formalize data governance framework",
     "text": "Implement formal data governance with stewards, policies, and a governance committee. Establish MDM practices for key entities.",
     "effort": "high", "impact": "high", "horizon": "90d",
     "reference_ids": '[]'},
    {"domain": "Data Foundation", "subdomain": "Data Architecture", "score_min": 31, "score_max": 60, "priority": 2,
     "title": "Automate data pipelines",
     "text": "Implement automated ETL/ELT pipelines with monitoring and alerting. Reduce manual data transfers and establish data catalog.",
     "effort": "high", "impact": "high", "horizon": "90d",
     "reference_ids": '[]'},

    # Use Cases & Value — Initial
    {"domain": "Use Cases & Value", "subdomain": "Use Case Identification", "score_min": 0, "score_max": 30, "priority": 1,
     "title": "Identify and prioritize quick-win AI use cases",
     "text": "Run workshops with business teams to identify AI opportunities. Score by value, feasibility, and data availability. Select 2-3 quick wins.",
     "effort": "low", "impact": "high", "horizon": "30d",
     "reference_ids": '[]'},
    {"domain": "Use Cases & Value", "subdomain": "Value Measurement", "score_min": 0, "score_max": 30, "priority": 2,
     "title": "Define KPIs for AI pilot projects",
     "text": "Establish clear success metrics (business and technical) before launching any AI project. Track baseline and measure improvement.",
     "effort": "low", "impact": "medium", "horizon": "30d",
     "reference_ids": '[]'},
    # Use Cases — Structured
    {"domain": "Use Cases & Value", "subdomain": "Industrialization", "score_min": 31, "score_max": 60, "priority": 2,
     "title": "Standardize model deployment process",
     "text": "Create deployment templates and CI/CD pipelines for ML models. Implement monitoring for model drift and performance degradation.",
     "effort": "high", "impact": "high", "horizon": "90d",
     "reference_ids": '[]'},
    {"domain": "Use Cases & Value", "subdomain": "Value Measurement", "score_min": 31, "score_max": 60, "priority": 2,
     "title": "Implement ROI tracking for AI projects",
     "text": "Build a simple dashboard to track ROI and business impact of AI initiatives. Compare projected vs actual value for each use case.",
     "effort": "medium", "impact": "medium", "horizon": "60d",
     "reference_ids": '[]'},

    # Technology & Infrastructure — Initial
    {"domain": "Technology & Infrastructure", "subdomain": "ML Platforms & Tools", "score_min": 0, "score_max": 30, "priority": 1,
     "title": "Select and deploy an ML platform",
     "text": "Evaluate ML platforms (Dataiku, SageMaker, Vertex AI, open-source stack) based on team skills and use cases. Deploy for pilot projects.",
     "effort": "high", "impact": "high", "horizon": "60d",
     "reference_ids": '[]'},
    {"domain": "Technology & Infrastructure", "subdomain": "Cloud & Infrastructure", "score_min": 0, "score_max": 30, "priority": 2,
     "title": "Assess cloud readiness for AI workloads",
     "text": "Evaluate current infrastructure against AI requirements. Plan migration path for compute-intensive workloads to cloud.",
     "effort": "medium", "impact": "medium", "horizon": "60d",
     "reference_ids": '[]'},
    # Technology — Structured
    {"domain": "Technology & Infrastructure", "subdomain": "MLOps & Automation", "score_min": 31, "score_max": 60, "priority": 2,
     "title": "Implement MLOps practices",
     "text": "Establish experiment tracking, model versioning, and basic CI/CD for ML. Start with the most critical production models.",
     "effort": "high", "impact": "high", "horizon": "90d",
     "reference_ids": '[]'},

    # Security & Compliance — Initial
    {"domain": "Security & Compliance", "subdomain": "Regulatory Compliance", "score_min": 0, "score_max": 30, "priority": 1,
     "title": "Conduct EU AI Act impact assessment",
     "text": "Map all AI systems to EU AI Act risk categories. Identify high-risk systems requiring immediate compliance actions.",
     "effort": "medium", "impact": "high", "horizon": "30d",
     "reference_ids": '["eu_ai_act"]'},
    {"domain": "Security & Compliance", "subdomain": "Risk Management", "score_min": 0, "score_max": 30, "priority": 1,
     "title": "Establish AI risk management framework",
     "text": "Define risk assessment process for AI projects. Create risk register and mitigation plans aligned with enterprise risk management.",
     "effort": "medium", "impact": "high", "horizon": "60d",
     "reference_ids": '["nist_ai_rmf", "iso_42001"]'},
    {"domain": "Security & Compliance", "subdomain": "Data Privacy & Security", "score_min": 0, "score_max": 30, "priority": 1,
     "title": "Ensure GDPR compliance for AI data processing",
     "text": "Conduct DPIA for AI systems processing personal data. Implement data anonymization for training datasets.",
     "effort": "medium", "impact": "high", "horizon": "60d",
     "reference_ids": '["gdpr"]'},
    # Security — Structured
    {"domain": "Security & Compliance", "subdomain": "Regulatory Compliance", "score_min": 31, "score_max": 60, "priority": 2,
     "title": "Build AI system documentation for compliance",
     "text": "Create comprehensive documentation for all AI systems covering data sources, model logic, testing, and monitoring. Prepare for audit readiness.",
     "effort": "high", "impact": "high", "horizon": "90d",
     "reference_ids": '["eu_ai_act", "iso_42001"]'},

    # Adoption & Change — Initial
    {"domain": "Adoption & Change", "subdomain": "Training & Skills", "score_min": 0, "score_max": 30, "priority": 1,
     "title": "Launch AI awareness program",
     "text": "Organize AI literacy sessions for all employees. Cover basics of AI, its impact on the industry, and practical applications in their roles.",
     "effort": "low", "impact": "high", "horizon": "30d",
     "reference_ids": '[]'},
    {"domain": "Adoption & Change", "subdomain": "Change Management", "score_min": 0, "score_max": 30, "priority": 2,
     "title": "Develop AI change management plan",
     "text": "Create a communication strategy for AI adoption. Identify change champions in each department. Plan workshops to address concerns.",
     "effort": "low", "impact": "medium", "horizon": "30d",
     "reference_ids": '[]'},
    {"domain": "Adoption & Change", "subdomain": "Culture & Leadership", "score_min": 0, "score_max": 30, "priority": 1,
     "title": "Secure visible leadership commitment to AI",
     "text": "Organize a COMEX presentation on AI strategy and expected outcomes. Get formal commitment and regular review cadence.",
     "effort": "low", "impact": "high", "horizon": "30d",
     "reference_ids": '[]'},
    # Adoption — Structured
    {"domain": "Adoption & Change", "subdomain": "Training & Skills", "score_min": 31, "score_max": 60, "priority": 2,
     "title": "Build role-based AI training curriculum",
     "text": "Develop training programs tailored to roles: executives (strategy), managers (project management), technical teams (hands-on), business users (tools).",
     "effort": "medium", "impact": "high", "horizon": "60d",
     "reference_ids": '[]'},
    {"domain": "Adoption & Change", "subdomain": "Culture & Leadership", "score_min": 31, "score_max": 60, "priority": 2,
     "title": "Foster data-driven decision culture",
     "text": "Implement data-driven decision frameworks. Celebrate data-informed wins. Create internal AI community for knowledge sharing.",
     "effort": "medium", "impact": "medium", "horizon": "60d",
     "reference_ids": '[]'},

    # Deployed / Advanced level recommendations
    {"domain": "Governance", "subdomain": "", "score_min": 61, "score_max": 100, "priority": 3,
     "title": "Optimize AI governance maturity",
     "text": "Refine portfolio management, automate compliance checks, establish AI center of excellence, and implement continuous strategy review cycles.",
     "effort": "medium", "impact": "medium", "horizon": "90d",
     "reference_ids": '["iso_42001"]'},
    {"domain": "Data Foundation", "subdomain": "", "score_min": 61, "score_max": 100, "priority": 3,
     "title": "Advance to real-time data capabilities",
     "text": "Implement real-time data streaming, self-healing pipelines, and automated data quality enforcement. Consider data mesh architecture.",
     "effort": "high", "impact": "medium", "horizon": "90d",
     "reference_ids": '[]'},
    {"domain": "Technology & Infrastructure", "subdomain": "", "score_min": 61, "score_max": 100, "priority": 3,
     "title": "Scale MLOps to enterprise level",
     "text": "Implement advanced MLOps: feature stores, automated retraining, A/B testing, model governance, and multi-cloud optimization.",
     "effort": "high", "impact": "medium", "horizon": "90d",
     "reference_ids": '[]'},
]


def seed_recommendations():
    """Insert seed recommendation rules if table is empty."""
    session = get_session()
    try:
        count = session.query(RecommendationRule).count()
        if count == 0:
            for rule in SEED_RULES:
                session.add(RecommendationRule(**rule))
            session.commit()
    finally:
        session.close()


def get_recommendations(domain_scores, subdomain_scores=None):
    """
    Get applicable recommendations based on current scores.

    Args:
        domain_scores: dict of {domain: score}
        subdomain_scores: dict of {domain: {subdomain: score}} (optional, for finer matching)

    Returns:
        list of recommendation dicts sorted by priority
    """
    session = get_session()
    try:
        all_rules = session.query(RecommendationRule).all()
        recommendations = []

        for rule in all_rules:
            domain = rule.domain
            score = domain_scores.get(domain)
            if score is None:
                continue

            # Check if score falls within rule's range
            if rule.score_min <= score <= rule.score_max:
                # If subdomain specified on rule, check subdomain score too
                if rule.subdomain and subdomain_scores:
                    sd_score = subdomain_scores.get(domain, {}).get(rule.subdomain)
                    if sd_score is not None and not (rule.score_min <= sd_score <= rule.score_max):
                        continue

                recommendations.append({
                    "id": rule.id,
                    "domain": rule.domain,
                    "subdomain": rule.subdomain,
                    "priority": rule.priority,
                    "title": rule.title,
                    "text": rule.text,
                    "effort": rule.effort,
                    "impact": rule.impact,
                    "horizon": rule.horizon,
                    "reference_ids": rule.reference_ids,
                })

        recommendations.sort(key=lambda r: (r["priority"], r["domain"]))
        return recommendations
    finally:
        session.close()


def generate_roadmap(recommendations):
    """
    Generate a 30/60/90-day roadmap from recommendations.
    """
    roadmap = {"30d": [], "60d": [], "90d": []}
    for rec in recommendations:
        horizon = rec.get("horizon", "90d")
        if horizon in roadmap:
            roadmap[horizon].append(rec)
        else:
            roadmap["90d"].append(rec)
    return roadmap
