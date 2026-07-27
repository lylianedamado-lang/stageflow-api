from collections.abc import Sequence

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, NotFoundError
from app.db.session import get_db
from app.models.application import Application, ApplicationStatus
from app.models.offer import Offer, OfferStatus

ACTIVE_STATUSES = (ApplicationStatus.PENDING, ApplicationStatus.ACCEPTED)


class ApplicationRepository:
    """Accès aux candidatures et application des invariants."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Lecture -----------------------------------------------------

    def get_by_id(self, application_id: int) -> Application | None:
        return self.db.get(Application, application_id)

    def get_or_404(self, application_id: int) -> Application:
        application = self.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Candidature introuvable")
        return application

    def get_by_offer_and_student(
        self, offer_id: int, student_id: int
    ) -> Application | None:
        stmt = select(Application).where(
            Application.offer_id == offer_id,
            Application.student_id == student_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_student(
        self, student_id: int, *, limit: int, offset: int
    ) -> tuple[Sequence[Application], int]:
        condition = Application.student_id == student_id
        total = self.db.execute(
            select(func.count()).select_from(Application).where(condition)
        ).scalar_one()
        items = (
            self.db.execute(
                select(Application)
                .where(condition)
                .order_by(Application.id.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return items, total

    def list_by_offer(
        self, offer_id: int, *, limit: int, offset: int
    ) -> tuple[Sequence[Application], int]:
        condition = Application.offer_id == offer_id
        total = self.db.execute(
            select(func.count()).select_from(Application).where(condition)
        ).scalar_one()
        items = (
            self.db.execute(
                select(Application)
                .where(condition)
                .order_by(Application.id.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return items, total

    def count_by_status(self) -> dict[str, int]:
        rows = self.db.execute(
            select(Application.status, func.count(Application.id)).group_by(
                Application.status
            )
        ).all()
        counts = {status.value: 0 for status in ApplicationStatus}
        for status, total in rows:
            counts[status.value] = total
        return counts

    # --- Écriture ----------------------------------------------------

    def create(self, *, offer: Offer, student_id: int, motivation: str) -> Application:
        """Invariants : offre publiée, et une seule candidature active par offre."""
        if offer.status is not OfferStatus.PUBLISHED:
            raise BusinessRuleError(
                "Impossible de candidater à une offre non publiée"
            )

        existante = self.get_by_offer_and_student(offer.id, student_id)
        if existante is not None:
            if existante.status in ACTIVE_STATUSES:
                raise BusinessRuleError(
                    "Une candidature active existe déjà pour cette offre"
                )
            raise BusinessRuleError(
                "Vous avez déjà candidaté à cette offre"
            )

        application = Application(
            offer_id=offer.id,
            student_id=student_id,
            motivation=motivation,
            status=ApplicationStatus.PENDING,
        )
        self.db.add(application)
        self.db.commit()
        self.db.refresh(application)
        return application

    def decide(
        self, application: Application, *, decision: str, comment: str | None
    ) -> Application:
        """Invariant : seule une candidature en attente peut être arbitrée."""
        if application.status is not ApplicationStatus.PENDING:
            raise BusinessRuleError(
                f"Seule une candidature en attente peut être arbitrée "
                f"(statut actuel : {application.status.value})"
            )

        application.status = (
            ApplicationStatus.ACCEPTED
            if decision == "accept"
            else ApplicationStatus.REJECTED
        )
        application.decision_comment = comment
        self.db.commit()
        self.db.refresh(application)
        return application

    def withdraw(self, application: Application) -> Application:
        """Invariant : une candidature acceptée ne peut plus être retirée."""
        if application.status is ApplicationStatus.ACCEPTED:
            raise BusinessRuleError(
                "Une candidature acceptée ne peut plus être retirée"
            )
        if application.status is not ApplicationStatus.PENDING:
            raise BusinessRuleError(
                f"Candidature déjà close (statut : {application.status.value})"
            )

        application.status = ApplicationStatus.WITHDRAWN
        self.db.commit()
        self.db.refresh(application)
        return application


def get_application_repository(db: Session = Depends(get_db)) -> ApplicationRepository:
    return ApplicationRepository(db)