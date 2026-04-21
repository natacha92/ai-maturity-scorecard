"""
excel_to_questions_agent.py
============================
Pipeline multi-agent pour convertir un fichier Excel de référentiel
en questions JSON compatibles avec questionnaire.json.

Usage :
    # Test gratuit (0 appel API)
    python excel_to_questions_agent.py --input data/referentiel.xlsx --dry-run

    # Production
    python excel_to_questions_agent.py --input data/referentiel.xlsx

    # Output personnalisé
    python excel_to_questions_agent.py --input data/referentiel.xlsx --output data/questionnaire_v2.json

Agents :
    0. Analyzer     → identifie les capacités distinctes par sous-domaine (affiche le plan)
    1. Parser       → lit l'Excel, groupe les lignes par sous-domaine
    2. Enricher     → génère les questions JSON selon le plan (1 appel par sous-domaine)
    3. Validator    → vérifie la cohérence par batch de 10
    4. Consolidator → fusionne avec questionnaire.json existant, déduplique, trie

Règles de scoring :
    Score 0 → rien en place        (ajouté automatiquement)
    Score 1 → niveau 1 Excel       (mapping direct)
    Score 2 → niveau 2 Excel       (mapping direct)
    Score 3 → niveau 3 Excel       (mapping direct)
    MAX = 3 pts — normalisé sur 100 dynamiquement dans scoring.py
"""

import json
import time
import argparse
import pandas as pd
from pathlib import Path
import requests

# ── Config ────────────────────────────────────────────────────────────────────
MODEL      = "claude-sonnet-4-20250514"
MAX_TOKENS = 4000
API_URL    = "https://api.anthropic.com/v1/messages"
HEADERS    = {"Content-Type": "application/json"}


# ── Helpers API ───────────────────────────────────────────────────────────────

def call_claude(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
    """Appel API Claude avec retry exponentiel et gestion budget."""
    payload = {
        "model":       MODEL,
        "max_tokens":  MAX_TOKENS,
        "temperature": temperature,
        "system":      system_prompt,
        "messages":    [{"role": "user", "content": user_prompt}],
    }
    for attempt in range(3):
        try:
            resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=90)
            resp.raise_for_status()
            data = resp.json()
            usage = data.get("usage", {})
            inp   = usage.get("input_tokens", 0)
            out   = usage.get("output_tokens", 0)
            cost  = (inp * 3 + out * 15) / 1_000_000
            print(f"    💰 {inp} in / {out} out — ~${cost:.4f}")
            return data["content"][0]["text"]
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in (429, 402):
                print(f"  ⛔ Limite de budget atteinte — arrêt propre")
                raise SystemExit(1)
            print(f"  ⚠️ Tentative {attempt+1}/3 — HTTP {e.response.status_code}")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"  ⚠️ Tentative {attempt+1}/3 — {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError("API inaccessible après 3 tentatives")


def safe_json_parse(text: str) -> list:
    """Parse JSON depuis la réponse Claude (retire les balises markdown)."""
    text = text.strip()
    if "```" in text:
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text  = "\n".join(lines)
    start = min(
        (text.find("[") if text.find("[") != -1 else len(text)),
        (text.find("{") if text.find("{") != -1 else len(text))
    )
    return json.loads(text[start:])


# ── Agent 0 : Analyzer ────────────────────────────────────────────────────────

