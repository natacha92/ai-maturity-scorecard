import json
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, DateTime,
    ForeignKey, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///paims.db"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Client(Base):
    __tablename__ = "clients"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    name         = Column(String(200), nullable=False)
    sector       = Column(String(100))
    size         = Column(String(50))        # PME, ETI, GE
    country      = Column(String(100), default="France")
    tech_stack   = Column(Text, default="[]")  # JSON list
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    assessments  = relationship("Assessment", back_populates="client", cascade="all, delete-orphan")

    def get_tech_stack(self):
        try:
            return json.loads(self.tech_stack or "[]")
        except json.JSONDecodeError:
            return []

    def set_tech_stack(self, stack_list):
        self.tech_stack = json.dumps(stack_list)


class Assessment(Base):
    __tablename__ = "assessments"

    id                     = Column(Integer, primary_key=True, autoincrement=True)
    client_id              = Column(Integer, ForeignKey("clients.id"), nullable=False)
    questionnaire_version  = Column(String(20), default="data_maturity_v1")  # ← ton referentiel_id
    name                   = Column(String(200), nullable=False)
    status                 = Column(String(20), default="draft")  # draft, in_progress, completed
    consultant_feeling     = Column(String(10), default="")   # low/medium/high
    consultant_summary     = Column(Text, default="")          # synthèse globale
    created_at             = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at             = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                                    onupdate=lambda: datetime.now(timezone.utc))

    client           = relationship("Client", back_populates="assessments")
    responses        = relationship("Response", back_populates="assessment", cascade="all, delete-orphan")
    reports          = relationship("Report", back_populates="assessment", cascade="all, delete-orphan")
    attachments      = relationship("Attachment", back_populates="assessment", cascade="all, delete-orphan")
    document_reviews = relationship("DocumentReview", back_populates="assessment", cascade="all, delete-orphan")


class Response(Base):
    __tablename__ = "responses"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id  = Column(Integer, ForeignKey("assessments.id"), nullable=False)

    # Identification de la question
    question_id    = Column(String(50), nullable=False)   # ex: "CAP_ERP_001"
    question_type  = Column(String(20), nullable=False)   # "scored", "applicability", "evidence"

    # Réponse pour single_choice
    selected_label = Column(String(300), nullable=True)   # ex: "ERP largement déployé..."
    selected_score = Column(Float, nullable=True)         # ex: 3.0  (None si N/A ou evidence)

    # Réponse pour text (evidence)
    answer_text    = Column(Text, default="")             # champ libre preuve

    # N/A
    is_na          = Column(Boolean, default=False)

    consultant_confidence = Column(Float, default=1.0)  # 0.0 (pas du tout confiant) à 1.0 (très confiant)

    # Contexte
    answer_text        = Column(Text, default="")
    current_tools      = Column(Text, default="[]")   # JSON list
    current_documents  = Column(Text, default="[]")   # JSON list

    # Insights business (JSON lists)
    pain_points    = Column(Text, default="[]")
    weaknesses     = Column(Text, default="[]")
    strengths      = Column(Text, default="[]")
    opportunities  = Column(Text, default="[]")
    risks          = Column(Text, default="[]")

    # Note consultant
    consultant_note = Column(Text, default="")

    assessment = relationship("Assessment", back_populates="responses")

    def to_scoring_dict(self):
        """
        Retourne le format attendu par rules.py et scoring.py :
        {
            "label": "ERP largement déployé...",
            "score": 3.0,
            "is_na": False,
            "selected_choice": "ERP largement déployé..."  ← compatibilité rules.py
        }
        """
        return {
            "label":           self.selected_label,
            "score":           self.selected_score,
            "is_na":           self.is_na,
            "selected_choice": self.selected_label,  # alias pour rules.py
            "answer_text":     self.answer_text,
            "consultant_confidence": self.consultant_confidence or 1.0,
            "current_tools":   self.current_tools,
            "current_documents": self.current_documents,
            "pain_points":     self.pain_points,
            "weaknesses":      self.weaknesses,
            "strengths":       self.strengths,
            "opportunities":   self.opportunities,
            "risks":           self.risks,
            "consultant_note": self.consultant_note
        }


class RecommendationRule(Base):
    __tablename__ = "recommendation_rules"

    id             = Column(Integer, primary_key=True, autoincrement=True)

    # Alignés sur les vrais noms de domaines du JSON
    domain     = Column(String(200), nullable=False)
    subdomain  = Column(String(200), default="")

    score_min  = Column(Float, default=0)
    score_max  = Column(Float, default=100)
    priority   = Column(Integer, default=3)   # 1=critique, 5=nice-to-have
    title      = Column(String(300), nullable=False)
    text       = Column(Text, nullable=False)
    effort     = Column(String(20), default="medium")   # low, medium, high
    impact     = Column(String(20), default="medium")   # low, medium, high
    horizon    = Column(String(20), default="60d")      # 30d, 60d, 90d
    reference_ids = Column(Text, default="[]")   # 

class Report(Base):
    __tablename__ = "reports"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False)
    report_type   = Column(String(50), nullable=False)   # "comex", "detailed", "gap"
    content_json  = Column(Text, nullable=False)
    generated_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    assessment = relationship("Assessment", back_populates="reports")

    def get_content(self):
        return json.loads(self.content_json)

    def set_content(self, data):
        self.content_json = json.dumps(data, default=str)

class Attachment(Base):
    __tablename__ = "attachments"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False)
    question_id   = Column(String(50), nullable=False)
    filename      = Column(String(300), nullable=False)
    filepath      = Column(String(500), nullable=False)
    mimetype      = Column(String(100), default="")
    uploaded_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    assessment = relationship("Assessment", back_populates="attachments")
    reviews    = relationship("DocumentReview", back_populates="attachment")


