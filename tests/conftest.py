import os

# Doit etre defini AVANT l'import de app.core.config : la CI n'a pas de .env.
os.environ.setdefault("JWT_SECRET_KEY", "cle-de-test-non-secrete")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEBUG", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import User, UserRole  # noqa: F401  (enregistre les tables)
from app.repositories.user_repository import UserRepository
from app.utils.hashing import hash_password

TEST_PASSWORD = "Passw0rd!"


@pytest.fixture()
def engine():
    """Base SQLite en memoire, recreee pour chaque test."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture()
def db_session(engine) -> Session:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session) -> TestClient:
    """Client HTTP dont la dependance get_db pointe vers la base de test."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def make_user(db_session):
    """Fabrique de comptes de test."""

    def _make(
        email: str,
        role: UserRole,
        *,
        full_name: str = "Compte Test",
        company_name: str | None = None,
        is_active: bool = True,
    ) -> User:
        repo = UserRepository(db_session)
        user = repo.create(
            email=email,
            hashed_password=hash_password(TEST_PASSWORD),
            full_name=full_name,
            role=role,
            company_name=company_name,
        )
        if not is_active:
            repo.set_active(user, False)
        return user

    return _make


@pytest.fixture()
def auth_headers(client):
    """Retourne l'en-tete Authorization pour un email donne."""

    def _headers(email: str, password: str = TEST_PASSWORD) -> dict[str, str]:
        response = client.post(
            "/auth/login/json", json={"email": email, "password": password}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _headers


# --- Comptes prets a l'emploi ---------------------------------------

@pytest.fixture()
def student(make_user) -> User:
    return make_user("eleve@dsia.fr", UserRole.STUDENT, full_name="Eleve DSIA")


@pytest.fixture()
def company_a(make_user) -> User:
    return make_user(
        "a@boite.fr", UserRole.COMPANY, full_name="Boite A", company_name="Boite A"
    )


@pytest.fixture()
def company_b(make_user) -> User:
    return make_user(
        "b@boite.fr", UserRole.COMPANY, full_name="Boite B", company_name="Boite B"
    )


@pytest.fixture()
def manager(make_user) -> User:
    return make_user("resp@dsia.fr", UserRole.PROGRAM_MANAGER, full_name="Responsable")


@pytest.fixture()
def admin(make_user) -> User:
    return make_user("admin@dsia.fr", UserRole.ADMIN, full_name="Admin")
