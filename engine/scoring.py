from typing import Any, Dict, List, Optional, Tuple
from engine.rules import parse_rule

# ── Constantes ────────────────────────────────────────────────────────────────

MAX_SCORE = 4.0  # Score max possible par question dans le JSON
# Dans scoring.py, remplace score_to_maturity_label par :

MATURITY_LEVELS = [
    {"min": 0,  "max": 30,  "level": 1, "label": "Initial",         "color": "#EF4444", "description": "Approche non structurée, systèmes de base absents ou non utilisés."},
    {"min": 31, "max": 60,  "level": 2, "label": "En développement","color": "#F97316", "description": "Initiatives en cours mais non industrialisées, résultats variables."},
    {"min": 61, "max": 80,  "level": 3, "label": "Structuré",       "color": "#FACC15", "description": "Mise en œuvre active avec des processus définis et suivis."},
    {"min": 81, "max": 100, "level": 4, "label": "Optimisé",        "color": "#22C55E", "description": "Approche optimisée, gouvernée et en amélioration continue."},
]

def get_maturity_level(score: Optional[float]) -> Dict[str, Any]:
    """Retourne le dict complet du niveau de maturité pour un score /100."""
    if score is None:
        return {"level": 0, "label": "Non évalué", "color": "#F3F4F6", "description": "Aucune donnée disponible."}
    for m in MATURITY_LEVELS:
        if m["min"] <= score <= m["max"]:
            return m
    return MATURITY_LEVELS[-1]

def score_to_maturity_label(score: Optional[float]) -> str:
    return get_maturity_level(score)["label"]

def score_to_color(score: Optional[float]) -> str:
    return get_maturity_level(score)["color"]

