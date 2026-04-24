from typing import Any, Dict, List, Optional, Tuple
from engine.rules import parse_rule

# ── Constantes ────────────────────────────────────────────────────────────────

def get_max_score(question: Dict[str, Any]) -> float:
    """Détecte dynamiquement le score max des choices."""
    choices = question.get("choices", [])
    if not choices:
        return 3.0
    return float(max(c.get("score", 0) for c in choices))


def compute_document_penalty(
    question: Dict[str, Any],
    questions: List[Dict[str, Any]],
    document_reviews: Dict[str, List[Dict[str, Any]]],
) -> float:
    """
    Calcule un coefficient de pénalité documentaire (entre 0.5 et 1.0)
    pour une question scored, en se basant sur les DocumentReview de la
    question evidence associée (même sous-domaine, même niveau excel).

    Logique :
      - Si aucune question evidence associée, ou aucun review → pas de pénalité (1.0)
      - conforme  = 1.0  (pas de pénalité)
      - partiel   = 0.75 (pénalité légère)
      - absent    = 0.5  (pénalité forte)
      - non_vérifié → ignoré dans le calcul

    Le coefficient final est la moyenne des scores des reviews analysés.
    Le score scored est multiplié par ce coefficient.

    Exemple :
      Score déclaré = 3 (max), 2 docs : 1 conforme + 1 absent
      → coefficient = (1.0 + 0.5) / 2 = 0.75
      → score ajusté = 3 * 0.75 = 2.25 sur 3 → 75% au lieu de 100%
    """
    STATUS_COEFF = {"conforme": 1.0, "partiel": 0.75, "absent": 0.5}

    # Trouve la question evidence associée :
    # même domaine_specifique et même excel_line_ref
    scored_line = question.get("excel_line_ref")
    scored_subdom = question.get("domaine_specifique")

    linked_evid_ids = [
        q["question_id"]
        for q in questions
        if q.get("question_type") == "evidence"
        and q.get("domaine_specifique") == scored_subdom
        and q.get("excel_line_ref") == scored_line
    ]

    if not linked_evid_ids:
        return 1.0  # Pas d'evidence associée → pas de pénalité

    # Collecte tous les reviews de ces questions evidence
    all_coeffs = []
    for evid_id in linked_evid_ids:
        reviews = document_reviews.get(evid_id, [])
        for rev in reviews:
            status = rev.get("status", "non_vérifié")
            if status in STATUS_COEFF:
                all_coeffs.append(STATUS_COEFF[status])

    if not all_coeffs:
        return 1.0  # Reviews non encore saisis → pas de pénalité

    return sum(all_coeffs) / len(all_coeffs)




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

def compute_level_info(score: Optional[float], max_score: float = 3.0) -> Dict[str, Any]:
    """
    Retourne le niveau atteint et la progression vers le suivant.
    
    Exemple avec max_score=3 :
      score=0 → niveau 0, progression 0%  vers niveau 1
      score=1 → niveau 1, progression 33% vers niveau 2
      score=2 → niveau 2, progression 66% vers niveau 3
      score=3 → niveau 3, progression 100% (terminé)
    """
    if score is None:
        return {
            "niveau_atteint":   None,
            "niveau_max":       int(max_score),
            "progression_pct":  None,
            "vers_niveau":      None,
            "label":            "Non évalué",
            "complete":         False,
        }

    niveau     = int(score)
    niveau_max = int(max_score)
    pct        = round((score / max_score) * 100, 1) if max_score > 0 else 0

    return {
        "niveau_atteint":  niveau,
        "niveau_max":      niveau_max,
        "progression_pct": pct,
        "vers_niveau":     niveau + 1 if niveau < niveau_max else None,
        "label":           f"Niveau {niveau}" if niveau > 0 else "Non démarré",
        "complete":        niveau >= niveau_max,
    }


