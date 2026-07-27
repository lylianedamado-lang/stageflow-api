from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

BCRYPT_MAX_BYTES = 72


def hash_password(plain_password: str) -> str:
    """Retourne le hash bcrypt du mot de passe en clair."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compare un mot de passe en clair à son hash. Ne lève jamais d'exception."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError:
        return False