from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.application import ApplicationStatus


class ApplicationCreate(BaseModel):
    """DTO d'entrée : dépôt d'une candidature."""

    motivation: str = Field(min_length=20, max_length=5000)


class ApplicationRead(BaseModel):
    """DTO de sortie."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    offer_id: int
    student_id: int
    motivation: str
    status: ApplicationStatus
    decision_comment: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationDecisionRequest(BaseModel):
    """DTO d'entrée : arbitrage d'une candidature."""

    decision: Literal["accept", "reject"]
    comment: str | None = Field(default=None, max_length=1000)