def compute_scores(
    questions: List[Dict[str, Any]],
    responses: Dict[str, Dict[str, Any]],
    document_reviews: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    Calcule le score global et par domaine principal.
    - Exclut les questions non applicables (applicability_rule)
    - Exclut les questions marquées N/A (score_mode: exclude_if_na)
    - Pondère par 'poids'
    - Pondère aussi par la confiance consultant
    - Applique un coefficient de pénalité documentaire si document_reviews fourni
    - Normalise sur 100

    document_reviews : dict {question_id: [review_dict, ...]}
      Si fourni, les scores scored sont multipliés par le coefficient
      calculé depuis les DocumentReview de la question evidence associée.
    """
    if document_reviews is None:
        document_reviews = {}

    domain_scores: Dict[str, Dict[str, float]] = {}
    global_weighted_sum = 0.0
    global_weight = 0.0
    confidence_sum = 0.0
    confidence_count = 0

    for q in questions:
        if q.get("question_type") != "scored":
            continue
        if not parse_rule(q.get("applicability_rule", "always"), responses):
            continue

        response = responses.get(q["question_id"])

        if response and response.get("is_na"):
            if q.get("score_mode") == "exclude_if_na":
                continue
            else:
                score = 0.0
        elif not response:
            continue
        elif response.get("score") is None:
            continue
        else:
            score = float(response["score"])

        weight     = float(q.get("poids", 1))
        confidence = float(response.get("consultant_confidence", 1.0))
        max_score  = get_max_score(q)
        score_pct  = (score / max_score) * 100.0 if max_score > 0 else 0.0

        # ── Pénalité documentaire ─────────────────────────────────
        doc_penalty = compute_document_penalty(q, questions, document_reviews)
        adjusted_score_pct = score_pct * confidence * doc_penalty

        domain = q.get("domaine_principal", "Autre")
        domain_scores.setdefault(domain, {"weighted_sum": 0.0, "weight": 0.0})
        domain_scores[domain]["weighted_sum"] += adjusted_score_pct * weight
        domain_scores[domain]["weight"]       += weight

        global_weighted_sum += adjusted_score_pct * weight
        global_weight       += weight

        confidence_sum  += confidence
        confidence_count += 1

    result = {
        "global_score": round(global_weighted_sum / global_weight, 1) if global_weight else None,
        "domains":      {},
        "avg_confidence": round(confidence_sum / confidence_count, 2) if confidence_count else None,
    }

    for domain, agg in domain_scores.items():
        result["domains"][domain] = (
            round(agg["weighted_sum"] / agg["weight"], 1) if agg["weight"] else None
        )

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
        elif not response:
            continue
        elif response.get("score") is None:
            continue
        else:
            max_score = get_max_score(q)
            score_pct = (float(response["score"]) / max_score) * 100.0

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
    responses: Dict[str, Dict[str, Any]],
    domain: Optional[str] = None,
) -> Tuple[int, int, int, int]:
    """
    Retourne (scored_répondues, scored_total, evidence_remplies, evidence_total).
    Une question est considérée répondue si elle est présente dans responses
    (sauvegardée en base), quelle que soit la valeur du score.
    """
    scored_total    = 0
    scored_answered = 0
    evid_total      = 0
    evid_answered   = 0

    for q in questions:
        # Filtre domaine
        if domain and q.get("domaine_principal") != domain:
            continue
        # Filtre applicabilité — on utilise responses pour les règles
        if not parse_rule(q.get("applicability_rule", "always"), responses):
            continue

        qtype = q.get("question_type")
        qid   = q["question_id"]

        # Une question est répondue si elle est présente dans responses (a été sauvegardée)
        is_answered = qid in responses

        if qtype == "scored":
            scored_total += 1
            if is_answered:
                scored_answered += 1
        elif qtype == "evidence":
            evid_total += 1
            if is_answered:
                evid_answered += 1

    return scored_answered, scored_total, evid_answered, evid_total

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