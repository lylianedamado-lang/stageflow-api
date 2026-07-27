from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.core.errors import AuthenticationError, BusinessRuleError
from app.core.security import create_access_token
from app.repositories.user_repository import UserRepository, get_user_repository
from app.schemas.auth import LoginRequest, Token, TokenWithUser
from app.schemas.user import UserCreate, UserRead
from app.utils.hashing import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

Repo = Annotated[UserRepository, Depends(get_user_repository)]


def _authenticate(repo: UserRepository, email: str, password: str):
    """Vérifie les identifiants. Message volontairement identique dans tous les cas."""
    user = repo.get_by_email(email)
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthenticationError("Email ou mot de passe incorrect")
    if not user.is_active:
        raise AuthenticationError("Compte désactivé")
    return user


def _issue_token(user) -> dict:
    return {
        "access_token": create_access_token(subject=user.id, role=user.role.value),
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Inscription publique",
    responses={400: {"description": "Email déjà utilisé"}},
)
def register(payload: UserCreate, repo: Repo) -> UserRead:
    """Crée un compte student ou company. Les rôles a privilégés sont refusés."""
    if repo.email_exists(payload.email):
        raise BusinessRuleError("Cet email est déjà utilisé")

    user = repo.create(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        company_name=payload.company_name,
    )
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=Token,
    summary="Connexion (formulaire OAuth2)",
    responses={401: {"description": "Identifiants invalides"}},
)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    repo: Repo,
) -> Token:
    """Flux OAuth2 password : le champ username reçoit l'email."""
    user = _authenticate(repo, form_data.username, form_data.password)
    return Token(**_issue_token(user))


@router.post(
    "/login/json",
    response_model=TokenWithUser,
    summary="Connexion (JSON)",
    responses={401: {"description": "Identifiants invalides"}},
)
def login_json(payload: LoginRequest, repo: Repo) -> TokenWithUser:
    """Variante JSON, plus pratique pour un client ou des tests."""
    user = _authenticate(repo, payload.email, payload.password)
    return TokenWithUser(**_issue_token(user), user=UserRead.model_validate(user))
