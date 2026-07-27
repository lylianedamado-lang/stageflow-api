from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import PASSWORD_MAX, PASSWORD_MIN, UserRead

class LoginRequest(BaseModel):
    """DTO d'entrée : connexion en JSON (alternative au formulaire OAuth2)."""

    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class Token(BaseModel):
    """DTO de sortie : réponse standard OAuth2."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenWithUser(Token):
    """Jeton accompagné du profil, pratique côté client."""

    user: UserRead