ANALYZER_SYSTEM = """
Tu es un expert en conception de référentiels de maturité data.
Tu reçois des lignes d'un tableau Excel représentant les niveaux d'un sous-domaine.

TON RÔLE : identifier les capacités distinctes cachées dans ces lignes.

RÈGLES D'ANALYSE :

1. Une capacité = une dimension métier mesurable indépendamment
   Exemples de capacités DISTINCTES : ERP, CRM, Documentation, Gouvernance
   Exemples de capacités NON distinctes : "niveau 1 ERP" et "niveau 2 ERP" → même capacité

2. Les N lignes Excel représentent N niveaux de maturité.
   Si toutes les lignes parlent du même concept → 1 seule capacité
   Si les lignes mélangent plusieurs concepts distincts → plusieurs capacités

3. Pour chaque capacité identifiée, précise :
   - id        : code court en majuscules (ex: ERP, CRM, GOV)
   - label     : nom court de la capacité
   - justification : pourquoi c'est une capacité distincte (1 phrase)
   - niveaux   : les descriptions des niveaux 1, 2, 3 extraits du Excel

Réponds UNIQUEMENT avec un tableau JSON valide.
Pas de markdown. Commence directement par [

Format attendu :
[
  {
    "id": "ERP",
    "label": "Mise en place ERP",
    "justification": "Système distinct du CRM, mesurable indépendamment",
    "niveau_1": "description niveau 1 pour cette capacité",
    "niveau_2": "description niveau 2 pour cette capacité",
    "niveau_3": "description niveau 3 pour cette capacité",
    "outils_necessaires": [],
    "outils_optionnels": [],
    "pre_requis": "",
    "dependances": "",
    "conditions_progression": ""
  }
]
"""

def agent_analyzer(groups: dict) -> dict:
    """
    Pour chaque groupe (domaine, sous-domaine), identifie les capacités distinctes.
    Affiche le plan pour information (pas de validation bloquante).
    Retourne un dict {(domaine, sous-domaine): [capacités]}.
    """
    print("\n🔍 Agent 0 — Analyzer : identification des capacités...")

    capacity_plan = {}
    total = len(groups)

    for idx, ((domain, subdomain), rows) in enumerate(groups.items(), 1):
        print(f"\n  [{idx}/{total}] {domain} / {subdomain}")

        user_prompt = f"""
Analyse ces lignes Excel et identifie les capacités distinctes.

DOMAINE    : {domain}
SOUS-DOMAINE : {subdomain}

DONNÉES :
{json.dumps(rows, ensure_ascii=False, indent=2)}
"""
        try:
            raw        = call_claude(ANALYZER_SYSTEM, user_prompt)
            capacities = safe_json_parse(raw)

            if isinstance(capacities, list):
                capacity_plan[(domain, subdomain)] = capacities

                # Affiche le plan pour info (non bloquant)
                print(f"    📋 {len(capacities)} capacité(s) identifiée(s) :")
                for cap in capacities:
                    print(f"       • [{cap['id']}] {cap['label']}")
                    print(f"         → {cap['justification']}")
            else:
                print(f"    ⚠️ Réponse inattendue — sous-domaine ignoré")

        except SystemExit:
            raise
        except Exception as e:
            print(f"    ❌ Erreur : {e}")

        time.sleep(1)

    return capacity_plan


# ── Agent 1 : Parser ──────────────────────────────────────────────────────────

def agent_parser(excel_path: Path) -> tuple[list[dict], dict]:
    """
    Lit l'Excel, normalise les colonnes, groupe par (domaine, sous-domaine).
    Retourne (rows, groups). Aucun token utilisé.
    """
    print("\n🔵 Agent 1 — Parser : lecture de l'Excel...")

    df = pd.read_excel(excel_path)
    df.columns = [str(c).strip() for c in df.columns]

    rows = []
    for _, row in df.iterrows():
        r = {col: str(row.get(col, "")).strip() for col in df.columns}
        d = r.get("Domaine principal", "") or r.get("domaine_principal", "")
        if not d or d.lower() == "nan":
            continue
        rows.append(r)

    # Groupe par (domaine, sous-domaine)
    groups = {}
    for r in rows:
        d = r.get("Domaine principal", r.get("domaine_principal", "?"))
        s = r.get("Domaine Spécifique", r.get("domaine_specifique", "?"))
        groups.setdefault((d, s), []).append(r)

    print(f"  ✅ {len(rows)} lignes — {len(groups)} sous-domaines :")
    for (d, s), grp in groups.items():
        print(f"     • {d} / {s} → {len(grp)} niveau(x)")

    return rows, groups


