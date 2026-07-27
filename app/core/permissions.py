from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.role import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Identifie l'appelant à partir du jeton Bearer. Lève 401 si impossible."""
    if not token:
        raise AuthenticationError("Jeton absent")

    payload = decode_access_token(token)

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError("Jeton incomplet") from exc

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise AuthenticationError("Utilisateur inconnu")
    if not user.is_active:
        raise AuthenticationError("Compte désactivé")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed_roles: UserRole) -> Callable[..., User]:
    """Fabrique une dépendance qui n'autorise que les rôles indiqués."""

    def dependency(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles:
            attendus = ", ".join(r.value for r in allowed_roles)
            raise PermissionDeniedError(
                f"Rôle requis : {attendus}. Rôle actuel : {current_user.role.value}"
            )
        return current_user

    return dependency


require_student = require_roles(UserRole.STUDENT)
require_company = require_roles(UserRole.COMPANY)
require_program_manager = require_roles(UserRole.PROGRAM_MANAGER)
require_admin = require_roles(UserRole.ADMIN)
require_staff = require_roles(UserRole.PROGRAM_MANAGER, UserRole.ADMIN)