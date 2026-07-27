from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Erreur applicative de base, traduite en réponse HTTP par un handler."""

    status_code: int = 500
    default_detail: str = "Erreur interne du serveur"
    error_code: str = "internal_error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class BusinessRuleError(AppError):
    """400 - une règle métier n'est pas respectée."""

    status_code = 400
    default_detail = "Règle métier non respectée"
    error_code = "business_rule_violation"


class AuthenticationError(AppError):
    """401 - identité non établie ou jeton invalide."""

    status_code = 401
    default_detail = "Authentification requise"
    error_code = "unauthenticated"


class PermissionDeniedError(AppError):
    """403 - identité connue mais habilitation insuffisante."""

    status_code = 403
    default_detail = "Accès non autorisé"
    error_code = "forbidden"


class NotFoundError(AppError):
    """404 - ressource absente ou non visible pour cet utilisateur."""

    status_code = 404
    default_detail = "Ressource introuvable"
    error_code = "not_found"


def register_exception_handlers(app: FastAPI) -> None:
    """Traduit toute AppError en réponse JSON homogène."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "detail": exc.detail,
                "path": request.url.path,
            },
            headers=(
                {"WWW-Authenticate": "Bearer"}
                if exc.status_code == 401
                else None
            ),
        )