# ── Agent 2 : Enricher ────────────────────────────────────────────────────────

ENRICHER_SYSTEM = """
Tu es un expert en conception de référentiels de maturité data.
Tu reçois un plan de capacités et tu dois générer les questions JSON correspondantes.

═══════════════════════════════════════════════════════
RÈGLES FONDAMENTALES
═══════════════════════════════════════════════════════

1. PRINCIPE : 1 capacité = 1 question scored
   Chaque capacité du plan → 1 applicability + 1 scored + 1 evidence

2. ÉCHELLE DE SCORING — OBLIGATOIRE ET UNIQUE
   Score 0 → rien en place / inexistant    (toujours le premier choice)
   Score 1 → niveau 1 (informel / ad hoc)  = niveau 1 du tableau Excel
   Score 2 → niveau 2 (partiel / structuré) = niveau 2 du tableau Excel
   Score 3 → niveau 3 (optimisé / piloté)  = niveau 3 du tableau Excel
   MAX = 3 pts — JAMAIS de score 4 ou 5

3. MAPPING NIVEAUX EXCEL → CHOICES
   choice 0 : "Aucun(e) [capacité] en place"           score: 0
   choice 1 : [description niveau 1 du plan]            score: 1
   choice 2 : [description niveau 2 du plan]            score: 2
   choice 3 : [description niveau 3 du plan]            score: 3

4. TYPES DE QUESTIONS PAR CAPACITÉ
   - 1 "applicability" : "Est-ce que [capacité] est pertinent pour votre activité ?"
   - 1 "scored"        : "Quel est le niveau de [capacité] ?" (choices 0→3)
   - 1 "evidence"      : "Quels éléments prouvent [capacité] ?" (texte libre)

5. FORMAT DES QUESTION_ID
   APP_[ID]_001, CAP_[ID]_001, EVID_[ID]_001
   ID = code de la capacité fourni dans le plan (ex: ERP, CRM, GOV)

6. APPLICABILITY RULES
   - applicability → "always"
   - scored/evidence → "only_if(APP_[ID]_001 == 'Oui')"

7. N/A
   - scored       → na_allowed: true,  score_mode: "exclude_if_na"
   - applicability → na_allowed: false, score_mode: "normal"
   - evidence     → na_allowed: true,  score_mode: "normal"

8. POIDS (0 à 5)
   - applicability + evidence → poids: 0
   - scored → poids selon importance : 5=critique, 3=important, 1=secondaire

9. FORMULATION
   ❌ Pas d'outil dans le label : "Utilisez-vous SAP ?"
   ✅ Capacité métier : "Quel est le niveau de structuration de votre ERP ?"
   ❌ Vague : "bonne gouvernance"
   ✅ Observable : "politiques définies et appliquées"

10. CHAMPS OBLIGATOIRES
    question_id, parent_question_id, question_type, question_label,
    question_help, type_reponse, choices, poids, niveau,
    applicability_rule, na_allowed, score_mode,
    valeur_donnee, domaine_principal, description_domaine_principal,
    domaine_specifique, description_domaine_specifique,
    niveau_label, niveau_scorecard, description_niveau,
    outils_necessaires, outils_optionnels, pre_requis_metier,
    dependances_inter_domaines, conditions_progression, contrainte_globale,
    ordre_domaine_principal, ordre_domaine_specifique, ordre_niveau,
    capability_group, llm_context

11. CHAMPS DE PROGRESSION — INTERDICTION DES POURCENTAGES
    Concerne : conditions_progression, contrainte_globale, description_niveau

    ❌ INTERDIT :
       "Atteindre 70% de completion"
       "75% des processus complétés"
       "Minimum 80% de couverture"

    ✅ REMPLACER PAR des critères observables et binaires :
       "Les systèmes ERP et CRM couvrent les fonctions opérationnelles critiques"
       "Les processus sont documentés et appliqués par les équipes"
       "Les rôles sont définis, assignés et actifs"

    👉 RÈGLE : si le texte source contient un %, reformule en critère observable.
       Un critère de progression doit répondre à "Est-ce en place ? Oui / Non"
       — jamais à "À quel pourcentage ?"


Réponds UNIQUEMENT avec un tableau JSON valide.
Pas de markdown. Commence directement par [
"""

