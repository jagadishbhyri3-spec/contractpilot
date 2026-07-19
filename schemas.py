"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    tier: str
    analyses_used: int
    analyses_limit: int

    class Config:
        from_attributes = True


class ClauseResponse(BaseModel):
    id: int
    clause_type: str
    risk_level: str
    explanation: str
    suggested_revision: Optional[str]
    original_text: str

    class Config:
        from_attributes = True


class ContractCreate(BaseModel):
    title: str


class ContractResponse(BaseModel):
    id: int
    title: str
    filename: str
    risk_score: Optional[float]
    status: str
    created_at: datetime
    clauses: List[ClauseResponse] = []

    class Config:
        from_attributes = True


class AnalysisResult(BaseModel):
    risk_score: float
    summary: str
    clauses: List[dict]
