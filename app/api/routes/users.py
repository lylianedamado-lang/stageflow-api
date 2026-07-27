import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.errors import BusinessRuleError, NotFoundError
from app.core.permissions import CurrentUser, require_admin
from app.models.user import User
from app.repositories.user_repository import UserRepository, get_user_repository
from app.schemas.user import UserRead, UserRoleUpdate
from app.utils.pagination import Page, Pagination

logger = logging.getLogger("stageflow.audit")

router = APIRouter(prefix="/users", tags=["users"])

Repo = Annotated[UserRepository, Depends(get_user_repository)]


@router.get("/me", response_model=UserRead, summary="Profil de l'utilisateur connecté")
def read_me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.get(
    "",
    response_model=Page[UserRead],
    summary="Lister les comptes (admin)",
    responses={403: {"description": "Réservé à l'administrateur"}},
)
def list_users(
    repo: Repo,
    pagination: Pagination,
    _: Annotated[User, Depends(require_admin)],
) -> Page[UserRead]:
    items = repo.list_all(limit=pagination.limit, offset=pagination.offset)
    return Page[UserRead](
        items=[UserRead.model_validate(u) for u in items],
        total=repo.count(),
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.patch(
    "/{user_id}/role",
    response_model=UserRead,
    summary="Forcer le rôle d'un compte (admin)",
    responses={
        400: {"description": "Operation interdite"},
        403: {"description": "Réservé à l'administrateur"},
        404: {"description": "Utilisateur introuvable"},
    },
)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    repo: Repo,
    admin: Annotated[User, Depends(require_admin)],
) -> UserRead:
    target = repo.get_by_id(user_id)
    if target is None:
        raise NotFoundError("Utilisateur introuvable")
    if target.id == admin.id:
        raise BusinessRuleError("Un administrateur ne peut pas modifier son propre rôle")

    ancien_role = target.role.value
    repo.update_role(target, payload.role)

    logger.warning(
        "Changement de rôle : user_id=%s %s -> %s par admin_id=%s",
        target.id,
        ancien_role,
        payload.role.value,
        admin.id,
    )
    return UserRead.model_validate(target)
