"""
Multi-client benchmark engine — Phase 3.
Compare clients by sector, size, or across all assessments.
"""

import json
from collections import defaultdict
from models.database import get_session, Client, Assessment, Response
from engine.scoring import compute_scores
from src.data_loader import load_questionnaire_cached
from pathlib import Path
from engine.scoring import compute_scores, get_maturity_level
QUESTIONNAIRE_PATH = str(Path("data/questionnaire.json"))


def get_all_completed_assessments():
    """Load all completed assessments with their scores."""
    session = get_session()
    try:
        assessments = (
            session.query(Assessment)
            .filter(Assessment.status == "completed")
            .all()
        )

        results = []
        questionnaire = load_questionnaire_cached(QUESTIONNAIRE_PATH)

        for assessment in assessments:
            client = session.query(Client).get(assessment.client_id)
            if not client:
                continue

            responses_db = (
                session.query(Response)
                .filter(Response.assessment_id == assessment.id)
                .all()
            )

            resp_dict = {}
            for r in responses_db:
                resp_dict[r.question_id] = {
                    "score": r.selected_score,
                    "label": r.selected_label,
                    "is_na": r.is_na,
                    "selected_choice": r.selected_label,
                }

            scores = compute_scores(questionnaire, resp_dict)

            scores["maturity_level"] = get_maturity_level(scores["global_score"])
            
            results.append({
                "assessment_id": assessment.id,
                "assessment_name": assessment.name,
                "client_id": client.id,
                "client_name": client.name,
                "sector": client.sector or "Unknown",
                "size": client.size or "Unknown",
                "country": client.country or "Unknown",
                "global_score": scores["global_score"],
                "domain_scores": scores["domains"],
                "maturity_level": scores["maturity_level"],
                "created_at": str(assessment.created_at),
            })

        return results
    finally:
        session.close()


def benchmark_by_sector(assessments):
    """Group assessments by sector and compute averages."""
    by_sector = defaultdict(list)
    for a in assessments:
        by_sector[a["sector"]].append(a)

    result = {}
    for sector, items in by_sector.items():
        domain_totals = defaultdict(list)
        global_scores = []
        for item in items:
            global_scores.append(item["global_score"])
            for domain, score in item["domain_scores"].items():
                domain_totals[domain].append(score)

        result[sector] = {
            "count": len(items),
            "avg_global": round(sum(global_scores) / len(global_scores), 1),
            "avg_domains": {
                d: round(sum(s) / len(s), 1) for d, s in domain_totals.items()
            },
        }
    return result


def benchmark_by_size(assessments):
    """Group assessments by company size and compute averages."""
    by_size = defaultdict(list)
    for a in assessments:
        by_size[a["size"]].append(a)

    result = {}
    for size, items in by_size.items():
        domain_totals = defaultdict(list)
        global_scores = []
        for item in items:
            global_scores.append(item["global_score"])
            for domain, score in item["domain_scores"].items():
                domain_totals[domain].append(score)

        result[size] = {
            "count": len(items),
            "avg_global": round(sum(global_scores) / len(global_scores), 1),
            "avg_domains": {
                d: round(sum(s) / len(s), 1) for d, s in domain_totals.items()
            },
        }
    return result


def compute_percentile(score, all_scores):
    """Compute the percentile rank of a score within a list of scores."""
    if not all_scores:
        return 50
    below = sum(1 for s in all_scores if s < score)
    return round((below / len(all_scores)) * 100, 1)


def get_client_ranking(client_id, assessments):
    """Get a client's ranking among all assessments."""
    client_assessments = [a for a in assessments if a["client_id"] == client_id]
    if not client_assessments:
        return None

    latest = max(client_assessments, key=lambda a: a["created_at"])
    all_globals = [a["global_score"] for a in assessments]
    all_globals_sorted = sorted(all_globals, reverse=True)

    rank = all_globals_sorted.index(latest["global_score"]) + 1

    return {
        "client_name": latest["client_name"],
        "global_score": latest["global_score"],
        "rank": rank,
        "total": len(assessments),
        "percentile": compute_percentile(latest["global_score"], all_globals),
        "domain_scores": latest["domain_scores"],
    }


def get_client_history(client_id, assessments):
    """Get score evolution over time for a client."""
    client_assessments = sorted(
        [a for a in assessments if a["client_id"] == client_id],
        key=lambda a: a["created_at"],
    )
    return client_assessments
