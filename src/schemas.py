import json
from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------- Auth ----------

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Tickets & decisions ----------

class TicketCreate(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class DecisionOut(BaseModel):
    action: str
    reason: str
    confidence: float
    sources: List[str]
    created_at: datetime

    @field_validator("sources", mode="before")
    @classmethod
    def parse_sources(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    class Config:
        from_attributes = True


class TicketOut(BaseModel):
    id: int
    message: str
    created_at: datetime
    decision: Optional[DecisionOut] = None

    class Config:
        from_attributes = True


# ---------- LLM structured output (internal use) ----------

class AIDecision(BaseModel):
    """
    Schema the LLM's JSON response must conform to. Validated before
    anything is persisted or shown to the user.
    """
    action: Literal[
        "APPROVE_REFUND",
        "APPROVE_REPLACEMENT",
        "REQUEST_PHOTOS",
        "DENY",
        "ESCALATE",
        "NEEDS_MORE_INFORMATION",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    sources: List[str]