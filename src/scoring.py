from typing import Any, Dict, List, Optional
from src.rules import parse_rule

def compute_scores(questions: List[Dict[str, Any]], responses: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    domain_scores: Dict[str, Dict[str, float]] = {}
    global_weighted_sum = 0.0
    global_weight = 0.0

    for q in questions:
        if q.get("question_type") != "scored":
            continue
        if not parse_rule(q.get("applicability_rule", "always"), responses):
            continue

        response = responses.get(q["question_id"])
        if not response or response.get("score") is None:
            continue

        score = float(response["score"])
        weight = float(q.get("poids", 1))
        domain = q.get("domaine_principal", "Autre")

        domain_scores.setdefault(domain, {"weighted_sum": 0.0, "weight": 0.0})
        domain_scores[domain]["weighted_sum"] += score * weight
        domain_scores[domain]["weight"] += weight

        global_weighted_sum += score * weight
        global_weight += weight

    result = {
        "global_score": round(global_weighted_sum / global_weight, 2) if global_weight else None,
        "domains": {},
    }

    for domain, agg in domain_scores.items():
        result["domains"][domain] = round(agg["weighted_sum"] / agg["weight"], 2) if agg["weight"] else None

    return result

def score_to_color(score: Optional[float]) -> str:
    if score is None:
        return "#F3F4F6"
    if score < 25:
        return "#E5E7EB"
    if score < 50:
        return "#FACC15"
    return "#22C55E"

def build_maturity_structure(questions: List[Dict[str, Any]], responses: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}

    for q in questions:
        if q.get("question_type") != "scored":
            continue
        if not parse_rule(q.get("applicability_rule", "always"), responses):
            continue

        response = responses.get(q["question_id"])
        if not response or response.get("score") is None:
            continue

        domain = q.get("domaine_principal", "Autre")
        segment = q.get("domaine_specifique", "Autre")
        domain_order = q.get("ordre_domaine_principal", 999)
        segment_order = q.get("ordre_domaine_specifique", 999)

        weight = float(q.get("poids", 1))
        score_pct = (float(response["score"]) / 4.0) * 100.0

        grouped.setdefault(domain, {
            "label": domain,
            "score_sum": 0.0,
            "weight_sum": 0.0,
            "order": domain_order,
            "segments": {}
        })

        grouped[domain]["segments"].setdefault(segment, {
            "label": segment,
            "score_sum": 0.0,
            "weight_sum": 0.0,
            "order": segment_order
        })

        grouped[domain]["segments"][segment]["score_sum"] += score_pct * weight
        grouped[domain]["segments"][segment]["weight_sum"] += weight
        grouped[domain]["score_sum"] += score_pct * weight
        grouped[domain]["weight_sum"] += weight

    result = []
    for _, domain_data in sorted(grouped.items(), key=lambda x: x[1]["order"]):
        segments = []
        for _, seg_data in sorted(domain_data["segments"].items(), key=lambda x: x[1]["order"]):
            seg_score = round(seg_data["score_sum"] / seg_data["weight_sum"]) if seg_data["weight_sum"] > 0 else None
            segments.append({
                "label": seg_data["label"],
                "score": seg_score,
                "color": score_to_color(seg_score),
            })

        level_score = round(domain_data["score_sum"] / domain_data["weight_sum"]) if domain_data["weight_sum"] > 0 else None

        result.append({
            "label": domain_data["label"],
            "score": level_score,
            "segments": segments,
        })

    return result