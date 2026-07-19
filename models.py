"""SQLAlchemy models for ContractPilot."""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class UserTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    tier = Column(Enum(UserTier), default=UserTier.FREE)
    analyses_used = Column(Integer, default=0)
    analyses_limit = Column(Integer, default=1)  # Free tier: 1 analysis
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    contracts = relationship("Contract", back_populates="owner", cascade="all, delete-orphan")


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    original_text = Column(Text, nullable=False)
    risk_score = Column(Float, nullable=True)
    status = Column(String, default="analyzing")  # analyzing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="contracts")
    clauses = relationship("Clause", back_populates="contract", cascade="all, delete-orphan")


class Clause(Base):
    __tablename__ = "clauses"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    clause_type = Column(String, nullable=False)  # e.g., "termination", "liability", "ip"
    original_text = Column(Text, nullable=False)
    risk_level = Column(String, nullable=False)  # low, medium, high, critical
    explanation = Column(Text, nullable=False)
    suggested_revision = Column(Text, nullable=True)
    position_start = Column(Integer, nullable=True)
    position_end = Column(Integer, nullable=True)

    contract = relationship("Contract", back_populates="clauses")
