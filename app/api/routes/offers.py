from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.permissions import (
    CurrentUser,
    require_company,
    require_program_manager,
    require_staff,
    require_student,
)
from app.models.offer import Offer, OfferStatus
from app.models.role import UserRole
from app.models.user import User
from app.repositories.application_repository import (
    ApplicationRepository,
    get_application_repository,
)
from app.repositories.offer_repository import OfferRepository, get_offer_repository
from app.schemas.application import ApplicationCreate, ApplicationRead
from app.schemas.offer import (
    OfferCreate,
    OfferRead,
    OfferReviewRequest,
    OfferUpdate,
    StatsResponse,
)
from app.utils.pagination import Page, Pagination

router = APIRouter(prefix="/offers", tags=["offers"])

OfferRepo = Annotated[OfferRepository, Depends(get_offer_repository)]
AppRepo = Annotated[ApplicationRepository, Depends(get_application_repository)]

STAFF_ROLES = (UserRole.PROGRAM_MANAGER, UserRole.ADMIN)


# --- Helpers d'habilitation -----------------------------------------

def _visible_offer_or_404(repo: OfferRepository, offer_id: int, user: User) -> Offer:
    """404 si l'offre n'existe pas OU n'est pas visible par cet utilisateur."""
    offer = repo.get_or_404(offer_id)
    if offer.status is OfferStatus.PUBLISHED:
        return offer
    if user.role in STAFF_ROLES:
        return offer
    if user.role is UserRole.COMPANY and offer.company_id == user.id:
        return offer
    raise NotFoundError("Offre introuvable")


def _assert_owner_or_staff(offer: Offer, user: User) -> None:
    """403 si l'offre est visible mais n'appartient pas à cet utilisateur."""
    if user.role in STAFF_ROLES:
        return
    if user.role is UserRole.COMPANY and offer.company_id == user.id:
        return
    raise PermissionDeniedError("Cette offre ne vous appartient pas")


# --- Statistiques (déclarée AVANT /{offer_id}) ----------------------

@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Statistiques globales (responsable)",
    responses={403: {"description": "Réservé au responsable pédagogique"}},
)
def offer_stats(
    offer_repo: OfferRepo,
    app_repo: AppRepo,
    _: Annotated[User, Depends(require_staff)],
) -> StatsResponse:
    return StatsResponse(
        offers_by_status=offer_repo.count_by_status(),
        applications_by_status=app_repo.count_by_status(),
    )


# --- Cycle de vie de l'offre ----------------------------------------

@router.post(
    "",
    response_model=OfferRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une offre en brouillon (entreprise)",
    responses={403: {"description": "Réservé aux comptes entreprise"}},
)
def create_offer(
    payload: OfferCreate,
    repo: OfferRepo,
    company: Annotated[User, Depends(require_company)],
) -> OfferRead:
    offer = repo.create_draft(company=company, **payload.model_dump())
    return OfferRead.model_validate(offer)