def agent_enricher(
    capacity_plan: dict,
    existing_questions: list[dict],
    groups: dict,
) -> list[dict]:
    """
    Génère les questions JSON à partir du plan de capacités.
    1 appel API par sous-domaine.
    """
    print("\n🟡 Agent 2 — Enricher : génération des questions...")

    existing_ids  = {q["question_id"] for q in existing_questions}
    domain_orders = {}
    subdom_orders = {}
    for q in existing_questions:
        d = q.get("domaine_principal", "")
        s = q.get("domaine_specifique", "")
        if d: domain_orders[d] = q.get("ordre_domaine_principal", 99)
        if s: subdom_orders[s] = q.get("ordre_domaine_specifique", 99)

    all_new = []
    total   = len(capacity_plan)

    for idx, ((domain, subdomain), capacities) in enumerate(capacity_plan.items(), 1):
        print(f"\n  [{idx}/{total}] {domain} / {subdomain} — {len(capacities)} capacité(s)")

        d_order = domain_orders.get(domain, 10 + idx)
        s_order = subdom_orders.get(subdomain, idx)

        # Récupère les métadonnées du groupe Excel
        group_rows = groups.get((domain, subdomain), [])
        valeur_donnee = group_rows[0].get("Valeur de la données", "") if group_rows else ""
        desc_domaine  = group_rows[0].get("Description du domaine Principal", "") if group_rows else ""
        desc_subdom   = group_rows[0].get("Description du domaine Spécifique", "") if group_rows else ""

        user_prompt = f"""
Génère les questions JSON pour ce sous-domaine.

DOMAINE PRINCIPAL      : {domain}
DESCRIPTION DOMAINE    : {desc_domaine}
SOUS-DOMAINE           : {subdomain}
DESCRIPTION SOUS-DOM   : {desc_subdom}
VALEUR DE LA DONNÉE    : {valeur_donnee}
ORDRE DOMAINE          : {d_order}
ORDRE SOUS-DOMAINE     : {s_order}

CAPACITÉS IDENTIFIÉES PAR L'AGENT 0 :
{json.dumps(capacities, ensure_ascii=False, indent=2)}

IDs DÉJÀ UTILISÉS (ne pas réutiliser) :
{json.dumps(sorted(existing_ids), ensure_ascii=False)}

RAPPEL SCORING :
- choices toujours : score 0 (rien), score 1 (niveau 1), score 2 (niveau 2), score 3 (niveau 3)
- JAMAIS de score 4
- Les descriptions des choices viennent des champs niveau_1/2/3 du plan
"""
        try:
            raw       = call_claude(ENRICHER_SYSTEM, user_prompt)
            questions = safe_json_parse(raw)

            if isinstance(questions, list):
                all_new.extend(questions)
                for q in questions:
                    existing_ids.add(q.get("question_id", ""))
                print(f"    ✅ {len(questions)} questions générées")
            else:
                print(f"    ⚠️ Réponse inattendue")

        except SystemExit:
            raise
        except Exception as e:
            print(f"    ❌ Erreur : {e}")

        time.sleep(1)

    print(f"\n  ✅ Total généré : {len(all_new)} questions")
    return all_new


# ── Agent 3 : Validator ───────────────────────────────────────────────────────

