from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.role import UserRole

# bcrypt ignore silencieusement au-dela de 72 octets : on borne en amont.
PASSWORD_MIN = 8
PASSWORD_MAX = 72


class UserCreate(BaseModel):
    """DTO d'entree : inscription publique."""

    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
    full_name: str = Field(min_length=2, max_length=150)
    role: UserRole = UserRole.STUDENT
    company_name: str | None = Field(default=None, max_length=150)

    @model_validator(mode="after")
    def check_role_and_company(self) -> "UserCreate":
        # Un compte a privileges ne peut jamais etre cree par inscription libre.
        if self.role in (UserRole.PROGRAM_MANAGER, UserRole.ADMIN):
            raise ValueError(
                "L'inscription publique n'autorise que les roles student et company"
            )
        if self.role is UserRole.COMPANY and not self.company_name:
            raise ValueError("company_name est obligatoire pour un compte entreprise")
        if self.role is not UserRole.COMPANY and self.company_name:
            raise ValueError("company_name est reserve aux comptes entreprise")
        return self


class UserRead(BaseModel):
    """DTO de sortie : jamais de hashed_password ici."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    company_name: str | None
    is_active: bool
    created_at: datetime


class UserRoleUpdate(BaseModel):
    """DTO d'entree : changement de role, reserve a l'admin."""

    role: UserRole
