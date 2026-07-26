from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.time import utcnow


class OfferStatus(str, Enum):
    """Cycle de vie d'une offre : draft -> submitted -> published | rejected."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    PUBLISHED = "published"
    REJECTED = "rejected"


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mission: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)

    status: Mapped[OfferStatus] = mapped_column(
        SAEnum(
            OfferStatus,
            native_enum=False,
            length=32,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=OfferStatus.DRAFT,
        nullable=False,
        index=True,
    )

    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    company: Mapped["User"] = relationship(back_populates="offers")
    applications: Mapped[list["Application"]] = relationship(
        back_populates="offer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Offer id={self.id} title={self.title} status={self.status}>"