VALIDATOR_SYSTEM = """
Tu es un expert en validation de référentiels de maturité data.
Vérifie et corrige silencieusement ce batch de questions JSON.

VÉRIFICATIONS OBLIGATOIRES :

1. question_id : format correct (APP_XXX_001, CAP_XXX_001, EVID_XXX_001)
2. choices :
   - scored      → exactement 4 choices, scores 0/1/2/3 (JAMAIS 4 ou 5)
   - applicability → choices avec "Oui"/"Non", scores 0/0
   - evidence    → choices vide []
3. poids : 0 pour applicability/evidence, 1 à 5 pour scored
4. na_allowed : false pour applicability, true pour scored/evidence
5. score_mode : "exclude_if_na" pour scored, "normal" pour les autres
6. applicability_rule :
   - applicability → "always"
   - scored/evidence → "only_if(APP_[CODE]_001 == 'Oui')"
7. type_reponse : "single_choice" pour applicability/scored, "text" pour evidence
8. Tous les champs obligatoires présents et non vides
9. question_label : formulation métier, mesurable, objective
10. Score max = 3 — corriger tout score > 3
11. conditions_progression, contrainte_globale, description_niveau :
    - Supprimer tout pourcentage ("70%", "75%", "80%", etc.)
    - Reformuler en critère observable binaire (oui/non)
    - Ex: "Atteindre 70% de completion" 
      → "Les systèmes couvrent les fonctions opérationnelles critiques"
Corrige sans commentaire.
Réponds UNIQUEMENT avec le tableau JSON corrigé.
Pas de markdown. Commence directement par [
"""

def agent_validator(questions: list[dict]) -> list[dict]:
    """Valide et corrige par batch de 10 questions."""
    print("\n🟠 Agent 3 — Validator : validation...")

    validated  = []
    batch_size = 10
    batches    = [questions[i:i+batch_size] for i in range(0, len(questions), batch_size)]

    for idx, batch in enumerate(batches, 1):
        print(f"  Batch {idx}/{len(batches)} ({len(batch)} questions)...")
        try:
            raw       = call_claude(VALIDATOR_SYSTEM,
                                    json.dumps(batch, ensure_ascii=False, indent=2))
            corrected = safe_json_parse(raw)
            if isinstance(corrected, list):
                validated.extend(corrected)
                print(f"    ✅ {len(corrected)} validées")
            else:
                validated.extend(batch)
                print(f"    ⚠️ Pas de correction, batch conservé")
        except SystemExit:
            raise
        except Exception as e:
            print(f"    ❌ Erreur batch {idx} ({e}) — conservé tel quel")
            validated.extend(batch)
        time.sleep(1)

    print(f"  ✅ {len(validated)} questions validées au total")
    return validated


# ── Agent 4 : Consolidator ────────────────────────────────────────────────────

def agent_consolidator(
    existing: list[dict],
    new_questions: list[dict]
) -> list[dict]:
    """
    Fusionne existing + new_questions.
    Déduplique et trie localement — 0 token.
    """
    print("\n🟢 Agent 4 — Consolidator : fusion...")

    existing_ids = {q["question_id"] for q in existing}
    truly_new    = [q for q in new_questions if q.get("question_id") not in existing_ids]

    print(f"  Questions existantes    : {len(existing)}")
    print(f"  Nouvelles (après dédup) : {len(truly_new)}")

    if not truly_new:
        print("  ✅ Rien à ajouter")
        return existing

    combined   = existing + truly_new
    TYPE_ORDER = {"applicability": 0, "scored": 1, "evidence": 2}

    combined.sort(key=lambda q: (
        q.get("ordre_domaine_principal", 99),
        q.get("ordre_domaine_specifique", 99),
        q.get("ordre_niveau", 99),
        TYPE_ORDER.get(q.get("question_type", ""), 3),
    ))

    print(f"  ✅ Questionnaire final : {len(combined)} questions")
    return combined


# ── Pipeline principal ────────────────────────────────────────────────────────