class DocumentReview(Base):
    """
    Analyse experte d'un document pour une question evidence.
    Une question peut avoir plusieurs DocumentReview (un par document analysé).
    Le document peut être :
      - un fichier uploadé (attachment_id renseigné)
      - un document attendu mais absent (attachment_id NULL, status="absent")
      - un document mentionné sans upload (attachment_id NULL, document_label renseigné)
    """
    __tablename__ = "document_reviews"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False)
    question_id   = Column(String(50), nullable=False)

    # Lien optionnel vers un fichier uploadé
    attachment_id = Column(Integer, ForeignKey("attachments.id"), nullable=True)

    # Identifiant du document attendu (tiré de documents_attendus[].doc_id dans le JSON)
    # None si document ajouté librement par l'auditeur hors liste
    doc_id = Column(String(100), nullable=True)

    # Nom du document (libre, ou repris du label si doc_id fourni)
    document_label = Column(String(300), nullable=False, default="Document sans titre")

    # Statut de conformité évalué par l'expert
    # "non_vérifié" | "conforme" | "partiel" | "absent"
    status = Column(String(20), default="non_vérifié")

    # Analyse experte
    elements_trouves   = Column(Text, default="")   # Ce qui est bien présent dans le doc
    elements_manquants = Column(Text, default="")   # Ce qui est attendu mais absent
    observation        = Column(Text, default="")   # Note libre de l'expert

    # Niveau de confiance de l'expert sur cette analyse
    # "Élevée" | "Moyenne" | "Faible"
    expert_confidence = Column(String(20), default="Moyenne")

    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_at = Column(DateTime, nullable=True)   # Date de dernière analyse

    # Relations
    assessment = relationship("Assessment", back_populates="document_reviews")
    attachment = relationship("Attachment", back_populates="reviews")

    def to_dict(self):
        """Sérialise le review pour l'affichage et les exports."""
        return {
            "id":                 self.id,
            "question_id":        self.question_id,
            "attachment_id":      self.attachment_id,
            "doc_id":             self.doc_id,
            "document_label":     self.document_label,
            "status":             self.status,
            "elements_trouves":   self.elements_trouves,
            "elements_manquants": self.elements_manquants,
            "observation":        self.observation,
            "expert_confidence":  self.expert_confidence,
            "reviewed_at":        self.reviewed_at.isoformat() if self.reviewed_at else None,
        }


def init_db():
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()


def load_responses_for_scoring(assessment_id: int) -> dict:
    """
    Charge toutes les réponses d'un assessment et les convertit
    au format attendu par scoring.py et rules.py.

    Retourne : {question_id: {"label": ..., "score": ..., "is_na": ...}}
    """
    session = get_session()
    try:
        responses = session.query(Response).filter_by(assessment_id=assessment_id).all()
        return {r.question_id: r.to_scoring_dict() for r in responses}
    finally:
        session.close()


def load_document_reviews(assessment_id: int) -> dict:
    """
    Charge tous les DocumentReview d'un assessment.

    Retourne : {question_id: [review.to_dict(), ...]}
    Permet d'accéder rapidement à tous les reviews d'une question.
    """
    session = get_session()
    try:
        reviews = (
            session.query(DocumentReview)
            .filter_by(assessment_id=assessment_id)
            .order_by(DocumentReview.question_id, DocumentReview.id)
            .all()
        )
        result = {}
        for r in reviews:
            result.setdefault(r.question_id, []).append(r.to_dict())
        return result
    finally:
        session.close()


def compute_document_coverage(assessment_id: int) -> dict:
    """
    Calcule le taux de couverture documentaire par domaine.

    Pour chaque DocumentReview :
      conforme  → 1.0
      partiel   → 0.5
      absent    → 0.0
      non_vérifié → ignoré (pas dans le calcul)

    Retourne : {
        "global": {"taux": 72, "conforme": 8, "partiel": 3, "absent": 2, "total": 13},
        "by_question": {question_id: {"taux": 80, ...}},
    }
    """
    session = get_session()
    try:
        reviews = (
            session.query(DocumentReview)
            .filter_by(assessment_id=assessment_id)
            .all()
        )
    finally:
        session.close()

    STATUS_SCORES = {"conforme": 1.0, "partiel": 0.5, "absent": 0.0}

    by_question = {}
    global_scores = []

    for r in reviews:
        if r.status not in STATUS_SCORES:
            continue  # on ignore "non_vérifié"

        s = STATUS_SCORES[r.status]
        global_scores.append(s)

        qid = r.question_id
        by_question.setdefault(qid, {"scores": [], "conforme": 0, "partiel": 0, "absent": 0})
        by_question[qid]["scores"].append(s)
        by_question[qid][r.status] += 1

    # Agrège par question
    by_question_result = {}
    for qid, data in by_question.items():
        scores = data["scores"]
        taux = round(sum(scores) / len(scores) * 100) if scores else None
        by_question_result[qid] = {
            "taux":     taux,
            "conforme": data["conforme"],
            "partiel":  data["partiel"],
            "absent":   data["absent"],
            "total":    len(scores),
        }

    # Global
    global_taux = round(sum(global_scores) / len(global_scores) * 100) if global_scores else None
    global_result = {
        "taux":    global_taux,
        "conforme": sum(1 for r in reviews if r.status == "conforme"),
        "partiel":  sum(1 for r in reviews if r.status == "partiel"),
        "absent":   sum(1 for r in reviews if r.status == "absent"),
        "total":    len([r for r in reviews if r.status in STATUS_SCORES]),
    }

    return {
        "global":      global_result,
        "by_question": by_question_result,
    }