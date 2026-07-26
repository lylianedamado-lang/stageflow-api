from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# SQLite refuse par defaut d'etre utilise depuis plusieurs threads.
# FastAPI etant multi-thread, on desactive cette verification pour SQLite uniquement.
connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Dependance FastAPI : ouvre une session par requete et la ferme toujours."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