def run_pipeline(
    excel_path: Path,
    questionnaire_path: Path,
    output_path: Path,
    dry_run: bool = False,
):
    print("=" * 60)
    print("🚀 Pipeline multi-agent — Excel → Questions JSON")
    print(f"   Input  : {excel_path}")
    print(f"   Output : {output_path}")
    print(f"   Mode   : {'DRY RUN (0 appel API)' if dry_run else 'PRODUCTION'}")
    print("=" * 60)

    # Charge le questionnaire existant
    print(f"\n📂 Chargement de {questionnaire_path}...")
    with open(questionnaire_path, "r", encoding="utf-8") as f:
        questionnaire_data = json.load(f)
    existing_questions = questionnaire_data.get("questions", [])
    print(f"  ✅ {len(existing_questions)} questions existantes")

    # ── Agent 1 : Parse ───────────────────────────────────────────────────────
    rows, groups = agent_parser(excel_path)
    if not rows:
        print("❌ Aucune ligne trouvée — vérifiez les noms de colonnes")
        return

    if dry_run:
        print("\n⚠️  DRY RUN — arrêt avant les appels API")
        print(f"  {len(rows)} lignes prêtes — {len(groups)} sous-domaines à traiter")
        return

    # ── Agent 0 : Analyze ─────────────────────────────────────────────────────
    capacity_plan = agent_analyzer(groups)
    if not capacity_plan:
        print("❌ Aucune capacité identifiée")
        return

    # Sauvegarde du plan (pour audit)
    plan_path = output_path.parent / f"{output_path.stem}_plan.json"
    plan_serializable = {f"{d}/{s}": caps for (d, s), caps in capacity_plan.items()}
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan_serializable, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Plan sauvegardé : {plan_path}")

    # ── Agent 2 : Enrich ──────────────────────────────────────────────────────
    new_questions = agent_enricher(capacity_plan, existing_questions, groups)
    if not new_questions:
        print("❌ Aucune question générée")
        return

    # Sauvegarde intermédiaire (sécurité)
    raw_path = output_path.parent / f"{output_path.stem}_raw.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(new_questions, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Sauvegarde intermédiaire : {raw_path}")

    # ── Agent 3 : Validate ────────────────────────────────────────────────────
    validated = agent_validator(new_questions)

    # ── Agent 4 : Consolidate ─────────────────────────────────────────────────
    final_questions = agent_consolidator(existing_questions, validated)

    # Sauvegarde finale
    final_data = {**questionnaire_data, "questions": final_questions}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"✅ Pipeline terminé !")
    print(f"   Questions avant  : {len(existing_questions)}")
    print(f"   Questions après  : {len(final_questions)}")
    print(f"   Ajoutées         : {len(final_questions) - len(existing_questions)}")
    print(f"   Plan             : {plan_path}")
    print(f"   Output           : {output_path}")
    print(f"{'=' * 60}")

    print(f"""
⚠️  RAPPEL : mets à jour engine/scoring.py pour le score dynamique :

    # Remplace :
    MAX_SCORE = 4.0
    score_pct = (score / MAX_SCORE) * 100.0

    # Par :
    max_score = max((c["score"] for c in q.get("choices", [])), default=3)
    score_pct = (score / max_score) * 100.0 if max_score > 0 else 0.0
""")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline multi-agent Excel → Questions JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  # Test sans appel API
  python excel_to_questions_agent.py --input data/referentiel.xlsx --dry-run

  # Production
  python excel_to_questions_agent.py --input data/referentiel.xlsx

  # Output personnalisé
  python excel_to_questions_agent.py --input data/referentiel.xlsx --output data/questionnaire_v2.json
        """
    )
    parser.add_argument("--input",         required=True,
                        help="Chemin vers le fichier Excel")
    parser.add_argument("--output",        default="data/questionnaire_updated.json",
                        help="Fichier de sortie")
    parser.add_argument("--questionnaire", default="data/questionnaire.json",
                        help="Questionnaire existant")
    parser.add_argument("--dry-run",       action="store_true",
                        help="Parse l'Excel sans appeler l'API (test gratuit)")
    args = parser.parse_args()

    run_pipeline(
        excel_path=Path(args.input),
        questionnaire_path=Path(args.questionnaire),
        output_path=Path(args.output),
        dry_run=args.dry_run,
    )