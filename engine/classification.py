"""
Auto-classification of client maturity archetype based on score profile.
Phase 1 feature.
"""

ARCHETYPES = [
    {
        "id": "data_strong_gov_weak",
        "name": "Data-rich, Governance-poor",
        "description": "Strong data foundation but lacking governance and strategy. Risk of uncontrolled AI proliferation.",
        "conditions": {
            "Data Foundation": {"min": 50},
            "Governance": {"max": 40},
        },
        "risk_level": "high",
        "key_recommendation": "Prioritize governance framework before scaling AI use cases.",
    },
    {
        "id": "strategy_no_execution",
        "name": "Strategy without Execution",
        "description": "Good governance and strategy in place but weak technology and industrialization. Classic top-down approach.",
        "conditions": {
            "Governance": {"min": 50},
            "Technology & Infrastructure": {"max": 40},
        },
        "risk_level": "medium",
        "key_recommendation": "Invest in technology platform and MLOps to enable execution.",
    },
    {
        "id": "tech_driven_no_value",
        "name": "Technology-driven, Value-blind",
        "description": "Strong technical capabilities but weak use case identification and ROI tracking. Building for the sake of building.",
        "conditions": {
            "Technology & Infrastructure": {"min": 50},
            "Use Cases & Value": {"max": 40},
        },
        "risk_level": "medium",
        "key_recommendation": "Focus on business-driven use case selection and ROI measurement.",
    },
    {
        "id": "compliance_first",
        "name": "Compliance-first, Innovation-late",
        "description": "Strong on security and compliance but weak on adoption and use cases. Risk-averse culture slowing AI adoption.",
        "conditions": {
            "Security & Compliance": {"min": 50},
            "Adoption & Change": {"max": 40},
        },
        "risk_level": "low",
        "key_recommendation": "Balance compliance with innovation. Launch internal AI champions program.",
    },
    {
        "id": "early_stage",
        "name": "Early Stage — Greenfield",
        "description": "Low maturity across all domains. Starting the AI journey.",
        "conditions": {
            "_global_max": 30,
        },
        "risk_level": "medium",
        "key_recommendation": "Start with governance and quick-win use cases. Build foundations progressively.",
    },
    {
        "id": "balanced_growth",
        "name": "Balanced Growth",
        "description": "Moderate and balanced maturity across domains. Good foundation for scaling.",
        "conditions": {
            "_global_min": 40,
            "_global_max": 70,
            "_variance_max": 15,
        },
        "risk_level": "low",
        "key_recommendation": "Continue balanced investment. Focus on weakest domain to maintain alignment.",
    },
    {
        "id": "advanced_leader",
        "name": "AI Leader",
        "description": "High maturity across all domains. Focus on optimization and innovation.",
        "conditions": {
            "_global_min": 70,
        },
        "risk_level": "low",
        "key_recommendation": "Optimize, innovate, and share best practices. Consider AI center of excellence.",
    },
]


def classify_client(domain_scores, global_score):
    """
    Classify a client into a maturity archetype based on their score profile.

    Returns:
        dict with archetype info, or a default 'unclassified' archetype.
    """
    scores = domain_scores
    variance = _compute_variance(list(scores.values())) if scores else 0

    for archetype in ARCHETYPES:
        if _matches(archetype["conditions"], scores, global_score, variance):
            return {
                "archetype_id": archetype["id"],
                "archetype_name": archetype["name"],
                "description": archetype["description"],
                "risk_level": archetype["risk_level"],
                "key_recommendation": archetype["key_recommendation"],
            }

    return {
        "archetype_id": "unclassified",
        "archetype_name": "Mixed Profile",
        "description": "Score profile does not match a standard archetype. Review domain scores individually.",
        "risk_level": "medium",
        "key_recommendation": "Focus on the weakest domain to address the largest gap.",
    }


def _matches(conditions, domain_scores, global_score, variance):
    for key, constraint in conditions.items():
        if key == "_global_min":
            if global_score < constraint:
                return False
        elif key == "_global_max":
            if global_score > constraint:
                return False
        elif key == "_variance_max":
            if variance > constraint:
                return False
        elif key in domain_scores:
            score = domain_scores[key]
            if "min" in constraint and score < constraint["min"]:
                return False
            if "max" in constraint and score > constraint["max"]:
                return False
        else:
            return False
    return True


def _compute_variance(values):
    if not values:
        return 0
    mean = sum(values) / len(values)
    return (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
