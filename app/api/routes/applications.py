from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.errors import PermissionDeniedError
from app.core.permissions import CurrentUser, require_program_manager, require_student
from app.models.user import User
from app.repositories.application_repository import (
    ApplicationRepository,
    get_application_repository,
)
from app.schemas.application import ApplicationDecisionRequest, ApplicationRead
from app.utils.pagination import Page, Pagination

router = APIRouter(prefix="/applications", tags=["applications"])

AppRepo = Annotated[ApplicationRepository, Depends(get_application_repository)]


@router.get(
    "/me",
    response_model=Page[ApplicationRead],
    summary="Mes candidatures (etudiant)",
    responses={403: {"description": "Reserve aux etudiants"}},
)
def list_my_applications(
    repo: AppRepo,
    pagination: Pagination,
    student: Annotated[User, Depends(require_student)],
) -> Page[ApplicationRead]:
    items, total = repo.list_by_student(
        student.id, limit=pagination.limit, offset=pagination.offset
    )
    return Page[ApplicationRead](
        items=[ApplicationRead.model_validate(a) for a in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.patch(
    "/{application_id}/decision",
    response_model=ApplicationRead,
    summary="Accepter ou refuser une candidature (responsable)",
    responses={
        400: {"description": "La candidature n'est plus en attente"},
        403: {"description": "Reserve au responsable pedagogique"},
        404: {"description": "Candidature introuvable"},
    },
)
def decide_application(
    application_id: int,
    payload: ApplicationDecisionRequest,
    repo: AppRepo,
    _: Annotated[User, Depends(require_program_manager)],
) -> ApplicationRead:
    application = repo.get_or_404(application_id)
    application = repo.decide(
        application, decision=payload.decision, comment=payload.comment
    )
    return ApplicationRead.model_validate(application)


@router.delete(
    "/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer sa candidature (etudiant)",
    responses={
        400: {"description": "Candidature acceptee ou deja close"},
        403: {"description": "Candidature d'un autre etudiant"},
        404: {"description": "Candidature introuvable"},
    },
)
def withdraw_application(
    application_id: int,
    repo: AppRepo,
    student: Annotated[User, Depends(require_student)],
) -> Response:
    application = repo.get_or_404(application_id)
    if application.student_id != student.id:
        raise PermissionDeniedError("Cette candidature ne vous appartient pas")
    repo.withdraw(application)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
