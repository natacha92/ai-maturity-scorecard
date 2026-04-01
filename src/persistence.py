import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

def save_assessment(assessments_dir: Path, client_name: str, assessment_name: str, responses: Dict[str, Dict[str, Any]], scores: Dict[str, Any]) -> Path:
    assessments_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "assessment_id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "client": {
            "name": client_name,
            "secteur": None,
            "taille": None
        },
        "assessment": {
            "name": assessment_name,
            "version": "v1",
            "consultant": None
        },
        "responses": [],
        "scores": scores
    }

    for r in responses.values():
        payload["responses"].append({
            "question_id": r.get("question_id"),
            "question_type": r.get("question_type"),
            "answer": {
                "selected_choice": r.get("selected_choice"),
                "score": r.get("score")
            },
            "context": {
                "comment": r.get("comment"),
                "current_tools": r.get("current_tools", []),
                "current_documents": r.get("current_documents", []),
                "pain_points": r.get("pain_points", []),
                "weaknesses": r.get("weaknesses", []),
                "obstacles": r.get("obstacles", [])
            }
        })

    safe_client = client_name.replace(" ", "_") or "client"
    safe_assessment = assessment_name.replace(" ", "_") or "audit"
    path = assessments_dir / f"{safe_client}__{safe_assessment}.json"

    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return path