@router.get(
    "",
    response_model=Page[OfferRead],
    summary="Lister les offres publiées",
)
def list_offers(
    repo: OfferRepo,
    pagination: Pagination,
    current_user: CurrentUser,
    mine: Annotated[bool, Query(description="Entreprise : mes offres")] = False,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[OfferRead]:
    if mine and current_user.role is UserRole.COMPANY:
        items, total = repo.list_by_company(
            current_user.id, limit=pagination.limit, offset=pagination.offset
        )
    else:
        items, total = repo.list_published(
            limit=pagination.limit, offset=pagination.offset, search=search
        )
    return Page[OfferRead](
        items=[OfferRead.model_validate(o) for o in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/{offer_id}",
    response_model=OfferRead,
    summary="Détail d'une offre",
    responses={404: {"description": "Offre absente ou non visible"}},
)
def get_offer(offer_id: int, repo: OfferRepo, current_user: CurrentUser) -> OfferRead:
    offer = _visible_offer_or_404(repo, offer_id, current_user)
    return OfferRead.model_validate(offer)


@router.patch(
    "/{offer_id}",
    response_model=OfferRead,
    summary="Modifier un brouillon (entreprise propriétaire)",
    responses={
        400: {"description": "L'offre n'est plus en brouillon"},
        403: {"description": "Offre appartenant à une autre entreprise"},
    },
)
def update_offer(
    offer_id: int,
    payload: OfferUpdate,
    repo: OfferRepo,
    company: Annotated[User, Depends(require_company)],
) -> OfferRead:
    offer = _visible_offer_or_404(repo, offer_id, company)
    _assert_owner_or_staff(offer, company)
    offer = repo.update_draft(offer, **payload.model_dump())
    return OfferRead.model_validate(offer)


@router.patch(
    "/{offer_id}/submit",
    response_model=OfferRead,
    summary="Soumettre l'offre à validation (entreprise propriétaire)",
    responses={
        400: {"description": "Transition invalide ou champs manquants"},
        403: {"description": "Offre appartenant à une autre entreprise"},
    },
)
def submit_offer(
    offer_id: int,
    repo: OfferRepo,
    company: Annotated[User, Depends(require_company)],
) -> OfferRead:
    offer = _visible_offer_or_404(repo, offer_id, company)
    _assert_owner_or_staff(offer, company)
    return OfferRead.model_validate(repo.submit(offer))


@router.patch(
    "/{offer_id}/review",
    response_model=OfferRead,
    summary="Publier ou refuser une offre (responsable)",
    responses={
        400: {"description": "L'offre n'est pas au statut submitted"},
        403: {"description": "Réservé au responsable pédagogique"},
    },
)
def review_offer(
    offer_id: int,
    payload: OfferReviewRequest,
    repo: OfferRepo,
    _: Annotated[User, Depends(require_program_manager)],
) -> OfferRead:
    offer = repo.get_or_404(offer_id)
    offer = repo.review(offer, decision=payload.decision, comment=payload.comment)
    return OfferRead.model_validate(offer)


# --- Candidatures rattachées à une offre ----------------------------

@router.post(
    "/{offer_id}/applications",
    response_model=ApplicationRead,
    status_code=status.HTTP_201_CREATED,
    tags=["applications"],
    summary="Déposer une candidature (étudiant)",
    responses={
        400: {"description": "Offre non publiée ou candidature déjà existante"},
        403: {"description": "Réservé aux étudiants"},
        404: {"description": "Offre absente ou non visible"},
    },
)
def create_application(
    offer_id: int,
    payload: ApplicationCreate,
    offer_repo: OfferRepo,
    app_repo: AppRepo,
    student: Annotated[User, Depends(require_student)],
) -> ApplicationRead:
    offer = _visible_offer_or_404(offer_repo, offer_id, student)
    application = app_repo.create(
        offer=offer, student_id=student.id, motivation=payload.motivation
    )
    return ApplicationRead.model_validate(application)


@router.get(
    "/{offer_id}/applications",
    response_model=Page[ApplicationRead],
    tags=["applications"],
    summary="Candidatures d'une offre (entreprise propriétaire ou responsable)",
    responses={
        403: {"description": "Offre appartenant à une autre entreprise"},
        404: {"description": "Offre absente ou non visible"},
    },
)
def list_offer_applications(
    offer_id: int,
    offer_repo: OfferRepo,
    app_repo: AppRepo,
    pagination: Pagination,
    current_user: CurrentUser,
) -> Page[ApplicationRead]:
    offer = _visible_offer_or_404(offer_repo, offer_id, current_user)
    _assert_owner_or_staff(offer, current_user)
    items, total = app_repo.list_by_offer(
        offer_id, limit=pagination.limit, offset=pagination.offset
    )
    return Page[ApplicationRead](
        items=[ApplicationRead.model_validate(a) for a in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )