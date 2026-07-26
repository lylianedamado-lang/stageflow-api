from datetime import timedelta

import jwt

from app.core.config import settings
from app.core.errors import AuthenticationError
from app.utils.time import utcnow

TOKEN_TYPE_ACCESS = "access"


def create_access_token(
    subject: str | int,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Genere un JWT signe contenant l'identifiant et le role de l'utilisateur."""
    now = utcnow()
    expire = now + (
        expires_delta
        or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {
        "sub": str(subject),
        "role": role,
        "type": TOKEN_TYPE_ACCESS,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    """Verifie la signature et l'expiration, puis retourne le contenu du jeton."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Jeton expire") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Jeton invalide") from exc

    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise AuthenticationError("Type de jeton invalide")
    if payload.get("sub") is None:
        raise AuthenticationError("Jeton incomplet")

    return payload
