from enum import Enum


class UserRole(str, Enum):
    """Rôles applicatifs de StageFlow."""

    STUDENT = "student"
    COMPANY = "company"
    PROGRAM_MANAGER = "program_manager"
    ADMIN = "admin"
