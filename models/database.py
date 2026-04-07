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
    created_at             = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at             = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                                    onupdate=lambda: datetime.now(timezone.utc))

    client    = relationship("Client", back_populates="assessments")
    responses = relationship("Response", back_populates="assessment", cascade="all, delete-orphan")
    reports   = relationship("Report", back_populates="assessment", cascade="all, delete-orphan")


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