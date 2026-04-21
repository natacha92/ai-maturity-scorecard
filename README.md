# Data Maturity Scorecard

Application Streamlit de diagnostic de maturité data pour cabinets de conseil.  
Elle guide l'auditeur à travers un questionnaire structuré, collecte des preuves documentaires, calcule un score de maturité pondéré et génère des livrables clients (scorecard, rapport COMEX, roadmap).

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Installation](#installation)
- [Lancement](#lancement)
- [Structure du projet](#structure-du-projet)
- [Le questionnaire JSON](#le-questionnaire-json)
- [Modèle de données](#modèle-de-données)
- [Moteur de scoring](#moteur-de-scoring)
- [Audit documentaire](#audit-documentaire)
- [Pages de l'application](#pages-de-lapplication)
- [Mettre à jour le questionnaire](#mettre-à-jour-le-questionnaire)
- [Roadmap](#roadmap)

---

## Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| **Questionnaire guidé** | 302 questions sur 7 domaines, 44 sous-domaines, avec applicabilité dynamique |
| **Scoring de maturité** | Score /100 par domaine, pondéré par le poids des questions et la confiance de l'auditeur |
| **Audit documentaire** | Analyse experte de chaque document fourni (Conforme / Partiel / Absent) |
| **Pénalité documentaire** | Le score déclaratif est automatiquement modulé par les résultats de l'audit documentaire |
| **Scorecard visuelle** | Maturity map, gap analysis, archétype client |
| **Rapport COMEX** | Export PDF de synthèse exécutive |
| **Roadmap priorisée** | Recommandations 30/60/90 jours avec matrice impact/effort |
| **Benchmark sectoriel** | Comparaison par secteur et taille d'entreprise |
| **Multi-clients / multi-assessments** | Gestion de plusieurs clients et historique des audits |

---

## Architecture

```
app.py                          # Point d'entrée Streamlit
│
├── pages/
│   ├── 0_Admin.py              # Administration (import JSON, gestion BDD)
│   ├── 1_Clients.py            # Gestion des clients
│   ├── 2_Questionnaire.py      # Saisie du questionnaire + audit documentaire
│   ├── 3_Scorecard.py          # Scorecard de maturité
│   ├── 4_Recommendations.py    # Roadmap et recommandations
│   ├── 5_COMEX_Report.py       # Rapport exécutif PDF
│   ├── 6_Benchmark.py          # Benchmark sectoriel
│   └── 7_Audit_Documentaire.py # Synthèse de l'audit documentaire
│
├── models/
│   └── database.py             # Modèles SQLAlchemy + fonctions utilitaires
│
├── engine/
│   ├── scoring.py              # Calcul des scores de maturité
│   ├── rules.py                # Évaluation des règles d'applicabilité
│   ├── recommendations.py      # Génération des recommandations
│   ├── classification.py       # Archétypes clients
│   └── benchmark.py            # Comparaison sectorielle
│
├── src/
│   ├── data_loader.py          # Chargement et cache du questionnaire JSON
│   ├── config.py               # Configuration globale
│   ├── state.py                # Session Streamlit
│   └── persistence.py          # Sauvegarde JSON legacy
│
├── reports/
│   └── comex.py                # Génération du rapport COMEX
│
├── utils/
│   └── charts.py               # Helpers graphiques Plotly
│
└── data/
    ├── questionnaire.json       # Référentiel de questions (source de vérité)
    └── referentiel.xlsx         # Référentiel source (Excel d'origine)
```

**Base de données :** SQLite (`paims.db`) — créée automatiquement au premier lancement.

---

## Installation

### Prérequis

- Python 3.9+
- pip

### Étapes

```bash
# 1. Cloner le dépôt
git clone <repo-url>
cd ai-maturity-scorecard

# 2. Créer un environnement virtuel (recommandé)
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Vérifier que le questionnaire est bien en place
ls data/questionnaire.json
```

### Dépendances principales

```
streamlit       # Interface web
sqlalchemy      # ORM SQLite
pandas          # Manipulation de données
plotly          # Graphiques interactifs
reportlab       # Génération PDF
```

---

## Lancement

```bash
streamlit run app.py
```

L'application est accessible sur `http://localhost:8501`.

La base de données SQLite (`paims.db`) est créée automatiquement au premier lancement dans le répertoire courant.

---

## Structure du projet

### Flux de travail

```
1. Créer un client         →  page 1_Clients
2. Démarrer un assessment  →  page 2_Questionnaire
3. Remplir le questionnaire par domaine
4. Uploader les documents  →  dans chaque question evidence
5. Analyser les documents  →  expander "Analyse documentaire"
6. Sauvegarder + Terminer  →  boutons en bas de page
7. Consulter les résultats →  pages 3, 4, 5, 6, 7
```

---

## Le questionnaire JSON

**Fichier :** `data/questionnaire.json`  
**Source :** `questionnaire_enrichi.json` (version enrichie avec documents attendus et points à valider)

### Statistiques

| Métrique | Valeur |
|---|---|
| Questions totales | 302 |
| Questions d'applicabilité | 32 |
| Questions scored (notées 0→3) | 135 |
| Questions evidence (preuves) | 135 |
| Domaines principaux | 7 |
| Sous-domaines | 44 |
| Documents attendus (sur questions evidence) | 400 |
| Points à valider (sur ces documents) | 1 467 |

### Les 7 domaines

| # | Domaine | Questions |
|---|---|---|
| 1 | Fondation opérationnelle du business | 35 |
| 2 | Data Management | 49 |
| 3 | Business Intelligence et Reporting | 77 |
| 4 | Data Science et Modélisation Avancée | 37 |
| 5 | IA / Automatisations | 25 |
| 6 | Data Driven Culture | 42 |
| 7 | Data Sharing | 37 |

### Structure d'une question

Chaque entrée du JSON suit ce schéma :

```json
{
  "question_id": "CAP_GOV_005",
  "question_type": "scored",
  "question_label": "Des politiques de gestion des données sont-elles définies ?",
  "question_help": "Texte d'aide affiché sous la question",
  "type_reponse": "single_choice",
  "choices": [
    { "label": "Aucune politique définie", "score": 0 },
    { "label": "Pratiques informelles", "score": 1 },
    { "label": "Politique formalisée", "score": 2 },
    { "label": "Gouvernance complète et auditée", "score": 3 }
  ],
  "poids": 4,
  "applicability_rule": "only_if(APP_GOV_001 == 'Oui')",
  "na_allowed": true,
  "score_mode": "exclude_if_na",
  "domaine_principal": "Data Management",
  "domaine_specifique": "Gouvernance",
  "excel_line_ref": 17
}
```

### Types de questions

| Type | Rôle | Impact score |
|---|---|---|
| `applicability` | Active ou désactive un groupe de questions | Non |
| `scored` | Question notée de 0 à 3 (score de maturité) | Oui |
| `evidence` | Preuve documentaire associée à une question scored | Via pénalité documentaire |

### Règles d'applicabilité

Syntaxe dans `applicability_rule` :

```
"always"                          →  toujours affichée
"only_if(APP_DS_001 == 'Oui')"    →  affichée si réponse = 'Oui'
"only_if(CAP_ERP_001 >= 2)"       →  affichée si score >= 2
```

Le moteur `engine/rules.py` évalue ces règles dynamiquement à chaque réponse.

### Documents attendus (sur les questions `evidence`)

```json
"documents_attendus": [
  {
    "doc_id": "EVID_GOV_005_D1",
    "label": "Politique de gouvernance des données",
    "description": "",
    "obligatoire": true,
    "points_a_valider": [
      "Le document est-il daté et signé par un responsable ?",
      "Le périmètre d'application est-il clairement défini ?",
      "Les rôles et responsabilités sont-ils nommément désignés ?",
      "Une date de révision ou de mise à jour est-elle prévue ?"
    ]
  }
]
```

---

## Modèle de données

**Fichier :** `models/database.py`

### Tables

#### `clients`
| Colonne | Type | Description |
|---|---|---|
| `id` | Integer PK | Identifiant |
| `name` | String | Nom du client |
| `sector` | String | Secteur d'activité |
| `size` | String | Taille (PME, ETI, GE) |
| `country` | String | Pays |
| `tech_stack` | Text (JSON) | Stack technologique |

#### `assessments`
| Colonne | Type | Description |
|---|---|---|
| `id` | Integer PK | Identifiant |
| `client_id` | FK | Client associé |
| `name` | String | Nom de l'assessment |
| `status` | String | `draft` / `in_progress` / `completed` |
| `questionnaire_version` | String | Version du référentiel utilisé |
| `consultant_summary` | Text | Synthèse libre du consultant |

#### `responses`
| Colonne | Type | Description |
|---|---|---|
| `question_id` | String | ID de la question |
| `question_type` | String | `scored` / `applicability` / `evidence` |
| `selected_label` | String | Libellé du choix sélectionné |
| `selected_score` | Float | Score numérique (0-3) |
| `is_na` | Boolean | Question marquée N/A |
| `consultant_confidence` | Float | Confiance de l'auditeur (0.5 / 0.75 / 1.0) |
| `current_tools` | Text (JSON) | Outils actuellement en place |
| `current_documents` | Text (JSON) | Documents actuels |
| `pain_points` | Text (JSON) | Douleurs identifiées |
| `weaknesses` | Text (JSON) | Faiblesses |
| `strengths` | Text (JSON) | Forces |
| `opportunities` | Text (JSON) | Opportunités |
| `risks` | Text (JSON) | Risques |
| `consultant_note` | Text | Note libre de l'auditeur |

#### `attachments`
| Colonne | Type | Description |
|---|---|---|
| `assessment_id` | FK | Assessment associé |
| `question_id` | String | Question à laquelle le fichier est lié |
| `filename` | String | Nom du fichier |
| `filepath` | String | Chemin sur le serveur |
| `mimetype` | String | Type MIME |

Fichiers stockés dans : `data/attachments/{assessment_id}/{question_id}/`

#### `document_reviews`
| Colonne | Type | Description |
|---|---|---|
| `assessment_id` | FK | Assessment associé |
| `question_id` | String | Question evidence associée |
| `attachment_id` | FK (nullable) | Fichier uploadé lié (optionnel) |
| `doc_id` | String (nullable) | ID du document attendu dans le JSON (`EVID_XXX_D1`) |
| `document_label` | String | Nom du document analysé |
| `status` | String | `non_vérifié` / `conforme` / `partiel` / `absent` |
| `elements_trouves` | Text | Ce qui a été trouvé dans le document |
| `elements_manquants` | Text | Ce qui manque ou est insuffisant |
| `observation` | Text | Note libre de l'expert |
| `expert_confidence` | String | `Élevée` / `Moyenne` / `Faible` |
| `reviewed_at` | DateTime | Date de la dernière analyse |

### Fonctions utilitaires

```python
from models.database import (
    load_responses_for_scoring,   # → dict {question_id: scoring_dict}
    load_document_reviews,        # → dict {question_id: [review_dict, ...]}
    compute_document_coverage,    # → dict {global: {...}, by_question: {...}}
)
```

---

## Moteur de scoring

**Fichier :** `engine/scoring.py`

### Formule

```
score_ajusté = score_brut × confiance_consultant × coefficient_documentaire
```

| Facteur | Valeur | Description |
|---|---|---|
| `score_brut` | 0 – 3 | Réponse sélectionnée par l'auditeur |
| `confiance_consultant` | 0.5 / 0.75 / 1.0 | Fiabilité estimée de la réponse |
| `coefficient_documentaire` | 0.5 – 1.0 | Calculé depuis les `DocumentReview` |

### Coefficient documentaire (`compute_document_penalty`)

Pour chaque question `scored`, la fonction cherche la question `evidence` associée (même sous-domaine, même `excel_line_ref`) et agrège les statuts de ses `DocumentReview` :

| Statut du document | Coefficient |
|---|---|
| `conforme` | 1.0 |
| `partiel` | 0.75 |
| `absent` | 0.5 |
| `non_vérifié` | ignoré |

Si aucun document n'a encore été analysé, le coefficient est `1.0` (pas de pénalité).

### Score final normalisé

Le score par domaine est la moyenne pondérée des scores ajustés, normalisée sur 100.

### Niveaux de maturité

| Score | Niveau | Label |
|---|---|---|
| 0 – 30 | 1 | Initial |
| 31 – 60 | 2 | En développement |
| 61 – 80 | 3 | Structuré |
| 81 – 100 | 4 | Optimisé |

### Appel

```python
from engine.scoring import compute_scores
from models.database import load_responses_for_scoring, load_document_reviews

responses = load_responses_for_scoring(assessment_id)
doc_reviews = load_document_reviews(assessment_id)

scores = compute_scores(
    questions,
    responses,
    document_reviews=doc_reviews   # optionnel — pas de pénalité si absent
)

# Résultat
scores["global_score"]       # float : score global /100
scores["domains"]            # dict  : {domaine: score /100}
scores["avg_confidence"]     # float : confiance moyenne 0-1
```

---

## Audit documentaire

### Workflow

```
1. Auditeur ouvre une question evidence dans le questionnaire
2. Voit la liste des documents attendus (Requis / Utile) depuis documents_attendus[]
3. Clique "Commencer l'analyse" sur chaque document
4. Sélectionne le statut : Conforme / Partiel / Absent
5. Lie optionnellement un fichier uploadé
6. Remplit les éléments trouvés, manquants, observation
7. Guide les points_a_valider affichés pour chaque document
8. Sauvegarde → crée un DocumentReview en base
```

### Impact sur le score

Les `DocumentReview` créés pendant l'audit sont lus par `compute_document_penalty()` au moment du scoring. Un document absent pénalise le score de la question `scored` associée d'un coefficient 0.5.

### Page de synthèse

La page `7_Audit_Documentaire.py` offre :
- Taux de couverture documentaire global
- Vue filtrée par domaine, sous-domaine, statut
- Alerte sur les questions sans aucun document analysé
- Export CSV de la grille d'audit complète

---

## Pages de l'application

### `2_Questionnaire.py` — Questionnaire

- Sélection client + assessment (création ou reprise)
- Navigation par domaine principal, puis sous-domaine
- Pour chaque question :
  - **Applicability** : radio Oui/Non, active/désactive les questions suivantes
  - **Scored** : radio 0→3 + expander "En savoir plus" (description du niveau, outils nécessaires, dépendances)
  - **Evidence** : liste des documents Requis/Utile + expander "Analyse documentaire"
  - **Contexte & Insights** : confiance, outils, SWOT, note consultant
  - **Upload** : pièces jointes liées à la question
- Score en temps réel dans la sidebar

### `3_Scorecard.py` — Scorecard

- Score global + niveau de maturité
- Archétype client (classification automatique)
- Scores par domaine avec barres de progression
- Maturity map (heatmap hiérarchique domaine → sous-domaine)
- Gap analysis vs cible (défaut : 70%)

### `4_Recommendations.py` — Roadmap

- Recommandations filtrées par score de domaine
- Priorisation par niveau (Critique → Nice-to-have)
- Plan d'action 30/60/90 jours
- Tableau export

### `7_Audit_Documentaire.py` — Audit documentaire

- Métriques : taux de couverture, conformes, partiels, absents
- Vue détaillée par domaine et sous-domaine
- Filtres par statut et domaine
- Export CSV

---

## Mettre à jour le questionnaire

### Remplacer le fichier de questions

```bash
cp questionnaire_enrichi.json data/questionnaire.json
```

Le chargeur `src/data_loader.py` utilise `@st.cache_data` — vider le cache si nécessaire :

```python
from src.data_loader import load_questionnaire_cached
load_questionnaire_cached.clear()
```

Ou simplement redémarrer Streamlit.

### Supprimer les fichiers obsolètes

```bash
rm data/questionnaire_V0.json
rm data/questionnaire_V1.json
rm data/questionnaire_V2.json
```

### Structure requise pour une nouvelle question

Toute nouvelle question doit avoir au minimum :

```json
{
  "question_id":        "CAP_XXX_001",      // unique
  "question_type":      "scored",            // scored | evidence | applicability
  "question_label":     "...",
  "type_reponse":       "single_choice",
  "choices":            [...],               // score max = 3 pour les scored
  "poids":              4,                   // 0 pour applicability et evidence
  "applicability_rule": "always",
  "na_allowed":         true,
  "score_mode":         "exclude_if_na",
  "domaine_principal":  "Data Management",
  "domaine_specifique": "Gouvernance",
  "excel_line_ref":     17
}
```

Pour les questions `evidence`, ajouter `documents_attendus` avec `doc_id`, `label`, `obligatoire` et `points_a_valider`.

---

## Roadmap

### Court terme

- [ ] Rendre la pénalité documentaire configurable par domaine
- [ ] Ajouter un export Excel de la scorecard complète
- [ ] Permettre la comparaison de deux assessments d'un même client

### Moyen terme

- [ ] Calcul du ROI estimé par recommandation (hypothèses sectorielles + calibrage client)
- [ ] Benchmark sectoriel enrichi (données réelles anonymisées)
- [ ] Interface de création/édition de questions dans l'app Admin

### Long terme (Roadmap IA)

- [ ] RAG sur les référentiels TOGAF, DAMA-DMBOK, ISO 8000 pour enrichir les recommandations
- [ ] Analyse automatique des documents uploadés (extraction de contenu, vérification des points à valider)
- [ ] Génération automatique des observations d'audit

---

## Conventions de nommage

### IDs de questions

| Préfixe | Type | Exemple |
|---|---|---|
| `APP_` | Applicabilité | `APP_GOV_001` |
| `CAP_` | Question scored | `CAP_GOV_005` |
| `EVID_` | Question evidence | `EVID_GOV_005` |

### IDs de documents attendus

Format : `{question_id}_D{numéro}`

Exemple : `EVID_GOV_005_D1`, `EVID_GOV_005_D2`

---

## Licence

Voir `LICENSE`.