from collections.abc import Sequence

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, NotFoundError
from app.db.session import get_db
from app.models.offer import Offer, OfferStatus
from app.models.user import User

REQUIRED_FIELDS_FOR_PUBLICATION = ("title", "mission", "skills")


class OfferRepository:
    """Accès aux offres et application des invariants de cycle de vie."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Lecture -----------------------------------------------------

    def get_by_id(self, offer_id: int) -> Offer | None:
        return self.db.get(Offer, offer_id)

    def get_or_404(self, offer_id: int) -> Offer:
        offer = self.get_by_id(offer_id)
        if offer is None:
            raise NotFoundError("Offre introuvable")
        return offer

    def list_published(
        self, *, limit: int, offset: int, search: str | None = None
    ) -> tuple[Sequence[Offer], int]:
        conditions = [Offer.status == OfferStatus.PUBLISHED]
        if search:
            conditions.append(Offer.title.ilike(f"%{search}%"))

        stmt = select(Offer).where(*conditions).order_by(Offer.id.desc())
        total = self.db.execute(
            select(func.count()).select_from(Offer).where(*conditions)
        ).scalar_one()
        items = self.db.execute(stmt.limit(limit).offset(offset)).scalars().all()
        return items, total

    def list_by_company(
        self, company_id: int, *, limit: int, offset: int
    ) -> tuple[Sequence[Offer], int]:
        condition = Offer.company_id == company_id
        total = self.db.execute(
            select(func.count()).select_from(Offer).where(condition)
        ).scalar_one()
        items = (
            self.db.execute(
                select(Offer)
                .where(condition)
                .order_by(Offer.id.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return items, total

    def count_by_status(self) -> dict[str, int]:
        rows = self.db.execute(
            select(Offer.status, func.count(Offer.id)).group_by(Offer.status)
        ).all()
        counts = {status.value: 0 for status in OfferStatus}
        for status, total in rows:
            counts[status.value] = total
        return counts

    # --- Écriture ----------------------------------------------------

    def create_draft(self, *, company: User, **fields) -> Offer:
        offer = Offer(company_id=company.id, status=OfferStatus.DRAFT, **fields)
        self.db.add(offer)
        self.db.commit()
        self.db.refresh(offer)
        return offer

    def update_draft(self, offer: Offer, **fields) -> Offer:
        if offer.status is not OfferStatus.DRAFT:
            raise BusinessRuleError(
                "Seule une offre en brouillon peut être modifiée"
            )
        for key, value in fields.items():
            if value is not None:
                setattr(offer, key, value)
        self.db.commit()
        self.db.refresh(offer)
        return offer

    def submit(self, offer: Offer) -> Offer:
        """Invariant : draft -> submitted, et l'offre doit être complète."""
        if offer.status is not OfferStatus.DRAFT:
            raise BusinessRuleError(
                f"Transition invalide : {offer.status.value} -> submitted"
            )

        manquants = [
            champ
            for champ in REQUIRED_FIELDS_FOR_PUBLICATION
            if not getattr(offer, champ)
        ]
        if manquants:
            raise BusinessRuleError(
                f"Champs obligatoires manquants : {', '.join(manquants)}"
            )

        offer.status = OfferStatus.SUBMITTED
        self.db.commit()
        self.db.refresh(offer)
        return offer

    def review(self, offer: Offer, *, decision: str, comment: str | None) -> Offer:
        """Invariant : submitted -> published | rejected."""
        if offer.status is not OfferStatus.SUBMITTED:
            raise BusinessRuleError(
                f"Seule une offre soumise peut être arbitrée "
                f"(statut actuel : {offer.status.value})"
            )

        offer.status = (
            OfferStatus.PUBLISHED if decision == "publish" else OfferStatus.REJECTED
        )
        offer.review_comment = comment
        self.db.commit()
        self.db.refresh(offer)
        return offer


def get_offer_repository(db: Session = Depends(get_db)) -> OfferRepository:
    return OfferRepository(db)