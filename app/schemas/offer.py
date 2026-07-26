from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.offer import OfferStatus


class OfferCreate(BaseModel):
    """DTO d'entree : creation d'un brouillon, champs facultatifs."""

    title: str | None = Field(default=None, max_length=200)
    mission: str | None = None
    skills: str | None = None
    location: str | None = Field(default=None, max_length=150)


class OfferUpdate(OfferCreate):
    """DTO d'entree : modification d'un brouillon."""


class OfferRead(BaseModel):
    """DTO de sortie."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    mission: str | None
    skills: str | None
    location: str | None
    status: OfferStatus
    company_id: int
    review_comment: str | None
    created_at: datetime
    updated_at: datetime


class OfferReviewRequest(BaseModel):
    """DTO d'entree : arbitrage du responsable pedagogique."""

    decision: Literal["publish", "reject"]
    comment: str | None = Field(default=None, max_length=1000)


class StatsResponse(BaseModel):
    """DTO de sortie : statistiques agregees."""

    offers_by_status: dict[str, int]
    applications_by_status: dict[str, int]
