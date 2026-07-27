from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# SQLite refuse par défaut d'être utilisé depuis plusieurs threads.
# FastAPI étant multi-thread, on désactive cette vérification pour SQLite uniquement.
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


def get_db():
    """Dépendance FastAPI : ouvre une session par requête et la ferme toujours."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