def compute_scores(questions: List[Dict[str, Any]], responses: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calcule le score global et par domaine principal.
    - Exclut les questions non applicables (applicability_rule)
    - Exclut les questions marquées N/A (score_mode: exclude_if_na)
    - Pondère par 'poids'
    - Normalise sur 100
    """
    domain_scores: Dict[str, Dict[str, float]] = {}
    global_weighted_sum = 0.0
    global_weight = 0.0

    for q in questions:
        if q.get("question_type") != "scored":
            continue
        if not parse_rule(q.get("applicability_rule", "always"), responses):
            continue

        response = responses.get(q["question_id"])

        # Question N/A : exclure si score_mode == exclude_if_na
        if response and response.get("is_na"):
            if q.get("score_mode") == "exclude_if_na":
                continue  # on exclut du calcul, elle ne pénalise pas
            else:
                score = 0.0  # score_mode normal : N/A compte comme 0
        elif not response or response.get("score") is None:
            continue  # pas encore répondu → on ignore
        else:
            score = float(response["score"])

        weight = float(q.get("poids", 1))
        score_pct = (score / MAX_SCORE) * 100.0
        domain = q.get("domaine_principal", "Autre")

        domain_scores.setdefault(domain, {"weighted_sum": 0.0, "weight": 0.0})
        domain_scores[domain]["weighted_sum"] += score_pct * weight
        domain_scores[domain]["weight"] += weight

        global_weighted_sum += score_pct * weight
        global_weight += weight

    result = {
        # Score global normalisé sur 100
        "global_score": round(global_weighted_sum / global_weight, 1) if global_weight else None,
        "domains": {},
    }

    for domain, agg in domain_scores.items():
        result["domains"][domain] = round(agg["weighted_sum"] / agg["weight"], 1) if agg["weight"] else None

    return result

def build_maturity_structure(questions: List[Dict[str, Any]], responses: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:

    grouped: Dict[str, Dict[str, Any]] = {}

    for q in questions:
        if q.get("question_type") != "scored":
            continue
        if not parse_rule(q.get("applicability_rule", "always"), responses):
            continue

        response = responses.get(q["question_id"])

         # Même logique N/A que compute_scores
        if response and response.get("is_na"):
            if q.get("score_mode") == "exclude_if_na":
                continue
            score_pct = 0.0
        elif not response or response.get("score") is None:
            continue
        else:
            score_pct = (float(response["score"]) / MAX_SCORE) * 100.0

        domain        = q.get("domaine_principal", "Autre")
        segment       = q.get("domaine_specifique", "Autre")
        cap_group     = q.get("capability_group", "NA")
        domain_order  = q.get("ordre_domaine_principal", 999)
        segment_order = q.get("ordre_domaine_specifique", 999)
        weight        = float(q.get("poids", 1))

        # Domaine principal
        grouped.setdefault(domain, {
            "label": domain,
            "score_sum": 0.0, "weight_sum": 0.0,
            "order": domain_order,
            "segments": {}
        })

        # Sous-domaine
        grouped[domain]["segments"].setdefault(segment, {
            "label": segment,
            "score_sum": 0.0, "weight_sum": 0.0,
            "order": segment_order,
            "capability_groups": {}
        })

        # Capability group (ex: ERP, CRM...)
        if cap_group and cap_group != "NA":
            grouped[domain]["segments"][segment]["capability_groups"].setdefault(cap_group, {
                "label": cap_group,
                "score_sum": 0.0, "weight_sum": 0.0,
            })
            grouped[domain]["segments"][segment]["capability_groups"][cap_group]["score_sum"] += score_pct * weight
            grouped[domain]["segments"][segment]["capability_groups"][cap_group]["weight_sum"] += weight

        grouped[domain]["segments"][segment]["score_sum"] += score_pct * weight
        grouped[domain]["segments"][segment]["weight_sum"] += weight
        grouped[domain]["score_sum"] += score_pct * weight
        grouped[domain]["weight_sum"] += weight

    # ── Mise en forme finale ──────────────────────────────────────────────────
    result = []
    for _, domain_data in sorted(grouped.items(), key=lambda x: x[1]["order"]):
        segments = []
        for _, seg_data in sorted(domain_data["segments"].items(), key=lambda x: x[1]["order"]):

            # Capability groups
            cap_groups = []
            for cap_label, cap_data in seg_data["capability_groups"].items():
                cap_score = _safe_score(cap_data)
                cap_groups.append({
                    "label": cap_label,
                    "score": cap_score,
                    "color": score_to_color(cap_score),
                    "maturity": score_to_maturity_label(cap_score),
                })

            seg_score = _safe_score(seg_data)
            segments.append({
                "label": seg_data["label"],
                "score": seg_score,
                "color": score_to_color(seg_score),
                "maturity": score_to_maturity_label(seg_score),
                "capability_groups": cap_groups,
            })

        domain_score = _safe_score(domain_data)
        result.append({
            "label": domain_data["label"],
            "score": domain_score,
            "color": score_to_color(domain_score),
            "maturity": score_to_maturity_label(domain_score),
            "segments": segments,
        })

    return result

# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_score(data: Dict[str, float]) -> Optional[float]:
    """Calcule un score arrondi ou None si aucun poids."""
    if data["weight_sum"] <= 0:
        return None
    return round(data["score_sum"] / data["weight_sum"], 1)


def compute_completion(
    questions: List[Dict[str, Any]],
    responses: Dict[str, Dict[str, Any]]
) -> Tuple[int, int]:
    """
    Retourne (questions_répondues, questions_applicables_total).
    Utile pour afficher une barre de progression dans le questionnaire.
    """
    total = 0
    answered = 0

    for q in questions:
        if q.get("question_type") == "evidence":
            continue  # on ne compte pas les preuves dans la completion
        if not parse_rule(q.get("applicability_rule", "always"), responses):
            continue
        total += 1
        r = responses.get(q["question_id"])
        if r and (r.get("score") is not None or r.get("is_na")):
            answered += 1

    return answered, total

def compute_gap_analysis(
    domain_scores: Dict[str, Optional[float]],
    target_scores: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """Gap entre score actuel et cible par domaine (défaut cible = 70)."""
    if target_scores is None:
        target_scores = {d: 70.0 for d in domain_scores}

    gaps = {}
    for domain, current in domain_scores.items():
        if current is None:
            continue
        target = target_scores.get(domain, 70.0)
        gaps[domain] = {
            "current": current,
            "target": target,
            "gap": round(target - current, 1),
            "gap_pct": round(((target - current) / target) * 100, 1) if target > 0 else 0,
        }
    return gaps