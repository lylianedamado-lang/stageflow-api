from collections.abc import Sequence

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.role import UserRole
from app.models.user import User


class UserRepository:
    """Seul point d'acces SQL aux comptes utilisateurs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Lecture -----------------------------------------------------

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        return self.db.execute(stmt).scalar_one_or_none()

    def email_exists(self, email: str) -> bool:
        return self.get_by_email(email) is not None

    def list_all(self, *, limit: int = 20, offset: int = 0) -> Sequence[User]:
        stmt = select(User).order_by(User.id).limit(limit).offset(offset)
        return self.db.execute(stmt).scalars().all()

    def count(self) -> int:
        return self.db.execute(select(func.count(User.id))).scalar_one()

    # --- Ecriture ----------------------------------------------------

    def create(
        self,
        *,
        email: str,
        hashed_password: str,
        full_name: str,
        role: UserRole,
        company_name: str | None = None,
    ) -> User:
        user = User(
            email=email.lower(),
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
            company_name=company_name,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_role(self, user: User, new_role: UserRole) -> User:
        user.role = new_role
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_active(self, user: User, is_active: bool) -> User:
        user.is_active = is_active
        self.db.commit()
        self.db.refresh(user)
        return user


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    """Fournit un repository deja relie a la session de la requete."""
    return UserRepository(db)
